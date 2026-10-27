"""Calendários (out/2026): dias úteis, feriados, janelas proibidas; pular ou adiar no agendador; Health."""
import unittest
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.exceptions import ConflictException, ValidationException
from app.domain.enums import CalendarType, SchedulePolicy, ScheduleStatus, ScheduleType, TaskStatus
from app.models.calendar import Calendar
from app.models.schedule import Schedule
from app.models.task import Task
from app.services import calendar_service as svc
from app.services.scheduler_engine_service import SchedulerEngineService

from tests.test_concurrency_watchdog import Fixture

BRT = ZoneInfo("America/Sao_Paulo")


def _cal(**kw) -> Calendar:
    c = Calendar(name=kw.pop("name", "ALZ"), active=True)
    c.weekdays_json = kw.pop("weekdays", [0, 1, 2, 3, 4])
    c.holidays_json = kw.pop("holidays", [])
    c.blackouts_json = kw.pop("blackouts", [])
    return c


class PureRulesTests(unittest.TestCase):
    def test_holidays_brazil_2026(self):
        days = svc.brazilian_national_holidays(2026)
        self.assertIn("2026-04-03", days)  # Sexta-feira Santa
        self.assertIn("2026-02-17", days)  # terça de Carnaval
        self.assertIn("2026-06-04", days)  # Corpus Christi
        self.assertIn("2026-11-20", days)

    def test_weekend_and_holiday_are_blocked_and_defer_to_same_time(self):
        cal = _cal(holidays=["2026-12-25"])
        friday_holiday = datetime(2026, 12, 25, 6, 0, tzinfo=BRT)
        result = svc.check_at(cal, friday_holiday)
        self.assertFalse(result.allowed)
        self.assertIn("feriado", result.reason)
        self.assertEqual(result.next_allowed_at, datetime(2026, 12, 28, 6, 0, tzinfo=BRT))  # segunda, 06:00

        saturday = datetime(2026, 10, 31, 9, 30, tzinfo=BRT)
        self.assertEqual(svc.check_at(cal, saturday).next_allowed_at, datetime(2026, 11, 2, 9, 30, tzinfo=BRT))

    def test_blackout_window_defers_to_window_end(self):
        cal = _cal(blackouts=[{"label": "Backup", "start": "00:00", "end": "02:00", "weekdays": []}])
        at = datetime(2026, 10, 27, 1, 0, tzinfo=BRT)  # terça 01:00
        result = svc.check_at(cal, at)
        self.assertFalse(result.allowed)
        self.assertIn("Backup", result.reason)
        self.assertEqual(result.next_allowed_at, datetime(2026, 10, 27, 2, 0, tzinfo=BRT))
        self.assertTrue(svc.check_at(cal, datetime(2026, 10, 27, 2, 0, tzinfo=BRT)).allowed)

    def test_blackout_only_on_some_weekdays(self):
        cal = _cal(weekdays=list(range(7)), blackouts=[{"label": "Fechamento", "start": "08:00", "end": "12:00", "weekdays": [0]}])
        self.assertFalse(svc.check_at(cal, datetime(2026, 10, 26, 9, 0, tzinfo=BRT)).allowed)  # segunda
        self.assertTrue(svc.check_at(cal, datetime(2026, 10, 27, 9, 0, tzinfo=BRT)).allowed)  # terça


class CrudTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db

    def test_create_validate_import_and_delete_in_use(self):
        cal = svc.create_calendar(self.db, {"name": "ALZ", "weekdays": [0, 1, 2, 3, 4], "holidays": ["2026-12-25"], "blackouts": []})
        data = svc.to_read(self.db, cal)
        self.assertEqual(data["weekdays_label"], "seg a sex")
        with self.assertRaises(ValidationException):
            svc.create_calendar(self.db, {"name": "x", "weekdays": [], "holidays": [], "blackouts": []})
        with self.assertRaises(ValidationException):
            svc.create_calendar(self.db, {"name": "y", "weekdays": [0], "holidays": ["25/12/2026"], "blackouts": []})
        with self.assertRaises(ConflictException):
            svc.create_calendar(self.db, {"name": "ALZ", "weekdays": [0], "holidays": [], "blackouts": []})

        cal = svc.import_holidays(self.db, cal.id, 2026)
        self.assertIn("2026-04-03", svc.calendar_holidays(cal))
        self.assertIn("2026-12-25", svc.calendar_holidays(cal))

        runner = self.f.runner("r1")
        auto, _ = self.f.automation(runners=[runner])
        self.db.add(Schedule(name="s", automation_id=auto.id, schedule_type=ScheduleType.CALENDAR,
                             calendar_type=CalendarType.DAY, interval_value=1, interval_unit="days", priority=5,
                             policy=SchedulePolicy.CREATE_ALWAYS, status=ScheduleStatus.ACTIVE, active=True,
                             timezone="America/Sao_Paulo", calendar_id=cal.id))
        self.db.flush()
        with self.assertRaises(ConflictException):
            svc.delete_calendar(self.db, cal.id)


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner("r1")
        self.auto, self.ver = self.f.automation(runners=[self.runner])
        self.cal = _cal(holidays=["2026-12-25"])
        self.db.add(self.cal)
        self.db.flush()

    def _schedule(self, policy="defer"):
        s = Schedule(
            name="s", automation_id=self.auto.id, schedule_type=ScheduleType.CALENDAR,
            calendar_type=CalendarType.DAY, interval_value=1, interval_unit="days", priority=5,
            policy=SchedulePolicy.CREATE_ALWAYS, status=ScheduleStatus.ACTIVE, active=True,
            timezone="America/Sao_Paulo", calendar_id=self.cal.id, calendar_policy=policy,
            next_run_at=datetime.now(UTC) - timedelta(minutes=1), start_at=datetime.now(UTC) - timedelta(minutes=2),
        )
        self.db.add(s)
        self.db.flush()
        return s

    def test_resolve_skip_and_defer(self):
        holiday_utc = datetime(2026, 12, 25, 9, 0, tzinfo=UTC)  # 06:00 em Brasília
        skip = self._schedule("skip")
        decision, when, reason = svc.resolve_for_schedule(skip, holiday_utc)
        self.assertEqual(decision, "skip")
        self.assertIn("feriado", reason)

        defer = self._schedule("defer")
        defer.name = "d"
        decision, when, reason = svc.resolve_for_schedule(defer, holiday_utc)
        self.assertEqual(decision, "defer")
        self.assertEqual(when, datetime(2026, 12, 28, 9, 0, tzinfo=UTC))

        ok, when, _ = svc.resolve_for_schedule(defer, datetime(2026, 12, 23, 9, 0, tzinfo=UTC))
        self.assertEqual((ok, when), ("ok", datetime(2026, 12, 23, 9, 0, tzinfo=UTC)))

    def test_engine_skips_with_reason_on_holiday(self):
        schedule = self._schedule("skip")
        today_local = datetime.now(BRT).date()
        self.cal.holidays_json = [today_local.isoformat()]
        self.db.flush()
        SchedulerEngineService(self.db).process_schedules()
        self.db.refresh(schedule)
        tasks = self.db.query(Task).filter(Task.schedule_id == schedule.id).all()
        self.assertEqual(tasks, [])
        self.assertIn("Calendário", schedule.last_skipped_reason or "")

    def test_engine_defers_to_next_allowed_day(self):
        schedule = self._schedule("defer")
        today_local = datetime.now(BRT).date()
        self.cal.holidays_json = [today_local.isoformat()]
        self.cal.weekdays_json = list(range(7))
        self.db.flush()
        SchedulerEngineService(self.db).process_schedules()
        tasks = self.db.query(Task).filter(Task.schedule_id == schedule.id).all()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].status, TaskStatus.WAITING)
        requested = tasks[0].requested_start_at
        requested = requested if requested.tzinfo else requested.replace(tzinfo=UTC)
        self.assertEqual(requested.astimezone(BRT).date(), today_local + timedelta(days=1))

    def test_health_not_overdue_on_holiday(self):
        from app.services.automation_health_service import AutomationHealthService

        schedule = self._schedule("defer")
        self.cal.holidays_json = [datetime.now(BRT).date().isoformat()]
        self.db.flush()
        old_task = self.f.task(self.auto, self.ver, status=TaskStatus.FINISHED, runner=self.runner,
                               finished_at=datetime.now(UTC) - timedelta(days=3))
        window = AutomationHealthService._calculate_expected_window(schedule=schedule, task=old_task, now_utc=datetime.now(UTC))
        self.assertFalse(window.is_overdue)
