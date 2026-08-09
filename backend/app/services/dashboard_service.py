"""角色首页聚合服务——学生/教师真实数据聚合，JOIN/子查询避免 N+1 循环"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, distinct, exists, func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Assignment, Chapter, CodeGrade, Course, CourseEnrollment, Exam, ExamAnswer,
    ExamQuestion, ExamSubmission, ExperimentModule, ExperimentRecord,
    ExperimentSubmission, JudgeQuestion, Lesson, Submission, User,
)
from app.services.announcement_service import (
    list_visible_announcements, unread_announcement_count,
)
from app.schemas.dashboard import (
    ContinueLearning, CourseHealth, CourseSnapshot, ManagedCourse,
    PriorityItem, RecentFeedback, StudentDashboardRead, StudentSummary,
    TeacherActivity, TeacherDashboardRead, TeacherSummary, WorkItem,
)

PRIORITY_CAP = 8
FEEDBACK_CAP = 5
ACTIVITY_CAP = 8
URGENT_HOURS = 24
SOON_HOURS = 72
# 截止风险窗口：计划规定"未来 7 天内的截止"；urgency 分级仍用 24/72 小时
DEADLINE_WINDOW_HOURS = 24 * 7
_URGENCY_RANK = {"urgent": 0, "soon": 1, "normal": 2}


def _urgency(hours: float) -> str:
    if hours <= URGENT_HOURS:
        return "urgent"
    if hours <= SOON_HOURS:
        return "soon"
    return "normal"


def _hours_until(now: datetime, time_at: datetime | None) -> float:
    if time_at is None:
        return SOON_HOURS * 365
    if time_at.tzinfo is None:
        # SQLite/MySQL 的 DateTime(timezone=True) 返回 naive UTC，按 UTC 处理
        time_at = time_at.replace(tzinfo=timezone.utc)
    return (time_at - now).total_seconds() / 3600


def _asc_sort_key(value: datetime | None):
    """升序排序键：naive 视为 UTC；None 恒排最后"""
    if value is None:
        return (1, 0.0)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (0, value.timestamp())


def _desc_sort_key(value: datetime | None):
    """降序排序键：naive 视为 UTC；None 恒排最后"""
    if value is None:
        return (2, 0.0)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (1, -value.timestamp())


# ── 学生首页 ───────────────────────────────────────────────────


def build_student_dashboard(db: Session, user: User, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    summary = StudentSummary()
    priority_items: list[PriorityItem] = []
    courses: list[CourseSnapshot] = []
    feedback: list[RecentFeedback] = []
    continue_learning: ContinueLearning | None = None

    enrolled_ids = list(
        db.scalars(
            select(Course.id)
            .join(CourseEnrollment, CourseEnrollment.course_id == Course.id)
            .where(
                CourseEnrollment.student_id == user.id,
                CourseEnrollment.status == "enrolled",
                Course.status == "published",
            )
        ).all()
    )
    summary.course_count = len(enrolled_ids)

    if enrolled_ids:
        # ── 待交作业：至少一题无当前学生提交 ──
        pending_rows = db.execute(
            select(Assignment, Course.title)
            .join(Course, Course.id == Assignment.course_id)
            .where(
                Assignment.course_id.in_(enrolled_ids),
                Assignment.status == "published",
                exists().where(
                    and_(
                        JudgeQuestion.assignment_id == Assignment.id,
                        ~exists().where(
                            Submission.question_id == JudgeQuestion.id,
                            Submission.student_id == user.id,
                        ),
                    )
                ),
            )
            .order_by(Assignment.due_at)
        ).all()
        summary.pending_assignment_count = len(pending_rows)
        for assignment, course_title in pending_rows:
            priority_items.append(
                PriorityItem(
                    kind="assignment", id=assignment.id, title=assignment.title,
                    course_title=course_title, time_at=assignment.due_at,
                    urgency=_urgency(_hours_until(now, assignment.due_at)),
                    route=f"/student/assignments/{assignment.id}",
                )
            )

        # ── 即将考试：已发布、有效时间未过、未提交/未评分 ──
        exam_rows = db.execute(
            select(Exam, Course.title)
            .join(Course, Course.id == Exam.course_id)
            .where(
                Exam.course_id.in_(enrolled_ids),
                Exam.status == "published",
                or_(Exam.start_at > now, Exam.end_at > now),
                ~exists().where(
                    ExamSubmission.exam_id == Exam.id,
                    ExamSubmission.student_id == user.id,
                    ExamSubmission.status.in_(("submitted", "grading", "graded")),
                ),
            )
            .order_by(Exam.start_at)
        ).all()
        summary.upcoming_exam_count = len(exam_rows)
        for exam, course_title in exam_rows:
            time_at = exam.start_at or exam.end_at
            priority_items.append(
                PriorityItem(
                    kind="exam", id=exam.id, title=exam.title,
                    course_title=course_title, time_at=time_at,
                    urgency=_urgency(_hours_until(now, time_at)),
                    route=f"/student/exams/{exam.id}",
                )
            )

        # ── 进行中实验：课程课时记录（需课程可达）与模块记录 ──
        lesson_rows = db.execute(
            select(ExperimentRecord, Lesson.title, Course.id, Course.title)
            .join(Lesson, Lesson.id == ExperimentRecord.lesson_id)
            .join(Chapter, Chapter.id == Lesson.chapter_id)
            .join(Course, Course.id == Chapter.course_id)
            .where(
                ExperimentRecord.student_id == user.id,
                ExperimentRecord.status == "started",
                ExperimentRecord.lesson_id.is_not(None),
                Course.id.in_(enrolled_ids),
            )
            .order_by(ExperimentRecord.updated_at.desc())
        ).all()
        module_rows = db.execute(
            select(ExperimentRecord, ExperimentModule.name)
            .join(ExperimentModule, ExperimentModule.id == ExperimentRecord.module_id)
            .where(
                ExperimentRecord.student_id == user.id,
                ExperimentRecord.status == "started",
                ExperimentRecord.module_id.is_not(None),
            )
            .order_by(ExperimentRecord.updated_at.desc())
        ).all()
        for record, lesson_title, course_id, course_title in lesson_rows:
            priority_items.append(
                PriorityItem(
                    kind="experiment", id=record.id, title=lesson_title,
                    course_title=course_title, time_at=record.updated_at,
                    urgency=_urgency(_hours_until(now, record.updated_at)),
                    route=f"/student/courses/{course_id}/notebook/{record.lesson_id}",
                )
            )
        for record, module_name in module_rows:
            priority_items.append(
                PriorityItem(
                    kind="experiment", id=record.id, title=module_name,
                    course_title=None, time_at=record.updated_at,
                    urgency=_urgency(_hours_until(now, record.updated_at)),
                    route=f"/student/experiments/{record.module_id}",
                )
            )

        # ── 续学：最近更新的可达实验记录，回退到第一门课 ──
        cont_rows = db.execute(
            select(ExperimentRecord, Lesson.title, Course.id, Course.title)
            .join(Lesson, Lesson.id == ExperimentRecord.lesson_id)
            .join(Chapter, Chapter.id == Lesson.chapter_id)
            .join(Course, Course.id == Chapter.course_id)
            .where(ExperimentRecord.student_id == user.id, Course.id.in_(enrolled_ids))
            .order_by(ExperimentRecord.updated_at.desc())
            .limit(1)
        ).all()
        cont_module = db.execute(
            select(ExperimentRecord, ExperimentModule.name)
            .join(ExperimentModule, ExperimentModule.id == ExperimentRecord.module_id)
            .where(ExperimentRecord.student_id == user.id)
            .order_by(ExperimentRecord.updated_at.desc())
            .limit(1)
        ).all()
        if cont_rows:
            record, lesson_title, course_id, course_title = cont_rows[0]
            continue_learning = ContinueLearning(
                kind="lesson_experiment", title=lesson_title, subtitle=course_title,
                updated_at=record.updated_at,
                route=f"/student/courses/{course_id}/notebook/{record.lesson_id}",
            )
        elif cont_module:
            record, module_name = cont_module[0]
            continue_learning = ContinueLearning(
                kind="module_experiment", title=module_name, subtitle=None,
                updated_at=record.updated_at,
                route=f"/student/experiments/{record.module_id}",
            )

        # ── 课程快照：按课程聚合真实计数 ──
        pending_by_course = dict(
            db.execute(
                select(Assignment.course_id, func.count(Assignment.id))
                .where(
                    Assignment.course_id.in_(enrolled_ids),
                    Assignment.status == "published",
                    exists().where(
                        and_(
                            JudgeQuestion.assignment_id == Assignment.id,
                            ~exists().where(
                                Submission.question_id == JudgeQuestion.id,
                                Submission.student_id == user.id,
                            ),
                        )
                    ),
                )
                .group_by(Assignment.course_id)
            ).all()
        )
        exams_by_course = dict(
            db.execute(
                select(Exam.course_id, func.count(Exam.id))
                .where(
                    Exam.course_id.in_(enrolled_ids),
                    Exam.status == "published",
                    or_(Exam.start_at > now, Exam.end_at > now),
                    ~exists().where(
                        ExamSubmission.exam_id == Exam.id,
                        ExamSubmission.student_id == user.id,
                        ExamSubmission.status.in_(("submitted", "grading", "graded")),
                    ),
                )
                .group_by(Exam.course_id)
            ).all()
        )
        activity_by_course = dict(
            db.execute(
                select(Course.id, func.max(ExperimentRecord.updated_at))
                .select_from(ExperimentRecord)
                .join(Lesson, Lesson.id == ExperimentRecord.lesson_id)
                .join(Chapter, Chapter.id == Lesson.chapter_id)
                .join(Course, Course.id == Chapter.course_id)
                .where(ExperimentRecord.student_id == user.id, Course.id.in_(enrolled_ids))
                .group_by(Course.id)
            ).all()
        )
        course_rows = db.execute(
            select(Course).where(Course.id.in_(enrolled_ids)).order_by(Course.title)
        ).scalars().all()
        for course in course_rows:
            courses.append(
                CourseSnapshot(
                    id=course.id, title=course.title,
                    pending_assignment_count=pending_by_course.get(course.id, 0),
                    upcoming_exam_count=exams_by_course.get(course.id, 0),
                    last_activity_at=activity_by_course.get(course.id),
                    route=f"/student/courses/{course.id}",
                )
            )
        courses.sort(key=lambda c: c.last_activity_at is None)

        # ── 最新反馈：实验复核 / 作业判题 / 考试评分 ──
        exp_fb = db.execute(
            select(
                ExperimentSubmission, ExperimentRecord, Lesson.title,
                ExperimentModule.name, Course.id, Course.title,
            )
            .join(ExperimentRecord, ExperimentRecord.id == ExperimentSubmission.record_id)
            .outerjoin(Lesson, Lesson.id == ExperimentRecord.lesson_id)
            .outerjoin(ExperimentModule, ExperimentModule.id == ExperimentRecord.module_id)
            .outerjoin(Chapter, Chapter.id == Lesson.chapter_id)
            .outerjoin(Course, Course.id == Chapter.course_id)
            .where(
                ExperimentRecord.student_id == user.id,
                ExperimentSubmission.reviewed_at.is_not(None),
                # 课时实验反馈仅限当前已选 published 课程；独立模块实验（无课程）保留
                or_(Course.id.is_(None), Course.id.in_(enrolled_ids)),
            )
            .order_by(ExperimentSubmission.reviewed_at.desc())
        ).all()
        for sub, record, lesson_title, module_name, course_id, course_title in exp_fb:
            title = lesson_title or module_name
            route = (
                f"/student/courses/{course_id}/notebook/{record.lesson_id}"
                if record.lesson_id
                else f"/student/experiments/{record.module_id}"
            )
            feedback.append(
                RecentFeedback(
                    kind="experiment", id=sub.id, title=f"{title} 反馈",
                    course_title=course_title, score=sub.score, feedback=sub.feedback,
                    graded_at=sub.reviewed_at, route=route,
                )
            )
        assign_fb = db.execute(
            select(Submission, JudgeQuestion.title, Assignment.title, Course.title)
            .join(JudgeQuestion, JudgeQuestion.id == Submission.question_id)
            .join(Assignment, Assignment.id == JudgeQuestion.assignment_id)
            .join(Course, Course.id == Assignment.course_id)
            .where(
                Submission.student_id == user.id,
                Submission.grading_status == "completed",
                Submission.score.is_not(None),
                Course.id.in_(enrolled_ids),
                Course.status == "published",
            )
            .order_by(Submission.finished_at.desc())
        ).all()
        for sub, _q_title, assignment_title, course_title in assign_fb:
            feedback.append(
                RecentFeedback(
                    kind="assignment", id=sub.id, title=assignment_title,
                    course_title=course_title, score=sub.score, feedback=None,
                    graded_at=sub.finished_at, route=f"/student/submissions/{sub.id}",
                )
            )
        exam_fb = db.execute(
            select(ExamSubmission, Exam.title, Course.title)
            .join(Exam, Exam.id == ExamSubmission.exam_id)
            .join(Course, Course.id == Exam.course_id)
            .where(
                ExamSubmission.student_id == user.id,
                ExamSubmission.status == "graded",
                ExamSubmission.score.is_not(None),
                Course.id.in_(enrolled_ids),
                Course.status == "published",
            )
            .order_by(ExamSubmission.graded_at.desc())
        ).all()
        for sub, exam_title, course_title in exam_fb:
            feedback.append(
                RecentFeedback(
                    kind="exam", id=sub.id, title=f"{exam_title} 成绩",
                    course_title=course_title, score=sub.score, feedback=None,
                    graded_at=sub.graded_at, route=f"/student/exams/{sub.exam_id}",
                )
            )
        feedback.sort(key=lambda f: _desc_sort_key(f.graded_at))
        feedback = feedback[:FEEDBACK_CAP]

    if continue_learning is None and courses:
        first = courses[0]
        continue_learning = ContinueLearning(
            kind="course", title=first.title, subtitle=None,
            updated_at=first.last_activity_at, route=first.route,
        )

    announcements = list_visible_announcements(db, user, now, limit=PRIORITY_CAP)
    summary.unread_announcement_count = unread_announcement_count(db, user, now)
    priority_items = priority_items[:PRIORITY_CAP]

    return StudentDashboardRead(
        summary=summary, priority_items=priority_items,
        continue_learning=continue_learning, courses=courses,
        recent_feedback=feedback, announcements=announcements,
    )


# ── 教师首页 ───────────────────────────────────────────────────


def _teacher_pending_review_rows(db: Session, owned_ids: list[int]):
    """教师课程内的待复核数据：实验提交（未复核）与 AI 评分（需复核）"""
    exp_rows = db.execute(
        select(
            ExperimentSubmission, ExperimentRecord, User.real_name,
            Lesson.title, ExperimentModule.name, Course.id, Course.title,
        )
        .join(ExperimentRecord, ExperimentRecord.id == ExperimentSubmission.record_id)
        .outerjoin(Lesson, Lesson.id == ExperimentRecord.lesson_id)
        .outerjoin(ExperimentModule, ExperimentModule.id == ExperimentRecord.module_id)
        .outerjoin(Chapter, Chapter.id == Lesson.chapter_id)
        .outerjoin(Course, Course.id == Chapter.course_id)
        .join(User, User.id == ExperimentRecord.student_id)
        .where(ExperimentSubmission.reviewed_at.is_(None), Course.id.in_(owned_ids))
        .order_by(ExperimentSubmission.submitted_at)
    ).all()
    ai_rows = db.execute(
        select(
            CodeGrade, Submission, Assignment, Course.id, Course.title, User.real_name,
        )
        .join(Submission, Submission.id == CodeGrade.submission_id)
        .join(JudgeQuestion, JudgeQuestion.id == Submission.question_id)
        .join(Assignment, Assignment.id == JudgeQuestion.assignment_id)
        .join(Course, Course.id == Assignment.course_id)
        .join(User, User.id == Submission.student_id)
        .where(CodeGrade.needs_teacher_review.is_(True), Course.id.in_(owned_ids))
    ).all()
    exam_ai_rows = db.execute(
        select(
            CodeGrade, ExamAnswer, Exam, Course.id, Course.title, User.real_name,
        )
        .join(ExamAnswer, ExamAnswer.id == CodeGrade.exam_answer_id)
        .join(ExamSubmission, ExamSubmission.id == ExamAnswer.submission_id)
        .join(Exam, Exam.id == ExamSubmission.exam_id)
        .join(Course, Course.id == Exam.course_id)
        .join(User, User.id == ExamSubmission.student_id)
        .where(CodeGrade.needs_teacher_review.is_(True), Course.id.in_(owned_ids))
    ).all()
    return exp_rows, ai_rows, exam_ai_rows


def _deadline_stats_batch(db: Session, assignments: list[Assignment]) -> dict[int, tuple[int, int]]:
    """批量统计一组作业的 (完成全部题目的当前选课学生数, 选课学生数)，避免逐作业 N+1

    已提交定义：学生对作业的全部题目都有提交记录（只答一题不算已提交）；
    且该学生必须仍处于 enrolled 状态——退课/异常提交者不进入分子。
    """
    if not assignments:
        return {}
    assignment_ids = [a.id for a in assignments]
    total_questions = dict(
        db.execute(
            select(JudgeQuestion.assignment_id, func.count(JudgeQuestion.id))
            .where(JudgeQuestion.assignment_id.in_(assignment_ids))
            .group_by(JudgeQuestion.assignment_id)
        ).all()
    )
    pairs = db.execute(
        select(Submission.student_id, Submission.question_id, JudgeQuestion.assignment_id)
        .join(JudgeQuestion, JudgeQuestion.id == Submission.question_id)
        .where(JudgeQuestion.assignment_id.in_(assignment_ids))
        .distinct()
    ).all()
    seen: dict[tuple[int, int], set[int]] = {}
    for student_id, question_id, assignment_id in pairs:
        seen.setdefault((assignment_id, student_id), set()).add(question_id)
    completed: dict[int, set[int]] = {}
    for (assignment_id, student_id), questions in seen.items():
        if total_questions.get(assignment_id, 0) > 0 and len(questions) >= total_questions[assignment_id]:
            completed.setdefault(assignment_id, set()).add(student_id)
    # 当前 enrolled 学生（按课程分组，一次查询）
    course_ids = list({a.course_id for a in assignments})
    enrolled_by_course: dict[int, set[int]] = {}
    if course_ids:
        for cid, sid in db.execute(
            select(CourseEnrollment.course_id, CourseEnrollment.student_id)
            .where(
                CourseEnrollment.course_id.in_(course_ids),
                CourseEnrollment.status == "enrolled",
            )
        ).all():
            enrolled_by_course.setdefault(cid, set()).add(sid)
    return {
        a.id: (
            len(completed.get(a.id, set()) & enrolled_by_course.get(a.course_id, set())),
            len(enrolled_by_course.get(a.course_id, set())),
        )
        for a in assignments
    }


def build_teacher_dashboard(db: Session, user: User, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    summary = TeacherSummary()
    work_items: list[WorkItem] = []
    course_health: list[CourseHealth] = []
    activity: list[TeacherActivity] = []
    managed: list[ManagedCourse] = []

    courses = (
        db.scalars(
            select(Course).where(Course.teacher_id == user.id).order_by(Course.title)
        ).all()
    )
    owned_ids = [course.id for course in courses]
    summary.course_count = len(courses)
    managed = [ManagedCourse(id=course.id, title=course.title) for course in courses]

    if owned_ids:
        summary.student_count = (
            db.scalar(
                select(func.count(distinct(CourseEnrollment.student_id))).where(
                    CourseEnrollment.course_id.in_(owned_ids),
                    CourseEnrollment.status == "enrolled",
                )
            )
            or 0
        )

        exp_rows, ai_rows, exam_ai_rows = _teacher_pending_review_rows(db, owned_ids)
        summary.pending_review_count = len(exp_rows) + len(ai_rows) + len(exam_ai_rows)

        # ── 7 天内截止的作业（urgency 分级仍按 24/72 小时）──
        deadline_rows = db.execute(
            select(Assignment, Course.id, Course.title)
            .join(Course, Course.id == Assignment.course_id)
            .where(
                Assignment.course_id.in_(owned_ids),
                Assignment.status == "published",
                Assignment.due_at > now,
                Assignment.due_at <= now + timedelta(hours=DEADLINE_WINDOW_HOURS),
            )
            .order_by(Assignment.due_at)
        ).all()
        summary.upcoming_deadline_count = len(deadline_rows)

        # ── 工作队列 ──
        for sub, record, student_name, lesson_title, module_name, course_id, course_title in exp_rows:
            item_title = lesson_title or module_name
            work_items.append(
                WorkItem(
                    kind="experiment_review", id=sub.id,
                    title=f"{student_name} 提交了{item_title}",
                    course_id=course_id, course_title=course_title,
                    detail="等待教师反馈", time_at=sub.submitted_at,
                    urgency=_urgency(_hours_until(now, sub.submitted_at)),
                    route=f"/teacher/submissions/{sub.id}",
                )
            )
        for cg, sub, assignment, course_id, course_title, student_name in ai_rows:
            work_items.append(
                WorkItem(
                    kind="ai_review", id=cg.id,
                    title=f"{student_name} 提交了{assignment.title}",
                    course_id=course_id, course_title=course_title,
                    detail="AI 评分待复核", time_at=cg.finished_at,
                    urgency=_urgency(_hours_until(now, cg.finished_at)),
                    route=f"/teacher/ai-grading/{cg.id}",
                )
            )
        for cg, answer, exam, course_id, course_title, student_name in exam_ai_rows:
            work_items.append(
                WorkItem(
                    kind="ai_review", id=cg.id,
                    title=f"{student_name} 提交了{exam.title}",
                    course_id=course_id, course_title=course_title,
                    detail="AI 评分待复核", time_at=cg.finished_at,
                    urgency=_urgency(_hours_until(now, cg.finished_at)),
                    route=f"/teacher/ai-grading/{cg.id}",
                )
            )
        deadline_stats = _deadline_stats_batch(db, [a for a, _cid, _ct in deadline_rows])
        for assignment, course_id, course_title in deadline_rows:
            submitted, expected = deadline_stats[assignment.id]
            # 工作队列只提示参与不完全的截止：全员已提交（且有人选课）时省略
            if expected > 0 and submitted >= expected:
                continue
            work_items.append(
                WorkItem(
                    kind="deadline", id=assignment.id, title=assignment.title,
                    course_id=course_id, course_title=course_title,
                    detail=f"{submitted}/{expected} 已提交", time_at=assignment.due_at,
                    urgency=_urgency(_hours_until(now, assignment.due_at)),
                    route=f"/teacher/assignments/{assignment.id}/edit",
                )
            )
        work_items.sort(
            key=lambda w: (_URGENCY_RANK[w.urgency], _asc_sort_key(w.time_at))
        )
        work_items = work_items[:PRIORITY_CAP]

        # ── 课程概览：按课程聚合待复核与截止数 ──
        exp_by_course: dict[int, int] = {}
        ai_by_course: dict[int, int] = {}
        for sub, record, _n, _l, _m, course_id, _ct in exp_rows:
            exp_by_course[course_id] = exp_by_course.get(course_id, 0) + 1
        for cg, _s, _a, course_id, _ct, _n in ai_rows:
            ai_by_course[course_id] = ai_by_course.get(course_id, 0) + 1
        for cg, _ans, _e, course_id, _ct, _n in exam_ai_rows:
            ai_by_course[course_id] = ai_by_course.get(course_id, 0) + 1
        deadline_by_course: dict[int, list] = {}
        for assignment, course_id, _ct in deadline_rows:
            deadline_by_course.setdefault(course_id, []).append(assignment)

        # 批量统计所有课程的选课学生数（一次查询）
        enrolled_counts = dict(
            db.execute(
                select(CourseEnrollment.course_id, func.count(distinct(CourseEnrollment.student_id)))
                .where(
                    CourseEnrollment.course_id.in_(owned_ids),
                    CourseEnrollment.status == "enrolled",
                )
                .group_by(CourseEnrollment.course_id)
            ).all()
        )

        for course in courses:
            cid = course.id
            deadline_list = deadline_by_course.get(cid, [])
            at_risk_submitted = sum(deadline_stats[a.id][0] for a in deadline_list)
            at_risk_expected = sum(deadline_stats[a.id][1] for a in deadline_list)
            course_health.append(
                CourseHealth(
                    course_id=cid, title=course.title,
                    student_count=enrolled_counts.get(cid, 0),
                    pending_review_count=exp_by_course.get(cid, 0)
                    + ai_by_course.get(cid, 0),
                    upcoming_deadline_count=len(deadline_list),
                    at_risk_submitted_count=at_risk_submitted,
                    at_risk_expected_count=at_risk_expected,
                    route=f"/teacher/courses/{cid}/manage",
                )
            )
        course_health.sort(
            key=lambda h: (
                h.upcoming_deadline_count == 0,
                -h.upcoming_deadline_count,
                -h.pending_review_count,
                h.title,
            )
        )

        # ── 最近动态：真实实验提交 ──
        activity_rows = db.execute(
            select(
                ExperimentSubmission, User.real_name,
                Lesson.title, ExperimentModule.name, Course.id, Course.title,
            )
            .join(ExperimentRecord, ExperimentRecord.id == ExperimentSubmission.record_id)
            .outerjoin(Lesson, Lesson.id == ExperimentRecord.lesson_id)
            .outerjoin(ExperimentModule, ExperimentModule.id == ExperimentRecord.module_id)
            .outerjoin(Chapter, Chapter.id == Lesson.chapter_id)
            .outerjoin(Course, Course.id == Chapter.course_id)
            .join(User, User.id == ExperimentRecord.student_id)
            .where(Course.id.in_(owned_ids))
            .order_by(ExperimentSubmission.submitted_at.desc())
            .limit(ACTIVITY_CAP)
        ).all()
        for sub, student_name, lesson_title, module_name, course_id, course_title in activity_rows:
            item_title = lesson_title or module_name
            activity.append(
                TeacherActivity(
                    kind="experiment_submission", id=sub.id,
                    title=f"{student_name} 提交了{item_title}",
                    course_title=course_title, actor_name=student_name,
                    happened_at=sub.submitted_at, route=f"/teacher/submissions/{sub.id}",
                )
            )

    announcements = list_visible_announcements(db, user, now, limit=PRIORITY_CAP)
    return TeacherDashboardRead(
        summary=summary, work_items=work_items, course_health=course_health,
        recent_activity=activity, managed_courses=managed,
        announcements=announcements,
    )
