from sqlalchemy.orm import Session

from app.models.bot import Bot


class BotRepository:

    @staticmethod
    def get_all(db: Session):
        return db.query(Bot).all()

    @staticmethod
    def get_by_id(db: Session, bot_id: int):
        return db.query(Bot).filter(Bot.id == bot_id).first()

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
        