"""AI 评分 API——题目配置、Rubric 管理、教师复核、重评"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.config import Settings, get_settings
from app.dependencies import get_db, get_redis_client
from app.errors import api_error
from app.models import (
    Assignment, CodeGrade, Course, Exam, ExamAnswer, ExamQuestion, ExamSubmission,
    GradeOverride, JudgeQuestion, QuestionRubric, Submission, User,
)
from app.schemas import PaginatedResponse
from app.schemas.ai_grading import (
    AIQuestionConfigUpdate, GradeOverrideCreate, RubricDocument,
)
from app.services.ai_client import DeepSeekClient
from app.services.rubric_service import (
    build_question_snapshot, generate_rubric, get_latest_locked_rubric,
    lock_rubric, update_draft_rubric,
)
from app.services.ai_grading_queue import enqueue_ai_grade
from app.services.ai_grading_queue import enqueue_ai_grade

router = APIRouter(prefix="/ai-grading", tags=["AI 评分"])


def _teacher_or_admin(user: User):
    if user.role not in ("teacher", "admin"):
        raise api_error(403, "FORBIDDEN", "仅教师和管理员可访问")


def _get_course_for_question(db: Session, kind: str, question_id: int) -> Course:
    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
        if q is None:
            raise api_error(404, "NOT_FOUND", "题目不存在")
        assignment = db.get(Assignment, q.assignment_id)
        return db.get(Course, assignment.course_id) if assignment else None
    elif kind == "exam":
        q = db.get(ExamQuestion, question_id)
        if q is None:
            raise api_error(404, "NOT_FOUND", "题目不存在")
        exam = db.get(Exam, q.exam_id)
        return db.get(Course, exam.course_id) if exam else None
    raise api_error(400, "INVALID_KIND", "kind 必须为 assignment 或 exam")


def _ensure_course_teacher(db: Session, course: Course | None, user: User):
    if course is None:
        raise api_error(404, "NOT_FOUND", "课程不存在")
    if user.role != "admin" and course.teacher_id != user.id:
        raise api_error(403, "FORBIDDEN", "仅课程教师可操作")


# ── 题目配置 ──

@router.get("/questions/{kind}/{question_id}/config")
def get_question_ai_config(
    kind: str, question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    elif kind == "exam":
        q = db.get(ExamQuestion, question_id)
    else:
        raise api_error(400, "INVALID_KIND", "kind 必须为 assignment 或 exam")
    if q is None:
        raise api_error(404, "NOT_FOUND", "题目不存在")
    return {
        "grading_mode": q.grading_mode,
        "teacher_constraints": q.teacher_constraints,
        "reference_solution": q.reference_solution,
        "test_groups": q.test_groups,
        "score_cap_rules": q.score_cap_rules,
    }


@router.put("/questions/{kind}/{question_id}/config")
def update_question_ai_config(
    kind: str, question_id: int,
    data: AIQuestionConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    elif kind == "exam":
        q = db.get(ExamQuestion, question_id)
        if q and q.question_type != "code" and data.grading_mode != "legacy":
            raise api_error(400, "CHOICE_LEGACY_ONLY", "选择题只支持 legacy 模式")
    else:
        raise api_error(400, "INVALID_KIND", "kind 必须为 assignment 或 exam")
    if q is None:
        raise api_error(404, "NOT_FOUND", "题目不存在")

    course = _get_course_for_question(db, kind, question_id)
    _ensure_course_teacher(db, course, current_user)

    q.grading_mode = data.grading_mode
    q.teacher_constraints = data.teacher_constraints
    q.reference_solution = data.reference_solution
    q.test_groups = [g.model_dump() for g in data.test_groups]
    q.score_cap_rules = [r.model_dump() for r in data.score_cap_rules]
    db.commit()
    return {"ok": True, "grading_mode": q.grading_mode}


# ── Rubric 管理 ──

@router.get("/questions/{kind}/{question_id}/rubrics")
def list_rubrics(
    kind: str, question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    col = QuestionRubric.judge_question_id if kind == "assignment" else QuestionRubric.exam_question_id
    rubrics = db.scalars(
        select(QuestionRubric).where(col == question_id).order_by(QuestionRubric.version.desc())
    ).all()
    return {
        "items": [{
            "id": r.id, "version": r.version, "status": r.status,
            "source_hash": r.source_hash, "model_name": r.model_name,
            "locked_at": r.locked_at.isoformat() if r.locked_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rubrics]
    }


@router.post("/questions/{kind}/{question_id}/rubrics/generate")
def generate_rubric_endpoint(
    kind: str, question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _teacher_or_admin(current_user)
    if not settings.ai_ready:
        raise api_error(503, "AI_NOT_READY", "AI 服务未配置 API Key")

    course = _get_course_for_question(db, kind, question_id)
    _ensure_course_teacher(db, course, current_user)

    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    else:
        q = db.get(ExamQuestion, question_id)
    if q is None:
        raise api_error(404, "NOT_FOUND", "题目不存在")

    snapshot = build_question_snapshot(
        title=q.title,
        description=getattr(q, "description", getattr(q, "prompt", None)),
        function_name=getattr(q, "function_name", getattr(q, "prompt", None)),
        teacher_constraints=q.teacher_constraints,
        test_groups=q.test_groups,
        reference_solution=q.reference_solution,
        is_exam=(kind == "exam"),
    )

    client = DeepSeekClient(settings)
    rubric = generate_rubric(db, client, kind=kind, question_id=question_id, snapshot=snapshot)
    db.commit()
    return {"id": rubric.id, "version": rubric.version, "status": rubric.status, "rubric_json": rubric.rubric_json}


@router.patch("/rubrics/{rubric_id}")
def patch_rubric(
    rubric_id: int,
    document: RubricDocument,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    rubric = db.get(QuestionRubric, rubric_id)
    if rubric is None:
        raise api_error(404, "NOT_FOUND", "Rubric 不存在")

    k = "assignment" if rubric.judge_question_id else "exam"
    qid = rubric.judge_question_id or rubric.exam_question_id
    course = _get_course_for_question(db, k, qid)
    _ensure_course_teacher(db, course, current_user)

    try:
        updated = update_draft_rubric(db, rubric_id, document)
    except ValueError as exc:
        raise api_error(400, "INVALID_STATE", str(exc))
    return {"id": updated.id, "status": updated.status}


@router.post("/rubrics/{rubric_id}/lock")
def lock_rubric_endpoint(
    rubric_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    rubric = db.get(QuestionRubric, rubric_id)
    if rubric is None:
        raise api_error(404, "NOT_FOUND", "Rubric 不存在")

    k = "assignment" if rubric.judge_question_id else "exam"
    qid = rubric.judge_question_id or rubric.exam_question_id
    course = _get_course_for_question(db, k, qid)
    _ensure_course_teacher(db, course, current_user)

    try:
        locked = lock_rubric(db, rubric_id)
    except ValueError as exc:
        raise api_error(400, "INVALID_STATE", str(exc))
    return {"id": locked.id, "status": locked.status, "locked_at": locked.locked_at.isoformat()}


# ── 评分列表与详情 ──

@router.get("/grades", response_model=PaginatedResponse)
def list_grades(
    kind: str | None = Query(None),
    question_id: int | None = Query(None),
    student_id: int | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)

    query = select(CodeGrade)
    count_q = select(func.count()).select_from(CodeGrade)

    # 教师只能看自己课程的
    if current_user.role == "teacher":
        query = (
            query.outerjoin(Submission, CodeGrade.submission_id == Submission.id)
            .outerjoin(ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id)
            .outerjoin(JudgeQuestion, Submission.question_id == JudgeQuestion.id)
            .outerjoin(ExamQuestion, ExamAnswer.question_id == ExamQuestion.id)
            .outerjoin(Assignment, JudgeQuestion.assignment_id == Assignment.id)
            .outerjoin(Exam, ExamQuestion.exam_id == Exam.id)
            .outerjoin(Course, (Assignment.course_id == Course.id) | (Exam.course_id == Course.id))
            .where(Course.teacher_id == current_user.id)
        )

    if kind:
        if kind == "assignment":
            query = query.where(CodeGrade.submission_id.isnot(None))
            count_q = count_q.where(CodeGrade.submission_id.isnot(None))
        elif kind == "exam":
            query = query.where(CodeGrade.exam_answer_id.isnot(None))
            count_q = count_q.where(CodeGrade.exam_answer_id.isnot(None))

    if question_id is not None:
        query = query.outerjoin(Submission, CodeGrade.submission_id == Submission.id).where(
            Submission.question_id == question_id
        )
    if student_id is not None:
        query = query.outerjoin(Submission, CodeGrade.submission_id == Submission.id).where(
            Submission.student_id == student_id
        )
    if status:
        query = query.where(CodeGrade.status == status)
        count_q = count_q.where(CodeGrade.status == status)

    total = db.scalar(count_q) or 0
    grades = db.scalars(
        query.order_by(CodeGrade.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = []
    for cg in grades:
        items.append({
            "id": cg.id,
            "submission_id": cg.submission_id,
            "exam_answer_id": cg.exam_answer_id,
            "mode": cg.mode,
            "status": cg.status,
            "functional_score": cg.functional_score,
            "algorithm_score": cg.algorithm_score,
            "robustness_score": cg.robustness_score,
            "quality_score": cg.quality_score,
            "raw_total": cg.raw_total,
            "score_cap": cg.score_cap,
            "final_score_100": cg.final_score_100,
            "needs_teacher_review": cg.needs_teacher_review,
            "attempt_count": cg.attempt_count,
            "created_at": cg.created_at.isoformat() if cg.created_at else None,
        })
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/grades/{grade_id}")
def get_grade_detail(
    grade_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    cg = db.get(CodeGrade, grade_id)
    if cg is None:
        raise api_error(404, "NOT_FOUND", "评分记录不存在")

    # 教师权限校验
    if current_user.role == "teacher":
        if cg.submission_id:
            sub = db.get(Submission, cg.submission_id)
            if sub:
                q = db.get(JudgeQuestion, sub.question_id)
                if q:
                    a = db.get(Assignment, q.assignment_id)
                    if a:
                        course = db.get(Course, a.course_id)
                        if course and course.teacher_id != current_user.id:
                            raise api_error(403, "FORBIDDEN", "无权访问")

    # 获取覆盖历史
    overrides = db.scalars(
        select(GradeOverride).where(GradeOverride.code_grade_id == grade_id).order_by(GradeOverride.id.desc())
    ).all()

    return {
        "id": cg.id,
        "submission_id": cg.submission_id,
        "exam_answer_id": cg.exam_answer_id,
        "rubric_id": cg.rubric_id,
        "mode": cg.mode,
        "status": cg.status,
        "functional_score": cg.functional_score,
        "algorithm_score": cg.algorithm_score,
        "robustness_score": cg.robustness_score,
        "quality_score": cg.quality_score,
        "raw_total": cg.raw_total,
        "score_cap": cg.score_cap,
        "final_score_100": cg.final_score_100,
        "scaled_score": cg.scaled_score,
        "deterministic_details": cg.deterministic_details,
        "static_analysis": cg.static_analysis,
        "ai_result": cg.ai_result,
        "raw_response": cg.raw_response,
        "needs_teacher_review": cg.needs_teacher_review,
        "review_reason": cg.review_reason,
        "attempt_count": cg.attempt_count,
        "last_error": cg.last_error,
        "overrides": [{
            "id": o.id,
            "original_snapshot": o.original_snapshot,
            "replacement_snapshot": o.replacement_snapshot,
            "reason": o.reason,
            "reviewer_id": o.reviewer_id,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        } for o in overrides],
    }


@router.post("/grades/{grade_id}/retry")
def retry_grade(
    grade_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis_client),
):
    _teacher_or_admin(current_user)
    cg = db.get(CodeGrade, grade_id)
    if cg is None:
        raise api_error(404, "NOT_FOUND", "评分记录不存在")

    # 允许重试 pending/queued/running/completed/review_required/system_error
    cg.status = "pending"
    cg.last_error = None
    db.commit()

    enqueue_ai_grade(db, redis_client, grade_id)
    db.commit()
    return {"ok": True, "grade_id": grade_id, "status": "pending"}


@router.post("/grades/{grade_id}/override")
def override_grade(
    grade_id: int,
    data: GradeOverrideCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    cg = db.get(CodeGrade, grade_id)
    if cg is None:
        raise api_error(404, "NOT_FOUND", "评分记录不存在")

    # 保存原始快照
    original = {
        "algorithm_score": cg.algorithm_score,
        "quality_score": cg.quality_score,
        "final_score_100": cg.final_score_100,
        "needs_teacher_review": cg.needs_teacher_review,
    }

    if data.algorithm_score is not None:
        cg.algorithm_score = data.algorithm_score
    if data.quality_score is not None:
        cg.quality_score = data.quality_score
    if data.final_score_100 is not None:
        cg.final_score_100 = data.final_score_100

    # 如果之前有复核标记，覆盖后清除
    if cg.needs_teacher_review:
        cg.needs_teacher_review = False
        cg.review_reason = None

    # 重建 replacement 快照
    replacement = {
        "algorithm_score": cg.algorithm_score,
        "quality_score": cg.quality_score,
        "final_score_100": cg.final_score_100,
        "needs_teacher_review": cg.needs_teacher_review,
    }

    # 写入审计记录
    override_record = GradeOverride(
        code_grade_id=grade_id,
        original_snapshot=original,
        replacement_snapshot=replacement,
        reason=data.reason,
        reviewer_id=current_user.id,
    )
    db.add(override_record)

    # 更新正式成绩（active 模式）
    if cg.mode == "active" and cg.submission_id:
        sub = db.get(Submission, cg.submission_id)
        if sub:
            sub.score = cg.final_score_100
            sub.status = "graded"

    db.commit()
    return {"ok": True, "grade_id": grade_id, "original": original, "replacement": replacement}


@router.post("/questions/{kind}/{question_id}/regrade")
def regrade_question(
    kind: str,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client=Depends(get_redis_client),
):
    _teacher_or_admin(current_user)
    course = _get_course_for_question(db, kind, question_id)
    _ensure_course_teacher(db, course, current_user)

    # 获取当前锁定 Rubric
    rubric = get_latest_locked_rubric(db, kind=kind, question_id=question_id)
    if rubric is None:
        raise api_error(400, "NO_RUBRIC", "该题目尚无锁定 Rubric")

    # 查找该题所有历史提交
    if kind == "assignment":
        subs = db.scalars(
            select(Submission).where(Submission.question_id == question_id)
        ).all()
        count = 0
        for sub in subs:
            existing = db.scalar(
                select(CodeGrade).where(CodeGrade.submission_id == sub.id)
            )
            if existing:
                existing.status = "pending"
                existing.rubric_id = rubric.id
                existing.last_error = None
            else:
                cg = CodeGrade(
                    submission_id=sub.id, rubric_id=rubric.id, mode="shadow", status="pending",
                )
                db.add(cg)
            count += 1
    else:
        answers = db.scalars(
            select(ExamAnswer).where(ExamAnswer.question_id == question_id)
        ).all()
        count = 0
        for ans in answers:
            existing = db.scalar(
                select(CodeGrade).where(CodeGrade.exam_answer_id == ans.id)
            )
            if existing:
                existing.status = "pending"
                existing.rubric_id = rubric.id
                existing.last_error = None
            else:
                q = db.get(ExamQuestion, question_id)
                cg = CodeGrade(
                    exam_answer_id=ans.id, rubric_id=rubric.id,
                    mode=q.grading_mode if q else "shadow", status="pending",
                )
                db.add(cg)
            count += 1

    db.commit()

    # 查询所有 pendings 并逐个入队
    col = CodeGrade.submission_id if kind == "assignment" else CodeGrade.exam_answer_id
    pends = db.scalars(
        select(CodeGrade).where(col.isnot(None), CodeGrade.status == "pending")
    )
    queued = 0
    for cg in pends:
        if enqueue_ai_grade(db, redis_client, cg.id):
            queued += 1
    db.commit()

    return {"ok": True, "total": count, "queued": queued}
