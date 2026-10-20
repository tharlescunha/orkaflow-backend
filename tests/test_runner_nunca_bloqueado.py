"""O sistema nunca bloqueia runner: só o administrador desativa (enabled=False)."""
import unittest

from app.domain.enums import RunnerStatus, TaskStatus
from app.services.task_service import TaskService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class RunnerNuncaBloqueadoTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.svc = WorkerService(self.f.db)
        self.r = self.f.runner()
        self.auto, self.version = self.f.automation(runners=[self.r])

    def test_parada_forcada_nao_bloqueia_o_runner(self):
        task = self.f.task(self.auto, self.version)
        self.svc.claim_task(task.id, self.f.payload(self.r))

        TaskService(self.f.db).force_stop(task.id)

        self.f.db.refresh(task)
        self.f.db.refresh(self.r)
        self.assertEqual(task.status, TaskStatus.FORCED_STOP)
        self.assertNotEqual(self.r.status, RunnerStatus.BLOCKED)
        self.assertIn(self.r.status, (RunnerStatus.ONLINE, RunnerStatus.BUSY))

    def test_runner_apos_parada_forcada_continua_recebendo_tasks(self):
        first = self.f.task(self.auto, self.version)
        self.svc.claim_task(first.id, self.f.payload(self.r))
        TaskService(self.f.db).force_stop(first.id)

        second = self.f.task(self.auto, self.version)
        result = self.svc.claim_task(second.id, self.f.payload(self.r))

        self.assertEqual(result["task_id"], second.id)
        self.assertEqual(result["status"], TaskStatus.READY)

    def test_runner_bloqueado_por_versao_antiga_volta_ao_vivo(self):
        # Dados herdados: runner marcado BLOCKED por paradas forçadas de versões anteriores.
        self.r.status = RunnerStatus.BLOCKED
        self.f.db.add(self.r)
        self.f.db.flush()

        task = self.f.task(self.auto, self.version)
        result = self.svc.claim_task(task.id, self.f.payload(self.r))

        self.f.db.refresh(self.r)
        self.assertEqual(result["task_id"], task.id)
        self.assertNotEqual(self.r.status, RunnerStatus.BLOCKED)


if __name__ == "__main__":
    unittest.main()
