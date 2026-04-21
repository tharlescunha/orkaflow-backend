from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import TaskStatus
from app.models.automation import Automation
from app.models.automation_runner import AutomationRunner
from app.models.bot_version import BotVersion
from app.models.runner import Runner
from app.models.task import Task
from app.models.task_parameter import TaskParameter


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def _detail_query(self) -> Select[tuple[Task]]:
        return (
            select(Task)
            .options(
                selectinload(Task.parameters),
                selectinload(Task.automation),
                selectinload(Task.runner).selectinload(Runner.config),
                selectinload(Task.bot_version),
                selectinload(Task.created_by_user),
                selectinload(Task.schedule),
                selectinload(Task.telemetry),
            )
        )

    def _list_query(self) -> Select[tuple[Task]]:
        return (
            select(Task)
            .options(
                selectinload(Task.automation),
                selectinload(Task.runner),
                selectinload(Task.bot_version),
                selectinload(Task.created_by_user),
            )
        )

    def get_by_id(self, task_id: int) -> Task | None:
        stmt = self._detail_query().where(Task.id == task_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        statuses: list[TaskStatus] | None = None,
        automation_ids: list[int] | None = None,
        runner_ids: list[int] | None = None,
        created_by: int | None = None,
    ) -> tuple[Sequence[Task], int]:
        stmt = self._list_query()
        count_stmt = select(func.count(Task.id))

        if statuses:
            stmt = stmt.where(Task.status.in_(statuses))
            count_stmt = count_stmt.where(Task.status.in_(statuses))

        if automation_ids:
            stmt = stmt.where(Task.automation_id.in_(automation_ids))
            count_stmt = count_stmt.where(Task.automation_id.in_(automation_ids))

        if runner_ids:
            stmt = stmt.where(Task.runner_id.in_(runner_ids))
            count_stmt = count_stmt.where(Task.runner_id.in_(runner_ids))

        if created_by is not None:
            stmt = stmt.where(Task.created_by == created_by)
            count_stmt = count_stmt.where(Task.created_by == created_by)

        stmt = stmt.order_by(Task.id.desc()).offset(skip).limit(limit)

        items = self.db.execute(stmt).scalars().all()
        total = self.db.execute(count_stmt).scalar_one()

        return items, total

    def list_active_automation_options(self) -> Sequence[Automation]:
        stmt = (
            select(Automation)
            .where(Automation.active == True)
            .order_by(Automation.name.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def list_active_runner_options(self) -> Sequence[Runner]:
        stmt = (
            select(Runner)
            .where(Runner.enabled == True)
            .order_by(Runner.name.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def create(self, data: dict) -> Task:
        task = Task(**data)
        self.db.add(task)
        self.db.flush()
        self.db.refresh(task)
        return task

    def update(self, task: Task, data: dict) -> Task:
        for field, value in data.items():
            setattr(task, field, value)

        self.db.add(task)
        self.db.flush()
        self.db.refresh(task)
        return task

    def create_parameter(self, data: dict) -> TaskParameter:
        parameter = TaskParameter(**data)
        self.db.add(parameter)
        self.db.flush()
        self.db.refresh(parameter)
        return parameter

    def create_parameters_bulk(self, task_id: int, parameters: list[dict]) -> list[TaskParameter]:
        created: list[TaskParameter] = []

        for param in parameters:
            payload = dict(param)
            payload["task_id"] = task_id
            created.append(self.create_parameter(payload))

        return created

    def get_parameters(self, task_id: int) -> Sequence[TaskParameter]:
        stmt = (
            select(TaskParameter)
            .where(TaskParameter.task_id == task_id)
            .order_by(TaskParameter.id.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def get_automation_by_id(self, automation_id: int) -> Automation | None:
        stmt = select(Automation).where(Automation.id == automation_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_latest_bot_version_for_bot(self, bot_id: int) -> BotVersion | None:
        stmt = (
            select(BotVersion)
            .where(BotVersion.bot_id == bot_id)
            .order_by(BotVersion.id.desc())
        )
        return self.db.execute(stmt).scalars().first()

    def get_automation_parameters(self, automation_id: int):
        from app.models.automation_parameter import AutomationParameter

        stmt = (
            select(AutomationParameter)
            .where(AutomationParameter.automation_id == automation_id)
            .order_by(AutomationParameter.order_index.asc(), AutomationParameter.id.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def automation_has_runner_link(self, automation_id: int, runner_id: int) -> bool:
        stmt = select(AutomationRunner).where(
            AutomationRunner.automation_id == automation_id,
            AutomationRunner.runner_id == runner_id,
        )
        return self.db.execute(stmt).scalar_one_or_none() is not None

    def count_active_for_runner(self, runner_id: int) -> int:
        active_statuses = (
            TaskStatus.READY,
            TaskStatus.RUNNING,
            TaskStatus.STOP_REQUESTED,
        )

        stmt = (
            select(func.count(Task.id))
            .where(Task.runner_id == runner_id)
            .where(Task.status.in_(active_statuses))
        )
        return int(self.db.execute(stmt).scalar_one())

    def list_active_for_runner(self, runner_id: int) -> Sequence[Task]:
        active_statuses = (
            TaskStatus.READY,
            TaskStatus.RUNNING,
            TaskStatus.STOP_REQUESTED,
        )

        stmt = (
            self._detail_query()
            .where(Task.runner_id == runner_id)
            .where(Task.status.in_(active_statuses))
            .order_by(Task.id.asc())
        )
        return self.db.execute(stmt).scalars().all()

    def list_waiting_candidates_for_runner(self, runner_id: int) -> Sequence[Task]:
        now = datetime.now(UTC)

        stmt = (
            self._detail_query()
            .where(Task.status == TaskStatus.WAITING)
            .where((Task.runner_id.is_(None)) | (Task.runner_id == runner_id))
            .where((Task.requested_start_at.is_(None)) | (Task.requested_start_at <= now))
            .order_by(Task.priority.desc(), Task.id.asc())
        )
        return self.db.execute(stmt).scalars().all()
    