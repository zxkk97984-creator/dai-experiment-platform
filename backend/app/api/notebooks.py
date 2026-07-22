"""Notebook API 路由 — 教师上传、学生交互、代码执行、保存/提交/重置"""
import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import User
from app.schemas import (
    CellExecuteRequest,
    CellExecuteResponse,
    NotebookCellsSaveRequest,
    NotebookResponse,
    NotebookSaveResponse,
    NotebookSubmitResponse,
    TemplateUpgradeRequest,
)
from app.services.notebook_service import NotebookService

router = APIRouter(prefix="/notebooks", tags=["notebooks"])


def _get_service(db: Session) -> NotebookService:
    return NotebookService(db)


def _require_owner(record_id: int, student_id: int, db: Session):
    """校验记录所有权"""
    from app.models import NotebookRecord
    record = db.get(NotebookRecord, record_id)
    if not record or record.student_id != student_id:
        raise api_error(403, "FORBIDDEN", "无权访问此记录")


# ── 学生端 ─────────────────────────────────────────────────────


@router.get("/{lesson_id}", response_model=NotebookResponse)
def get_notebook(
    lesson_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    """获取 notebook 内容和学生副本状态"""
    svc = _get_service(db)
    try:
        data = svc.get_notebook_data(lesson_id, current_user.id)
        return data
    except ValueError as e:
        raise api_error(404, "NOTEBOOK_NOT_FOUND", str(e))


@router.put("/records/{record_id}/cells", response_model=NotebookSaveResponse)
def save_cells(
    record_id: int,
    body: NotebookCellsSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    """保存学生修改的代码（草稿）"""
    _require_owner(record_id, current_user.id, db)
    svc = _get_service(db)
    try:
        svc.save_cells(record_id, current_user.id, body.cells)
        return {"record_id": record_id}
    except ValueError as e:
        raise api_error(400, "SAVE_FAILED", str(e))


@router.post(
    "/records/{record_id}/cells/{cell_id}/execute",
    response_model=CellExecuteResponse,
)
def execute_cell(
    record_id: int,
    cell_id: str,
    body: CellExecuteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    """执行指定代码 cell（有状态，跨 cell 共享变量）"""
    _require_owner(record_id, current_user.id, db)
    svc = _get_service(db)
    try:
        result = svc.execute_cell(record_id, current_user.id, cell_id, body.code)
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise api_error(400, "EXECUTION_FAILED", str(e))


@router.post("/records/{record_id}/reset")
def reset_notebook(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    """重置为教师模板"""
    _require_owner(record_id, current_user.id, db)
    svc = _get_service(db)
    try:
        svc.reset_to_template(record_id, current_user.id)
        return {"message": "已重置为模板"}
    except ValueError as e:
        raise api_error(400, "RESET_FAILED", str(e))


@router.post("/records/{record_id}/submit", response_model=NotebookSubmitResponse)
def submit_notebook(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    """提交笔记本（生成不可变快照）"""
    _require_owner(record_id, current_user.id, db)
    svc = _get_service(db)
    try:
        sub = svc.submit(record_id, current_user.id)
        return {
            "record_id": record_id,
            "attempt_number": sub.attempt_number,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else "",
        }
    except ValueError as e:
        raise api_error(400, "SUBMIT_FAILED", str(e))


@router.post("/records/{record_id}/interrupt")
def interrupt_kernel(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    """中断当前 kernel 执行"""
    _require_owner(record_id, current_user.id, db)
    from app.services.kernel_manager import get_kernel_manager
    get_kernel_manager().interrupt(record_id)
    return {"message": "已中断"}


@router.post("/records/{record_id}/restart-kernel")
def restart_kernel(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    """重启 kernel（销毁旧容器并创建新的）"""
    _require_owner(record_id, current_user.id, db)
    from app.models import NotebookRecord as NR
    from app.services.kernel_manager import get_kernel_manager
    record = db.get(NR, record_id)
    lesson_dir = record.lesson.notebook_path or "" if record else ""
    get_kernel_manager().restart(record_id, lesson_dir)
    return {"message": "Kernel 已重启"}


@router.post("/records/{record_id}/upgrade-template")
def upgrade_template(
    record_id: int,
    body: TemplateUpgradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("student")),
):
    """处理模板升级（保留旧版或加载新版）"""
    _require_owner(record_id, current_user.id, db)
    svc = _get_service(db)
    try:
        svc.upgrade_template(record_id, current_user.id, body.action)
        return {"message": "已处理"}
    except ValueError as e:
        raise api_error(400, "UPGRADE_FAILED", str(e))


# ── 教师端 ─────────────────────────────────────────────────────


@router.post("/lessons/{lesson_id}/upload")
def upload_notebook(
    lesson_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    """教师上传 .ipynb 或 .zip 实验包"""
    # 校验文件扩展名
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".ipynb", ".zip"):
        raise api_error(400, "INVALID_FILE", "只支持 .ipynb 或 .zip 文件")

    # 保存到临时文件
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        svc = _get_service(db)
        result = svc.upload_notebook(lesson_id, tmp_path, current_user)
        return result
    except ValueError as e:
        raise api_error(400, "UPLOAD_FAILED", str(e))
    finally:
        os.unlink(tmp_path)
