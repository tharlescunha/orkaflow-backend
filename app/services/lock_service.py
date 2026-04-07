# app/services/lock_service.py

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.domain.enums import LockScopeType
from app.repositories.lock_repository import LockRepository


class LockService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LockRepository(db)

    def build_task_lock_key(self, task) -> str:
        return f"automation:{task.automation_id}"

    def acquire_for_task(self, task, runner_id: int | None = None):
        now = datetime.now(UTC)
        lock_key = self.build_task_lock_key(task)

        active_lock = self.repository.get_active_by_key(lock_key)
        if active_lock:
            if active_lock.expires_at and active_lock.expires_at <= now:
                self.repository.release(active_lock, now)
            else:
                raise ValidationException(
                    f"Já existe lock ativo para a chave '{lock_key}'."
                )

        expires_at = None
        if task.timeout_seconds:
            expires_at = now + timedelta(seconds=task.timeout_seconds)

        lock = self.repository.create(
            {
                "lock_key": lock_key,
                "scope_type": LockScopeType.AUTOMATION,
                "owner_task_id": task.id,
                "runner_id": runner_id,
                "acquired_at": now,
                "expires_at": expires_at,
                "released_at": None,
                "active": True,
            }
        )

        return lock

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
    