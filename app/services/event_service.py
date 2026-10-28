"""Eventos (out/2026): "Quando" (robô + condição sobre a saída) → "Então" (requisições HTTP).

Fluxo:
1. A task termina (ou o worker avisa credencial inválida). Nos mesmos pontos do gatilho de sucesso,
   ``enqueue_for_task`` procura regras ativas para a automação/bot e o tipo de gatilho, confere a
   condição (retorno contém X, código de saída N) e grava um ``EventRun`` pendente com as variáveis.
   Nunca levanta: um erro aqui não pode derrubar o fechamento da task.
2. O loop de notificações (``app/workers/notifications_main.py``) chama ``process_pending`` e
   executa cada disparo fora da transação da task, reaproveitando o envio do canal de notificação
   (etapas prévias com extração de variáveis, envio principal, retentativas, mascaramento).
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, ValidationException
from app.domain.enums import TaskStatus
from app.models.automation import Automation
from app.models.bot import Bot
from app.models.event_rule import EventRule, EventRun
from app.models.runner import Runner
from app.models.task import Task
from app.models.task_telemetry import TaskTelemetry
from app.services import notification_service as notif

logger = logging.getLogger("orkaflow.events")

MAX_PENDING_PER_CYCLE = 20
MAX_RETURN_CHARS = 4000

TRIGGERS: list[tuple[str, str, str]] = [
    ("task_error", "Terminou com erro", "A task terminou com erro ou parada forçada."),
    ("task_success", "Terminou com sucesso", "A task terminou com sucesso."),
    ("task_timeout", "Estourou o tempo", "A task foi encerrada por timeout ou inatividade."),
    ("credential_invalid", "Credencial inválida", "O robô avisou que a senha venceu, está errada ou o usuário foi bloqueado."),
    ("result_contains", "Retorno contém", "O resultado do robô (arquivo de resultado) tem a chave informada, opcionalmente com o valor esperado."),
    ("exit_code", "Código de saída igual a", "O robô terminou com o código de saída informado."),
]
TRIGGER_LABELS = {t: label for t, label, _ in TRIGGERS}

# nome, descrição, exemplo (tela e teste)
VARIABLES: list[tuple[str, str, str]] = [
    ("evento", "Tipo do gatilho que disparou", "task_error"),
    ("regra", "Nome da regra de evento", "Avisar no Teams"),
    ("task_id", "ID da task", "42724"),
    ("status", "Status final da task", "error"),
    ("automacao", "Nome da automação", "Automacao_Estoque_PO"),
    ("automacao_id", "ID da automação", "16"),
    ("bot", "Nome do bot", "BOT_ETL_Estoque_PO"),
    ("runner", "Máquina que executou", "SRVPMW01RPA14"),
    ("erro", "Mensagem final da task (ou erro)", "Credencial inválida: SAP: senha expirou"),
    ("erro_resumo", "Primeira linha do erro (até 300 caracteres)", "Credencial inválida: SAP: senha expirou"),
    ("codigo_saida", "Código de saída do robô", "3"),
    ("retorno", "Resultado do robô em JSON (texto)", '{"linhas": 1200}'),
    ("credencial", "Nome da credencial (gatilho de credencial)", "SAP produção"),
    ("credencial_id", "ID da credencial", "16"),
    ("motivo", "Motivo do alerta de credencial", "senha_expirada"),
    ("chave", "Chave da credencial que falhou", "sap_senha"),
    ("sistema", "Sistema informado pelo robô", "SAP"),
    ("data_hora", "Data e hora do disparo (UTC, ISO 8601)", "2026-10-27T18:30:00+00:00"),
    ("link_task", "Link da task no painel (usa a URL base do canal de notificação)", "http://painel/tasks/42724"),
]


# ------------------------------------------------------------------- helpers
def _loads(text: str | None, default):
    if not text:
        return default
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default


def _lookup(data: Any, path: str) -> Any:
    """Caminho `a.b.0.c` dentro do JSON de retorno. Devolve None se não achar."""
    current = data
    for part in [p for p in (path or "").split(".") if p]:
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def _flatten(prefix: str, data: Any, out: dict[str, str], depth: int = 0) -> None:
    """`retorno.a.b` vira variável para o template (até 3 níveis)."""
    if depth > 3:
        return
    if isinstance(data, dict):
        for key, value in data.items():
            name = f"{prefix}.{key}"
            if isinstance(value, (dict, list)):
                out[name] = json.dumps(value, ensure_ascii=False)[:MAX_RETURN_CHARS]
                _flatten(name, value, out, depth + 1)
            else:
                out[name] = "" if value is None else str(value)
    elif isinstance(data, list):
        for index, value in enumerate(data[:20]):
            name = f"{prefix}.{index}"
            out[name] = json.dumps(value, ensure_ascii=False)[:MAX_RETURN_CHARS] if isinstance(value, (dict, list)) else str(value)


def trigger_label(trigger_type: str) -> str:
    return TRIGGER_LABELS.get(trigger_type, trigger_type)


# ------------------------------------------------------------------- regras (CRUD)
def rule_to_read(db: Session, rule: EventRule, runs_count: int | None = None) -> dict:
    config = _loads(rule.trigger_config_json, {}) or {}
    if runs_count is None:
        runs_count = db.scalar(select(func.count(EventRun.id)).where(EventRun.rule_id == rule.id)) or 0
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "active": rule.active,
        "scope_type": rule.scope_type,
        "scope_id": rule.scope_id,
        "scope_ids": rule_scope_ids(rule),
        "scope_label": _scope_label(db, rule),
        "trigger_type": rule.trigger_type,
        "trigger_label": trigger_label(rule.trigger_type),
        "trigger_config": {"key": config.get("key"), "value": config.get("value"), "code": config.get("code")},
        "pre_steps": notif.channel_pre_steps(rule),
        "url": rule.url,
        "method": rule.method,
        "headers": notif.channel_headers(rule),
        "body_template": rule.body_template,
        "timeout_seconds": rule.timeout_seconds,
        "last_run_at": rule.last_run_at,
        "last_run_ok": rule.last_run_ok,
        "runs_count": runs_count,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
    }


def rule_scope_ids(rule: EventRule) -> list[int]:
    """Todos os alvos da regra (lista em scope_ids_json, senão o scope_id). Vazia para 'all'."""
    if rule.scope_type == "all":
        return []
    ids: list[int] = []
    for raw in _loads(rule.scope_ids_json, []) or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    if not ids and rule.scope_id:
        ids.append(int(rule.scope_id))
    return ids


def _normalize_scope_ids(data: dict) -> list[int]:
    """scope_ids do payload (ou o scope_id antigo), sem repetidos e na ordem enviada."""
    ids: list[int] = []
    for raw in list(data.get("scope_ids") or []) + [data.get("scope_id")]:
        if raw in (None, ""):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and value not in ids:
            ids.append(value)
    return ids


def _scope_label(db: Session, rule: EventRule) -> str | None:
    if rule.scope_type == "all":
        return "Qualquer automação"
    ids = rule_scope_ids(rule)
    if not ids:
        return None
    names: list[str] = []
    for scope_id in ids:
        if rule.scope_type == "automation":
            automation = db.get(Automation, scope_id)
            names.append((automation.label or automation.name) if automation else f"automação #{scope_id} (removida)")
        else:
            bot = db.get(Bot, scope_id)
            names.append(bot.name if bot else f"bot #{scope_id} (removido)")
    return ", ".join(names)


def _validate_rule_data(db: Session, data: dict) -> None:
    scope_type = data.get("scope_type")
    scope_ids = _normalize_scope_ids(data)
    if scope_type in ("automation", "bot") and not scope_ids:
        raise ValidationException("Escolha a automação ou o bot do evento (ou use o escopo 'qualquer').")
    if scope_type == "automation":
        for scope_id in scope_ids:
            if db.get(Automation, scope_id) is None:
                raise ValidationException(f"Automação #{scope_id} não encontrada.")
    if scope_type == "bot":
        for scope_id in scope_ids:
            if db.get(Bot, scope_id) is None:
                raise ValidationException(f"Bot #{scope_id} não encontrado.")
    config = data.get("trigger_config") or {}
    if data.get("trigger_type") == "result_contains" and not (config.get("key") or "").strip():
        raise ValidationException("Para 'Retorno contém' informe a chave do retorno (ex.: status).")
    if data.get("trigger_type") == "exit_code" and config.get("code") is None:
        raise ValidationException("Para 'Código de saída' informe o número.")


def _apply(rule: EventRule, data: dict) -> None:
    rule.name = data["name"].strip()
    rule.description = (data.get("description") or None)
    rule.active = bool(data.get("active", True))
    rule.scope_type = data["scope_type"]
    scope_ids = _normalize_scope_ids(data) if data["scope_type"] != "all" else []
    rule.scope_id = scope_ids[0] if scope_ids else None
    rule.scope_ids_json = json.dumps(scope_ids) if len(scope_ids) > 1 else None
    rule.trigger_type = data["trigger_type"]
    config = data.get("trigger_config") or {}
    rule.trigger_config_json = json.dumps(
        {k: v for k, v in config.items() if v not in (None, "")}, ensure_ascii=False
    )
    rule.pre_steps_json = json.dumps(data.get("pre_steps") or [], ensure_ascii=False)
    rule.url = data["url"]
    rule.method = data.get("method") or "POST"
    rule.headers_json = json.dumps(data.get("headers") or {}, ensure_ascii=False)
    rule.body_template = data.get("body_template") or ""
    rule.timeout_seconds = int(data.get("timeout_seconds") or 15)


def list_rules(db: Session, active: bool | None = None) -> list[dict]:
    stmt = select(EventRule).order_by(EventRule.active.desc(), EventRule.name.asc())
    if active is not None:
        stmt = stmt.where(EventRule.active == active)  # noqa: E712
    rules = db.scalars(stmt).all()
    counts = dict(
        db.execute(select(EventRun.rule_id, func.count(EventRun.id)).group_by(EventRun.rule_id)).all()
    )
    return [rule_to_read(db, rule, counts.get(rule.id, 0)) for rule in rules]


def get_rule(db: Session, rule_id: int) -> EventRule:
    rule = db.get(EventRule, rule_id)
    if rule is None:
        raise NotFoundException("Evento não encontrado.")
    return rule


def create_rule(db: Session, data: dict, created_by: int | None = None) -> EventRule:
    _validate_rule_data(db, data)
    rule = EventRule(created_by=created_by)
    _apply(rule, data)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(db: Session, rule_id: int, data: dict) -> EventRule:
    rule = get_rule(db, rule_id)
    _validate_rule_data(db, data)
    _apply(rule, data)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule_id: int) -> None:
    rule = get_rule(db, rule_id)
    db.delete(rule)
    db.commit()


# ------------------------------------------------------------------- variáveis
def _exit_code(db: Session, task: Task) -> int | None:
    row = db.scalars(
        select(TaskTelemetry).where(TaskTelemetry.task_id == task.id).order_by(TaskTelemetry.id.desc())
    ).first()
    return getattr(row, "exit_code", None) if row is not None else None


def build_variables(db: Session, task: Task | None, trigger_type: str, extra: dict | None = None) -> dict[str, str]:
    extra = extra or {}
    channel = notif.get_or_create_channel(db)
    base = (channel.panel_base_url or "").rstrip("/")
    variables: dict[str, str] = {name: "" for name, _d, _e in VARIABLES}
    variables.update({"evento": trigger_type, "data_hora": datetime.now(UTC).isoformat()})

    if task is not None:
        automation = task.automation or db.get(Automation, task.automation_id)
        bot = getattr(automation, "bot", None) if automation else None
        runner = db.get(Runner, task.runner_id) if task.runner_id else None
        message = task.final_message or ""
        exit_code = _exit_code(db, task)
        variables.update(
            {
                "task_id": str(task.id),
                "status": task.status.value if hasattr(task.status, "value") else str(task.status or ""),
                "automacao": (automation.label or automation.name) if automation else "",
                "automacao_id": str(automation.id) if automation else "",
                "bot": bot.name if bot is not None else "",
                "runner": (runner.label or runner.name) if runner else "",
                "erro": message[:notif.MAX_ERROR_CHARS],
                "erro_resumo": (message.splitlines()[0] if message else "")[:300],
                "codigo_saida": "" if exit_code is None else str(exit_code),
                "retorno": (task.result_json or "")[:MAX_RETURN_CHARS],
                "link_task": f"{base}/tasks/{task.id}" if base else "",
            }
        )
        parsed = _loads(task.result_json, None)
        if isinstance(parsed, (dict, list)):
            _flatten("retorno", parsed, variables)

    for key in ("credencial", "credencial_id", "motivo", "chave", "sistema"):
        if extra.get(key) is not None:
            variables[key] = str(extra[key])
    if extra.get("mensagem") and not variables.get("erro"):
        variables["erro"] = str(extra["mensagem"])[:notif.MAX_ERROR_CHARS]
        variables["erro_resumo"] = variables["erro"][:300]
    return variables


def sample_variables(db: Session) -> dict[str, str]:
    values = {name: example for name, _d, example in VARIABLES}
    values["data_hora"] = datetime.now(UTC).isoformat()
    return values


# ------------------------------------------------------------------- gatilho
def _matches(rule: EventRule, task: Task | None, trigger_type: str, db: Session) -> bool:
    if rule.trigger_type != trigger_type:
        return False
    config = _loads(rule.trigger_config_json, {}) or {}
    if trigger_type == "result_contains":
        if task is None:
            return False
        parsed = _loads(task.result_json, None)
        value = _lookup(parsed, str(config.get("key") or ""))
        if value is None:
            return False
        expected = config.get("value")
        if expected in (None, ""):
            return True
        return str(value).strip().lower() == str(expected).strip().lower()
    if trigger_type == "exit_code":
        if task is None or config.get("code") is None:
            return False
        return _exit_code(db, task) == int(config["code"])
    return True


def _in_scope(rule: EventRule, task: Task | None) -> bool:
    if rule.scope_type == "all":
        return True
    if task is None:
        return False
    ids = rule_scope_ids(rule)
    if rule.scope_type == "automation":
        return task.automation_id in ids
    automation = task.automation
    bot_id = getattr(automation, "bot_id", None) if automation is not None else None
    return bot_id in ids


def trigger_types_for_task(task: Task) -> list[str]:
    """Gatilhos que uma task finalizada pode disparar (além de retorno/código, que valem sempre)."""
    status = task.status.value if hasattr(task.status, "value") else str(task.status)
    types: list[str] = ["result_contains", "exit_code"]
    if status == TaskStatus.FINISHED.value:
        types.insert(0, "task_success")
    elif status == TaskStatus.TIMEOUT.value:
        types.insert(0, "task_timeout")
    elif status in (TaskStatus.ERROR.value, TaskStatus.FORCED_STOP.value):
        types.insert(0, "task_error")
    return types


def enqueue_for_task(db: Session, task: Task, trigger_types: list[str] | None = None, extra: dict | None = None) -> int:
    """Grava os disparos pendentes para a task. Nunca levanta exceção."""
    try:
        types = trigger_types or trigger_types_for_task(task)
        rules = db.scalars(select(EventRule).where(EventRule.active == True)).all()  # noqa: E712
        created = 0
        for rule in rules:
            if not _in_scope(rule, task):
                continue
            for trigger_type in types:
                if not _matches(rule, task, trigger_type, db):
                    continue
                variables = build_variables(db, task, trigger_type, extra)
                variables["regra"] = rule.name
                automation = task.automation
                db.add(
                    EventRun(
                        rule_id=rule.id,
                        rule_name=rule.name,
                        task_id=task.id,
                        automation_name=(automation.label or automation.name) if automation else None,
                        trigger_type=trigger_type,
                        status="pending",
                        variables_json=json.dumps(variables, ensure_ascii=False),
                    )
                )
                created += 1
                break  # uma regra dispara uma vez por task
        if created:
            db.flush()
        return created
    except Exception:  # noqa: BLE001
        logger.exception("Eventos: falha ao enfileirar disparos da task %s", getattr(task, "id", None))
        return 0


# ------------------------------------------------------------------- execução
def _execute(db: Session, run: EventRun, rule: EventRule, variables: dict[str, str], *, retries: bool) -> dict:
    run.status = "running"
    run.started_at = datetime.now(UTC)
    db.flush()
    result = notif._deliver_with_retries(rule, variables) if retries else notif.deliver(rule, variables)
    secrets = list(result.pop("_secrets", []) or [])
    run.ok = bool(result.get("ok"))
    run.status = "success" if run.ok else "error"
    run.status_code = result.get("status_code")
    run.error = result.get("error")
    run.response_snippet = result.get("response_snippet")
    run.details_json = json.dumps(notif._scrub(result, secrets), ensure_ascii=False)
    run.finished_at = datetime.now(UTC)
    rule.last_run_at = run.finished_at
    rule.last_run_ok = run.ok
    db.flush()
    return result


def process_pending(db: Session, limit: int = MAX_PENDING_PER_CYCLE) -> int:
    """Executa os disparos pendentes (chamado pelo loop de notificações)."""
    runs = db.scalars(
        select(EventRun).where(EventRun.status == "pending").order_by(EventRun.id.asc()).limit(limit)
    ).all()
    handled = 0
    for run in runs:
        rule = db.get(EventRule, run.rule_id) if run.rule_id else None
        if rule is None or not rule.active:
            run.status = "error"
            run.error = "Regra removida ou desativada antes do disparo."
            run.finished_at = datetime.now(UTC)
            db.commit()
            continue
        variables = _loads(run.variables_json, {}) or {}
        try:
            _execute(db, run, rule, variables, retries=True)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Eventos: disparo %s falhou", run.id)
            run.status = "error"
            run.error = str(exc)[:1000]
            run.finished_at = datetime.now(UTC)
        db.commit()
        handled += 1
    return handled


def run_test(db: Session, rule_id: int, task_id: int | None = None) -> EventRun:
    """Dispara a regra agora (sem retentativas) com a task informada, a última do escopo ou exemplos."""
    rule = get_rule(db, rule_id)
    task = db.get(Task, task_id) if task_id else _last_task_for_rule(db, rule)
    variables = build_variables(db, task, rule.trigger_type) if task else sample_variables(db)
    variables["regra"] = rule.name
    variables["evento"] = rule.trigger_type
    run = EventRun(
        rule_id=rule.id,
        rule_name=rule.name,
        task_id=task.id if task else None,
        automation_name=(task.automation.label or task.automation.name) if task and task.automation else None,
        trigger_type=rule.trigger_type,
        status="pending",
        variables_json=json.dumps(variables, ensure_ascii=False),
    )
    db.add(run)
    db.flush()
    _execute(db, run, rule, variables, retries=False)
    run.status = "test" if run.ok else "error"
    db.commit()
    db.refresh(run)
    return run


def _last_task_for_rule(db: Session, rule: EventRule) -> Task | None:
    stmt = select(Task).order_by(Task.id.desc())
    ids = rule_scope_ids(rule)
    if rule.scope_type == "automation" and ids:
        stmt = stmt.where(Task.automation_id.in_(ids))
    elif rule.scope_type == "bot" and ids:
        stmt = stmt.join(Automation, Automation.id == Task.automation_id).where(Automation.bot_id.in_(ids))
    return db.scalars(stmt.limit(1)).first()


# ------------------------------------------------------------------- histórico
def run_to_read(run: EventRun) -> dict:
    return {
        "id": run.id,
        "rule_id": run.rule_id,
        "rule_name": run.rule_name,
        "task_id": run.task_id,
        "automation_name": run.automation_name,
        "trigger_type": run.trigger_type,
        "trigger_label": trigger_label(run.trigger_type),
        "status": run.status,
        "ok": run.ok,
        "status_code": run.status_code,
        "error": run.error,
        "response_snippet": run.response_snippet,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
    }


def run_detail(run: EventRun) -> dict:
    data = run_to_read(run)
    data["variables"] = _loads(run.variables_json, {}) or {}
    data["details"] = _loads(run.details_json, None)
    return data


def list_runs(db: Session, rule_id: int | None = None, task_id: int | None = None, limit: int = 50) -> list[EventRun]:
    stmt = select(EventRun).order_by(EventRun.id.desc()).limit(limit)
    if rule_id is not None:
        stmt = stmt.where(EventRun.rule_id == rule_id)
    if task_id is not None:
        stmt = stmt.where(EventRun.task_id == task_id)
    return list(db.scalars(stmt).all())


def get_run(db: Session, run_id: int) -> EventRun:
    run = db.get(EventRun, run_id)
    if run is None:
        raise NotFoundException("Disparo não encontrado.")
    return run
