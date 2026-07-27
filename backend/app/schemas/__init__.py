from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PaginatedResponse(BaseModel):
    items: list[Any]
    page: int = 1
    page_size: int = 20
    total: int = 0


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    real_name: str
    role: str
    status: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead


class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    role: str
    status: str = "active"


class UserUpdate(BaseModel):
    real_name: str | None = None
    role: str | None = None
    status: str | None = None


class PasswordUpdate(BaseModel):
    password: str


class StatusUpdate(BaseModel):
    status: str


class CourseCreate(BaseModel):
    title: str
    description: str | None = None
    status: str = "draft"


class CourseUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None = None
    status: str
    teacher_id: int | None = None


class ChapterCreate(BaseModel):
    title: str
    order_index: int = 0


class LessonCreate(BaseModel):
    title: str
    content_type: str = "markdown"
    content: str | None = None
    notebook_path: str | None = None
    video_url: str | None = None
    order_index: int = 0


class LessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    chapter_id: int
    title: str
    content_type: str
    content: str | None = None
    notebook_path: str | None = None
    video_url: str | None = None
    order_index: int


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    order_index: int
    lessons: list[LessonRead] = Field(default_factory=list)


class EnrollmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    student_id: int
    status: str


class AssignmentCreate(BaseModel):
    course_id: int
    title: str
    description: str | None = None
    status: str = "draft"
    due_at: datetime | None = None


class AssignmentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    due_at: datetime | None = None


class AssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    description: str | None = None
    status: str
    due_at: datetime | None = None


class PublicCase(BaseModel):
    """公开样例——统一格式：{"args": [1, 2], "expected": 3}

    自动迁移旧格式 {"input": [1,2], "expected": 3} → {"args": [1,2], "expected": 3}。
    expected 为必填；拒绝同时传入冲突的 input 和 args。
    """
    model_config = ConfigDict(extra="allow")
    args: list[Any] = Field(default_factory=list)
    expected: Any = Field(...)

    @model_validator(mode="before")
    @classmethod
    def _migrate_input_to_args(cls, data: Any) -> Any:
        """迁移旧格式：input → args；拒绝同时传入非空 input 和 args。"""
        if not isinstance(data, dict):
            return data
        has_input = "input" in data
        has_args = "args" in data and bool(data.get("args"))
        if has_input and has_args:
            raise ValueError("不能同时传入 input 和 args，请统一使用 args")
        if has_input:
            data = {**data, "args": data.pop("input")}
        return data

    @model_validator(mode="after")
    def _reject_unknown_fields(self) -> "PublicCase":
        """拒绝未知多余字段（模拟 extra=forbid 但排除已处理的 input）"""
        # 此方法保留以兼容未来扩展——当前 extra=allow 不做额外检查
        return self


class JudgeQuestionCreate(BaseModel):
    title: str
    description: str | None = None
    function_name: str
    signature: str | None = None
    starter_code: str | None = None
    public_cases: list[PublicCase] = Field(default_factory=list)
    hidden_tests: str
    time_limit_ms: int = 10000
    memory_limit_mb: int = 256


class JudgeQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    title: str
    description: str | None = None
    function_name: str
    signature: str | None = None
    starter_code: str | None = None
    public_cases: list[Any] = Field(default_factory=list)
    time_limit_ms: int
    memory_limit_mb: int


class SubmissionCreate(BaseModel):
    question_id: int
    code: str


class SubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    student_id: int
    code: str
    status: str
    stdout: str | None = None
    stderr: str | None = None
    score: float | None = None
    result_details: dict | None = None
    execution_time_ms: int | None = None


class SampleRunResponse(BaseModel):
    """sample-run 响应"""
    output: str = ""
    status: str = ""
    execution_time_ms: int = 0


class ExamCreate(BaseModel):
    course_id: int
    title: str
    status: str = "draft"
    duration_minutes: int = 60
    start_at: datetime | None = None
    end_at: datetime | None = None


class ExamUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    duration_minutes: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None


class ExamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    status: str
    duration_minutes: int
    start_at: datetime | None = None
    end_at: datetime | None = None


class ExamSubmitRequest(BaseModel):
    score: float = 0


class ExamQuestionCreate(BaseModel):
    question_type: str
    prompt: str
    options: dict | None = None
    correct_answer: dict = Field(default_factory=dict)
    points: float = 1
    order_index: int = 0
    starter_code: str | None = None
    public_cases: list[PublicCase] | None = None
    hidden_tests: str | None = None
    time_limit_ms: int | None = None
    memory_limit_mb: int | None = None


class ExamQuestionUpdate(BaseModel):
    """考试题目更新——所有字段可选，仅更新传入的字段"""
    question_type: str | None = None
    prompt: str | None = None
    options: dict | None = None
    correct_answer: dict | None = None
    points: float | None = None
    order_index: int | None = None
    starter_code: str | None = None
    public_cases: list[PublicCase] | None = None
    hidden_tests: str | None = None
    time_limit_ms: int | None = None
    memory_limit_mb: int | None = None


class ExamQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    exam_id: int
    question_type: str
    prompt: str
    options: dict | None = None
    points: float
    order_index: int
    starter_code: str | None = None
    public_cases: list | None = None


class ExamSubmissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    student_id: int
    status: str
    score: float | None = None
    expires_at: datetime | None = None


class ExamGradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    student_id: int
    score: float


# ── Notebook 模板 Schemas ─────────────────────────────────────


