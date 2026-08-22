from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.dependencies import get_current_user
from app.errors import api_error
from app.models import User
from app.schemas import JupyterEntryResponse

router = APIRouter(prefix="/jupyter", tags=["jupyter"])


@router.get("/entry", response_model=JupyterEntryResponse)
def jupyter_entry(
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
):
    if not get_settings().jupyter_enabled:
        raise api_error(503, "JUPYTER_DISABLED", "JupyterLab 已关闭，请使用内置 Notebook Player")
    return JupyterEntryResponse(iframe_url=settings.jupyter_base_url)


@router.get("/templates")
def jupyter_templates(_: User = Depends(get_current_user)):
    raise api_error(
        410,
        "JUPYTER_TEMPLATES_RETIRED",
        "Jupyter 模板复制接口已下线，请使用 /api/v1/experiments 的 Notebook 模板流程",
    )


@router.post("/templates/{template_id}/copy")
def copy_template(template_id: str, _: User = Depends(get_current_user)):
    raise api_error(
        410,
        "JUPYTER_TEMPLATES_RETIRED",
        "Jupyter 模板复制接口已下线，请使用 /api/v1/experiments 的 Notebook 模板流程",
    )
