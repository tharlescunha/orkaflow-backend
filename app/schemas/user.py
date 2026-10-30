from __future__ import annotations

from datetime import datetime

from typing import Annotated

from pydantic import Field, StringConstraints

from app.schemas.common import OrkaBaseSchema


# E-mail aceito em rede interna: valida só o formato (algo@dominio.ext). O EmailStr
# recusava domínios reservados como "empresa.local", comuns em ambiente corporativo.
EmailAddress = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        max_length=150,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    ),
]


class UserPermissionRead(OrkaBaseSchema):
    id: int
    module: str
    action: str
    description: str | None = None


class UserProfileRead(OrkaBaseSchema):
    id: int
    name: str
    description: str | None = None
    active: bool
    permissions: list[UserPermissionRead] = []


class UserBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=150, description="Nome do usuário.")
    login: str = Field(..., min_length=3, max_length=80, description="Login único do usuário.")
    email: EmailAddress = Field(..., description="E-mail do usuário.")
    active: bool = Field(default=True, description="Indica se o usuário está ativo.")
    role: str = Field(..., min_length=1, max_length=50, description="Role legada do usuário.")
    profile_id: int | None = Field(
        default=None,
        description="ID do perfil vinculado ao usuário.",
    )


class UserCreate(UserBase):
    password: str = Field(
        ...,
        min_length=6,
        max_length=128,
        description="Senha em texto puro apenas na criação. Deve ser convertida em hash no service.",
    )


class UserUpdate(OrkaBaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    login: str | None = Field(default=None, min_length=3, max_length=80)
    email: EmailAddress | None = None
    active: bool | None = None
    role: str | None = Field(default=None, min_length=1, max_length=50)
    profile_id: int | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class UserRead(OrkaBaseSchema):
    id: int
    name: str
    login: str
    email: EmailAddress
    active: bool
    role: str
    profile_id: int | None = None
    profile: UserProfileRead | None = None
    sync_enabled: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class UserListItem(OrkaBaseSchema):
    id: int
    name: str
    login: str
    email: EmailAddress
    active: bool
    role: str
    profile_id: int | None = None
    profile: UserProfileRead | None = None


class UserChangeStatus(OrkaBaseSchema):
    active: bool = Field(..., description="Define se o usuário ficará ativo ou bloqueado.")
    