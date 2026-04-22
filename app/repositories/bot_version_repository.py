from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.bot_version import BotVersion


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BotVersionRepository:

    @staticmethod
    def get_all(db: Session):
        return (
            db.query(BotVersion)
            .order_by(BotVersion.created_at.desc(), BotVersion.id.desc())
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, bot_version_id: int):
        return db.query(BotVersion).filter(BotVersion.id == bot_version_id).first()

    @staticmethod
    def get_by_bot_and_version(db: Session, bot_id: int, version: str):
        return (
            db.query(BotVersion)
            .filter(BotVersion.bot_id == bot_id, BotVersion.version == version)
            .first()
        )

    @staticmethod
    def create(db: Session, data: dict):
        payload = dict(data)

        payload.setdefault("created_at", utc_now())
        payload.setdefault("updated_at", utc_now())

        bot_version = BotVersion(**payload)
        db.add(bot_version)
        db.commit()
        db.refresh(bot_version)
        return bot_version

    @staticmethod
    def update(db: Session, bot_version: BotVersion, data: dict):
        for key, value in data.items():
            setattr(bot_version, key, value)

        bot_version.updated_at = utc_now()

        db.commit()
        db.refresh(bot_version)
        return bot_version

    @staticmethod
    def delete(db: Session, bot_version: BotVersion):
        db.delete(bot_version)
        db.commit()
        