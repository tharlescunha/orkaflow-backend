from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.runner import Runner
from app.repositories.automation_runner_repository import AutomationRunnerRepository
from app.services.automation_service import AutomationService


class AutomationRunnerService:
    @staticmethod
    def list_by_automation(db: Session, automation_id: int):
        AutomationService.get(db, automation_id)
        return AutomationRunnerRepository.list_by_automation(db, automation_id)

    @staticmethod
    def link_runner(db: Session, automation_id: int, runner_id: int):
        AutomationService.get(db, automation_id)

        runner = db.query(Runner).filter(Runner.id == runner_id).first()
        if not runner:
            raise NotFoundException("Runner não encontrado")

        existing = AutomationRunnerRepository.get_by_automation_and_runner(
            db, automation_id, runner_id
        )
        if existing:
            raise ConflictException("Esse runner já está vinculado à automação")

        return AutomationRunnerRepository.create(
            db,
            {
                "automation_id": automation_id,
                "runner_id": runner_id,
            },
        )

    @staticmethod
    def unlink_runner(db: Session, automation_id: int, link_id: int):
        AutomationService.get(db, automation_id)

        link = AutomationRunnerRepository.get_by_id(db, link_id)
        if not link or link.automation_id != automation_id:
            raise NotFoundException("Vínculo de runner não encontrado para essa automação")

        AutomationRunnerRepository.delete(db, link)
        