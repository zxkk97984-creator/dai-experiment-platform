"""教师成绩统计总览契约。"""

from pydantic import BaseModel, Field


class ExamStatisticsRead(BaseModel):
    id: int
    title: str
    course_id: int
    course_title: str | None = None
    status: str
    review_released: bool = False
    expected_count: int = 0
    graded_count: int = 0
    average_score: float | None = None
    pass_rate: float = 0
    route: str


class TeacherGradeStatisticsRead(BaseModel):
    course_count: int = 0
    active_course_count: int = 0
    student_count: int = 0
    exam_count: int = 0
    graded_count: int = 0
    average_score: float | None = None
    pass_rate: float = 0
    exams: list[ExamStatisticsRead] = Field(default_factory=list)
