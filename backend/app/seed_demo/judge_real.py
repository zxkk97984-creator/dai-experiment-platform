# -*- coding: utf-8 -*-
"""真实 Docker 判题（评审 5）：核心演示链优先走真实 Judge。

实现：复用 app.worker.judge_worker 的低层函数（_write_submission_files、
_run_docker_pytest、_status_from_pytest），在种子进程内直接运行真实判题沙箱，
产出真实 status/score/result_details/stdout/stderr/execution_time_ms。

可用性检测（技术债修复 2026-08-15）：
- Docker 可用 + dai-judge-python 镜像存在 + basic 环境版本 available 且
  image_digest 非空，且 digest 必须能解析为本机真实存在的镜像
  （docker image inspect 成功）——占位 digest（如 sha256:aaa...）不再被
  误判为“真实判题可用”。
- 判题工作目录：优先 settings.judge_work_dir；未配置时落在仓库内
  backend/.judge_work/（宿主机可见，Docker daemon 可挂载），
  避免在沙箱/受限环境里 /tmp 对 daemon 不可见导致空挂载、pytest usage error。

Docker 级失败（returncode >= 125，如镜像不存在/权限拒绝）降级为 Fixture：
上次踩坑：docker 返回 125 “No such image” 时 _status_from_pytest 不会抛异常，
而会得到 system_error 状态，导致种子把整批提交写坏（525 条 system_error）。
任一失败时调用方应降级为 Fixture。
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import EnvironmentVersion, JudgeQuestion, Submission
from app.services.environment_service import current_available_version, resolve_run_image_ref
from app.worker import judge_worker

logger = logging.getLogger("dai.seed_demo.judge_real")


def _seed_judge_work_root(settings: Settings) -> Path:
    """判题工作目录根：优先平台配置；否则仓库内 .judge_work（宿主机可见）。"""
    configured = settings.judge_work_dir
    if configured:
        root = Path(os.fspath(configured))
    else:
        root = Path(__file__).resolve().parents[2] / ".judge_work"  # backend/.judge_work
    root.mkdir(parents=True, exist_ok=True)
    return root


def real_judge_available(db: Session, settings: Settings | None = None) -> tuple[bool, str]:
    """检测真实判题链路是否可用。返回 (可用, 原因说明)。

    关键修复：digest 必须能解析为本机真实镜像（docker image inspect 成功），
    占位 digest（sha256:aaa...）不会误报可用 → 种子自动降级 Fixture。
    """
    settings = settings or get_settings()
    if not shutil.which("docker"):
        return False, "docker 命令不可用"
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", settings.judge_image],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0:
            return False, f"判题镜像 {settings.judge_image} 不存在"
    except Exception as exc:
        return False, f"Docker 检测失败: {exc}"
    basic = current_available_version(db, "basic")
    if basic is None or not basic.image_digest:
        return False, "basic 环境版本不可用（无 available 且 digest 的版本）"
    # digest 必须能解析为本机真实镜像（防占位 digest 误报）
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", basic.image_digest],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0:
            return False, f"basic 环境镜像未构建/占位 digest（{basic.image_digest[:24]}…）"
    except Exception as exc:
        return False, f"环境镜像检测失败: {exc}"
    return True, "真实判题可用"


def judge_submission_real(db: Session, submission: Submission, question: JudgeQuestion) -> bool:
    """对一条提交运行真实判题（legacy 路径：隐藏测试全过/不过）。

    成功返回 True 并写回真实结果；任何失败返回 False（调用方降级 Fixture）。
    注意：本函数不管理队列/Redis，仅执行判题与结果写回。
    """
    settings = get_settings()
    if not real_judge_available(db, settings)[0]:
        return False
    work_root = _seed_judge_work_root(settings)
    workdir = None
    try:
        # 解析运行镜像引用（basic 环境 digest）
        env_id = submission.environment_version_id
        image_ref = None
        if env_id is not None:
            try:
                image_ref = resolve_run_image_ref(db, env_id)
            except Exception:
                image_ref = None
        workdir = Path(tempfile.mkdtemp(prefix="dai-seed-judge-", dir=work_root))
        timeout_s = max(1, min(question.time_limit_ms or 10000, settings.judge_timeout_seconds * 1000) // 1000)
        memory = max(question.memory_limit_mb or 256, 256)
        judge_worker._write_submission_files(workdir, submission, question)
        stdout, stderr, returncode, elapsed = judge_worker._run_docker_pytest(
            workdir, settings, timeout_s, memory,
            host_workdir=workdir,
            image_ref=image_ref,
        )
        # Docker 级失败（镜像缺失/权限/守护进程错误）→ 降级 Fixture，
        # 绝不把 system_error 写进种子数据（技术债修复）。
        if returncode >= 125:
            logger.warning(
                "[真实判题] submission=%s Docker 级失败 rc=%s，降级 Fixture: %s",
                submission.id, returncode, (stderr or "")[-200:],
            )
            return False
        status, score = judge_worker._status_from_pytest(returncode, stdout, stderr)
        submission.status = status
        submission.score = score
        submission.stdout = stdout[-8000:]
        submission.stderr = stderr[-8000:]
        submission.execution_time_ms = elapsed
        submission.grading_status = "completed"
        submission.finished_at = _now_aware()
        submission.result_details = {
            "returncode": returncode,
            "seed_fixture": False,
        }
        db.flush()
        logger.info("[真实判题] submission=%s status=%s score=%s", submission.id, status, score)
        return True
    except Exception as exc:
        logger.warning("[真实判题] submission=%s 失败，降级 Fixture: %s", submission.id, exc)
        return False
    finally:
        if workdir is not None:
            shutil.rmtree(workdir, ignore_errors=True)


def _now_aware():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
