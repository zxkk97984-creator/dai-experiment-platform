from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.dependencies import get_db, require_roles
from app.errors import api_error
from app.models import User
from app.schemas.studio import (
    StudioDraftUpdate,
    StudioImportCreate,
    StudioImportExisting,
    StudioPreviewRunRequest,
    StudioPreviewRunResponse,
    StudioTemplateBindRequest,
    StudioTemplateCreate,
    StudioTemplateMetadataUpdate,
    StudioTemplateRead,
    StudioVersionRead,
)
from app.services.kernel_manager import get_kernel_manager
from app.services import studio_service


router = APIRouter(prefix="/studio", tags=["studio"])
studio_user = require_roles("admin", "teacher", "developer")


def _import_create_form(
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
    lesson_id: Annotated[int | None, Form()] = None,
    module_id: Annotated[int | None, Form()] = None,
    environment_version_id: Annotated[int | None, Form()] = None,
    import_policy_mode: Annotated[str | None, Form()] = None,
    allowed_imports_json: Annotated[str | None, Form()] = None,
) -> StudioImportCreate:
    """导入创建表单——环境字段可选；allowed_imports 以 JSON 数组字符串传输。"""
    allowed_imports: list[str] = []
    if allowed_imports_json:
        try:
            parsed = json.loads(allowed_imports_json)
        except ValueError:
            raise api_error(422, "IMPORT_INVALID_ALLOWED_IMPORTS", "allowed_imports 必须是 JSON 数组")
        if not isinstance(parsed, list) or not all(isinstance(x, str) for x in parsed):
            raise api_error(422, "IMPORT_INVALID_ALLOWED_IMPORTS", "allowed_imports 必须是字符串数组")
        allowed_imports = parsed
    return StudioImportCreate(
        name=name,
        description=description,
        lesson_id=lesson_id,
        module_id=module_id,
        environment_version_id=environment_version_id,
        import_policy_mode=import_policy_mode or "unrestricted",
        allowed_imports=allowed_imports,
    )


def _import_existing_form(
    draft_revision: Annotated[int, Form()],
) -> StudioImportExisting:
    return StudioImportExisting(draft_revision=draft_revision)


@router.get("/templates", response_model=list[StudioTemplateRead])
def get_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    return studio_service.list_templates(db, current_user)


@router.post(
    "/templates",
    response_model=StudioTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
def post_template(
    payload: StudioTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.create_template(db, payload, current_user)
    return studio_service.template_read(db, template)


# This static route is intentionally registered before /templates/{id}.
@router.post(
    "/templates/import",
    response_model=StudioTemplateRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_new_template(
    file: Annotated[UploadFile, File()],
    payload: StudioImportCreate = Depends(_import_create_form),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(studio_user),
):
    data = await file.read(studio_service.MAX_IMPORT_BYTES + 1)
    imported = studio_service.parse_import(file.filename or "", data)
    template = studio_service.create_imported_template(
        db,
        settings,
        current_user,
        name=payload.name,
        description=payload.description,
        lesson_id=payload.lesson_id,
        module_id=payload.module_id,
        environment_version_id=payload.environment_version_id,
        import_policy_mode=payload.import_policy_mode,
        allowed_imports=payload.allowed_imports,
        imported=imported,
    )
    return studio_service.template_read(db, template)


@router.get("/templates/{template_id}", response_model=StudioTemplateRead)
def get_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    return studio_service.template_read(db, template)


@router.patch("/templates/{template_id}", response_model=StudioTemplateRead)
def patch_template(
    template_id: int,
    payload: StudioTemplateMetadataUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    template = studio_service.update_metadata(db, template, payload)
    return studio_service.template_read(db, template)


@router.post("/templates/{template_id}/bind", response_model=StudioTemplateRead)
def bind_template(
    template_id: int,
    payload: StudioTemplateBindRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    template = studio_service.bind_template(db, template, payload, current_user)
    return studio_service.template_read(db, template)


@router.put("/templates/{template_id}/draft", response_model=StudioTemplateRead)
def put_draft(
    template_id: int,
    payload: StudioDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    template = studio_service.save_draft(db, template, payload)
    # Invalidation must not eagerly create a replacement container.
    get_kernel_manager().destroy(
        studio_service.preview_session_key(template.id, current_user.id)
    )
    return studio_service.template_read(db, template)


@router.post(
    "/templates/{template_id}/import",
    response_model=StudioTemplateRead,
)
async def import_existing_template(
    template_id: int,
    file: Annotated[UploadFile, File()],
    payload: StudioImportExisting = Depends(_import_existing_form),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    data = await file.read(studio_service.MAX_IMPORT_BYTES + 1)
    imported = studio_service.parse_import(file.filename or "", data)
    template = studio_service.import_into_template(
        db,
        settings,
        template,
        expected_revision=payload.draft_revision,
        imported=imported,
    )
    get_kernel_manager().destroy(
        studio_service.preview_session_key(template.id, current_user.id)
    )
    return studio_service.template_read(db, template)


@router.post(
    "/templates/{template_id}/publish",
    response_model=StudioVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def publish_template(
    template_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: User = Depends(studio_user),
):
    version = studio_service.publish_template(
        db, settings, template_id, current_user
    )
    return studio_service._version_read(version)


@router.get(
    "/templates/{template_id}/versions",
    response_model=list[StudioVersionRead],
)
def get_history(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    return studio_service.list_versions(db, template)


@router.get(
    "/templates/{template_id}/versions/{version_id}",
    response_model=StudioVersionRead,
)
def get_history_version(
    template_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    version = studio_service.get_version(db, template, version_id)
    return studio_service._version_read(version)


@router.get("/templates/{template_id}/export")
def export_template(
    template_id: int,
    scope: Literal["draft"] = Query(default="draft"),
    version_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    if version_id is not None:
        version = studio_service.get_version(db, template, version_id)
        cells = version.cells
        metadata = version.notebook_metadata or {}
        suffix = f"v{version.version_number}"
    elif scope == "draft":
        cells = template.draft_cells or []
        metadata = template.draft_metadata or {}
        suffix = "draft"
    else:
        raise api_error(422, "VERSION_REQUIRED", "请选择要导出的模板版本")
    content = studio_service.export_notebook(cells, metadata)
    filename = f"template-{template.id}-{suffix}.ipynb"
    return Response(
        content=content,
        media_type="application/x-ipynb+json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/templates/{template_id}/preview/run",
    response_model=StudioPreviewRunResponse,
)
def run_preview(
    template_id: int,
    payload: StudioPreviewRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    result = studio_service.preview_run(
        template, current_user, payload.cell_id, get_kernel_manager(), db
    )
    return StudioPreviewRunResponse(**result)


@router.post("/templates/{template_id}/preview/interrupt")
def interrupt_preview(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    get_kernel_manager().interrupt(
        studio_service.preview_session_key(template.id, current_user.id)
    )
    return {"status": "interrupted"}


@router.post("/templates/{template_id}/preview/reset")
def reset_preview(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(studio_user),
):
    template = studio_service.get_managed_template(db, template_id, current_user)
    get_kernel_manager().destroy(
        studio_service.preview_session_key(template.id, current_user.id)
    )
    return {"status": "reset"}
