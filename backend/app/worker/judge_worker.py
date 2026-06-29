import subprocess
import sys
import tempfile
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import SessionLocal
from app.models import JudgeQuestion, Submission


def _write_submission_files(workdir: Path, submission: Submission, question: JudgeQuestion) -> Path:
    user_code = workdir / "user_code.py"
    test_file = workdir / "test_user_code.py"
    user_code.write_text(submission.code, encoding="utf-8")
    hidden_tests = question.hidden_tests
    if "import user_code" not in hidden_tests and "from user_code" not in hidden_tests:
        hidden_tests = f"import user_code\n\n{hidden_tests}"
    test_file.write_text(hidden_tests, encoding="utf-8")
    return test_file


def _run_local_pytest(workdir: Path, test_file: Path, timeout_seconds: int) -> tuple[str, str, int, int]:
    started = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(test_file.name)],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return result.stdout, result.stderr, result.returncode, elapsed_ms
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return exc.stdout or "", exc.stderr or "Execution timed out", 124, elapsed_ms


def _run_docker_pytest(workdir: Path, settings: Settings, timeout_seconds: int) -> tuple[str, str, int, int]:
    started = time.perf_counter()
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        str(settings.judge_cpu_limit),
        "--memory",
        f"{settings.judge_memory_limit_mb}m",
        "-v",
        f"{workdir}:/work:ro",
        "-w",
        "/work",
        settings.judge_image,
        "python",
        "-m",
        "pytest",
        "-q",
        "test_user_code.py",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return result.stdout, result.stderr, result.returncode, elapsed_ms
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return exc.stdout or "", exc.stderr or "Execution timed out", 124, elapsed_ms


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
        return submission

    submission.status = "running"
    db.commit()

    with tempfile.TemporaryDirectory(prefix="dai-judge-") as temp_dir:
        workdir = Path(temp_dir)
        test_file = _write_submission_files(workdir, submission, question)
        timeout_seconds = max(int(question.time_limit_ms / 1000), settings.judge_timeout_seconds)
        if settings.judge_use_docker:
            stdout, stderr, returncode, elapsed_ms = _run_docker_pytest(workdir, settings, timeout_seconds)
        else:
            stdout, stderr, returncode, elapsed_ms = _run_local_pytest(workdir, test_file, timeout_seconds)

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
