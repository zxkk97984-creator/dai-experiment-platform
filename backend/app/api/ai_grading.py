"""AI 评分 API——题目配置、Rubric 管理、教师复核、重评"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, or_
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.config import Settings, get_settings
from app.dependencies import get_db, get_redis_client
from app.errors import api_error
from app.models import (
    Assignment, CodeGrade, Course, Exam, ExamAnswer, ExamQuestion,
    GradeOverride, JudgeQuestion, QuestionRubric, Submission, User,
)
from app.schemas import PaginatedResponse
from app.schemas.ai_grading import AIQuestionConfigUpdate, GradeOverrideCreate, RubricDocument
from app.services.ai_client import DeepSeekClient
from app.services.rubric_service import (
    build_question_snapshot, generate_rubric, get_latest_locked_rubric,
    lock_rubric, update_draft_rubric,
)
from app.services.ai_grading_queue import enqueue_ai_grade
from app.services.score_merger import merge_scores

router = APIRouter(prefix="/ai-grading", tags=["AI 评分"])


def _teacher_or_admin(user: User):
    if user.role not in ("teacher", "admin"):
        raise api_error(403, "FORBIDDEN", "仅教师和管理员可访问")


def _ensure_course_teacher(db: Session, course_id: int, user: User):
    """验证用户是该课程的教师或 admin"""
    if user.role == "admin":
        return
    course = db.get(Course, course_id)
    if not course:
        raise api_error(404, "NOT_FOUND", "课程不存在")
    if course.teacher_id != user.id:
        raise api_error(403, "FORBIDDEN", "仅课程教师可操作")


def _get_course_id_for_question(db: Session, kind: str, question_id: int) -> int:
    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
        if q is None:
            raise api_error(404, "NOT_FOUND", "题目不存在")
        a = db.get(Assignment, q.assignment_id)
        if a is None:
            raise api_error(404, "NOT_FOUND", "作业不存在")
        return a.course_id
    elif kind == "exam":
        q = db.get(ExamQuestion, question_id)
        if q is None:
            raise api_error(404, "NOT_FOUND", "题目不存在")
        e = db.get(Exam, q.exam_id)
        if e is None:
            raise api_error(404, "NOT_FOUND", "考试不存在")
        return e.course_id
    raise api_error(400, "INVALID_KIND", "kind 必须为 assignment 或 exam")


def _teacher_course_ids(db: Session, user: User) -> list[int]:
    """返回教师所教的所有课程 ID（admin 返回空列表表示不限制）"""
    if user.role == "admin":
        return []
    rows = db.scalars(
        select(Course.id).where(Course.teacher_id == user.id)
    ).all()
    return list(rows)


def _check_grade_permission(db: Session, cg: CodeGrade, user: User):
    """验证教师有权访问该评分记录——fail-closed（关联缺失时拒绝）"""
    course_ids = _teacher_course_ids(db, user)
    if not course_ids:
        raise api_error(403, "FORBIDDEN", "无权操作")
    if cg.submission_id:
        sub = db.get(Submission, cg.submission_id)
        if not sub:
            raise api_error(403, "FORBIDDEN", "提交记录不存在")
        q = db.get(JudgeQuestion, sub.question_id)
        if not q:
            raise api_error(403, "FORBIDDEN", "题目不存在")
        a = db.get(Assignment, q.assignment_id)
        if not a or a.course_id not in course_ids:
            raise api_error(403, "FORBIDDEN", "无权操作")
    elif cg.exam_answer_id:
        ans = db.get(ExamAnswer, cg.exam_answer_id)
        if not ans:
            raise api_error(403, "FORBIDDEN", "答案记录不存在")
        q = db.get(ExamQuestion, ans.question_id)
        if not q:
            raise api_error(403, "FORBIDDEN", "题目不存在")
        e = db.get(Exam, q.exam_id)
        if not e or e.course_id not in course_ids:
            raise api_error(403, "FORBIDDEN", "无权操作")
    else:
        raise api_error(403, "FORBIDDEN", "无效的评分记录")


# ── 题目配置 ──

@router.get("/questions/{kind}/{question_id}/config")
def get_question_ai_config(
    kind: str, question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    course_id = _get_course_id_for_question(db, kind, question_id)
    _ensure_course_teacher(db, course_id, current_user)

    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    else:
        q = db.get(ExamQuestion, question_id)
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
    course_id = _get_course_id_for_question(db, kind, question_id)
    _ensure_course_teacher(db, course_id, current_user)

    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    else:
        q = db.get(ExamQuestion, question_id)
        if q and q.question_type != "code" and data.grading_mode != "legacy":
            raise api_error(400, "CHOICE_LEGACY_ONLY", "选择题只支持 legacy 模式")

    if q is None:
        raise api_error(404, "NOT_FOUND", "题目不存在")

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
    course_id = _get_course_id_for_question(db, kind, question_id)
    _ensure_course_teacher(db, course_id, current_user)

    col = QuestionRubric.judge_question_id if kind == "assignment" else QuestionRubric.exam_question_id
    rubrics = db.scalars(
        select(QuestionRubric).where(col == question_id).order_by(QuestionRubric.version.desc())
    ).all()
    return {"items": [{
        "id": r.id, "version": r.version, "status": r.status,
        "source_hash": r.source_hash, "model_name": r.model_name,
        "locked_at": r.locked_at.isoformat() if r.locked_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rubrics]}


@router.post("/questions/{kind}/{question_id}/rubrics/generate")
def generate_rubric_endpoint(
    kind: str, question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    _teacher_or_admin(current_user)
    course_id = _get_course_id_for_question(db, kind, question_id)
    _ensure_course_teacher(db, course_id, current_user)

    if not settings.ai_ready:
        raise api_error(503, "AI_NOT_READY", "AI 服务未配置 API Key")

    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    else:
        q = db.get(ExamQuestion, question_id)
    if q is None:
        raise api_error(404, "NOT_FOUND", "题目不存在")

    title = getattr(q, 'title', None) or getattr(q, 'prompt', '')
    desc = getattr(q, 'description', None) if hasattr(q, 'description') else getattr(q, 'prompt', None)
    fn = getattr(q, 'function_name', None) if hasattr(q, 'function_name') else getattr(q, 'prompt', None)

    snapshot = build_question_snapshot(
        title=title, description=desc, function_name=fn,
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
    rubric_id: int, document: RubricDocument,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _teacher_or_admin(current_user)
    rubric = db.get(QuestionRubric, rubric_id)
    if rubric is None:
        raise api_error(404, "NOT_FOUND", "Rubric 不存在")

    qid = rubric.judge_question_id or rubric.exam_question_id
    k = "assignment" if rubric.judge_question_id else "exam"
    course_id = _get_course_id_for_question(db, k, qid)
    _ensure_course_teacher(db, course_id, current_user)

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

    qid = rubric.judge_question_id or rubric.exam_question_id
    k = "assignment" if rubric.judge_question_id else "exam"
    course_id = _get_course_id_for_question(db, k, qid)
    _ensure_course_teacher(db, course_id, current_user)

    try:
        locked = lock_rubric(db, rubric_id)
    except ValueError as exc:
        raise api_error(400, "INVALID_STATE", str(exc))
    return {"id": locked.id, "status": locked.status, "locked_at": locked.locked_at.isoformat()}


# ── 评分列表与详情 ──

def _build_grade_base_query(db: Session, user: User, kind: str | None,
                             question_id: int | None, student_id: int | None, status: str | None):
    """构建带权限筛选的 CodeGrade 查询。按 kind 构建单一路径避免重复 JOIN。"""
    course_ids = _teacher_course_ids(db, user)

    if user.role == "admin":
        query = select(CodeGrade)
        count_q = select(func.count()).select_from(CodeGrade)
    elif kind == "assignment":
        # 单一路径：CodeGrade → Submission → JudgeQuestion → Assignment
        query = select(CodeGrade).join(
            Submission, CodeGrade.submission_id == Submission.id
        ).join(
            JudgeQuestion, Submission.question_id == JudgeQuestion.id
        ).join(
            Assignment, JudgeQuestion.assignment_id == Assignment.id
        ).where(Assignment.course_id.in_(course_ids))
        count_q = select(func.count()).select_from(CodeGrade).join(
            Submission, CodeGrade.submission_id == Submission.id
        ).join(
            JudgeQuestion, Submission.question_id == JudgeQuestion.id
        ).join(
            Assignment, JudgeQuestion.assignment_id == Assignment.id
        ).where(Assignment.course_id.in_(course_ids))
    elif kind == "exam":
        # 单一路径：CodeGrade → ExamAnswer → ExamQuestion → Exam
        query = select(CodeGrade).join(
            ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id
        ).join(
            ExamQuestion, ExamAnswer.question_id == ExamQuestion.id
        ).join(
            Exam, ExamQuestion.exam_id == Exam.id
        ).where(Exam.course_id.in_(course_ids))
        count_q = select(func.count()).select_from(CodeGrade).join(
            ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id
        ).join(
            ExamQuestion, ExamAnswer.question_id == ExamQuestion.id
        ).join(
            Exam, ExamQuestion.exam_id == Exam.id
        ).where(Exam.course_id.in_(course_ids))
    else:
        # 无 kind 筛选：需要两条路径的 UNION（使用 distinct outerjoin 保底，但用子查询更干净）
        # 这里用 OR 条件 + LEFT JOIN 两条路径，确保教师只能看到自己课程的数据
        query = select(CodeGrade).distinct().outerjoin(
            Submission, CodeGrade.submission_id == Submission.id
        ).outerjoin(
            JudgeQuestion, Submission.question_id == JudgeQuestion.id
        ).outerjoin(
            Assignment, JudgeQuestion.assignment_id == Assignment.id
        ).outerjoin(
            ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id
        ).outerjoin(
            ExamQuestion, ExamAnswer.question_id == ExamQuestion.id
        ).outerjoin(
            Exam, ExamQuestion.exam_id == Exam.id
        ).where(
            or_(
                Assignment.course_id.in_(course_ids) if course_ids else False,
                Exam.course_id.in_(course_ids) if course_ids else False,
            )
        )
        count_q = select(func.count()).select_from(CodeGrade).distinct().outerjoin(
            Submission, CodeGrade.submission_id == Submission.id
        ).outerjoin(
            JudgeQuestion, Submission.question_id == JudgeQuestion.id
        ).outerjoin(
            Assignment, JudgeQuestion.assignment_id == Assignment.id
        ).outerjoin(
            ExamAnswer, CodeGrade.exam_answer_id == ExamAnswer.id
        ).outerjoin(
            ExamQuestion, ExamAnswer.question_id == ExamQuestion.id
        ).outerjoin(
            Exam, ExamQuestion.exam_id == Exam.id
        ).where(
            or_(
                Assignment.course_id.in_(course_ids) if course_ids else False,
                Exam.course_id.in_(course_ids) if course_ids else False,
            )
        )

    # kind 筛选：已在 base query 中按路径构建，这里只需过滤 NULL
    if kind:
        if kind == "assignment":
            query = query.where(CodeGrade.submission_id.isnot(None))
            count_q = count_q.where(CodeGrade.submission_id.isnot(None))
        elif kind == "exam":
            query = query.where(CodeGrade.exam_answer_id.isnot(None))
            count_q = count_q.where(CodeGrade.exam_answer_id.isnot(None))

    # question_id 筛选：使用已 JOIN 的表列，不再重复 JOIN
    if question_id is not None:
        if kind == "exam":
            query = query.where(ExamAnswer.question_id == question_id)
            count_q = count_q.where(ExamAnswer.question_id == question_id)
        else:
            # assignment 或无 kind：通过 Submission → JudgeQuestion
            query = query.where(Submission.question_id == question_id)
            count_q = count_q.where(Submission.question_id == question_id)

    # student_id 筛选：使用已 JOIN 的表列
    if student_id is not None:
        if kind == "exam":
            # 需要 ExamSubmission 获取 student_id，只在需要时 JOIN
            from app.models import ExamSubmission as _ExamSubmission
            query = query.outerjoin(
                _ExamSubmission, ExamAnswer.submission_id == _ExamSubmission.id
            ).where(_ExamSubmission.student_id == student_id)
            count_q = count_q.outerjoin(
                _ExamSubmission, ExamAnswer.submission_id == _ExamSubmission.id
            ).where(_ExamSubmission.student_id == student_id)
        else:
            # assignment 或无 kind：Submission 已在 base 中
            query = query.where(Submission.student_id == student_id)
            count_q = count_q.where(Submission.student_id == student_id)

    if status:
        query = query.where(CodeGrade.status == status)
        count_q = count_q.where(CodeGrade.status == status)

    return query, count_q


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

    query, count_q = _build_grade_base_query(db, current_user, kind, question_id, student_id, status)

    total = db.scalar(count_q) or 0
    grades = db.scalars(
        query.order_by(CodeGrade.id.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    items = [{
        "id": cg.id, "submission_id": cg.submission_id, "exam_answer_id": cg.exam_answer_id,
        "mode": cg.mode, "status": cg.status,
        "functional_score": cg.functional_score, "algorithm_score": cg.algorithm_score,
        "robustness_score": cg.robustness_score, "quality_score": cg.quality_score,
        "raw_total": cg.raw_total, "score_cap": cg.score_cap,
        "final_score_100": cg.final_score_100,
        "needs_teacher_review": cg.needs_teacher_review,
        "attempt_count": cg.attempt_count,
        "created_at": cg.created_at.isoformat() if cg.created_at else None,
    } for cg in grades]
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

    # 权限：fail-closed——关联缺失时拒绝访问
    if current_user.role != "admin":
        course_ids = _teacher_course_ids(db, current_user)
        if not course_ids:
            raise api_error(403, "FORBIDDEN", "无权访问")
        if cg.submission_id:
            sub = db.get(Submission, cg.submission_id)
            if not sub:
                raise api_error(403, "FORBIDDEN", "提交记录不存在")
            q = db.get(JudgeQuestion, sub.question_id)
            if not q:
                raise api_error(403, "FORBIDDEN", "题目不存在")
            a = db.get(Assignment, q.assignment_id)
            if not a or a.course_id not in course_ids:
                raise api_error(403, "FORBIDDEN", "无权访问")
        elif cg.exam_answer_id:
            ans = db.get(ExamAnswer, cg.exam_answer_id)
            if not ans:
                raise api_error(403, "FORBIDDEN", "答案记录不存在")
            q = db.get(ExamQuestion, ans.question_id)
            if not q:
                raise api_error(403, "FORBIDDEN", "题目不存在")
            e = db.get(Exam, q.exam_id)
            if not e or e.course_id not in course_ids:
                raise api_error(403, "FORBIDDEN", "无权访问")
        else:
            raise api_error(403, "FORBIDDEN", "无效的评分记录")

    overrides = db.scalars(
        select(GradeOverride).where(GradeOverride.code_grade_id == grade_id).order_by(GradeOverride.id.desc())
    ).all()

    # 获取学生代码
    student_code = None
    if cg.submission_id:
        sub = db.get(Submission, cg.submission_id)
        if sub:
            student_code = sub.code
    elif cg.exam_answer_id:
        ans = db.get(ExamAnswer, cg.exam_answer_id)
        if ans:
            student_code = ans.code_answer

    return {
        "id": cg.id, "submission_id": cg.submission_id, "exam_answer_id": cg.exam_answer_id,
        "rubric_id": cg.rubric_id, "mode": cg.mode, "status": cg.status,
        "functional_score": cg.functional_score, "algorithm_score": cg.algorithm_score,
        "robustness_score": cg.robustness_score, "quality_score": cg.quality_score,
        "raw_total": cg.raw_total, "score_cap": cg.score_cap,
        "final_score_100": cg.final_score_100, "scaled_score": cg.scaled_score,
        "deterministic_details": cg.deterministic_details,
        "static_analysis": cg.static_analysis,
        "ai_result": cg.ai_result, "raw_response": cg.raw_response,
        "student_code": student_code,
        "needs_teacher_review": cg.needs_teacher_review,
        "review_reason": cg.review_reason,
        "attempt_count": cg.attempt_count, "last_error": cg.last_error,
        "overrides": [{
            "id": o.id, "original_snapshot": o.original_snapshot,
            "replacement_snapshot": o.replacement_snapshot,
            "reason": o.reason, "reviewer_id": o.reviewer_id,
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

    # 权限：教师只能操作自己课程的评分
    if current_user.role != "admin":
        _check_grade_permission(db, cg, current_user)

    # 条件重置：只重置失败终态（review_required/system_error），不碰 running/queued/completed
    if cg.status in ("running", "queued", "pending"):
        return {"ok": True, "grade_id": grade_id, "status": cg.status, "message": "评分进行中，不重复入队"}
    if cg.status == "completed":
        raise api_error(400, "ALREADY_COMPLETED", "评分已成功完成，无需重试。如需重新评分请使用重评功能。")

    cg.status = "pending"
    cg.last_error = None
    cg.attempt_count = 0
    db.commit()

    ok = enqueue_ai_grade(db, redis_client, grade_id)
    db.commit()
    return {"ok": ok, "grade_id": grade_id, "status": "queued" if ok else "pending"}


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

    # 权限
    if current_user.role != "admin":
        _check_grade_permission(db, cg, current_user)

    original = {
        "algorithm_score": cg.algorithm_score,
        "quality_score": cg.quality_score,
        "final_score_100": cg.final_score_100,
        "needs_teacher_review": cg.needs_teacher_review,
    }

    a_score = data.algorithm_score if data.algorithm_score is not None else cg.algorithm_score or 0
    q_score = data.quality_score if data.quality_score is not None else cg.quality_score or 0
    f_score = cg.functional_score or 0
    r_score = cg.robustness_score or 0

    if data.algorithm_score is not None:
        cg.algorithm_score = data.algorithm_score
    if data.quality_score is not None:
        cg.quality_score = data.quality_score

    if data.final_score_100 is not None:
        cg.final_score_100 = data.final_score_100
        cg.raw_total = data.final_score_100
    else:
        # 重算
        merged = merge_scores(f=f_score, a=a_score, r=r_score, q=q_score, cap=cg.score_cap, exam_points=None)
        cg.raw_total = merged.raw_total
        cg.final_score_100 = merged.final_score_100
        if cg.scaled_score is not None and cg.exam_answer_id:
            ans = db.get(ExamAnswer, cg.exam_answer_id)
            if ans:
                eq = db.get(ExamQuestion, ans.question_id)
                if eq:
                    cg.scaled_score = round(merged.final_score_100 / 100 * eq.points, 4)

    if cg.needs_teacher_review:
        cg.needs_teacher_review = False
        cg.review_reason = None

    replacement = {
        "algorithm_score": cg.algorithm_score,
        "quality_score": cg.quality_score,
        "final_score_100": cg.final_score_100,
        "needs_teacher_review": cg.needs_teacher_review,
    }

    override_record = GradeOverride(
        code_grade_id=grade_id, original_snapshot=original,
        replacement_snapshot=replacement, reason=data.reason, reviewer_id=current_user.id,
    )
    db.add(override_record)

    # 同步正式分 + 标记为已完成
    if cg.mode == "active":
        cg.status = "completed"
        cg.finished_at = datetime.now(timezone.utc)
        if cg.submission_id:
            sub = db.get(Submission, cg.submission_id)
            if sub:
                sub.score = cg.final_score_100
                sub.status = "graded"
        elif cg.exam_answer_id:
            ans = db.get(ExamAnswer, cg.exam_answer_id)
            if ans and cg.scaled_score is not None:
                ans.score = cg.scaled_score
                ans.grading_status = "completed"
                from app.services.exam_grading import finalize_if_ready
                db.flush()  # 确保 ans 更新对 finalize 可见
                finalize_if_ready(ans.submission_id, db)

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
    course_id = _get_course_id_for_question(db, kind, question_id)
    _ensure_course_teacher(db, course_id, current_user)

    rubric = get_latest_locked_rubric(db, kind=kind, question_id=question_id)
    if rubric is None:
        raise api_error(400, "NO_RUBRIC", "该题目尚无锁定 Rubric")

    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    else:
        q = db.get(ExamQuestion, question_id)
    if q is None:
        raise api_error(404, "NOT_FOUND", "题目不存在")

    gmode = getattr(q, 'grading_mode', 'legacy') or 'legacy'
    count = 0
    queued = 0

    if kind == "assignment":
        subs = db.scalars(
            select(Submission).where(Submission.question_id == question_id)
        ).all()
        for sub in subs:
            existing = db.scalar(
                select(CodeGrade).where(CodeGrade.submission_id == sub.id)
            )
            if existing:
                # 跳过进行中的评分，防止并发覆盖
                if existing.status in ("running", "queued"):
                    continue
                existing.status = "pending"
                existing.rubric_id = rubric.id
                existing.last_error = None
                existing.attempt_count = 0
            else:
                f_score = (sub.result_details or {}).get("f_score", 0) if sub.result_details else 0
                r_score = (sub.result_details or {}).get("r_score", 0) if sub.result_details else 0
                det = (sub.result_details or {}).get("groups", []) if sub.result_details else []
                existing = CodeGrade(
                    submission_id=sub.id, rubric_id=rubric.id, mode=gmode, status="pending",
                    functional_score=f_score, robustness_score=r_score,
                    deterministic_details=det,
                )
                db.add(existing)
            count += 1
    else:
        answers = db.scalars(
            select(ExamAnswer).where(ExamAnswer.question_id == question_id)
        ).all()
        for ans in answers:
            existing = db.scalar(
                select(CodeGrade).where(CodeGrade.exam_answer_id == ans.id)
            )
            if existing:
                # 跳过进行中的评分，防止并发覆盖
                if existing.status in ("running", "queued"):
                    continue
                existing.status = "pending"
                existing.rubric_id = rubric.id
                existing.last_error = None
                existing.attempt_count = 0
            else:
                f_score = (ans.result_details or {}).get("f_score", 0) if ans.result_details else 0
                r_score = (ans.result_details or {}).get("r_score", 0) if ans.result_details else 0
                det = (ans.result_details or {}).get("groups", []) if ans.result_details else []
                existing = CodeGrade(
                    exam_answer_id=ans.id, rubric_id=rubric.id, mode=gmode, status="pending",
                    functional_score=f_score, robustness_score=r_score,
                    deterministic_details=det,
                )
                db.add(existing)
            count += 1

    db.commit()

    # 仅入队目标题目的 pendings
    if kind == "assignment":
        pends = db.scalars(
            select(CodeGrade).where(
                CodeGrade.submission_id.in_(
                    select(Submission.id).where(Submission.question_id == question_id)
                ),
                CodeGrade.status == "pending"
            )
        ).all()
    else:
        pends = db.scalars(
            select(CodeGrade).where(
                CodeGrade.exam_answer_id.in_(
                    select(ExamAnswer.id).where(ExamAnswer.question_id == question_id)
                ),
                CodeGrade.status == "pending"
            )
        ).all()

    for cg in pends:
        if enqueue_ai_grade(db, redis_client, cg.id):
            queued += 1
    db.commit()

    return {"ok": True, "total": count, "queued": queued}
