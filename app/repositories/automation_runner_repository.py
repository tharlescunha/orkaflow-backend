from sqlalchemy.orm import Session, joinedload

from app.models.automation_runner import AutomationRunner


class AutomationRunnerRepository:
    @staticmethod
    def list_by_automation(db: Session, automation_id: int):
        return (
            db.query(AutomationRunner)
            .options(joinedload(AutomationRunner.runner))
            .filter(AutomationRunner.automation_id == automation_id)
            .order_by(AutomationRunner.id.asc())
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, link_id: int):
        return (
            db.query(AutomationRunner)
            .options(joinedload(AutomationRunner.runner))
            .filter(AutomationRunner.id == link_id)
            .first()
        )

    @staticmethod
    def get_by_automation_and_runner(db: Session, automation_id: int, runner_id: int):
        return (
            db.query(AutomationRunner)
            .filter(
                AutomationRunner.automation_id == automation_id,
                AutomationRunner.runner_id == runner_id,
            )
            .first()
        )

    @staticmethod
    def create(db: Session, data: dict):
        link = AutomationRunner(**data)
        db.add(link)
        db.commit()
        db.refresh(link)
        return link

    @staticmethod
    def delete(db: Session, link: AutomationRunner):
        db.delete(link)
        db.commit()
        