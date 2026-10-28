from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import OrkaBaseSchema


class GitEnvironmentBase(OrkaBaseSchema):
    name: str = Field(..., min_length=1, max_length=120)
    # Começo do link dos repositórios, ex.: https://dev.azure.com/alzgraos/ ou https://github.com/tharlescunha/
    url_prefix: str = Field(..., min_length=8, max_length=500)
    username: str | None = Field(default=None, max_length=150)
    expires_at: datetime | None = None
    active: bool = True

    @field_validator("url_prefix")
    @classmethod
    def _prefix(cls, value: str):
        value = value.strip()
        if not value.lower().startswith(("http://", "https://")):
            raise ValueError("O prefixo deve começar com http:// ou https://")
        if "@" in value.split("://", 1)[1].split("/", 1)[0]:
            raise ValueError("O prefixo não pode trazer usuário ou token; o token vai no campo próprio.")
        return value


class GitEnvironmentCreate(GitEnvironmentBase):
    token: str = Field(..., min_length=1, max_length=2000)


class GitEnvironmentUpdate(GitEnvironmentBase):
    # Vazio/None mantém o token que já está salvo.
    token: str | None = Field(default=None, max_length=2000)


class GitEnvironmentRead(OrkaBaseSchema):
    id: int
    name: str
    url_prefix: str
    username: str | None = None
    token_hint: str | None = None
    expires_at: datetime | None = None
    # valido | vence_em_breve | vencido
    expiry_status: str
    days_to_expire: int | None = None
    active: bool
    created_at: datetime
    updated_at: datetime | None = None


class GitUrlCheck(OrkaBaseSchema):
    url: str = Field(..., min_length=1, max_length=1000)


class GitUrlCheckResult(OrkaBaseSchema):
    """O que o formulário do bot mostra abaixo do link: de onde vem o token para esse endereço."""

    # link | ambiente | nenhum
    token_source: str
    environment_id: int | None = None
    environment_name: str | None = None
    expiry_status: str | None = None
    days_to_expire: int | None = None
    message: str
