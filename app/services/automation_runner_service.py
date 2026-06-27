from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException
from app.models.runner import Runner
from app.repositories.automation_runner_repository import AutomationRunnerRepository
from app.services.automation_service import AutomationService


class AutomationRunnerService:
    @staticmethod
    def _serialize(link):
        runner = getattr(link, "runner", None)

        status = None
        if runner is not None:
            status = runner.status.value if hasattr(runner.status, "value") else runner.status

        return {
            "id": link.id,
            "automation_id": link.automation_id,
            "runner_id": link.runner_id,
            "runner_name": runner.name if runner else None,
            "runner_label": runner.label if runner else None,
            "runner_status": status,
            "runner_enabled": runner.enabled if runner else None,
            "created_at": getattr(link, "created_at", None),
        }

    @staticmethod
    def list_by_automation(db: Session, automation_id: int):
        AutomationService.get(db, automation_id)
        links = AutomationRunnerRepository.list_by_automation(db, automation_id)
        return [AutomationRunnerService._serialize(link) for link in links]

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

        link = AutomationRunnerRepository.create(
            db,
            {
                "automation_id": automation_id,
                "runner_id": runner_id,
            },
        )
        link = AutomationRunnerRepository.get_by_id(db, link.id)
        return AutomationRunnerService._serialize(link)

    @staticmethod
    def unlink_runner(db: Session, automation_id: int, link_id: int):
        AutomationService.get(db, automation_id)

        link = AutomationRunnerRepository.get_by_id(db, link_id)
        if not link or link.automation_id != automation_id:
            raise NotFoundException("Vínculo de runner não encontrado para essa automação")

        AutomationRunnerRepository.delete(db, link)
        