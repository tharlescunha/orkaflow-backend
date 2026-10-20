"""Testes da integração das melhorias de outubro/2026 sobre o código de junho/2026 (sqlite em memória)."""
import json
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.core.exceptions import ValidationException
from app.domain.enums import (
    CalendarType,
    RunnerStatus,
    SchedulePolicy,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from app.models.automation_success_trigger import AutomationSuccessTrigger
from app.models.bot_version import BotVersion
from app.models.schedule import Schedule
from app.models.task import Task
from app.services.scheduler_engine_service import SchedulerEngineService
from app.services.task_service import TaskService
from app.services.watchdog_service import WatchdogService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class SuccessTriggerTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.svc = WorkerService(self.f.db)
        self.r = self.f.runner()
        self.src, self.src_v = self.f.automation(runners=[self.r])
        self.dst, self.dst_v = self.f.automation(runners=[self.r])
        self.f.db.add(
            AutomationSuccessTrigger(
                source_automation_id=self.src.id, target_automation_id=self.dst.id, active=True
            )
        )
        self.f.db.flush()

    def _children(self, parent):
        return list(
            self.f.db.execute(select(Task).where(Task.parent_task_id == parent.id)).scalars().all()
        )

    def _finish_payload(self, status, **kw):
        base = dict(
            status=status,
            final_message=None,
            items_processed=None,
            items_failed=None,
            result_json=None,
        )
        base.update(kw)
        return self.f.payload(self.r, **base)

    def test_trigger_fires_after_finish_task(self):
        t = self.f.task(self.src, self.src_v)
        self.svc.claim_task(t.id, self.f.payload(self.r))
        self.svc.finish_task(t.id, self._finish_payload(TaskStatus.FINISHED, final_message="ok"))
        children = self._children(t)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].automation_id, self.dst.id)
        self.assertEqual(children[0].status, TaskStatus.WAITING)

    def test_trigger_fires_once_and_not_on_error(self):
        t = self.f.task(self.src, self.src_v)
        self.svc.claim_task(t.id, self.f.payload(self.r))
        payload = self._finish_payload(TaskStatus.FINISHED, result_json='{"x": 1}')
        self.svc.finish_task(t.id, payload)
        self.svc.finish_task(t.id, payload)  # repetido: estado final ignorado
        self.assertEqual(len(self._children(t)), 1)
        self.f.db.refresh(t)
        self.assertEqual(t.result_json, '{"x": 1}')

        a2, v2 = self.f.automation(runners=[self.r])
        self.f.db.add(
            AutomationSuccessTrigger(
                source_automation_id=a2.id, target_automation_id=self.dst.id, active=True
            )
        )
        self.f.db.flush()
        t2 = self.f.task(a2, v2)
        self.svc.claim_task(t2.id, self.f.payload(self.r))
        self.svc.finish_task(t2.id, self._finish_payload(TaskStatus.ERROR, final_message="falhou"))
        self.assertEqual(len(self._children(t2)), 0)

    def test_trigger_fires_via_update_task_status(self):
        t = self.f.task(self.src, self.src_v)
        self.svc.claim_task(t.id, self.f.payload(self.r))
        self.svc.update_task_status(t.id, self._finish_payload(TaskStatus.FINISHED, items_processed=3))
        self.assertEqual(len(self._children(t)), 1)

    def test_trigger_fires_via_panel_status_update(self):
        from app.schemas.task import TaskStatusUpdate

        t = self.f.task(self.src, self.src_v, TaskStatus.RUNNING, runner=self.r)
        TaskService(self.f.db).update_status(t.id, TaskStatusUpdate(status=TaskStatus.FINISHED))
        self.assertEqual(len(self._children(t)), 1)


class ConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.svc = WorkerService(self.f.db)

    def test_n_background_plus_one_foreground(self):
        r = self.f.runner(max_concurrency=2)
        bg = [self.f.automation("background", runners=[r]) for _ in range(3)]
        fg = [self.f.automation("foreground", runners=[r]) for _ in range(2)]
        tb = [self.f.task(a, v) for a, v in bg]
        tf = [self.f.task(a, v) for a, v in fg]

        self.svc.claim_task(tb[0].id, self.f.payload(r))
        self.svc.claim_task(tb[1].id, self.f.payload(r))
        with self.assertRaises(ValidationException):
            self.svc.claim_task(tb[2].id, self.f.payload(r))  # N=2 atingido

        self.svc.claim_task(tf[0].id, self.f.payload(r))  # foreground roda junto
        with self.assertRaises(ValidationException):
            self.svc.claim_task(tf[1].id, self.f.payload(r))  # no máx. 1 FG

        self.f.db.refresh(r)
        self.assertEqual(r.status, RunnerStatus.BUSY)

    def test_second_task_same_automation_blocked_by_june_rule(self):
        r = self.f.runner(max_concurrency=3)
        auto, ver = self.f.automation(runners=[r])
        t1 = self.f.task(auto, ver)
        self.svc.claim_task(t1.id, self.f.payload(r))
        t2 = self.f.task(auto, ver)
        with self.assertRaises(ValidationException):
            self.svc.claim_task(t2.id, self.f.payload(r))


class WatchdogJuneTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.wd = WatchdogService(self.f.db)

    def test_full_watchdog_cycle_never_sets_stop_requested(self):
        old = datetime.now(UTC) - timedelta(hours=2)
        r = self.f.runner(status=RunnerStatus.BUSY)
        r.last_heartbeat = old
        auto, ver = self.f.automation(runners=[r])
        t = self.f.task(
            auto, ver, TaskStatus.RUNNING, runner=r, started_at=datetime.now(UTC), last_update_at=old
        )
        self.wd.mark_offline_runners()
        self.wd.release_expired_locks()
        self.wd.requeue_stale_waiting_assignments()
        self.wd.mark_timed_out_tasks()
        self.wd.recover_orphan_tasks()
        self.wd.fail_tasks_without_online_workers()
        self.f.db.refresh(t)
        self.assertEqual(t.status, TaskStatus.RUNNING)
        self.assertFalse(t.stop_requested)

    def test_requeue_stale_waiting_assignment_june_feature(self):
        old = datetime.now(UTC) - timedelta(minutes=10)
        r = self.f.runner()
        auto, ver = self.f.automation(runners=[r])
        t = self.f.task(auto, ver, TaskStatus.WAITING, runner=r, last_update_at=old)
        self.assertEqual(self.wd.requeue_stale_waiting_assignments(), 1)
        self.f.db.refresh(t)
        self.assertIsNone(t.runner_id)
        self.assertEqual(t.status, TaskStatus.WAITING)


class SchedulerJuneTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def _schedule(self, auto, **kw):
        s = Schedule(
            name="s",
            automation_id=auto.id,
            schedule_type=ScheduleType.CALENDAR,
            calendar_type=CalendarType.ONCE,
            policy=SchedulePolicy.CREATE_ALWAYS,
            status=ScheduleStatus.ACTIVE,
            active=True,
            timezone="UTC",
            next_run_at=datetime.now(UTC) - timedelta(minutes=1),
            start_at=datetime.now(UTC) - timedelta(minutes=2),
            **kw,
        )
        self.f.db.add(s)
        self.f.db.flush()
        return s

    def test_creates_task_with_runtime_parameters_and_inactivates_once(self):
        r = self.f.runner()
        auto, ver = self.f.automation(runners=[r])
        auto.default_runtime_parameters_json = {"a": 1}
        self.f.db.flush()
        s = self._schedule(auto)
        self.assertEqual(SchedulerEngineService(self.f.db).process_schedules(), 1)
        task = self.f.db.execute(select(Task).where(Task.schedule_id == s.id)).scalars().one()
        names = {p.parameter_name: p.parameter_value for p in task.parameters}
        self.assertEqual(json.loads(names["runtime_parameters_json"]), {"a": 1})
        self.f.db.refresh(s)
        self.assertEqual(s.status, ScheduleStatus.INACTIVE)

    def test_open_task_keeps_schedule_active_and_retries(self):
        r = self.f.runner()
        auto, ver = self.f.automation(runners=[r])
        self.f.task(auto, ver, TaskStatus.RUNNING, runner=r)
        s = self._schedule(auto)
        before = s.next_run_at
        self.assertEqual(SchedulerEngineService(self.f.db).process_schedules(), 0)
        self.f.db.refresh(s)
        self.assertEqual(s.status, ScheduleStatus.ACTIVE)
        self.assertTrue(s.active)
        self.assertEqual(s.next_run_at.replace(tzinfo=None), before.replace(tzinfo=None))
        self.assertIn("aberta", s.last_skipped_reason)

    def test_inactive_automation_never_sets_schedule_error(self):
        r = self.f.runner()
        auto, ver = self.f.automation(runners=[r])
        auto.active = False
        self.f.db.flush()
        s = self._schedule(auto)
        SchedulerEngineService(self.f.db).process_schedules()
        self.f.db.refresh(s)
        self.assertEqual(s.status, ScheduleStatus.ACTIVE)
        self.assertIsNotNone(s.last_skipped_reason)


class BotVersionTests(unittest.TestCase):
    def test_sync_uses_active_version_and_bot_auto_update(self):
        f = Fixture()
        r = f.runner()
        auto, v1 = f.automation(runners=[r])
        v1.is_active = True
        bot = auto.bot
        bot.auto_update = True
        v2 = BotVersion(
            bot_id=bot.id, storage_type="git", version="2", is_active=False, created_by=f.user.id
        )
        f.db.add(v2)
        f.db.flush()

        out = WorkerService(f.db).sync_runner(
            SimpleNamespace(uuid=r.uuid, token=f.token, host_name=None, ip=None)
        )
        info = out.bots[0]
        self.assertEqual(info["bot_version_id"], v1.id)
        self.assertTrue(info["auto_update"])
        self.assertEqual(info["execution_mode"], "background")


if __name__ == "__main__":
    unittest.main()
