"""教师成绩统计总览 API。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_roles
from app.models import User
from app.schemas.statistics import TeacherGradeStatisticsRead
from app.services.statistics_service import build_teacher_grade_statistics

router = APIRouter(prefix="/teacher", tags=["成绩统计"])


@router.get("/grade-statistics", response_model=TeacherGradeStatisticsRead)
def grade_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher")),
):
    return build_teacher_grade_statistics(db, current_user)
