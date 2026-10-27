from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.automation_exclusive_group import (
    AutomationExclusiveGroup,
    AutomationExclusiveGroupMember,
)


class AutomationExclusiveGroupRepository:
    @staticmethod
    def list(db: Session, *, active: bool | None = None) -> Sequence[AutomationExclusiveGroup]:
        stmt = (
            select(AutomationExclusiveGroup)
            .options(selectinload(AutomationExclusiveGroup.automation_links))
            .order_by(AutomationExclusiveGroup.name.asc())
        )

        if active is not None:
            stmt = stmt.where(AutomationExclusiveGroup.active == active)

        return db.execute(stmt).scalars().all()

    @staticmethod
    def get_by_id(db: Session, group_id: int) -> AutomationExclusiveGroup | None:
        stmt = (
            select(AutomationExclusiveGroup)
            .options(selectinload(AutomationExclusiveGroup.automation_links))
            .where(AutomationExclusiveGroup.id == group_id)
        )
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_name(db: Session, name: str) -> AutomationExclusiveGroup | None:
        stmt = select(AutomationExclusiveGroup).where(AutomationExclusiveGroup.name == name)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def create(db: Session, data: dict) -> AutomationExclusiveGroup:
        group = AutomationExclusiveGroup(**data)
        db.add(group)
        db.commit()
        db.refresh(group)
        return group

    @staticmethod
    def replace_members_for_group(
        db: Session,
        group_id: int,
        automation_ids: list[int],
    ) -> None:
        """Deixa o grupo exatamente com essas automações (lado do grupo; o inverso de replace_for_automation)."""
        current_stmt = select(AutomationExclusiveGroupMember).where(
            AutomationExclusiveGroupMember.group_id == group_id
        )
        current = list(db.execute(current_stmt).scalars().all())
        current_ids = {item.automation_id for item in current}
        desired_ids = set(automation_ids)

        for item in current:
            if item.automation_id not in desired_ids:
                db.delete(item)

        for automation_id in desired_ids - current_ids:
            db.add(AutomationExclusiveGroupMember(group_id=group_id, automation_id=automation_id))

        db.flush()
        # O grupo já carregado na sessão guarda a lista antiga de vínculos: força recarregar.
        group = db.get(AutomationExclusiveGroup, group_id)
        if group is not None:
            db.expire(group, ["automation_links"])

    @staticmethod
    def delete(db: Session, group: AutomationExclusiveGroup) -> None:
        db.delete(group)
        db.commit()

    @staticmethod
    def list_for_automation(
        db: Session,
        automation_id: int,
    ) -> Sequence[AutomationExclusiveGroup]:
        stmt = (
            select(AutomationExclusiveGroup)
            .join(
                AutomationExclusiveGroupMember,
                AutomationExclusiveGroupMember.group_id == AutomationExclusiveGroup.id,
            )
            .where(AutomationExclusiveGroupMember.automation_id == automation_id)
            .order_by(AutomationExclusiveGroup.name.asc())
        )
        return db.execute(stmt).scalars().all()

    @staticmethod
    def replace_for_automation(
        db: Session,
        automation_id: int,
        group_ids: list[int],
    ) -> None:
        current_stmt = select(AutomationExclusiveGroupMember).where(
            AutomationExclusiveGroupMember.automation_id == automation_id
        )
        current = list(db.execute(current_stmt).scalars().all())
        current_ids = {item.group_id for item in current}
        desired_ids = set(group_ids)

        for item in current:
            if item.group_id not in desired_ids:
                db.delete(item)

        for group_id in desired_ids - current_ids:
            db.add(
                AutomationExclusiveGroupMember(
                    group_id=group_id,
                    automation_id=automation_id,
                )
            )

        db.flush()
