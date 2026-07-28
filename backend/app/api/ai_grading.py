"""AI 评分 API——题目配置、Rubric 管理、教师复核"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.assignments import ensure_assignment_manager, require_assignment
from app.api.auth import get_current_user
from app.config import Settings, get_settings
from app.dependencies import get_db
from app.models import Course, Exam, ExamQuestion, JudgeQuestion, QuestionRubric, User
from app.schemas.ai_grading import AIQuestionConfigUpdate, RubricDocument
from app.services.ai_client import DeepSeekClient
from app.services.rubric_service import (
    generate_rubric_from_snapshot,
    get_latest_locked_rubric,
    lock_rubric,
    update_draft_rubric,
)

router = APIRouter(prefix="/ai-grading", tags=["AI 评分"])


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _require_teacher_or_admin(user: User) -> None:
    if user.role not in ("teacher", "admin"):
        raise api_error(403, "FORBIDDEN", "仅教师和管理员可访问")


def _get_course_for_question(db: Session, kind: str, question_id: int) -> Course:
    """获取题目所属课程"""
    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
        if q is None:
            raise api_error(404, "NOT_FOUND", "题目不存在")
        course = db.get(Course, q.assignment.course_id)
    elif kind == "exam":
        q = db.get(ExamQuestion, question_id)
        if q is None:
            raise api_error(404, "NOT_FOUND", "题目不存在")
        course = db.get(Course, q.exam.course_id)
    else:
        raise api_error(400, "INVALID_KIND", "kind 必须为 assignment 或 exam")
    return course


# ── 题目配置 ──


@router.get("/questions/{kind}/{question_id}/config")
def get_question_ai_config(
    kind: str,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取题目 AI 评分配置"""
    _require_teacher_or_admin(current_user)

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
    kind: str,
    question_id: int,
    data: AIQuestionConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新题目 AI 评分配置"""
    _require_teacher_or_admin(current_user)

    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    elif kind == "exam":
        q = db.get(ExamQuestion, question_id)
        # 选择题强制 legacy
        if q and q.question_type != "code":
            if data.grading_mode != "legacy":
                raise api_error(400, "CHOICE_LEGACY_ONLY", "选择题只支持 legacy 模式")
    else:
        raise api_error(400, "INVALID_KIND", "kind 必须为 assignment 或 exam")

    if q is None:
        raise api_error(404, "NOT_FOUND", "题目不存在")

    # 权限：确保是题目所属课程的教师
    course = _get_course_for_question(db, kind, question_id)
    if current_user.role != "admin" and course.teacher_id != current_user.id:
        raise api_error(403, "FORBIDDEN", "仅课程教师可修改配置")

    q.grading_mode = data.grading_mode
    q.teacher_constraints = data.teacher_constraints
    q.reference_solution = data.reference_solution
    q.test_groups = [g.model_dump() for g in data.test_groups]
    q.score_cap_rules = [r.model_dump() for r in data.score_cap_rules]
    db.flush()

    return {"ok": True, "grading_mode": q.grading_mode}


# ── Rubric 管理 ──


@router.get("/questions/{kind}/{question_id}/rubrics")
def list_rubrics(
    kind: str,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出题目所有 Rubric 版本"""
    _require_teacher_or_admin(current_user)
    _get_course_for_question(db, kind, question_id)

    col = QuestionRubric.judge_question_id if kind == "assignment" else QuestionRubric.exam_question_id
    rubrics = db.scalars(
        select(QuestionRubric)
        .where(col == question_id)
        .order_by(QuestionRubric.version.desc())
    ).all()

    return {
        "items": [
            {
                "id": r.id,
                "version": r.version,
                "status": r.status,
                "source_hash": r.source_hash,
                "model_name": r.model_name,
                "locked_at": r.locked_at.isoformat() if r.locked_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rubrics
        ]
    }


@router.post("/questions/{kind}/{question_id}/rubrics/generate")
def generate_rubric(
    kind: str,
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    """生成新 Rubric（draft）"""
    _require_teacher_or_admin(current_user)
    course = _get_course_for_question(db, kind, question_id)

    if current_user.role != "admin" and course.teacher_id != current_user.id:
        raise api_error(403, "FORBIDDEN", "仅课程教师可生成 Rubric")

    if not settings.ai_ready:
        raise api_error(503, "AI_NOT_READY", "AI 服务未配置 API Key")

    if kind == "assignment":
        q = db.get(JudgeQuestion, question_id)
    else:
        q = db.get(ExamQuestion, question_id)

    from app.services.rubric_service import build_question_snapshot

    snapshot = build_question_snapshot(
        title=q.title,
        description=getattr(q, "description", None),
        function_name=getattr(q, "function_name", getattr(q, "prompt", None)),
        teacher_constraints=q.teacher_constraints,
        test_groups=q.test_groups,
        reference_solution=q.reference_solution,
        is_exam=(kind == "exam"),
    )

    client = DeepSeekClient(settings)
    rubric = generate_rubric_from_snapshot(db, client, kind=kind, question_id=question_id, snapshot=snapshot)

    return {
        "id": rubric.id,
        "version": rubric.version,
        "status": rubric.status,
        "rubric_json": rubric.rubric_json,
    }


@router.patch("/rubrics/{rubric_id}")
def patch_rubric(
    rubric_id: int,
    document: RubricDocument,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改 draft Rubric"""
    _require_teacher_or_admin(current_user)

    rubric = db.get(QuestionRubric, rubric_id)
    if rubric is None:
        raise api_error(404, "NOT_FOUND", "Rubric 不存在")

    course = _get_course_for_question(
        db,
        "assignment" if rubric.judge_question_id else "exam",
        rubric.judge_question_id or rubric.exam_question_id,
    )
    if current_user.role != "admin" and course.teacher_id != current_user.id:
        raise api_error(403, "FORBIDDEN", "仅课程教师可修改 Rubric")

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
    """锁定 Rubric"""
    _require_teacher_or_admin(current_user)

    rubric = db.get(QuestionRubric, rubric_id)
    if rubric is None:
        raise api_error(404, "NOT_FOUND", "Rubric 不存在")

    course = _get_course_for_question(
        db,
        "assignment" if rubric.judge_question_id else "exam",
        rubric.judge_question_id or rubric.exam_question_id,
    )
    if current_user.role != "admin" and course.teacher_id != current_user.id:
        raise api_error(403, "FORBIDDEN", "仅课程教师可锁定 Rubric")

    try:
        locked = lock_rubric(db, rubric_id)
    except ValueError as exc:
        raise api_error(400, "INVALID_STATE", str(exc))

    return {"id": locked.id, "status": locked.status, "locked_at": locked.locked_at.isoformat()}
