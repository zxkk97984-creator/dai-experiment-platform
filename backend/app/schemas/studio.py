from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


def _non_empty_cell_id(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("cell id must not be empty")
    return value


CellId = Annotated[str, AfterValidator(_non_empty_cell_id)]


class StudioCell(BaseModel):
    """The complete, fixed Studio cell contract."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: CellId
    type: Literal["markdown", "code"]
    source: str = ""
    order: int
    student_editable: bool
    source_hidden: bool

    @model_validator(mode="after")
    def reject_hidden_markdown(self):
        if self.type == "markdown" and self.source_hidden:
            raise ValueError("markdown cells cannot be hidden")
        return self


class StudioTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    lesson_id: int | None = None
    module_id: int | None = None

    @model_validator(mode="after")
    def one_context_at_most(self):
        if self.lesson_id is not None and self.module_id is not None:
            raise ValueError("lesson_id and module_id are mutually exclusive")
        return self


class StudioTemplateMetadataUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class StudioTemplateBindRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_id: int | None = None
    module_id: int | None = None

    @model_validator(mode="after")
    def one_context_at_most(self):
        if self.lesson_id is not None and self.module_id is not None:
            raise ValueError("lesson_id and module_id are mutually exclusive")
        return self


class StudioDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    draft_revision: int
    cells: list[StudioCell]

    @model_validator(mode="after")
    def unique_cell_ids(self):
        ids = [cell.id for cell in self.cells]
        if len(ids) != len(set(ids)):
            raise ValueError("cell ids must be unique")
        return self


class StudioImportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    lesson_id: int | None = None
    module_id: int | None = None

    @model_validator(mode="after")
    def one_context_at_most(self):
        if self.lesson_id is not None and self.module_id is not None:
            raise ValueError("lesson_id and module_id are mutually exclusive")
        return self


class StudioImportExisting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_revision: int


class StudioPreviewRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cell_id: CellId


class StudioPreviewRunResponse(BaseModel):
    outputs: list[dict] = Field(default_factory=list)
    execution_time_ms: int | None = None


class StudioVersionRead(BaseModel):
    id: int
    template_id: int
    version_number: int
    sha256: str
    cells: list[StudioCell]
    cell_order: list[str]
    notebook_metadata: dict
    assets_dir: str | None = None
    published_at: datetime
    published_by_id: int


class StudioTemplateRead(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: str
    current_version_id: int | None = None
    owner_id: int
    draft_cells: list[StudioCell]
    draft_revision: int
    draft_metadata: dict
    draft_assets_dir: str | None = None
    lesson_id: int | None = None
    module_id: int | None = None
    current_version: StudioVersionRead | None = None
