# app/repositories/runner_repository.py

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.runner import Runner
from app.models.runner_config import RunnerConfig


class RunnerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, runner_id: int) -> Runner | None:
        stmt = (
            select(Runner)
            .options(selectinload(Runner.config))
            .where(Runner.id == runner_id)
        )
        return self.db.scalar(stmt)

    def get_by_label(self, label: str) -> Runner | None:
        stmt = select(Runner).where(Runner.label == label)
        return self.db.scalar(stmt)
    
    def get_by_name(self, name: str) -> Runner | None:
        stmt = select(Runner).where(Runner.name == name)
        return self.db.scalar(stmt)

    def get_by_machine_uuid(self, machine_uuid: str) -> Runner | None:
        stmt = select(Runner).where(Runner.uuid == machine_uuid)
        return self.db.scalar(stmt)

    def get_by_uuid(self, uuid: str) -> Runner | None:
        stmt = select(Runner).where(Runner.uuid == uuid)
        return self.db.scalar(stmt)

    def list_all(
        self,
        skip: int = 0,
        limit: int = 100,
        enabled: bool | None = None,
        status: str | None = None,
    ) -> list[Runner]:
        stmt = select(Runner).options(selectinload(Runner.config)).order_by(Runner.name)

        if enabled is not None:
            stmt = stmt.where(Runner.enabled == enabled)

        if status is not None:
            stmt = stmt.where(Runner.status == status)

        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def create(self, **data) -> Runner:
        runner = Runner(**data)
        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)
        return runner

    def update(self, runner: Runner, **data) -> Runner:
        for field, value in data.items():
            if value is not None:
                setattr(runner, field, value)

        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)
        return runner

    def disable(self, runner: Runner) -> Runner:
        runner.enabled = False
        self.db.add(runner)
        self.db.commit()
        self.db.refresh(runner)
        return runner

    def create_config(self, runner_id: int, **data) -> RunnerConfig:
        config = RunnerConfig(runner_id=runner_id, **data)
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def get_config(self, runner_id: int) -> RunnerConfig | None:
        stmt = select(RunnerConfig).where(RunnerConfig.runner_id == runner_id)
        return self.db.scalar(stmt)

    def update_config(self, config: RunnerConfig, **data) -> RunnerConfig:
        for field, value in data.items():
            if value is not None:
                setattr(config, field, value)

        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config