"""Nov/2026: credencial bloqueada por senha errada/expirada.

1) Trocar a senha na tela precisa GRAVAR o desbloqueio (antes só fazia flush e a sessão fechava sem commit).
2) Desbloqueio manual (sem trocar a senha, ex.: o usuário foi liberado direto no SAP) e lista dos bloqueados.
"""
import unittest

from app.core.exceptions import ConflictException, NotFoundException
from app.domain.enums import ScheduleStatus, TaskStatus
from app.models.credential import Credential
from app.schemas.credential import CredentialItemUpdate
from app.services.credential_health_service import PAUSE_REASON, CredentialHealthService
from app.services.credential_service import CredentialService

from tests.test_credential_health import CredentialHealthBase


class _Base(CredentialHealthBase):
    def _bloquear(self, schedule=None):
        task = self._running_task()
        self.svc.report_credential_alert(task.id, self._alert(task))
        task.status = TaskStatus.ERROR
        self.db.commit()  # tudo o que veio até aqui já está gravado
        return task


class TrocarSenhaGravaTests(_Base):
    def test_trocar_a_senha_grava_o_desbloqueio_mesmo_se_a_sessao_fechar_sem_commit(self):
        schedule = self._schedule(self.auto)
        self._bloquear()
        self.db.refresh(schedule)
        self.assertEqual(schedule.status, ScheduleStatus.PAUSED)

        CredentialService(self.db).update_item(self.credential.id, self.item.id, CredentialItemUpdate(value="nova"))
        self.db.rollback()  # fim da requisição: o que não foi confirmado se perde

        self.db.refresh(self.credential)
        self.db.refresh(schedule)
        self.assertEqual(self.credential.status, "nao_verificada")
        self.assertEqual(schedule.status, ScheduleStatus.ACTIVE)


class DesbloqueioManualTests(_Base):
    def test_desbloquear_volta_para_nao_verificada_e_reativa_os_agendamentos(self):
        schedule = self._schedule(self.auto)
        self._bloquear()

        result = CredentialService(self.db).unblock(self.credential.id, user_id=self.f.user.id)
        self.db.rollback()  # tem que estar gravado

        self.db.refresh(self.credential)
        self.db.refresh(schedule)
        self.assertEqual(result["schedules_reactivated"], 1)
        self.assertEqual(self.credential.status, "nao_verificada")
        self.assertIsNone(self.credential.status_reason)
        self.assertEqual(schedule.status, ScheduleStatus.ACTIVE)
        self.assertTrue(schedule.active)
        self.assertIsNone(schedule.paused_reason)

    def test_so_reativa_o_que_a_credencial_pausou(self):
        pausado_por_ela = self._schedule(self.auto)
        outra, _ = self.f.automation(runners=[self.runner])
        pausado_a_mao = self._schedule(outra)
        pausado_a_mao.status = ScheduleStatus.PAUSED
        pausado_a_mao.active = False
        self.db.flush()
        self._bloquear()

        CredentialService(self.db).unblock(self.credential.id)

        self.db.refresh(pausado_por_ela)
        self.db.refresh(pausado_a_mao)
        self.assertEqual(pausado_por_ela.status, ScheduleStatus.ACTIVE)
        self.assertEqual(pausado_a_mao.status, ScheduleStatus.PAUSED)

    def test_task_nova_deixa_de_ser_recusada_depois_de_desbloquear(self):
        from types import SimpleNamespace  # noqa: F401
        from app.services.task_service import TaskService

        self._bloquear()
        with self.assertRaises(ConflictException):
            TaskService(self.db).create_manual_task(self._manual_payload(), created_by=self.f.user.id)

        CredentialService(self.db).unblock(self.credential.id)
        created = TaskService(self.db).create_manual_task(self._manual_payload(), created_by=self.f.user.id)
        self.assertTrue(created["id"])

    def test_se_o_robo_falhar_de_novo_ela_bloqueia_outra_vez(self):
        self._bloquear()
        CredentialService(self.db).unblock(self.credential.id)
        task = self._running_task()
        self.svc.report_credential_alert(task.id, self._alert(task, motivo="senha_incorreta"))
        self.db.refresh(self.credential)
        self.assertEqual(self.credential.status, "senha_incorreta")

    def test_nao_bloqueada_devolve_409_e_inexistente_404(self):
        with self.assertRaises(ConflictException):
            CredentialService(self.db).unblock(self.credential.id)
        with self.assertRaises(NotFoundException):
            CredentialService(self.db).unblock(999999)


class ListaDeBloqueadasTests(_Base):
    def test_lista_so_as_bloqueadas_com_automacoes_e_agendamentos_pausados(self):
        self._schedule(self.auto)
        self._bloquear()
        ok = Credential(label="Outra ok", repository_id=self.auto.repository_id, active=True)
        self.db.add(ok)
        self.db.commit()

        rows = CredentialHealthService(self.db).list_blocked()

        self.assertEqual([r["id"] for r in rows], [self.credential.id])
        row = rows[0]
        self.assertEqual(row["label"], "SAP produção")
        self.assertEqual(row["status"], "senha_expirada")
        self.assertEqual(row["status_label"], "senha expirada")
        self.assertIn("SAP", row["status_reason"])
        self.assertEqual(row["schedules_paused"], 1)
        self.assertEqual([a["id"] for a in row["automations"]], [self.auto.id])
        self.assertIsNotNone(row["status_updated_at"])

    def test_lista_vazia_quando_nada_esta_bloqueado(self):
        self.assertEqual(CredentialHealthService(self.db).list_blocked(), [])

    def test_credencial_inativa_nao_aparece(self):
        self._bloquear()
        self.credential.active = False
        self.db.commit()
        self.assertEqual(CredentialHealthService(self.db).list_blocked(), [])


if __name__ == "__main__":
    unittest.main()
