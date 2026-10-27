"""Fila com explicação (out/2026): por que uma task WAITING ainda não foi para um runner.

Usado pelo dispatcher (pré-vinculação) e pelo next-task do worker. O motivo fica em
`tasks.waiting_reason` (apagado ao vincular/assumir) e vai uma vez por hora para o TaskLog,
para o histórico contar a história sem encher o log a cada ciclo.
"""
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.domain.enums import TaskLogLevel, TaskLogSource
from app.models.task import Task
from app.repositories.task_repository import TaskRepository
from app.services.task_events import add_task_log_once

REASON_LOG_WINDOW = timedelta(hours=1)
REASON_MAX_LEN = 300


@dataclass(frozen=True)
class WaitReason:
    message: str
    event_code: str


def describe_wait_reason(repo: TaskRepository, task: Task) -> WaitReason | None:
    """Regras de junho/2026 (uma task aberta por automação; exclusão mútua por grupo).

    Devolve o motivo na mesma ordem em que o claim do worker rejeitaria a task, ou None
    quando essas regras não a seguram.
    """
    open_task = repo.get_open_task_for_automation(task.automation_id, exclude_task_id=task.id)
    if open_task is not None:
        return WaitReason(
            f"Aguardando a task #{open_task.id} da mesma automação terminar "
            f"(uma task aberta por automação; ela está {open_task.status.value}).",
            "WAIT_AUTOMATION_BUSY",
        )
    reserved = repo.get_reserved_task_for_exclusive_groups(task.automation_id, exclude_task_id=task.id)
    if reserved is not None:
        return WaitReason(
            f"Aguardando o grupo exclusivo: a task #{reserved.id} (automação #{reserved.automation_id}) "
            f"está {reserved.status.value} e automações do mesmo grupo não rodam juntas.",
            "WAIT_EXCLUSIVE_GROUP",
        )
    if repo.has_active_lock_for_exclusive_groups(task.automation_id):
        return WaitReason(
            "Aguardando o grupo exclusivo: outra automação do grupo ainda segura o lock de execução.",
            "WAIT_EXCLUSIVE_GROUP_LOCK",
        )
    return None


def set_waiting_reason(
    db: Session,
    task: Task,
    reason: WaitReason,
    *,
    source: TaskLogSource = TaskLogSource.DISPATCHER,
) -> None:
    """Grava o motivo na task (só se mudou) e no log (no máximo 1x por hora por motivo)."""
    message = reason.message[:REASON_MAX_LEN]
    if task.waiting_reason != message:
        task.waiting_reason = message
        db.add(task)
    add_task_log_once(
        db,
        task.id,
        message,
        reason.event_code,
        within=REASON_LOG_WINDOW,
        level=TaskLogLevel.INFO,
        source=source,
    )
