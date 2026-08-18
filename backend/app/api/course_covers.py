"""课程封面接口：教师上传/移除 + 公开读取媒体。

- PUT/DELETE /courses/{id}/cover：仅管理员或课程 owner 教师可写，复用
  `require_course` / `ensure_course_manager`；
- GET /media/course-covers/{id}：公开读取，无登录、Cookie、Token 或签名；
  带匹配的版本参数 v 时返回一年 immutable 缓存，替换封面后 v 变化使旧
  缓存失效。
"""
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.courses import ensure_course_manager, require_course
from app.config import Settings, get_settings
from app.dependencies import get_current_user, get_db
from app.errors import api_error
from app.models import Course, User
from app.schemas import CourseRead
from app.storage import StorageArea, StorageError, StorageService
from app.services.course_cover_service import (
    COVER_KEY_PREFIX,
    content_type_for_storage_key,
    remove_storage_key,
    store_upload,
)
from app.services.storage_object_binding_service import (
    register_active_object,
    retire_bound_object,
)
from .storage_media import storage_response

router = APIRouter(tags=["course-covers"])


@router.put("/courses/{course_id}/cover", response_model=CourseRead)
async def put_course_cover(
    course_id: int,
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> CourseRead:
    # 权限判断先于文件写入，避免未授权用户占用磁盘
    course = require_course(course_id, db)
    ensure_course_manager(course, current_user)

    stored = await store_upload(file, course_id, settings)

    storage = StorageService.from_settings(settings)
    try:
        new_object = register_active_object(
            db,
            storage,
            area=StorageArea.COVERS,
            namespace="course-covers",
            object_key=stored.storage_key,
            original_filename=file.filename or "cover",
            content_type=stored.content_type,
            size_bytes=stored.size,
            created_by_id=current_user.id,
        )
        # 文件写入完成后锁定课程行，读取锁内真正的最新旧 key，
        # 避免并发上传互相覆盖时留下孤儿文件
        locked = db.execute(
            select(Course).where(Course.id == course_id).with_for_update()
        ).scalar_one()
        old_key = locked.cover
        old_object_id = locked.cover_object_id
        locked.cover = stored.storage_key
        locked.cover_object_id = new_object.id
        db.commit()
    except Exception:
        # 数据库提交失败：删除刚写入的新文件，保留旧字段和旧文件
        db.rollback()
        remove_storage_key(settings, stored.storage_key)
        raise
    # 业务行提交成功后才进入旧对象 deleting，避免先删旧对象造成数据丢失。
    retire_bound_object(
        db,
        storage,
        object_id=old_object_id,
        area=StorageArea.COVERS,
        legacy_key=old_key,
        logger_name="course_cover",
    )
    return locked


@router.delete("/courses/{course_id}/cover", status_code=status.HTTP_204_NO_CONTENT)
def delete_course_cover(
    course_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(get_current_user),
) -> None:
    course = require_course(course_id, db)
    ensure_course_manager(course, current_user)
    # 行锁确保不会和替换操作互相覆盖
    locked = db.execute(
        select(Course).where(Course.id == course_id).with_for_update()
    ).scalar_one()
    old_key = locked.cover
    old_object_id = locked.cover_object_id
    locked.cover = None
    locked.cover_object_id = None
    db.commit()
    retire_bound_object(
        db,
        StorageService.from_settings(settings),
        object_id=old_object_id,
        area=StorageArea.COVERS,
        legacy_key=old_key,
        logger_name="course_cover",
    )
    return None


@router.get("/media/course-covers/{course_id}")
def get_course_cover_media(
    course_id: int,
    request: Request,
    v: Annotated[str | None, Query()] = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    course = db.get(Course, course_id)
    # 统一 404，隐藏“课程不存在”和“课程存在但没有可读取封面”的差异
    if not course or not course.cover or not course.cover.startswith(COVER_KEY_PREFIX):
        raise api_error(404, "COVER_NOT_FOUND", "封面不存在")
    # 版本参数与当前 key 不同：旧 URL 在未命中缓存时不得读取到新图
    if v is not None and v != course.cover:
        raise api_error(404, "COVER_NOT_FOUND", "封面不存在")
    try:
        response = storage_response(
            request,
            StorageService.from_settings(settings),
            StorageArea.COVERS,
            course.cover,
            media_type=content_type_for_storage_key(course.cover),
            headers={
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": (
                    "public, max-age=31536000, immutable"
                    if v is not None
                    else "public, max-age=300"
                ),
            },
        )
    except StorageError:
        raise api_error(404, "COVER_NOT_FOUND", "封面不存在")
    return response
