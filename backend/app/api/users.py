from fastapi import APIRouter, Depends, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import User
from app.schemas import PaginatedResponse, PasswordUpdate, StatusUpdate, UserCreate, UserRead, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = {"student", "teacher", "admin", "developer"}
VALID_STATUSES = {"active", "disabled"}


@router.get("", response_model=PaginatedResponse)
def list_users(
    page: int = 1,
    page_size: int = 20,
    role: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    query = select(User)
    count_query = select(func.count()).select_from(User)
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if status_filter:
        query = query.where(User.status == status_filter)
        count_query = count_query.where(User.status == status_filter)
    total = db.scalar(count_query) or 0
    users = db.scalars(query.order_by(User.id).offset((page - 1) * page_size).limit(page_size)).all()
    return PaginatedResponse(items=[UserRead.model_validate(user) for user in users], page=page, page_size=page_size, total=total)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    if payload.role not in VALID_ROLES:
        raise api_error(400, "INVALID_ROLE", "角色无效")
    if payload.status not in VALID_STATUSES:
        raise api_error(400, "INVALID_STATUS", "用户状态无效")
    if db.scalar(select(User).where(User.username == payload.username)):
        raise api_error(409, "USERNAME_EXISTS", "用户名已存在")
    student_no = payload.student_no.strip() if payload.student_no else None
    if payload.role == "student" and not student_no:
        raise api_error(422, "STUDENT_NO_REQUIRED", "新建学生必须填写学号")
    if student_no and db.scalar(select(User).where(User.student_no == student_no)):
        raise api_error(409, "STUDENT_NO_EXISTS", "学号已存在")
    user = User(
        username=payload.username,
        student_no=student_no,
        real_name=payload.real_name,
        role=payload.role,
        status=payload.status,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/students", response_model=PaginatedResponse)
def list_students(
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """学生候选列表——教师选择白名单学生用，只暴露 active student"""
    page_size = max(1, min(page_size, 100))
    filters = (User.role == "student", User.status == "active")
    query = select(User).where(*filters)
    count_query = select(func.count()).select_from(User).where(*filters)
    if q:
        like = f"%{q}%"
        name_match = or_(User.username.ilike(like), User.real_name.ilike(like))
        query = query.where(name_match)
        count_query = count_query.where(name_match)
    total = db.scalar(count_query) or 0
    users = db.scalars(
        query.order_by(User.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return PaginatedResponse(
        items=[UserRead.model_validate(user) for user in users],
        page=page, page_size=page_size, total=total,
    )


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise api_error(403, "FORBIDDEN", "没有权限查看该用户")
    user = db.get(User, user_id)
    if not user:
        raise api_error(404, "USER_NOT_FOUND", "用户不存在")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise api_error(403, "FORBIDDEN", "没有权限修改该用户")
    user = db.get(User, user_id)
    if not user:
        raise api_error(404, "USER_NOT_FOUND", "用户不存在")
    updates = payload.model_dump(exclude_unset=True)
    if "role" in updates and current_user.role != "admin":
        raise api_error(403, "FORBIDDEN", "只有管理员可以修改角色")
    if "student_no" in updates:
        student_no = updates["student_no"].strip() if updates["student_no"] else None
        target_role = updates.get("role", user.role)
        if target_role == "student" and not student_no:
            raise api_error(422, "STUDENT_NO_REQUIRED", "学生必须填写学号")
        duplicate = db.scalar(select(User).where(User.student_no == student_no, User.id != user_id)) if student_no else None
        if duplicate:
            raise api_error(409, "STUDENT_NO_EXISTS", "学号已存在")
        updates["student_no"] = student_no
    for key, value in updates.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/password", response_model=UserRead)
def update_password(
    user_id: int,
    payload: PasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin" and current_user.id != user_id:
        raise api_error(403, "FORBIDDEN", "没有权限修改该用户密码")
    user = db.get(User, user_id)
    if not user:
        raise api_error(404, "USER_NOT_FOUND", "用户不存在")
    user.password_hash = hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/status", response_model=UserRead)
def update_status(
    user_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    if payload.status not in VALID_STATUSES:
        raise api_error(400, "INVALID_STATUS", "用户状态无效")
    user = db.get(User, user_id)
    if not user:
        raise api_error(404, "USER_NOT_FOUND", "用户不存在")
    user.status = payload.status
    db.commit()
    db.refresh(user)
    return user
