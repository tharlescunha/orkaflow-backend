from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models.bot import Bot
from app.models.bot_version import BotVersion


class BotRepository:
    @staticmethod
    def list_paginated(
        db: Session,
        *,
        skip: int = 0,
        limit: int = 10,
        search: str | None = None,
        repository_id: int | None = None,
        active: bool | None = None,
    ):
        query = db.query(Bot).options(joinedload(Bot.repository))

        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Bot.name.ilike(term),
                    Bot.description.ilike(term),
                )
            )

        if repository_id is not None:
            query = query.filter(Bot.repository_id == repository_id)

        if active is not None:
            query = query.filter(Bot.active == active)

        total = query.count()

        items = (
            query.order_by(Bot.created_at.desc(), Bot.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

        return items, total

    @staticmethod
    def get_by_id(db: Session, bot_id: int):
        return (
            db.query(Bot)
            .options(joinedload(Bot.repository))
            .filter(Bot.id == bot_id)
            .first()
        )

    @staticmethod
    def get_latest_versions_map(db: Session, bot_ids: list[int]) -> dict[int, str]:
        if not bot_ids:
            return {}

        rows = (
            db.query(BotVersion.bot_id, BotVersion.version)
            .filter(BotVersion.bot_id.in_(bot_ids))
            .order_by(
                BotVersion.bot_id.asc(),
                BotVersion.created_at.desc(),
                BotVersion.id.desc(),
            )
            .all()
        )

        versions: dict[int, str] = {}

        for row in rows:
            if row.bot_id not in versions:
                versions[row.bot_id] = row.version

        return versions

    @staticmethod
    def has_versions(db: Session, bot_id: int) -> bool:
        return (
            db.query(BotVersion.id)
            .filter(BotVersion.bot_id == bot_id)
            .first()
            is not None
        )

    @staticmethod
    def create(db: Session, data: dict):
        bot = Bot(**data)
        db.add(bot)
        db.commit()
        db.refresh(bot)
        return bot

    @staticmethod
    def update(db: Session, bot: Bot, data: dict):
        for key, value in data.items():
            setattr(bot, key, value)

        db.commit()
        db.refresh(bot)
        return bot

    @staticmethod
    def delete(db: Session, bot: Bot):
        db.delete(bot)
        db.commit()
        