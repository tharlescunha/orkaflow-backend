"""Out/2026: desativar repositório desativa bots e automações; MCP devolve prints como imagem."""
import base64
import unittest
from datetime import UTC, datetime

from app.domain.enums import TaskStatus
from app.models.automation import Automation
from app.models.bot import Bot
from app.models.task_error import TaskError
from app.mcp import server as mcp_server
from app.schemas.repository import RepositoryUpdate
from app.services.repository_service import RepositoryService

from tests.test_concurrency_watchdog import Fixture

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


class RepositoryCascadeTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner()
        self.a, _ = self.f.automation(runners=[self.r])
        self.b, _ = self.f.automation(runners=[self.r])

    def _states(self):
        bots = [bot.active for bot in self.db.query(Bot).filter(Bot.repository_id == self.f.repo.id).all()]
        autos = [a.active for a in self.db.query(Automation).filter(Automation.repository_id == self.f.repo.id).all()]
        return bots, autos

    def test_delete_deactivates_bots_and_automations(self):
        self.assertEqual(self._states(), ([True, True], [True, True]))
        RepositoryService(self.db).delete(self.f.repo.id)
        self.assertEqual(self._states(), ([False, False], [False, False]))

    def test_update_active_false_cascades_but_true_does_not_reactivate(self):
        svc = RepositoryService(self.db)
        svc.update(self.f.repo.id, RepositoryUpdate(active=False))
        self.assertEqual(self._states(), ([False, False], [False, False]))
        svc.update(self.f.repo.id, RepositoryUpdate(active=True))
        self.assertEqual(self._states(), ([False, False], [False, False]))


class McpImageToolsTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner("SRV-RPA-01")
        self.auto, self.version = self.f.automation(runners=[self.runner])
        self.db.commit()

    def call(self, name, **arguments):
        return mcp_server._handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
            self.db,
            self.f.user,
        )["result"]

    def test_print_do_erro_returns_image_content(self):
        task = self.f.task(self.auto, self.version, TaskStatus.ERROR, runner=self.runner)
        self.db.add(TaskError(task_id=task.id, error_type="SapError", message="Tela não abriu", error_screenshot=PNG_1PX))
        self.db.commit()

        result = self.call("print_do_erro", task_id=task.id)
        self.assertFalse(result["isError"])
        kinds = [c["type"] for c in result["content"]]
        self.assertEqual(kinds, ["text", "image"])
        self.assertEqual(result["content"][1]["mimeType"], "image/png")
        self.assertEqual(base64.b64decode(result["content"][1]["data"]), PNG_1PX)
        self.assertNotIn("_imagens", result["structuredContent"])
        self.assertEqual(result["structuredContent"]["print"]["erro"], "Tela não abriu")

        detail = self.call("detalhe_task", task_id=task.id)["structuredContent"]
        self.assertTrue(detail["tem_print_do_erro"])

    def test_print_do_erro_without_image_explains(self):
        task = self.f.task(self.auto, self.version, TaskStatus.ERROR, runner=self.runner)
        self.db.commit()
        result = self.call("print_do_erro", task_id=task.id)
        self.assertEqual([c["type"] for c in result["content"]], ["text"])
        self.assertIn("screenshot_on_error", result["structuredContent"]["aviso"])

    def test_tela_da_maquina_returns_last_screenshot(self):
        self.runner.last_screenshot_image = PNG_1PX
        self.runner.last_screenshot_at = datetime.now(UTC)
        self.db.commit()
        result = self.call("tela_da_maquina", maquina="SRV-RPA-01")
        self.assertEqual([c["type"] for c in result["content"]], ["text", "image"])
        self.assertIsNone(result["structuredContent"].get("aviso"))

        other = self.f.runner("SEM-PRINT", host="H2")
        self.db.commit()
        result = self.call("tela_da_maquina", maquina="SEM-PRINT")
        self.assertEqual([c["type"] for c in result["content"]], ["text"])
        self.assertIn("ainda não enviou", result["structuredContent"]["aviso"])
