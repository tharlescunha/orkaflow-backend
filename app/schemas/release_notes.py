from app.schemas.common import OrkaBaseSchema


class ReleaseCommitRead(OrkaBaseSchema):
    repo: str  # backend | frontend | worker
    hash: str


class ReleaseFileRead(OrkaBaseSchema):
    status: str  # A (novo) | M (alterado) | D (removido) | R (renomeado)
    repo: str
    path: str


class ReleaseItemRead(OrkaBaseSchema):
    version: str
    type: str  # geral | melhoria | correcao
    type_label: str  # Geral | Melhoria | Correção
    released_at: str  # ISO com fuso de Brasília, ex.: 2026-11-17T14:20:00-03:00
    title: str
    requester: str | None = None
    commits: list[ReleaseCommitRead] = []
    problem: str
    solution: str
    files: list[ReleaseFileRead] = []


class ReleaseCountsRead(OrkaBaseSchema):
    geral: int = 0
    melhoria: int = 0
    correcao: int = 0


class ReleaseNotesRead(OrkaBaseSchema):
    total: int
    current_version: str | None = None
    last_release_at: str | None = None
    counts: ReleaseCountsRead
    items: list[ReleaseItemRead] = []


class ReleaseVersionRead(OrkaBaseSchema):
    version: str | None = None
    released_at: str | None = None
