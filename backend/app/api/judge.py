import math
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.courses import can_view_course
from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_db, get_redis_client
from app.errors import api_error
from app.models import Assignment, Course, CourseEnrollment, JudgeQuestion, Submission, User
from app.schemas import PaginatedResponse, SampleRunResponse, SubmissionCreate, SubmissionRead
from app.worker.judge_worker import _get_timeout, _run_docker_pytest, _status_from_pytest

router = APIRouter(prefix="/judge", tags=["judge"])


def require_submission(submission_id: int, db: Session) -> Submission:
    submission = db.get(Submission, submission_id)
    if not submission:
        raise api_error(404, "SUBMISSION_NOT_FOUND", "提交不存在")
    return submission


def can_view_submission(submission: Submission, user: User, db: Session) -> bool:
    if user.role == "admin":
        return True
    if user.role == "teacher":
        question = db.get(JudgeQuestion, submission.question_id)
        if question:
            assignment = db.get(Assignment, question.assignment_id)
            if assignment:
                course = db.get(Course, assignment.course_id)
                if course and course.teacher_id == user.id:
                    return True
        return False
    return submission.student_id == user.id


@router.post("/submissions", response_model=SubmissionRead, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise api_error(403, "FORBIDDEN", "只有学生可以提交代码")
    question = db.get(JudgeQuestion, payload.question_id)
    if not question:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在")
    assignment = db.get(Assignment, question.assignment_id)
    if not assignment or assignment.status != "published":
        raise api_error(400, "ASSIGNMENT_NOT_AVAILABLE", "作业不可提交")
    course = db.get(Course, assignment.course_id)
    if not course or not can_view_course(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限提交该题目")
    # check max attempts
    if question.max_attempts is not None:
        count = db.scalar(
            select(func.count()).select_from(Submission).where(
                Submission.question_id == payload.question_id,
                Submission.student_id == current_user.id,
            )
        ) or 0
        if count >= question.max_attempts:
            raise api_error(400, "MAX_ATTEMPTS_REACHED", f"已达到最大提交次数（{question.max_attempts}次）")
    submission = Submission(
        question_id=payload.question_id,
        student_id=current_user.id,
        code=payload.code,
        status="queued",
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Process synchronously with hidden tests
    try:
        submission.status = "running"
        db.commit()

        with tempfile.TemporaryDirectory(prefix="dai-judge-") as temp_dir:
            workdir = Path(temp_dir)
            user_code_path = workdir / "user_code.py"
            user_code_path.write_text(payload.code, encoding="utf-8")

            hidden_tests = question.hidden_tests
            if "import user_code" not in hidden_tests and "from user_code" not in hidden_tests:
                hidden_tests = f"import user_code\n\n{hidden_tests}"
            test_path = workdir / "test_user_code.py"
            test_path.write_text(hidden_tests, encoding="utf-8")

            timeout_seconds = _get_timeout(question, settings)
            memory_mb = question.memory_limit_mb or settings.judge_memory_limit_mb

            stdout, stderr, returncode, elapsed_ms = _run_docker_pytest(
                workdir, settings, timeout_seconds, memory_mb
            )

        status_text, score_val = _status_from_pytest(returncode, stdout, stderr)
        submission.status = status_text
        submission.score = score_val
        submission.stdout = stdout[-5000:]
        submission.stderr = stderr[-5000:]
        submission.execution_time_ms = elapsed_ms
    except FileNotFoundError:
        submission.status = "system_error"
        submission.stdout = "Docker not available"
    except Exception as e:
        submission.status = "system_error"
        submission.stdout = str(e)[:500]

    db.commit()
    db.refresh(submission)
    return submission


@router.get("/submissions", response_model=PaginatedResponse)
def list_submissions(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Submission)
    count_query = select(func.count()).select_from(Submission)
    if current_user.role == "student":
        query = query.where(Submission.student_id == current_user.id)
        count_query = count_query.where(Submission.student_id == current_user.id)
    elif current_user.role == "teacher":
        # 教师只看自己课程的提交
        query = query.join(JudgeQuestion, Submission.question_id == JudgeQuestion.id).join(
            Assignment, JudgeQuestion.assignment_id == Assignment.id
        ).join(Course, Assignment.course_id == Course.id).where(
            Course.teacher_id == current_user.id
        )
        count_query = count_query.join(JudgeQuestion, Submission.question_id == JudgeQuestion.id).join(
            Assignment, JudgeQuestion.assignment_id == Assignment.id
        ).join(Course, Assignment.course_id == Course.id).where(
            Course.teacher_id == current_user.id
        )
    total = db.scalar(count_query) or 0
    submissions = db.scalars(query.order_by(Submission.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedResponse(items=[SubmissionRead.model_validate(item) for item in submissions], page=page, page_size=page_size, total=total)


@router.get("/submissions/{submission_id}", response_model=SubmissionRead)
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = require_submission(submission_id, db)
    if not can_view_submission(submission, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该提交")
    return submission


@router.get("/submissions/{submission_id}/result", response_model=SubmissionRead)
def get_submission_result(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = require_submission(submission_id, db)
    if not can_view_submission(submission, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该判题结果")
    return submission

@router.post("/questions/{question_id}/sample-run", response_model=SampleRunResponse)
def sample_run(
    question_id: int,
    payload: SubmissionCreate,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
):
    """仅运行公开样例——不创建 Submission、不计提交次数、不访问隐藏测试"""
    if current_user.role != "student":
        raise api_error(403, "FORBIDDEN", "只有学生可以使用 sample-run")

    if question_id != payload.question_id:
        raise api_error(400, "QUESTION_MISMATCH", "题目 ID 不一致")
    question = db.get(JudgeQuestion, question_id)
    if not question:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在")

    assignment = db.get(Assignment, question.assignment_id)
    if not assignment or assignment.status != "published":
        raise api_error(403, "ASSIGNMENT_NOT_AVAILABLE", "作业未发布")
    course = db.get(Course, assignment.course_id)
    if not course or course.status != "published":
        raise api_error(403, "COURSE_NOT_AVAILABLE", "课程未发布")
    enrollment = db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.student_id == current_user.id,
            CourseEnrollment.status == "enrolled",
        )
    )
    if not enrollment:
        raise api_error(403, "NOT_ENROLLED", "请先选课")

    public_cases = question.public_cases or []
    if not public_cases:
        return SampleRunResponse(output="", status="no_public_cases", execution_time_ms=0)

    # 仅用公开样例构建测试文件
    test_code = f"{payload.code}\n\n"
    test_code += "def test_public_cases():\n"
    for case in public_cases:
        test_code += f"    assert {question.function_name}({case.get('input', '')}) == {case.get('expected', '')}\n"

    with tempfile.TemporaryDirectory(prefix="dai-sample-") as temp_dir:
        workdir = Path(temp_dir)
        (workdir / "test_sample.py").write_text(test_code, encoding="utf-8")
        timeout_seconds = _get_timeout(question, settings)
        memory_mb = question.memory_limit_mb or settings.judge_memory_limit_mb

        try:
            stdout, stderr, returncode, elapsed_ms = _run_docker_pytest(
                workdir, settings, timeout_seconds, memory_mb, test_filename="test_sample.py",
            )
        except FileNotFoundError:
            raise api_error(503, "JUDGE_UNAVAILABLE", "判题服务不可用（Docker 未就绪）")

    status, _score = _status_from_pytest(returncode, stdout, stderr)
    return SampleRunResponse(
        output=f"{stdout}\n{stderr}",
        status=status,
        execution_time_ms=elapsed_ms,
    )
