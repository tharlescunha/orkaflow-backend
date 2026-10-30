"""Out/2026: versão do worker (aba Works) e tela Sync por usuário."""
import unittest
from types import SimpleNamespace
from unittest import mock

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.models.user import User
from app.services import sync_service
from app.services.sync_service import SyncService
from app.services.worker_release_service import WorkerReleaseService, commit_matches
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture

SHA = "b6d65fd" + "a" * 33


class WorkerReleaseTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner("SRV-A")
        self.db.commit()
        self.svc = WorkerReleaseService(self.db)

    def _hb(self, **extra):
        return SimpleNamespace(uuid=self.r.uuid, token=self.f.token, ip=None, running_tasks=0, **extra)

    def test_commit_matches_curto_contra_inteiro(self):
        self.assertTrue(commit_matches("b6d65fd", SHA))
        self.assertFalse(commit_matches("1234567", SHA))
        self.assertFalse(commit_matches("b6d", SHA))
        self.assertFalse(commit_matches(None, SHA))

    def test_link_com_token_e_recusado(self):
        with self.assertRaises(ValidationException):
            self.svc.set_repo_url("https://user:token@github.com/x/y.git")
        with self.assertRaises(ValidationException):
            self.svc.set_repo_url("ftp://x/y")
        self.svc.set_repo_url("https://github.com/tharlescunha/worker-url.git")
        self.assertEqual(self.svc.overview()["repo_url"], "https://github.com/tharlescunha/worker-url.git")

    def test_verificar_guarda_commit_e_marca_desatualizada(self):
        self.svc.set_repo_url("https://github.com/tharlescunha/worker-url.git")
        WorkerService(self.db).heartbeat(self._hb(worker_commit="1111111", worker_version="0.3.0"))
        with mock.patch.object(WorkerReleaseService, "_ls_remote", return_value=(SHA, None)):
            overview = self.svc.check_latest()
        self.assertEqual(overview["latest_commit"], SHA)
        runner = overview["runners"][0]
        self.assertEqual(runner["worker_commit"], "1111111")
        self.assertIs(runner["up_to_date"], False)

        WorkerService(self.db).heartbeat(self._hb(worker_commit="b6d65fd"))
        self.assertIs(self.svc.overview()["runners"][0]["up_to_date"], True)

    def test_erro_do_git_fica_visivel_e_nao_derruba(self):
        self.svc.set_repo_url("https://github.com/tharlescunha/worker-url.git")
        with mock.patch.object(WorkerReleaseService, "_ls_remote", return_value=(None, "Sem acesso.")):
            overview = self.svc.check_latest()
        self.assertIsNone(overview["latest_commit"])
        self.assertEqual(overview["latest_error"], "Sem acesso.")

    def test_pedido_chega_no_heartbeat_e_some_quando_o_worker_reinicia(self):
        hb = WorkerService(self.db).heartbeat
        self.assertFalse(hb(self._hb()).update_requested)

        self.assertEqual(self.svc.request_update([self.r.id]), 1)
        self.assertTrue(hb(self._hb(worker_commit="1111111")).update_requested)

        # Worker antigo (sem campos novos) continua recebendo o pedido e não quebra.
        self.assertTrue(hb(self._hb()).update_requested)

        # Confirmação de outro pedido não vale.
        self.assertTrue(hb(self._hb(worker_commit="1111111", update_ack="outro")).update_requested)

        # O worker confirma o código do pedido depois de reiniciar (mesmo sem commit novo): atendido.
        rid = hb(self._hb()).update_request_id
        self.assertIsNotNone(rid)
        self.assertFalse(hb(self._hb(worker_commit="1111111", update_ack=rid)).update_requested)

    def test_commit_novo_tambem_encerra_o_pedido(self):
        hb = WorkerService(self.db).heartbeat
        hb(self._hb(worker_commit="1111111"))
        self.svc.request_update(None)
        self.assertFalse(hb(self._hb(worker_commit="2222222")).update_requested)

    def test_cancelar_pedido(self):
        self.svc.request_update([self.r.id])
        self.svc.cancel_update(self.r.id)
        self.assertIsNone(self.svc.overview()["runners"][0]["update_requested_at"])


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.user = User(name="A", login="aaa", email="a@x.com", password_hash="x", active=True, role="admin")
        self.other = User(name="B", login="bbb", email="b@x.com", password_hash="x", active=True, role="admin")
        self.db.add_all([self.user, self.other])
        self.db.commit()

    def test_sync_vem_desligado_e_so_o_dono_liga(self):
        self.assertFalse(self.user.sync_enabled)
        with self.assertRaises(ForbiddenException):
            SyncService(self.db, self.user).state()
        SyncService(self.db, self.user).set_preference(True)
        self.assertEqual(SyncService(self.db, self.user).state()["checks"], [])
        self.assertFalse(self.other.sync_enabled)
        with self.assertRaises(ForbiddenException):
            SyncService(self.db, self.other).state()

    def _on(self):
        SyncService(self.db, self.user).set_preference(True)
        return SyncService(self.db, self.user)

    def test_url_invalida_e_barrada(self):
        svc = self._on()
        for url in ("ftp://x", "sem-esquema", "http://user:pw@host/"):
            with self.assertRaises(ValidationException):
                svc.create_check({"name": "x", "url": url, "interval_seconds": 60, "timeout_seconds": 5, "active": True})

    def test_sistema_de_um_usuario_nao_aparece_para_outro(self):
        svc = self._on()
        check = svc.create_check(
            {"name": "Insumos API", "url": "https://exemplo.com/health", "project": "Insumos", "server": "Azure",
             "interval_seconds": 60, "timeout_seconds": 5, "active": True}
        )
        SyncService(self.db, self.other).set_preference(True)
        with self.assertRaises(NotFoundException):
            SyncService(self.db, self.other).ping(check.id)
        self.assertEqual(SyncService(self.db, self.other).state()["checks"], [])

    def test_ping_ok_e_falha(self):
        svc = self._on()
        check = svc.create_check(
            {"name": "x", "url": "https://exemplo.com/h", "interval_seconds": 60, "timeout_seconds": 5, "active": True}
        )
        with mock.patch.object(sync_service, "_blocked_address", return_value=None), mock.patch.object(
            SyncService, "_request", return_value=(True, 200, 42, None)
        ):
            got = svc.ping(check.id)
        self.assertTrue(got.last_ok)
        self.assertEqual((got.last_status_code, got.last_latency_ms), (200, 42))
        with mock.patch.object(SyncService, "_request", return_value=(False, None, 5000, "Sem resposta em 5s.")):
            got = svc.ping(check.id)
        self.assertFalse(got.last_ok)
        self.assertEqual(got.last_error, "Sem resposta em 5s.")

    def test_status_esperado(self):
        check = SimpleNamespace(url="https://exemplo.com", timeout_seconds=1, expected_status=204)
        with mock.patch.object(sync_service, "_blocked_address", return_value=None), mock.patch(
            "urllib.request.urlopen", side_effect=sync_service.urllib.error.HTTPError("u", 200, "ok", {}, None)
        ):
            ok, code, _, _ = SyncService._request(check)
        self.assertEqual(code, 200)
        self.assertFalse(ok)

    def test_loopback_e_metadata_sao_barrados(self):
        check = SimpleNamespace(url="http://127.0.0.1:8000/", timeout_seconds=1, expected_status=None)
        ok, _, _, error = SyncService._request(check)
        self.assertFalse(ok)
        self.assertIn("não permitido", error)

    def test_picks_ignoram_automacao_inexistente(self):
        svc = self._on()
        r = self.f.runner("r-pick")
        auto, _ver = self.f.automation(runners=[r])
        self.db.commit()
        self.assertEqual(svc.set_picks([auto.id, 999999]), [auto.id])
        self.assertEqual(svc.state()["automation_ids"], [auto.id])
        self.assertEqual(svc.set_picks([]), [])


if __name__ == "__main__":
    unittest.main()
