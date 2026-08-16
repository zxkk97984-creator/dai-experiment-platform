"""跨实验 / 作业 / 考试的提交展示状态归一化。

Dashboard 最近提交表与统一提交中心共用同一套判定规则，避免前端三套映射漂移。
"""

from app.models import CodeGrade, ExamSubmission, ExperimentSubmission, Submission

PENDING = "pending_grading"
GRADED = "graded"
REVIEW = "review_required"
FAILED = "failed"
PUBLISH = "pending_release"
TONES = {
    PENDING: "warning",
    GRADED: "success",
    REVIEW: "info",
    FAILED: "danger",
    PUBLISH: "neutral",
}


def experiment_display(sub: ExperimentSubmission) -> tuple[str, str]:
    if sub.score is not None:
        return GRADED, TONES[GRADED]
    return PENDING, TONES[PENDING]


def assignment_display(sub: Submission, code_grade: CodeGrade | None = None) -> tuple[str, str]:
    if sub.status == "system_error" or sub.grading_status == "system_error":
        return FAILED, TONES[FAILED]
    if sub.grading_status in ("pending", "queued", "running"):
        return PENDING, TONES[PENDING]
    if code_grade is not None and code_grade.needs_teacher_review:
        return REVIEW, TONES[REVIEW]
    if sub.score is not None:
        return GRADED, TONES[GRADED]
    return PENDING, TONES[PENDING]


def exam_display(sub: ExamSubmission) -> tuple[str, str]:
    mapping = {
        "started": (PENDING, TONES[PENDING]),
        "submitted": (PENDING, TONES[PENDING]),
        "grading": (PENDING, TONES[PENDING]),
        "review_required": (REVIEW, TONES[REVIEW]),
        "graded": (GRADED, TONES[GRADED]),
    }
    return mapping.get(sub.status, (sub.status, "neutral"))
