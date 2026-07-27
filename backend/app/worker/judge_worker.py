"""判题 Worker——消费 Redis 队列，执行 Docker 沙箱判题。

使用统一 judge_queue 协议进行状态管理：
  - claim_job: 条件 UPDATE queued→running（原子抢占）
  - complete_job: running→completed
  - fail_job: 重试退回 pending / 终态 system_error
"""

import json as _json
import logging
import math
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import ExamAnswer, ExamQuestion, ExamSubmission, JudgeQuestion, Submission

logger = logging.getLogger("dai.worker")

EXAM_JUDGE_QUEUE = "judge:exam:queue"


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _get_timeout(question: JudgeQuestion, settings: Settings) -> int:
    """超时秒数：ceil(time_limit_ms / 1000)，受全局硬上限约束，至少 1 秒"""
    raw = max(question.time_limit_ms, 1)
    per_question = math.ceil(raw / 1000)
    return max(min(per_question, settings.judge_timeout_seconds), 1)


def _write_submission_files(workdir: Path, submission: Submission, question: JudgeQuestion) -> Path:
    user_code = workdir / "user_code.py"
    test_file = workdir / "test_user_code.py"
    user_code.write_text(submission.code, encoding="utf-8")
    hidden_tests = question.hidden_tests
    if "import user_code" not in hidden_tests and "from user_code" not in hidden_tests:
        hidden_tests = f"import user_code\n\n{hidden_tests}"
    test_file.write_text(hidden_tests, encoding="utf-8")
    return test_file


def _run_docker_pytest(workdir: Path, settings: Settings, timeout_seconds: int,
                       memory_limit_mb: int = 256, test_filename: str = "test_user_code.py") -> tuple[str, str, int, int]:
    """统一 Docker sandbox——唯一入口。正式题用 test_user_code.py，sample 用 test_sample.py"""
    container_name = f"dai-judge-{secrets.token_hex(8)}"
    command = [
        "docker", "run", "--rm", "--name", container_name,
        "--network", "none",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:exec,size=64m",
        "--cpus", str(settings.judge_cpu_limit),
        "--memory", f"{memory_limit_mb}m",
        "--pids-limit", "50",
        "--user", "1000:1000",
        "-v", f"{workdir}:/work:ro",
        "-w", "/work",
        settings.judge_image,
        "python", "-m", "pytest", "-q", "-p", "no:cacheprovider", test_filename,
    ]
    started = time.perf_counter()
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return result.stdout, result.stderr, result.returncode, elapsed_ms
    except subprocess.TimeoutExpired:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
        return "", "Execution timed out", 124, elapsed_ms


def _status_from_pytest(returncode: int, stdout: str, stderr: str) -> tuple[str, float]:
    output = f"{stdout}\n{stderr}"
    if returncode == 0:
        return "accepted", 100
    if returncode == 124:
        return "time_limit_exceeded", 0
    if "AssertionError" in output or "assert " in output:
        return "wrong_answer", 0
    if returncode == 1:
        return "runtime_error", 0
    return "system_error", 0


# ═══════════════════════════════════════════════════════════════
# 判题处理（使用统一 judge_queue 协议）
# ═══════════════════════════════════════════════════════════════

