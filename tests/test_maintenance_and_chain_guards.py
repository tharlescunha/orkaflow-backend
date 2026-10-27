"""Validação de outubro/2026: a caixa "Modo manutenção" do Runner Config precisa valer de verdade,
e o gatilho de sucesso (encadeamento) não pode entrar em ciclo nem derrubar o fechamento da task."""
import unittest

from sqlalchemy import select

from app.core.exceptions import ValidationException
from app.domain.enums import TaskStatus
from app.models.automation_success_trigger import AutomationSuccessTrigger
from app.models.task import Task
from app.models.task_log import TaskLog
from app.services.automation_trigger_service import AutomationTriggerService
from app.services.dispatch_service import DispatchService
from app.services.runner_service import RunnerService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class MaintenanceModeTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.svc = WorkerService(self.db)
        self.r = self.f.runner("r1")
        self.auto, self.ver = self.f.automation(runners=[self.r])

    def _set_maintenance(self, on: bool):
        self.r.config.maintenance_mode = on
        self.db.flush()

    def test_checkbox_blocks_next_task_and_claim(self):
        task = self.f.task(self.auto, self.ver)
        self._set_maintenance(True)

        response = self.svc.get_next_task(self.f.payload(self.r))
        self.assertFalse(response["found"])

        with self.assertRaises(ValidationException):
            self.svc.claim_task(task.id, self.f.payload(self.r))

        self._set_maintenance(False)
        self.svc.claim_task(task.id, self.f.payload(self.r))
        self.db.refresh(task)
        self.assertEqual(task.status, TaskStatus.READY)

    def test_dispatcher_skips_runner_in_maintenance(self):
        other = self.f.runner("r2", host="HOST2")
        auto, ver = self.f.automation(runners=[self.r, other])
        task = self.f.task(auto, ver)
        self._set_maintenance(True)

        DispatchService(self.db).dispatch_pending_tasks()
        self.db.refresh(task)
        self.assertEqual(task.runner_id, other.id)

    def test_manual_task_cannot_be_pinned_to_maintenance_runner(self):
        from types import SimpleNamespace

        from app.services.task_service import TaskService

        self._set_maintenance(True)
        payload = SimpleNamespace(
            automation_id=self.auto.id,
            runner_id=self.r.id,
            priority=5,
            scheduled_for=None,
            timeout_seconds=None,
            inactivity_timeout_seconds=None,
            execution_mode="manual",
            parent_task_id=None,
            correlation_id=None,
            queue_name=None,
            parameters=None,
            runtime_parameters_json=None,
            credentials_json=None,
            bot_version_id=None,
        )
        with self.assertRaises(ValidationException):
            TaskService(self.db).create_manual_task(payload, created_by=self.f.user.id)

    def test_entering_maintenance_returns_queued_tasks_to_other_machines(self):
        """Out/2026: tasks já pré-vinculadas à máquina voltam para a fila ao marcar manutenção."""
        from app.schemas.runner import RunnerConfigUpdate

        other = self.f.runner("r2", host="HOST2")
        auto, ver = self.f.automation(runners=[self.r, other])
        queued = self.f.task(auto, ver, runner=self.r)          # WAITING pré-vinculada à r1
        running = self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=self.r)

        RunnerService(self.db).update_config(self.r.id, RunnerConfigUpdate(maintenance_mode=True))
        self.db.refresh(queued)
        self.db.refresh(running)
        self.assertIsNone(queued.runner_id)
        self.assertIn("manutenção", queued.waiting_reason)
        self.assertEqual(running.runner_id, self.r.id)          # o que roda, termina

        DispatchService(self.db).dispatch_pending_tasks()
        self.db.refresh(queued)
        self.assertEqual(queued.runner_id, other.id)

    def test_panel_shows_maintenance_even_with_running_task(self):
        self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=self.r)
        self._set_maintenance(True)
        read = RunnerService(self.db).get(self.r.id)
        self.assertEqual(read.status, "maintenance")


class ChainGuardTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner()
        self.a, self.a_v = self.f.automation(runners=[self.r])
        self.b, self.b_v = self.f.automation(runners=[self.r])
        self.svc = AutomationTriggerService(self.db)

    def _trigger(self, src, dst):
        self.db.add(AutomationSuccessTrigger(source_automation_id=src.id, target_automation_id=dst.id, active=True))
        self.db.flush()

    def _children(self, parent):
        return list(self.db.execute(select(Task).where(Task.parent_task_id == parent.id)).scalars().all())

    def _logs(self, task):
        return [log.message for log in self.db.execute(select(TaskLog).where(TaskLog.task_id == task.id)).scalars()]

    def test_cycle_a_b_a_stops_at_second_hop(self):
        self._trigger(self.a, self.b)
        self._trigger(self.b, self.a)

        parent = self.f.task(self.a, self.a_v, status=TaskStatus.FINISHED, runner=self.r)
        children = self.svc.create_success_followups(parent)
        self.assertEqual(len(children), 1)
        child = children[0]
        self.assertEqual(child.automation_id, self.b.id)

        # B terminou: não pode criar A de novo (A já está na cadeia).
        child.status = TaskStatus.FINISHED
        self.db.flush()
        grandchildren = self.svc.create_success_followups(child)
        self.assertEqual(grandchildren, [])
        self.assertTrue(any("ciclo" in m for m in self._logs(child)))

    def test_invalid_result_json_keeps_fixed_triggers(self):
        self._trigger(self.a, self.b)
        parent = self.f.task(self.a, self.a_v, status=TaskStatus.FINISHED, runner=self.r, result_json="{nao e json")
        children = self.svc.create_success_followups(parent)
        self.assertEqual([c.automation_id for c in children], [self.b.id])

    def test_trigger_failure_does_not_raise(self):
        self._trigger(self.a, self.b)
        parent = self.f.task(self.a, self.a_v, status=TaskStatus.FINISHED, runner=self.r)

        def boom(*_args, **_kwargs):
            raise RuntimeError("falha simulada no gatilho")

        self.svc._create_followup_task = boom  # noqa: SLF001
        self.assertEqual(self.svc.create_success_followups(parent), [])
        self.assertTrue(any("ignorado" in m for m in self._logs(parent)))
        self.assertEqual(self._children(parent), [])
