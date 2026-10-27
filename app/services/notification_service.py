# app/services/notification_service.py
"""
Notificação de falhas de agendamento.

Quando um agendamento ATIVO falha N vezes seguidas (N = failure_threshold do canal), o
serviço envia uma requisição HTTP totalmente configurável (URL, método, cabeçalhos e corpo
com variáveis {{erro}}, {{automacao}}...) e, conforme a configuração, pausa o agendamento
(e opcionalmente desativa a automação). Agendamento pausado não gera mais tasks.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from types import SimpleNamespace
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.domain.enums import ScheduleStatus, TaskStatus
from app.models.automation import Automation
from app.models.notification_channel import NotificationChannel, NotificationLog
from app.models.runner import Runner
from app.models.schedule import Schedule
from app.models.task import Task
from app.models.task_error import TaskError

logger = logging.getLogger("orkaflow.notifications")

FAILURE_STATUSES = (TaskStatus.ERROR, TaskStatus.TIMEOUT)
FINAL_FOR_STREAK = (TaskStatus.FINISHED, TaskStatus.ERROR, TaskStatus.TIMEOUT)
SEND_ATTEMPTS = 3
SEND_RETRY_DELAYS_SECONDS = (2, 5)
MAX_ERROR_CHARS = 3500
MAX_SNIPPET_CHARS = 1500
MAX_RESPONSE_BODY_CHARS = 32000

# nome, descrição, exemplo (usado pela tela e pelo envio de teste)
VARIABLES: list[tuple[str, str, str]] = [
    ("erro", "Mensagem e trecho do erro da última falha", "RuntimeError: Falha no login SAP: senha incorreta"),
    ("erro_resumo", "Primeira linha do erro (até 300 caracteres)", "RuntimeError: Falha no login SAP"),
    ("ultimas_falhas", "Uma linha por falha seguida: #task: erro", "#42715: Falha no login SAP"),
    ("automacao", "Nome da automação", "Automacao_Estoque_PO"),
    ("automacao_id", "ID da automação", "12"),
    ("agendamento", "Nome do agendamento", "Agendamento_Estoque_PO"),
    ("agendamento_id", "ID do agendamento", "18"),
    ("bot", "Nome do bot da automação", "BOT_ETL_Estoque_PO"),
    ("runner", "Máquina da última falha", "SRVPMW01RPA14"),
    ("task_id", "ID da última task que falhou", "42723"),
    ("task_ids", "IDs das tasks que falharam, separados por vírgula", "42715,42719,42723"),
    ("tentativas", "Quantidade de falhas seguidas", "3"),
    ("data_hora", "Data e hora do envio (UTC, ISO 8601)", "2026-10-21T18:30:00+00:00"),
    ("link_task", "Link da última task no painel (exige a URL base do painel)", "http://painel/tasks/42723"),
]

# Aceita ponto no nome ({{retorno.status}}): os eventos expõem os campos do retorno do robô assim.
_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.]*)\s*\}\}")
_SECRET_HEADER_HINTS = ("authorization", "token", "key", "secret", "senha", "password", "cookie")


# --------------------------------------------------------------------------- canal
def get_or_create_channel(db: Session) -> NotificationChannel:
    channel = db.scalars(select(NotificationChannel).order_by(NotificationChannel.id)).first()
    if channel is None:
        channel = NotificationChannel(
            name="Chamado",
            enabled=False,
            url="",
            method="POST",
            headers_json=json.dumps({"Content-Type": "application/json"}),
            body_template=(
                '{\n  "titulo": "Falha na automação {{automacao}}",\n'
                '  "descricao": "O agendamento {{agendamento}} falhou {{tentativas}} vezes seguidas.\\n\\n{{erro}}"\n}'
            ),
            timeout_seconds=15,
            failure_threshold=3,
            pause_schedule=True,
            deactivate_automation=False,
        )
        db.add(channel)
        db.commit()
        db.refresh(channel)
    return channel


def channel_headers(channel: NotificationChannel) -> dict[str, str]:
    if not channel.headers_json:
        return {}
    try:
        data = json.loads(channel.headers_json)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def channel_pre_steps(channel: NotificationChannel) -> list[dict]:
    if not channel.pre_steps_json:
        return []
    try:
        data = json.loads(channel.pre_steps_json)
    except (ValueError, TypeError):
        return []
    return [step for step in data if isinstance(step, dict)] if isinstance(data, list) else []


def channel_to_read(channel: NotificationChannel) -> dict:
    return {
        "pre_steps": channel_pre_steps(channel),
        "id": channel.id,
        "name": channel.name,
        "enabled": channel.enabled,
        "url": channel.url,
        "method": channel.method,
        "headers": channel_headers(channel),
        "body_template": channel.body_template,
        "timeout_seconds": channel.timeout_seconds,
        "failure_threshold": channel.failure_threshold,
        "pause_schedule": channel.pause_schedule,
        "deactivate_automation": channel.deactivate_automation,
        "panel_base_url": channel.panel_base_url,
        "updated_at": channel.updated_at,
    }


def update_channel(db: Session, data: dict) -> NotificationChannel:
    channel = get_or_create_channel(db)
    was_enabled = bool(channel.enabled)

    for field in (
        "name", "enabled", "url", "method", "body_template", "timeout_seconds",
        "failure_threshold", "pause_schedule", "deactivate_automation", "panel_base_url",
    ):
        if field in data and data[field] is not None:
            setattr(channel, field, data[field])

    if "panel_base_url" in data and not data["panel_base_url"]:
        channel.panel_base_url = None

    if data.get("headers") is not None:
        channel.headers_json = json.dumps(data["headers"], ensure_ascii=False)

    if data.get("pre_steps") is not None:
        channel.pre_steps_json = json.dumps(data["pre_steps"], ensure_ascii=False)

    if channel.enabled and not (channel.url or "").strip():
        db.rollback()
        raise ValidationException("Informe a URL de destino para ativar as notificações.")

    if channel.enabled and not was_enabled:
        # Ao ativar, a contagem de falhas seguidas começa do zero: falhas antigas não notificam.
        channel.counting_since = datetime.now(timezone.utc)

    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


# ------------------------------------------------------------------ renderização
def _escape(value: str, mode: str) -> str:
    if mode == "json":
        return json.dumps(value, ensure_ascii=False)[1:-1]
    if mode == "url":
        return urllib.parse.quote(value, safe="")
    return value


def render_template(text: str, variables: dict[str, str], mode: str = "raw") -> str:
    """Troca {{variavel}} pelo valor. Em mode='json' escapa aspas/quebras de linha."""

    def _sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in variables:
            return match.group(0)
        return _escape(str(variables[name]), mode)

    return _VAR_RE.sub(_sub, text or "")


@dataclass
class PreparedRequest:
    url: str
    method: str
    headers: dict[str, str]
    body: str


def _looks_like_json(body: str, headers: dict[str, str]) -> bool:
    content_type = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
    if content_type:
        return "json" in content_type.lower()
    return body.lstrip().startswith(("{", "["))


def build_request(channel: NotificationChannel, variables: dict[str, str]) -> PreparedRequest:
    headers = {
        key: render_template(value, variables, "raw") for key, value in channel_headers(channel).items()
    }
    body_json = _looks_like_json(channel.body_template, headers)
    body = render_template(channel.body_template, variables, "json" if body_json else "raw")

    if body and not any(k.lower() == "content-type" for k in headers):
        headers["Content-Type"] = "application/json" if body_json else "text/plain; charset=utf-8"

    return PreparedRequest(
        url=render_template(channel.url, variables, "url").strip(),
        method=(channel.method or "POST").upper(),
        headers=headers,
        body=body,
    )


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    masked = {}
    for key, value in headers.items():
        secret = any(hint in key.lower() for hint in _SECRET_HEADER_HINTS)
        masked[key] = "***" if secret and value else value
    return masked


def preview_of(prepared: PreparedRequest) -> dict:
    return {
        "url": prepared.url,
        "method": prepared.method,
        "headers": mask_headers(prepared.headers),
        "body": prepared.body,
    }


# ------------------------------------------------------------------------- envio
MAX_BODY_FOR_EXTRACT = 64 * 1024


def extract_value(body_text: str, path: str) -> str | None:
    """
    Tira um valor da resposta de uma etapa. `path` vazio ou "$" = resposta inteira (texto ou
    JSON string); com ponto para campos e números para itens de lista ("token", "data.token",
    "0", "itens.0.id"). Devolve None se não achar ou se vier vazio.
    """
    text = (body_text or "").strip()
    try:
        value = json.loads(text)
    except ValueError:
        value = text

    parts = [p for p in (path or "").strip().removeprefix("$").strip(".").split(".") if p]
    for part in parts:
        if isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        elif isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None

    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    value = str(value).strip()
    return value or None


def _http_send(prepared: PreparedRequest, timeout: int) -> dict:
    """Faz a chamada HTTP. Nunca levanta exceção. `body_text` guarda a resposta (uso interno)."""
    out = {"ok": False, "status_code": None, "response_snippet": None, "body_text": "", "error": None}

    if not prepared.url.lower().startswith(("http://", "https://")):
        out["error"] = "URL de destino inválida ou vazia."
        return out

    request = urllib.request.Request(
        prepared.url,
        data=prepared.body.encode("utf-8") if prepared.body else None,
        method=prepared.method,
        headers=prepared.headers,
    )

    try:
        with urllib.request.urlopen(request, timeout=max(1, timeout or 15)) as response:
            out["status_code"] = response.status
            raw = response.read(MAX_BODY_FOR_EXTRACT).decode("utf-8", "replace")
            out["body_text"] = raw
            out["response_snippet"] = raw[:MAX_SNIPPET_CHARS]
    except urllib.error.HTTPError as exc:
        out["status_code"] = exc.code
        try:
            raw = exc.read(MAX_BODY_FOR_EXTRACT).decode("utf-8", "replace")
            out["body_text"] = raw
            out["response_snippet"] = raw[:MAX_SNIPPET_CHARS]
        except Exception:
            pass
        out["error"] = f"HTTP {exc.code}: {exc.reason}"
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"

    status = out["status_code"]
    out["ok"] = status is not None and 200 <= status < 300 and out["error"] is None
    return out


def _step_as_channel(step: dict) -> SimpleNamespace:
    """Adapta uma etapa para reaproveitar build_request (mesmas regras de variáveis/escape)."""
    return SimpleNamespace(
        url=step.get("url") or "",
        method=(step.get("method") or "POST").upper(),
        headers_json=json.dumps(step.get("headers") or {}),
        body_template=step.get("body_template") or "",
    )


def _run_pre_steps(channel: NotificationChannel, variables: dict[str, str]):
    """
    Executa as etapas anteriores em ordem. Devolve (variáveis completas, resultados, erro).
    Os valores extraídos (ex.: token) só ficam em memória: nunca vão para log nem para a API.
    """
    all_vars = dict(variables)
    results: list[dict] = []
    # (as variáveis extraídas ficam em all_vars; deliver() as usa para mascarar o histórico)

    for index, step in enumerate(channel_pre_steps(channel), start=1):
        name = step.get("name") or f"Etapa {index}"
        prepared = build_request(_step_as_channel(step), all_vars)
        sent = _http_send(prepared, channel.timeout_seconds)

        entry = {
            "name": name,
            "ok": sent["ok"],
            "status_code": sent["status_code"],
            "error": sent["error"],
            "extracted": [],
        }

        if sent["ok"]:
            for rule in step.get("extract") or []:
                variable = str(rule.get("variable") or "").strip()
                if not variable:
                    continue
                value = extract_value(sent["body_text"], str(rule.get("path") or ""))
                if value is None:
                    entry["ok"] = False
                    entry["error"] = (
                        f"Não encontrei '{rule.get('path') or 'resposta inteira'}' na resposta "
                        f"para guardar em '{variable}'."
                    )
                    break
                all_vars[variable] = value
                entry["extracted"].append(variable)
        elif sent["response_snippet"]:
            # Resposta de erro da etapa (ex.: login recusado). Só quando falhou: não carrega token.
            entry["error"] = f"{sent['error']} - {sent['response_snippet'][:200]}"

        results.append(entry)

        if not entry["ok"]:
            return all_vars, results, f"Etapa '{name}' falhou: {entry['error']}"

    return all_vars, results, None


def deliver(channel: NotificationChannel, variables: dict[str, str]) -> dict:
    """
    Executa as etapas anteriores (se houver) e o envio principal. Nunca levanta exceção:
    devolve o resultado, com `steps` descrevendo cada etapa anterior (sem valores extraídos).
    """
    all_vars, step_results, step_error = _run_pre_steps(channel, variables)
    prepared = build_request(channel, all_vars)

    result = {
        "ok": False,
        "status_code": None,
        "response_snippet": None,
        "error": None,
        "request_preview": preview_of(prepared),
        "steps": step_results,
        "response_body": None,
        # valores extraídos pelas etapas (ex.: token): só para mascarar o histórico; nunca vão para a API
        "_secrets": [all_vars[name] for step in step_results for name in step["extracted"] if name in all_vars],
    }

    if step_error:
        result["error"] = f"{step_error} O envio principal não foi executado."
        return result

    sent = _http_send(prepared, channel.timeout_seconds)
    result.update(
        ok=sent["ok"],
        status_code=sent["status_code"],
        response_snippet=sent["response_snippet"],
        error=sent["error"],
        response_body=(sent["body_text"] or "")[:MAX_RESPONSE_BODY_CHARS] or None,
    )
    return result


def sample_variables(channel: NotificationChannel) -> dict[str, str]:
    values = {name: example for name, _desc, example in VARIABLES}
    values["data_hora"] = datetime.now(timezone.utc).isoformat()
    if channel.panel_base_url:
        values["link_task"] = f"{channel.panel_base_url.rstrip('/')}/tasks/42723"
    return values


def send_test(db: Session) -> dict:
    channel = get_or_create_channel(db)
    result = deliver(channel, sample_variables(channel))
    _write_log(db, channel, kind="test", result=result)
    db.commit()
    result.pop("_secrets", None)  # valores extraídos (ex.: token) nunca saem do serviço
    return result


def _scrub(value, secrets: list[str]):
    """Troca valores secretos (ex.: token extraído) por *** em qualquer texto do detalhe."""
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, "***")
        return value
    if isinstance(value, dict):
        return {k: _scrub(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, secrets) for v in value]
    return value


def _write_log(
    db: Session,
    channel: NotificationChannel,
    *,
    kind: str,
    result: dict,
    schedule: Schedule | None = None,
    automation: Automation | None = None,
    task_ids: list[int] | None = None,
    paused: bool = False,
) -> NotificationLog:
    secrets = [s for s in (result.get("_secrets") or []) if s]
    details = _scrub(
        {
            "request": result.get("request_preview"),
            "steps": result.get("steps") or [],
            "response_body": result.get("response_body"),
        },
        secrets,
    )

    entry = NotificationLog(
        channel_id=channel.id,
        kind=kind,
        schedule_id=schedule.id if schedule else None,
        schedule_name=(schedule.name if schedule else None),
        automation_name=(automation.label or automation.name) if automation else None,
        task_ids=",".join(str(t) for t in task_ids) if task_ids else None,
        ok=bool(result.get("ok")),
        status_code=result.get("status_code"),
        error=_scrub(result.get("error"), secrets),
        response_snippet=_scrub((result.get("response_snippet") or "")[:MAX_SNIPPET_CHARS], secrets) or None,
        paused_schedule=paused,
        details_json=json.dumps(details, ensure_ascii=False),
    )
    db.add(entry)
    return entry


def get_log(db: Session, log_id: int) -> NotificationLog | None:
    return db.get(NotificationLog, log_id)


def log_detail(entry: NotificationLog) -> dict:
    """Linha do histórico com requisição, etapas e resposta completa (se guardadas)."""
    details: dict = {}
    if entry.details_json:
        try:
            parsed = json.loads(entry.details_json)
            details = parsed if isinstance(parsed, dict) else {}
        except ValueError:
            details = {}

    return {
        "id": entry.id,
        "created_at": entry.created_at,
        "kind": entry.kind,
        "schedule_id": entry.schedule_id,
        "schedule_name": entry.schedule_name,
        "automation_name": entry.automation_name,
        "task_ids": entry.task_ids,
        "ok": entry.ok,
        "status_code": entry.status_code,
        "error": entry.error,
        "response_snippet": entry.response_snippet,
        "paused_schedule": entry.paused_schedule,
        "request": details.get("request"),
        "steps": details.get("steps") or [],
        "response_body": details.get("response_body"),
    }


def list_logs(db: Session, limit: int = 50) -> list[NotificationLog]:
    return list(
        db.scalars(select(NotificationLog).order_by(NotificationLog.id.desc()).limit(max(1, min(limit, 500))))
    )


# ----------------------------------------------------------- regra das falhas seguidas
def _task_error_text(db: Session, task: Task) -> str:
    error = db.scalars(
        select(TaskError).where(TaskError.task_id == task.id).order_by(TaskError.id.desc())
    ).first()

    if error is not None:
        text = error.message or ""
        if error.stacktrace:
            text = f"{text}\n{error.stacktrace}"
    else:
        text = task.final_message or f"Task finalizada com status {getattr(task.status, 'value', task.status)}."

    return text.strip()[:MAX_ERROR_CHARS]


def _watermark(db: Session, schedule_id: int) -> int:
    """Maior task já incluída em um alerta deste agendamento (evita realertar as mesmas falhas)."""
    entry = db.scalars(
        select(NotificationLog)
        .where(NotificationLog.schedule_id == schedule_id, NotificationLog.kind == "failure_alert")
        .order_by(NotificationLog.id.desc())
    ).first()

    if entry is None or not entry.task_ids:
        return 0

    try:
        return max(int(part) for part in entry.task_ids.split(",") if part.strip())
    except ValueError:
        return 0


def failing_streak(
    db: Session, schedule: Schedule, threshold: int, since: datetime | None = None
) -> list[Task]:
    """As últimas `threshold` tasks finais do agendamento, se TODAS falharam (senão, lista vazia).

    `since`: só conta tasks finalizadas a partir desse momento (ver counting_since do canal).
    """
    stmt = select(Task).where(
        Task.schedule_id == schedule.id,
        Task.status.in_(FINAL_FOR_STREAK),
        Task.id > _watermark(db, schedule.id),
    )
    if since is not None:
        stmt = stmt.where(func.coalesce(Task.finished_at, Task.last_update_at, Task.created_at) >= since)

    tasks = list(db.scalars(stmt.order_by(Task.id.desc()).limit(threshold)))

    if len(tasks) < threshold or any(task.status not in FAILURE_STATUSES for task in tasks):
        return []

    return list(reversed(tasks))  # ordem cronológica


def build_variables(
    db: Session,
    channel: NotificationChannel,
    schedule: Schedule,
    automation: Automation | None,
    tasks: list[Task],
) -> dict[str, str]:
    last = tasks[-1]
    errors = {task.id: _task_error_text(db, task) for task in tasks}
    runner = db.get(Runner, last.runner_id) if last.runner_id else None
    bot = getattr(automation, "bot", None) if automation else None
    base = (channel.panel_base_url or "").rstrip("/")

    last_error = errors[last.id]

    return {
        "erro": last_error,
        "erro_resumo": (last_error.splitlines()[0] if last_error else "")[:300],
        "ultimas_falhas": "\n".join(
            f"#{task.id}: {(errors[task.id].splitlines() or [''])[0][:300]}" for task in tasks
        ),
        "automacao": (automation.label or automation.name) if automation else "",
        "automacao_id": str(automation.id) if automation else "",
        "agendamento": schedule.name,
        "agendamento_id": str(schedule.id),
        "bot": bot.name if bot is not None else "",
        "runner": (runner.label or runner.name) if runner else "",
        "task_id": str(last.id),
        "task_ids": ",".join(str(task.id) for task in tasks),
        "tentativas": str(len(tasks)),
        "data_hora": datetime.now(timezone.utc).isoformat(),
        "link_task": f"{base}/tasks/{last.id}" if base else "",
    }


def _deliver_with_retries(channel: NotificationChannel, variables: dict[str, str]) -> dict:
    result: dict = {}
    for attempt in range(1, SEND_ATTEMPTS + 1):
        result = deliver(channel, variables)
        if result["ok"]:
            break
        logger.warning("Notificação: tentativa %s/%s falhou: %s", attempt, SEND_ATTEMPTS, result.get("error"))
        if attempt < SEND_ATTEMPTS:
            time.sleep(SEND_RETRY_DELAYS_SECONDS[min(attempt - 1, len(SEND_RETRY_DELAYS_SECONDS) - 1)])
    return result


def enabled_channel_stmt():
    # `== True` (e não `.is_(True)`): o SQL Server não aceita `IS 1`.
    return select(NotificationChannel).where(NotificationChannel.enabled == True).order_by(NotificationChannel.id)  # noqa: E712


def active_schedules_stmt():
    return select(Schedule).where(Schedule.status == ScheduleStatus.ACTIVE, Schedule.active == True)  # noqa: E712


def evaluate_failures(db: Session) -> int:
    """
    Procura agendamentos ativos com N falhas seguidas, notifica e pausa. Devolve quantos
    foram tratados. Sem canal ativo, não faz nada.
    """
    channel = db.scalars(enabled_channel_stmt()).first()
    if channel is None:
        return 0

    threshold = max(1, channel.failure_threshold or 3)
    schedules = list(db.scalars(active_schedules_stmt()))

    handled = 0
    for schedule in schedules:
        tasks = failing_streak(db, schedule, threshold, channel.counting_since)
        if not tasks:
            continue

        automation = db.get(Automation, schedule.automation_id)
        variables = build_variables(db, channel, schedule, automation, tasks)
        result = _deliver_with_retries(channel, variables)

        paused = False
        if channel.pause_schedule:
            schedule.status = ScheduleStatus.PAUSED
            schedule.active = False
            paused = True

        if channel.deactivate_automation and automation is not None:
            automation.active = False

        outcome = "notificação enviada" if result["ok"] else f"falha ao notificar ({result.get('error')})"
        schedule.last_error = (
            f"{len(tasks)} falhas seguidas ({','.join(str(t.id) for t in tasks)}): {outcome}"
            + ("; agendamento pausado." if paused else ".")
        )[:1000]
        db.add(schedule)

        _write_log(
            db,
            channel,
            kind="failure_alert",
            result=result,
            schedule=schedule,
            automation=automation,
            task_ids=[task.id for task in tasks],
            paused=paused,
        )
        db.commit()
        handled += 1
        logger.warning(
            "Agendamento %s (%s): %s falhas seguidas; %s%s",
            schedule.id, schedule.name, len(tasks), outcome, "; pausado" if paused else "",
        )

    return handled