def process_submission(db: Session, redis_client, settings: Settings, submission_id: int) -> Submission:
    """处理普通作业判题——使用统一 judge_queue 状态机"""
    from app.services.judge_queue import claim_job, complete_job, fail_job

    submission = db.get(Submission, submission_id)
    if not submission:
        logger.error("Submission %s 不存在", submission_id)
        raise ValueError(f"Submission {submission_id} does not exist")

    # 幂等：已完成的提交不重复判题
    if submission.grading_status == "completed":
        return submission

    try:
        # 原子抢占：queued → running
        if not claim_job(db, job_type="assignment", object_id=submission_id):
            # 抢占失败：已被其他 Worker 领取或状态不对，跳过
            logger.debug("抢占 Submission %s 失败，跳过", submission_id)
            return submission

        question = db.get(JudgeQuestion, submission.question_id)
        if not question:
            fail_job(db, job_type="assignment", object_id=submission_id,
                     error="题目不存在", retryable=False)
            submission.status = "system_error"
            submission.score = 0
            db.commit()
            db.refresh(submission)
            redis_client.setex(f"judge:result:{submission.id}", 3600, submission.status)
            return submission

        submission.status = "running"
        db.commit()

        with tempfile.TemporaryDirectory(prefix="dai-judge-") as temp_dir:
            workdir = Path(temp_dir)
            _write_submission_files(workdir, submission, question)
            timeout_seconds = _get_timeout(question, settings)
            memory_limit_mb = question.memory_limit_mb or settings.judge_memory_limit_mb

            try:
                stdout, stderr, returncode, elapsed_ms = _run_docker_pytest(
                    workdir, settings, timeout_seconds, memory_limit_mb,
                )
            except Exception as e:
                # Docker 执行异常：可重试
                fail_job(db, job_type="assignment", object_id=submission_id,
                         error=f"Docker 判题失败: {e}", retryable=True)
                submission.status = "system_error"
                submission.score = 0
                submission.stderr = f"Docker 判题失败: {e}"
                submission.result_details = {"error": str(e)}
                db.commit()
                db.refresh(submission)
                redis_client.setex(f"judge:result:{submission.id}", 3600, submission.status)
                logger.warning("Submission %s Docker 执行异常，已退回 pending", submission_id)
                return submission

        final_status, score = _status_from_pytest(returncode, stdout, stderr)
        submission.status = final_status
        submission.stdout = stdout[-8000:]
        submission.stderr = stderr[-8000:]
        submission.score = score
        submission.execution_time_ms = elapsed_ms
        submission.result_details = {"returncode": returncode}
        db.commit()

        # 标记完成
        complete_job(db, job_type="assignment", object_id=submission_id,
                     score=score, result_details={"returncode": returncode})
        db.refresh(submission)
        redis_client.setex(f"judge:result:{submission.id}", 3600, submission.status)
        logger.info("Submission %s 判题完成: %s (%.1f)", submission_id, final_status, score)
        return submission

    except Exception:
        # 未知异常：退回 pending 等待恢复扫描重试
        logger.exception("Submission %s 未知异常，退回 pending", submission_id)
        try:
            fail_job(db, job_type="assignment", object_id=submission_id,
                     error="Worker 未知异常", retryable=True)
        except Exception:
            logger.exception("fail_job 也失败了")
            # 尽力手动设回 pending
            try:
                submission.grading_status = "pending"
                submission.last_error = "Worker 未知异常（fail_job 失败）"
                db.commit()
            except Exception:
                logger.exception("连手动退回都失败了")
        return submission


# ═══════════════════════════════════════════════════════════════
# 考试判题
# ═══════════════════════════════════════════════════════════════

def enqueue_exam_answer(submission_id: int, answer_id: int, question: ExamQuestion):
    """考试编程题入队——委托给统一 judge_queue 入口。

    保留此函数以兼容旧调用方。新代码应直接使用 judge_queue.enqueue_job。
    """
    from app.services.judge_queue import enqueue_job as _enq
    from app.database import SessionLocal

    # 需要 DB session 做条件更新
    with SessionLocal() as db:
        _enq(db, job_type="exam", object_id=answer_id)


def _maybe_finalize_exam(submission_id: int, db: Session) -> None:
    """检查是否所有答案均已完成，是则汇总生成最终成绩。

    委托给 exam_grading.finalize_if_ready——原子化汇总，与 exam_service 共用同一实现。
    """
    from app.services.exam_grading import finalize_if_ready
    finalize_if_ready(submission_id, db)


