"""Aba Integração: tokens de integração, servidor MCP e documentação só para logados (sqlite em memória)."""
import asyncio
import json
import unittest
from datetime import UTC, datetime, timedelta
from unittest import mock

from starlette.requests import Request

from app.api.deps import user_from_token
from app.core.exceptions import ForbiddenException, UnauthorizedException, ValidationException
from app.core.security import create_access_token
from app.domain.enums import ScheduleStatus, SchedulePolicy, ScheduleType, TaskStatus
from app.mcp import server as mcp_server
from app.mcp.tools import TOOLS
from app.models.schedule import Schedule
from app.models.task import Task
from app.models.task_error import TaskError
from app.services import api_token_service as tokens
from tests.test_concurrency_watchdog import Fixture


class ApiTokenTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.user = self.f.user

    def test_create_returns_raw_once_and_stores_only_the_hash(self):
        token, raw = tokens.create_token(self.db, self.user, "Claude", 30)
        self.assertTrue(raw.startswith("ork_"))
        self.assertNotEqual(token.token_hash, raw)
        self.assertNotIn(raw, json.dumps(tokens.to_read(token), default=str))
        self.assertEqual(token.token_prefix, raw[:12])
        self.assertEqual(tokens.to_read(token)["status"], "ativo")

    def test_authenticate_revoke_and_expiry(self):
        token, raw = tokens.create_token(self.db, self.user, "Claude", None)
        self.assertEqual(tokens.authenticate(self.db, raw).id, self.user.id)
        self.assertIsNotNone(token.last_used_at)
        self.assertIsNone(tokens.authenticate(self.db, raw + "x"))

        tokens.revoke_token(self.db, self.user.id, token.id)
        self.assertIsNone(tokens.authenticate(self.db, raw))
        self.assertEqual(tokens.to_read(token)["status"], "revogado")

        expired, raw2 = tokens.create_token(self.db, self.user, "velho", 1)
        expired.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        self.db.commit()
        self.assertIsNone(tokens.authenticate(self.db, raw2))
        self.assertEqual(tokens.to_read(expired)["status"], "expirado")

    def test_validation_and_ownership(self):
        with self.assertRaises(ValidationException):
            tokens.create_token(self.db, self.user, "  ", 30)
        with self.assertRaises(ValidationException):
            tokens.create_token(self.db, self.user, "x", 0)
        token, _ = tokens.create_token(self.db, self.user, "x", 30)
        with self.assertRaises(Exception):
            tokens.revoke_token(self.db, self.user.id + 99, token.id)

    def test_user_from_token_accepts_integration_token_and_keeps_jwt(self):
        _, raw = tokens.create_token(self.db, self.user, "Claude", 30)
        self.assertEqual(user_from_token(raw, self.db).id, self.user.id)
        self.assertEqual(user_from_token(create_access_token(self.user.id), self.db).id, self.user.id)
        with self.assertRaises(UnauthorizedException):
            user_from_token("ork_nao-existe", self.db)
        with self.assertRaises(UnauthorizedException):
            user_from_token("lixo", self.db)

    def test_blocked_user_token_stops_working(self):
        _, raw = tokens.create_token(self.db, self.user, "Claude", 30)
        self.user.active = False
        self.db.commit()
        with self.assertRaises(ForbiddenException):
            user_from_token(raw, self.db)


class McpHandlerTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner("SRV-RPA-01")
        self.auto, self.version = self.f.automation(runners=[self.runner])
        self.db.commit()

    def rpc(self, method, params=None, id_=1):
        message = {"jsonrpc": "2.0", "id": id_, "method": method}
        if params is not None:
            message["params"] = params
        return mcp_server._handle(message, self.db, self.f.user)

    def call(self, name, **arguments):
        result = self.rpc("tools/call", {"name": name, "arguments": arguments})["result"]
        text = result["content"][0]["text"]
        return result, (text if result["isError"] else json.loads(text))

    def test_initialize_and_list(self):
        init = self.rpc("initialize", {"protocolVersion": "2025-03-26"})["result"]
        self.assertEqual(init["protocolVersion"], "2025-03-26")
        self.assertIn("tools", init["capabilities"])
        self.assertEqual(self.rpc("initialize", {"protocolVersion": "1999"})["result"]["protocolVersion"], "2025-06-18")

        listed = self.rpc("tools/list")["result"]["tools"]
        self.assertEqual(len(listed), len(TOOLS))
        by_name = {t["name"]: t for t in listed}
        self.assertTrue(by_name["resumo_do_dia"]["annotations"]["readOnlyHint"])
        self.assertFalse(by_name["criar_task"]["annotations"]["readOnlyHint"])
        for tool in listed:
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_protocol_errors(self):
        self.assertIsNone(mcp_server._handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, self.db, self.f.user))
        self.assertEqual(self.rpc("metodo/inexistente")["error"]["code"], mcp_server.METHOD_NOT_FOUND)
        self.assertEqual(self.rpc("tools/call", {"name": "nao_existe"})["error"]["code"], mcp_server.INVALID_PARAMS)
        self.assertEqual(mcp_server._handle({"id": 1}, self.db, self.f.user)["error"]["code"], mcp_server.INVALID_REQUEST)

    def test_read_only_tools(self):
        now = datetime.now(UTC)
        task = self.f.task(self.auto, self.version, TaskStatus.ERROR, runner=self.runner,
                           started_at=now - timedelta(minutes=5), finished_at=now, final_message="Falhou no SAP")
        self.db.add(TaskError(task_id=task.id, error_type="SapError", message="Tela não abriu",
                              stacktrace="Traceback ..."))
        self.db.commit()

        _, summary = self.call("resumo_do_dia")
        self.assertEqual(summary["com_erro"], 1)

        _, detail = self.call("detalhe_task", task_id=task.id)
        self.assertEqual(detail["status"], "error")
        self.assertIn("Tela não abriu", json.dumps(detail, ensure_ascii=False))

        _, machine = self.call("status_maquina", maquina="SRV-RPA-01")
        self.assertTrue(machine["online"])

        _, last = self.call("ultimas_execucoes")
        self.assertEqual(last["execucoes"][0]["task_id"], task.id)

        result, _ = self.call("detalhe_task", task_id=987654)
        self.assertTrue(result["isError"])

    def test_create_and_stop_task(self):
        result, created = self.call("criar_task", automacao=self.auto.name, parametros={"filial": "010"})
        self.assertFalse(result["isError"])
        task = self.db.get(Task, created["task_id"])
        self.assertEqual(task.status, TaskStatus.WAITING)
        self.assertEqual(task.created_by, self.f.user.id)

        duplicate, _ = self.call("criar_task", automacao=self.auto.name)
        self.assertTrue(duplicate["isError"])

        _, stopped = self.call("parar_task", task_id=task.id)
        self.assertEqual(stopped["status"], "canceled")

    def test_pause_and_reactivate_schedule(self):
        schedule = Schedule(name="diario", automation_id=self.auto.id, schedule_type=ScheduleType.CRON,
                            cron_expression="0 8 * * *", policy=SchedulePolicy.CREATE_ALWAYS,
                            status=ScheduleStatus.ACTIVE, active=True, timezone="America/Sao_Paulo")
        self.db.add(schedule)
        self.db.commit()

        self.call("pausar_agendamento", agendamento_id=schedule.id)
        self.db.refresh(schedule)
        self.assertEqual((schedule.status, schedule.active), (ScheduleStatus.PAUSED, False))

        self.call("reativar_agendamento", agendamento_id=schedule.id)
        self.db.refresh(schedule)
        self.assertEqual((schedule.status, schedule.active), (ScheduleStatus.ACTIVE, True))


