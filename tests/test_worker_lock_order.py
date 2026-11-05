"""Nov/2026: deadlocks no DW-ALZ entre runners, tasks e locks.

O heartbeat segurava a linha do runner e esperava a linha de locks; log/erro/telemetria seguravam tasks/locks
e só depois pediam o runner. Regra testada: a gravação do "worker vivo" (last_heartbeat) é confirmada sozinha,
antes de qualquer escrita em tasks ou locks da mesma chamada. Sessão com expire_on_commit=True, como em produção.
"""
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.domain.enums import ErrorCategory, LockScopeType, TaskLogLevel, TaskLogSource, TaskStatus
from app.models.lock import Lock
from app.models.task import Task
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class LockOrderTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.r = self.f.runner("r1")
        self.auto, self.ver = self.f.automation(runners=[self.r])
        self.task = self.f.task(self.auto, self.ver, TaskStatus.RUNNING, runner=self.r)
        self.f.db.add(
            Lock(
                lock_key="k1",
                scope_type=LockScopeType.AUTOMATION,
                owner_task_id=self.task.id,
                runner_id=self.r.id,
                acquired_at=datetime.now(UTC),
                active=True,
            )
        )
        self.f.db.commit()
        self.task_id, self.runner_id = self.task.id, self.r.id

        engine = self.f.db.get_bind()
        self.db = sessionmaker(bind=engine, expire_on_commit=True)()  # igual à produção
        self.log = []
        event.listen(engine, "before_cursor_execute", self._on_sql)
        event.listen(engine, "commit", lambda _c: self.log.append("COMMIT"))
        self.svc = WorkerService(self.db)

    def _on_sql(self, _conn, _cur, statement, *_a):
        s = " ".join(statement.split()).upper()
        if s.startswith("UPDATE RUNNERS") and "LAST_HEARTBEAT" in s:
            self.log.append("ALIVE")
        elif s.startswith("UPDATE TASKS"):
            self.log.append("TASKS")
        elif s.startswith("UPDATE LOCKS"):
            self.log.append("LOCKS")

    def _p(self, **extra):
        return SimpleNamespace(uuid=self.r.uuid, token=self.f.token, **extra)

    def _assert_alive_sozinho(self):
        """Entre o UPDATE do last_heartbeat e o COMMIT seguinte não pode haver escrita em tasks/locks."""
        self.assertIn("ALIVE", self.log, self.log)
        # 1) o runner vem primeiro: nenhuma escrita em tasks/locks antes dele
        primeiro = next(i for i in self.log if i in ("ALIVE", "TASKS", "LOCKS"))
        self.assertEqual(primeiro, "ALIVE", f"tasks/locks gravados antes do runner: {self.log}")
        # 2) e ele é confirmado sozinho: nada de tasks/locks antes do COMMIT seguinte
        aberto = False
        for item in self.log:
            if item == "ALIVE":
                aberto = True
            elif item == "COMMIT":
                aberto = False
            elif aberto:
                self.fail(f"{item} gravado na mesma transação do last_heartbeat: {self.log}")

    def test_heartbeat_renova_locks_depois_de_soltar_o_runner(self):
        self.svc.heartbeat(self._p(ip="1.1.1.1", running_tasks=1))
        self._assert_alive_sozinho()
        self.assertIn("LOCKS", self.log)  # a renovação continua acontecendo

    def test_log_do_worker(self):
        self.svc.create_task_log(
            self.task_id,
            self._p(
                level=TaskLogLevel.INFO, message="oi", source=TaskLogSource.WORKER, reference=None,
                error_type=None, sequence_number=1, event_code=None,
            ),
        )
        self._assert_alive_sozinho()
        self.assertIn("LOCKS", self.log)

    def test_erro_do_worker(self):
        self.svc.create_task_error(
            self.task_id,
            self._p(
                error_screenshot_base64=None, error_type="X", message="m", stacktrace=None,
                error_category=ErrorCategory.TECHNICAL, is_retryable=False, source=TaskLogSource.WORKER, code=None,
            ),
        )
        self._assert_alive_sozinho()

    def test_status_de_progresso_e_final(self):
        base = dict(items_processed=None, items_failed=None, final_message=None, result_json=None)
        self.svc.update_task_status(self.task_id, self._p(status=TaskStatus.RUNNING, **base))
        self._assert_alive_sozinho()
        self.log.clear()
        self.svc.finish_task(self.task_id, self._p(status=TaskStatus.FINISHED, **base))
        self._assert_alive_sozinho()
        self.db.expire_all()
        self.assertEqual(self.db.get(Task, self.task_id).status, TaskStatus.FINISHED)

    def test_heartbeat_continua_marcando_o_runner_vivo_e_online(self):
        from app.domain.enums import RunnerStatus
        from app.models.runner import Runner

        self.svc.heartbeat(self._p(ip=None, running_tasks=0))
        self.db.expire_all()
        runner = self.db.get(Runner, self.runner_id)
        self.assertEqual(runner.status, RunnerStatus.BUSY)  # há task RUNNING aberta
        self.assertIsNotNone(runner.last_heartbeat)


if __name__ == "__main__":
    unittest.main()
