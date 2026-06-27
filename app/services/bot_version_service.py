import re

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.user import User
from app.repositories.bot_version_repository import BotVersionRepository


SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class BotVersionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BotVersionRepository

    def list(self):
        return self.repo.get_all(self.db)

    def get(self, bot_version_id: int):
        bot_version = self.repo.get_by_id(self.db, bot_version_id)
        if not bot_version:
            raise NotFoundException("Versão do bot não encontrada.")
        return bot_version

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

        if not data.get("created_by"):
            data["created_by"] = 1

        user = self.db.query(User).filter(User.id == data["created_by"]).first()
        if not user:
            raise NotFoundException("Usuário criador não encontrado.")

        return self.repo.create(self.db, data)

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

        return self.repo.update(self.db, bot_version, data)

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
        