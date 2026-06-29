from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.dependencies import get_current_user
from app.models import User
from app.schemas import JupyterEntryResponse, NotebookCopyResponse, NotebookTemplateRead, PaginatedResponse

router = APIRouter(prefix="/jupyter", tags=["jupyter"])


@router.get("/entry", response_model=JupyterEntryResponse)
def jupyter_entry(
    settings: Settings = Depends(get_settings),
    _: User = Depends(get_current_user),
):
    return JupyterEntryResponse(iframe_url=settings.jupyter_base_url)


@router.get("/templates", response_model=PaginatedResponse)
def jupyter_templates(_: User = Depends(get_current_user)):
    templates = [
        NotebookTemplateRead(
            id="intro-ml",
            name="intro-ml.ipynb",
            path="templates/intro-ml.ipynb",
        ),
        NotebookTemplateRead(
            id="deep-learning-basics",
            name="deep-learning-basics.ipynb",
            path="templates/deep-learning-basics.ipynb",
        ),
    ]
    return PaginatedResponse(items=templates, page=1, page_size=len(templates), total=len(templates))


@router.post("/templates/{template_id}/copy", response_model=NotebookCopyResponse)
def copy_template(template_id: str, _: User = Depends(get_current_user)):
    return NotebookCopyResponse(template_id=template_id, target_path=f"workspaces/current/{template_id}.ipynb")
