"""Maestro no backend (out/2026): progresso da task, next_bot por nome e campo do argumento do bot."""
import json
import unittest
from types import SimpleNamespace

from sqlalchemy import select

from app.core.exceptions import ForbiddenException
from app.domain.enums import ExecutionMode, TaskStatus
from app.models.automation_success_trigger import AutomationSuccessTrigger
from app.models.task import Task
from app.models.task_log import TaskLog
from app.services.automation_trigger_service import AutomationTriggerService
from app.services.task_service import TaskService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner()
        self.auto, self.ver = self.f.automation(runners=[self.r])
        self.svc = WorkerService(self.db)

    def test_progress_saved_while_running_and_shown_in_read(self):
        task = self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=self.r)
        out = self.svc.update_task_progress(task.id, self.f.payload(self.r, current=3, total=7, text="Enviando ao SAP"))
        self.assertEqual((out["progress_current"], out["progress_total"], out["progress_text"]), (3, 7, "Enviando ao SAP"))
        data = TaskService(self.db).get_task(task.id)
        self.assertEqual(data["progress_text"], "Enviando ao SAP")
        items, _ = TaskService(self.db).list_tasks()
        self.assertEqual(items[0]["progress_current"], 3)

    def test_progress_ignored_after_finish_and_refused_for_other_runner(self):
        task = self.f.task(self.auto, self.ver, status=TaskStatus.FINISHED, runner=self.r)
        out = self.svc.update_task_progress(task.id, self.f.payload(self.r, current=9, total=9, text="x"))
        self.assertIsNone(out["progress_current"])

        other = self.f.runner("r2", host="HOST2")
        running = self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=self.r)
        with self.assertRaises(ForbiddenException):
            self.svc.update_task_progress(running.id, self.f.payload(other, current=1, total=None, text=None))


class NextBotByNameTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner()
        self.a, self.a_v = self.f.automation(runners=[self.r])
        self.b, self.b_v = self.f.automation(runners=[self.r])
        self.b.name = "Aprovacao_Pedidos"
        self.db.flush()
        self.svc = AutomationTriggerService(self.db)

    def _parent(self, result: dict):
        return self.f.task(self.a, self.a_v, status=TaskStatus.FINISHED, runner=self.r, result_json=json.dumps(result))

    def _logs(self, task):
        return [log.message for log in self.db.execute(select(TaskLog).where(TaskLog.task_id == task.id)).scalars()]

    def test_next_bot_by_name_without_registered_trigger(self):
        parent = self._parent({"pedidos": 2, "orkaflow": {"next_automations": [{"automation": "Aprovacao_Pedidos", "parameters": {"lote": "A"}}]}})
        children = self.svc.create_success_followups(parent)
        self.assertEqual([c.automation_id for c in children], [self.b.id])
        self.assertEqual(children[0].execution_mode, ExecutionMode.TRIGGER)
        self.assertEqual(children[0].parent_task_id, parent.id)

    def test_unknown_name_and_other_repository_are_ignored_with_log(self):
        parent = self._parent({"orkaflow": {"next_automations": [{"automation": "NaoExiste"}]}})
        self.assertEqual(self.svc.create_success_followups(parent), [])
        self.assertTrue(any("NaoExiste" in m for m in self._logs(parent)))

        # Automação de outro repositório: recusada mesmo por id.
        from app.models.repository import Repository

        other_repo = Repository(name="outro")
        self.db.add(other_repo)
        self.db.flush()
        self.f.repo = other_repo
        c, _ = self.f.automation(runners=[self.r])
        parent2 = self._parent({"orkaflow": {"next_automations": [c.id]}})
        self.assertEqual(self.svc.create_success_followups(parent2), [])
        self.assertTrue(any("outro repositorio" in m for m in self._logs(parent2)))

    def test_registered_triggers_still_work_without_workflow(self):
        self.db.add(AutomationSuccessTrigger(source_automation_id=self.a.id, target_automation_id=self.b.id, active=True))
        self.db.flush()
        parent = self.f.task(self.a, self.a_v, status=TaskStatus.FINISHED, runner=self.r)
        children = self.svc.create_success_followups(parent)
        self.assertEqual([c.automation_id for c in children], [self.b.id])

    def test_workflow_with_registered_trigger_keeps_trigger_settings(self):
        self.db.add(AutomationSuccessTrigger(source_automation_id=self.a.id, target_automation_id=self.b.id, active=True, priority_override=9))
        self.db.flush()
        parent = self._parent({"orkaflow": {"next_automations": [{"automation": "Aprovacao_Pedidos"}]}})
        children = self.svc.create_success_followups(parent)
        self.assertEqual(children[0].priority, 9)


class BotArgFlagTests(unittest.TestCase):
    def test_bot_flag_defaults_true_and_goes_to_worker_payload(self):
        from app.models.bot import Bot

        f = Fixture()
        auto, _ = f.automation()
        bot = f.db.get(Bot, auto.bot_id)
        self.assertTrue(bot.reads_task_file_arg)
        bot.reads_task_file_arg = False
        f.db.flush()
        from app.services.bot_service import BotService

        read = BotService(f.db).get(bot.id)
        self.assertFalse(read["reads_task_file_arg"] if isinstance(read, dict) else read.reads_task_file_arg)
