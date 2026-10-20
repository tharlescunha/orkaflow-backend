"""Helpers para registrar TaskLog/TaskError gerados pelo sistema (watchdog, dispatcher, scheduler)."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import ErrorCategory, TaskLogLevel, TaskLogSource
from app.models.task_error import TaskError
from app.models.task_log import TaskLog


def add_task_log(
    db: Session,
    task_id: int,
    message: str,
    *,
    level: TaskLogLevel = TaskLogLevel.WARNING,
    source: TaskLogSource = TaskLogSource.SYSTEM,
    event_code: str | None = None,
    runner_id: int | None = None,
    reference: str | None = None,
) -> TaskLog:
    log = TaskLog(
        task_id=task_id,
        level=level,
        message=message,
        source=source,
        event_code=event_code,
        runner_id=runner_id,
        reference=reference,
    )
    db.add(log)
    return log


def has_log(
    db: Session,
    task_id: int,
    event_code: str,
    *,
    within: timedelta | None = None,
) -> bool:
    stmt = (
        select(func.count(TaskLog.id))
        .where(TaskLog.task_id == task_id)
        .where(TaskLog.event_code == event_code)
    )
    if within is not None:
        stmt = stmt.where(TaskLog.created_at >= datetime.now(UTC) - within)
    return int(db.execute(stmt).scalar_one() or 0) > 0


def add_task_log_once(
    db: Session,
    task_id: int,
    message: str,
    event_code: str,
    *,
    within: timedelta | None = None,
    **kwargs,
) -> bool:
    """Grava o log só se ainda não existir um com o mesmo event_code (dentro da janela)."""
    if has_log(db, task_id, event_code, within=within):
        return False
    add_task_log(db, task_id, message, event_code=event_code, **kwargs)
    return True


def add_task_error(
    db: Session,
    task_id: int,
    error_type: str,
    message: str,
    *,
    category: ErrorCategory | None = ErrorCategory.TECHNICAL,
    source: TaskLogSource = TaskLogSource.SYSTEM,
    code: str | None = None,
    is_retryable: bool = False,
) -> TaskError:
    error = TaskError(
        task_id=task_id,
        error_type=error_type[:100],
        message=message,
        error_category=category,
        is_retryable=is_retryable,
        source=source,
        code=code,
    )
    db.add(error)
    return error
