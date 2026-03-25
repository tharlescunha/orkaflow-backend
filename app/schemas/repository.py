# app\schemas\repository.py

from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class RepositoryBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=100, description="Nome do repositório.")
    description: str | None = Field(
        default=None,
        max_length=500,
        description="Descrição opcional do repositório.",
    )
    active: bool = Field(default=True, description="Indica se o repositório está ativo.")


class RepositoryCreate(RepositoryBase):
    pass


class RepositoryUpdate(OrkaBaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    active: bool | None = None


class RepositoryRead(RepositoryBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None


class RepositoryListItem(OrkaBaseSchema):
    id: int
    name: str
    description: str | None = None
    active: bool
    