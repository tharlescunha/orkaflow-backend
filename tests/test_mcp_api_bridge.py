"""MCP: guia "como fazer" e ponte com a API (buscar, detalhar e chamar qualquer rota do painel)."""
import asyncio
import json
import unittest
from unittest import mock

from fastapi import FastAPI
from sqlalchemy import create_engine as real_create_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

import tests.test_concurrency_watchdog as watchdog_tests
from app.api.router import api_router
from app.core.database import get_db
from app.domain.enums import UserRole
from app.mcp import server as mcp_server
from app.mcp.playbooks import PLAYBOOKS
from app.models.automation_runner import AutomationRunner
from app.models.user import User
from app.services import api_token_service as tokens


def _shared_engine(url, **kwargs):
    # A chamada interna roda o endpoint em outra thread: todas precisam ver o mesmo banco em memória.
    return real_create_engine(url, poolclass=StaticPool, connect_args={"check_same_thread": False})


class BridgeTests(unittest.TestCase):
    def setUp(self):
        with mock.patch.object(watchdog_tests, "create_engine", _shared_engine):
            self.f = watchdog_tests.Fixture()
        self.runner = self.f.runner("SRV-RPA-01")
        self.auto, _ = self.f.automation()
        self.f.db.commit()
        _, self.token = tokens.create_token(self.f.db, self.f.user, "teste", 30)

        self.app = FastAPI()
        self.app.include_router(api_router, prefix="/api/v1")
        self.app.include_router(mcp_server.router)
        self.app.dependency_overrides[get_db] = lambda: self.f.db

    def mcp(self, method, params=None, token=None):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
        headers = [(b"content-type", b"application/json"),
                   (b"authorization", f"Bearer {token or self.token}".encode())]

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        async def run():
            scope = {"type": "http", "method": "POST", "path": "/mcp", "headers": headers,
                     "query_string": b"", "app": self.app}
            return await mcp_server.mcp_endpoint(Request(scope, receive), db=self.f.db)

        return json.loads(asyncio.run(run()).body)

    def tool(self, name, **arguments):
        result = self.mcp("tools/call", {"name": name, "arguments": arguments})["result"]
        text = result["content"][0]["text"]
        try:
            data = json.loads(text)
        except ValueError:
            data = text
        return result["isError"], data

    def test_new_tools_are_listed(self):
        names = {t["name"] for t in self.mcp("tools/list")["result"]["tools"]}
        self.assertTrue({"como_fazer", "buscar_rotas", "detalhe_rota", "chamar_api"} <= names)

    def test_how_to_guide(self):
        _, general = self.tool("como_fazer")
        self.assertEqual(sorted(general["assuntos"]), sorted(PLAYBOOKS))
        _, schedules = self.tool("como_fazer", assunto="agendamentos")
        self.assertIn("POST /api/v1/schedules/", schedules["guia"])

    def test_search_and_detail(self):
        _, groups = self.tool("buscar_rotas")
        names = {g["grupo"] for g in groups["grupos"]}
        self.assertIn("Automations", names)
        self.assertFalse([n for n in names if n.startswith("Worker") or n == "Tokens de integração"])

        _, found = self.tool("buscar_rotas", busca="vincula maquina automacao")
        self.assertIn("POST /api/v1/automations/{automation_id}/runners", [r["rota"] for r in found["rotas"]])

        _, found = self.tool("buscar_rotas", busca="criar agendamento")
        self.assertEqual(found["rotas"][0]["rota"], "POST /api/v1/schedules/")

        _, detail = self.tool("detalhe_rota", rota="POST /api/v1/schedules/")
        fields = {f["nome"]: f for f in detail["corpo"]}
        self.assertTrue(fields["name"]["obrigatorio"])
        self.assertIn("cron", fields["schedule_type"]["tipo"])
        self.assertIn("exemplo_corpo", detail)

    def test_call_reads_and_writes_with_the_users_permissions(self):
        failed, listed = self.tool("chamar_api", metodo="GET", caminho="/api/v1/automations")
        self.assertFalse(failed)
        self.assertEqual(listed["status"], 200)

        failed, linked = self.tool("chamar_api", metodo="POST",
                                   caminho=f"/api/v1/automations/{self.auto.id}/runners",
                                   corpo={"runner_id": self.runner.id})
        self.assertFalse(failed, linked)
        self.assertEqual(self.f.db.query(AutomationRunner).filter_by(automation_id=self.auto.id).count(), 1)

        failed, duplicate = self.tool("chamar_api", metodo="POST",
                                      caminho=f"/api/v1/automations/{self.auto.id}/runners",
                                      corpo={"runner_id": self.runner.id})
        self.assertTrue(failed)
        self.assertEqual(duplicate["status"], 409)

    def test_non_admin_gets_403_from_admin_routes(self):
        viewer = User(name="v", login="v", email="v@x", password_hash="x", role=UserRole.VIEWER)
        self.f.db.add(viewer)
        self.f.db.commit()
        _, raw = tokens.create_token(self.f.db, viewer, "viewer", 30)
        result = self.mcp("tools/call", {"name": "chamar_api", "arguments": {
            "metodo": "POST", "caminho": "/api/v1/env-variables/",
            "corpo": {"name": "X", "scope_type": "global", "value": "1"}}}, token=raw)["result"]
        self.assertTrue(result["isError"])
        self.assertEqual(json.loads(result["content"][0]["text"])["status"], 403)

    def test_blocked_routes(self):
        for method, path in [
            ("GET", "/api/v1/credentials/1/items/1/reveal"),
            ("POST", "/api/v1/worker/heartbeat/"),
            ("PUT", f"/api/v1/users/{self.f.user.id}"),
            ("POST", "/api/v1/api-tokens/"),
            ("POST", "/api/v1/auth/login"),
        ]:
            failed, message = self.tool("chamar_api", metodo=method, caminho=path, corpo={} if method != "GET" else None)
            self.assertTrue(failed, path)
            self.assertIn("indisponível no MCP", message if isinstance(message, str) else "", path)

        failed, message = self.tool("chamar_api", metodo="GET", caminho="/api/v1/nao-existe")
        self.assertTrue(failed)
        self.assertIn("não existe", message)


if __name__ == "__main__":
    unittest.main()
