"""Variáveis de ambiente do robô: escopos com herança, segredos criptografados, endpoint do worker."""
import unittest
from types import SimpleNamespace

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException, ValidationException
from app.domain.enums import TaskStatus
from app.models.env_variable import EnvVariable
from app.services import env_variable_service as svc
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class EnvBase(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r1 = self.f.runner("r1")
        self.r2 = self.f.runner("r2", host="HOST2")
        self.auto, self.version = self.f.automation(runners=[self.r1, self.r2])
        self.other_auto, _ = self.f.automation(runners=[self.r1])

    def add(self, name, value, scope="global", scope_id=None, **kw):
        return svc.create_variable(
            self.db, {"name": name, "value": value, "scope_type": scope, "scope_id": scope_id, **kw}
        )

    def effective(self, auto=None, runner=None):
        rows = svc.effective_variables(self.db, (auto or self.auto).id, runner.id if runner else None)
        return {row["name"]: row for row in rows}


class ImportTests(EnvBase):
    def run_import(self, items, scope="global", scope_id=None, overwrite=False):
        return svc.import_variables(self.db, scope, scope_id, items, overwrite=overwrite)

    def test_creates_valid_and_reports_invalid_and_duplicates(self):
        result = self.run_import([
            {"name": "sap_url", "value": "https://sap"},
            {"name": "SENHA_SAP", "value": "s3cr3t", "is_secret": True},
            {"name": "1INVALIDO", "value": "x"},
            {"name": "PATH", "value": "x"},
            {"name": "SAP_URL", "value": "repetida"},
            {"name": "TOKEN_VAZIO", "value": "", "is_secret": True},
        ])

        self.assertEqual((result["created"], result["errors"]), (2, 4))
        statuses = [(r["name"], r["status"]) for r in result["results"]]
        self.assertEqual(statuses[0], ("SAP_URL", "created"))
        self.assertEqual(statuses[1], ("SENHA_SAP", "created"))
        self.assertEqual(statuses[4], ("SAP_URL", "error"), "repetida no arquivo: vale a primeira")

        stored = {v.name: v for v in svc.list_variables(self.db, "global")}
        self.assertEqual(stored["SAP_URL"].value, "https://sap")
        self.assertNotEqual(stored["SENHA_SAP"].value, "s3cr3t", "segredo fica criptografado")
        self.assertIsNone(svc.to_read(self.db, stored["SENHA_SAP"])["value"])

    def test_existing_are_kept_unless_overwrite(self):
        self.add("DESK_URL", "antigo")

        kept = self.run_import([{"name": "DESK_URL", "value": "novo"}])
        self.assertEqual((kept["skipped"], kept["updated"]), (1, 0))
        self.assertEqual(svc.list_variables(self.db, "global")[0].value, "antigo")

        replaced = self.run_import([{"name": "DESK_URL", "value": "novo"}], overwrite=True)
        self.assertEqual(replaced["updated"], 1)
        self.assertEqual(svc.list_variables(self.db, "global")[0].value, "novo")

    def test_import_into_bot_scope_and_bad_target(self):
        result = self.run_import([{"name": "FILIAL", "value": "001"}], scope="bot", scope_id=self.auto.bot_id)
        self.assertEqual(result["created"], 1)
        self.assertEqual(self.effective()["FILIAL"]["scope_type"], "bot")
        with self.assertRaises(NotFoundException):
            self.run_import([{"name": "X", "value": "1"}], scope="runner", scope_id=9999)


class NameAndScopeValidationTests(EnvBase):
    def test_name_is_uppercased_and_validated(self):
        self.assertEqual(self.add("sap_url", "x").name, "SAP_URL")
        for bad in ("", "1ABC", "TEM ESPACO", "A-B", "PATH", "temp", "ORKAFLOW_TASK_ID", "orkaflow_x"):
            with self.assertRaises(ValidationException, msg=bad):
                self.add(bad, "x")

    def test_duplicate_in_same_scope_conflicts_but_other_scope_is_fine(self):
        self.add("DESK_URL", "a")
        with self.assertRaises(ConflictException):
            self.add("desk_url", "b")
        self.add("DESK_URL", "c", scope="bot", scope_id=self.auto.bot_id)

    def test_scope_target_must_exist_and_global_uses_zero(self):
        with self.assertRaises(NotFoundException):
            self.add("X", "1", scope="runner", scope_id=9999)
        with self.assertRaises(ValidationException):
            self.add("X", "1", scope="bot")
        with self.assertRaises(ValidationException):
            self.add("X", "1", scope="planeta", scope_id=1)
        self.assertEqual(self.add("G", "1", scope_id=77).scope_id, 0)


class InheritanceTests(EnvBase):
    def test_most_specific_scope_wins_with_overrides_listed(self):
        self.add("URL", "global")
        self.add("URL", "bot", scope="bot", scope_id=self.auto.bot_id)
        self.add("URL", "auto", scope="automation", scope_id=self.auto.id)
        self.add("URL", "maquina", scope="runner", scope_id=self.r1.id)

        with_runner = self.effective(runner=self.r1)["URL"]
        self.assertEqual(with_runner["value"], "maquina")
        self.assertEqual(with_runner["scope_type"], "runner")
        self.assertEqual([o["scope_type"] for o in with_runner["overrides"]], ["automation", "bot", "global"])

        self.assertEqual(self.effective()["URL"]["value"], "auto")
        self.assertEqual(self.effective(runner=self.r2)["URL"]["value"], "auto", "outra máquina não pega o valor da r1")

    def test_scopes_only_apply_to_their_targets(self):
        self.add("SO_BOT", "1", scope="bot", scope_id=self.auto.bot_id)
        self.add("SO_AUTO", "1", scope="automation", scope_id=self.auto.id)
        self.add("GLOBAL", "1")

        self.assertEqual(sorted(self.effective(auto=self.other_auto)), ["GLOBAL"])
        self.assertEqual(sorted(self.effective()), ["GLOBAL", "SO_AUTO", "SO_BOT"])

    def test_inactive_variable_is_ignored_and_lower_level_shows_through(self):
        self.add("URL", "global")
        high = self.add("URL", "bot", scope="bot", scope_id=self.auto.bot_id)
        svc.update_variable(self.db, high.id, {"active": False})
        self.assertEqual(self.effective()["URL"]["value"], "global")


class SecretTests(EnvBase):
    def test_secret_is_encrypted_at_rest_and_never_returned(self):
        var = self.add("SAP_SENHA", "s3gredo!", is_secret=True)

        raw = self.db.get(EnvVariable, var.id).value
        self.assertNotIn("s3gredo", raw)
        self.assertIsNone(svc.to_read(self.db, var)["value"])
        self.assertIsNone(self.effective()["SAP_SENHA"]["value"])
        self.assertTrue(self.effective()["SAP_SENHA"]["is_secret"])

    def test_worker_gets_plain_values_and_secret_names(self):
        self.add("SAP_SENHA", "s3gredo!", is_secret=True)
        self.add("SAP_URL", "https://sap", scope="automation", scope_id=self.auto.id)
        task = self.f.task(self.auto, self.version, status=TaskStatus.READY, runner=self.r1)

        resolved = svc.resolve_for_task(self.db, task)

        self.assertEqual(resolved["variables"], {"SAP_SENHA": "s3gredo!", "SAP_URL": "https://sap"})
        self.assertEqual(resolved["secret_names"], ["SAP_SENHA"])

    def test_update_keeps_secret_when_value_omitted_and_handles_secret_toggle(self):
        var = self.add("TOKEN", "abc", is_secret=True)
        svc.update_variable(self.db, var.id, {"description": "nova descrição"})
        self.assertEqual(svc._plain_value(self.db.get(EnvVariable, var.id)), "abc")

        svc.update_variable(self.db, var.id, {"value": "xyz"})
        self.assertEqual(svc._plain_value(self.db.get(EnvVariable, var.id)), "xyz")

        with self.assertRaises(ValidationException):
            svc.update_variable(self.db, var.id, {"is_secret": False})  # exige novo valor

        svc.update_variable(self.db, var.id, {"is_secret": False, "value": "publico"})
        self.assertEqual(svc.to_read(self.db, self.db.get(EnvVariable, var.id))["value"], "publico")

        plain = self.add("PLAIN", "valor")
        svc.update_variable(self.db, plain.id, {"is_secret": True})  # passa a secreta criptografando o atual
        self.assertNotIn("valor", self.db.get(EnvVariable, plain.id).value)
        self.assertEqual(svc._plain_value(self.db.get(EnvVariable, plain.id)), "valor")

    def test_secret_requires_a_value(self):
        with self.assertRaises(ValidationException):
            self.add("VAZIA", "", is_secret=True)


class WorkerEndpointTests(EnvBase):
    def test_worker_only_gets_env_of_its_own_task(self):
        self.add("A", "1")
        task = self.f.task(self.auto, self.version, status=TaskStatus.READY, runner=self.r1)
        service = WorkerService(self.db)

        ok = service.resolve_task_env(task.id, self.f.payload(self.r1))
        self.assertEqual(ok["variables"], {"A": "1"})

        with self.assertRaises(ForbiddenException):
            service.resolve_task_env(task.id, self.f.payload(self.r2))


class SqlServerCompatibilityTests(unittest.TestCase):
    def test_active_rows_query_has_no_boolean_is_for_mssql(self):
        from sqlalchemy.dialects import mssql

        automation = SimpleNamespace(id=1, bot_id=2)
        sql = str(
            svc.active_rows_stmt(automation, 3).compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True})
        )
        self.assertNotIn(" IS 1", sql)
        self.assertIn("= 1", sql)


if __name__ == "__main__":
    unittest.main()
