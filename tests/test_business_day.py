"""Agendamento "no N-ésimo dia útil do mês às HH:MM" (out/2026)."""
import unittest
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.exceptions import ValidationException
from app.domain.enums import CalendarType, SchedulePolicy, ScheduleStatus, ScheduleType, TaskStatus
from app.models.calendar import Calendar
from app.models.schedule import Schedule
from app.models.task import Task
from app.services import calendar_service as svc
from app.services.schedule_service import ScheduleService
from app.services.scheduler_engine_service import SchedulerEngineService

from tests.test_concurrency_watchdog import Fixture

BRT = ZoneInfo("America/Sao_Paulo")


class NthBusinessDayTests(unittest.TestCase):
    def test_without_calendar_counts_monday_to_friday(self):
        # Outubro/2026 começa numa quinta: 1º dia útil = 01/10, 3º = 05/10 (segunda).
        self.assertEqual(svc.nth_business_day(None, 2026, 10, 1).isoformat(), "2026-10-01")
        self.assertEqual(svc.nth_business_day(None, 2026, 10, 3).isoformat(), "2026-10-05")

    def test_with_calendar_skips_holidays(self):
        cal = Calendar(name="x", active=True)
        cal.weekdays_json = [0, 1, 2, 3, 4]
        cal.holidays_json = ["2026-10-01", "2026-10-02"]
        cal.blackouts_json = []
        # 01 e 02 (qui, sex) são feriados: 1º dia útil vira 05/10.
        self.assertEqual(svc.nth_business_day(cal, 2026, 10, 1).isoformat(), "2026-10-05")
        self.assertIsNone(svc.nth_business_day(cal, 2026, 10, 23))

    def test_next_occurrence_rolls_to_next_month(self):
        after = datetime(2026, 10, 6, 9, 0, tzinfo=BRT)  # já passou do 3º dia útil (05/10 08:00)
        nxt = svc.next_business_day_occurrence(None, 3, "08:00", after)
        self.assertEqual(nxt, datetime(2026, 11, 4, 8, 0, tzinfo=BRT))  # nov/2026: 02 (seg) feriado? não: sem calendário conta seg a sex -> 02, 03, 04


class ServiceAndEngineTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner("r1")
        self.auto, self.ver = self.f.automation(runners=[self.runner])

    def _create(self, **kw):
        data = dict(
            name="dia util", automation_id=self.auto.id, priority=5, schedule_type=ScheduleType.CALENDAR,
            calendar_type=CalendarType.DAY, policy=SchedulePolicy.CREATE_ALWAYS, timezone="America/Sao_Paulo",
            active=True, use_default_runtime_parameters=True, runtime_parameters_json=None,
            interval_value=5, interval_unit="days", business_day_of_month=3, time_of_day="08:00",
            retry_max=0, retry_delay_seconds=300, retry_on=["erro", "timeout"], calendar_id=None, calendar_policy="defer",
        )
        data.update(kw)
        return ScheduleService.create(self.db, data)

    def test_create_normalizes_to_monthly_and_requires_time(self):
        schedule = self._create()
        self.assertEqual(schedule.calendar_type, CalendarType.MONTH)
        self.assertEqual((schedule.interval_value, schedule.interval_unit), (1, "months"))
        self.assertEqual((schedule.business_day_of_month, schedule.time_of_day), (3, "08:00"))
        self.assertIsNone(schedule.next_run_at)
        with self.assertRaises(ValidationException):
            self._create(name="sem hora", time_of_day=None)
        with self.assertRaises(ValidationException):
            self._create(name="fora", business_day_of_month=40)

    def test_engine_sets_first_occurrence_in_the_future_and_does_not_run_now(self):
        schedule = self._create()
        engine = SchedulerEngineService(self.db)
        engine.process_schedules()
        self.db.refresh(schedule)
        tasks = self.db.query(Task).filter(Task.schedule_id == schedule.id).all()
        self.assertEqual(tasks, [])
        self.assertIsNotNone(schedule.next_run_at)
        nxt = schedule.next_run_at if schedule.next_run_at.tzinfo else schedule.next_run_at.replace(tzinfo=UTC)
        self.assertGreater(nxt, datetime.now(UTC))
        local = nxt.astimezone(BRT)
        self.assertEqual((local.hour, local.minute), (8, 0))
        self.assertEqual(svc.nth_business_day(None, local.year, local.month, 3), local.date())

    def test_engine_creates_task_when_due_and_advances_a_month(self):
        schedule = self._create()
        # Simula a ocorrência vencida: 3º dia útil do mês passado às 08:00 BRT.
        now_local = datetime.now(BRT)
        prev_month = (now_local.replace(day=1) - timedelta(days=1))
        due_day = svc.nth_business_day(None, prev_month.year, prev_month.month, 3)
        due_local = datetime.combine(due_day, datetime.min.time(), tzinfo=BRT).replace(hour=8)
        schedule.next_run_at = due_local.astimezone(UTC)
        schedule.start_at = due_local.astimezone(UTC) - timedelta(days=1)
        self.db.flush()
        SchedulerEngineService(self.db).process_schedules()
        tasks = self.db.query(Task).filter(Task.schedule_id == schedule.id).all()
        self.assertGreaterEqual(len(tasks), 1)
        self.assertEqual(tasks[0].status, TaskStatus.WAITING)
        self.db.refresh(schedule)
        nxt = schedule.next_run_at if schedule.next_run_at.tzinfo else schedule.next_run_at.replace(tzinfo=UTC)
        self.assertGreater(nxt, datetime.now(UTC))