class NotebookCellSchema(BaseModel):
    """统一的 Cell 定义"""
    id: str
    type: str  # "markdown" | "code"
    source: str = ""
    order: int = 0
    student_editable: bool = True
    source_hidden: bool = False


class NotebookTemplateCreate(BaseModel):
    name: str
    description: str | None = None


class NotebookTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class NotebookTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    status: str
    current_version_id: int | None = None
    owner_id: int
    draft_revision: int


class NotebookTemplateVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    template_id: int
    version_number: int
    sha256: str
    cells: list[NotebookCellSchema] = Field(default_factory=list)
    cell_order: list[str] = Field(default_factory=list)
    assets_dir: str | None = None
    published_at: datetime


# ── 实验模块 Schemas ──────────────────────────────────────────


class ExperimentModuleCreate(BaseModel):
    name: str
    description: str | None = None
    template_id: int | None = None
    status: str = "draft"


class ExperimentModuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    entry_url: str | None = None
    template_id: int | None = None
    owner_id: int | None = None
    status: str


# ── 统一实验记录 Schemas ──────────────────────────────────────


class ExperimentCellsSaveRequest(BaseModel):
    """学生保存 cells。仅 student_editable code cells。"""
    cells: dict[str, str]  # {cell_id: source_code}
    record_revision: int    # 乐观并发控制


class ExperimentCellExecuteRequest(BaseModel):
    code: str


class ExperimentCellExecuteResponse(BaseModel):
    outputs: list[dict] = Field(default_factory=list)
    execution_time_ms: int | None = None
    execution_count: int = 0


class ExperimentCellOut(BaseModel):
    """返回给前端的 cell（学生视角不包含 source_hidden cells）"""
    id: str
    type: str  # "markdown" | "code"
    source: str = ""
    order: int = 0
    student_editable: bool = True
    # source_hidden=true 的 cell 完全不返回
    outputs: dict | None = None
    is_running: bool = False


class ExperimentRecordRead(BaseModel):
    id: int
    lesson_id: int | None = None
    module_id: int | None = None
    student_id: int
    status: str
    template_version_id: int
    record_revision: int
    cells_sources: dict[str, str] = Field(default_factory=dict)
    started_at: datetime | None = None
    submitted_at: datetime | None = None


class ExperimentSubmissionRead(BaseModel):
    """实验提交记录"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    record_id: int
    attempt_number: int
    client_request_id: str | None = None
    cells_snapshot: dict = Field(default_factory=dict)
    submitted_at: datetime | None = None
    score: float | None = None
    feedback: str | None = None
    reviewed_by_id: int | None = None
    reviewed_at: datetime | None = None


class ExperimentSubmitRequest(BaseModel):
    """实验提交请求——client_request_id 用于幂等"""
    client_request_id: str = Field(min_length=32, max_length=36)  # UUID v4


class ExperimentReviewUpdate(BaseModel):
    """教师评分反馈"""
    score: float | None = None
    feedback: str | None = None


class ExperimentRecordDetailResponse(BaseModel):
    """GET /records/{id} 完整响应（学生不含 source_hidden cells）"""
    id: int
    lesson_id: int | None = None
    module_id: int | None = None
    student_id: int
    status: str
    template_version_id: int
    record_revision: int
    entry_name: str = ""             # 模块名或课时名
    entry_description: str | None = None
    cells: list[ExperimentCellOut] = Field(default_factory=list)
    execution_count: int = 0


# ── Jupyter（旧）──────────────────────────────────────────────


class JupyterEntryResponse(BaseModel):
    iframe_url: str
    deprecated: bool = True


class NotebookCopyResponse(BaseModel):
    template_id: str
    target_path: str
    deprecated: bool = True


class JupyterTemplateRead(BaseModel):
    """旧 Jupyter 模板（仅兼容旧 API）"""
    id: str
    name: str
    path: str


# ── 废弃的旧 Schema（保留兼容，标记 deprecated）───────────────


class NotebookCellOut(BaseModel):
    """[已废弃] 旧 notebook cell schema"""
    id: str
    cell_type: str
    source: str
    rendered_html: str | None = None
    outputs: dict | None = None
    execution_count: int | None = None
    status: str | None = None


class NotebookResponse(BaseModel):
    """[已废弃] GET /notebooks/{lesson_id}"""
    record_id: int
    lesson_id: int
    status: str
    cells: list[NotebookCellOut]
    cell_order: list[str]
    template_outdated: bool = False
    deprecated: bool = True


class NotebookCellsSaveRequest(BaseModel):
    """[已废弃]"""
    cells: dict[str, str]


class NotebookSaveResponse(BaseModel):
    """[已废弃]"""
    record_id: int
    deprecated: bool = True


class ExperimentRecordCreate(BaseModel):
    """[已废弃] 旧实验记录创建"""
    module_id: int
    status: str = "started"
    metadata: dict[str, Any] = Field(default_factory=dict)


# Studio schemas live in a dedicated module to keep this compatibility module
# importable for existing API consumers.
from .studio import (  # noqa: E402
    StudioCell,
    StudioDraftUpdate,
    StudioImportCreate,
    StudioImportExisting,
    StudioPreviewRunRequest,
    StudioPreviewRunResponse,
    StudioTemplateBindRequest,
    StudioTemplateCreate,
    StudioTemplateMetadataUpdate,
    StudioTemplateRead,
    StudioVersionRead,
)
