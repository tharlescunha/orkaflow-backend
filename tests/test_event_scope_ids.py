"""Out/2026: uma regra de evento vale para vários bots (ou automações) de uma vez (scope_ids)."""
import unittest

from app.core.exceptions import ValidationException
from app.domain.enums import TaskStatus
from app.models.event_rule import EventRun
from app.services import event_service as svc

from tests.test_concurrency_watchdog import Fixture


class EventScopeIdsTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner("r1")
        self.auto1, self.ver1 = self.f.automation(runners=[self.runner])
        self.auto2, self.ver2 = self.f.automation(runners=[self.runner])
        self.auto3, self.ver3 = self.f.automation(runners=[self.runner])

    def _rule(self, **kw):
        data = dict(
            name="Avisar", description=None, active=True, scope_type="bot", scope_id=None, scope_ids=[],
            trigger_type="task_error", trigger_config={}, pre_steps=[], url="http://127.0.0.1:9/hook",
            method="POST", headers={}, body_template="{}", timeout_seconds=5,
        )
        data.update(kw)
        return svc.create_rule(self.db, data, created_by=self.f.user.id)

    def _pending_runs(self, task):
        return self.db.query(EventRun).filter(EventRun.task_id == task.id).count()

    def test_rule_for_two_bots_fires_for_both_and_not_for_the_third(self):
        rule = self._rule(scope_ids=[self.auto1.bot_id, self.auto2.bot_id])
        self.assertEqual(rule.scope_id, self.auto1.bot_id)
        read = svc.rule_to_read(self.db, rule)
        self.assertEqual(read["scope_ids"], [self.auto1.bot_id, self.auto2.bot_id])
        self.assertIn(",", read["scope_label"])

        t1 = self.f.task(self.auto1, self.ver1, status=TaskStatus.ERROR, runner=self.runner)
        t2 = self.f.task(self.auto2, self.ver2, status=TaskStatus.ERROR, runner=self.runner)
        t3 = self.f.task(self.auto3, self.ver3, status=TaskStatus.ERROR, runner=self.runner)
        self.db.commit()
        for task in (t1, t2, t3):
            svc.enqueue_for_task(self.db, task)
        self.assertEqual(self._pending_runs(t1), 1)
        self.assertEqual(self._pending_runs(t2), 1)
        self.assertEqual(self._pending_runs(t3), 0)

    def test_single_scope_id_still_works_and_reads_as_one_item_list(self):
        rule = self._rule(scope_type="automation", scope_id=self.auto2.id)
        self.assertIsNone(rule.scope_ids_json)
        self.assertEqual(svc.rule_to_read(self.db, rule)["scope_ids"], [self.auto2.id])

    def test_duplicates_are_dropped_and_unknown_bot_is_refused(self):
        rule = self._rule(scope_ids=[self.auto1.bot_id, self.auto1.bot_id, self.auto2.bot_id])
        self.assertEqual(svc.rule_to_read(self.db, rule)["scope_ids"], [self.auto1.bot_id, self.auto2.bot_id])
        with self.assertRaises(ValidationException):
            self._rule(scope_ids=[self.auto1.bot_id, 999_999])

    def test_update_can_shrink_to_one_target(self):
        rule = self._rule(scope_ids=[self.auto1.bot_id, self.auto2.bot_id])
        data = svc.rule_to_read(self.db, rule)
        data["scope_ids"] = [self.auto2.bot_id]
        data["scope_id"] = None
        svc.update_rule(self.db, rule.id, data)
        self.db.refresh(rule)
        self.assertEqual(rule.scope_id, self.auto2.bot_id)
        self.assertIsNone(rule.scope_ids_json)
