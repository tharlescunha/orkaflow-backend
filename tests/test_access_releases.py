"""Nov/2026: "liberar acesso". Alguém avisa no painel que um usuário bloqueado (ex.: aprovador do SAP) já está ok;
o robô recebe `LIBERACOES_DE_ACESSO` (login -> horário) junto com as variáveis e ignora as recusas anteriores a ele.
Guardado em system_settings (sem tabela nova)."""
import json
import unittest
from datetime import UTC, datetime, timedelta

from app.core.exceptions import ValidationException
from app.domain.enums import TaskStatus
from app.models.env_variable import EnvVariable
from app.models.system_setting import SystemSetting
from app.services import env_variable_service
from app.services.access_release_service import ENV_NAME, SETTING_KEY, AccessReleaseService

from tests.test_concurrency_watchdog import Fixture

T0 = datetime(2026, 11, 17, 14, 10, 0, tzinfo=UTC)


class _Base(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.svc = AccessReleaseService(self.db)
        self.user = self.f.user

    def _task(self):
        runner = self.f.runner("r1")
        auto, ver = self.f.automation(runners=[runner])
        return self.f.task(auto, ver, TaskStatus.RUNNING, runner=runner)


class LiberarTests(_Base):
    def test_libera_normaliza_o_login_e_guarda_quem_e_quando(self):
        item = self.svc.release("  lezanatta ", self.user, system="SAP", note="Senha trocada pelo próprio", now=T0)
        self.db.rollback()  # tem que estar gravado

        rows = AccessReleaseService(self.db).list(now=T0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["login"], "LEZANATTA")
        self.assertEqual(rows[0]["system"], "SAP")
        self.assertEqual(rows[0]["note"], "Senha trocada pelo próprio")
        self.assertEqual(rows[0]["released_at"], "2026-11-17T14:10:00Z")
        self.assertEqual(rows[0]["released_by_id"], self.user.id)
        self.assertEqual(rows[0]["released_by_name"], self.user.name)
        self.assertTrue(rows[0]["active"])
        self.assertEqual(item["login"], "LEZANATTA")

    def test_login_vazio_ou_com_espaco_no_meio_e_recusado(self):
        for bad in ("", "   ", "dois nomes", "x" * 81):
            with self.assertRaises(ValidationException):
                self.svc.release(bad, self.user, now=T0)
        self.assertEqual(self.svc.list(now=T0), [])

    def test_historico_mais_novo_primeiro_e_marca_o_que_ainda_vale(self):
        self.svc.release("antigo", self.user, now=T0 - timedelta(hours=60))
        self.svc.release("recente", self.user, now=T0 - timedelta(hours=1))
        rows = self.svc.list(now=T0)
        self.assertEqual([r["login"] for r in rows], ["RECENTE", "ANTIGO"])
        self.assertEqual([r["active"] for r in rows], [True, False])

    def test_historico_tem_teto(self):
        for i in range(305):
            self.svc.release(f"u{i}", self.user, now=T0 + timedelta(seconds=i))
        rows = self.svc.list(now=T0 + timedelta(seconds=400))
        self.assertEqual(len(rows), 300)
        self.assertEqual(rows[0]["login"], "U304")


class ValorParaOsRobosTests(_Base):
    def test_so_as_ultimas_48h_e_a_mais_nova_por_login(self):
        self.svc.release("lezanatta", self.user, now=T0 - timedelta(hours=5))
        self.svc.release("lezanatta", self.user, now=T0 - timedelta(hours=1))
        self.svc.release("outro", self.user, now=T0 - timedelta(hours=49))
        self.assertEqual(self.svc.env_value(now=T0), {"LEZANATTA": "2026-11-17T13:10:00Z"})

    def test_sem_liberacao_valendo_nao_ha_valor(self):
        self.assertEqual(self.svc.env_value(now=T0), {})
        self.assertIsNone(self.svc.env_json(now=T0))


class EntregaAoRoboTests(_Base):
    def test_resolve_for_task_so_injeta_quando_ha_liberacao_valendo(self):
        task = self._task()
        antes = env_variable_service.resolve_for_task(self.db, task)
        self.assertNotIn(ENV_NAME, antes["variables"])

        self.svc.release("lezanatta", self.user)
        depois = env_variable_service.resolve_for_task(self.db, task)
        valor = json.loads(depois["variables"][ENV_NAME])
        self.assertEqual(list(valor), ["LEZANATTA"])
        self.assertTrue(valor["LEZANATTA"].endswith("Z"))
        self.assertNotIn(ENV_NAME, depois["secret_names"])

    def test_variavel_explicita_com_o_mesmo_nome_vence(self):
        task = self._task()
        self.db.add(EnvVariable(name=ENV_NAME, scope_type="global", scope_id=0, value="{}", is_secret=False, active=True))
        self.db.flush()
        self.svc.release("lezanatta", self.user)
        self.assertEqual(env_variable_service.resolve_for_task(self.db, task)["variables"][ENV_NAME], "{}")

    def test_configuracao_corrompida_nao_quebra_a_entrega_das_variaveis(self):
        task = self._task()
        self.db.add(SystemSetting(key=SETTING_KEY, value="isto não é json"))
        self.db.flush()
        result = env_variable_service.resolve_for_task(self.db, task)
        self.assertNotIn(ENV_NAME, result["variables"])
        # e uma nova liberação conserta o registro
        self.svc.release("lezanatta", self.user)
        self.assertEqual([r["login"] for r in self.svc.list()], ["LEZANATTA"])


if __name__ == "__main__":
    unittest.main()
