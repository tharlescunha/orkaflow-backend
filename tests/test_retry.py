"""Retentativa automática por automação (out/2026)."""
import unittest
from datetime import UTC, datetime, timedelta

from app.domain.enums import CalendarType, ExecutionMode, SchedulePolicy, ScheduleStatus, ScheduleType, TaskStatus
from app.models.schedule import Schedule
from app.models.task import Task
from app.models.task_log import TaskLog
from app.models.task_parameter import TaskParameter
from app.services.retry_service import schedule_retry_if_applicable
from app.services.task_service import TaskService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class RetryBase(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner("r1")
        self.auto, self.ver = self.f.automation(runners=[self.runner])
        self.schedule = Schedule(
            name="s", automation_id=self.auto.id, schedule_type=ScheduleType.CALENDAR,
            calendar_type=CalendarType.HOUR, interval_value=1, interval_unit="hours", priority=5,
            policy=SchedulePolicy.CREATE_ALWAYS, status=ScheduleStatus.ACTIVE, active=True, timezone="UTC",
            retry_max=2, retry_delay_seconds=300, retry_on_json=["erro", "timeout"],
        )
        self.db.add(self.schedule)
        self.db.flush()

    def _failed(self, status=TaskStatus.ERROR, **kw):
        kw.setdefault("schedule_id", self.schedule.id)
        task = self.f.task(self.auto, self.ver, status=status, runner=self.runner, **kw)
        self.db.add(TaskParameter(task_id=task.id, parameter_name="parameters_json",
                                  parameter_value='{"filtros": {"ano": 2026}}', is_secret=False))
        self.db.flush()
        return task

    def _children(self, parent):
        return list(self.db.query(Task).filter(Task.parent_task_id == parent.id).all())

    def _logs(self, task):
        return [log.message for log in self.db.query(TaskLog).filter(TaskLog.task_id == task.id).all()]


class RetryTests(RetryBase):
    def test_error_creates_scheduled_retry_with_same_parameters(self):
        task = self._failed()
        new = schedule_retry_if_applicable(self.db, task)
        self.assertIsNotNone(new)
        self.assertEqual(new.execution_mode, ExecutionMode.RETRY)
        self.assertEqual(new.parent_task_id, task.id)
        self.assertEqual(new.retry_count, 1)
        self.assertEqual(new.status, TaskStatus.SCHEDULED)
        self.assertIsNone(new.runner_id)
        self.assertGreater(new.requested_start_at.replace(tzinfo=UTC), datetime.now(UTC) + timedelta(seconds=250))
        params = {p.parameter_name: p.parameter_value for p in self.db.query(TaskParameter).filter_by(task_id=new.id)}
        self.assertIn("filtros", params["parameters_json"])
        self.assertTrue(any("Retentativa automática 1 de 2" in m for m in self._logs(task)))

    def test_exhausts_after_retry_max(self):
        first = self._failed()
        second = self._failed(retry_count=1, parent_task_id=first.id)
        third = schedule_retry_if_applicable(self.db, second)
        self.assertIsNotNone(third)
        self.assertEqual(third.retry_count, 2)
        third.status = TaskStatus.ERROR
        self.db.flush()
        self.assertIsNone(schedule_retry_if_applicable(self.db, third))
        self.assertTrue(any("esgotada" in m for m in self._logs(third)))

    def test_no_retry_when_disabled_or_wrong_status(self):
        self.schedule.retry_max = 0
        self.db.flush()
        self.assertIsNone(schedule_retry_if_applicable(self.db, self._failed()))
        self.schedule.retry_max = 2
        self.db.flush()
        self.assertIsNone(schedule_retry_if_applicable(self.db, self._failed(TaskStatus.CANCELED)))
        self.assertIsNone(schedule_retry_if_applicable(self.db, self._failed(TaskStatus.FORCED_STOP)))
        self.assertIsNone(schedule_retry_if_applicable(self.db, self._failed(TaskStatus.FINISHED)))

    def test_retry_on_filters_timeout(self):
        self.schedule.retry_on_json = ["erro"]
        self.db.flush()
        self.assertIsNone(schedule_retry_if_applicable(self.db, self._failed(TaskStatus.TIMEOUT)))
        self.assertIsNotNone(schedule_retry_if_applicable(self.db, self._failed(TaskStatus.ERROR)))

    def test_no_retry_when_another_task_is_open(self):
        task = self._failed()
        self.f.task(self.auto, self.ver, status=TaskStatus.WAITING)
        self.assertIsNone(schedule_retry_if_applicable(self.db, task))
        self.assertTrue(any("já existe a task" in m for m in self._logs(task)))

    def test_zero_delay_goes_straight_to_waiting(self):
        self.schedule.retry_delay_seconds = 0
        self.db.flush()
        new = schedule_retry_if_applicable(self.db, self._failed())
        self.assertEqual(new.status, TaskStatus.WAITING)
        self.assertIsNone(new.requested_start_at)

    def test_worker_finish_with_error_schedules_retry(self):
        task = self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=self.runner, schedule_id=self.schedule.id)
        WorkerService(self.db).finish_task(task.id, self.f.payload(
            self.runner, status=TaskStatus.ERROR, final_message="falhou", result_json=None,
            items_processed=None, items_failed=None))
        children = self._children(task)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].execution_mode, ExecutionMode.RETRY)

    def test_panel_cancel_does_not_retry(self):
        task = self.f.task(self.auto, self.ver, status=TaskStatus.WAITING)
        TaskService(self.db).cancel_task(task.id)
        self.assertEqual(self._children(task), [])

    def test_manual_task_without_schedule_does_not_retry(self):
        task = self._failed(schedule_id=None)
        self.assertIsNone(schedule_retry_if_applicable(self.db, task))

    def test_schedule_api_exposes_and_validates_retry(self):
        from app.schemas.schedule import ScheduleResponse
        from app.services.schedule_service import ScheduleService

        data = ScheduleResponse.model_validate(self.schedule, from_attributes=True)
        self.assertEqual((data.retry_max, data.retry_delay_seconds, data.retry_on), (2, 300, ["erro", "timeout"]))

        ScheduleService.update(self.db, self.schedule.id, {"retry_max": 3, "retry_on": ["timeout"]})
        self.db.refresh(self.schedule)
        self.assertEqual((self.schedule.retry_max, self.schedule.retry_on_json), (3, ["timeout"]))

        # 5 tentativas x 900 s = 4500 s > intervalo de 1 h: não cabe.
        from app.core.exceptions import ValidationException
        with self.assertRaises(ValidationException):
            ScheduleService.update(self.db, self.schedule.id, {"retry_max": 5, "retry_delay_seconds": 900})
