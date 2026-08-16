"""用户偏好契约。"""

from pydantic import BaseModel, ConfigDict, Field


class UserPreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    preferences: dict = Field(default_factory=dict)


class UserPreferencesUpdate(BaseModel):
    sidebar_collapsed: bool | None = None
    preferred_page_size: int | None = Field(default=None, ge=10, le=100)
