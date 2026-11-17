from pydantic import Field

from app.schemas.common import OrkaBaseSchema


class AccessReleaseCreate(OrkaBaseSchema):
    login: str = Field(..., min_length=1, max_length=80, description="Usuário liberado (ex.: o login do aprovador no SAP).")
    system: str | None = Field(default=None, max_length=60, description="Sistema do usuário (ex.: SAP). Só informativo.")
    note: str | None = Field(default=None, max_length=300)


class AccessReleaseRead(OrkaBaseSchema):
    login: str
    system: str | None = None
    note: str | None = None
    # Horário UTC no formato 2026-11-17T14:10:00Z: é o que o robô recebe em LIBERACOES_DE_ACESSO.
    released_at: str
    released_by_id: int | None = None
    released_by_name: str | None = None
    # Ainda entregue aos robôs (últimas 48 h).
    active: bool = True
