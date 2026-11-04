"""Nov/2026: Database Status dentro do Regente (token da identidade do app, rotas protegidas e desligadas por padrão)."""
import json
import os
import unittest
from types import SimpleNamespace
from unittest import mock

from app.api.deps import require_admin
from app.api.v1.dbstatus import DbStatusDisabled, dbstatus_route
from app.core.exceptions import NotFoundException
from app.dbstatus import service
from app.main import app


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TokenTests(unittest.TestCase):
    def setUp(self):
        service._tok.clear()
        self.addCleanup(service._tok.clear)

    def test_no_app_service_usa_a_identidade_gerenciada_e_guarda_em_cache(self):
        env = {"IDENTITY_ENDPOINT": "http://127.0.0.1:41337/msi/token", "IDENTITY_HEADER": "segredo"}
        with mock.patch.dict(os.environ, env), mock.patch.object(
            service, "urlopen", return_value=_Resp({"access_token": "TOKEN-MI", "expires_on": "9999999999"})
        ) as urlopen, mock.patch.object(service.subprocess, "run") as run:
            self.assertEqual(service.get_token("https://database.windows.net/"), "TOKEN-MI")
            self.assertEqual(service.get_token("https://database.windows.net/"), "TOKEN-MI")  # cache

        self.assertEqual(urlopen.call_count, 1)
        self.assertFalse(run.called)  # não chamou o az
        req = urlopen.call_args.args[0]
        self.assertIn("resource=https%3A%2F%2Fdatabase.windows.net%2F", req.full_url)
        self.assertEqual(req.get_header("X-identity-header"), "segredo")

    def test_fora_do_azure_usa_o_az(self):
        env = {k: v for k, v in os.environ.items() if k not in ("IDENTITY_ENDPOINT", "IDENTITY_HEADER")}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            service.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="TOKEN-AZ\n", stderr="")
        ) as run:
            self.assertEqual(service.get_token("https://management.azure.com/"), "TOKEN-AZ")
        self.assertIn("get-access-token", run.call_args.args[0])

    def test_falha_do_az_vira_erro_claro(self):
        env = {k: v for k, v in os.environ.items() if k not in ("IDENTITY_ENDPOINT", "IDENTITY_HEADER")}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(
            service.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="", stderr="login expirado")
        ):
            with self.assertRaises(RuntimeError) as ctx:
                service.get_token("x")
        self.assertIn("login expirado", str(ctx.exception))


def _request(query=""):
    return SimpleNamespace(url=SimpleNamespace(query=query))


def _settings(enabled):
    return mock.patch("app.api.v1.dbstatus.get_settings", return_value=SimpleNamespace(dbstatus_enabled=enabled))


class RotasTests(unittest.TestCase):
    def test_as_dez_rotas_do_painel_existem(self):
        esperado = {"databases", "overview", "snapshot", "db", "db/live", "db/queries", "db/extra", "db/events", "db/usage", "db/schemas"}
        self.assertEqual({r.removeprefix("/api/") for r in service.ROUTES}, esperado)

    def test_desligado_por_padrao_responde_503(self):
        with _settings(False):
            with self.assertRaises(DbStatusDisabled) as ctx:
                dbstatus_route("databases", _request(), None)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("DBSTATUS_ENABLED", ctx.exception.detail)

    def test_ligado_chama_a_rota_e_repassa_os_parametros(self):
        visto = {}

        def fake(qs):
            visto.update(qs)
            return {"ok": True, "range": qs.get("range")}

        with _settings(True), mock.patch.dict(service.ROUTES, {"/api/overview": fake}), mock.patch.object(service, "start", return_value=True):
            resp = dbstatus_route("overview", _request("range=24h"), None)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(json.loads(resp.body), {"ok": True, "range": ["24h"]})
        self.assertEqual(visto, {"range": ["24h"]})
        self.assertEqual(resp.headers["cache-control"], "no-store")

    def test_rota_com_barra_aninhada_e_serializa_datas(self):
        from datetime import datetime

        with _settings(True), mock.patch.dict(
            service.ROUTES, {"/api/db/live": lambda qs: {"quando": datetime(2026, 11, 4, 12, 0)}}
        ), mock.patch.object(service, "start", return_value=True):
            resp = dbstatus_route("db/live", _request("s=a&d=b"), None)
        self.assertEqual(json.loads(resp.body)["quando"], "2026-11-04 12:00:00")

    def test_rota_desconhecida_e_404(self):
        with _settings(True):
            with self.assertRaises(NotFoundException):
                dbstatus_route("nao-existe", _request(), None)

    def test_a_rota_exige_administrador(self):
        rota = next(r for r in app.routes if getattr(r, "path", "") == "/api/v1/dbstatus/{route:path}")
        chamadas = [d.call for d in rota.dependant.dependencies]
        self.assertIn(require_admin, chamadas)


class PastaDeDadosTests(unittest.TestCase):
    def test_wal_so_fora_do_app_service(self):
        # Local: WAL (rápido). No App Service o /home é disco de rede: modo comum.
        self.assertEqual(service.JOURNAL_MODE, "DELETE" if service.ON_APP_SERVICE else "WAL")


if __name__ == "__main__":
    unittest.main()
