"""Retentativa automática por automação (out/2026).

Quando uma task de um agendamento termina com erro ou timeout e o agendamento tem ``retry_max`` > 0,
o orquestrador cria sozinho a próxima tentativa: mesma automação e parâmetros, ``execution_mode=retry``,
``parent_task_id`` apontando para a que falhou, ``retry_count`` incrementado e
``requested_start_at = agora + retry_delay_seconds`` (status SCHEDULED; o motor de agendamento
promove para WAITING na hora certa e o despacho normal aplica máquina e grupo exclusivo).

Fica no agendamento (não na automação) porque o mesmo robô pode ter dois agendamentos com regras
diferentes. Task manual ou via API não retenta sozinha.
Nunca retenta: cancelada, parada forçada, credencial inválida, agendamento/automação/bot inativos,
falha que não está em ``retry_on``, outra task já aberta para a automação, ou tentativas esgotadas.
Nunca levanta exceção: um problema aqui não pode derrubar o fechamento da task.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.enums import ExecutionMode, TaskLogLevel, TaskLogSource, TaskStatus
from app.models.automation import Automation
from app.models.schedule import Schedule
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.services.credential_health_service import CredentialHealthService
from app.services.task_events import add_task_log

logger = logging.getLogger("orkaflow.retry")

RETRY_MAX_LIMIT = 5
RETRY_ON_OPTIONS = ("erro", "timeout")
DEFAULT_RETRY_ON = ["erro", "timeout"]

_STATUS_TO_OPTION = {
    TaskStatus.ERROR: "erro",
    TaskStatus.TIMEOUT: "timeout",
}


def retry_on_for(schedule: Schedule) -> list[str]:
    raw = getattr(schedule, "retry_on_json", None)
    if isinstance(raw, list) and raw:
        return [str(item) for item in raw if str(item) in RETRY_ON_OPTIONS]
    return list(DEFAULT_RETRY_ON)


def _status_value(task: Task) -> TaskStatus | None:
    status = task.status
    if isinstance(status, TaskStatus):
        return status
    try:
        return TaskStatus(str(status))
    except ValueError:
        return None


def schedule_retry_if_applicable(db: Session, task: Task) -> Task | None:
    """Cria a próxima tentativa se a automação pedir. Devolve a task nova ou None."""
    try:
        with db.begin_nested():
            return _schedule(db, task)
    except Exception:  # noqa: BLE001
        logger.exception("Retentativa: falha ao avaliar a task %s", getattr(task, "id", None))
        return None


def _schedule(db: Session, task: Task) -> Task | None:
    status = _status_value(task)
    option = _STATUS_TO_OPTION.get(status) if status else None
    if option is None:
        return None  # sucesso, cancelada, parada forçada etc.

    if not task.schedule_id:
        return None  # só tasks de agendamento retentam
    schedule = db.get(Schedule, task.schedule_id)
    if schedule is None:
        return None
    retry_max = int(getattr(schedule, "retry_max", 0) or 0)
    if retry_max <= 0:
        return None
    if option not in retry_on_for(schedule):
        return None
    if not schedule.active:
        return _skip(db, task, "agendamento pausado ou inativo")

    automation = task.automation or db.get(Automation, task.automation_id)
    if automation is None:
        return None

    attempt = int(task.retry_count or 0)
    if attempt >= retry_max:
        add_task_log(
            db,
            task.id,
            f"Retentativa automática esgotada: {attempt} de {retry_max} tentativa(s) extra(s) já feita(s). "
            "A automação não vai tentar de novo sozinha.",
            level=TaskLogLevel.WARNING,
            source=TaskLogSource.SYSTEM,
            event_code="RETRY_EXHAUSTED",
            runner_id=task.runner_id,
        )
        return None

    if not automation.active or not automation.bot or not automation.bot.active:
        return _skip(db, task, "automação ou bot inativos")

    blocked = CredentialHealthService(db).blocked_reason(automation)
    if blocked:
        return _skip(db, task, blocked)

    repo = TaskRepository(db)
    open_task = repo.get_open_task_for_automation(automation.id, exclude_task_id=task.id)
    if open_task:
        return _skip(db, task, f"já existe a task #{open_task.id} aberta para a automação")

    delay = max(0, int(getattr(schedule, "retry_delay_seconds", 0) or 0))
    now = datetime.now(UTC)
    start_at = now + timedelta(seconds=delay)

    new_task = repo.create(
        {
            "automation_id": task.automation_id,
            "bot_version_id": task.bot_version_id,
            "runner_id": None,  # despacho normal escolhe a máquina (grupo exclusivo respeitado)
            "created_by": task.created_by,
            "schedule_id": task.schedule_id,
            "parent_task_id": task.id,
            "priority": task.priority,
            "status": TaskStatus.SCHEDULED if delay > 0 else TaskStatus.WAITING,
            "requested_start_at": start_at if delay > 0 else None,
            "timeout_seconds": task.timeout_seconds,
            "inactivity_timeout_seconds": task.inactivity_timeout_seconds,
            "execution_mode": ExecutionMode.RETRY,
            "correlation_id": task.correlation_id,
            "queue_name": task.queue_name,
            "retry_count": attempt + 1,
            "last_update_at": now,
            "created_at": now,
        }
    )

    parameters = [
        {
            "parameter_name": p.parameter_name,
            "parameter_value": p.parameter_value,
            "is_secret": p.is_secret,
            "resolved_from_credential_item_id": p.resolved_from_credential_item_id,
        }
        for p in repo.get_parameters(task.id)
    ]
    if parameters:
        repo.create_parameters_bulk(new_task.id, parameters)

    when = "agora" if delay <= 0 else f"em {delay}s ({start_at.isoformat(timespec='seconds')})"
    add_task_log(
        db,
        task.id,
        f"Retentativa automática {attempt + 1} de {retry_max}: task #{new_task.id} criada para rodar {when}.",
        level=TaskLogLevel.INFO,
        source=TaskLogSource.SYSTEM,
        event_code="RETRY_SCHEDULED",
        runner_id=task.runner_id,
    )
    add_task_log(
        db,
        new_task.id,
        f"Tentativa {attempt + 1} de {retry_max} da task #{task.id} ({option}).",
        level=TaskLogLevel.INFO,
        source=TaskLogSource.SYSTEM,
        event_code="RETRY_OF",
    )
    logger.info("Retentativa: task %s -> nova task %s (tentativa %s/%s)", task.id, new_task.id, attempt + 1, retry_max)
    return new_task


def _skip(db: Session, task: Task, reason: str) -> None:
    add_task_log(
        db,
        task.id,
        f"Retentativa automática não criada: {reason}.",
        level=TaskLogLevel.WARNING,
        source=TaskLogSource.SYSTEM,
        event_code="RETRY_SKIPPED",
        runner_id=task.runner_id,
    )
    return None
