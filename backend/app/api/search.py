"""全局搜索 API——角色隔离，仅返回摘要。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas.search import SearchResponse
from app.services.search_service import search_all

router = APIRouter(prefix="/search", tags=["搜索"])


@router.get("", response_model=SearchResponse)
def global_search(
    q: str = Query(..., min_length=1, max_length=80),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return search_all(db, current_user, q.strip())
