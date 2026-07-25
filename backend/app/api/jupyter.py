from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.dependencies import get_current_user
from app.errors import api_error
from app.models import User
from app.schemas import JupyterEntryResponse, JupyterTemplateRead, NotebookCopyResponse, PaginatedResponse

router = APIRouter(prefix="/jupyter", tags=["jupyter"])


@router.get("/entry", response_model=JupyterEntryResponse)
def jupyter_entry(
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
):
    if not get_settings().jupyter_enabled:
        raise api_error(503, "JUPYTER_DISABLED", "JupyterLab 已关闭，请使用内置 Notebook Player")
    return JupyterEntryResponse(iframe_url=settings.jupyter_base_url)


@router.get("/templates", response_model=PaginatedResponse)
def jupyter_templates(_: User = Depends(get_current_user)):
    templates = [
        JupyterTemplateRead(
            id="intro-ml",
            name="intro-ml.ipynb",
            path="templates/intro-ml.ipynb",
        ),
        JupyterTemplateRead(
            id="deep-learning-basics",
            name="deep-learning-basics.ipynb",
            path="templates/deep-learning-basics.ipynb",
        ),
    ]
    return PaginatedResponse(items=templates, page=1, page_size=len(templates), total=len(templates))


@router.post("/templates/{template_id}/copy", response_model=NotebookCopyResponse)
def copy_template(template_id: str, _: User = Depends(get_current_user)):
    return NotebookCopyResponse(template_id=template_id, target_path=f"workspaces/current/{template_id}.ipynb")
