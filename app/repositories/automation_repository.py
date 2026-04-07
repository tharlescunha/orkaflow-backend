from sqlalchemy.orm import Session, joinedload

from app.models.automation import Automation


class AutomationRepository:
    @staticmethod
    def list(
        db: Session,
        *,
        active: bool | None = None,
        repository_id: int | None = None,
        bot_id: int | None = None,
    ):
        query = (
            db.query(Automation)
            .options(
                joinedload(Automation.bot),
                joinedload(Automation.repository),
            )
        )

        if active is not None:
            query = query.filter(Automation.active == active)

        if repository_id is not None:
            query = query.filter(Automation.repository_id == repository_id)

        if bot_id is not None:
            query = query.filter(Automation.bot_id == bot_id)

        return query.order_by(Automation.name.asc()).all()

    @staticmethod
    def get_by_id(db: Session, automation_id: int):
        return (
            db.query(Automation)
            .options(
                joinedload(Automation.bot),
                joinedload(Automation.repository),
            )
            .filter(Automation.id == automation_id)
            .first()
        )

    @staticmethod
    def get_by_repository_and_name(db: Session, repository_id: int, name: str):
        return (
            db.query(Automation)
            .filter(
                Automation.repository_id == repository_id,
                Automation.name == name,
            )
            .first()
        )

    @staticmethod
    def create(db: Session, data: dict):
        automation = Automation(**data)
        db.add(automation)
        db.commit()
        db.refresh(automation)
        return automation

    @staticmethod
    def update(db: Session, automation: Automation, data: dict):
        for key, value in data.items():
            setattr(automation, key, value)

        db.commit()
        db.refresh(automation)
        return automation
    