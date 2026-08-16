"""站内通知契约。"""

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationRead(BaseModel):
    id: int
    type: str
    title: str
    content: str = ""
    entity_kind: str | None = None
    entity_id: int | None = None
    route: str | None = None
    priority: str = "normal"
    created_at: datetime
    is_read: bool = False


class NotificationListRead(BaseModel):
    items: list[NotificationRead] = Field(default_factory=list)
    unread_count: int = 0
    total: int = 0
