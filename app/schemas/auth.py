from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class LoginRequest(OrkaBaseSchema):
    login: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class RefreshTokenRequest(OrkaBaseSchema):
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(OrkaBaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeResponse(OrkaBaseSchema):
    id: int
    name: str
    login: str
    email: str
    role: str
    active: bool
    