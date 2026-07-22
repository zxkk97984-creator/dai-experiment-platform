import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import ExperimentModule, ExperimentRecord, User
from app.schemas import (
    ExperimentCellExecuteRequest,
    ExperimentCellExecuteResponse,
    ExperimentCellsSaveRequest,
    ExperimentModuleCreate,
    ExperimentModuleRead,
    ExperimentRecordCreate,
    ExperimentRecordDetailResponse,
    ExperimentRecordRead,
    PaginatedResponse,
)
from app.services.kernel_manager import get_kernel_manager

router = APIRouter(prefix="/experiments", tags=["experiments"])

# ── 实验模块 API（Notebook 风格）──

def record_read(record: ExperimentRecord) -> ExperimentRecordRead:
    return ExperimentRecordRead(
        id=record.id,
        module_id=record.module_id,
        student_id=record.student_id,
        status=record.status,
        metadata=record.metadata_json or {},
    )


def _require_owner(record: ExperimentRecord, current_user: User) -> None:
    """确保当前用户是该实验记录的所有者"""
    if record.student_id != current_user.id:
        raise api_error(403, "FORBIDDEN", "无权操作此实验记录")


def _get_or_create_record(module_id: int, student_id: int, db: Session) -> ExperimentRecord:
    """获取或创建学生的实验记录"""
    record = db.scalar(
        select(ExperimentRecord).where(
            ExperimentRecord.module_id == module_id,
            ExperimentRecord.student_id == student_id,
        )
    )
    if not record:
        record = ExperimentRecord(
            module_id=module_id,
            student_id=student_id,
            status="started",
            metadata_json={
                "cells": {},
                "cell_order": [],
                "cell_outputs": {},
                "execution_count": 0,
            },
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


@router.get("/modules", response_model=PaginatedResponse)
def list_modules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    modules = db.scalars(select(ExperimentModule).order_by(ExperimentModule.id)).all()
    return PaginatedResponse(items=[ExperimentModuleRead.model_validate(module) for module in modules], page=1, page_size=len(modules) or 20, total=len(modules))


@router.post("/modules", response_model=ExperimentModuleRead, status_code=status.HTTP_201_CREATED)
def create_module(
    payload: ExperimentModuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer", "teacher")),
):
    module = ExperimentModule(**payload.model_dump())
    db.add(module)
    db.commit()
    db.refresh(module)
    return module


@router.get("/modules/{module_id}", response_model=ExperimentModuleRead)
def get_module(module_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    module = db.get(ExperimentModule, module_id)
    if not module:
        raise api_error(404, "EXPERIMENT_MODULE_NOT_FOUND", "实验模块不存在")
    return module


@router.post("/records", response_model=ExperimentRecordRead, status_code=status.HTTP_201_CREATED)
def create_record(
    payload: ExperimentRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    if not db.get(ExperimentModule, payload.module_id):
        raise api_error(404, "EXPERIMENT_MODULE_NOT_FOUND", "实验模块不存在")
    record = ExperimentRecord(
        module_id=payload.module_id,
        student_id=current_user.id,
        status=payload.status,
        metadata_json=payload.metadata,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record_read(record)


@router.get("/records", response_model=PaginatedResponse)
def list_records(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(ExperimentRecord)
    if current_user.role == "student":
        query = query.where(ExperimentRecord.student_id == current_user.id)
    records = db.scalars(query.order_by(ExperimentRecord.id)).all()
    return PaginatedResponse(items=[record_read(record) for record in records], page=1, page_size=len(records) or 20, total=len(records))


# ── Notebook 风格实验 API ──────────────────────────────────────


@router.get("/records/{record_id}", response_model=ExperimentRecordDetailResponse)
def get_record_detail(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取实验记录详情（含 cells 和 outputs）"""
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_owner(record, current_user)

    module = db.get(ExperimentModule, record.module_id)
    meta = record.metadata_json or {}
    cells_data = meta.get("cells", {})
    cell_order = meta.get("cell_order", [])
    cell_outputs = meta.get("cell_outputs", {})
    execution_count = meta.get("execution_count", 0)

    cells = []
    for cell_id in cell_order:
        cell_info = cells_data.get(cell_id, {})
        cells.append({
            "id": cell_id,
            "source": cell_info.get("source", ""),
            "order": cell_info.get("order", 0),
            "outputs": cell_outputs.get(cell_id),
            "is_running": False,
        })

    return ExperimentRecordDetailResponse(
        id=record.id,
        module_id=record.module_id,
        student_id=record.student_id,
        status=record.status,
        module_name=module.name if module else "",
        module_description=module.description if module else None,
        cells=cells,
        cell_order=cell_order,
        execution_count=execution_count,
    )


@router.put("/records/{record_id}/cells")
def save_cells(
    record_id: int,
    payload: ExperimentCellsSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存实验 cells 源码"""
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_owner(record, current_user)

    meta = dict(record.metadata_json or {})
    cells_data = meta.get("cells", {})

    # 更新 cells 源码
    for cell_id, source in payload.cells.items():
        if cell_id in cells_data:
            cells_data[cell_id]["source"] = source
        else:
            # 新 cell
            order = len(payload.cell_order) if payload.cell_order else len(cells_data)
            cells_data[cell_id] = {"source": source, "order": order}

    # 清理已删除的 cell
    valid_ids = set(payload.cells.keys())
    for cid in list(cells_data.keys()):
        if cid not in valid_ids:
            del cells_data[cid]
            meta.get("cell_outputs", {}).pop(cid, None)

    meta["cells"] = cells_data
    if payload.cell_order:
        meta["cell_order"] = payload.cell_order

    record.metadata_json = meta
    db.commit()
    return {"record_id": record_id}


@router.post("/records/{record_id}/cells/{cell_id}/execute", response_model=ExperimentCellExecuteResponse)
def execute_cell(
    record_id: int,
    cell_id: str,
    payload: ExperimentCellExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """在 Docker kernel 中执行代码"""
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_owner(record, current_user)

    if len(payload.code) > 50000:
        raise api_error(400, "CODE_TOO_LONG", "代码过长，最多 50000 字符")

    try:
        km = get_kernel_manager()
        session = km.get_or_create_session(record_id)
        result = km.execute(record_id, payload.code)
    except RuntimeError as e:
        raise api_error(409, "KERNEL_BUSY", str(e))
    except Exception as e:
        raise api_error(500, "KERNEL_ERROR", f"执行失败：{e}")

    # 更新 outputs 到 metadata
    meta = dict(record.metadata_json or {})
    cell_outputs = meta.get("cell_outputs", {})
    execution_count = meta.get("execution_count", 0) + 1

    cell_outputs[cell_id] = {
        "execution_count": execution_count,
        "outputs": result["outputs"],
    }
    meta["cell_outputs"] = cell_outputs
    meta["execution_count"] = execution_count
    record.metadata_json = meta
    db.commit()

    return ExperimentCellExecuteResponse(
        outputs=result["outputs"],
        execution_time_ms=result["execution_time_ms"],
        execution_count=execution_count,
    )


@router.post("/records/{record_id}/interrupt")
def interrupt_kernel(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """中断当前 kernel 执行"""
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_owner(record, current_user)

    km = get_kernel_manager()
    km.interrupt(record_id)
    return {"status": "interrupted"}


@router.post("/records/{record_id}/restart")
def restart_kernel(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重启 kernel（清除所有 outputs）"""
    record = db.get(ExperimentRecord, record_id)
    if not record:
        raise api_error(404, "RECORD_NOT_FOUND", "实验记录不存在")
    _require_owner(record, current_user)

    # 清除 outputs
    meta = dict(record.metadata_json or {})
    meta["cell_outputs"] = {}
    meta["execution_count"] = 0
    record.metadata_json = meta
    db.commit()

    # 重启 kernel
    km = get_kernel_manager()
    km.restart(record_id)
    return {"status": "restarted"}


@router.post("/records/ensure/{module_id}", response_model=ExperimentRecordRead)
def ensure_record(
    module_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """确保学生有该模块的实验记录（不存在则创建）"""
    if not db.get(ExperimentModule, module_id):
        raise api_error(404, "EXPERIMENT_MODULE_NOT_FOUND", "实验模块不存在")
    record = _get_or_create_record(module_id, current_user.id, db)
    return record_read(record)
