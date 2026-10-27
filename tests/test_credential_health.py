"""Saúde das credenciais (out/2026): alerta do robô marca a credencial, pausa agendamentos, bloqueia
tasks novas; trocar a senha volta a 'não verificada' e reativa; sucesso marca 'válida'."""
import json
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.core.exceptions import ConflictException, ForbiddenException
from app.core.security import encrypt_credential_value
from app.domain.enums import CalendarType, SchedulePolicy, ScheduleStatus, ScheduleType, TaskStatus
from app.models.credential import Credential
from app.models.credential_item import CredentialItem
from app.models.repository import Repository
from app.models.schedule import Schedule
from app.schemas.credential import CredentialItemUpdate
from app.services.credential_health_service import (
    PAUSE_REASON,
    CredentialHealthService,
    credential_ids_in_value,
)
from app.services.credential_service import CredentialService
from app.services.scheduler_engine_service import SchedulerEngineService
from app.services.task_service import TaskService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class ReferenceParsingTests(unittest.TestCase):
    def test_finds_credential_id_in_dict_text_and_nested(self):
        self.assertEqual(credential_ids_in_value({"dados_acesso": {"credential_id": 16, "itens": {}}}), {16})
        self.assertEqual(credential_ids_in_value('{"filtros": {}, "dados_acesso": {"credential_id": "7"}}'), {7})
        self.assertEqual(credential_ids_in_value({"sap": {"dados_acesso": {"credential_id": 3}}}), {3})
        self.assertEqual(credential_ids_in_value("nao e json"), set())
        self.assertEqual(credential_ids_in_value(None), set())


class CredentialHealthBase(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.svc = WorkerService(self.db)
        self.runner = self.f.runner("r1")
        self.auto, self.ver = self.f.automation(runners=[self.runner])
        self.credential = Credential(label="SAP produção", repository_id=self.auto.repository_id, active=True)
        self.db.add(self.credential)
        self.db.flush()
        self.item = CredentialItem(
            credential_id=self.credential.id,
            key_name="sap_senha",
            encrypted_value=encrypt_credential_value("senha-antiga"),
            value_type="password",
            masked_preview="****",
        )
        self.db.add(self.item)
        self.auto.default_parameters_json = {
            "dados_acesso": {"credential_id": self.credential.id, "itens": {"sap_senha": None}}
        }
        self.db.flush()

    def _schedule(self, auto, **kw):
        s = Schedule(
            name=f"s-{auto.id}",
            automation_id=auto.id,
            schedule_type=ScheduleType.CALENDAR,
            calendar_type=CalendarType.ONCE,
            policy=SchedulePolicy.CREATE_ALWAYS,
            status=ScheduleStatus.ACTIVE,
            active=True,
            timezone="UTC",
            next_run_at=datetime.now(UTC) - timedelta(minutes=1),
            start_at=datetime.now(UTC) - timedelta(minutes=2),
            **kw,
        )
        self.db.add(s)
        self.db.flush()
        return s

    def _running_task(self):
        task = self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=self.runner)
        self.db.add(
            __import__("app.models.task_parameter", fromlist=["TaskParameter"]).TaskParameter(
                task_id=task.id,
                parameter_name="parameters_json",
                parameter_value=json.dumps(self.auto.default_parameters_json),
                is_secret=False,
            )
        )
        self.db.flush()
        return task

    def _alert(self, task, **kw):
        base = dict(credential_id=self.credential.id, chave="sap_senha", motivo="senha_expirada",
                    mensagem="SAP: senha expirou", sistema="SAP")
        base.update(kw)
        return self.f.payload(self.runner, **base)

    def _manual_payload(self, **kw):
        base = dict(
            automation_id=self.auto.id, runner_id=None, priority=5, requested_start_at=None,
            timeout_seconds=None, inactivity_timeout_seconds=None, execution_mode="manual",
            parent_task_id=None, correlation_id=None, queue_name=None, schedule_id=None,
            bot_version_id=None, parameters=[],
        )
        base.update(kw)
        return SimpleNamespace(**base)


