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


class MicrosoftLoginRequest(OrkaBaseSchema):
    # O id_token que a Microsoft devolveu ao navegador e o nonce que o navegador gerou para este login.
    id_token: str = Field(..., min_length=20, max_length=8000)
    nonce: str = Field(..., min_length=8, max_length=200)


class MicrosoftConfigRead(OrkaBaseSchema):
    enabled: bool
    tenant_id: str | None = None
    client_id: str | None = None


class AuthConfigRead(OrkaBaseSchema):
    microsoft: MicrosoftConfigRead


class MeResponse(OrkaBaseSchema):
    id: int
    name: str
    login: str
    email: str
    role: str
    active: bool
    