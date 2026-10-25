from datetime import datetime
import re

from pydantic import Field, field_validator

from app.schemas.common import OrkaBaseSchema


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class BotVersionBase(OrkaBaseSchema):
    bot_id: int
    version: str = Field(..., min_length=1, max_length=50)
    storage_type: str = Field(..., min_length=1, max_length=50)
    commit_hash: str | None = Field(default=None, max_length=80)
    branch: str | None = Field(default=None, max_length=120)
    artifact_path: str | None = Field(default=None, max_length=500)
    changelog: str | None = None
    checksum: str | None = Field(default=None, max_length=255)
    commit_author: str | None = Field(default=None, max_length=150)
    committed_at: datetime | None = None
    created_by: int | None = None
    is_active: bool = True

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str) -> str:
        value = value.strip()
        if not SEMVER_RE.match(value):
            raise ValueError("A versão deve estar no formato 1.0.0.")
        return value


class BotVersionCreate(BotVersionBase):
    pass


class BotVersionUpdate(OrkaBaseSchema):
    version: str | None = Field(default=None, min_length=1, max_length=50)
    storage_type: str | None = Field(default=None, min_length=1, max_length=50)
    artifact_path: str | None = Field(default=None, max_length=500)
    changelog: str | None = None
    checksum: str | None = Field(default=None, max_length=255)
    created_by: int | None = None
    is_active: bool | None = None

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not SEMVER_RE.match(value):
            raise ValueError("A versão deve estar no formato 1.0.0.")
        return value


class BotVersionResponse(OrkaBaseSchema):
    id: int
    bot_id: int
    bot_name: str | None = None
    version: str
    storage_type: str
    commit_hash: str | None = None
    branch: str | None = None
    artifact_path: str | None = None
    changelog: str | None = None
    checksum: str | None = None
    commit_author: str | None = None
    committed_at: datetime | None = None
    created_by: int | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None
    # Versão que o orquestrador usa hoje para esse bot (fixada por Release ou a mais nova).
    in_use: bool = False
    pinned: bool = False


class GitCommitRead(OrkaBaseSchema):
    hash: str
    short: str
    author: str
    committed_at: datetime
    message: str


class BotVersionGitPreview(OrkaBaseSchema):
    """Resultado de "sincronizar com o Git": o que a nova versão teria, sem gravar nada."""

    bot_id: int
    bot_name: str
    # sincronizado: o último commit já é a versão mais nova
    # nova_versao: o Git está à frente (ou o bot ainda não tem versão com commit)
    # ja_registrado: o último commit já existe numa versão mais antiga (use Release nela)
    status: str
    message: str
    branch: str
    repository: str  # URL sem usuário/token
    head: GitCommitRead
    commits: list[GitCommitRead]
    suggested_version: str
    changelog: str
    last_version: str | None = None
    last_commit: str | None = None
    existing_version_id: int | None = None
    existing_version: str | None = None