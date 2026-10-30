"""Versão do worker (aba Works em Configurações), out/2026.

- Guarda o link do repositório do worker e descobre o commit publicado na ``main`` (``git ls-remote``,
  com o token do ambiente de Git que cobre o link).
- Mostra, por máquina, o commit em que o worker está rodando (informado no heartbeat).
- Pedido de atualização: marca a máquina; o worker, no heartbeat, recebe ``update_requested`` e, ocioso, sai.
  O launcher da máquina baixa o código novo (git fetch + reset) e abre de novo. O pedido some quando o
  worker volta informando outro commit.
"""
import os
import re
import subprocess
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.models.runner import Runner
from app.models.system_setting import SystemSetting
from app.services.git_environment_service import GitEnvironmentService, url_has_credentials
from app.services.git_repo_service import mask_url_credentials

KEY_REPO_URL = "worker_repo_url"
KEY_LATEST_COMMIT = "worker_latest_commit"
KEY_LATEST_CHECKED_AT = "worker_latest_checked_at"
KEY_LATEST_ERROR = "worker_latest_error"

BRANCH = "main"
LS_REMOTE_TIMEOUT_SECONDS = 20
# Pedido sem resposta depois disso aparece como "sem resposta" no painel.
UPDATE_REQUEST_STALE_SECONDS = 30 * 60

_SHA = re.compile(r"^[0-9a-f]{7,40}$")


def commit_matches(runner_commit: str | None, latest: str | None) -> bool:
    """A máquina informa o commit curto (7+ caracteres); o publicado vem inteiro."""
    a = (runner_commit or "").strip().lower()
    b = (latest or "").strip().lower()
    return bool(a and b and _SHA.match(a) and b.startswith(a))


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def update_request_id(requested_at: datetime | None) -> str | None:
    """Código do pedido de atualização: o worker devolve em ``update_ack`` ao reiniciar por causa dele."""
    requested = _aware(requested_at)
    return requested.astimezone(UTC).strftime("%Y%m%dT%H%M%S%f") if requested else None


class WorkerReleaseService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ configurações
    def _get(self, key: str) -> str | None:
        row = self.db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        return row.value if row else None

    def _set(self, key: str, value: str | None) -> None:
        row = self.db.scalar(select(SystemSetting).where(SystemSetting.key == key))
        if row is None:
            self.db.add(SystemSetting(key=key, value=value))
        else:
            row.value = value

    def set_repo_url(self, url: str | None) -> None:
        clean = (url or "").strip()
        if clean and not re.match(r"^https?://", clean, re.IGNORECASE):
            raise ValidationException("Informe o link do repositório começando com http:// ou https://.")
        if url_has_credentials(clean):
            raise ValidationException(
                "Não coloque o token dentro do link. Cadastre o token em Configurações > Ambientes."
            )
        self._set(KEY_REPO_URL, clean or None)
        # Link novo: o commit visto antes não vale mais.
        self._set(KEY_LATEST_COMMIT, None)
        self._set(KEY_LATEST_CHECKED_AT, None)
        self._set(KEY_LATEST_ERROR, None)
        self.db.commit()

    # ------------------------------------------------------------------ commit publicado
    def check_latest(self) -> dict:
        url = (self._get(KEY_REPO_URL) or "").strip()
        if not url:
            raise ValidationException("Informe o link do repositório do worker antes de verificar.")

        resolved = GitEnvironmentService(self.db).resolve_url(url) or url
        commit, error = self._ls_remote(resolved)

        self._set(KEY_LATEST_CHECKED_AT, datetime.now(UTC).isoformat())
        if commit:
            self._set(KEY_LATEST_COMMIT, commit)
            self._set(KEY_LATEST_ERROR, None)
        else:
            self._set(KEY_LATEST_ERROR, error)
        self.db.commit()
        return self.overview()

    @staticmethod
    def _ls_remote(url: str) -> tuple[str | None, str | None]:
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo", "LC_ALL": "C"}
        try:
            result = subprocess.run(
                ["git", "ls-remote", url, f"refs/heads/{BRANCH}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=LS_REMOTE_TIMEOUT_SECONDS,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return None, f"O Git não respondeu em {LS_REMOTE_TIMEOUT_SECONDS}s."
        except FileNotFoundError:
            return None, "O Git não está instalado no servidor da API."

        if result.returncode != 0:
            detail = mask_url_credentials((result.stderr or result.stdout or "").strip())
            return None, detail[:300] or "Não foi possível consultar o repositório."

        first = (result.stdout or "").strip().split("\n", 1)[0].split()
        if not first or not _SHA.match(first[0].lower()):
            return None, f"A branch {BRANCH} não foi encontrada nesse repositório."
        return first[0].lower(), None

    # ------------------------------------------------------------------ visão geral
    def overview(self) -> dict:
        latest = self._get(KEY_LATEST_COMMIT)
        now = datetime.now(UTC)
        runners = self.db.scalars(
            select(Runner).where(Runner.deleted_at.is_(None)).order_by(Runner.name.asc())
        ).all()

        items = []
        for r in runners:
            requested = _aware(r.worker_update_requested_at)
            items.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "label": r.label,
                    "status": r.status,
                    "enabled": r.enabled,
                    "last_heartbeat": r.last_heartbeat,
                    "worker_commit": r.worker_commit,
                    "worker_version": r.worker_version,
                    "up_to_date": commit_matches(r.worker_commit, latest) if latest and r.worker_commit else None,
                    "update_requested_at": requested,
                    "update_request_stale": bool(
                        requested and (now - requested).total_seconds() > UPDATE_REQUEST_STALE_SECONDS
                    ),
                }
            )

        return {
            "repo_url": self._get(KEY_REPO_URL),
            "branch": BRANCH,
            "latest_commit": latest,
            "latest_checked_at": self._get(KEY_LATEST_CHECKED_AT),
            "latest_error": self._get(KEY_LATEST_ERROR),
            "runners": items,
        }

    # ------------------------------------------------------------------ pedido de atualização
    def request_update(self, runner_ids: list[int] | None) -> int:
        """Marca o pedido. ``runner_ids`` vazio/None = todas as máquinas ativas."""
        stmt = select(Runner).where(Runner.deleted_at.is_(None))
        if runner_ids:
            stmt = stmt.where(Runner.id.in_(runner_ids))
        else:
            stmt = stmt.where(Runner.enabled == True)  # noqa: E712
        runners = list(self.db.scalars(stmt).all())
        now = datetime.now(UTC)
        for r in runners:
            r.worker_update_requested_at = now
        self.db.commit()
        return len(runners)

    def cancel_update(self, runner_id: int) -> None:
        runner = self.db.get(Runner, runner_id)
        if runner is not None:
            runner.worker_update_requested_at = None
            self.db.commit()
