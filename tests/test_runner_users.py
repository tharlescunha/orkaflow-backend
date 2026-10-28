"""Out/2026: usuário de acesso (cadastrado) e usuário do Windows (do worker) na máquina."""
import unittest
from types import SimpleNamespace

from app.schemas.runner import RunnerUpdate
from app.services.runner_service import RunnerService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class RunnerUsersTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner("SRV-RPA-01")
        self.db.commit()

    def test_login_user_is_editable_and_shown(self):
        svc = RunnerService(self.db)
        svc.update(self.r.id, RunnerUpdate(login_user="ALZ\\rpa.suprimentos"))
        read = svc.get(self.r.id)
        self.assertEqual(read.login_user, "ALZ\\rpa.suprimentos")
        self.assertIsNone(read.os_user)
        overview = svc.get_overview(self.r.id)
        self.assertEqual(overview.runner.login_user, "ALZ\\rpa.suprimentos")

    def test_heartbeat_records_os_user_and_old_worker_keeps_it(self):
        svc = WorkerService(self.db)
        svc.heartbeat(self.f.payload(self.r, ip="10.0.0.5", running_tasks=0, os_user="ALZ\\svc.rpa"))
        self.db.refresh(self.r)
        self.assertEqual(self.r.os_user, "ALZ\\svc.rpa")
        # Worker antigo (sem o campo) não apaga o que já estava gravado.
        svc.heartbeat(SimpleNamespace(uuid=self.r.uuid, token=self.f.token, ip=None, running_tasks=0))
        self.db.refresh(self.r)
        self.assertEqual(self.r.os_user, "ALZ\\svc.rpa")
        read = RunnerService(self.db).get(self.r.id)
        self.assertEqual(read.os_user, "ALZ\\svc.rpa")
