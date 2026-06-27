from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lock import Lock


class LockRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, lock_id: int) -> Lock | None:
        stmt = select(Lock).where(Lock.id == lock_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_by_key(self, lock_key: str) -> Lock | None:
        stmt = (
            select(Lock)
            .with_hint(Lock, "WITH (UPDLOCK, ROWLOCK, HOLDLOCK)", "mssql")
            .where(Lock.lock_key == lock_key)
            .where(Lock.active == True)
            .where(Lock.released_at.is_(None))
            .order_by(Lock.id.desc())
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active_expired(self, now: datetime) -> list[Lock]:
        stmt = (
            select(Lock)
            .where(Lock.active == True)
            .where(Lock.released_at.is_(None))
            .where(Lock.expires_at.is_not(None))
            .where(Lock.expires_at <= now)
        )
        return list(self.db.execute(stmt).scalars().all())

    def create(self, data: dict) -> Lock:
        lock = Lock(**data)
        self.db.add(lock)
        self.db.flush()
        self.db.refresh(lock)
        return lock

    def update(self, lock: Lock, data: dict) -> Lock:
        for field, value in data.items():
            setattr(lock, field, value)

        self.db.add(lock)
        self.db.flush()
        self.db.refresh(lock)
        return lock

    def release(self, lock: Lock, released_at: datetime) -> Lock:
        return self.update(
            lock,
            {
                "active": False,
                "released_at": released_at,
            },
        )

    def release_by_task_id(self, task_id: int, released_at: datetime) -> list[Lock]:
        stmt = (
            select(Lock)
            .where(Lock.owner_task_id == task_id)
            .where(Lock.active == True)
            .where(Lock.released_at.is_(None))
        )
        locks = list(self.db.execute(stmt).scalars().all())

        for lock in locks:
            self.release(lock, released_at)

        return locks

    def release_by_runner_id(self, runner_id: int, released_at: datetime) -> list[Lock]:
        """
        Libera todos os locks associados a um runner offline.

        Proteções aplicadas:
        - somente locks ativos
        - somente locks ainda não liberados
        - somente locks com owner_task_id preenchido
        """

        stmt = (
            select(Lock)
            .where(Lock.runner_id == runner_id)
            .where(Lock.active == True)
            .where(Lock.released_at.is_(None))
            .where(Lock.owner_task_id.is_not(None))
        )

        locks = list(self.db.execute(stmt).scalars().all())

        for lock in locks:
            self.release(lock, released_at)

        return locks
    
