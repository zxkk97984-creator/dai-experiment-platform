"""环境构建 Worker（Phase 1）——单进程单任务，DB 是任务事实源，Redis list 只负责唤醒。

状态机：
    draft → queued → building → succeeded
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
import secrets
import socket
import threading
import time
from datetime import timedelta

from sqlalchemy import select, update

from app.config import Settings, get_settings
from app.database import SessionLocal, sessionmaker_for_engine
from app.models import EnvironmentBuildJob, EnvironmentDraft, EnvironmentProfile, EnvironmentVersion
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
from app.services.environment_builder_v2 import (
    V2BuildFailure,
    V2BuildResult,
    V2BuildTimeout,
    canonical_v2_manifest,
    build_config_fingerprint,
    execute_v2_build,
)
from app.services.environment_candidates import refresh_apt_candidate_cache
from app.services.environment_service import get_packages_for_version
from app.services.environment_spec import SUPPORTED_PYTHON_VERSIONS
from app.services.time_utils import as_utc, utc_now

logger = logging.getLogger("dai.worker.env_build")

# lease 时长：Worker 崩溃后其他实例可接管；总构建时长上限来自 settings.env_build_timeout_seconds
LEASE_SECONDS = 60
APT_CACHE_REFRESH_SECONDS = 6 * 60 * 60


class LeaseLost(RuntimeError):
    """Raised when a Worker no longer owns the DB lease for a build job."""


class LeaseGuard:
    """Refresh a build lease from an independent short-lived DB session.

    The main build session is also used for phase/log CAS updates.  A separate
    session is required here because Docker can run for minutes without
    producing output and SQLAlchemy sessions are not thread-safe.
    """

    def __init__(self, bind, job_id: int, owner_id: str, lease_token: str):
        self._session_factory = sessionmaker_for_engine(bind)
        self.job_id = job_id
        self.owner_id = owner_id
        self.lease_token = lease_token
        self.lost = threading.Event()
        self._stop = threading.Event()
        self._process_lock = threading.Lock()
        self._process = None
        self._thread = threading.Thread(
            target=self._run,
            name=f"env-build-lease-{job_id}",
            daemon=True,
        )

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb):
        self._stop.set()
        self._thread.join(timeout=2)
        self._kill_process_if_needed()

    def register_process(self, process):
        with self._process_lock:
            self._process = process
            lost = self.lost.is_set()
        if lost:
            self._kill_process_if_needed()

    def unregister_process(self, process):
        with self._process_lock:
            if self._process is process:
                self._process = None

    def assert_owned(self):
        if self.lost.is_set():
            raise LeaseLost(f"build job {self.job_id} lease is no longer owned")

    def _kill_process_if_needed(self):
        with self._process_lock:
            process = self._process
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

    def _run(self):
        interval = max(1, LEASE_SECONDS // 3)
        while not self._stop.wait(interval):
            try:
                with self._session_factory() as db:
                    result = db.execute(
                        update(EnvironmentBuildJob)
                        .where(
                            EnvironmentBuildJob.id == self.job_id,
                            EnvironmentBuildJob.status == "building",
                            EnvironmentBuildJob.worker_id == self.owner_id,
                            EnvironmentBuildJob.lease_token == self.lease_token,
                        )
                        .values(
                            heartbeat_at=utc_now(),
                            lease_until=utc_now() + timedelta(seconds=LEASE_SECONDS),
                        )
                    )
                    if result.rowcount != 1:
                        db.rollback()
                        self.lost.set()
                        self._kill_process_if_needed()
                        return
                    db.commit()
            except Exception:  # noqa: BLE001 - lease loss is fail-closed
                logger.exception("构建任务 %s heartbeat 失败", self.job_id)
                self.lost.set()
                self._kill_process_if_needed()
                return


def _mark_version_failed(db, version_id: int) -> None:
    """把当前未可用版本收敛到 failed，不回退已发布版本。"""
    version = db.get(EnvironmentVersion, version_id)
    if version is not None and version.status not in ("available", "inactive"):
        version.status = "failed"


def _mark_v2_draft_failed(db, version_id: int, job_id: int | None = None) -> None:
    """Release a V2 draft when recovery discovers a terminal failed attempt."""

    version = db.get(EnvironmentVersion, version_id)
    if version is None:
        return
    draft = db.get(EnvironmentDraft, version.profile_id)
    if draft is None:
        return
    if draft.candidate_version_id == version.id and (
        job_id is None or draft.active_build_job_id == job_id
    ):
        draft.active_build_job_id = None
        draft.state = "failed"


def _redact_error_detail(value):
    """Redact nested V2 stderr/details before they are persisted as JSON."""

    if isinstance(value, str):
        return redact_build_log(value)
    if isinstance(value, dict):
        return {str(key): _redact_error_detail(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_error_detail(item) for item in value]
    return value


def _cleanup_temp_image(temp_tag: str | None) -> None:
    if not temp_tag:
        return
    try:
        import subprocess

        subprocess.run(
            ["docker", "image", "rm", "--force", temp_tag],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:  # noqa: BLE001 - cleanup must not hide the lease result
        logger.warning("无法清理临时环境镜像 %s", temp_tag, exc_info=True)


def _touch_job_lease(
    db,
    *,
    job_id: int,
    owner_id: str,
    lease_token: str,
    phase: str | None = None,
    log_text: str | None = None,
) -> None:
    values = {
        "heartbeat_at": utc_now(),
        "lease_until": utc_now() + timedelta(seconds=LEASE_SECONDS),
    }
    if phase is not None:
        values["phase"] = phase
    if log_text is not None:
        values["log_text"] = log_text
    result = db.execute(
        update(EnvironmentBuildJob)
        .where(
            EnvironmentBuildJob.id == job_id,
            EnvironmentBuildJob.status == "building",
            EnvironmentBuildJob.worker_id == owner_id,
            EnvironmentBuildJob.lease_token == lease_token,
        )
        .values(**values)
    )
    if result.rowcount != 1:
        db.rollback()
        raise LeaseLost(f"build job {job_id} lease is no longer owned")
    db.commit()


def _fail(
    db,
    job: EnvironmentBuildJob,
    status: str,
    exc: BuildFailure,
    now,
    *,
    owner_id: str,
    lease_token: str,
    temp_tag: str | None = None,
) -> str:
    result = db.execute(
        update(EnvironmentBuildJob)
        .where(
            EnvironmentBuildJob.id == job.id,
            EnvironmentBuildJob.status == "building",
            EnvironmentBuildJob.worker_id == owner_id,
            EnvironmentBuildJob.lease_token == lease_token,
        )
        .values(
            status=status,
            error_code=exc.code,
            error_message=str(exc)[:500],
            phase="done",
            finished_at=now,
            lease_until=None,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        _cleanup_temp_image(temp_tag)
        return "lease_lost"
    _mark_version_failed(db, job.environment_version_id)
    db.commit()
    _cleanup_temp_image(temp_tag)
    return status


def claim_build_job(db, job_id: int, owner_id: str, now) -> bool:
    """条件更新抢占任务——并发 Worker 只有一个 claim 成功（rowcount==1）。"""
    lease_token = secrets.token_urlsafe(32)
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
            lease_token=lease_token,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        return False
    job = db.get(EnvironmentBuildJob, job_id)
    if job is not None:
        db.refresh(job)  # update 语句不同步已加载对象，刷新使调用方可见 building 状态
        version = db.get(EnvironmentVersion, job.environment_version_id)
        if version is not None and version.status not in ("available", "inactive"):
            version.status = "building"
    db.commit()
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
    if job.build_mode == "v2":
        return process_v2_build(db, settings, owner_id, job_id, now=now)
    if job.build_mode != "legacy":
        return _fail(
            db,
            job,
            "failed",
            BuildFailure("未知构建模式", code="BUILD_MODE_INVALID"),
            now,
            owner_id=owner_id,
            lease_token=job.lease_token or "",
        )
    lease_token = job.lease_token
    if not lease_token:
        return "lease_lost"

    version = db.get(EnvironmentVersion, job.environment_version_id)
    if version is None:
        return _fail(
            db,
            job,
            "failed",
            BuildFailure("环境版本不存在", code="VERSION_MISSING"),
            now,
            owner_id=owner_id,
            lease_token=lease_token,
        )
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
        _touch_job_lease(
            db,
            job_id=job.id,
            owner_id=owner_id,
            lease_token=lease_token,
            log_text=truncate_build_log(joined, settings.env_build_log_max_bytes),
        )

    try:
        with LeaseGuard(db.get_bind(), job.id, owner_id, lease_token) as lease:
            result: BuildResult = execute_build(
                spec,
                settings,
                on_log=on_log,
                temp_tag=temp_tag,
                dockerfile_text=dockerfile,
                lease_check=lease.assert_owned,
                register_process=lease.register_process,
                unregister_process=lease.unregister_process,
            )
            lease.assert_owned()
    except LeaseLost:
        _cleanup_temp_image(temp_tag)
        return "lease_lost"
    except BuildTimeout as exc:
        return _fail(
            db, job, "timed_out", exc, now,
            owner_id=owner_id, lease_token=lease_token, temp_tag=temp_tag,
        )
    except BuildFailure as exc:
        return _fail(
            db, job, "failed", exc, now,
            owner_id=owner_id, lease_token=lease_token, temp_tag=temp_tag,
        )
    except Exception as exc:  # noqa: BLE001 —— Worker 未知异常也落 failed，避免任务丢失
        logger.exception("构建任务 %s 未知异常", job_id)
        return _fail(
            db,
            job,
            "failed",
            BuildFailure(f"Worker 未知异常: {exc}", code="WORKER_ERROR"),
            now,
            owner_id=owner_id,
            lease_token=lease_token,
            temp_tag=temp_tag,
        )

    # 成功：先以 lease CAS 锁定终态，再写入版本，防止旧 Worker 覆盖新尝试。
    result_update = db.execute(
        update(EnvironmentBuildJob)
        .where(
            EnvironmentBuildJob.id == job.id,
            EnvironmentBuildJob.status == "building",
            EnvironmentBuildJob.worker_id == owner_id,
            EnvironmentBuildJob.lease_token == lease_token,
        )
        .values(
            status="succeeded",
            error_code=None,
            error_message=None,
            phase="done",
            lease_until=None,
            finished_at=now,
        )
    )
    if result_update.rowcount != 1:
        db.rollback()
        _cleanup_temp_image(temp_tag)
        return "lease_lost"
    version.status = "available"
    version.image_digest = result.image_digest
    version.image_tag = spec.image_tag
    version.python_version = spec.python_version
    version.dockerfile_sha256 = spec_dockerfile_sha256(dockerfile)
    version.resolved_packages = result.resolved_packages
    version.available_at = now
    db.commit()
    logger.info("环境 %s v%s 构建成功: %s", spec.profile_slug, version.version_number, result.image_digest)

    # 正式标签：digest 才是运行事实源，标签失败不影响可用性
    try:
        _tag_official_image(temp_tag, spec.image_tag)
    except Exception:  # noqa: BLE001
        logger.warning("正式标签 %s 添加失败（digest 仍可用）", spec.image_tag)
    return "succeeded"


def process_v2_build(
    db,
    settings: Settings,
    owner_id: str,
    job_id: int,
    now=None,
) -> str:
    """Run the V2 phased resolver/build flow and update the Draft state."""

    now = now or utc_now()
    job = db.get(EnvironmentBuildJob, job_id)
    if job is None or job.status != "building":
        return job.status if job else "missing"
    if job.build_mode != "v2":
        return process_build(db, settings, owner_id, job_id, now=now)
    lease_token = job.lease_token
    if not lease_token:
        return "lease_lost"
    version = db.get(EnvironmentVersion, job.environment_version_id)
    profile = db.get(EnvironmentProfile, version.profile_id) if version else None
    if version is None or profile is None:
        return _fail(
            db,
            job,
            "failed",
            BuildFailure("环境版本或档位不存在", code="VERSION_MISSING"),
            now,
            owner_id=owner_id,
            lease_token=lease_token,
        )

    def set_phase(phase: str) -> None:
        _touch_job_lease(
            db,
            job_id=job.id,
            owner_id=owner_id,
            lease_token=lease_token,
            phase=phase,
        )

    logs: list[str] = []

    def on_log(line: str) -> None:
        logs.append(line)
        _touch_job_lease(
            db,
            job_id=job.id,
            owner_id=owner_id,
            lease_token=lease_token,
            log_text=truncate_build_log(
                redact_build_log("\n".join(logs)), settings.env_build_log_max_bytes
            ),
        )

    temp_tag = f"{settings.env_image_repository}:v2-build-job-{job.id}"
    try:
        with LeaseGuard(db.get_bind(), job.id, owner_id, lease_token) as lease:
            expected_fingerprint = build_config_fingerprint(version.python_version, settings)
            if (
                job.build_config_fingerprint is not None
                and job.build_config_fingerprint != expected_fingerprint
            ):
                raise V2BuildFailure(
                    "Worker 构建配置与任务快照不一致",
                    code="BUILD_CONFIG_MISMATCH",
                    detail={"expected": job.build_config_fingerprint, "actual": expected_fingerprint},
                )
            manifest = canonical_v2_manifest(
                base_image_ref=version.base_image_ref,
                python_version=version.python_version,
                minimum_memory_mb=version.minimum_memory_mb,
                requested_spec=version.requested_spec,
                settings=settings,
            )
            if manifest["manifest_sha256"] != version.manifest_sha256:
                raise V2BuildFailure(
                    "环境版本 manifest 与构建输入不一致",
                    code="BUILD_VALIDATION_FAILED",
                    detail={"expected": version.manifest_sha256, "actual": manifest["manifest_sha256"]},
                )
            result: V2BuildResult = execute_v2_build(
                manifest,
                settings,
                on_phase=set_phase,
                on_log=on_log,
                timeout=settings.env_build_timeout_seconds,
                temp_tag=temp_tag,
                lease_check=lease.assert_owned,
                register_process=lease.register_process,
                unregister_process=lease.unregister_process,
            )
            lease.assert_owned()
    except LeaseLost:
        _cleanup_temp_image(temp_tag)
        return "lease_lost"
    except V2BuildTimeout as exc:
        return _fail_v2(
            db, job, "timed_out", exc, now,
            owner_id=owner_id, lease_token=lease_token, temp_tag=temp_tag,
        )
    except V2BuildFailure as exc:
        return _fail_v2(
            db, job, "failed", exc, now,
            owner_id=owner_id, lease_token=lease_token, temp_tag=temp_tag,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("V2 构建任务 %s 未知异常", job_id)
        return _fail_v2(
            db,
            job,
            "failed",
            V2BuildFailure(f"Worker 未知异常: {exc}", code="WORKER_ERROR"),
            now,
            owner_id=owner_id,
            lease_token=lease_token,
            temp_tag=temp_tag,
        )

    # finalizing 也必须先通过同一 lease CAS；旧 Worker 不得更新版本或草稿。
    result_update = db.execute(
        update(EnvironmentBuildJob)
        .where(
            EnvironmentBuildJob.id == job.id,
            EnvironmentBuildJob.status == "building",
            EnvironmentBuildJob.worker_id == owner_id,
            EnvironmentBuildJob.lease_token == lease_token,
        )
        .values(
            status="succeeded",
            phase="done",
            error_code=None,
            error_message=None,
            error_detail=None,
            result_summary=result.result_summary,
            lease_until=None,
            finished_at=now,
        )
    )
    if result_update.rowcount != 1:
        db.rollback()
        _cleanup_temp_image(temp_tag)
        return "lease_lost"
    version.status = "available"
    version.image_digest = result.image_digest
    version.dockerfile_sha256 = result.dockerfile_sha256
    version.resolved_spec = result.resolved_spec
    version.resolved_packages = {
        item["name"]: item["version"] for item in result.resolved_spec.get("python_lock", [])
    }
    version.available_at = now
    draft = db.get(EnvironmentDraft, profile.id)
    if draft is not None and draft.candidate_version_id == version.id and draft.active_build_job_id == job.id:
        draft.active_build_job_id = None
        draft.state = "ready"
    db.commit()
    logger.info("V2 环境 %s v%s 构建成功: %s", profile.slug, version.version_number, result.image_digest)
    return "succeeded"


def _fail_v2(
    db,
    job: EnvironmentBuildJob,
    status: str,
    exc: V2BuildFailure,
    now,
    *,
    owner_id: str,
    lease_token: str,
    temp_tag: str | None = None,
) -> str:
    result = db.execute(
        update(EnvironmentBuildJob)
        .where(
            EnvironmentBuildJob.id == job.id,
            EnvironmentBuildJob.status == "building",
            EnvironmentBuildJob.worker_id == owner_id,
            EnvironmentBuildJob.lease_token == lease_token,
        )
        .values(
            status=status,
            phase="done",
            error_code=exc.code,
            error_message=str(exc)[:500],
            error_detail=_redact_error_detail(exc.detail) if exc.detail else None,
            finished_at=now,
            lease_until=None,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        _cleanup_temp_image(temp_tag)
        return "lease_lost"
    _mark_version_failed(db, job.environment_version_id)
    version = db.get(EnvironmentVersion, job.environment_version_id)
    if version is not None:
        draft = db.get(EnvironmentDraft, version.profile_id)
        if draft is not None and draft.active_build_job_id == job.id:
            draft.active_build_job_id = None
            draft.state = "failed"
    db.commit()
    _cleanup_temp_image(temp_tag)
    return status


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
        timed_out = (
            started is not None
            and (now - started).total_seconds() > settings.env_build_timeout_seconds
        )
        values = (
            {
                "status": "timed_out",
                "phase": "done",
                "error_code": "BUILD_TIMEOUT",
                "error_message": "构建超过时限",
                "lease_until": None,
                "lease_token": None,
                "finished_at": now,
            }
            if timed_out
            else {
                "status": "queued",
                "phase": "queued" if job.build_mode == "v2" else job.phase,
                "worker_id": None,
                "lease_until": None,
                "lease_token": None,
            }
        )
        result = db.execute(
            update(EnvironmentBuildJob)
            .where(
                EnvironmentBuildJob.id == job.id,
                EnvironmentBuildJob.status == "building",
                EnvironmentBuildJob.lease_until.is_not(None),
                EnvironmentBuildJob.lease_until < now,
                EnvironmentBuildJob.worker_id == job.worker_id,
                EnvironmentBuildJob.lease_token == job.lease_token,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            continue
        if timed_out:
            _mark_version_failed(db, job.environment_version_id)
            if job.build_mode == "v2":
                _mark_v2_draft_failed(db, job.environment_version_id, job.id)
            stats["timed_out"] += 1
        else:
            version = db.get(EnvironmentVersion, job.environment_version_id)
            if version is not None and version.status not in ("available", "inactive"):
                version.status = "queued"
            stats["requeued"] += 1
            if redis_client is not None:
                _enqueue_build_wakeup(redis_client, settings, job.environment_version_id)
    db.commit()
    return stats


def _enqueue_build_wakeup(redis_client, settings: Settings, version_id: int) -> bool:
    """向 Redis 推送一次版本唤醒消息；已有同版本消息时避免重复。"""
    if redis_client is None:
        return False
    try:
        for raw_data in redis_client.lrange(settings.env_build_queue_name, 0, -1):
            try:
                payload = _json.loads(raw_data)
            except Exception:  # noqa: BLE001 - 坏消息不应阻止当前任务唤醒
                continue
            if payload.get("version_id") == version_id:
                return False
        redis_client.rpush(
            settings.env_build_queue_name,
            _json.dumps({"type": "env_build", "version_id": version_id}),
        )
        return True
    except Exception:  # noqa: BLE001 - DB 状态保留 queued，后续对账继续尝试
        logger.warning("无法唤醒环境构建任务 version_id=%s", version_id, exc_info=True)
        return False


def reconcile_build_state(db, settings: Settings, redis_client=None) -> dict:
    """以 DB 任务事实源修复 Redis 丢消息和版本状态漂移。

    Worker 重启或 Redis 短暂不可用后，queued 任务可能没有唤醒消息；同时旧版
    Worker 在失败时只更新 job，导致 version 永久停在 queued。本函数只把已有
    任务重新唤醒，或把已有失败终态同步到 version，不伪造 succeeded/available。
    """
    stats = {"requeued": 0, "versions_failed": 0, "errors_cleared": 0}

    succeeded_jobs = db.scalars(
        select(EnvironmentBuildJob).where(
            EnvironmentBuildJob.status == "succeeded",
            (EnvironmentBuildJob.error_code.is_not(None) | EnvironmentBuildJob.error_message.is_not(None)),
        )
    ).all()
    for job in succeeded_jobs:
        version = db.get(EnvironmentVersion, job.environment_version_id)
        if version is not None and version.status == "available" and version.image_digest:
            job.error_code = None
            job.error_message = None
            stats["errors_cleared"] += 1

    queued_jobs = db.scalars(
        select(EnvironmentBuildJob).where(EnvironmentBuildJob.status == "queued")
    ).all()
    for job in queued_jobs:
        if _enqueue_build_wakeup(redis_client, settings, job.environment_version_id):
            stats["requeued"] += 1

    queued_versions = db.scalars(
        select(EnvironmentVersion).where(EnvironmentVersion.status == "queued")
    ).all()
    for version in queued_versions:
        active_job = db.scalar(
            select(EnvironmentBuildJob.id)
            .where(
                EnvironmentBuildJob.environment_version_id == version.id,
                EnvironmentBuildJob.status.in_(["queued", "building"]),
            )
            .limit(1)
        )
        if active_job is not None:
            continue
        latest_job = db.scalar(
            select(EnvironmentBuildJob)
            .where(EnvironmentBuildJob.environment_version_id == version.id)
            .order_by(EnvironmentBuildJob.created_at.desc(), EnvironmentBuildJob.id.desc())
            .limit(1)
        )
        if latest_job is not None and latest_job.status in ("failed", "timed_out"):
            version.status = "failed"
            if job.build_mode == "v2":
                _mark_v2_draft_failed(db, version.id, latest_job.id)
            stats["versions_failed"] += 1
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
        if fresh is not None and fresh.status == "building" and fresh.lease_token:
            _fail(
                db,
                fresh,
                "failed",
                BuildFailure("Worker 主流程异常", code="WORKER_ERROR"),
                utc_now(),
                owner_id=owner_id,
                lease_token=fresh.lease_token,
            )
    return True


def run_worker_loop() -> None:
    """主循环：单进程单任务；每 60 秒做一次崩溃恢复扫描。"""
    import redis as _redis

    settings = get_settings()
    redis_client = _redis.Redis.from_url(settings.redis_url, decode_responses=True)
    owner_id = f"env-builder:{socket.gethostname()}:{os.getpid()}"
    logger.info("环境构建 Worker 启动，队列: %s，owner=%s", settings.env_build_queue_name, owner_id)

    with SessionLocal() as db:
        startup_stats = reconcile_build_state(db, settings, redis_client=redis_client)
        if any(startup_stats.values()):
            logger.info("构建启动对账: %s", startup_stats)

    last_recovery = time.monotonic()
    last_apt_refresh = time.monotonic()
    while True:
        try:
            with SessionLocal() as db:
                if time.monotonic() - last_recovery > 60:
                    stats = recover_stale_builds(db, settings, utc_now(), redis_client=redis_client)
                    reconcile_stats = reconcile_build_state(db, settings, redis_client=redis_client)
                    if any(stats.values()) or any(reconcile_stats.values()):
                        logger.info("构建崩溃恢复: %s，对账: %s", stats, reconcile_stats)
                    last_recovery = time.monotonic()
                if (
                    settings.environment_editor_v2_enabled
                    and time.monotonic() - last_apt_refresh > APT_CACHE_REFRESH_SECONDS
                ):
                    _refresh_apt_caches(settings, redis_client)
                    last_apt_refresh = time.monotonic()
                run_once(db, redis_client, settings, owner_id)
        except Exception:  # noqa: BLE001
            logger.exception("环境构建主循环异常")
            time.sleep(1)


def _refresh_apt_caches(settings: Settings, redis_client) -> None:
    for python_version in SUPPORTED_PYTHON_VERSIONS:
        try:
            count = refresh_apt_candidate_cache(
                redis_client,
                settings,
                python_version=python_version,
            )
            if count:
                logger.info("apt 候选缓存刷新完成 Python=%s packages=%s", python_version, count)
        except Exception:  # noqa: BLE001 - indexing is optional; builds remain authoritative
            logger.warning("apt 候选缓存刷新失败 Python=%s", python_version, exc_info=True)


if __name__ == "__main__":
    run_worker_loop()
