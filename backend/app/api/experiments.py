"""统一实验 API — 模块管理 + 记录管理 + Cell 操作 + 提交（v5 统一模型）"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import (
    CourseEnrollment,
    ExperimentModule,
    ExperimentRecord,
    Lesson,
    NotebookTemplate,
    NotebookTemplateVersion,
    User,
)
from app.schemas import (
    ExperimentCellExecuteRequest,
    ExperimentCellExecuteResponse,
    ExperimentCellOut,
    ExperimentCellsSaveRequest,
    ExperimentModuleCreate,
    ExperimentModuleRead,
    ExperimentRecordDetailResponse,
    ExperimentRecordRead,
    PaginatedResponse,
)
from app.services.kernel_manager import get_kernel_manager

router = APIRouter(prefix="/experiments", tags=["experiments"])

# ── 工具函数 ──────────────────────────────────────────────────


def _record_read(record: ExperimentRecord) -> ExperimentRecordRead:
    return ExperimentRecordRead(
        id=record.id,
        lesson_id=record.lesson_id,
        module_id=record.module_id,
        student_id=record.student_id,
        status=record.status,
        template_version_id=record.template_version_id,
        record_revision=record.record_revision,
        cells_sources=record.cells_sources,
        started_at=record.started_at,
        submitted_at=record.submitted_at,
    )


def _require_owner(record: ExperimentRecord, current_user: User) -> None:
    """确保当前用户是该实验记录的所有者"""
    if record.student_id != current_user.id:
        raise api_error(403, "FORBIDDEN", "无权操作此实验记录")


def _require_record_accessible(record: ExperimentRecord, current_user: User, db: Session) -> None:
    """校验 record 所有权 + 其关联的 lesson/module 当前仍可访问"""
    _require_owner(record, current_user)
    if record.lesson_id:
        _check_lesson_access(record.lesson_id, current_user.id, db)
    elif record.module_id:
        _check_module_access(record.module_id, db)


def _ensure_template_version(
    lesson_id: int | None,
    module_id: int | None,
    db: Session,
) -> NotebookTemplateVersion:
    if lesson_id:
        lesson = db.get(Lesson, lesson_id)
        if not lesson or not lesson.template_id:
            raise api_error(404, "TEMPLATE_NOT_FOUND", "该课时未关联 Notebook 模板")
        template = db.get(NotebookTemplate, lesson.template_id)
    elif module_id:
        module = db.get(ExperimentModule, module_id)
        if not module or not module.template_id:
            raise api_error(404, "TEMPLATE_NOT_FOUND", "该模块未关联 Notebook 模板")
        template = db.get(NotebookTemplate, module.template_id)
    else:
        raise api_error(400, "INVALID_ENTRY", "必须指定 lesson_id 或 module_id")

    if not template or not template.current_version_id:
        raise api_error(404, "VERSION_NOT_FOUND", "该模板尚未发布版本")

    version = db.get(NotebookTemplateVersion, template.current_version_id)
    if not version:
        raise api_error(404, "VERSION_NOT_FOUND", "模板版本不存在")
    if version.template_id != template.id:
        raise api_error(500, "VERSION_MISMATCH", "模板版本不匹配")
    return version


def _check_lesson_access(lesson_id: int, student_id: int, db: Session) -> Lesson:
    """校验学生有权限访问课时：课程 published + 选课 enrolled"""
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise api_error(404, "LESSON_NOT_FOUND", "课时不存在")
    chapter = lesson.chapter
    if not chapter:
        raise api_error(404, "CHAPTER_NOT_FOUND", "章节不存在")
    course = chapter.course
    if not course or course.status != "published":
        raise api_error(403, "COURSE_NOT_AVAILABLE", "课程未发布")
    enrollment = db.scalar(
        select(CourseEnrollment).where(
            CourseEnrollment.course_id == course.id,
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.status == "enrolled",
        )
    )
    if not enrollment:
        raise api_error(403, "NOT_ENROLLED", "请先选课")
    return lesson


def _check_module_access(module_id: int, db: Session) -> ExperimentModule:
    module = db.get(ExperimentModule, module_id)
    if not module:
        raise api_error(404, "EXPERIMENT_MODULE_NOT_FOUND", "实验模块不存在")
    if module.status != "published":
        raise api_error(403, "MODULE_NOT_PUBLISHED", "实验模块未发布")
    return module


# ── 实验模块 API（Notebook 风格 kernel 端点）───────────────────


@router.get("/modules", response_model=PaginatedResponse)
def list_modules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(ExperimentModule)
    if current_user.role == "student":
        query = query.where(ExperimentModule.status == "published")
    elif current_user.role == "developer":
        query = query.where(ExperimentModule.owner_id == current_user.id)
    modules = db.scalars(query.order_by(ExperimentModule.id)).all()
    return PaginatedResponse(
        items=[ExperimentModuleRead.model_validate(m) for m in modules],
        page=1, page_size=max(len(modules), 1), total=len(modules),
    )


@router.post("/modules", response_model=ExperimentModuleRead, status_code=status.HTTP_201_CREATED)
def create_module(
    payload: ExperimentModuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "developer")),
):
    module = ExperimentModule(**payload.model_dump(), owner_id=current_user.id)
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


@router.get("/modules/{module_id}", response_model=ExperimentModuleRead)
def get_module(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    module = db.get(ExperimentModule, module_id)
    if not module:
        raise api_error(404, "EXPERIMENT_MODULE_NOT_FOUND", "实验模块不存在")
    if current_user.role == "student" and module.status != "published":
        raise api_error(403, "FORBIDDEN", "无权查看未发布的实验模块")
    return module


@router.patch("/modules/{module_id}", response_model=ExperimentModuleRead)
def patch_module(
    module_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "developer")),
):
    module = db.get(ExperimentModule, module_id)
    if not module:
        raise api_error(404, "EXPERIMENT_MODULE_NOT_FOUND", "实验模块不存在")
    if current_user.role == "developer" and module.owner_id != current_user.id:
        raise api_error(403, "FORBIDDEN", "无权管理其他开发者的实验模块")
    for key in ("name", "description", "template_id", "status"):
        if key in payload:
            setattr(module, key, payload[key])
    db.commit()
    db.refresh(module)
    return module


# ── 记录管理 ──────────────────────────────────────────────────


@router.post("/records/ensure-for-lesson/{lesson_id}", response_model=ExperimentRecordRead)
def ensure_record_for_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    _check_lesson_access(lesson_id, current_user.id, db)

    existing = db.scalar(
        select(ExperimentRecord).where(
            ExperimentRecord.lesson_id == lesson_id,
            ExperimentRecord.student_id == current_user.id,
        )
    )
    if existing:
        return _record_read(existing)

    version = _ensure_template_version(lesson_id=lesson_id, module_id=None, db=db)
    record = ExperimentRecord(
        lesson_id=lesson_id, module_id=None,
        template_version_id=version.id,
        student_id=current_user.id,
        status="started",
        started_at=datetime.now(timezone.utc),
        cells_sources={
            cell["id"]: cell["source"]
            for cell in version.cells
            if cell.get("type") == "code" and not cell.get("source_hidden")
        },
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _record_read(record)


@router.post("/records/ensure-for-module/{module_id}", response_model=ExperimentRecordRead)
def ensure_record_for_module(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    _check_module_access(module_id, db)

    existing = db.scalar(
        select(ExperimentRecord).where(
            ExperimentRecord.module_id == module_id,
            ExperimentRecord.student_id == current_user.id,
        )
    )
    if existing:
        return _record_read(existing)

    version = _ensure_template_version(lesson_id=None, module_id=module_id, db=db)
    record = ExperimentRecord(
        lesson_id=None, module_id=module_id,
        template_version_id=version.id,
        student_id=current_user.id,
        status="started",
        started_at=datetime.now(timezone.utc),
        cells_sources={
            cell["id"]: cell["source"]
            for cell in version.cells
            if cell.get("type") == "code" and not cell.get("source_hidden")
        },
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _record_read(record)


# ── Notebook 风格实验 API ──────────────────────────────────────


@router.get("/records/{record_id}", response_model=ExperimentRecordDetailResponse)
def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_record_accessible(record, current_user, db)

    version = db.get(NotebookTemplateVersion, record.template_version_id)
    if not version:
        raise api_error(500, "VERSION_MISSING", "模板版本丢失")

    cells_out = []
    for cell in version.cells:
        if cell.get("source_hidden"):
            continue
        cell_id = cell["id"]
        outputs = record.cells_outputs.get(cell_id)
        cells_out.append(ExperimentCellOut(
            id=cell_id,
            type=cell.get("type", "code"),
            source=record.cells_sources.get(cell_id, cell.get("source", "")),
            order=cell.get("order", 0),
            student_editable=cell.get("student_editable", True),
            outputs=outputs,
            is_running=False,
        ))

    entry_name = ""
    entry_description = None
    if record.lesson_id and record.lesson:
        entry_name = record.lesson.title
    elif record.module_id and record.module:
        entry_name = record.module.name
        entry_description = record.module.description

    visible_count = sum(
        1 for cell in cells_out
        if cell.id in record.cells_outputs
        and not any(c.get("id") == cell.id and c.get("source_hidden") for c in version.cells)
    )

    return ExperimentRecordDetailResponse(
        id=record.id, lesson_id=record.lesson_id, module_id=record.module_id,
        student_id=record.student_id, status=record.status,
        template_version_id=record.template_version_id,
        record_revision=record.record_revision,
        entry_name=entry_name, entry_description=entry_description,
        cells=cells_out, execution_count=visible_count,
    )


@router.get("/records", response_model=PaginatedResponse)
def list_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(ExperimentRecord)
    if current_user.role == "student":
        query = query.where(ExperimentRecord.student_id == current_user.id)
    records = db.scalars(query.order_by(ExperimentRecord.id)).all()

    # 过滤已无权访问的记录（退课/课程下架等）
    visible = []
    for r in records:
        try:
            _require_record_accessible(r, current_user, db)
            visible.append(r)
        except Exception:
            pass

    return PaginatedResponse(
        items=[_record_read(r) for r in visible],
        page=1, page_size=max(len(visible), 1), total=len(visible),
    )


@router.put("/records/{record_id}/cells")
def save_cells(
    record_id: int,
    payload: ExperimentCellsSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_record_accessible(record, current_user, db)

    if payload.record_revision != record.record_revision:
        raise api_error(409, "REVISION_CONFLICT", "记录已被他人修改，请刷新后重试")

    version = db.get(NotebookTemplateVersion, record.template_version_id)
    if version:
        editable_ids = {
            cell["id"] for cell in version.cells
            if cell.get("type") == "code"
            and cell.get("student_editable", True)
            and not cell.get("source_hidden")
        }
        for cell_id in payload.cells:
            if cell_id not in editable_ids:
                raise api_error(403, "CELL_NOT_EDITABLE", f"Cell {cell_id} 不允许修改")

    merged = dict(record.cells_sources)
    merged.update(payload.cells)
    record.cells_sources = merged
    record.record_revision += 1
    db.commit()
    return {"record_id": record_id, "record_revision": record.record_revision}


def _visible_execution_count(record: ExperimentRecord, version) -> int:
    """计算可见 cell 的最大 execution_count（排除 hidden cells）"""
    if not version:
        return 0
    hidden_ids = {c["id"] for c in version.cells if c.get("source_hidden")}
    max_count = 0
    for cid, output in record.cells_outputs.items():
        if cid not in hidden_ids and isinstance(output, dict):
            cnt = output.get("execution_count", 0)
            if cnt > max_count:
                max_count = cnt
    return max_count


@router.post("/records/{record_id}/cells/{cell_id}/execute", response_model=ExperimentCellExecuteResponse)
def execute_cell(
    record_id: int,
    cell_id: str,
    payload: ExperimentCellExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_record_accessible(record, current_user, db)

    version = db.get(NotebookTemplateVersion, record.template_version_id)
    if version:
        cell_def = next((c for c in version.cells if c["id"] == cell_id), None)
        if cell_def is None:
            raise api_error(404, "CELL_NOT_FOUND", f"Cell {cell_id} 不存在")
        if cell_def.get("source_hidden"):
            raise api_error(403, "CELL_HIDDEN", f"Cell {cell_id} 不可直接执行")
        if cell_def.get("type") != "code":
            raise api_error(400, "CELL_NOT_CODE", f"Cell {cell_id} 不是代码 cell")
        if not cell_def.get("student_editable", True):
            expected = record.cells_sources.get(cell_id, cell_def.get("source", ""))
            if payload.code != expected:
                raise api_error(403, "CELL_READONLY", f"Cell {cell_id} 为只读，不允许修改源码")

    if len(payload.code) > 50000:
        raise api_error(400, "CODE_TOO_LONG", "代码过长，最多 50000 字符")

    _init_hidden_cells_once(record, version, db)

    try:
        km = get_kernel_manager()
        km.get_or_create_session(record_id)
        result = km.execute(record_id, payload.code)
    except RuntimeError as e:
        raise api_error(409, "KERNEL_BUSY", str(e))
    except Exception as e:
        raise api_error(500, "KERNEL_ERROR", f"执行失败：{e}")

    outputs = record.cells_outputs.copy()
    execution_count = _visible_execution_count(record, version) + 1
    outputs[cell_id] = {
        "execution_count": execution_count,
        "outputs": result["outputs"],
        "execution_time_ms": result["execution_time_ms"],
    }
    record.cells_outputs = outputs
    db.commit()

    return ExperimentCellExecuteResponse(
        outputs=result["outputs"],
        execution_time_ms=result["execution_time_ms"],
        execution_count=execution_count,
    )


def _init_hidden_cells_once(record: ExperimentRecord, version, db: Session) -> None:
    """仅在 kernel 首次创建时按 order 执行 hidden cells。成功后在 Redis + session 标记。"""
    if not version:
        return
    hidden_cells = sorted(
        [c for c in version.cells if c.get("source_hidden") and c.get("type") == "code"],
        key=lambda c: c.get("order", 0),
    )
    if not hidden_cells:
        return

    km = get_kernel_manager()
    try:
        km.get_or_create_session(record.id)
    except Exception as e:
        raise api_error(500, "KERNEL_INIT_FAILED", f"Kernel 创建失败：{e}")

    version_id = record.template_version_id
    if km.is_template_initialized(record.id, version_id):
        return

    for cell in hidden_cells:
        try:
            km.execute(record.id, cell["source"])
        except Exception:
            km.destroy(record.id)
            raise api_error(500, "KERNEL_INIT_FAILED",
                            f"隐藏初始化 cell {cell['id']} 执行失败，Kernel 已销毁")

    try:
        km.mark_template_initialized(record.id, version_id)
    except Exception as e:
        km.destroy(record.id)
        raise api_error(
            500,
            "KERNEL_INIT_FAILED",
            f"Kernel 初始化状态保存失败，Kernel 已销毁：{e}",
        )


@router.post("/records/{record_id}/interrupt")
def interrupt_kernel(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_record_accessible(record, current_user, db)

    km = get_kernel_manager()
    km.interrupt(record_id)
    return {"status": "interrupted"}


@router.post("/records/{record_id}/restart")
def restart_kernel(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_record_accessible(record, current_user, db)

    record.cells_outputs = {}
    db.commit()

    km = get_kernel_manager()
    km.restart(record_id)
    return {"status": "restarted"}
