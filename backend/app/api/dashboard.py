"""角色首页仪表盘端点——聚合逻辑全部在服务层，端点仅做角色锁定"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_roles
from app.models import User
from app.schemas.dashboard import StudentDashboardRead, TeacherDashboardRead
from app.services.dashboard_service import build_student_dashboard, build_teacher_dashboard

router = APIRouter(prefix="/dashboard", tags=["首页仪表盘"])


@router.get("/student", response_model=StudentDashboardRead)
def student_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    return build_student_dashboard(db, current_user)


@router.get("/teacher", response_model=TeacherDashboardRead)
def teacher_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher")),
):
    return build_teacher_dashboard(db, current_user)
