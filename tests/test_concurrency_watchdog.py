"""Testes de capacidade por modo, claim atômico e watchdog (sqlite em memória).

Rodar: python -m unittest discover -s tests -v
SQL Server não é exercitado aqui (UPDLOCK/hints, rowcount real, índice filtrado em
produção); sqlite valida a lógica e o índice único filtrado (sqlite_where).
"""
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401  (registra todos os modelos)
from app.core.exceptions import ValidationException
from app.core.security import generate_runner_token, get_runner_token_hash
from app.domain.enums import (
    BotSourceType,
    BotTechnology,
    RunnerStatus,
    TaskLogLevel,
    TaskLogSource,
    TaskStatus,
    UserRole,
)
from app.models.automation import Automation
from app.models.automation_runner import AutomationRunner
from app.models.base import Base
from app.models.bot import Bot
from app.models.bot_version import BotVersion
from app.models.lock import Lock
from app.models.repository import Repository
from app.models.runner import Runner
from app.models.runner_config import RunnerConfig
from app.models.task import Task
from app.models.task_log import TaskLog
from app.models.user import User
from app.services.capacity_service import CapacityService
from app.services.watchdog_service import WatchdogService
from app.services.worker_service import WorkerService


class Fixture:
    def __init__(self):
        engine = create_engine("sqlite://")

        @event.listens_for(engine, "connect")
        def _sqlite_funcs(dbapi_conn, _record):
            # server_default dos modelos usa função do SQL Server.
            dbapi_conn.create_function(
                "sysdatetimeoffset", 0, lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            )

        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine, expire_on_commit=False)()
        db = self.db

        user = User(name="u", login="u", email="u@x", password_hash="x", role=UserRole.ADMIN)
        repo = Repository(name="r")
        db.add_all([user, repo])
        db.flush()
        self.user, self.repo = user, repo
        self.token = generate_runner_token()
        self._n = 0

    def runner(self, name="r1", host="HOST1", max_concurrency=1, status=RunnerStatus.ONLINE):
        r = Runner(
            uuid=f"uuid-{name}",
            name=name,
            host_name=host,
            token_hash=get_runner_token_hash(self.token),
            status=status,
            enabled=True,
            last_heartbeat=datetime.now(UTC),
        )
        self.db.add(r)
        self.db.flush()
        self.db.add(RunnerConfig(runner_id=r.id, max_concurrency=max_concurrency, polling_interval=10))
        self.db.flush()
        return r

    def automation(self, mode="background", runners=()):
        self._n += 1
        bot = Bot(
            name=f"bot{self._n}",
            technology=BotTechnology.PYTHON,
            repository_id=self.repo.id,
            source_type=BotSourceType.MANUAL,
            entrypoint="main.py",
            execution_mode=mode,
        )
        self.db.add(bot)
        self.db.flush()
        version = BotVersion(
            bot_id=bot.id, storage_type="git", version="1", is_active=True, created_by=self.user.id
        )
        auto = Automation(name=f"a{self._n}", bot_id=bot.id, repository_id=self.repo.id)
        self.db.add_all([version, auto])
        self.db.flush()
        for r in runners:
            self.db.add(AutomationRunner(automation_id=auto.id, runner_id=r.id))
        self.db.flush()
        return auto, version

    def task(self, auto, version, status=TaskStatus.WAITING, runner=None, **kw):
        t = Task(
            automation_id=auto.id,
            bot_version_id=version.id,
            runner_id=runner.id if runner else None,
            status=status,
            **kw,
        )
        self.db.add(t)
        self.db.flush()
        return t

    def payload(self, runner, **extra):
        return SimpleNamespace(uuid=runner.uuid, token=self.token, **extra)


class CapacityAndClaimTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.svc = WorkerService(self.f.db)

    def test_background_capacity_follows_max_concurrency(self):
        r = self.f.runner(max_concurrency=2)
        for _ in range(2):
            auto, ver = self.f.automation(runners=[r])
            self.f.task(auto, ver, TaskStatus.RUNNING, runner=r)
        cap = CapacityService(self.f.db)
        self.assertFalse(cap.has_capacity(r, "background"))
        self.assertTrue(cap.has_capacity(r, "foreground"))  # fg roda junto com bg

    def test_waiting_pinned_does_not_consume_capacity(self):
        r = self.f.runner()
        auto, ver = self.f.automation(runners=[r])
        self.f.task(auto, ver, TaskStatus.WAITING, runner=r)
        self.assertTrue(CapacityService(self.f.db).has_capacity(r, "background"))

    def test_foreground_exclusive_per_host(self):
        r1 = self.f.runner("r1", host="H")
        r2 = self.f.runner("r2", host="h")
        auto, ver = self.f.automation("foreground", runners=[r1, r2])
        self.f.task(auto, ver, TaskStatus.RUNNING, runner=r1)
        self.assertFalse(CapacityService(self.f.db).has_capacity(r2, "foreground"))

    def test_next_task_filters_by_mode(self):
        r = self.f.runner()
        a_bg, v_bg = self.f.automation("background", runners=[r])
        a_fg, v_fg = self.f.automation("foreground", runners=[r])
        t_bg = self.f.task(a_bg, v_bg, priority=1)
        t_fg = self.f.task(a_fg, v_fg, priority=9)
        res = self.svc.get_next_task(self.f.payload(r, execution_mode="background"))
        self.assertEqual(res["task_id"], t_bg.id)
        res = self.svc.get_next_task(self.f.payload(r, execution_mode="foreground"))
        self.assertEqual(res["task_id"], t_fg.id)

    def test_next_task_empty_when_no_capacity(self):
        r = self.f.runner()
        a1, v1 = self.f.automation(runners=[r])
        a2, v2 = self.f.automation(runners=[r])
        self.f.task(a1, v1, TaskStatus.RUNNING, runner=r)
        self.f.task(a2, v2)
        res = self.svc.get_next_task(self.f.payload(r, execution_mode="background"))
        self.assertFalse(res["found"])

    def test_claim_is_exclusive(self):
        r1 = self.f.runner("r1", host="A")
        r2 = self.f.runner("r2", host="B")
        auto, ver = self.f.automation(runners=[r1, r2])
        t = self.f.task(auto, ver)
        out = self.svc.claim_task(t.id, self.f.payload(r1))
        self.assertEqual(out["status"], TaskStatus.READY)
        with self.assertRaises(ValidationException):
            self.svc.claim_task(t.id, self.f.payload(r2))

    def test_claim_respects_capacity(self):
        r = self.f.runner()
        a1, v1 = self.f.automation(runners=[r])
        a2, v2 = self.f.automation(runners=[r])
        t1 = self.f.task(a1, v1)
        t2 = self.f.task(a2, v2)
        self.svc.claim_task(t1.id, self.f.payload(r))
        with self.assertRaises(ValidationException):
            self.svc.claim_task(t2.id, self.f.payload(r))

    def test_claim_revives_offline_runner(self):
        r = self.f.runner(status=RunnerStatus.OFFLINE)
        auto, ver = self.f.automation(runners=[r])
        t = self.f.task(auto, ver)
        self.svc.claim_task(t.id, self.f.payload(r))
        self.assertIn(r.status, (RunnerStatus.ONLINE, RunnerStatus.BUSY))

    def test_unique_active_lock_per_key(self):
        from sqlalchemy.exc import IntegrityError
        from app.domain.enums import LockScopeType

        r = self.f.runner()
        auto, ver = self.f.automation(runners=[r])
        t = self.f.task(auto, ver)
        now = datetime.now(UTC)
        kw = dict(lock_key="k", scope_type=LockScopeType.AUTOMATION, owner_task_id=t.id, acquired_at=now, active=True)
        self.f.db.add(Lock(**kw))
        self.f.db.flush()
        self.f.db.add(Lock(**kw))
        with self.assertRaises(IntegrityError):
            self.f.db.flush()


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.wd = WatchdogService(self.f.db)

    def _running(self, runner_name="r1", **kw):
        r = self.f.runner(name=runner_name)
        auto, ver = self.f.automation(runners=[r])
        t = self.f.task(auto, ver, TaskStatus.RUNNING, runner=r, **kw)
        return r, t

    def test_orphan_only_warns_never_stops(self):
        old = datetime.now(UTC) - timedelta(hours=1)
        r, t = self._running(started_at=old, last_update_at=old)
        r.last_heartbeat = old
        r.status = RunnerStatus.OFFLINE
        self.assertEqual(self.wd.recover_orphan_tasks(), 1)
        self.assertEqual(self.wd.recover_orphan_tasks(), 0)  # sem spam
        self.f.db.refresh(t)
        self.assertEqual(t.status, TaskStatus.RUNNING)
        self.assertFalse(t.stop_requested)

    def test_offline_runner_keeps_tasks_and_locks(self):
        r, t = self._running(started_at=datetime.now(UTC))
        r.last_heartbeat = datetime.now(UTC) - timedelta(hours=1)
        self.assertEqual(self.wd.mark_offline_runners(), 1)
        self.f.db.refresh(t)
        self.assertEqual(t.status, TaskStatus.RUNNING)
        self.assertFalse(t.stop_requested)

    def test_timeout_needs_margin_and_sets_stop(self):
        now = datetime.now(UTC)
        _, inside = self._running(
            started_at=now - timedelta(seconds=3600 + 60), last_update_at=now, timeout_seconds=3600
        )
        self.assertEqual(self.wd.mark_timed_out_tasks(), 0)
        inside.started_at = now - timedelta(seconds=3600 + 200)
        self.assertEqual(self.wd.mark_timed_out_tasks(), 1)
        self.f.db.refresh(inside)
        self.assertEqual(inside.status, TaskStatus.TIMEOUT)
        self.assertTrue(inside.stop_requested)

    def test_inactivity_timeout_without_stop_requested(self):
        now = datetime.now(UTC)
        _, t = self._running(
            started_at=now - timedelta(minutes=10),
            last_update_at=now - timedelta(minutes=5),
            inactivity_timeout_seconds=60,
        )
        self.assertEqual(self.wd.mark_timed_out_tasks(), 1)
        self.f.db.refresh(t)
        self.assertEqual(t.status, TaskStatus.TIMEOUT)
        self.assertFalse(t.stop_requested)

    def test_running_sem_sinal_do_worker_vira_erro_cedo(self):
        now = datetime.now(UTC)
        started = now - timedelta(minutes=4)
        _, t = self._running(started_at=started, last_update_at=started, timeout_seconds=3600)
        self.assertEqual(self.wd.mark_timed_out_tasks(), 1)
        self.f.db.refresh(t)
        self.assertEqual(t.status, TaskStatus.ERROR)
        self.assertFalse(t.stop_requested)
        self.assertIn("worker não deu nenhum sinal", t.final_message or "")

    def test_running_recente_ou_com_sinal_nao_e_encerrada(self):
        now = datetime.now(UTC)
        _, recente = self._running("ra", started_at=now - timedelta(minutes=2), last_update_at=now - timedelta(minutes=2))
        _, com_log = self._running("rb", started_at=now - timedelta(minutes=4), last_update_at=now - timedelta(minutes=4))
        _, com_etapa = self._running("rc", started_at=now - timedelta(minutes=4), last_update_at=now - timedelta(minutes=1))
        self.f.db.add(TaskLog(task_id=com_log.id, level=TaskLogLevel.INFO, message="x", source=TaskLogSource.WORKER))
        self.f.db.commit()
        self.assertEqual(self.wd.mark_timed_out_tasks(), 0)
        for t in (recente, com_log, com_etapa):
            self.f.db.refresh(t)
            self.assertEqual(t.status, TaskStatus.RUNNING)

    def test_stale_ready_becomes_error_without_stop(self):
        r = self.f.runner()
        auto, ver = self.f.automation(runners=[r])
        old = datetime.now(UTC) - timedelta(hours=1)
        t = self.f.task(auto, ver, TaskStatus.READY, runner=r, last_update_at=old, runner_claimed_at=old)
        self.assertEqual(self.wd.mark_timed_out_tasks(), 1)
        self.f.db.refresh(t)
        self.assertEqual(t.status, TaskStatus.ERROR)
        self.assertFalse(t.stop_requested)

    def test_no_online_runner_does_not_fail_tasks(self):
        r = self.f.runner(status=RunnerStatus.OFFLINE)
        auto, ver = self.f.automation(runners=[r])
        t = self.f.task(auto, ver, TaskStatus.RUNNING, runner=r, started_at=datetime.now(UTC))
        self.wd.fail_tasks_without_online_workers()
        self.f.db.refresh(t)
        self.assertEqual(t.status, TaskStatus.RUNNING)


class DispatchAndRegisterTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()

    def test_dispatch_balances_by_load_and_skips_offline(self):
        from app.services.dispatch_service import DispatchService

        r1 = self.f.runner("r1", host="A", max_concurrency=3)
        r2 = self.f.runner("r2", host="B", max_concurrency=3)
        off = self.f.runner("r3", host="C", status=RunnerStatus.OFFLINE)
        tasks = []
        for _ in range(4):
            auto, ver = self.f.automation(runners=[r1, r2, off])
            tasks.append(self.f.task(auto, ver))
        self.assertEqual(DispatchService(self.f.db).dispatch_pending_tasks(), 4)
        counts = {}
        for t in tasks:
            self.f.db.refresh(t)
            self.assertEqual(t.status, TaskStatus.WAITING)
            self.assertNotEqual(t.runner_id, off.id)
            counts[t.runner_id] = counts.get(t.runner_id, 0) + 1
        self.assertEqual(counts[r1.id], 2)
        self.assertEqual(counts[r2.id], 2)

    def test_dispatch_does_not_pin_without_eligible_runner(self):
        from app.services.dispatch_service import DispatchService

        off = self.f.runner("r3", status=RunnerStatus.OFFLINE)
        auto, ver = self.f.automation(runners=[off])
        t = self.f.task(auto, ver)
        self.assertEqual(DispatchService(self.f.db).dispatch_pending_tasks(), 0)
        self.f.db.refresh(t)
        self.assertIsNone(t.runner_id)

    def test_register_is_upsert_by_name(self):
        r = self.f.runner("Meu-Worker", host="H1")
        payload = SimpleNamespace(
            uuid="novo-uuid", name="meu-worker", label="L", host_name="H1", ip="1.1.1.1",
            os_name="Windows", os_version="11", cpu_arch="x64", memory_total=1, access_remote=False,
        )
        out = WorkerService(self.f.db).register_runner(payload)
        self.assertEqual(out["runner_id"], r.id)
        self.assertEqual(out["uuid"], "novo-uuid")
        self.assertTrue(out["token"])


if __name__ == "__main__":
    unittest.main()
