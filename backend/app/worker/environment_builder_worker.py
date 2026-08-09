"""环境构建 Worker（Phase 1）——单进程单任务，DB 是任务事实源，Redis list 只负责唤醒。

状态机：
    queued → building → succeeded
                      ↘ failed
                      ↘ timed_out

执行流程：
1. 条件更新 claim 构建任务（UPDATE ... WHERE status='queued'，rowcount 防并发抢占）
2. 生成 job 专属临时 tag（不覆盖已发布标签）
3. 流式读取构建日志（subprocess argv，禁止 shell），逐行脱敏入库 + 刷新 lease
4. 构建超时（> DAI_ENV_BUILD_TIMEOUT_SECONDS）→ timed_out
5. 构建成功后离线 smoke（import + pip freeze）→ 捕获 image ID digest
6. 事务内写入 digest、冻结 resolved package manifest、版本转 available
7. 仅全部验证完成后添加正式 dai-env-<slug>:vN 标签
8. 失败不修改旧 current available 版本；显式重试由管理 API（Phase 2）创建新 job 并关联 retry_of_id
"""
from __future__ import annotations

import json as _json
import logging
import os
import socket
import time
from datetime import timedelta

from sqlalchemy import select, update

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import EnvironmentBuildJob, EnvironmentProfile, EnvironmentVersion
from app.services.environment_builder import (
    BuildFailure,
    BuildResult,
    BuildTimeout,
    _docker_tag,
    canonical_build_spec,
    execute_build,
    redact_build_log,
    render_dockerfile,
    spec_dockerfile_sha256,
    truncate_build_log,
)
from app.services.environment_service import get_packages_for_version
from app.services.time_utils import as_utc, utc_now

logger = logging.getLogger("dai.worker.env_build")

# lease 时长：Worker 崩溃后其他实例可接管；总构建时长上限来自 settings.env_build_timeout_seconds
LEASE_SECONDS = 60


def _fail(db, job: EnvironmentBuildJob, status: str, exc: BuildFailure, now) -> str:
    job.status = status
    job.error_code = exc.code
    job.error_message = str(exc)[:500]
    job.finished_at = now
    db.commit()
    return status


def claim_build_job(db, job_id: int, owner_id: str, now) -> bool:
    """条件更新抢占任务——并发 Worker 只有一个 claim 成功（rowcount==1）。"""
    result = db.execute(
        update(EnvironmentBuildJob)
        .where(
            EnvironmentBuildJob.id == job_id,
            EnvironmentBuildJob.status == "queued",
        )
        .values(
            status="building",
            worker_id=owner_id,
            started_at=now,
            heartbeat_at=now,
            lease_until=now + timedelta(seconds=LEASE_SECONDS),
        )
    )
    db.commit()
    if result.rowcount != 1:
        return False
    job = db.get(EnvironmentBuildJob, job_id)
    if job is not None:
        db.refresh(job)  # update 语句不同步已加载对象，刷新使调用方可见 building 状态
    return True


def process_build(
    db,
    settings: Settings,
    owner_id: str,
    job_id: int,
    now=None,
) -> str:
    """执行一个已 claim 的构建任务，返回终态（succeeded / failed / timed_out）。"""
    now = now or utc_now()
    job = db.get(EnvironmentBuildJob, job_id)
    if job is None or job.status != "building":
        return job.status if job else "missing"

    version = db.get(EnvironmentVersion, job.environment_version_id)
    if version is None:
        return _fail(db, job, "failed", BuildFailure("环境版本不存在", code="VERSION_MISSING"), now)
    profile = db.get(EnvironmentProfile, version.profile_id)
    packages = get_packages_for_version(db, version.id)
    spec = canonical_build_spec(
        base_image_ref=version.base_image_ref,
        profile_slug=profile.slug if profile else "unknown",
        version_number=version.version_number,
        packages=packages,
        settings=settings,
    )
    dockerfile = render_dockerfile(spec)
    temp_tag = f"{settings.env_image_repository}:build-job-{job.id}"

    logs: list[str] = []

    def on_log(line: str) -> None:
        """逐行回调：脱敏 + 60 KiB 尾部截断后入库，并刷新 lease（崩溃恢复依据）"""
        logs.append(line)
        joined = redact_build_log("\n".join(logs))
        job.log_text = truncate_build_log(joined, settings.env_build_log_max_bytes)
        job.heartbeat_at = utc_now()
        job.lease_until = job.heartbeat_at + timedelta(seconds=LEASE_SECONDS)
        db.commit()

    try:
        result: BuildResult = execute_build(
            spec, settings, on_log=on_log, temp_tag=temp_tag, dockerfile_text=dockerfile
        )
    except BuildTimeout as exc:
        return _fail(db, job, "timed_out", exc, now)
    except BuildFailure as exc:
        return _fail(db, job, "failed", exc, now)
    except Exception as exc:  # noqa: BLE001 —— Worker 未知异常也落 failed，避免任务丢失
        logger.exception("构建任务 %s 未知异常", job_id)
        return _fail(db, job, "failed", BuildFailure(f"Worker 未知异常: {exc}", code="WORKER_ERROR"), now)

    # 成功：事务内冻结 digest + 版本转 available
    version.status = "available"
    version.image_digest = result.image_digest
    version.image_tag = spec.image_tag
    version.python_version = spec.python_version
    version.dockerfile_sha256 = spec_dockerfile_sha256(dockerfile)
    version.resolved_packages = result.resolved_packages
    version.available_at = now
    job.status = "succeeded"
    job.finished_at = now
    db.commit()
    logger.info("环境 %s v%s 构建成功: %s", spec.profile_slug, version.version_number, result.image_digest)

    # 正式标签：digest 才是运行事实源，标签失败不影响可用性
    try:
        _tag_official_image(temp_tag, spec.image_tag)
    except Exception:  # noqa: BLE001
        logger.warning("正式标签 %s 添加失败（digest 仍可用）", spec.image_tag)
    return "succeeded"


