from collections.abc import Sequence
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, audit_log_id: int) -> AuditLog | None:
        stmt = select(AuditLog).where(AuditLog.id == audit_log_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        entity_name: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        actor_user_id: int | None = None,
    ) -> tuple[Sequence[AuditLog], int]:
        stmt = select(AuditLog)
        count_stmt = select(func.count(AuditLog.id))

        if entity_name is not None:
            stmt = stmt.where(AuditLog.entity_name == entity_name)
            count_stmt = count_stmt.where(AuditLog.entity_name == entity_name)

        if entity_id is not None:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
            count_stmt = count_stmt.where(AuditLog.entity_id == entity_id)

        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
            count_stmt = count_stmt.where(AuditLog.action == action)

        if actor_user_id is not None:
            stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
            count_stmt = count_stmt.where(AuditLog.actor_user_id == actor_user_id)

        stmt = stmt.order_by(AuditLog.id.desc()).offset(skip).limit(limit)

        items = self.db.execute(stmt).scalars().all()
        total = self.db.execute(count_stmt).scalar_one()

        return items, total

    def create(self, data: dict) -> AuditLog:
        audit_log = AuditLog(**data)
        self.db.add(audit_log)
        self.db.flush()
        self.db.refresh(audit_log)
        return audit_log
    