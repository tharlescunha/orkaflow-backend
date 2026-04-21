from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.automation import Automation
from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.repository import Repository
from app.models.runner import Runner
from app.models.task import Task
from app.models.task_error import TaskError
from app.models.user import User


class TaskErrorRepositoryExtended:
    def __init__(self, db: Session):
        self.db = db

    def _serialize_rich_error(self, error: TaskError) -> dict:
        task = error.task
        automation = task.automation if task else None
        bot_version = task.bot_version if task else None
        bot = bot_version.bot if bot_version else None
        repository = automation.repository if automation else None
        runner = task.runner if task else None
        user = task.created_by_user if task else None

        duration = None
        if task and task.started_at and task.finished_at:
            duration = int((task.finished_at - task.started_at).total_seconds())

        return {
            "id": error.id,
            "task_id": error.task_id,
            "error_type": error.error_type,
            "message": error.message,
            "stacktrace": error.stacktrace,
            "error_category": error.error_category,
            "is_retryable": error.is_retryable,
            "source": error.source,
            "code": error.code,
            "created_at": error.created_at,
            "updated_at": None,

            "task_status": task.status if task else None,

            "automation_id": automation.id if automation else None,
            "automation_name": automation.name if automation else None,
            "automation_label": automation.label if automation else None,

            "bot_id": bot.id if bot else None,
            "bot_name": bot.name if bot else None,

            "bot_version_id": bot_version.id if bot_version else None,
            "bot_version_label": bot_version.version if bot_version else None,

            "repository_id": repository.id if repository else None,
            "repository_name": repository.name if repository else None,

            "runner_id": runner.id if runner else None,
            "runner_name": runner.name if runner else None,
            "runner_label": runner.label if runner else None,

            "created_by": user.id if user else None,
            "created_by_name": user.name if user else None,

            "final_message": task.final_message if task else None,

            "task_created_at": task.created_at if task else None,
            "task_started_at": task.started_at if task else None,
            "task_finished_at": task.finished_at if task else None,

            "execution_duration_seconds": duration,
        }

    def get_rich_error(self, error_id: int) -> dict | None:
        stmt = (
            select(TaskError)
            .where(TaskError.id == error_id)
            .join(Task, Task.id == TaskError.task_id)
            .join(Automation, Automation.id == Task.automation_id)
            .join(BotVersion, BotVersion.id == Task.bot_version_id)
            .join(Bot, Bot.id == BotVersion.bot_id)
            .join(Repository, Repository.id == Automation.repository_id)
            .outerjoin(Runner, Runner.id == Task.runner_id)
            .outerjoin(User, User.id == Task.created_by)
            .options(
                joinedload(TaskError.task)
                .joinedload(Task.automation)
                .joinedload(Automation.repository),
                joinedload(TaskError.task)
                .joinedload(Task.bot_version)
                .joinedload(BotVersion.bot),
                joinedload(TaskError.task).joinedload(Task.runner),
                joinedload(TaskError.task).joinedload(Task.created_by_user),
            )
        )

        error = self.db.execute(stmt).scalar_one_or_none()
        if not error:
            return None

        return self._serialize_rich_error(error)

    def list_all(
        self,
        *,
        skip: int = 0,
        limit: int = 10,
        q: str | None = None,
        task_id: int | None = None,
        automation_id: int | None = None,
        error_type: str | None = None,
        error_category: str | None = None,
        source: str | None = None,
        code: str | None = None,
        is_retryable: bool | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[Sequence[dict], int]:
        stmt = (
            select(TaskError)
            .join(Task, Task.id == TaskError.task_id)
            .join(Automation, Automation.id == Task.automation_id)
            .join(BotVersion, BotVersion.id == Task.bot_version_id)
            .join(Bot, Bot.id == BotVersion.bot_id)
            .join(Repository, Repository.id == Automation.repository_id)
            .outerjoin(Runner, Runner.id == Task.runner_id)
            .outerjoin(User, User.id == Task.created_by)
            .options(
                joinedload(TaskError.task)
                .joinedload(Task.automation)
                .joinedload(Automation.repository),
                joinedload(TaskError.task)
                .joinedload(Task.bot_version)
                .joinedload(BotVersion.bot),
                joinedload(TaskError.task).joinedload(Task.runner),
                joinedload(TaskError.task).joinedload(Task.created_by_user),
            )
        )

        count_stmt = (
            select(func.count(TaskError.id))
            .join(Task, Task.id == TaskError.task_id)
            .join(Automation, Automation.id == Task.automation_id)
        )

        if task_id:
            stmt = stmt.where(TaskError.task_id == task_id)
            count_stmt = count_stmt.where(TaskError.task_id == task_id)

        if automation_id:
            stmt = stmt.where(Task.automation_id == automation_id)
            count_stmt = count_stmt.where(Task.automation_id == automation_id)

        if error_type:
            stmt = stmt.where(TaskError.error_type == error_type)
            count_stmt = count_stmt.where(TaskError.error_type == error_type)

        if error_category:
            stmt = stmt.where(TaskError.error_category == error_category)
            count_stmt = count_stmt.where(TaskError.error_category == error_category)

        if source:
            stmt = stmt.where(TaskError.source == source)
            count_stmt = count_stmt.where(TaskError.source == source)

        if code:
            stmt = stmt.where(TaskError.code == code)
            count_stmt = count_stmt.where(TaskError.code == code)

        if is_retryable is not None:
            stmt = stmt.where(TaskError.is_retryable == is_retryable)
            count_stmt = count_stmt.where(TaskError.is_retryable == is_retryable)

        if start_date:
            stmt = stmt.where(TaskError.created_at >= start_date)
            count_stmt = count_stmt.where(TaskError.created_at >= start_date)

        if end_date:
            stmt = stmt.where(TaskError.created_at <= end_date)
            count_stmt = count_stmt.where(TaskError.created_at <= end_date)

        if q:
            search = f"%{q}%"
            stmt = stmt.where(
                or_(
                    TaskError.message.ilike(search),
                    TaskError.stacktrace.ilike(search),
                    Automation.name.ilike(search),
                    Automation.label.ilike(search),
                    Bot.name.ilike(search),
                    Repository.name.ilike(search),
                    Runner.name.ilike(search),
                    Runner.label.ilike(search),
                )
            )
            count_stmt = count_stmt.where(
                or_(
                    TaskError.message.ilike(search),
                    TaskError.stacktrace.ilike(search),
                    Automation.name.ilike(search),
                    Automation.label.ilike(search),
                    Bot.name.ilike(search),
                    Repository.name.ilike(search),
                    Runner.name.ilike(search),
                    Runner.label.ilike(search),
                )
            )

        stmt = stmt.order_by(TaskError.created_at.desc(), TaskError.id.desc()).offset(skip).limit(limit)

        items = self.db.execute(stmt).scalars().all()
        total = self.db.execute(count_stmt).scalar_one()

        return [self._serialize_rich_error(error) for error in items], total
    