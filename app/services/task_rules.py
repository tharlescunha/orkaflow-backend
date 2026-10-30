"""Constantes e helpers compartilhados das regras de execução de tasks."""
from datetime import UTC, datetime

from app.domain.enums import TaskStatus

# Margem somada ao timeout da task antes do backend declarar TIMEOUT
# (o worker já mata o processo no timeout dele).
TASK_TIMEOUT_MARGIN_SECONDS = 120

# Task READY (claim feito) que nunca chegou a RUNNING e ficou parada.
STALE_READY_CLAIM_SECONDS = 30 * 60

# Task RUNNING sem nenhum sinal do worker (log do worker/robô ou progresso) depois do início:
# o worker avisou "iniciada" mas travou antes de executar. Não precisa esperar o timeout inteiro.
NO_WORKER_SIGNAL_SECONDS = 180

# Task WAITING pré-vinculada a runner indisponível: desfaz vínculo após esse tempo.
WAITING_UNLINK_AFTER_SECONDS = 5 * 60

# Runner sem heartbeat por mais que isso vira OFFLINE (não mexe nas tasks).
RUNNER_OFFLINE_AFTER_SECONDS = 180

# Limites de concorrência por runner (tasks BACKGROUND simultâneas).
MIN_CONCURRENCY = 1
MAX_CONCURRENCY_CAP = 5

MODE_BACKGROUND = "background"
MODE_FOREGROUND = "foreground"

FINAL_STATUSES = frozenset(
    {
        TaskStatus.FINISHED,
        TaskStatus.ERROR,
        TaskStatus.TIMEOUT,
        TaskStatus.CANCELED,
        TaskStatus.FORCED_STOP,
    }
)

# Estados em que a task ocupa capacidade do runner (WAITING pré-vinculada NÃO ocupa).
EXECUTING_STATUSES = frozenset(
    {
        TaskStatus.READY,
        TaskStatus.RUNNING,
        TaskStatus.STOP_REQUESTED,
    }
)


def normalize_mode(value) -> str:
    """Normaliza o modo de execução do bot; qualquer coisa fora de foreground é background."""
    raw = getattr(value, "value", value)
    text = str(raw or "").strip().lower()
    return MODE_FOREGROUND if text == MODE_FOREGROUND else MODE_BACKGROUND


def as_aware(dt: datetime | None) -> datetime | None:
    """Garante datetime com timezone UTC (SQL Server/sqlite podem devolver naive)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def release_waiting_tasks_of_runner(db, runner, *, reason: str) -> int:
    """Tasks WAITING pré-vinculadas à máquina voltam para a fila (runner_id NULL) com o motivo.

    Usado quando a máquina entra em manutenção: o despachante já não escolhe a máquina para
    tasks novas; isto cuida das que já estavam na fila dela. Nada em execução é tocado."""
    from sqlalchemy import select

    from app.domain.enums import TaskLogLevel, TaskLogSource, TaskStatus
    from app.models.task import Task
    from app.services.task_events import add_task_log

    tasks = list(
        db.execute(
            select(Task)
            .where(Task.runner_id == runner.id)
            .where(Task.status == TaskStatus.WAITING)
            .where(Task.runner_claimed_at.is_(None))
        ).scalars().all()
    )
    label = getattr(runner, "label", None) or getattr(runner, "name", None) or f"#{runner.id}"
    for task in tasks:
        task.runner_id = None
        task.waiting_reason = f"Devolvida à fila: a máquina '{label}' entrou em manutenção."
        task.last_update_at = datetime.now(UTC)
        db.add(task)
        add_task_log(
            db,
            task.id,
            f"Máquina '{label}' entrou em manutenção: task devolvida à fila para outra máquina.",
            level=TaskLogLevel.INFO,
            source=TaskLogSource.DISPATCHER,
            event_code="RUNNER_MAINTENANCE_REQUEUE",
            runner_id=runner.id,
        )
    if tasks:
        db.flush()
    return len(tasks)


def runner_in_maintenance(runner) -> bool:
    """Máquina em manutenção: pelo status (API) ou pela caixa "Modo manutenção" do Runner Config.

    Antes só o status contava e a caixa do painel não fazia nada: a máquina seguia pegando task.
    """
    if runner is None:
        return False
    if str(getattr(runner, "status", "") or "") == "maintenance":
        return True
    config = getattr(runner, "config", None)
    return bool(config is not None and getattr(config, "maintenance_mode", False))