async def _inline(func, *args):
    # sqlite em memória é uma conexão por thread: roda na mesma thread do teste.
    return func(*args)


class McpHttpTests(unittest.TestCase):
    """Chama o endpoint direto (o venv não tem httpx para o TestClient)."""

    def setUp(self):
        self.f = Fixture()
        self.f.db.commit()

    def post(self, body, token=None):
        raw_body = json.dumps(body).encode()
        headers = [(b"content-type", b"application/json")]
        if token:
            headers.append((b"authorization", f"Bearer {token}".encode()))

        async def receive():
            return {"type": "http.request", "body": raw_body, "more_body": False}

        request = Request({"type": "http", "method": "POST", "path": "/mcp", "headers": headers, "query_string": b""}, receive)
        with mock.patch.object(mcp_server, "run_in_threadpool", _inline):
            return asyncio.run(mcp_server.mcp_endpoint(request, db=self.f.db))

    def test_requires_a_valid_token(self):
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        response = self.post(ping)
        self.assertEqual(response.status_code, 401)
        self.assertIn("Bearer", response.headers["www-authenticate"])
        self.assertEqual(self.post(ping, "ork_invalido").status_code, 401)

        _, raw = tokens.create_token(self.f.db, self.f.user, "Claude", 30)
        self.assertEqual(json.loads(self.post(ping, raw).body), {"jsonrpc": "2.0", "id": 1, "result": {}})

    def test_notifications_batch_and_no_stream(self):
        _, raw = tokens.create_token(self.f.db, self.f.user, "Claude", 30)
        self.assertEqual(self.post({"jsonrpc": "2.0", "method": "notifications/initialized"}, raw).status_code, 202)
        batch = self.post([{"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}], raw)
        self.assertEqual([r["id"] for r in json.loads(batch.body)], [1, 2])
        self.assertEqual(mcp_server.mcp_no_stream().status_code, 405)


class DocsAndIntegrationTests(unittest.TestCase):
    def test_public_docs_are_off_by_default(self):
        from app.main import app

        paths = {route.path for route in app.routes}
        self.assertFalse(paths & {"/docs", "/redoc", "/openapi.json"})
        for expected in ("/mcp", "/api/v1/integration/openapi", "/api/v1/integration/mcp-info", "/api/v1/api-tokens/"):
            self.assertIn(expected, paths)

    def test_documented_openapi_adds_the_guide(self):
        from app.api.v1 import integration
        from app.main import app

        guide = {"GET /api/v1/tasks/": {"summary": "Lista as tasks", "description": "Explicação"}}
        with mock.patch.object(integration, "GUIDE", guide), mock.patch.object(integration, "TAG_GUIDE", {"Tasks": "Grupo"}):
            spec = integration.build_documented_openapi(app)
        operation = spec["paths"]["/api/v1/tasks/"]["get"]
        self.assertEqual(operation["summary"], "Lista as tasks")
        self.assertEqual(operation["x-orkaflow-guide"]["description"], "Explicação")
        self.assertIn({"name": "Tasks", "description": "Grupo"}, spec["tags"])
        # Não altera o OpenAPI em cache da aplicação.
        self.assertNotIn("x-orkaflow-guide", app.openapi()["paths"]["/api/v1/tasks/"]["get"])

    def test_every_route_has_a_guide(self):
        from app.integration.api_guide import GUIDE
        from app.main import app

        keys = {
            f"{method.upper()} {path}"
            for path, item in app.openapi()["paths"].items()
            for method in item
            if method in ("get", "post", "put", "patch", "delete")
        }
        self.assertEqual(sorted(keys - set(GUIDE)), [])


if __name__ == "__main__":
    unittest.main()