class AlertFlowTests(CredentialHealthBase):
    def test_alert_marks_credential_pauses_schedules_and_logs(self):
        schedule = self._schedule(self.auto)
        other_auto, _ = self.f.automation(runners=[self.runner])
        other_schedule = self._schedule(other_auto)
        task = self._running_task()

        result = self.svc.report_credential_alert(task.id, self._alert(task))

        self.assertEqual(result["status"], "senha_expirada")
        self.assertEqual(result["schedules_paused"], 1)
        self.db.refresh(self.credential)
        self.assertEqual(self.credential.status, "senha_expirada")
        self.assertIn("SAP", self.credential.status_reason)
        self.assertEqual(self.credential.status_task_id, task.id)
        self.db.refresh(schedule)
        self.assertEqual(schedule.status, ScheduleStatus.PAUSED)
        self.assertEqual(schedule.paused_reason, PAUSE_REASON)
        self.assertEqual(schedule.paused_credential_id, self.credential.id)
        self.db.refresh(other_schedule)
        self.assertEqual(other_schedule.status, ScheduleStatus.ACTIVE)

    def test_alert_without_credential_id_finds_it_in_task_parameters(self):
        task = self._running_task()
        result = self.svc.report_credential_alert(task.id, self._alert(task, credential_id=None, motivo="xyz"))
        self.assertEqual(result["credential_id"], self.credential.id)
        self.assertEqual(result["status"], "invalida")

    def test_new_task_is_refused_with_409_while_invalid(self):
        task = self._running_task()
        self.svc.report_credential_alert(task.id, self._alert(task))
        task.status = TaskStatus.ERROR
        self.db.flush()
        with self.assertRaises(ConflictException) as ctx:
            TaskService(self.db).create_manual_task(self._manual_payload(), created_by=self.f.user.id)
        self.assertIn("SAP produção", str(ctx.exception.detail))

    def test_scheduler_skips_with_reason_while_invalid(self):
        schedule = self._schedule(self.auto)
        task = self._running_task()
        self.svc.report_credential_alert(task.id, self._alert(task))
        task.status = TaskStatus.ERROR
        self.db.flush()
        # Reativa à mão para ver o agendador recusar sozinho.
        schedule.status = ScheduleStatus.ACTIVE
        schedule.active = True
        self.db.flush()
        outcome, reason = SchedulerEngineService(self.db)._create_task(schedule, datetime.now(UTC), datetime.now(UTC))
        self.assertEqual(outcome, "skipped")
        self.assertIn("Credencial", reason)

    def test_changing_password_reactivates_and_success_marks_valid(self):
        schedule = self._schedule(self.auto)
        task = self._running_task()
        self.svc.report_credential_alert(task.id, self._alert(task))
        task.status = TaskStatus.ERROR
        self.db.flush()

        CredentialService(self.db).update_item(
            self.credential.id, self.item.id, CredentialItemUpdate(value="senha-nova")
        )
        self.db.refresh(self.credential)
        self.db.refresh(schedule)
        self.assertEqual(self.credential.status, "nao_verificada")
        self.assertEqual(schedule.status, ScheduleStatus.ACTIVE)
        self.assertIsNone(schedule.paused_reason)

        # Nova task com sucesso -> válida.
        task2 = self._running_task()
        self.svc.finish_task(task2.id, self.f.payload(self.runner, status=TaskStatus.FINISHED, final_message=None,
                                                      result_json=None, items_processed=None, items_failed=None))
        self.db.refresh(self.credential)
        self.assertEqual(self.credential.status, "valida")
        self.assertEqual(self.credential.status_task_id, task2.id)

    def test_success_of_task_older_than_alert_does_not_clear_invalid(self):
        task = self._running_task()
        task.started_at = datetime.now(UTC) - timedelta(hours=1)
        self.db.flush()
        self.svc.report_credential_alert(task.id, self._alert(task))
        CredentialHealthService(self.db).mark_valid_from_task(task)
        self.db.refresh(self.credential)
        self.assertEqual(self.credential.status, "senha_expirada")


class ResolveGuardTests(CredentialHealthBase):
    def test_resolve_refuses_credential_from_another_repository(self):
        other_repo = Repository(name="OUTRO", description=None, active=True)
        self.db.add(other_repo)
        self.db.flush()
        foreign = Credential(label="Outro", repository_id=other_repo.id, active=True)
        self.db.add(foreign)
        self.db.flush()
        task = self._running_task()
        with self.assertRaises(ForbiddenException):
            self.svc.resolve_credential_for_runner(
                foreign.id, self.f.payload(self.runner, keys=None, task_id=task.id)
            )
        ok = self.svc.resolve_credential_for_runner(
            self.credential.id, self.f.payload(self.runner, keys=["sap_senha"], task_id=task.id)
        )
        self.assertEqual(ok["dados_acesso"]["sap_senha"], "senha-antiga")

    def test_resolve_refuses_task_of_another_runner(self):
        other = self.f.runner("r2", host="HOST2")
        task = self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=other)
        with self.assertRaises(ForbiddenException):
            self.svc.resolve_credential_for_runner(
                self.credential.id, self.f.payload(self.runner, keys=None, task_id=task.id)
            )


class DefaultsMergeTests(CredentialHealthBase):
    def test_manual_task_gets_automation_defaults_and_keeps_filtros(self):
        from app.schemas.task import TaskParameterCreate

        payload = self._manual_payload(parameters=[
            TaskParameterCreate(parameter_name="parameters_json", parameter_value=json.dumps({"filtros": {"ano": 2026}}))
        ])
        created = TaskService(self.db).create_manual_task(payload, created_by=self.f.user.id)
        params = {p.parameter_name: p.parameter_value for p in TaskService(self.db).get_task_parameters(created["id"])}
        merged = json.loads(params["parameters_json"])
        self.assertEqual(merged["filtros"], {"ano": 2026})
        self.assertEqual(merged["dados_acesso"]["credential_id"], self.credential.id)

    def test_manual_task_without_parameters_uses_defaults(self):
        created = TaskService(self.db).create_manual_task(self._manual_payload(), created_by=self.f.user.id)
        params = {p.parameter_name: p.parameter_value for p in TaskService(self.db).get_task_parameters(created["id"])}
        self.assertIn("dados_acesso", json.loads(params["parameters_json"]))
