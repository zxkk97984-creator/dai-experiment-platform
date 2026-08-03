from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


# ── 用户 ─────────────────────────────────────────────────────


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    real_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)


# ── 课程 / 章节 / 课时 ────────────────────────────────────────


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    teacher: Mapped[User | None] = relationship()
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by="Chapter.order_index",
    )


class Chapter(TimestampMixin, Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped[Course] = relationship(back_populates="chapters")
    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="Lesson.order_index",
    )


class Lesson(TimestampMixin, Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(30), default="markdown")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("notebook_templates.id"), nullable=True)
    notebook_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    # 发布状态：draft（草稿）/ published（已发布）/ pending（待发布）
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="published", nullable=False)

    chapter: Mapped[Chapter] = relationship(back_populates="lessons")
    notebook_template: Mapped["NotebookTemplate | None"] = relationship(foreign_keys=[template_id])


# ── 选课 ─────────────────────────────────────────────────────


class CourseEnrollment(TimestampMixin, Base):
    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("course_id", "student_id", name="uq_course_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="enrolled")

    course: Mapped[Course] = relationship()
    student: Mapped[User] = relationship()


# ── 作业与判题 ───────────────────────────────────────────────


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    course: Mapped[Course] = relationship()
    questions: Mapped[list["JudgeQuestion"]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class JudgeQuestion(TimestampMixin, Base):
    __tablename__ = "judge_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    function_name: Mapped[str] = mapped_column(String(120))
    signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_cases: Mapped[list] = mapped_column(JSON, default=list)
    hidden_tests: Mapped[str] = mapped_column(Text)
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=10000)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=256)
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    # ── AI 评分配置 ──────────────────────────────────────────
    grading_mode: Mapped[str] = mapped_column(String(20), default="legacy", index=True)
    teacher_constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    reference_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_groups: Mapped[list] = mapped_column(JSON, default=list)
    score_cap_rules: Mapped[list] = mapped_column(JSON, default=list)

    assignment: Mapped[Assignment] = relationship(back_populates="questions")


