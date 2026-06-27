import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.repositories.runner_repository import RunnerRepository
from app.schemas.runner import RunnerConfigUpdate, RunnerCreate, RunnerRead, RunnerUpdate
from datetime import UTC, datetime
from app.schemas.runner_overview import (
    RunnerOverviewLinkedBot,
    RunnerOverviewLastExecution,
    RunnerOverviewListItem,
    RunnerOverviewListResponse,
    RunnerOverviewQueue,
    RunnerOverviewResponse,
    RunnerOverviewRunnerInfo,
    RunnerOverviewSummary,
    RunnerOverviewTaskItem,
    RunnerOverviewUtilization,
)

class RunnerService:
    def __init__(self, db: Session):
        self.repo = RunnerRepository(db)

    def _build_runner_read(self, runner):
        running_tasks_count = self.repo.count_running_tasks(runner.id)
        linked_bots_count = self.repo.count_linked_bots(runner.id)

        display_status = runner.status
        if running_tasks_count > 0:
            display_status = "busy"
        elif runner.status == "busy":
            display_status = "online"

        return RunnerRead.model_validate(
            {
                "id": runner.id,
                "uuid": runner.uuid,
                "name": runner.name,
                "label": runner.label,
                "host_name": runner.host_name,
                "ip": runner.ip,
                "os_name": runner.os_name,
                "os_version": runner.os_version,
                "cpu_arch": runner.cpu_arch,
                "memory_total": runner.memory_total,
                "access_remote": runner.access_remote,
                "enabled": runner.enabled,
                "status": display_status,
                "last_heartbeat": runner.last_heartbeat,
                "created_at": runner.created_at,
                "updated_at": runner.updated_at,
                "config": runner.config,
                "running_tasks_count": running_tasks_count,
                "has_running_task": running_tasks_count > 0,
                "linked_bots_count": linked_bots_count,
                "last_screenshot_at": runner.last_screenshot_at,
                "has_screenshot": runner.last_screenshot_image is not None,
            }
        )

    def create(self, data: RunnerCreate):
        if self.repo.get_by_name(data.name):
            raise ConflictException("Já existe um runner com esse nome.")

        payload = data.model_dump(exclude={"config"})
        payload["uuid"] = str(uuid.uuid4())

        runner = self.repo.create(**payload)

        if data.config:
            self.repo.create_config(runner_id=runner.id, **data.config.model_dump())

        runner = self.repo.get_by_id(runner.id)
        return self._build_runner_read(runner)

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        enabled: bool | None = None,
        status: str | None = None,
    ):
        runners = self.repo.list_all(skip=skip, limit=limit, enabled=enabled, status=status)
        return [self._build_runner_read(runner) for runner in runners]

    def get(self, runner_id: int):
        runner = self.repo.get_by_id(runner_id)
        if not runner:
            raise NotFoundException("Runner não encontrado.")
        return self._build_runner_read(runner)

    def update(self, runner_id: int, data: RunnerUpdate):
        runner = self.repo.get_by_id(runner_id)
        if not runner:
            raise NotFoundException("Runner não encontrado.")

        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"] != runner.name:
            if self.repo.get_by_name(update_data["name"]):
                raise ConflictException("Já existe um runner com esse nome.")

        updated_runner = self.repo.update(runner, **update_data)
        updated_runner = self.repo.get_by_id(updated_runner.id)
        return self._build_runner_read(updated_runner)

    def disable(self, runner_id: int):
        runner = self.repo.get_by_id(runner_id)
        if not runner:
            raise NotFoundException("Runner não encontrado.")

        updated_runner = self.repo.disable(runner)
        updated_runner = self.repo.get_by_id(updated_runner.id)
        return self._build_runner_read(updated_runner)

    def get_config(self, runner_id: int):
        runner = self.repo.get_by_id(runner_id)
        if not runner:
            raise NotFoundException("Runner não encontrado.")

        config = self.repo.get_config(runner_id)
        if not config:
            raise NotFoundException("Configuração do runner não encontrada.")
        return config

    def update_config(self, runner_id: int, data: RunnerConfigUpdate):
        runner = self.repo.get_by_id(runner_id)
        if not runner:
            raise NotFoundException("Runner não encontrado.")

        config = self.repo.get_config(runner_id)
        if not config:
            raise NotFoundException("Configuração do runner não encontrada.")

        update_data = data.model_dump(exclude_unset=True)

        if "max_concurrency" in update_data and update_data["max_concurrency"] < 1:
            raise ValidationException("max_concurrency deve ser maior ou igual a 1.")

        if "polling_interval" in update_data and update_data["polling_interval"] < 5:
            raise ValidationException("polling_interval deve ser maior ou igual a 5.")

        return self.repo.update_config(config, **update_data)
    
    def _task_to_overview_item(self, task):
        execution_duration_seconds = None

        if task.started_at and task.finished_at:
            execution_duration_seconds = int((task.finished_at - task.started_at).total_seconds())
        elif task.started_at and str(task.status) == "TaskStatus.RUNNING":
            execution_duration_seconds = int((datetime.now(UTC) - task.started_at).total_seconds())
        elif task.started_at and getattr(task.status, "value", None) == "running":
            execution_duration_seconds = int((datetime.now(UTC) - task.started_at).total_seconds())

        return RunnerOverviewTaskItem(
            task_id=task.id,
            automation_id=task.automation_id,
            automation_name=task.automation.name if task.automation else None,
            status=task.status,
            started_at=task.started_at,
            finished_at=task.finished_at,
            created_at=task.created_at,
            execution_duration_seconds=execution_duration_seconds,
            final_message=task.final_message,
        )

    def get_overview(
        self,
        runner_id: int,
        date_from=None,
        date_to=None,
        status=None,
        automation_id: int | None = None,
    ):
        runner = self.repo.get_by_id(runner_id)
        if not runner:
            raise NotFoundException("Runner não encontrado.")

        counts = self.repo.get_runner_task_counts(
            runner_id=runner_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            automation_id=automation_id,
        )

        linked_bots = self.repo.list_linked_bots(runner_id)
        running_tasks = self.repo.list_running_tasks(
            runner_id=runner_id,
            automation_id=automation_id,
        )
        recent_tasks = self.repo.list_recent_tasks(
            runner_id=runner_id,
            limit=10,
            date_from=date_from,
            date_to=date_to,
            status=status,
            automation_id=automation_id,
        )
        last_task = self.repo.get_last_execution_task(
            runner_id=runner_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            automation_id=automation_id,
        )
        oldest_waiting = self.repo.get_oldest_waiting_task(
            runner_id=runner_id,
            automation_id=automation_id,
        )

        execution_seconds = self.repo.get_total_execution_seconds(
            runner_id=runner_id,
            date_from=date_from,
            date_to=date_to,
            status=status,
            automation_id=automation_id,
        )

        now = datetime.now(UTC)

        if date_from is not None:
            registered_base = date_from if date_from > runner.created_at else runner.created_at
        else:
            registered_base = runner.created_at

        if date_to is not None:
            utilization_end = date_to
        else:
            utilization_end = now

        registered_seconds = max(0, int((utilization_end - registered_base).total_seconds()))
        utilization_percent = 0.0

        if registered_seconds > 0:
            utilization_percent = round((execution_seconds / registered_seconds) * 100, 2)

        oldest_waiting_seconds = None
        if oldest_waiting and oldest_waiting.created_at:
            oldest_waiting_seconds = int((now - oldest_waiting.created_at).total_seconds())

        summary = RunnerOverviewSummary(
            linked_bots_count=len(linked_bots),
            running_tasks_count=counts["running_tasks_count"],
            waiting_tasks_count=counts["waiting_tasks_count"],
            scheduled_tasks_count=counts["scheduled_tasks_count"],
            ready_tasks_count=counts["ready_tasks_count"],
            stop_requested_tasks_count=counts["stop_requested_tasks_count"],
            finished_tasks_count=counts["finished_tasks_count"],
            error_tasks_count=counts["error_tasks_count"],
            timeout_tasks_count=counts["timeout_tasks_count"],
            canceled_tasks_count=counts["canceled_tasks_count"],
            forced_stop_tasks_count=counts["forced_stop_tasks_count"],
            executed_total_count=(
                counts["finished_tasks_count"]
                + counts["error_tasks_count"]
                + counts["timeout_tasks_count"]
                + counts["canceled_tasks_count"]
                + counts["forced_stop_tasks_count"]
            ),
            success_total_count=counts["finished_tasks_count"],
            error_total_count=(
                counts["error_tasks_count"]
                + counts["timeout_tasks_count"]
                + counts["forced_stop_tasks_count"]
            ),
        )

        return RunnerOverviewResponse(
            runner=RunnerOverviewRunnerInfo(
                id=runner.id,
                uuid=runner.uuid,
                name=runner.name,
                label=runner.label,
                host_name=runner.host_name,
                ip=runner.ip,
                os_name=runner.os_name,
                os_version=runner.os_version,
                cpu_arch=runner.cpu_arch,
                memory_total=runner.memory_total,
                access_remote=runner.access_remote,
                enabled=runner.enabled,
                status=getattr(self._build_runner_read(runner), "status"),
                created_at=runner.created_at,
                updated_at=runner.updated_at,
                last_heartbeat=runner.last_heartbeat,
            ),
            summary=summary,
            utilization=RunnerOverviewUtilization(
                registered_seconds=registered_seconds,
                execution_seconds=execution_seconds,
                utilization_percent=utilization_percent,
            ),
            queue=RunnerOverviewQueue(
                waiting_tasks_count=counts["waiting_tasks_count"],
                oldest_waiting_task_id=oldest_waiting.id if oldest_waiting else None,
                oldest_waiting_automation_name=oldest_waiting.automation.name if oldest_waiting and oldest_waiting.automation else None,
                oldest_waiting_since=oldest_waiting.created_at if oldest_waiting else None,
                oldest_waiting_seconds=oldest_waiting_seconds,
            ),
            last_execution=RunnerOverviewLastExecution(
                task_id=last_task.id if last_task else None,
                automation_id=last_task.automation_id if last_task else None,
                automation_name=last_task.automation.name if last_task and last_task.automation else None,
                status=last_task.status if last_task else None,
                started_at=last_task.started_at if last_task else None,
                finished_at=last_task.finished_at if last_task else None,
                execution_duration_seconds=self._task_to_overview_item(last_task).execution_duration_seconds if last_task else None,
                final_message=last_task.final_message if last_task else None,
            ),
            linked_bots=[
                RunnerOverviewLinkedBot(
                    bot_id=item["bot_id"],
                    bot_name=item["bot_name"],
                )
                for item in linked_bots
            ],
            running_tasks=[self._task_to_overview_item(task) for task in running_tasks],
            recent_tasks=[self._task_to_overview_item(task) for task in recent_tasks],
        )

    def list_overview(
        self,
        skip: int = 0,
        limit: int = 100,
        enabled: bool | None = None,
        status: str | None = None,
        date_from=None,
        date_to=None,
        task_status=None,
        automation_id: int | None = None,
    ):
        runners = self.repo.list_all(skip=skip, limit=limit, enabled=enabled, status=status)

        items = []
        for runner in runners:
            overview = self.get_overview(
                runner_id=runner.id,
                date_from=date_from,
                date_to=date_to,
                status=task_status,
                automation_id=automation_id,
            )

            items.append(
                RunnerOverviewListItem(
                    runner_id=overview.runner.id,
                    runner_name=overview.runner.name,
                    runner_label=overview.runner.label,
                    status=overview.runner.status,
                    enabled=overview.runner.enabled,
                    linked_bots_count=overview.summary.linked_bots_count,
                    running_tasks_count=overview.summary.running_tasks_count,
                    waiting_tasks_count=overview.summary.waiting_tasks_count,
                    executed_total_count=overview.summary.executed_total_count,
                    success_total_count=overview.summary.success_total_count,
                    error_total_count=overview.summary.error_total_count,
                    utilization_percent=overview.utilization.utilization_percent,
                    last_execution_at=overview.last_execution.started_at,
                    last_execution_status=overview.last_execution.status,
                )
            )

        return RunnerOverviewListResponse(items=items, total=len(items))
    