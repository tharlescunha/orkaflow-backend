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
    def test_as_rotas_do_painel_existem(self):
        esperado = {"databases", "overview", "snapshot", "alerts", "db", "db/live", "db/queries", "db/extra", "db/events", "db/usage", "db/schemas"}
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


def _snap(**kw):
    base = {"ok": True, "cpu": 10.0, "io": 5.0, "log": 2.0, "dtu": 10.0, "workers": 3, "sessionsPct": 4, "blocked": 0}
    base.update(kw)
    return base


class AlertasDeBancoTests(unittest.TestCase):
    def test_banco_saudavel_nao_alerta(self):
        self.assertEqual(service.db_alert_reasons(_snap()), [])

    def test_dtu_critico_aponta_o_recurso_no_limite(self):
        r = service.db_alert_reasons(_snap(cpu=40.0, io=96.0, log=3.0, dtu=96.0))
        self.assertEqual(r, ["DTU em 96% (IO de dados no limite)"])

    def test_limites_sao_os_da_tela_90_por_cento_e_3_bloqueios(self):
        self.assertEqual(service.db_alert_reasons(_snap(dtu=89.9, cpu=89.9)), [])  # 89,9% ainda é atenção, não crítico
        self.assertEqual(len(service.db_alert_reasons(_snap(dtu=90.0, cpu=90.0))), 1)
        self.assertEqual(service.db_alert_reasons(_snap(blocked=2)), [])
        self.assertEqual(service.db_alert_reasons(_snap(blocked=3)), ["3 consultas bloqueadas"])

    def test_varios_motivos_juntos(self):
        r = service.db_alert_reasons(_snap(workers=95, sessionsPct=91, blocked=5, dtu=20.0))
        self.assertEqual(r, ["Workers em 95%", "Sessões em 91%", "5 consultas bloqueadas"])

    def test_leitura_que_falhou_nao_vira_alerta(self):
        # Sem permissão ou rede num banco não é "banco com problema": o painel mostra isso no próprio card.
        self.assertEqual(service.db_alert_reasons({"ok": False, "error": "login failed"}), [])
        self.assertEqual(service.db_alert_reasons(None), [])

    # ---- mesma regra da tela (conferida contra a função view() original, em JavaScript, em 12 casos)
    def _item(self, **kw):
        base = {"id": "a", "dtuModel": True, "now": {}, "recent": {}}
        base.update(kw)
        return base

    def test_deadlocks_criticos_como_na_tela(self):
        r = service.view_reasons(self._item(recent={"deadlock": 3}), _snap())
        self.assertEqual(r, [("red", "3 deadlocks nos últimos 15 min (crítico a partir de 3)")])

    def test_conexoes_recusadas_e_armazenamento(self):
        r = service.view_reasons(self._item(recent={"connection_failed": 12}, now={"storage_percent": 93}), _snap())
        self.assertEqual(
            r,
            [("red", "Armazenamento em 93% (crítico a partir de 92%)"), ("red", "12 conexões recusadas em 15 min (crítico a partir de 10)")],
        )

    def test_atencao_aparece_na_tela_mas_nao_vira_aviso_de_problema(self):
        r = service.view_reasons(self._item(recent={"deadlock": 1}), _snap(dtu=75.0, cpu=75.0, blocked=1))
        self.assertEqual({lv for lv, _ in r}, {"yellow"})

    def test_sem_leitura_direta_usa_as_metricas_do_azure(self):
        agora = {"dtu_consumption_percent": 93, "cpu_percent": 93, "physical_data_read_percent": 10, "workers_percent": 95}
        r = service.view_reasons(self._item(now=agora), None)
        self.assertEqual([lv for lv, _ in r], ["red", "red", "red"])  # DTU, CPU e Workers

    def test_rota_de_alertas_lista_so_os_criticos_do_pior_para_o_melhor(self):
        snap = {
            "a": _snap(dtu=95.0, cpu=95.0),
            "b": _snap(),
            "c": _snap(blocked=4, dtu=99.0, cpu=99.0),
            "d": {"ok": False, "error": "x"},
            "e": _snap(),  # saudável na leitura direta, mas com deadlocks (só o Azure Monitor enxerga)
        }
        dbs = [{"id": k, "server": "srv", "name": f"DB_{k.upper()}", "state": "Online", "dtuModel": True} for k in snap]
        recent = {"e": {"deadlock": 5}}
        live = lambda d: {**d, "now": {}, "recent": recent.get(d["id"], {})}
        with mock.patch.object(service, "snapshot_all", return_value=snap), mock.patch.object(
            service, "databases", return_value=dbs
        ), mock.patch.object(service, "_live_item", side_effect=live):
            out = service.api_alerts({})
        self.assertEqual([i["name"] for i in out["items"]], ["DB_C", "DB_A", "DB_E"])
        self.assertEqual(out["checked"], 5)
        c = out["items"][0]
        self.assertEqual(c["reasons"], ["DTU em 99% (crítico a partir de 90%)", "CPU em 99% (crítico a partir de 90%)", "4 consultas bloqueadas agora (crítico a partir de 3)"])
        self.assertEqual(out["items"][2]["reasons"], ["5 deadlocks nos últimos 15 min (crítico a partir de 3)"])
        self.assertIn("generated", out)

    def test_se_o_azure_monitor_falha_o_aviso_cai_na_leitura_direta(self):
        snap = {"a": _snap(dtu=97.0, cpu=97.0), "b": _snap()}
        dbs = [{"id": k, "server": "srv", "name": k.upper(), "state": "Online", "dtuModel": True} for k in snap]
        broken = lambda d: {**d, "error": "403 sem permissão"}
        with mock.patch.object(service, "snapshot_all", return_value=snap), mock.patch.object(
            service, "databases", return_value=dbs
        ), mock.patch.object(service, "_live_item", side_effect=broken):
            out = service.api_alerts({})
        self.assertEqual([i["name"] for i in out["items"]], ["A"])
        self.assertEqual(out["items"][0]["reasons"], ["DTU em 97% (CPU no limite)"])


class PastaDeDadosTests(unittest.TestCase):
    def test_wal_so_fora_do_app_service(self):
        # Local: WAL (rápido). No App Service o /home é disco de rede: modo comum.
        self.assertEqual(service.JOURNAL_MODE, "DELETE" if service.ON_APP_SERVICE else "WAL")


if __name__ == "__main__":
    unittest.main()
