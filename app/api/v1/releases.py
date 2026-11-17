from fastapi import APIRouter

from app.schemas.release_notes import ReleaseNotesRead, ReleaseVersionRead
from app.services.release_notes_service import ReleaseNotesService

# Lista completa das atualizações (exige login).
router = APIRouter(prefix="/releases", tags=["Releases"])
# Só a versão atual, sem login: a tela de entrada mostra o selo de versão antes de a pessoa logar.
public_router = APIRouter(prefix="/version", tags=["Releases"])


@router.get("/", response_model=ReleaseNotesRead)
def list_releases():
    """Histórico de atualizações do sistema, lido do ATUALIZACOES.md (do mais novo para o mais antigo)."""
    return ReleaseNotesService().read()


@public_router.get("", response_model=ReleaseVersionRead)
def current_version():
    """Versão atual do Regente e a data da última atualização."""
    return ReleaseNotesService().latest()
