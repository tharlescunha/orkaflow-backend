"""Gestão de grupos exclusivos (out/2026): listar com membros e lock atual, editar, desativar, excluir."""
import unittest
from datetime import UTC, datetime

from app.core.exceptions import ConflictException, NotFoundException
from app.domain.enums import LockScopeType, TaskStatus
from app.models.lock import Lock
from app.services.automation_service import AutomationService
from app.services.queue_reasons import describe_wait_reason
from app.repositories.task_repository import TaskRepository

from tests.test_concurrency_watchdog import Fixture


class ExclusiveGroupManagementTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner()
        self.a, self.a_v = self.f.automation(runners=[self.r])
        self.b, self.b_v = self.f.automation(runners=[self.r])

    def _group(self, **kw):
        data = {"name": "sap", "label": "SAP", "description": None, "capacity": 1, "active": True}
        data.update(kw)
        return AutomationService.create_exclusive_group(self.db, data)

    def test_create_with_members_and_list_shows_automations_and_lock(self):
        group = self._group(automation_ids=[self.a.id, self.b.id])
        self.assertEqual(group["automation_ids"], sorted([self.a.id, self.b.id]))
        self.assertEqual({m["name"] for m in group["automations"]}, {self.a.name, self.b.name})
        self.assertIsNone(group["current_lock"])

        running = self.f.task(self.a, self.a_v, status=TaskStatus.RUNNING, runner=self.r)
        self.db.add(
            Lock(
                lock_key=f"exclusive_group:{group['id']}",
                scope_type=LockScopeType.BUSINESS_RESOURCE,
                owner_task_id=running.id,
                runner_id=self.r.id,
                acquired_at=datetime.now(UTC),
                active=True,
            )
        )
        self.db.flush()

        listed = AutomationService.list_exclusive_groups(self.db)
        self.assertEqual(len(listed), 1)
        lock = listed[0]["current_lock"]
        self.assertEqual(lock["task_id"], running.id)
        self.assertEqual(lock["automation_id"], self.a.id)
        self.assertEqual(lock["runner_id"], self.r.id)

    def test_update_renames_replaces_members_and_rejects_duplicate_name(self):
        group = self._group(automation_ids=[self.a.id])
        other = self._group(name="cigam")

        updated = AutomationService.update_exclusive_group(
            self.db, group["id"], {"label": "SAP novo", "automation_ids": [self.b.id]}
        )
        self.assertEqual(updated["label"], "SAP novo")
        self.assertEqual(updated["automation_ids"], [self.b.id])

        with self.assertRaises(ConflictException):
            AutomationService.update_exclusive_group(self.db, other["id"], {"name": "sap"})
        with self.assertRaises(NotFoundException):
            AutomationService.update_exclusive_group(self.db, group["id"], {"automation_ids": [999]})

    def test_deactivated_group_stops_holding_tasks(self):
        group = self._group(automation_ids=[self.a.id, self.b.id])
        self.f.task(self.a, self.a_v, status=TaskStatus.RUNNING, runner=self.r)
        waiting = self.f.task(self.b, self.b_v)
        repo = TaskRepository(self.db)

        self.assertIsNotNone(describe_wait_reason(repo, waiting))

        AutomationService.update_exclusive_group(self.db, group["id"], {"active": False})
        self.assertIsNone(describe_wait_reason(repo, waiting))

    def test_delete_requires_no_members(self):
        group = self._group(automation_ids=[self.a.id])
        with self.assertRaises(ConflictException):
            AutomationService.delete_exclusive_group(self.db, group["id"])

        AutomationService.update_exclusive_group(self.db, group["id"], {"automation_ids": []})
        AutomationService.delete_exclusive_group(self.db, group["id"])
        with self.assertRaises(NotFoundException):
            AutomationService.get_exclusive_group(self.db, group["id"])

    def test_automation_side_still_works(self):
        """O vínculo pela automação (exclusive_group_ids) continua igual."""
        group = self._group()
        AutomationService.update(self.db, self.a.id, {"exclusive_group_ids": [group["id"]]})
        detail = AutomationService.get_exclusive_group(self.db, group["id"])
        self.assertEqual(detail["automation_ids"], [self.a.id])
