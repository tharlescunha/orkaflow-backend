"""Fila com explicação e encadeamento visível (out/2026).

- Dispatcher e next-task gravam em waiting_reason por que a task ainda espera.
- next-task pula a candidata presa por grupo exclusivo (não trava a fila inteira).
- Vincular/assumir limpa o motivo. Gatilho de sucesso cria filha com execution_mode=trigger,
  e o detalhe da task lista as filhas.
"""
import unittest

from sqlalchemy import select

from app.domain.enums import ExecutionMode, TaskStatus
from app.models.automation_exclusive_group import (
    AutomationExclusiveGroup,
    AutomationExclusiveGroupMember,
)
from app.models.automation_success_trigger import AutomationSuccessTrigger
from app.models.task_log import TaskLog
from app.services.automation_trigger_service import AutomationTriggerService
from app.services.dispatch_service import DispatchService
from app.services.task_service import TaskService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class QueueReasonTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner("r1", max_concurrency=3)

    def _group(self, *autos):
        group = AutomationExclusiveGroup(name="g", active=True)
        self.db.add(group)
        self.db.flush()
        for auto in autos:
            self.db.add(AutomationExclusiveGroupMember(group_id=group.id, automation_id=auto.id))
        self.db.flush()
        return group

    def _codes(self, task):
        return [
            log.event_code
            for log in self.db.execute(select(TaskLog).where(TaskLog.task_id == task.id)).scalars()
        ]

    def test_dispatcher_explains_automation_busy_and_clears_when_pinned(self):
        auto, ver = self.f.automation(runners=[self.r])
        running = self.f.task(auto, ver, status=TaskStatus.RUNNING, runner=self.r)
        waiting = self.f.task(auto, ver)

        DispatchService(self.db).dispatch_pending_tasks()
        self.db.refresh(waiting)
        self.assertIsNone(waiting.runner_id)
        self.assertIn(f"#{running.id}", waiting.waiting_reason)
        self.assertIn("WAIT_AUTOMATION_BUSY", self._codes(waiting))

        # Segundo ciclo não duplica o log (janela de 1h).
        DispatchService(self.db).dispatch_pending_tasks()
        self.assertEqual(self._codes(waiting).count("WAIT_AUTOMATION_BUSY"), 1)

        running.status = TaskStatus.FINISHED
        self.db.flush()
        DispatchService(self.db).dispatch_pending_tasks()
        self.db.refresh(waiting)
        self.assertEqual(waiting.runner_id, self.r.id)
        self.assertIsNone(waiting.waiting_reason)

    def test_dispatcher_explains_exclusive_group(self):
        a, a_v = self.f.automation(runners=[self.r])
        b, b_v = self.f.automation(runners=[self.r])
        self._group(a, b)
        busy = self.f.task(a, a_v, status=TaskStatus.RUNNING, runner=self.r)
        waiting = self.f.task(b, b_v)

        DispatchService(self.db).dispatch_pending_tasks()
        self.db.refresh(waiting)
        self.assertIsNone(waiting.runner_id)
        self.assertIn("grupo exclusivo", waiting.waiting_reason)
        self.assertIn(f"#{busy.id}", waiting.waiting_reason)
        self.assertIn("WAIT_EXCLUSIVE_GROUP", self._codes(waiting))

    def test_dispatcher_explains_no_runner(self):
        auto, ver = self.f.automation(runners=[])
        waiting = self.f.task(auto, ver)
        DispatchService(self.db).dispatch_pending_tasks()
        self.db.refresh(waiting)
        self.assertIn("nenhum runner", waiting.waiting_reason)

    def test_next_task_skips_task_held_by_exclusive_group(self):
        a, a_v = self.f.automation(runners=[self.r])
        b, b_v = self.f.automation(runners=[self.r])
        c, c_v = self.f.automation(runners=[self.r])
        self._group(a, b)
        self.f.task(a, a_v, status=TaskStatus.RUNNING, runner=self.r)
        held = self.f.task(b, b_v, priority=9)
        free = self.f.task(c, c_v, priority=1)

        svc = WorkerService(self.db)
        response = svc.get_next_task(self.f.payload(self.r))
        self.assertTrue(response["found"])
        self.assertEqual(response["task_id"], free.id)
        self.db.refresh(held)
        self.assertIn("grupo exclusivo", held.waiting_reason)

    def test_claim_clears_waiting_reason(self):
        auto, ver = self.f.automation(runners=[self.r])
        task = self.f.task(auto, ver, waiting_reason="Aguardando runner: ...")
        WorkerService(self.db).claim_task(task.id, self.f.payload(self.r))
        self.db.refresh(task)
        self.assertEqual(task.status, TaskStatus.READY)
        self.assertIsNone(task.waiting_reason)

    def test_read_hides_reason_outside_waiting(self):
        auto, ver = self.f.automation(runners=[self.r])
        task = self.f.task(auto, ver, status=TaskStatus.FINISHED, runner=self.r, waiting_reason="velho")
        data = TaskService(self.db).get_task(task.id)
        self.assertIsNone(data["waiting_reason"])


class ChainVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner()
        self.a, self.a_v = self.f.automation(runners=[self.r])
        self.b, self.b_v = self.f.automation(runners=[self.r])

    def test_trigger_child_has_trigger_mode_and_parent_lists_children(self):
        self.db.add(AutomationSuccessTrigger(source_automation_id=self.a.id, target_automation_id=self.b.id, active=True))
        self.db.flush()
        parent = self.f.task(self.a, self.a_v, status=TaskStatus.FINISHED, runner=self.r)
        children = AutomationTriggerService(self.db).create_success_followups(parent)
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].execution_mode, ExecutionMode.TRIGGER)
        self.assertEqual(children[0].parent_task_id, parent.id)

        data = TaskService(self.db).get_task(parent.id)
        self.assertEqual([c["id"] for c in data["children"]], [children[0].id])
        self.assertEqual(data["children"][0]["execution_mode"], ExecutionMode.TRIGGER)
        self.assertEqual(data["children"][0]["automation_name"], self.b.name)

        child_data = TaskService(self.db).get_task(children[0].id)
        self.assertEqual(child_data["parent_task_id"], parent.id)
        self.assertEqual(child_data["children"], [])
