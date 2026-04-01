from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ExecutionMode, ScheduleStatus
from app.models.schedule import Schedule
from app.services.task_service import TaskService
from app.schemas.task import TaskCreate


class SchedulerService:
    def __init__(self, db: Session):
        self.db = db
        self.task_service = TaskService(db)

    def run(self):
        now = datetime.now(UTC)
        print(f"[Scheduler] ciclo iniciado | now={now.isoformat()}")

        stmt = (
            select(Schedule)
            .where(Schedule.active == True)
            .where(Schedule.status == ScheduleStatus.ACTIVE)
            .where(Schedule.next_run_at != None)
            .where(Schedule.next_run_at <= now)
        )

        schedules = self.db.execute(stmt).scalars().all()
        print(f"[Scheduler] schedules encontrados: {len(schedules)}")

        for schedule in schedules:
            try:
                print(
                    f"[Scheduler] processando schedule id={schedule.id} "
                    f"automation_id={schedule.automation_id} "
                    f"next_run_at={schedule.next_run_at}"
                )
                self._process_schedule(schedule, now)
                print(f"[Scheduler] schedule {schedule.id} processado com sucesso")
            except Exception as exc:
                print(f"[Scheduler] erro schedule {schedule.id}: {exc}")

    def _process_schedule(self, schedule: Schedule, now: datetime):
        if schedule.last_run_at and schedule.last_run_at >= schedule.next_run_at:
            print(
                f"[Scheduler] schedule {schedule.id} ignorado "
                f"(last_run_at >= next_run_at)"
            )
            return

        self._create_task(schedule)

        old_next_run = schedule.next_run_at
        schedule.last_run_at = now
        schedule.next_run_at = self._calculate_next_run(schedule, now)

        self.db.commit()

        print(
            f"[Scheduler] task criada para schedule {schedule.id} | "
            f"old_next_run={old_next_run} new_next_run={schedule.next_run_at}"
        )

    def _create_task(self, schedule: Schedule):
        payload = {
            "automation_id": schedule.automation_id,
            "priority": schedule.priority or 5,
            "requested_start_at": datetime.now(UTC),
            "execution_mode": ExecutionMode.SCHEDULED,
            "parameters": self._build_parameters(schedule),
        }

        print(f"[Scheduler] criando task | payload={payload}")

        task_payload = TaskCreate(**payload)
        task = self.task_service.create_manual_task(task_payload)

        print(f"[Scheduler] task criada com sucesso | task_id={task.id}")

    def _build_parameters(self, schedule: Schedule):
        if not schedule.parameters_json:
            return []

        parameters = []

        for item in schedule.parameters_json:
            parameters.append(
                {
                    "parameter_name": item.get("parameter_name"),
                    "parameter_value": item.get("parameter_value"),
                    "is_secret": item.get("is_secret", False),
                    "resolved_from_credential_item_id": item.get(
                        "resolved_from_credential_item_id"
                    ),
                }
            )

        return parameters

    def _calculate_next_run(self, schedule: Schedule, now: datetime):
        if schedule.interval_value and schedule.interval_unit:
            if schedule.interval_unit == "seconds":
                return now + timedelta(seconds=schedule.interval_value)
            if schedule.interval_unit == "minutes":
                return now + timedelta(minutes=schedule.interval_value)
            if schedule.interval_unit == "hours":
                return now + timedelta(hours=schedule.interval_value)
            if schedule.interval_unit == "days":
                return now + timedelta(days=schedule.interval_value)

        return now + timedelta(minutes=5)
    