from datetime import datetime

from pydantic import EmailStr, Field

from app.schemas.common import OrkaBaseSchema


class UserBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=150, description="Nome do usuário.")
    login: str = Field(..., min_length=3, max_length=80, description="Login único do usuário.")
    email: EmailStr = Field(..., description="E-mail do usuário.")
    active: bool = Field(default=True, description="Indica se o usuário está ativo.")
    role: str = Field(..., min_length=1, max_length=50, description="Papel do usuário no sistema.")


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
    password: str | None = Field(default=None, min_length=6, max_length=128)


class UserRead(OrkaBaseSchema):
    id: int
    name: str
    login: str
    email: EmailStr
    active: bool
    role: str
    created_at: datetime
    updated_at: datetime | None = None


class UserListItem(OrkaBaseSchema):
    id: int
    name: str
    login: str
    email: EmailStr
    active: bool
    role: str
    