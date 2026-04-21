from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.access_control import Permission


class PermissionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, permission_id: int) -> Permission | None:
        stmt = select(Permission).where(Permission.id == permission_id)
        return self.db.scalar(stmt)

    def get_by_module_action(self, module: str, action: str) -> Permission | None:
        stmt = select(Permission).where(
            Permission.module == module,
            Permission.action == action,
        )
        return self.db.scalar(stmt)

    def list_all(self) -> list[Permission]:
        stmt = select(Permission).order_by(Permission.module, Permission.action)
        return list(self.db.scalars(stmt).all())

    def create(self, module: str, action: str, description: str | None = None) -> Permission:
        permission = Permission(
            module=module,
            action=action,
            description=description,
        )

        self.db.add(permission)
        self.db.commit()
        self.db.refresh(permission)
        return permission

    def get_or_create(self, module: str, action: str, description: str | None = None) -> Permission:
        existing = self.get_by_module_action(module, action)

        if existing:
            return existing

        return self.create(module, action, description)
    