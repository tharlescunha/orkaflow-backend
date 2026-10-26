"""GET /automations/ precisa carregar grupos e gatilhos em lote (era 2 queries por automação: timeout no Azure)."""
import unittest

from sqlalchemy import event

from app.models.automation_exclusive_group import (
    AutomationExclusiveGroup,
    AutomationExclusiveGroupMember,
)
from app.models.automation_success_trigger import AutomationSuccessTrigger
from app.services.automation_service import AutomationService
from tests.test_concurrency_watchdog import Fixture


class AutomationListQueryTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.autos = [self.f.automation()[0] for _ in range(12)]

        group_a = AutomationExclusiveGroup(name="sap", capacity=1, active=True)
        group_b = AutomationExclusiveGroup(name="cigam", capacity=1, active=True)
        self.db.add_all([group_a, group_b])
        self.db.flush()
        for auto in self.autos[:5]:
            self.db.add(AutomationExclusiveGroupMember(group_id=group_a.id, automation_id=auto.id))
        for auto in self.autos[3:8]:
            self.db.add(AutomationExclusiveGroupMember(group_id=group_b.id, automation_id=auto.id))
        for source, target in zip(self.autos[:6], self.autos[6:]):
            self.db.add(AutomationSuccessTrigger(source_automation_id=source.id, target_automation_id=target.id,
                                                 active=True, inherit_parent_parameters=True))
        self.db.add(AutomationSuccessTrigger(source_automation_id=self.autos[0].id,
                                             target_automation_id=self.autos[1].id, active=False,
                                             inherit_parent_parameters=True))
        self.db.commit()
        self.db.expire_all()

        self.queries = 0
        engine = self.db.get_bind()

        @event.listens_for(engine, "before_cursor_execute")
        def _count(*_args):
            self.queries += 1

        self.addCleanup(event.remove, engine, "before_cursor_execute", _count)

    def test_list_uses_a_fixed_number_of_queries(self):
        items = AutomationService.list(self.db)
        self.assertEqual(len(items), 12)
        # 1 automações + 1 grupos + 1 membros + 1 gatilhos + 1 alvos dos gatilhos
        self.assertLessEqual(self.queries, 5, f"{self.queries} queries para 12 automações")

    def test_list_matches_single_item_serialization(self):
        listed = {item["id"]: item for item in AutomationService.list(self.db)}
        for auto in self.autos:
            self.db.expire_all()
            single = AutomationService.get_serialized(self.db, auto.id)
            self.assertEqual(listed[auto.id], single, f"automação {auto.id}")

        first = listed[self.autos[0].id]
        self.assertEqual(first["exclusive_group_ids"], [listed[self.autos[0].id]["exclusive_groups"][0]["id"]])
        self.assertEqual(len(first["exclusive_groups"][0]["automation_ids"]), 5)
        self.assertEqual(first["success_trigger_automation_ids"], [self.autos[6].id])  # o inativo fica fora
        self.assertEqual(first["success_triggers"][0]["target_automation_name"], self.autos[6].name)

        fourth = listed[self.autos[3].id]
        self.assertEqual([g["name"] for g in fourth["exclusive_groups"]], ["cigam", "sap"])


if __name__ == "__main__":
    unittest.main()
