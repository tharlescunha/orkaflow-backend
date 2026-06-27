from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.domain.enums import TaskStatus
from app.models.automation import Automation
from app.models.automation_runner import AutomationRunner
from app.models.runner import Runner
from app.models.runner_config import RunnerConfig
from app.models.task import Task
from app.models.bot import Bot
from datetime import UTC, datetime
from sqlalchemy import case, func, select, distinct

class RunnerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, runner_id: int) -> Runner | None:
        stmt = (
            select(Runner)
            .options(selectinload(Runner.config))
            .where(Runner.id == runner_id)
        )
        return self.db.scalar(stmt)

    def get_by_label(self, label: str) -> Runner | None:
        stmt = select(Runner).where(Runner.label == label)
        return self.db.scalar(stmt)

    def get_by_name(self, name: str) -> Runner | None:
        stmt = select(Runner).where(Runner.name == name)
        return self.db.scalar(stmt)

    def get_by_machine_uuid(self, machine_uuid: str) -> Runner | None:
        stmt = select(Runner).where(Runner.uuid == machine_uuid)
        return self.db.scalar(stmt)

    def get_by_uuid(self, uuid: str) -> Runner | None:
        stmt = select(Runner).where(Runner.uuid == uuid)
        return self.db.scalar(stmt)

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        enabled: bool | None = None,
        status: str | None = None,
    ) -> list[Runner]:
        stmt = select(Runner).options(selectinload(Runner.config)).order_by(Runner.name)

        if enabled is not None:
            stmt = stmt.where(Runner.enabled == enabled)

        if status is not None:
            stmt = stmt.where(Runner.status == status)

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create(self, **data) -> Runner:
        runner = Runner(**data)
        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)
        return runner

    def update(self, runner: Runner, **data) -> Runner:
        for field, value in data.items():
            if value is not None:
                setattr(runner, field, value)

        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)
        return runner

    def disable(self, runner: Runner) -> Runner:
        runner.enabled = False
        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)
        return runner

    def create_config(self, runner_id: int, **data) -> RunnerConfig:
        config = RunnerConfig(runner_id=runner_id, **data)
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def get_config(self, runner_id: int) -> RunnerConfig | None:
        stmt = select(RunnerConfig).where(RunnerConfig.runner_id == runner_id)
        return self.db.scalar(stmt)

    def update_config(self, config: RunnerConfig, **data) -> RunnerConfig:
        for field, value in data.items():
            if value is not None:
                setattr(config, field, value)

        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    # NOVO
    def count_running_tasks(self, runner_id: int) -> int:
        stmt = (
            select(func.count(Task.id))
            .where(Task.runner_id == runner_id)
            .where(Task.status == TaskStatus.RUNNING)
        )
        return int(self.db.execute(stmt).scalar_one() or 0)

    # NOVO
    def count_linked_bots(self, runner_id: int) -> int:
        stmt = (
            select(func.count(func.distinct(Automation.bot_id)))
            .select_from(AutomationRunner)
            .join(Automation, Automation.id == AutomationRunner.automation_id)
            .where(AutomationRunner.runner_id == runner_id)
        )
        return int(self.db.execute(stmt).scalar_one() or 0)
    
    def list_linked_bots(self, runner_id: int) -> list[dict]:
        stmt = (
            select(
                Bot.id.label("bot_id"),
                Bot.name.label("bot_name"),
            )
            .select_from(AutomationRunner)
            .join(Automation, Automation.id == AutomationRunner.automation_id)
            .join(Bot, Bot.id == Automation.bot_id)
            .where(AutomationRunner.runner_id == runner_id)
            .group_by(Bot.id, Bot.name)
            .order_by(Bot.name.asc())
        )

        rows = self.db.execute(stmt).all()
        return [
            {
                "bot_id": row.bot_id,
                "bot_name": row.bot_name,
            }
            for row in rows
        ]

    def get_runner_task_counts(
        self,
        runner_id: int,
        date_from=None,
        date_to=None,
        status=None,
        automation_id: int | None = None,
    ) -> dict:
        stmt = select(
            func.count(case((Task.status == TaskStatus.RUNNING, 1))).label("running_tasks_count"),
            func.count(case((Task.status == TaskStatus.WAITING, 1))).label("waiting_tasks_count"),
            func.count(case((Task.status == TaskStatus.SCHEDULED, 1))).label("scheduled_tasks_count"),
            func.count(case((Task.status == TaskStatus.READY, 1))).label("ready_tasks_count"),
            func.count(case((Task.status == TaskStatus.STOP_REQUESTED, 1))).label("stop_requested_tasks_count"),
            func.count(case((Task.status == TaskStatus.FINISHED, 1))).label("finished_tasks_count"),
            func.count(case((Task.status == TaskStatus.ERROR, 1))).label("error_tasks_count"),
            func.count(case((Task.status == TaskStatus.TIMEOUT, 1))).label("timeout_tasks_count"),
            func.count(case((Task.status == TaskStatus.CANCELED, 1))).label("canceled_tasks_count"),
            func.count(case((Task.status == TaskStatus.FORCED_STOP, 1))).label("forced_stop_tasks_count"),
        ).where(Task.runner_id == runner_id)

        if date_from is not None:
            stmt = stmt.where(Task.created_at >= date_from)

        if date_to is not None:
            stmt = stmt.where(Task.created_at <= date_to)

        if status is not None:
            stmt = stmt.where(Task.status == status)

        if automation_id is not None:
            stmt = stmt.where(Task.automation_id == automation_id)

        row = self.db.execute(stmt).one()

        return {
            "running_tasks_count": int(row.running_tasks_count or 0),
            "waiting_tasks_count": int(row.waiting_tasks_count or 0),
            "scheduled_tasks_count": int(row.scheduled_tasks_count or 0),
            "ready_tasks_count": int(row.ready_tasks_count or 0),
            "stop_requested_tasks_count": int(row.stop_requested_tasks_count or 0),
            "finished_tasks_count": int(row.finished_tasks_count or 0),
            "error_tasks_count": int(row.error_tasks_count or 0),
            "timeout_tasks_count": int(row.timeout_tasks_count or 0),
            "canceled_tasks_count": int(row.canceled_tasks_count or 0),
            "forced_stop_tasks_count": int(row.forced_stop_tasks_count or 0),
        }

    def list_running_tasks(
        self,
        runner_id: int,
        automation_id: int | None = None,
    ) -> list[Task]:
        stmt = (
            select(Task)
            .options(selectinload(Task.automation))
            .where(Task.runner_id == runner_id)
            .where(Task.status == TaskStatus.RUNNING)
            .order_by(Task.started_at.asc(), Task.id.asc())
        )

        if automation_id is not None:
            stmt = stmt.where(Task.automation_id == automation_id)

        return list(self.db.execute(stmt).scalars().all())
    
    def list_recent_tasks(
        self,
        runner_id: int,
        limit: int = 10,
        date_from=None,
        date_to=None,
        status=None,
        automation_id: int | None = None,
    ) -> list[Task]:
        stmt = (
            select(Task)
            .options(selectinload(Task.automation))
            .where(Task.runner_id == runner_id)
            .order_by(Task.created_at.desc(), Task.id.desc())
            .limit(limit)
        )

        if date_from is not None:
            stmt = stmt.where(Task.created_at >= date_from)

        if date_to is not None:
            stmt = stmt.where(Task.created_at <= date_to)

        if status is not None:
            stmt = stmt.where(Task.status == status)

        if automation_id is not None:
            stmt = stmt.where(Task.automation_id == automation_id)

        return list(self.db.execute(stmt).scalars().all())

    def get_last_execution_task(
        self,
        runner_id: int,
        date_from=None,
        date_to=None,
        status=None,
        automation_id: int | None = None,
    ) -> Task | None:
        stmt = (
            select(Task)
            .options(selectinload(Task.automation))
            .where(Task.runner_id == runner_id)
            .where(Task.started_at.is_not(None))
            .order_by(Task.started_at.desc(), Task.id.desc())
        )

        if date_from is not None:
            stmt = stmt.where(Task.created_at >= date_from)

        if date_to is not None:
            stmt = stmt.where(Task.created_at <= date_to)

        if status is not None:
            stmt = stmt.where(Task.status == status)

        if automation_id is not None:
            stmt = stmt.where(Task.automation_id == automation_id)

        return self.db.execute(stmt).scalars().first()

    def get_oldest_waiting_task(
        self,
        runner_id: int,
        automation_id: int | None = None,
    ) -> Task | None:
        stmt = (
            select(Task)
            .options(selectinload(Task.automation))
            .where(Task.runner_id == runner_id)
            .where(Task.status == TaskStatus.WAITING)
            .order_by(Task.created_at.asc(), Task.id.asc())
        )

        if automation_id is not None:
            stmt = stmt.where(Task.automation_id == automation_id)

        return self.db.execute(stmt).scalars().first()

    def get_total_execution_seconds(
        self,
        runner_id: int,
        date_from=None,
        date_to=None,
        status=None,
        automation_id: int | None = None,
    ) -> int:
        tasks = self.list_recent_tasks(
            runner_id=runner_id,
            limit=100000,
            date_from=date_from,
            date_to=date_to,
            status=status,
            automation_id=automation_id,
        )

        now = datetime.now(UTC)
        total = 0

        for task in tasks:
            if task.started_at and task.finished_at:
                total += int((task.finished_at - task.started_at).total_seconds())
            elif task.started_at and task.status == TaskStatus.RUNNING:
                total += int((now - task.started_at).total_seconds())

        return total
    