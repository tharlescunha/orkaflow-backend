from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import OrkaBaseSchema


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
    email: EmailStr = Field(..., description="E-mail do usuário.")
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
    email: EmailStr | None = None
    active: bool | None = None
    role: str | None = Field(default=None, min_length=1, max_length=50)
    profile_id: int | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class UserRead(OrkaBaseSchema):
    id: int
    name: str
    login: str
    email: EmailStr
    active: bool
    role: str
    profile_id: int | None = None
    profile: UserProfileRead | None = None
    created_at: datetime
    updated_at: datetime | None = None


class UserListItem(OrkaBaseSchema):
    id: int
    name: str
    login: str
    email: EmailStr
    active: bool
    role: str
    profile_id: int | None = None
    profile: UserProfileRead | None = None


class UserChangeStatus(OrkaBaseSchema):
    active: bool = Field(..., description="Define se o usuário ficará ativo ou bloqueado.")
    