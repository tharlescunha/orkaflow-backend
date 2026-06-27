from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.automation_success_trigger import AutomationSuccessTrigger


class AutomationSuccessTriggerRepository:
    @staticmethod
    def list_for_source(
        db: Session,
        source_automation_id: int,
        *,
        active: bool | None = None,
    ) -> Sequence[AutomationSuccessTrigger]:
        stmt = (
            select(AutomationSuccessTrigger)
            .options(selectinload(AutomationSuccessTrigger.target_automation))
            .where(AutomationSuccessTrigger.source_automation_id == source_automation_id)
            .order_by(
                AutomationSuccessTrigger.priority_override.desc(),
                AutomationSuccessTrigger.id.asc(),
            )
        )

        if active is not None:
            stmt = stmt.where(AutomationSuccessTrigger.active == active)

        return db.execute(stmt).scalars().all()

    @staticmethod
    def replace_for_source(
        db: Session,
        source_automation_id: int,
        target_automation_ids: list[int],
    ) -> None:
        current_stmt = select(AutomationSuccessTrigger).where(
            AutomationSuccessTrigger.source_automation_id == source_automation_id
        )
        current = list(db.execute(current_stmt).scalars().all())
        current_ids = {item.target_automation_id for item in current}
        desired_ids = set(target_automation_ids)

        for item in current:
            if item.target_automation_id not in desired_ids:
                db.delete(item)
            elif not item.active:
                item.active = True
                db.add(item)

        for target_automation_id in desired_ids - current_ids:
            db.add(
                AutomationSuccessTrigger(
                    source_automation_id=source_automation_id,
                    target_automation_id=target_automation_id,
                    inherit_parent_parameters=True,
                    active=True,
                )
            )

        db.flush()
