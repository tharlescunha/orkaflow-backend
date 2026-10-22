from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.runner_log_line import RunnerLogLine


class RunnerLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def add_many(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        self.db.add_all([RunnerLogLine(**row) for row in rows])
        self.db.commit()
        return len(rows)

    def list_lines(
        self,
        runner_id: int,
        after_id: int | None = None,
        limit: int = 300,
        source: str | None = None,
        task_id: int | None = None,
        level: str | None = None,
        search: str | None = None,
    ) -> list[RunnerLogLine]:
        """Sem after_id: as últimas `limit` linhas. Com after_id: as seguintes. Sempre em ordem crescente."""
        stmt = select(RunnerLogLine).where(RunnerLogLine.runner_id == runner_id)

        if source:
            stmt = stmt.where(RunnerLogLine.source == source)
        if task_id is not None:
            stmt = stmt.where(RunnerLogLine.task_id == task_id)
        if level:
            stmt = stmt.where(RunnerLogLine.level == level)
        if search:
            stmt = stmt.where(RunnerLogLine.message.contains(search, autoescape=True))

        if after_id is not None:
            stmt = stmt.where(RunnerLogLine.id > after_id).order_by(RunnerLogLine.id.asc()).limit(limit)
            return list(self.db.scalars(stmt).all())

        stmt = stmt.order_by(RunnerLogLine.id.desc()).limit(limit)
        return list(reversed(self.db.scalars(stmt).all()))

    def last_id(self, runner_id: int) -> int | None:
        stmt = (
            select(RunnerLogLine.id)
            .where(RunnerLogLine.runner_id == runner_id)
            .order_by(RunnerLogLine.id.desc())
            .limit(1)
        )
        return self.db.scalar(stmt)

    def delete_older_than(self, cutoff: datetime, batch_size: int = 5000) -> int:
        """Apaga em lotes para não segurar lock grande no SQL Server."""
        ids = select(RunnerLogLine.id).where(RunnerLogLine.received_at < cutoff).limit(batch_size)
        result = self.db.execute(
            delete(RunnerLogLine).where(RunnerLogLine.id.in_(ids)).execution_options(synchronize_session=False)
        )
        self.db.commit()
        return int(result.rowcount or 0)
