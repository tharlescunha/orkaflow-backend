"""Out/2026: o dispatcher não sobrescreve uma task que o worker assumiu (claim) no meio do ciclo."""
import unittest
from unittest import mock

from sqlalchemy import update

from app.domain.enums import TaskStatus
from app.models.task import Task
from app.services import dispatch_service
from app.services.dispatch_service import DispatchService

from tests.test_concurrency_watchdog import Fixture


class DispatchRaceTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r1 = self.f.runner("r1", host="H1")
        self.r2 = self.f.runner("r2", host="H2")
        self.auto, self.ver = self.f.automation(runners=[self.r1, self.r2])
        self.task = self.f.task(self.auto, self.ver, TaskStatus.WAITING)
        self.db.commit()

    def test_pin_normal_grava_runner_e_tentativa(self):
        self.assertEqual(DispatchService(self.db).dispatch_pending_tasks(), 1)
        self.db.refresh(self.task)
        self.assertIsNotNone(self.task.runner_id)
        self.assertEqual(self.task.dispatch_attempts, 1)

    def test_claim_no_meio_do_ciclo_nao_e_sobrescrito(self):
        task_id = self.task.id
        runner_id = self.r2.id

        def claim_antes_do_pin(*_args, **_kwargs):
            # O worker da r2 assume a task depois da leitura do dispatcher e antes da gravação dele.
            self.db.execute(
                update(Task)
                .where(Task.id == task_id)
                .values(status=TaskStatus.READY, runner_id=runner_id, dispatch_attempts=1)
                .execution_options(synchronize_session=False)
            )
            return None

        with mock.patch.object(dispatch_service, "describe_wait_reason", side_effect=claim_antes_do_pin):
            dispatched = DispatchService(self.db).dispatch_pending_tasks()

        self.assertEqual(dispatched, 0)
        self.db.expire_all()
        task = self.db.get(Task, task_id)
        self.assertEqual(task.status, TaskStatus.READY)
        self.assertEqual(task.runner_id, runner_id)
        self.assertEqual(task.dispatch_attempts, 1)


if __name__ == "__main__":
    unittest.main()
