# app\schemas\common.py

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class OrkaBaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class TimestampSchema(OrkaBaseSchema):
    created_at: datetime
    updated_at: datetime | None = None


class ActiveSchema(OrkaBaseSchema):
    active: bool = True


class EnabledSchema(OrkaBaseSchema):
    enabled: bool = True


class MessageResponse(OrkaBaseSchema):
    message: str = Field(..., description="Mensagem de retorno da operação.")


class PaginatedResponse(OrkaBaseSchema, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
    