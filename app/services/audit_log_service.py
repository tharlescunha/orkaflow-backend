import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.repositories.audit_log_repository import AuditLogRepository


class AuditLogService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AuditLogRepository(db)

    def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        entity_name: str | None = None,
        entity_id: int | None = None,
        action: str | None = None,
        actor_user_id: int | None = None,
    ):
        return self.repo.list_all(
            skip=skip,
            limit=limit,
            entity_name=entity_name,
            entity_id=entity_id,
            action=action,
            actor_user_id=actor_user_id,
        )

    def register(
        self,
        *,
        entity_name: str,
        action: str,
        entity_id: int | None = None,
        actor_user_id: int | None = None,
        description: str | None = None,
        metadata: dict | None = None,
    ):
        payload = {
            "entity_name": entity_name,
            "entity_id": entity_id,
            "action": action,
            "actor_user_id": actor_user_id,
            "description": description,
            "metadata_json": json.dumps(metadata, ensure_ascii=False) if metadata else None,
            "created_at": datetime.now(UTC),
        }
        return self.repo.create(payload)
    