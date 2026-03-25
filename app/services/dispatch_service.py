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
    - respeitar concorrência do runner
    - pré-vincular a task ao runner
    - manter a task em WAITING

    Importante:
    Quem muda WAITING -> READY hoje é o WorkerService.claim_task().
    Então este service NÃO deve colocar a task em READY.
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
            if task.requested_start_at is not None and task.requested_start_at > datetime.now(UTC):
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
        links = self.automation_runner_repo.list_by_automation(self.db, task.automation_id)
        if not links:
            return None

        eligible_runner_ids = [link.runner_id for link in links]

        available_runners = self.runner_repo.list_all(
            skip=0,
            limit=500,
            enabled=True,
            status=RunnerStatus.ONLINE,
        )

        candidates = [runner for runner in available_runners if runner.id in eligible_runner_ids]

        best_runner = None
        best_load = None

        for runner in candidates:
            if not self._runner_can_receive_task(runner, task):
                continue

            current_load = self.task_repo.count_active_for_runner(runner.id)

            if best_runner is None or current_load < best_load:
                best_runner = runner
                best_load = current_load

        return best_runner

    def _runner_can_receive_task(self, runner, task) -> bool:
        if runner.status != RunnerStatus.ONLINE:
            return False

        if not runner.enabled:
            return False

        if not self.task_repo.automation_has_runner_link(task.automation_id, runner.id):
            return False

        config = self.runner_repo.get_config(runner.id)
        max_concurrency = 1

        if config and config.max_concurrency is not None:
            max_concurrency = max(1, config.max_concurrency)

        current_running = self.task_repo.count_active_for_runner(runner.id)
        if current_running >= max_concurrency:
            return False

        return True