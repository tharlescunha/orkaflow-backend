from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.domain.enums import LockScopeType
from app.repositories.automation_exclusive_group_repository import (
    AutomationExclusiveGroupRepository,
)
from app.repositories.lock_repository import LockRepository


class LockService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = LockRepository(db)

    def build_task_lock_key(self, task) -> str:
        return f"automation:{task.automation_id}"

    def build_task_lock_specs(self, task) -> list[tuple[str, LockScopeType]]:
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
        now = datetime.now(UTC)

        expires_at = None
        if task.timeout_seconds:
            expires_at = now + timedelta(seconds=task.timeout_seconds)

        created_locks = []
        for lock_key, scope_type in self.build_task_lock_specs(task):
            active_lock = self.repository.get_active_by_key(lock_key)
            if active_lock:
                if active_lock.expires_at and active_lock.expires_at <= now:
                    self.repository.release(active_lock, now)
                else:
                    raise ValidationException(
                        f"Ja existe lock ativo para a chave '{lock_key}'."
                    )

            created_locks.append(
                self.repository.create(
                    {
                        "lock_key": lock_key,
                        "scope_type": scope_type,
                        "owner_task_id": task.id,
                        "runner_id": runner_id,
                        "acquired_at": now,
                        "expires_at": expires_at,
                        "released_at": None,
                        "active": True,
                    }
                )
            )

        return created_locks

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