class Submission(TimestampMixin, Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("judge_questions.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    code: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="queued", index=True)
    # ── 判题队列状态机（Task 1） ──────────────────────────────
    grading_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending / queued / running / completed / system_error
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ── 判题结果 ──────────────────────────────────────────────
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    result_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    question: Mapped[JudgeQuestion] = relationship()
    student: Mapped[User] = relationship()


# ── 考试 ─────────────────────────────────────────────────────


class Exam(TimestampMixin, Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    course: Mapped[Course] = relationship()
    questions: Mapped[list["ExamQuestion"]] = relationship(back_populates="exam", cascade="all, delete-orphan")


class ExamSubmission(TimestampMixin, Base):
    """考试提交记录。answers 已删除，ExamAnswer 是唯一事实源。

    状态机：started -> submitted -> grading -> graded
            grading -> review_required（自动评分终止，需人工处理）
            review_required -> grading（仅显式受控重试）
    """
    __tablename__ = "exam_submissions"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_exam_student"),
        CheckConstraint(
            "status IN ('started', 'submitted', 'grading', 'graded', 'review_required')",
            name="ck_exam_submission_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="started", index=True)
    # started -> submitted -> grading -> graded；grading -> review_required -> grading
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # ── 自动评分终止（需人工处理） ────────────────────────────
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # 只存脱敏短摘要
    review_required_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    exam: Mapped[Exam] = relationship()
    student: Mapped[User] = relationship()
    answers: Mapped[list["ExamAnswer"]] = relationship(back_populates="submission", cascade="all, delete-orphan")


class SchedulerLease(TimestampMixin, Base):
    """多实例任务租约——同一时刻只允许一个实例执行某类扫描/恢复任务。

    - task_name 主键，天然防重复插入
    - lease_until 过期后其他实例可接管（崩溃自动释放）
    - 同一 owner 可续租
    - 不持有长事务：每轮扫描小批量，TTL 大于正常扫描时长
    """

    __tablename__ = "scheduler_leases"

    task_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(120))
    lease_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ExamGrade(TimestampMixin, Base):
    __tablename__ = "exam_grades"
    __table_args__ = (UniqueConstraint("exam_id", "student_id", name="uq_exam_grade"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0)

    exam: Mapped[Exam] = relationship()
    student: Mapped[User] = relationship()


class ExamQuestion(TimestampMixin, Base):
    """考试题目"""
    __tablename__ = "exam_questions"
    __table_args__ = (
        CheckConstraint(
            "question_type IN ('single_choice', 'multi_choice', 'code')",
            name="ck_exam_question_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    question_type: Mapped[str] = mapped_column(String(20))  # single_choice / multi_choice / code
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[dict] = mapped_column(JSON)  # {"correct":["A"]} 或 {"test_file":"..."}
    points: Mapped[float] = mapped_column(Float, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_cases: Mapped[list | None] = mapped_column(JSON, nullable=True)
    hidden_tests: Mapped[str | None] = mapped_column(Text, nullable=True)
    time_limit_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    memory_limit_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ── AI 评分配置 ──────────────────────────────────────────
    grading_mode: Mapped[str] = mapped_column(String(20), default="legacy", index=True)
    teacher_constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    reference_solution: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_groups: Mapped[list] = mapped_column(JSON, default=list)
    score_cap_rules: Mapped[list] = mapped_column(JSON, default=list)

    exam: Mapped[Exam] = relationship(back_populates="questions")


class ExamAnswer(TimestampMixin, Base):
    """考试答题唯一事实源——逐题行记录，禁止并发改整块 JSON"""
    __tablename__ = "exam_answers"
    __table_args__ = (
        UniqueConstraint("submission_id", "question_id", name="uq_exam_answer_q"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey("exam_submissions.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("exam_questions.id"), index=True)
    selected_options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # 选择题答案
    code_answer: Mapped[str | None] = mapped_column(Text, nullable=True)  # 编程题答案
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # ── 判题队列状态机（Task 1） ──────────────────────────────
    grading_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending / queued / running / completed / system_error
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ── 判题结果 ──────────────────────────────────────────────
    result_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    system_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    submission: Mapped[ExamSubmission] = relationship(back_populates="answers")
    question: Mapped[ExamQuestion] = relationship()


# ── Notebook 模板与版本 ───────────────────────────────────────


class NotebookTemplate(TimestampMixin, Base):
    """教师创建/编辑的实验模板"""
    __tablename__ = "notebook_templates"
    __table_args__ = (
        # FK 单独定义以使用 use_alter 解决循环依赖
        # migration 中通过 batch_alter_table 单独创建
        ForeignKeyConstraint(
            ["current_version_id"], ["notebook_template_versions.id"],
            use_alter=True, name="fk_template_current_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft / published
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    draft_cells: Mapped[list] = mapped_column(JSON, default=list)
    draft_revision: Mapped[int] = mapped_column(Integer, default=1)
    draft_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    draft_assets_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    versions: Mapped[list["NotebookTemplateVersion"]] = relationship(
        back_populates="template", cascade="all, delete-orphan",
        order_by="NotebookTemplateVersion.version_number",
        foreign_keys="[NotebookTemplateVersion.template_id]",
    )
    current_version: Mapped["NotebookTemplateVersion | None"] = relationship(
        foreign_keys=[current_version_id],
        primaryjoin="NotebookTemplate.current_version_id == NotebookTemplateVersion.id",
        post_update=True,
    )


class NotebookTemplateVersion(Base):
    """每次发布的不可变快照——资源路径为相对路径"""
    __tablename__ = "notebook_template_versions"
    __table_args__ = (
        UniqueConstraint("template_id", "version_number", name="uq_version_number_per_template"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("notebook_templates.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    cells: Mapped[list] = mapped_column(JSON, default=list)  # 不可变快照
    cell_order: Mapped[list] = mapped_column(JSON, default=list)
    notebook_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    assets_dir: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 相对路径
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    template: Mapped[NotebookTemplate] = relationship(
        back_populates="versions",
        foreign_keys=[template_id],
    )
    published_by: Mapped[User] = relationship()


# ── 实验模块 ──────────────────────────────────────────────────


class ExperimentModule(TimestampMixin, Base):
    __tablename__ = "experiment_modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("notebook_templates.id"), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)

    notebook_template: Mapped[NotebookTemplate | None] = relationship(foreign_keys=[template_id])
    owner: Mapped[User | None] = relationship(foreign_keys=[owner_id])


# ── 统一实验记录（替代 NotebookRecord）─────────────────────────


class ExperimentRecord(TimestampMixin, Base):
    """统一的实验/Notebook 学生记录。lesson_id 和 module_id 二选一。"""
    __tablename__ = "experiment_records"
    __table_args__ = (
        UniqueConstraint("lesson_id", "student_id", name="uq_record_lesson_student"),
        UniqueConstraint("module_id", "student_id", name="uq_record_module_student"),
        CheckConstraint(
            "(lesson_id IS NULL) != (module_id IS NULL)",
            name="ck_record_entry_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int | None] = mapped_column(ForeignKey("lessons.id"), nullable=True, index=True)
    module_id: Mapped[int | None] = mapped_column(ForeignKey("experiment_modules.id"), nullable=True, index=True)
    template_version_id: Mapped[int] = mapped_column(ForeignKey("notebook_template_versions.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="started")
    cells_sources: Mapped[dict] = mapped_column(JSON, default=dict)  # {cell_id: source}
    cells_outputs: Mapped[dict] = mapped_column(JSON, default=dict)  # {cell_id: {outputs, execution_count}}
    record_revision: Mapped[int] = mapped_column(Integer, default=1)  # 乐观并发控制
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    lesson: Mapped[Lesson | None] = relationship(foreign_keys=[lesson_id])
    module: Mapped[ExperimentModule | None] = relationship(foreign_keys=[module_id])
    template_version: Mapped[NotebookTemplateVersion] = relationship()
    student: Mapped[User] = relationship()
    submissions: Mapped[list["ExperimentSubmission"]] = relationship(
        back_populates="record", cascade="all, delete-orphan"
    )


class ExperimentSubmission(TimestampMixin, Base):
    """每次提交的记录，cells_snapshot 不可变

    client_request_id 由前端生成，用于幂等提交：
      同一 record_id + client_request_id 重复请求返回已有提交。
    """
    __tablename__ = "experiment_submissions"
    __table_args__ = (
        UniqueConstraint("record_id", "attempt_number", name="uq_experiment_submission_attempt"),
        UniqueConstraint("record_id", "client_request_id", name="uq_experiment_submission_idempotency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("experiment_records.id"), index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    client_request_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    cells_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # ── 教师评分反馈（Task 8） ────────────────────────────────
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    record: Mapped[ExperimentRecord] = relationship(back_populates="submissions")
    reviewed_by: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by_id])


# ── AI 智能代码评分 ────────────────────────────────────────────


class QuestionRubric(TimestampMixin, Base):
    """题目专属 Rubric——版本化管理，关联作业题或考试编程题"""
    __tablename__ = "question_rubrics"
    __table_args__ = (
        CheckConstraint(
            "(judge_question_id IS NULL) != (exam_question_id IS NULL)",
            name="ck_rubric_xor_target",
        ),
        UniqueConstraint("judge_question_id", "version", name="uq_rubric_judge_version"),
        UniqueConstraint("exam_question_id", "version", name="uq_rubric_exam_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    judge_question_id: Mapped[int | None] = mapped_column(
        ForeignKey("judge_questions.id"), nullable=True, index=True
    )
    exam_question_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_questions.id"), nullable=True, index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    source_hash: Mapped[str] = mapped_column(String(64))
    source_snapshot: Mapped[dict] = mapped_column(JSON)
    rubric_json: Mapped[dict] = mapped_column(JSON)
    model_name: Mapped[str] = mapped_column(String(120))
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CodeGrade(TimestampMixin, Base):
    """统一 AI 代码评分记录——XOR 外键关联 Submission 或 ExamAnswer"""
    __tablename__ = "code_grades"
    __table_args__ = (
        CheckConstraint(
            "(submission_id IS NULL) != (exam_answer_id IS NULL)",
            name="ck_code_grade_xor_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int | None] = mapped_column(
        ForeignKey("submissions.id"), nullable=True, unique=True
    )
    exam_answer_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_answers.id"), nullable=True, unique=True
    )
    rubric_id: Mapped[int] = mapped_column(ForeignKey("question_rubrics.id"))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    functional_score: Mapped[float] = mapped_column(Float, default=0)
    algorithm_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    robustness_score: Mapped[float] = mapped_column(Float, default=0)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score_100: Mapped[float | None] = mapped_column(Float, nullable=True)
    scaled_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    deterministic_details: Mapped[dict] = mapped_column(JSON, default=dict)
    static_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_teacher_review: Mapped[bool] = mapped_column(default=False)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class GradeOverride(TimestampMixin, Base):
    """教师覆盖审计记录——不可变、不可级联删除"""
    __tablename__ = "grade_overrides"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code_grade_id: Mapped[int] = mapped_column(ForeignKey("code_grades.id"), index=True)
    original_snapshot: Mapped[dict] = mapped_column(JSON)
    replacement_snapshot: Mapped[dict] = mapped_column(JSON)
    reason: Mapped[str] = mapped_column(Text)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))


# ── 公告与已读回执 ─────────────────────────────────────────────


class Announcement(TimestampMixin, Base):
    """公告：全局（管理员）或课程（任课教师）范围，纯文本内容"""

    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    content: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="normal", index=True)
    scope: Mapped[str] = mapped_column(String(20), index=True)  # global / course
    course_id: Mapped[int | None] = mapped_column(
        ForeignKey("courses.id"), nullable=True, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    course: Mapped[Course | None] = relationship()
    author: Mapped[User] = relationship()


class AnnouncementRead(Base):
    """已读回执——(announcement_id, user_id) 唯一，标记已读幂等"""

    __tablename__ = "announcement_reads"
    __table_args__ = (
        UniqueConstraint("announcement_id", "user_id", name="uq_announcement_read_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    announcement_id: Mapped[int] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