def _tag_official_image(temp_tag: str, image_tag: str) -> None:
    """仅全部验证完成后添加正式 dai-env-<slug>:vN 标签。"""
    _docker_tag(temp_tag, image_tag)


def recover_stale_builds(db, settings: Settings, now, redis_client=None) -> dict:
    """恢复 building 但 lease 过期的任务（Worker 崩溃）：

    - 总时长超过 timeout → timed_out
    - 否则回 queued（其他 Worker 可重新 claim 继续），并重新推送 Redis 唤醒消息——
      Redis list 只负责唤醒，原消息可能已被崩溃 Worker 消费，必须补一条否则任务永久卡住
    """
    stats = {"requeued": 0, "timed_out": 0}
    stale = db.scalars(
        select(EnvironmentBuildJob).where(
            EnvironmentBuildJob.status == "building",
            EnvironmentBuildJob.lease_until.is_not(None),
            EnvironmentBuildJob.lease_until < now,
        )
    ).all()
    for job in stale:
        started = as_utc(job.started_at)
        if started is not None and (now - started).total_seconds() > settings.env_build_timeout_seconds:
            job.status = "timed_out"
            job.error_code = "BUILD_TIMEOUT"
            job.error_message = "构建超过时限"
            job.finished_at = now
            stats["timed_out"] += 1
        else:
            job.status = "queued"
            job.worker_id = None
            job.lease_until = None
            stats["requeued"] += 1
            if redis_client is not None:
                redis_client.rpush(
                    settings.env_build_queue_name,
                    _json.dumps({"type": "env_build", "version_id": job.environment_version_id}),
                )
    db.commit()
    return stats


def _find_pending_job(db, version_id: int) -> EnvironmentBuildJob | None:
    """版本最新一次 queued 任务（attempt_number 最大）。"""
    return db.scalar(
        select(EnvironmentBuildJob)
        .where(
            EnvironmentBuildJob.environment_version_id == version_id,
            EnvironmentBuildJob.status == "queued",
        )
        .order_by(EnvironmentBuildJob.attempt_number.desc())
        .limit(1)
    )


def run_once(db, redis_client, settings: Settings, owner_id: str) -> bool:
    """处理一条队列消息，返回是否消费了消息。Redis 只负责唤醒。"""
    result = redis_client.blpop(settings.env_build_queue_name, timeout=1)
    if result is None:
        return False
    _queue_name, raw_data = result
    try:
        payload = _json.loads(raw_data)
    except Exception:
        logger.warning("无法解析环境构建消息: %s", str(raw_data)[:100])
        return True
    version_id = payload.get("version_id")
    if not version_id:
        return True
    job = _find_pending_job(db, version_id)
    if job is None:
        return True
    if not claim_build_job(db, job.id, owner_id, utc_now()):
        return True
    try:
        process_build(db, settings, owner_id, job.id)
    except Exception:  # noqa: BLE001
        logger.exception("构建任务 %s 主流程异常", job.id)
        fresh = db.get(EnvironmentBuildJob, job.id)
        if fresh is not None and fresh.status == "building":
            _fail(db, fresh, "failed", BuildFailure("Worker 主流程异常", code="WORKER_ERROR"), utc_now())
    return True


def run_worker_loop() -> None:
    """主循环：单进程单任务；每 60 秒做一次崩溃恢复扫描。"""
    import redis as _redis

    settings = get_settings()
    redis_client = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
    owner_id = f"env-builder:{socket.gethostname()}:{os.getpid()}"
    logger.info("环境构建 Worker 启动，队列: %s，owner=%s", settings.env_build_queue_name, owner_id)

    last_recovery = time.monotonic()
    while True:
        try:
            with SessionLocal() as db:
                if time.monotonic() - last_recovery > 60:
                    stats = recover_stale_builds(db, settings, utc_now(), redis_client=redis_client)
                    if any(stats.values()):
                        logger.info("构建崩溃恢复: %s", stats)
                    last_recovery = time.monotonic()
                run_once(db, redis_client, settings, owner_id)
        except Exception:  # noqa: BLE001
            logger.exception("环境构建主循环异常")
            time.sleep(1)


if __name__ == "__main__":
    run_worker_loop()
