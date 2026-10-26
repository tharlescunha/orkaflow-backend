from datetime import datetime

from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class ApiTokenCreate(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=120)
    # None = sem validade. O padrão da tela é 365 dias.
    expires_in_days: int | None = Field(default=365, ge=1, le=3650)


class ApiTokenRead(OrkaBaseSchema):
    id: int
    name: str
    token_prefix: str
    status: str  # ativo | revogado | expirado
    created_at: datetime
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiTokenCreated(ApiTokenRead):
    # Valor completo: aparece só nesta resposta.
    token: str
