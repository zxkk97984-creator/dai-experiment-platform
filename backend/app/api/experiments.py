from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db, require_roles
from app.errors import api_error
from app.models import ExperimentModule, ExperimentRecord, User
from app.schemas import ExperimentModuleCreate, ExperimentModuleRead, ExperimentRecordCreate, ExperimentRecordRead, PaginatedResponse

router = APIRouter(prefix="/experiments", tags=["experiments"])


def record_read(record: ExperimentRecord) -> ExperimentRecordRead:
    return ExperimentRecordRead(
        id=record.id,
        module_id=record.module_id,
        student_id=record.student_id,
        status=record.status,
        metadata=record.metadata_json or {},
    )


@router.get("/modules", response_model=PaginatedResponse)
def list_modules(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    modules = db.scalars(select(ExperimentModule).order_by(ExperimentModule.id)).all()
    return PaginatedResponse(items=[ExperimentModuleRead.model_validate(module) for module in modules], page=1, page_size=len(modules) or 20, total=len(modules))


@router.post("/modules", response_model=ExperimentModuleRead, status_code=status.HTTP_201_CREATED)
def create_module(
    payload: ExperimentModuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer")),
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
