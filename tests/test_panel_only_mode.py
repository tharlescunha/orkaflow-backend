"""Cópia "só painel" (ex.: Azure): CORS por variável, rotas /worker/* desligáveis e /health sem os processos de fundo."""
import importlib
import json
import unittest
from unittest import mock

from app.core.config import settings


class CorsOriginsTests(unittest.TestCase):
    def test_default_keeps_the_previous_origins(self):
        self.assertEqual(
            type(settings).model_fields["cors_origins"].default.split(","),
            ["http://localhost:5173", "http://127.0.0.1:5173", "http://10.50.156.202:5173"],
        )

    def test_list_is_trimmed_and_without_trailing_slash(self):
        with mock.patch.object(settings, "cors_origins", " https://a.azurestaticapps.net/ , http://x:5173,,"):
            self.assertEqual(settings.cors_origin_list, ["https://a.azurestaticapps.net", "http://x:5173"])


class WorkerRoutesFlagTests(unittest.TestCase):
    def _paths(self):
        import app.api.router as router_module

        router_module = importlib.reload(router_module)
        return {route.path for route in router_module.api_router.routes}

    def tearDown(self):
        import app.api.router as router_module

        importlib.reload(router_module)  # volta ao padrão para os outros testes

    def test_worker_routes_are_mounted_by_default(self):
        paths = self._paths()
        self.assertIn("/worker/heartbeat/", paths)
        self.assertIn("/runners/", paths)

    def test_panel_only_has_no_worker_routes_but_keeps_the_panel(self):
        with mock.patch.object(settings, "enable_worker_api", False):
            paths = self._paths()
        self.assertFalse([p for p in paths if p.startswith("/worker")])
        for expected in ("/runners/", "/tasks/", "/runner-logs/", "/bot-versions/git-preview", "/health"):
            self.assertIn(expected, paths)


class HealthPanelOnlyTests(unittest.TestCase):
    def _call(self, background_status):
        from app.api.v1 import health

        session = mock.MagicMock()
        with mock.patch.object(health, "SessionLocal", return_value=session), \
             mock.patch.object(health, "get_services_status", return_value=background_status):
            response = health.health_check()
        return response.status_code, json.loads(response.body)

    def test_full_mode_without_heartbeats_is_degraded(self):
        status, body = self._call({"services": {}, "supervisor": None})
        self.assertEqual((status, body["status"], body["mode"]), (200, "degraded", "full"))

    def test_panel_only_ignores_background_services(self):
        stale = {"services": {"dispatcher": {"status": "stale"}}, "supervisor": None}
        with mock.patch.object(settings, "health_check_background_workers", False):
            status, body = self._call(stale)
        self.assertEqual((status, body["status"], body["mode"]), (200, "ok", "panel_only"))
        self.assertEqual(set(body["components"]), {"database"})


if __name__ == "__main__":
    unittest.main()
