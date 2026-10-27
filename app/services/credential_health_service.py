"""Saúde das credenciais (out/2026).

O robô avisa (linha ``ORKAFLOW_ALERTA_CREDENCIAL`` no stdout ou código de saída 3) que a senha não
serve mais; o worker manda o alerta para cá. A partir daí a credencial fica marcada, os agendamentos
das automações que a usam são pausados e nenhuma task nova é aceita, até alguém trocar a senha.
Assim o usuário de serviço não é bloqueado no sistema de destino por tentativas repetidas.

Como uma automação "usa" uma credencial: pelo bloco ``dados_acesso.credential_id`` dentro do
``default_parameters_json`` dela (e do ``parameters_json`` da task). Não existe outro vínculo.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.domain.enums import CredentialStatus, ScheduleStatus, TaskLogLevel, TaskLogSource
from app.models.automation import Automation
from app.models.credential import Credential
from app.models.schedule import Schedule
from app.models.task import Task
from app.models.task_parameter import TaskParameter
from app.services.task_events import add_task_log

logger = logging.getLogger(__name__)

# Motivo gravado no agendamento quando a pausa veio daqui (a reativação só mexe nesses).
PAUSE_REASON = "credencial_invalida"

INVALID_STATUSES = {
    CredentialStatus.INVALIDA.value,
    CredentialStatus.SENHA_INCORRETA.value,
    CredentialStatus.SENHA_EXPIRADA.value,
    CredentialStatus.USUARIO_BLOQUEADO.value,
}

STATUS_LABELS = {
    CredentialStatus.VALIDA.value: "válida",
    CredentialStatus.NAO_VERIFICADA.value: "não verificada",
    CredentialStatus.INVALIDA.value: "inválida",
    CredentialStatus.SENHA_INCORRETA.value: "senha incorreta",
    CredentialStatus.SENHA_EXPIRADA.value: "senha expirada",
    CredentialStatus.USUARIO_BLOQUEADO.value: "usuário bloqueado",
}


def normalize_motivo(motivo: str | None) -> str:
    value = (motivo or "").strip().lower()
    if value in INVALID_STATUSES:
        return value
    return CredentialStatus.INVALIDA.value


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "")


# --------------------------------------------------------------------- referências
def credential_ids_in_value(value: Any) -> set[int]:
    """Procura ``dados_acesso.credential_id`` num JSON (dict ou texto). Olha também um nível abaixo,
    para o caso de o bloco estar aninhado (ex.: ``{"sap": {"dados_acesso": {...}}}``)."""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return set()
        try:
            value = json.loads(text)
        except Exception:  # noqa: BLE001
            return set()
    if not isinstance(value, dict):
        return set()

    found: set[int] = set()

    def _collect(block: Any) -> None:
        if isinstance(block, dict):
            raw = block.get("credential_id")
            if isinstance(raw, int) and raw > 0:
                found.add(raw)
            elif isinstance(raw, str) and raw.isdigit():
                found.add(int(raw))

    _collect(value.get("dados_acesso"))
    for nested in value.values():
        if isinstance(nested, dict):
            _collect(nested.get("dados_acesso"))
    return found


def credential_ids_for_automation(automation: Automation | None) -> set[int]:
    if automation is None:
        return set()
    return credential_ids_in_value(getattr(automation, "default_parameters_json", None))


class CredentialHealthService:
    def __init__(self, db: Session):
        self.db = db

    # ----------------------------------------------------------------- consultas
    def credential_ids_for_task(self, task: Task) -> set[int]:
        rows = self.db.execute(
            select(TaskParameter.parameter_value).where(
                TaskParameter.task_id == task.id,
                TaskParameter.parameter_name == "parameters_json",
            )
        ).scalars()
        found: set[int] = set()
        for raw in rows:
            found |= credential_ids_in_value(raw)
        return found

    def invalid_credentials_for_automation(self, automation: Automation | None) -> list[Credential]:
        ids = credential_ids_for_automation(automation)
        if not ids:
            return []
        rows = self.db.execute(select(Credential).where(Credential.id.in_(ids))).scalars().all()
        return [c for c in rows if (c.status or "") in INVALID_STATUSES]

    def blocked_reason(self, automation: Automation | None) -> str | None:
        """Mensagem para recusar task nova, ou None se tudo certo."""
        invalid = self.invalid_credentials_for_automation(automation)
        if not invalid:
            return None
        parts = [f"Credencial '{c.label}' com {status_label(c.status)}" for c in invalid]
        return "; ".join(parts) + ". Atualize em Credenciais para voltar a executar."

    def ensure_automation_credentials_usable(self, automation: Automation | None) -> None:
        reason = self.blocked_reason(automation)
        if reason:
            raise ConflictException(reason)

    def alerts_by_automation(self, automations: Iterable[Automation]) -> dict[int, list[dict]]:
        """Para telas (detalhe da automação, Health): credenciais inválidas por automação, numa consulta só."""
        automations = list(automations)
        wanted: dict[int, set[int]] = {a.id: credential_ids_for_automation(a) for a in automations}
        all_ids = set().union(*wanted.values()) if wanted else set()
        if not all_ids:
            return {}
        rows = self.db.execute(select(Credential).where(Credential.id.in_(all_ids))).scalars().all()
        invalid = {c.id: c for c in rows if (c.status or "") in INVALID_STATUSES}
        result: dict[int, list[dict]] = {}
        for automation_id, ids in wanted.items():
            hits = [self._alert_dict(invalid[i]) for i in sorted(ids) if i in invalid]
            if hits:
                result[automation_id] = hits
        return result

    @staticmethod
    def _alert_dict(credential: Credential) -> dict:
        return {
            "credential_id": credential.id,
            "credential_label": credential.label,
            "status": credential.status,
            "status_label": status_label(credential.status),
            "status_reason": credential.status_reason,
            "status_updated_at": credential.status_updated_at,
            "status_task_id": credential.status_task_id,
        }

    # ----------------------------------------------------------------- transições
    def mark_invalid(
        self,
        credential: Credential,
        *,
        motivo: str | None,
        mensagem: str | None,
        task: Task | None,
        chave: str | None = None,
        sistema: str | None = None,
    ) -> int:
        """Marca a credencial, pausa os agendamentos que a usam e registra na task. Devolve quantos pausou."""
        status = normalize_motivo(motivo)
        detail_parts = [p for p in [sistema, f"chave {chave}" if chave else None, mensagem] if p]
        reason = " · ".join(detail_parts)[:300] or status_label(status)

        credential.status = status
        credential.status_reason = reason
        credential.status_updated_at = datetime.now(UTC)
        credential.status_task_id = task.id if task else None
        self.db.flush()

        paused = self.pause_schedules_for_credential(credential)

        if task is not None:
            add_task_log(
                self.db,
                task.id,
                (
                    f"Credencial '{credential.label}' marcada como {status_label(status)}: {reason}. "
                    f"Agendamentos pausados: {paused}. Novas tasks desta automação ficam bloqueadas até "
                    "a credencial ser atualizada."
                ),
                level=TaskLogLevel.ERROR,
                source=TaskLogSource.BACKEND,
                event_code="credential_alert",
                runner_id=task.runner_id,
            )
        logger.warning(
            "Credencial %s marcada como %s (task %s); %s agendamento(s) pausado(s).",
            credential.id, status, task.id if task else None, paused,
        )
        return paused

    def mark_unverified(self, credential: Credential) -> int:
        """Alguém trocou um item: volta a 'não verificada' e reativa o que esta credencial pausou."""
        credential.status = CredentialStatus.NAO_VERIFICADA.value
        credential.status_reason = None
        credential.status_updated_at = datetime.now(UTC)
        credential.status_task_id = None
        self.db.flush()
        return self.reactivate_schedules_paused_by(credential)

    def mark_valid_from_task(self, task: Task) -> list[int]:
        """Task terminou com sucesso: as credenciais que ela usou passam a 'válida'.

        Uma credencial inválida só volta se a task começou depois da marcação (ex.: o usuário foi
        desbloqueado direto no sistema de destino, sem trocar nada aqui)."""
        ids = self.credential_ids_for_task(task)
        if not ids:
            return []
        rows = self.db.execute(select(Credential).where(Credential.id.in_(ids))).scalars().all()
        changed: list[int] = []
        started = task.started_at or task.created_at
        for credential in rows:
            current = credential.status or CredentialStatus.NAO_VERIFICADA.value
            if current in INVALID_STATUSES:
                marked_at = credential.status_updated_at
                if marked_at is None or started is None or _aware(started) <= _aware(marked_at):
                    continue
                self.reactivate_schedules_paused_by(credential)
            if current == CredentialStatus.VALIDA.value:
                continue
            credential.status = CredentialStatus.VALIDA.value
            credential.status_reason = None
            credential.status_updated_at = datetime.now(UTC)
            credential.status_task_id = task.id
            changed.append(credential.id)
        if changed:
            self.db.flush()
        return changed

    # ----------------------------------------------------------------- agendamentos
    def automations_using_credential(self, credential_id: int) -> list[Automation]:
        rows = self.db.execute(select(Automation).where(Automation.active == True)).scalars().all()  # noqa: E712
        return [a for a in rows if credential_id in credential_ids_for_automation(a)]

    def pause_schedules_for_credential(self, credential: Credential) -> int:
        automations = self.automations_using_credential(credential.id)
        if not automations:
            return 0
        schedules = self.db.execute(
            select(Schedule).where(
                Schedule.automation_id.in_([a.id for a in automations]),
                Schedule.active == True,  # noqa: E712
                Schedule.status == ScheduleStatus.ACTIVE,
            )
        ).scalars().all()
        for schedule in schedules:
            schedule.status = ScheduleStatus.PAUSED
            schedule.active = False
            schedule.paused_reason = PAUSE_REASON
            schedule.paused_credential_id = credential.id
            schedule.last_error = (
                f"Pausado automaticamente: credencial '{credential.label}' com {status_label(credential.status)}."
            )
        if schedules:
            self.db.flush()
        return len(schedules)

    def reactivate_schedules_paused_by(self, credential: Credential) -> int:
        schedules = self.db.execute(
            select(Schedule).where(
                Schedule.paused_reason == PAUSE_REASON,
                Schedule.paused_credential_id == credential.id,
                Schedule.status == ScheduleStatus.PAUSED,
            )
        ).scalars().all()
        for schedule in schedules:
            schedule.status = ScheduleStatus.ACTIVE
            schedule.active = True
            schedule.paused_reason = None
            schedule.paused_credential_id = None
            schedule.last_error = None
        if schedules:
            self.db.flush()
        return len(schedules)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
