"""Remover runner (soft delete) e tela de Logs das máquinas (sqlite em memória)."""
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy import select

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.domain.enums import RunnerStatus, TaskStatus
from app.models.automation_runner import AutomationRunner
from app.models.runner_log_line import RunnerLogLine
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.runner_log import WorkerLogBatchRequest
from app.services.automation_runner_service import AutomationRunnerService
from app.services.runner_log_service import RunnerLogService
from app.services.runner_service import RunnerService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class RunnerRemovalTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r1 = self.f.runner("r1")
        self.r2 = self.f.runner("r2", host="HOST2")
        self.auto, self.version = self.f.automation(runners=[self.r1, self.r2])
        self.svc = RunnerService(self.db)

    def names(self, **kw):
        return [r.name for r in self.svc.list(**kw)]

    def test_removed_runner_disappears_from_lists_but_stays_in_history(self):
        done = self.f.task(self.auto, self.version, TaskStatus.FINISHED, runner=self.r1)
        self.db.commit()

        result = self.svc.remove(self.r1.id)

        self.assertIsNotNone(result.deleted_at)
        self.assertFalse(result.enabled)
        self.assertEqual(self.names(), ["r2"])
        self.assertEqual(self.names(removed=True), ["r1"])
        self.assertEqual(self.svc.get(self.r1.id).name, "r1", "detalhe continua acessível")
        self.db.refresh(done)
        self.assertEqual(done.runner_id, self.r1.id, "task antiga mantém o runner")
        self.assertEqual([r.name for r in TaskRepository(self.db).list_active_runner_options()], ["r2"])
        self.assertEqual([r.name for r in DashboardRepository(self.db).list_runners()], ["r2"])

    def test_remove_unlinks_automations_and_requeues_waiting_tasks(self):
        waiting = self.f.task(self.auto, self.version, TaskStatus.WAITING, runner=self.r1)
        self.db.commit()

        self.svc.remove(self.r1.id)

        links = self.db.scalars(select(AutomationRunner.runner_id)).all()
        self.assertEqual(sorted(links), [self.r2.id])
        self.db.refresh(waiting)
        self.assertIsNone(waiting.runner_id)
        self.assertEqual(waiting.status, TaskStatus.WAITING)

    def test_remove_refuses_while_task_is_executing(self):
        self.f.task(self.auto, self.version, TaskStatus.RUNNING, runner=self.r1)
        self.db.commit()
        with self.assertRaises(ConflictException):
            self.svc.remove(self.r1.id)
        self.assertEqual(self.names(), ["r1", "r2"])

    def test_remove_is_idempotent_and_404_for_unknown(self):
        self.svc.remove(self.r1.id)
        self.svc.remove(self.r1.id)
        with self.assertRaises(NotFoundException):
            self.svc.remove(9999)

    def test_removed_runner_cannot_be_linked_again(self):
        self.svc.remove(self.r1.id)
        with self.assertRaises(NotFoundException):
            AutomationRunnerService.link_runner(self.db, self.auto.id, self.r1.id)

    def test_worker_of_removed_runner_is_refused(self):
        self.svc.remove(self.r1.id)
        worker = WorkerService(self.db)
        with self.assertRaises(ForbiddenException):
            worker.heartbeat(self.f.payload(self.r1, ip="1.1.1.1", running_tasks=0))

    def test_registering_again_brings_runner_back(self):
        self.svc.remove(self.r1.id)
        payload = SimpleNamespace(
            uuid="uuid-novo", name="r1", label=None, host_name="HOST1", ip="1.1.1.1",
            os_name=None, os_version=None, cpu_arch=None, memory_total=None, access_remote=False,
        )
        result = WorkerService(self.db).register_runner(payload)

        self.assertEqual(result["runner_id"], self.r1.id)
        self.assertTrue(result["enabled"])
        self.assertEqual(self.names(), ["r1", "r2"])
        self.assertEqual(self.names(removed=True), [])


class RunnerLogTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r1 = self.f.runner("r1")
        self.r2 = self.f.runner("r2", host="HOST2")
        self.db.commit()
        self.svc = RunnerLogService(self.db)

    def push(self, runner, *messages, level="INFO", token=None):
        return self.svc.ingest(
            WorkerLogBatchRequest(
                uuid=runner.uuid,
                token=token or self.f.token,
                lines=[
                    {"logged_at": datetime.now(UTC).isoformat(), "level": level, "message": m}
                    for m in messages
                ],
            )
        )

    def test_ingest_splits_bot_lines_and_keeps_indentation(self):
        self.push(self.r1, "Sync de bots concluido", "[BOT][task_id=42]     at linha 3")
        page = self.svc.list_lines(self.r1.id)

        worker_line, bot_line = page["items"]
        self.assertEqual((worker_line.source, worker_line.task_id), ("worker", None))
        self.assertEqual((bot_line.source, bot_line.task_id), ("bot", 42))
        self.assertEqual(bot_line.message, "    at linha 3")
        self.assertEqual(page["last_id"], bot_line.id)
        self.assertEqual(page["retention_days"], 3)

    def test_polling_after_id_returns_only_new_lines_of_that_runner(self):
        self.push(self.r1, "a", "b")
        self.push(self.r2, "outra maquina")
        first = self.svc.list_lines(self.r1.id)
        self.push(self.r1, "c")

        nxt = self.svc.list_lines(self.r1.id, after_id=first["last_id"])
        self.assertEqual([i.message for i in nxt["items"]], ["c"])
        empty = self.svc.list_lines(self.r1.id, after_id=nxt["last_id"])
        self.assertEqual(empty["items"], [])
        self.assertEqual(empty["last_id"], nxt["last_id"])

    def test_initial_page_returns_last_lines_in_order(self):
        self.push(self.r1, *[f"linha {i}" for i in range(10)])
        page = self.svc.list_lines(self.r1.id, limit=3)
        self.assertEqual([i.message for i in page["items"]], ["linha 7", "linha 8", "linha 9"])

    def test_filters(self):
        self.push(self.r1, "worker ok", "[BOT][task_id=1] robo 1", "[BOT][task_id=2] robo 2 100%")
        self.push(self.r1, "deu ruim", level="error")

        def msgs(**kw):
            return [i.message for i in self.svc.list_lines(self.r1.id, **kw)["items"]]

        self.assertEqual(msgs(source="bot"), ["robo 1", "robo 2 100%"])
        self.assertEqual(msgs(task_id=2), ["robo 2 100%"])
        self.assertEqual(msgs(level="error"), ["deu ruim"])
        self.assertEqual(msgs(search="100%"), ["robo 2 100%"])
        self.assertEqual(msgs(search="%"), ["robo 2 100%"], "curinga do LIKE é escapado")

    def test_invalid_token_and_removed_runner_are_refused(self):
        from app.core.exceptions import UnauthorizedException

        with self.assertRaises(UnauthorizedException):
            self.push(self.r1, "x", token="errado")
        RunnerService(self.db).remove(self.r1.id)
        with self.assertRaises(ForbiddenException):
            self.push(self.r1, "x")

    def test_unknown_runner_404_on_panel(self):
        with self.assertRaises(NotFoundException):
            self.svc.list_lines(9999)

    def test_purge_removes_only_expired_lines(self):
        self.push(self.r1, "nova")
        old = RunnerLogLine(
            runner_id=self.r1.id, logged_at=datetime.now(UTC), level="INFO", source="worker",
            message="velha", received_at=datetime.now(UTC) - timedelta(days=4),
        )
        self.db.add(old)
        self.db.commit()

        self.assertEqual(self.svc.purge_expired(), 1)
        self.assertEqual([i.message for i in self.svc.list_lines(self.r1.id)["items"]], ["nova"])


class SqlServerCompileTests(unittest.TestCase):
    """As consultas novas precisam compilar no dialeto do SQL Server (sem IS 1, LIMIT etc.)."""

    def test_queries_compile_for_mssql(self):
        from sqlalchemy import delete
        from sqlalchemy.dialects import mssql

        from app.models.runner import Runner

        dialect = mssql.dialect()
        ids = select(RunnerLogLine.id).where(RunnerLogLine.received_at < datetime.now(UTC)).limit(5000)
        stmt = delete(RunnerLogLine).where(RunnerLogLine.id.in_(ids))
        sql = str(stmt.compile(dialect=dialect))
        self.assertIn("TOP", sql)

        listing = str(select(Runner).where(Runner.deleted_at.is_(None)).compile(dialect=dialect))
        self.assertIn("deleted_at IS NULL", listing)


if __name__ == "__main__":
    unittest.main()
