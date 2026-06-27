from sqlalchemy.orm import Session

from app.models.automation_parameter import AutomationParameter


class AutomationParameterRepository:
    @staticmethod
    def list_by_automation(db: Session, automation_id: int):
        return (
            db.query(AutomationParameter)
            .filter(AutomationParameter.automation_id == automation_id)
            .order_by(AutomationParameter.order_index.asc(), AutomationParameter.id.asc())
            .all()
        )

    @staticmethod
    def get_by_id(db: Session, parameter_id: int):
        return (
            db.query(AutomationParameter)
            .filter(AutomationParameter.id == parameter_id)
            .first()
        )

    @staticmethod
    def get_by_automation_and_name(db: Session, automation_id: int, name: str):
        return (
            db.query(AutomationParameter)
            .filter(
                AutomationParameter.automation_id == automation_id,
                AutomationParameter.name == name,
            )
            .first()
        )

    @staticmethod
    def create(db: Session, data: dict):
        parameter = AutomationParameter(**data)
        db.add(parameter)
        db.commit()
        db.refresh(parameter)
        return parameter

    @staticmethod
    def update(db: Session, parameter: AutomationParameter, data: dict):
        for key, value in data.items():
            setattr(parameter, key, value)

        db.commit()
        db.refresh(parameter)
        return parameter

    @staticmethod
    def delete(db: Session, parameter: AutomationParameter):
        db.delete(parameter)
        db.commit()
        