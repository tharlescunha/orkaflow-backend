"""Leitura do repositório Git de um bot (último commit, mensagens, tags) para criar versões.

Usa o git da máquina do backend com um cache "bare" e leve por bot
(``runtime/git-cache/bot_<id>.git``, clone com ``--filter=blob:none``: só histórico,
sem arquivos). O token fica dentro da URL do bot; ele nunca aparece em erro nem em log.
"""
import logging
import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.core.exceptions import ValidationException
from app.services.system_heartbeat_service import heartbeat_dir

logger = logging.getLogger(__name__)

GIT_TIMEOUT_SECONDS = 120
MAX_CHANGELOG_COMMITS = 50
FIRST_SYNC_COMMITS = 10

_URL_CREDENTIALS_RE = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]+@")
_FIELD_SEP = "\x1f"
_LOG_FORMAT = _FIELD_SEP.join(["%H", "%an", "%aI", "%s"])

_locks: dict[int, threading.Lock] = {}
_locks_guard = threading.Lock()


def mask_url_credentials(text: str | None) -> str:
    if not text:
        return text or ""
    return _URL_CREDENTIALS_RE.sub(r"\1***@", text)


@dataclass
class GitCommit:
    hash: str
    author: str
    committed_at: datetime
    message: str

    @property
    def short(self) -> str:
        return self.hash[:7]


@dataclass
class GitSnapshot:
    branch: str
    head: GitCommit
    commits: list[GitCommit] = field(default_factory=list)  # do mais novo ao mais antigo
    tags: list[str] = field(default_factory=list)  # tags que apontam para o head
    base_found: bool = False  # o commit da versão anterior existe no histórico


class GitRepoError(ValidationException):
    pass


def _bot_lock(bot_id: int) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(bot_id, threading.Lock())


def cache_root() -> Path:
    return heartbeat_dir().parent / "git-cache"


class GitRepoService:
    def __init__(self, bot_id: int, source_url: str | None):
        if not source_url or not source_url.strip():
            raise GitRepoError("O bot não tem URL do repositório cadastrada.")
        if shutil.which("git") is None:
            raise GitRepoError("Git não está instalado no servidor do backend.")
        self.bot_id = bot_id
        self.url = source_url.strip()
        self.repo_dir = cache_root() / f"bot_{bot_id}.git"

    # ------------------------------------------------------------------ git
    def _git(self, *args: str, cwd: Path | None = None, check: bool = True) -> str:
        # Nunca pedir senha no terminal do serviço (travaria a requisição).
        full_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "echo", "LC_ALL": "C"}
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=GIT_TIMEOUT_SECONDS,
                env=full_env,
            )
        except subprocess.TimeoutExpired as exc:
            raise GitRepoError(f"O Git não respondeu em {GIT_TIMEOUT_SECONDS}s.") from exc

        if check and result.returncode != 0:
            detail = mask_url_credentials((result.stderr or result.stdout or "").strip())
            raise GitRepoError(_friendly_error(detail))
        return result.stdout

    def _ensure_cache(self) -> None:
        self.repo_dir.parent.mkdir(parents=True, exist_ok=True)

        if (self.repo_dir / "HEAD").exists():
            # URL pode ter mudado (token novo): sempre atualiza o origin antes de buscar.
            self._git("remote", "set-url", "origin", self.url, cwd=self.repo_dir)
            self._git(
                "fetch", "--prune", "--tags", "origin",
                "+refs/heads/*:refs/heads/*",
                cwd=self.repo_dir,
            )
            return

        try:
            self._git("clone", "--bare", "--filter=blob:none", "--quiet", self.url, str(self.repo_dir))
        except GitRepoError as exc:
            shutil.rmtree(self.repo_dir, ignore_errors=True)
            if "filter" not in str(exc.detail).lower() and "partial" not in str(exc.detail).lower():
                raise
            # Servidor sem "partial clone": clona o histórico completo (ainda sem arquivos de trabalho).
            self._git("clone", "--bare", "--quiet", self.url, str(self.repo_dir))

    def _default_branch(self) -> str:
        # No clone "bare" o HEAD local aponta para a branch padrão do remoto (sem ir à rede).
        out = self._git("symbolic-ref", "--short", "HEAD", cwd=self.repo_dir, check=False).strip()
        return out or "main"

    def _commit_exists(self, commit: str) -> bool:
        out = self._git("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}",
                        cwd=self.repo_dir, check=False)
        return bool(out.strip())

    def _log(self, *args: str, check: bool = True) -> list[tuple[GitCommit, str]]:
        """Commits e as refs de cada um (%D traz as tags: "tag: v1.2.0")."""
        out = self._git("log", f"--format={_LOG_FORMAT}{_FIELD_SEP}%D", *args,
                        cwd=self.repo_dir, check=check)
        commits = []
        for line in out.splitlines():
            parts = line.split(_FIELD_SEP)
            if len(parts) != 5:
                continue
            commit = GitCommit(
                hash=parts[0],
                author=parts[1],
                committed_at=datetime.fromisoformat(parts[2]),
                message=parts[3],
            )
            commits.append((commit, parts[4]))
        return commits

    # --------------------------------------------------------------- público
    def snapshot(self, branch: str | None = None, since_commit: str | None = None) -> GitSnapshot:
        """Atualiza o cache e devolve o último commit da branch e os commits desde `since_commit`."""
        with _bot_lock(self.bot_id):
            self._ensure_cache()

            target = (branch or "").strip() or self._default_branch()
            head = self._log("-1", f"refs/heads/{target}", "--", check=False)
            if not head and branch:
                # Branch da versão anterior sumiu: usa a padrão do repositório.
                target = self._default_branch()
                head = self._log("-1", f"refs/heads/{target}", "--", check=False)
            if not head:
                raise GitRepoError(f"Branch '{target}' sem commits ou inexistente no repositório.")

            ref = f"refs/heads/{target}"
            head_commit, head_refs = head[0]

            base_found = bool(since_commit) and self._commit_exists(since_commit)
            if base_found:
                commits = self._log(f"-{MAX_CHANGELOG_COMMITS}", f"{since_commit}..{ref}", "--")
            else:
                commits = self._log(f"-{FIRST_SYNC_COMMITS}", ref, "--")

            tags = [
                ref_name.strip()[len("tag: "):]
                for ref_name in head_refs.split(",")
                if ref_name.strip().startswith("tag: ")
            ]

            return GitSnapshot(
                branch=target,
                head=head_commit,
                commits=[c for c, _ in commits],
                tags=tags,
                base_found=base_found,
            )


def _friendly_error(detail: str) -> str:
    low = detail.lower()
    if "authentication failed" in low or "could not read username" in low or "403" in low:
        return "O Git recusou o acesso: o token da URL do bot é inválido ou expirou."
    if "not found" in low or "does not exist" in low or "404" in low:
        return "Repositório não encontrado: confira a URL cadastrada no bot."
    if "could not resolve host" in low or "unable to access" in low:
        return f"Não foi possível acessar o repositório: {detail}"
    return f"Falha ao ler o repositório: {detail}"
