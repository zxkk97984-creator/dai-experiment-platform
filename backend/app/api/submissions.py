"""统一提交中心 API——实验 / 作业 / 考试提交合并列表。"""

from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.dependencies import PaginationParams, get_current_user, get_db, pagination, require_roles
from app.models import User
from app.schemas.unified_submissions import UnifiedSubmissionListRead
from app.services.unified_submission_service import list_unified_submissions

from sqlalchemy.orm import Session

router = APIRouter(prefix="/submissions", tags=["统一提交"])


@router.get("/unified", response_model=UnifiedSubmissionListRead)
def unified_submissions(
    q: str | None = Query(None),
    course_id: int | None = None,
    kind: Literal["all", "experiment", "assignment", "exam"] = "all",
    status: Literal["all", "pending_grading", "graded", "review_required", "failed"] = "all",
    entry_id: int | None = None,
    sort: Literal["submitted_desc", "submitted_asc"] = "submitted_desc",
    pagination: PaginationParams = Depends(pagination),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("teacher", "admin")),
):
    items, total, page, page_size, summary, filter_options = list_unified_submissions(
        db,
        current_user,
        q=q,
        course_id=course_id,
        kind=kind,
        status=status,
        entry_id=entry_id,
        sort=sort,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return UnifiedSubmissionListRead(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        summary=summary,
        filter_options=filter_options,
    )
