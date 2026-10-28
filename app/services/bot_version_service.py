# annotations adiadas: o método list() da classe esconderia o tipo list nas anotações.
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.user import User
from app.repositories.bot_version_repository import BotVersionRepository
from app.services.git_environment_service import GitEnvironmentService
from app.services.git_repo_service import GitCommit, GitRepoService


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_URL_USERINFO_RE = re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]+@")


def _strip_credentials(url: str | None) -> str:
    return _URL_USERINFO_RE.sub(r"\1", url or "")


def _commit_read(commit: GitCommit) -> dict:
    return {
        "hash": commit.hash,
        "short": commit.short,
        "author": commit.author,
        "committed_at": commit.committed_at,
        "message": commit.message,
    }


def _build_changelog(commits: list[GitCommit]) -> str:
    return "\n".join(
        f"- {c.message} ({c.short}, {c.author}, {c.committed_at.strftime('%d/%m/%Y %H:%M')})"
        for c in commits
    )


class BotVersionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BotVersionRepository

    def _annotate(self, versions: list[BotVersion]) -> list[BotVersion]:
        """Marca em cada versão se é a usada hoje (in_use) e se foi fixada por Release (pinned).

        Mesma regra de TaskRepository.get_latest_bot_version_for_bot (fixada > ativa mais nova >
        mais nova), mas em 2 consultas para todos os bots: uma por bot deixava a lista lenta
        (100+ consultas; estourava o tempo no Azure).
        """
        bot_ids = {v.bot_id for v in versions}
        if not bot_ids:
            return versions

        pinned: dict[int, int | None] = dict(
            self.db.query(Bot.id, Bot.pinned_version_id).filter(Bot.id.in_(bot_ids)).all()
        )
        ids_by_bot: dict[int, list[tuple[int, bool]]] = {}
        for version_id, bot_id, is_active in (
            self.db.query(BotVersion.id, BotVersion.bot_id, BotVersion.is_active)
            .filter(BotVersion.bot_id.in_(bot_ids))
            .all()
        ):
            ids_by_bot.setdefault(bot_id, []).append((version_id, bool(is_active)))

        in_use: dict[int, int | None] = {}
        for bot_id, rows in ids_by_bot.items():
            all_ids = {version_id for version_id, _ in rows}
            active_ids = [version_id for version_id, active in rows if active]
            fixed = pinned.get(bot_id)
            if fixed in all_ids:
                in_use[bot_id] = fixed
            elif active_ids:
                in_use[bot_id] = max(active_ids)
            else:
                in_use[bot_id] = max(all_ids)

        for version in versions:
            version.in_use = in_use.get(version.bot_id) == version.id
            version.pinned = pinned.get(version.bot_id) == version.id
        return versions

    def list(self):
        return self._annotate(self.repo.get_all(self.db))

    def get(self, bot_version_id: int):
        bot_version = self.repo.get_by_id(self.db, bot_version_id)
        if not bot_version:
            raise NotFoundException("Versão do bot não encontrada.")
        return self._annotate([bot_version])[0]

    def create(self, data: dict):
        bot = self.db.query(Bot).filter(Bot.id == data["bot_id"]).first()
        if not bot:
            raise NotFoundException("Bot não encontrado.")

        if not bot.active:
            raise ConflictException("Não é permitido criar versão para bot inativo.")

        existing = self.repo.get_by_bot_and_version(
            self.db,
            bot_id=data["bot_id"],
            version=data["version"],
        )
        if existing:
            raise ConflictException("Já existe uma versão com esse número para esse bot.")

        commit_hash = (data.get("commit_hash") or "").strip()
        if commit_hash:
            same_commit = self._find_by_commit(data["bot_id"], commit_hash)
            if same_commit:
                raise ConflictException(
                    f"Esse commit já está na versão {same_commit.version}. "
                    "Use Release nela para voltar a usá-la."
                )

        if not data.get("created_by"):
            data["created_by"] = 1

        user = self.db.query(User).filter(User.id == data["created_by"]).first()
        if not user:
            raise NotFoundException("Usuário criador não encontrado.")

        created = self.repo.create(self.db, data)

        # Versão nova é a intenção do usuário: solta o Release fixado e passa a usar a nova.
        if bot.pinned_version_id is not None:
            bot.pinned_version_id = None
            self.db.commit()

        return self._annotate([created])[0]

    def _find_by_commit(self, bot_id: int, commit_hash: str) -> BotVersion | None:
        commit_hash = commit_hash.strip().lower()
        for version in self.db.query(BotVersion).filter(
            BotVersion.bot_id == bot_id, BotVersion.commit_hash.is_not(None)
        ):
            stored = (version.commit_hash or "").strip().lower()
            if len(stored) >= 7 and (stored.startswith(commit_hash) or commit_hash.startswith(stored)):
                return version
        return None

    def release(self, bot_version_id: int) -> BotVersion:
        """Passa a executar esta versão. Na mais nova, volta a seguir sempre a mais nova."""
        version = self.get(bot_version_id)
        bot = self.db.get(Bot, version.bot_id)
        if not bot:
            raise NotFoundException("Bot não encontrado.")

        newest = (
            self.db.query(BotVersion)
            .filter(BotVersion.bot_id == bot.id)
            .order_by(BotVersion.id.desc())
            .first()
        )

        version.is_active = True
        bot.pinned_version_id = None if newest and newest.id == version.id else version.id
        self.db.commit()
        self.db.refresh(version)
        return self._annotate([version])[0]

    def git_preview(self, bot_id: int) -> dict:
        """Lê o Git do bot e monta a nova versão sugerida (nada é gravado)."""
        bot = self.db.get(Bot, bot_id)
        if not bot:
            raise NotFoundException("Bot não encontrado.")

        versions = (
            self.db.query(BotVersion)
            .filter(BotVersion.bot_id == bot_id)
            .order_by(BotVersion.id.desc())
            .all()
        )
        last = versions[0] if versions else None
        last_with_commit = next((v for v in versions if v.commit_hash), None)

        clone_url = GitEnvironmentService(self.db).resolve_url(bot.source_url)
        snapshot = GitRepoService(bot.id, clone_url).snapshot(
            branch=last_with_commit.branch if last_with_commit else None,
            since_commit=last_with_commit.commit_hash if last_with_commit else None,
        )
        head = snapshot.head
        existing = self._find_by_commit(bot_id, head.hash)

        if existing and last_with_commit and existing.id == last_with_commit.id:
            status = "sincronizado"
            message = f"O bot já está sincronizado com o Git (versão {existing.version}, commit {head.short})."
        elif existing:
            status = "ja_registrado"
            message = (
                f"O último commit do Git ({head.short}) já está na versão {existing.version}. "
                "Use Release nela para voltar a usá-la."
            )
        else:
            status = "nova_versao"
            message = (
                f"O Git está à frente: commit {head.short} de {head.author}."
                if last_with_commit
                else f"Primeira versão a partir do Git: commit {head.short} de {head.author}."
            )

        return {
            "bot_id": bot.id,
            "bot_name": bot.name,
            "status": status,
            "message": message,
            "branch": snapshot.branch,
            "repository": _strip_credentials(bot.source_url),
            "head": _commit_read(head),
            "commits": [_commit_read(c) for c in snapshot.commits],
            "suggested_version": self._suggest_version(versions, snapshot.tags),
            "changelog": _build_changelog(snapshot.commits),
            "last_version": last.version if last else None,
            "last_commit": last_with_commit.commit_hash if last_with_commit else None,
            "existing_version_id": existing.id if existing else None,
            "existing_version": existing.version if existing else None,
        }

    @staticmethod
    def _suggest_version(versions: list[BotVersion], tags: list[str]) -> str:
        taken = {v.version for v in versions}
        for tag in tags:
            candidate = tag.strip().lstrip("vV")
            if SEMVER_RE.match(candidate) and candidate not in taken:
                return candidate

        best: tuple[int, int, int] | None = None
        for v in versions:
            m = SEMVER_RE.match(v.version or "")
            if m:
                key = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                best = key if best is None or key > best else best

        if best is None:
            return "1.0.0"
        return f"{best[0]}.{best[1]}.{best[2] + 1}"

    def update(self, bot_version_id: int, data: dict):
        bot_version = self.get(bot_version_id)

        if data.get("created_by"):
            user = self.db.query(User).filter(User.id == data["created_by"]).first()
            if not user:
                raise NotFoundException("Usuário criador não encontrado.")

        new_version = data.get("version")
        if new_version and new_version != bot_version.version:
            existing = self.repo.get_by_bot_and_version(
                self.db,
                bot_id=bot_version.bot_id,
                version=new_version,
            )
            if existing:
                raise ConflictException("Já existe uma versão com esse número para esse bot.")

        return self._annotate([self.repo.update(self.db, bot_version, data)])[0]

    def delete(self, bot_version_id: int):
        bot_version = self.get(bot_version_id)
        self.repo.delete(self.db, bot_version)

    def auto_create(self, bot_id: int, commit_hash: str, branch: str | None = None) -> BotVersion:
        """Cria automaticamente uma nova bot_version com semver auto-incrementado."""
        bot = self.db.query(Bot).filter(Bot.id == bot_id).first()
        if not bot:
            raise NotFoundException("Bot não encontrado.")
        if not bot.active:
            raise ConflictException("Não é permitido criar versão para bot inativo.")

        existing_for_commit = (
            self.db.query(BotVersion)
            .filter(BotVersion.bot_id == bot_id, BotVersion.commit_hash == commit_hash)
            .first()
        )
        if existing_for_commit:
            return existing_for_commit

        all_versions = (
            self.db.query(BotVersion)
            .filter(BotVersion.bot_id == bot_id)
            .all()
        )

        major, minor, patch = 1, 0, 0
        for v in all_versions:
            m = SEMVER_RE.match(v.version or "")
            if m:
                ma, mi, pa = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if (ma, mi, pa) >= (major, minor, patch):
                    major, minor, patch = ma, mi, pa + 1

        next_version = f"{major}.{minor}.{patch}"

        data = {
            "bot_id": bot_id,
            "version": next_version,
            "storage_type": "git",
            "commit_hash": commit_hash,
            "branch": branch or "main",
            "is_active": True,
            "created_by": 1,
        }
        return self.repo.create(self.db, data)
        