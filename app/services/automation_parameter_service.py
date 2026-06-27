from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.domain.enums import ParameterType
from app.repositories.automation_parameter_repository import AutomationParameterRepository
from app.services.automation_service import AutomationService


class AutomationParameterService:
    @staticmethod
    def list_by_automation(db: Session, automation_id: int):
        AutomationService.get(db, automation_id)
        return AutomationParameterRepository.list_by_automation(db, automation_id)

    @staticmethod
    def create(db: Session, automation_id: int, data: dict):
        AutomationService.get(db, automation_id)

        existing = AutomationParameterRepository.get_by_automation_and_name(
            db,
            automation_id=automation_id,
            name=data["name"],
        )
        if existing:
            raise ConflictException("Já existe um parâmetro com esse nome nessa automação")

        if data["type"] == ParameterType.SELECT and not data.get("allowed_values"):
            raise ValidationException("Parâmetro do tipo SELECT exige allowed_values")

        payload = {
            **data,
            "automation_id": automation_id,
        }
        return AutomationParameterRepository.create(db, payload)

    @staticmethod
    def update(db: Session, automation_id: int, parameter_id: int, data: dict):
        AutomationService.get(db, automation_id)

        parameter = AutomationParameterRepository.get_by_id(db, parameter_id)
        if not parameter or parameter.automation_id != automation_id:
            raise NotFoundException("Parâmetro da automação não encontrado")

        new_name = data.get("name", parameter.name)
        existing = AutomationParameterRepository.get_by_automation_and_name(
            db,
            automation_id=automation_id,
            name=new_name,
        )
        if existing and existing.id != parameter.id:
            raise ConflictException("Já existe um parâmetro com esse nome nessa automação")

        new_type = data.get("type", parameter.type)
        new_allowed_values = data.get("allowed_values", parameter.allowed_values)

        if new_type == ParameterType.SELECT and not new_allowed_values:
            raise ValidationException("Parâmetro do tipo SELECT exige allowed_values")

        return AutomationParameterRepository.update(db, parameter, data)

    @staticmethod
    def delete(db: Session, automation_id: int, parameter_id: int):
        AutomationService.get(db, automation_id)

        parameter = AutomationParameterRepository.get_by_id(db, parameter_id)
        if not parameter or parameter.automation_id != automation_id:
            raise NotFoundException("Parâmetro da automação não encontrado")

        AutomationParameterRepository.delete(db, parameter)
        