def process_exam_answer(db: Session, redis_client, settings: Settings, answer_id: int) -> ExamAnswer:
    """处理考试编程题判题——使用统一 judge_queue 状态机"""
    from app.services.judge_queue import claim_job, complete_job, fail_job

    answer = db.get(ExamAnswer, answer_id)
    if not answer:
        logger.error("ExamAnswer %s 不存在", answer_id)
        raise ValueError(f"ExamAnswer {answer_id} does not exist")

    # 幂等：已完成的答案不重复判题
    if answer.grading_status == "completed":
        _maybe_finalize_exam(answer.submission_id, db)
        return answer

    try:
        # 原子抢占：queued → running
        claimed = claim_job(db, job_type="exam", object_id=answer_id)

        # 抢占失败：说明已被其他 Worker 领取或状态不对（非 queued），直接返回
        # 旧 pending 数据由恢复扫描 requeue_stale_jobs 统一转为 queued，不在此绕过
        if not claimed:
            logger.debug("抢占 ExamAnswer %s 失败（已被其他 Worker 领取或状态非 queued），跳过", answer_id)
            return answer

        question = db.get(ExamQuestion, answer.question_id)
        if not question or not question.hidden_tests:
            fail_job(db, job_type="exam", object_id=answer_id,
                     error="题目未配置隐藏测试", retryable=False)
            answer.system_error = "题目未配置隐藏测试"
            answer.score = 0
            db.commit()
            _maybe_finalize_exam(answer.submission_id, db)
            return answer

        import tempfile
        with tempfile.TemporaryDirectory(prefix="dai-exam-judge-") as temp_dir:
            workdir = Path(temp_dir)
            user_code = workdir / "user_code.py"
            test_file = workdir / "test_user_code.py"
            user_code.write_text(answer.code_answer or "", encoding="utf-8")
            hidden_tests = question.hidden_tests
            if "import user_code" not in hidden_tests and "from user_code" not in hidden_tests:
                hidden_tests = f"import user_code\n\n{hidden_tests}"
            test_file.write_text(hidden_tests, encoding="utf-8")

            timeout_s = max(min(math.ceil((question.time_limit_ms or 10000) / 1000), settings.judge_timeout_seconds), 1)
            mem_mb = question.memory_limit_mb or settings.judge_memory_limit_mb

            try:
                stdout, stderr, returncode, elapsed_ms = _run_docker_pytest(workdir, settings, timeout_s, mem_mb)
            except Exception as e:
                fail_job(db, job_type="exam", object_id=answer_id,
                         error=f"Docker 判题失败: {e}", retryable=True)
                answer.score = 0
                answer.system_error = f"Docker 判题失败: {e}"
                answer.result_details = {"error": str(e)}
                db.commit()
                logger.warning("ExamAnswer %s Docker 执行异常，已退回 pending", answer_id)
                _maybe_finalize_exam(answer.submission_id, db)
                return answer

        final_status, _ = _status_from_pytest(returncode, stdout, stderr)
        score = float(question.points) if final_status == "accepted" else 0.0
        answer.score = float(score)
        answer.grading_status = "completed"
        answer.result_details = {"returncode": returncode, "stdout": stdout[-2000:], "stderr": stderr[-2000:]}
        db.commit()

        complete_job(db, job_type="exam", object_id=answer_id,
                     score=score, result_details=answer.result_details)
        logger.info("ExamAnswer %s 判题完成: %s (%.1f)", answer_id, final_status, score)

        _maybe_finalize_exam(answer.submission_id, db)
        return answer

    except Exception:
        # 未知异常：退回 pending 等待恢复扫描重试
        logger.exception("ExamAnswer %s 未知异常，退回 pending", answer_id)
        try:
            fail_job(db, job_type="exam", object_id=answer_id,
                     error="Worker 未知异常", retryable=True)
        except Exception:
            logger.exception("fail_job 也失败了")
            try:
                answer.grading_status = "pending"
                answer.last_error = "Worker 未知异常（fail_job 失败）"
                db.commit()
            except Exception:
                logger.exception("连手动退回都失败了")
        # 尝试汇总
        try:
            _maybe_finalize_exam(answer.submission_id, db)
        except Exception:
            logger.exception("_maybe_finalize_exam 失败")
        return answer


# ═══════════════════════════════════════════════════════════════
# Worker 主循环
# ═══════════════════════════════════════════════════════════════

def run_worker_loop():
    """主循环：同时消费普通判题队列和考试判题队列。

    消息格式（v2 统一协议）：
      {"type": "assignment" | "exam", "id": 123, "attempt": 1}
    """
    import redis as _redis

    settings = get_settings()
    redis_client = _redis.Redis.from_url(settings.redis_url, decode_responses=True)

    logger.info("Worker 启动，监听队列: %s, %s", settings.judge_queue_name, EXAM_JUDGE_QUEUE)

    while True:
        try:
            result = redis_client.brpop(
                [settings.judge_queue_name, EXAM_JUDGE_QUEUE], timeout=0
            )
            if result is None:
                continue
            queue_name, raw_data = result
        except Exception:
            logger.exception("brpop 异常，重试中...")
            time.sleep(1)
            continue

        # 解析统一 JSON 消息
        try:
            payload = _json.loads(raw_data)
            job_type = payload.get("type", "assignment" if queue_name != EXAM_JUDGE_QUEUE else "exam")
            job_id = payload["id"]
            job_attempt = payload.get("attempt", 0)
        except (ValueError, KeyError, _json.JSONDecodeError):
            # 兼容旧格式：普通作业 → 纯数字字符串
            logger.warning("无法解析消息格式，尝试旧格式兼容: %s", raw_data[:100])
            if queue_name == EXAM_JUDGE_QUEUE:
                try:
                    legacy = _json.loads(raw_data)
                    job_id = legacy.get("answer_id") or legacy.get("id")
                except Exception:
                    logger.exception("旧格式考试消息解析失败，丢弃")
                    continue
            else:
                try:
                    job_id = int(raw_data)
                except ValueError:
                    logger.exception("旧格式作业消息解析失败，丢弃")
                    continue
            job_type = "exam" if queue_name == EXAM_JUDGE_QUEUE else "assignment"
            job_attempt = 0

        with SessionLocal() as db:
            try:
                if job_type == "exam":
                    process_exam_answer(db, redis_client, settings, job_id)
                else:
                    process_submission(db, redis_client, settings, job_id)
            except Exception:
                logger.exception("判题异常: type=%s id=%s", job_type, job_id)


if __name__ == "__main__":
    run_worker_loop()
