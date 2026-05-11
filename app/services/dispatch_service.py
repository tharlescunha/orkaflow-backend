from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.domain.enums import RunnerStatus, TaskStatus
from app.repositories.automation_runner_repository import AutomationRunnerRepository
from app.repositories.runner_repository import RunnerRepository
from app.repositories.task_repository import TaskRepository


class DispatchService:
    """
    Dispatcher compatível com a estrutura atual do projeto.

    Papel dele no fluxo atual:
    - procurar tasks em WAITING sem runner definido
    - encontrar um runner ONLINE/ENABLED elegível para a automação
    - pré-vincular a task ao runner
    - manter a task em WAITING

    Importante:
    Quem muda WAITING -> READY hoje é o WorkerService.claim_task().
    Então este service NÃO deve colocar a task em READY.

    REGRA ATUAL:
    - só despacha task para runner ONLINE e habilitado
    - não despacha para runner OFFLINE
    - não despacha para runner BUSY
    - não despacha para runner MAINTENANCE
    - não despacha para runner BLOCKED
    - só despacha se o runner não tiver nenhuma task aberta vinculada
    - task finalizada, cancelada, erro ou timeout não bloqueia novo despacho
    """

    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepository(db)
        self.runner_repo = RunnerRepository(db)
        self.automation_runner_repo = AutomationRunnerRepository

    def dispatch_pending_tasks(self) -> int:
        waiting_tasks, _ = self.task_repo.list_all(
            skip=0,
            limit=500,
            status=TaskStatus.WAITING,
        )

        dispatched = 0

        for task in waiting_tasks:
            # Dispatcher só trabalha em task ainda não vinculada
            if task.runner_id is not None:
                continue

            # Segurança extra para agendamento futuro
            if (
                task.requested_start_at is not None
                and task.requested_start_at > datetime.now(UTC)
            ):
                continue

            runner = self._find_best_runner_for_task(task)
            if not runner:
                continue

            self.task_repo.update(
                task,
                {
                    "runner_id": runner.id,
                    "last_update_at": datetime.now(UTC),
                    "dispatch_attempts": (task.dispatch_attempts or 0) + 1,
                },
            )

            dispatched += 1

        if dispatched:
            self.db.commit()

        return dispatched

    def _find_best_runner_for_task(self, task):
        links = self.automation_runner_repo.list_by_automation(
            self.db,
            task.automation_id,
        )

        if not links:
            return None

        eligible_runner_ids = [link.runner_id for link in links]

        available_runners = self.runner_repo.list_all(
            skip=0,
            limit=500,
            enabled=True,
        )

        candidates = [
            runner
            for runner in available_runners
            if runner.id in eligible_runner_ids
        ]

        for runner in candidates:
            if not self._runner_can_receive_task(runner, task):
                continue

            return runner

        return None

    def _runner_can_receive_task(self, runner, task) -> bool:
        if not runner.enabled:
            return False

        if runner.status != RunnerStatus.ONLINE:
            return False

        if runner.status in (
            RunnerStatus.OFFLINE,
            RunnerStatus.BUSY,
            RunnerStatus.MAINTENANCE,
            RunnerStatus.BLOCKED,
        ):
            return False

        if not self.task_repo.automation_has_runner_link(
            task.automation_id,
            runner.id,
        ):
            return False

        # Regra principal:
        # runner só recebe nova task se não tiver nenhuma task aberta vinculada.
        if self.task_repo.count_open_for_runner(runner.id) > 0:
            return False

        return True

