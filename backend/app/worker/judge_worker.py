import math
import secrets
import subprocess
import tempfile
import time
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import JudgeQuestion, Submission, ExamAnswer, ExamQuestion, ExamSubmission


def _get_timeout(question: JudgeQuestion, settings: Settings) -> int:
    """超时秒数：ceil(time_limit_ms / 1000)，受全局硬上限约束，至少 1 秒"""
    raw = max(question.time_limit_ms, 1)  # 非正值至少 1ms
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


def process_submission(db: Session, redis_client, settings: Settings, submission_id: int) -> Submission:
    submission = db.get(Submission, submission_id)
    if not submission:
        raise ValueError(f"Submission {submission_id} does not exist")
    question = db.get(JudgeQuestion, submission.question_id)
    if not question:
        submission.status = "system_error"
        submission.stderr = "Question not found"
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
            submission.status = "system_error"
            submission.score = 0
            submission.stderr = f"Docker 判题失败: {e}"
            submission.result_details = {"error": str(e)}
            db.commit()
            db.refresh(submission)
            redis_client.setex(f"judge:result:{submission.id}", 3600, submission.status)
            return submission

    final_status, score = _status_from_pytest(returncode, stdout, stderr)
    submission.status = final_status
    submission.stdout = stdout[-8000:]
    submission.stderr = stderr[-8000:]
    submission.score = score
    submission.execution_time_ms = elapsed_ms
    submission.result_details = {"returncode": returncode}
    db.commit()
    db.refresh(submission)
    redis_client.setex(f"judge:result:{submission.id}", 3600, submission.status)
    return submission


def run_worker_loop():
    import redis

    settings = get_settings()
    redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    while True:
        _, raw_submission_id = redis_client.brpop(settings.judge_queue_name)
        with SessionLocal() as db:
            process_submission(db, redis_client, settings, int(raw_submission_id))


if __name__ == "__main__":
    run_worker_loop()

EXAM_JUDGE_QUEUE = "judge:exam:queue"

def enqueue_exam_answer(submission_id: int, answer_id: int, question: ExamQuestion):
    """把考试编程题答案推入 Redis 判题队列"""
    import redis, json
    settings = get_settings()
    r = redis.Redis.from_url(settings.redis_url, decode_responses=False)
    payload = json.dumps({"submission_id": submission_id, "answer_id": answer_id, "question_id": question.id})
    r.rpush(EXAM_JUDGE_QUEUE, payload)

def process_exam_answer(db: Session, redis_client, settings: Settings, answer_id: int) -> ExamAnswer:
    answer = db.get(ExamAnswer, answer_id)
    if not answer:
        raise ValueError(f"ExamAnswer {answer_id} does not exist")
    question = db.get(ExamQuestion, answer.question_id)
    if not question or not question.hidden_tests:
        answer.system_error = "题目未配置隐藏测试"
        answer.grading_status = "completed"
        answer.score = 0
        db.commit()
        return answer

    answer.grading_status = "running"
    db.commit()

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
            answer.grading_status = "completed"
            answer.score = 0
            answer.system_error = f"Docker 判题失败: {e}"
            answer.result_details = {"error": str(e)}
            db.commit()
            return answer

    final_status, _ = _status_from_pytest(returncode, stdout, stderr)
    score = float(question.points) if final_status == "accepted" else 0.0
    answer.grading_status = "completed"
    answer.score = float(score)
    answer.result_details = {"returncode": returncode, "stdout": stdout[-2000:], "stderr": stderr[-2000:]}
    db.commit()

    # 检查是否所有代码题都已判完，是则汇总
    submission = db.get(ExamSubmission, answer.submission_id)
    if submission and submission.status == "grading":
        from sqlalchemy import select as sel
        remaining = db.scalar(
            select(ExamAnswer).where(
                ExamAnswer.submission_id == submission.id,
                ExamAnswer.grading_status == "pending",
            ).limit(1)
        )
        if not remaining:
            total = db.scalar(
                select(func.sum(ExamAnswer.score)).where(
                    ExamAnswer.submission_id == submission.id,
                    ExamAnswer.grading_status == "completed",
                )
            ) or 0.0
            from app.services.exam_service import _finalize_grade as _fg
            _fg(submission, float(total), db)
            db.commit()

    return answer
