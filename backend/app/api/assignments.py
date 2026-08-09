from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.courses import can_access_course_content, require_course
from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import (
    Assignment,
    CodeGrade,
    Course,
    CourseEnrollment,
    JudgeQuestion,
    QuestionRubric,
    Submission,
    User,
)
from app.schemas import (
    AssignmentCreate,
    AssignmentRead,
    AssignmentUpdate,
    JudgeQuestionCreate,
    JudgeQuestionRead,
    JudgeQuestionUpdate,
    PaginatedResponse,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


def require_assignment(assignment_id: int, db: Session) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if not assignment:
        raise api_error(404, "ASSIGNMENT_NOT_FOUND", "作业不存在")
    return assignment


def _submitted_map(db: Session, assignments: list[Assignment], student_id: int) -> dict[int, bool]:
    """批量计算学生对每个作业的已交状态，避免逐作业 N+1 查询。

    语义与 dashboard 待办判定互补：「至少一题无该学生提交记录」即待办，
    因此「全部题目都有提交记录」才算已交；无题目作业不存在未交题目，视为已交。
    """
    if not assignments:
        return {}
    assignment_ids = [a.id for a in assignments]
    rows = db.execute(
        select(JudgeQuestion.assignment_id, JudgeQuestion.id)
        .where(JudgeQuestion.assignment_id.in_(assignment_ids))
    ).all()
    qids_by_assignment: dict[int, list[int]] = {}
    for aid, qid in rows:
        qids_by_assignment.setdefault(aid, []).append(qid)
    submitted_qids: set[int] = set()
    all_qids = [qid for _, qid in rows]
    if all_qids:
        submitted_qids = set(
            db.scalars(
                select(Submission.question_id).where(
                    Submission.student_id == student_id,
                    Submission.question_id.in_(all_qids),
                )
            ).all()
        )
    return {
        a.id: all(qid in submitted_qids for qid in qids_by_assignment.get(a.id, []))
        for a in assignments
    }


def ensure_assignment_manager(assignment: Assignment, user: User, db: Session):
    if user.role == "admin":
        return
    course = db.get(Course, assignment.course_id)
    if user.role == "teacher" and course and course.teacher_id == user.id:
        return
    raise api_error(403, "FORBIDDEN", "没有权限管理该作业")


def _assignment_with_summary(db: Session, assignment: Assignment) -> AssignmentRead:
    """读响应附加学生可见环境摘要（Phase 5）——不含 digest/tag/构建日志。"""
    data = AssignmentRead.model_validate(assignment)
    if assignment.environment_version_id is not None:
        from app.services.environment_service import (
            public_environment_summary,
            resolve_effective_policy,
        )
        data.environment_summary = public_environment_summary(
            db, assignment.environment_version_id,
            resolve_effective_policy(assignment, assignment),
        )
    return data


@router.get("", response_model=PaginatedResponse)
def list_assignments(
    course_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Assignment)
    count_query = select(func.count()).select_from(Assignment)
    if course_id:
        query = query.where(Assignment.course_id == course_id)
        count_query = count_query.where(Assignment.course_id == course_id)
    if current_user.role == "student":
        # 学生只看到 published assignment + published course + enrolled
        query = (
            query.join(Course, Assignment.course_id == Course.id)
            .join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
            .where(Assignment.status == "published")
            .where(Course.status == "published")
            .where(CourseEnrollment.student_id == current_user.id)
            .where(CourseEnrollment.status == "enrolled")
        )
        count_query = (
            count_query.join(Course, Assignment.course_id == Course.id)
            .join(CourseEnrollment, Course.id == CourseEnrollment.course_id)
            .where(Assignment.status == "published")
            .where(Course.status == "published")
            .where(CourseEnrollment.student_id == current_user.id)
            .where(CourseEnrollment.status == "enrolled")
        )
    elif current_user.role == "teacher":
        query = query.join(Course, Assignment.course_id == Course.id).where(Course.teacher_id == current_user.id)
        count_query = count_query.join(Course, Assignment.course_id == Course.id).where(Course.teacher_id == current_user.id)
    elif current_user.role != "admin":
        # developer or any unsupported role: empty
        query = query.where(Assignment.id == -1)
        count_query = count_query.where(Assignment.id == -1)
    total = db.scalar(count_query) or 0
    assignments = db.scalars(query.order_by(Assignment.id).offset((page - 1) * page_size).limit(page_size)).all()
    # 仅学生视角计算提交状态，供任务中心区分已交/待办（教师/管理员保持默认 False）
    submitted_map = _submitted_map(db, assignments, current_user.id) if current_user.role == "student" else {}
    items = []
    for item in assignments:
        data = AssignmentRead.model_validate(item).model_dump()
        if current_user.role == "student":
            data["is_submitted"] = submitted_map.get(item.id, True)
        items.append(data)
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=AssignmentRead, status_code=status.HTTP_201_CREATED)
def create_assignment(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    course = require_course(payload.course_id, db)
    if current_user.role == "teacher":
        if course.teacher_id != current_user.id:
            raise api_error(403, "FORBIDDEN", "只能在自己的课程中创建作业")
    data = payload.model_dump()
    # Phase 4：教师显式选择的环境必须 available；省略时服务层解析 basic 当前可用版本
    from app.services.environment_service import (
        resolve_basic_available_version,
        validate_environment_selection,
    )

    validate_environment_selection(db, data["environment_version_id"])
    if data["environment_version_id"] is None:
        basic = resolve_basic_available_version(db)
        data["environment_version_id"] = basic.id if basic else None
    assignment = Assignment(**data, created_by_id=current_user.id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/{assignment_id}", response_model=AssignmentRead)
def get_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = require_assignment(assignment_id, db)
    course = db.get(Course, assignment.course_id)
    if not course or not can_access_course_content(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看该作业")
    if current_user.role == "student" and assignment.status != "published":
        raise api_error(403, "ASSIGNMENT_NOT_AVAILABLE", "作业未发布")
    return _assignment_with_summary(db, assignment)


@router.patch("/{assignment_id}", response_model=AssignmentRead)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)
    updates = payload.model_dump(exclude_unset=True)
    # Phase 4 门禁：已发布作业的环境字段不可直接改，必须先回到 draft（发布后绑定不可变）
    from app.services.environment_service import ENV_FIELDS, validate_environment_selection

    env_changes = [k for k in ENV_FIELDS if k in updates]
    if env_changes and assignment.status != "draft":
        raise api_error(409, "ASSIGNMENT_NOT_EDITABLE", "已发布作业的环境设置不可修改，请先将作业切回 draft")
    if updates.get("environment_version_id") is not None:
        validate_environment_selection(db, updates["environment_version_id"])
    for key, value in updates.items():
        setattr(assignment, key, value)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.post("/{assignment_id}/publish", response_model=AssignmentRead)
def publish_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
):
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)

    # Phase 4 环境门禁：默认环境与题目覆盖环境必须 available、内存不得低于环境最低值
    from app.services.environment_service import validate_publish_gate

    all_questions = db.scalars(
        select(JudgeQuestion).where(JudgeQuestion.assignment_id == assignment_id)
    ).all()
    validate_publish_gate(db, assignment, all_questions)

    # AI 评分门禁：非 legacy 题目需要锁定 Rubric
    questions = [q for q in all_questions if q.grading_mode != "legacy"]

    if questions:
        if not settings.ai_ready:
            raise api_error(503, "AI_NOT_READY", "发布含 AI 评分的题目需要配置 DAI_AI_API_KEY")
        from app.services.ai_client import DeepSeekClient, AIServiceError
        from app.services.rubric_service import ensure_locked_rubrics_for_publish
        try:
            client = DeepSeekClient(settings)
            ensure_locked_rubrics_for_publish(db, client, questions)
        except AIServiceError as exc:
            raise api_error(503, "AI_RUBRIC_UNAVAILABLE", f"Rubric 生成失败: {exc}")

    assignment.status = "published"
    db.commit()
    db.refresh(assignment)
    return assignment


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除草稿作业：事务内级联清理题目/提交/Rubric/AI 评分记录（外键 RESTRICT，顺序重要）"""
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)
    if assignment.status != "draft":
        raise api_error(409, "ASSIGNMENT_NOT_DRAFT", "仅草稿作业可删除")
    # 有提交检查（草稿理论无提交，防边界）：任一题目存在提交即拒绝
    has_submission = db.scalar(
        select(Submission.id)
        .join(JudgeQuestion, Submission.question_id == JudgeQuestion.id)
        .where(JudgeQuestion.assignment_id == assignment_id)
        .limit(1)
    )
    if has_submission:
        raise api_error(409, "ASSIGNMENT_HAS_SUBMISSIONS", "该作业已有学生提交记录，不可删除")

    question_ids = db.scalars(
        select(JudgeQuestion.id).where(JudgeQuestion.assignment_id == assignment_id)
    ).all()
    submission_ids = db.scalars(
        select(Submission.id).where(Submission.question_id.in_(question_ids))
    ).all() if question_ids else []
    # 级联清理：code_grades 外键引用 question_rubrics 与 submissions，必须先于二者删除
    if submission_ids:
        db.execute(delete(CodeGrade).where(CodeGrade.submission_id.in_(submission_ids)))
    if question_ids:
        db.execute(delete(QuestionRubric).where(QuestionRubric.judge_question_id.in_(question_ids)))
        db.execute(delete(Submission).where(Submission.question_id.in_(question_ids)))
        db.execute(delete(JudgeQuestion).where(JudgeQuestion.id.in_(question_ids)))
    db.delete(assignment)
    db.commit()
    return None


@router.post("/{assignment_id}/unpublish", response_model=AssignmentRead)
def unpublish_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取消发布：published → draft，学生端立即不可见；不解除已锁定 Rubric，再发布走现有门禁"""
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)
    if assignment.status != "published":
        raise api_error(409, "ASSIGNMENT_NOT_PUBLISHED", "仅已发布的作业可取消发布")
    assignment.status = "draft"
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/{assignment_id}/questions", response_model=PaginatedResponse)
def list_questions(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = require_assignment(assignment_id, db)
    course = db.get(Course, assignment.course_id)
    if not course or not can_access_course_content(course, current_user, db):
        raise api_error(403, "FORBIDDEN", "没有权限查看题目")
    if current_user.role == "student" and assignment.status != "published":
        raise api_error(403, "ASSIGNMENT_NOT_AVAILABLE", "作业未发布")
    questions = db.scalars(select(JudgeQuestion).where(JudgeQuestion.assignment_id == assignment_id).order_by(JudgeQuestion.id)).all()
    items = []
    for question in questions:
        data = JudgeQuestionRead.model_validate(question)
        # Phase 5：题目 effective environment summary（覆盖时显示题目环境，否则作业默认）
        env_id = question.environment_version_id or assignment.environment_version_id
        if env_id is not None:
            from app.services.environment_service import (
                public_environment_summary,
                resolve_effective_policy,
            )
            data.environment_summary = public_environment_summary(
                db, env_id, resolve_effective_policy(assignment, question),
            )
        items.append(data)
    return PaginatedResponse(items=items, page=1, page_size=len(items) or 20, total=len(items))


@router.post("/{assignment_id}/questions", response_model=JudgeQuestionRead, status_code=status.HTTP_201_CREATED)
def create_question(
    assignment_id: int,
    payload: JudgeQuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)
    data = payload.model_dump(exclude_unset=True)
    # JSON null 与未提供字段语义一致：新建编程题默认进入 active。
    if data.get("grading_mode") is None:
        data["grading_mode"] = "active"
    # Phase 4：环境字段显式传参——未提供时显式置 None 表示继承作业默认
    # （模型层惰性默认仅服务旧 ORM 创建路径，教师 API 路径显式接管）
    data.setdefault("environment_version_id", None)
    from app.services.environment_service import validate_environment_selection

    validate_environment_selection(db, data.get("environment_version_id"))
    question = JudgeQuestion(assignment_id=assignment_id, **data)
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


@router.patch("/{assignment_id}/questions/{question_id}", response_model=JudgeQuestionRead)
def update_question(
    assignment_id: int,
    question_id: int,
    payload: JudgeQuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新作业编程题——要求教师所有权且作业处于 draft 状态"""
    assignment = require_assignment(assignment_id, db)
    ensure_assignment_manager(assignment, current_user, db)
    if assignment.status != "draft":
        raise api_error(409, "ASSIGNMENT_NOT_EDITABLE", "只有草稿状态的作业可以修改题目，请先将作业切回 draft")
    question = db.get(JudgeQuestion, question_id)
    if not question or question.assignment_id != assignment_id:
        raise api_error(404, "QUESTION_NOT_FOUND", "题目不存在或不属于该作业")
    updates = payload.model_dump(exclude_unset=True)
    # Phase 4：题目覆盖环境必须 available；None 表示继承作业默认
    from app.services.environment_service import validate_environment_selection

    if updates.get("environment_version_id") is not None:
        validate_environment_selection(db, updates["environment_version_id"])
    for key, value in updates.items():
        setattr(question, key, value)
    db.commit()
    db.refresh(question)
    return question
