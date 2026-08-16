"""全局搜索响应契约。"""

from pydantic import BaseModel, Field


class SearchResultItem(BaseModel):
    id: int
    title: str
    subtitle: str | None = None
    route: str
    meta: str | None = None


class SearchResponse(BaseModel):
    courses: list[SearchResultItem] = Field(default_factory=list)
    assignments: list[SearchResultItem] = Field(default_factory=list)
    exams: list[SearchResultItem] = Field(default_factory=list)
    students: list[SearchResultItem] = Field(default_factory=list)
    submissions: list[SearchResultItem] = Field(default_factory=list)
