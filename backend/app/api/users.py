from fastapi import APIRouter, Depends, status
from sqlalchemy import update, func, or_, select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_roles, PaginationParams, pagination
from app.errors import api_error
from app.models import User, UserPreference
from app.roles import VALID_ROLES
from app.schemas import PaginatedResponse, PasswordUpdate, StatusUpdate, UserCreate, UserRead, UserUpdate
from app.schemas.preferences import UserPreferencesRead, UserPreferencesUpdate
from app.security import hash_password, validate_password_rules, verify_password

router = APIRouter(prefix="/users", tags=["users"])

VALID_STATUSES = {"active", "disabled"}


@router.get("", response_model=PaginatedResponse)
def list_users(
    role: str | None = None,
    status_filter: str | None = None,
    pagination: PaginationParams = Depends(pagination),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    page, page_size = pagination.page, pagination.page_size
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
    try:
        validate_password_rules(payload.password, payload.username)
    except ValueError:
        raise api_error(422, "PASSWORD_EQUALS_USERNAME", "密码不能与用户名相同")
    user = User(
        username=payload.username,
        student_no=student_no,
        real_name=payload.real_name,
        department=payload.department,
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
    pagination: PaginationParams = Depends(pagination),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("teacher", "admin")),
):
    """学生候选列表——教师选择白名单学生用，只暴露 active student"""
    page, page_size = pagination.page, pagination.page_size
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


@router.get("/me/preferences", response_model=UserPreferencesRead)
def get_my_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.get(UserPreference, current_user.id)
    if row is None:
        return UserPreferencesRead(user_id=current_user.id, preferences={})
    return UserPreferencesRead(user_id=row.user_id, preferences=row.preferences or {})


@router.patch("/me/preferences", response_model=UserPreferencesRead)
def update_my_preferences(
    payload: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = db.get(UserPreference, current_user.id)
    if row is None:
        row = UserPreference(user_id=current_user.id, preferences={})
        db.add(row)
    updates = payload.model_dump(exclude_unset=True)
    row.preferences = {**(row.preferences or {}), **updates}
    db.commit()
    db.refresh(row)
    return UserPreferencesRead(user_id=row.user_id, preferences=row.preferences or {})


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
    if "role" in updates and updates["role"] not in VALID_ROLES:
        raise api_error(422, "INVALID_ROLE", "角色无效")
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
    # 本人改密必须验证旧密码；管理员重置无需旧密码
    if current_user.role != "admin":
        if not payload.current_password or not verify_password(
            payload.current_password, user.password_hash
        ):
            raise api_error(401, "CURRENT_PASSWORD_INVALID", "当前密码不正确")
    # 密码不得等同规范化用户名（共享边界）
    try:
        validate_password_rules(payload.password, user.username)
    except ValueError:
        raise api_error(422, "PASSWORD_EQUALS_USERNAME", "密码不能与用户名相同")
    user.password_hash = hash_password(payload.password)
    # 改密/重置立即撤销该用户全部会话（原子递增）
    db.execute(
        update(User).where(User.id == user.id).values(session_version=User.session_version + 1)
    )
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
    if payload.status == "disabled":
        # 禁用立即撤销该用户全部会话（原子递增）
        db.execute(
            update(User).where(User.id == user.id).values(session_version=User.session_version + 1)
        )
    db.commit()
    db.refresh(user)
    return user
