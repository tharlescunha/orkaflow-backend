"""Health: a última task de cada automação vem por MAX(id) (o ROW_NUMBER sobre todas as tasks levava ~7 s)."""
import unittest
from datetime import UTC, datetime, timedelta

from app.domain.enums import TaskStatus
from app.services.automation_health_service import AutomationHealthService
from app.repositories.runner_repository import RunnerRepository
from tests.test_concurrency_watchdog import Fixture


class HealthLastTasksTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner()
        self.now = datetime.now(UTC)

    def test_latest_task_per_automation(self):
        a1, v1 = self.f.automation()
        a2, v2 = self.f.automation()
        a3, _ = self.f.automation()  # sem task
        self.f.task(a1, v1, TaskStatus.FINISHED, started_at=self.now - timedelta(hours=2), finished_at=self.now - timedelta(hours=1))
        latest_a1 = self.f.task(a1, v1, TaskStatus.ERROR, runner=self.runner, started_at=self.now - timedelta(minutes=10))
        latest_a2 = self.f.task(a2, v2, TaskStatus.RUNNING, runner=self.runner, started_at=self.now)
        self.db.commit()

        tasks = {t.automation_id: t for t in AutomationHealthService._load_last_tasks(self.db, [a1.id, a2.id, a3.id])}
        self.assertEqual({a1.id: latest_a1.id, a2.id: latest_a2.id}, {k: v.id for k, v in tasks.items()})
        self.assertEqual(tasks[a1.id].runner.name, self.runner.name)

        items = AutomationHealthService.list(self.db)["items"]
        by_id = {i["automation_id"]: i for i in items}
        self.assertTrue(by_id[a1.id]["has_recent_error"])
        self.assertTrue(by_id[a2.id]["has_running_task"])
        self.assertIsNone(by_id[a3.id]["last_execution_at"])

    def test_manual_automation_is_never_overdue(self):
        manual, version = self.f.automation()
        never_ran, _ = self.f.automation()
        self.f.task(manual, version, TaskStatus.FINISHED, runner=self.runner,
                    started_at=self.now - timedelta(days=40), finished_at=self.now - timedelta(days=40))
        self.db.commit()

        by_id = {i["automation_id"]: i for i in AutomationHealthService.list(self.db)["items"]}
        self.assertFalse(by_id[manual.id]["is_overdue"])
        self.assertEqual(by_id[manual.id]["health_status"], "success")
        self.assertTrue(by_id[manual.id]["has_recent_success"])
        self.assertFalse(by_id[never_ran.id]["is_overdue"])
        self.assertEqual(by_id[never_ran.id]["health_status"], "warning")  # nunca rodou: atenção, não atraso

    # ---------------------------------------------------------------- task agendada para o futuro
    def _item(self, automation):
        by_id = {i["automation_id"]: i for i in AutomationHealthService.list(self.db)["items"]}
        return by_id[automation.id]

    def test_task_agendada_para_o_futuro_nao_e_atraso(self):
        auto, version = self.f.automation()
        start = self.now + timedelta(hours=8)
        self.f.task(auto, version, TaskStatus.SCHEDULED, requested_start_at=start,
                    last_update_at=self.now - timedelta(hours=2))
        self.db.commit()

        item = self._item(auto)
        self.assertEqual(item["health_status"], "scheduled")
        self.assertEqual(item["status_color"], "blue")
        self.assertFalse(item["is_overdue"])
        self.assertEqual(item["scheduled_start_at"].replace(tzinfo=UTC), start.replace(tzinfo=UTC))
        # Nada rodou: a "última execução" não pode ser a hora em que a task foi criada.
        self.assertIsNone(item["last_execution_at"])
        self.assertFalse(item["has_recent_success"])
        self.assertFalse(item["has_recent_error"])

    def test_agendada_com_horario_ja_vencido_volta_ao_comportamento_antigo(self):
        auto, version = self.f.automation()
        self.f.task(auto, version, TaskStatus.SCHEDULED, requested_start_at=self.now - timedelta(minutes=5))
        self.db.commit()

        item = self._item(auto)
        # O promotor deveria ter liberado: se ainda está assim, não é "agendada", é algo a olhar.
        self.assertEqual(item["health_status"], "warning")
        self.assertIsNone(item["scheduled_start_at"])

    def test_task_na_fila_nao_mostra_hora_de_criacao_como_execucao(self):
        auto, version = self.f.automation()
        self.f.task(auto, version, TaskStatus.WAITING)
        self.db.commit()

        item = self._item(auto)
        self.assertIsNone(item["last_execution_at"])
        self.assertIsNone(item["scheduled_start_at"])

    def test_task_que_rodou_continua_mostrando_a_execucao_real(self):
        auto, version = self.f.automation()
        finished = self.now - timedelta(minutes=20)
        self.f.task(auto, version, TaskStatus.FINISHED, runner=self.runner,
                    started_at=self.now - timedelta(minutes=30), finished_at=finished)
        self.db.commit()

        item = self._item(auto)
        self.assertEqual(item["health_status"], "success")
        self.assertIsNotNone(item["last_execution_at"])
        self.assertIsNone(item["scheduled_start_at"])

    def test_runner_last_execution_and_total_seconds(self):
        a1, v1 = self.f.automation()
        self.f.task(a1, v1, TaskStatus.FINISHED, runner=self.runner,
                    started_at=self.now - timedelta(minutes=30), finished_at=self.now - timedelta(minutes=20))
        newest = self.f.task(a1, v1, TaskStatus.FINISHED, runner=self.runner,
                             started_at=self.now - timedelta(minutes=5), finished_at=self.now - timedelta(minutes=2))
        self.db.commit()

        repo = RunnerRepository(self.db)
        self.assertEqual(repo.get_last_execution_task(self.runner.id).id, newest.id)
        self.assertEqual(repo.get_total_execution_seconds(self.runner.id), 10 * 60 + 3 * 60)


if __name__ == "__main__":
    unittest.main()
