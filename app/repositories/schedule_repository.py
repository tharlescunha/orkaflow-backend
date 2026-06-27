# app\repositories\schedule_repository.py

from sqlalchemy.orm import Session

from app.models.schedule import Schedule


class ScheduleRepository:
    @staticmethod
    def list(
        db: Session,
        *,
        automation_id: int | None = None,
        active: bool | None = None,
        status: str | None = None,
    ):
        query = db.query(Schedule)

        if automation_id is not None:
            query = query.filter(Schedule.automation_id == automation_id)

        if active is not None:
            query = query.filter(Schedule.active == active)

        if status is not None and hasattr(Schedule, "status"):
            query = query.filter(Schedule.status == status)

        return query.order_by(Schedule.id.desc()).all()

    @staticmethod
    def get_by_id(db: Session, schedule_id: int):
        return db.query(Schedule).filter(Schedule.id == schedule_id).first()

    @staticmethod
    def get_by_automation_and_name(db: Session, automation_id: int, name: str):
        return (
            db.query(Schedule)
            .filter(
                Schedule.automation_id == automation_id,
                Schedule.name == name,
            )
            .first()
        )

    @staticmethod
    def create(db: Session, data: dict):
        schedule = Schedule(**data)
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def update(db: Session, schedule: Schedule, data: dict):
        for key, value in data.items():
            setattr(schedule, key, value)

        db.commit()
        db.refresh(schedule)
        return schedule
    