# app/services/lock_service.py

from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.domain.enums import LockScopeType
from app.models.task import Task
from app.repositories.automation_exclusive_group_repository import (
    AutomationExclusiveGroupRepository,
)
from app.repositories.lock_repository import LockRepository
from app.services.task_rules import (
    EXECUTING_STATUSES,
    TASK_TIMEOUT_MARGIN_SECONDS,
    as_aware,
)


class LockService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LockRepository(db)

    def build_task_lock_key(self, task) -> str:
        return f"automation:{task.automation_id}"

    @staticmethod
    def build_foreground_lock_key(host_name: str | None, runner_id: int) -> str:
        host = (host_name or "").strip().lower()
        return f"foreground:{host}" if host else f"foreground:runner-{runner_id}"

    @staticmethod
    def compute_expires_at(task, now: datetime | None = None) -> datetime:
        """Expiração do lock = agora + timeout da task + margem (o timeout real é do watchdog)."""
        now = now or datetime.now(UTC)
        timeout = int(task.timeout_seconds or 3600)
        return now + timedelta(seconds=timeout + TASK_TIMEOUT_MARGIN_SECONDS)

    def is_key_locked(self, lock_key: str) -> bool:
        """True se existe lock ativo, não expirado e de task ainda aberta para a chave."""
        lock = self.repository.get_active_by_key(lock_key)
        if not lock:
            return False
        return not self._is_stale(lock, datetime.now(UTC))

    def _is_stale(self, lock, now: datetime) -> bool:
        expires_at = as_aware(lock.expires_at)
        if expires_at is not None and expires_at <= now:
            return True
        owner = self.db.get(Task, lock.owner_task_id)
        # Dono inexistente ou já fora de execução: lock órfão.
        return owner is None or owner.status not in EXECUTING_STATUSES

    def _acquire(
        self,
        lock_key: str,
        scope: LockScopeType,
        task,
        runner_id: int | None,
        message: str,
    ):
        now = datetime.now(UTC)

        active_lock = self.repository.get_active_by_key(lock_key)
        if active_lock:
            if active_lock.owner_task_id != task.id and not self._is_stale(active_lock, now):
                raise ValidationException(message)
            self.repository.release(active_lock, now)

        try:
            with self.db.begin_nested():
                return self.repository.create(
                    {
                        "lock_key": lock_key,
                        "scope_type": scope,
                        "owner_task_id": task.id,
                        "runner_id": runner_id,
                        "acquired_at": now,
                        "expires_at": self.compute_expires_at(task, now),
                        "released_at": None,
                        "active": True,
                    }
                )
        except IntegrityError:
            # Índice único filtrado (active=1): outro claim ganhou a corrida.
            raise ValidationException(message)

    def build_task_lock_specs(self, task) -> list[tuple[str, LockScopeType]]:
        """Lock da automação + um lock por grupo de exclusão ativo (recurso de junho/2026)."""
        specs = [(self.build_task_lock_key(task), LockScopeType.AUTOMATION)]
        exclusive_groups = AutomationExclusiveGroupRepository.list_for_automation(
            self.db,
            task.automation_id,
        )

        for group in exclusive_groups:
            if group.active:
                specs.append(
                    (
                        f"exclusive_group:{group.id}",
                        LockScopeType.BUSINESS_RESOURCE,
                    )
                )

        return specs

    def acquire_for_task(self, task, runner_id: int | None = None):
        """Adquire o lock da automação e os de grupos de exclusão, tudo ou nada."""
        created_locks = []
        # Savepoint externo: se qualquer chave estiver ocupada, nada fica pela metade.
        with self.db.begin_nested():
            for lock_key, scope_type in self.build_task_lock_specs(task):
                created_locks.append(
                    self._acquire(
                        lock_key,
                        scope_type,
                        task,
                        runner_id,
                        f"Já existe lock ativo para a chave '{lock_key}'.",
                    )
                )
        return created_locks

    def acquire_foreground_for_task(self, task, runner):
        lock_key = self.build_foreground_lock_key(runner.host_name, runner.id)
        return self._acquire(
            lock_key,
            LockScopeType.EXTERNAL_SYSTEM,
            task,
            runner.id,
            f"Já existe uma task FOREGROUND em execução neste host ('{lock_key}').",
        )

    def renew_task_locks(self, task) -> int:
        """Renova expires_at dos locks da task (atividade/heartbeat de task aberta)."""
        return self.repository.renew_by_task_id(task.id, self.compute_expires_at(task))

    def release_task_locks(self, task_id: int):
        now = datetime.now(UTC)
        return self.repository.release_by_task_id(task_id, now)

    def release_runner_locks(self, runner_id: int):
        now = datetime.now(UTC)
        return self.repository.release_by_runner_id(runner_id, now)

    def cleanup_expired_locks(self):
        now = datetime.now(UTC)
        expired = self.repository.list_active_expired(now)

        for lock in expired:
            self.repository.release(lock, now)

        return expired
