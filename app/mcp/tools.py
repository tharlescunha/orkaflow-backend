"""Ferramentas do MCP do OrkaFlow: o que uma IA pode consultar e fazer no orquestrador.

Cada ferramenta recebe a sessão do banco e o usuário dono do token, e usa as mesmas
regras do painel (services). Datas saem no horário de Brasília.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundException, ValidationException
from app.mcp import api_bridge
from app.mcp.playbooks import PLAYBOOKS, como_fazer
from app.domain.enums import TaskStatus
from app.models.automation import Automation
from app.models.bot import Bot
from app.models.runner import Runner
from app.models.schedule import Schedule
from app.models.task import Task
from app.models.task_error import TaskError
from app.models.task_log import TaskLog
from app.models.user import User
from app.schemas.task import TaskCreate, TaskParameterCreate
from app.services.bot_version_service import BotVersionService
from app.services.schedule_service import ScheduleService
from app.services.task_rules import EXECUTING_STATUSES, RUNNER_OFFLINE_AFTER_SECONDS, as_aware
from app.services.task_service import TaskService

BRT = ZoneInfo("America/Sao_Paulo")
MAX_LIMIT = 100
ERROR_STATUSES = {TaskStatus.ERROR, TaskStatus.TIMEOUT, TaskStatus.FORCED_STOP}


@dataclass
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict
    # Síncronas: (db, user, args). Com is_async: (request, args), rodam no loop e chamam a API por dentro.
    handler: Callable[..., Any]
    read_only: bool = True
    destructive: bool = False
    is_async: bool = False


# ------------------------------------------------------------------ helpers
def _dt(value) -> str | None:
    value = as_aware(value)
    return value.astimezone(BRT).isoformat(timespec="seconds") if value else None


def _status(value) -> str | None:
    return getattr(value, "value", value)


def _limit(args: dict, default: int = 20) -> int:
    try:
        return max(1, min(int(args.get("limite") or default), MAX_LIMIT))
    except (TypeError, ValueError):
        raise ValidationException("limite precisa ser um número.")


def _automation_name(automation: Automation | None) -> str | None:
    if automation is None:
        return None
    return automation.label or automation.name


def _find_automation(db: Session, ref) -> Automation:
    """Automação por id ou por nome/rótulo (busca aproximada; precisa achar só uma)."""
    if ref is None or str(ref).strip() == "":
        raise ValidationException("Informe a automação (id ou nome).")
    text = str(ref).strip()
    if text.isdigit():
        automation = db.get(Automation, int(text))
        if automation is None:
            raise NotFoundException(f"Automação {text} não encontrada.")
        return automation

    like = f"%{text.lower()}%"
    matches = list(
        db.scalars(
            select(Automation).where(
                or_(func.lower(Automation.name).like(like), func.lower(Automation.label).like(like))
            )
        )
    )
    exact = [a for a in matches if text.lower() in {(a.name or "").lower(), (a.label or "").lower()}]
    if len(exact) == 1:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise NotFoundException(f"Nenhuma automação com '{text}'. Use listar_automacoes para ver os nomes.")
    names = ", ".join(f"{a.id}={_automation_name(a)}" for a in matches[:10])
    raise ValidationException(f"Mais de uma automação com '{text}': {names}. Informe o id.")


def _find_runner(db: Session, ref) -> Runner:
    text = str(ref or "").strip()
    if not text:
        raise ValidationException("Informe a máquina (id ou nome).")
    if text.isdigit():
        runner = db.get(Runner, int(text))
        if runner is None or runner.deleted_at is not None:
            raise NotFoundException(f"Máquina {text} não encontrada.")
        return runner
    like = f"%{text.lower()}%"
    matches = list(
        db.scalars(
            select(Runner).where(
                Runner.deleted_at.is_(None),
                or_(func.lower(Runner.name).like(like), func.lower(Runner.label).like(like)),
            )
        )
    )
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise NotFoundException(f"Nenhuma máquina com '{text}'. Use listar_maquinas.")
    raise ValidationException(
        f"Mais de uma máquina com '{text}': " + ", ".join(f"{r.id}={r.name}" for r in matches[:10])
    )


def _task_summary(task: Task) -> dict:
    return {
        "task_id": task.id,
        "automacao": _automation_name(task.automation),
        "automacao_id": task.automation_id,
        "status": _status(task.status),
        "maquina": task.runner.name if task.runner else None,
        "criada_em": _dt(task.created_at),
        "inicio": _dt(task.started_at),
        "fim": _dt(task.finished_at),
        "mensagem_final": (task.final_message or "")[:500] or None,
    }


def _day_bounds(raw: str | None) -> tuple[date, datetime, datetime]:
    if raw:
        try:
            day = date.fromisoformat(str(raw).strip())
        except ValueError:
            raise ValidationException("data no formato AAAA-MM-DD (ex.: 2026-10-26).")
    else:
        day = datetime.now(BRT).date()
    start = datetime.combine(day, time.min, tzinfo=BRT)
    return day, start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def _runner_state(runner: Runner, running: int) -> dict:
    heartbeat = as_aware(runner.last_heartbeat)
    seconds = (datetime.now(UTC) - heartbeat).total_seconds() if heartbeat else None
    online = seconds is not None and seconds <= RUNNER_OFFLINE_AFTER_SECONDS
    return {
        "maquina_id": runner.id,
        "nome": runner.name,
        "rotulo": runner.label,
        "ativa": runner.enabled,
        "status": _status(runner.status),
        "online": online,
        "ultimo_sinal": _dt(runner.last_heartbeat),
        "segundos_sem_sinal": int(seconds) if seconds is not None else None,
        "tasks_em_execucao": running,
    }


# ------------------------------------------------------------- consultas
def listar_automacoes(db: Session, user: User, args: dict) -> dict:
    stmt = select(Automation).options(selectinload(Automation.bot)).order_by(Automation.name)
    if not args.get("incluir_inativas"):
        stmt = stmt.where(Automation.active == True)  # noqa: E712
    busca = (args.get("busca") or "").strip().lower()
    if busca:
        like = f"%{busca}%"
        stmt = stmt.where(or_(func.lower(Automation.name).like(like), func.lower(Automation.label).like(like)))
    rows = list(db.scalars(stmt.limit(_limit(args, 100))))
    return {
        "total": len(rows),
        "automacoes": [
            {
                "automacao_id": a.id,
                "nome": a.name,
                "rotulo": a.label,
                "ativa": a.active,
                "bot": a.bot.name if a.bot else None,
                "bot_id": a.bot_id,
            }
            for a in rows
        ],
    }


def ultimas_execucoes(db: Session, user: User, args: dict) -> dict:
    """Última task de cada automação ativa (ou de uma automação)."""
    if args.get("automacao"):
        automations = [_find_automation(db, args["automacao"])]
    else:
        automations = list(db.scalars(select(Automation).where(Automation.active == True)))  # noqa: E712

    ids = [a.id for a in automations]
    if not ids:
        return {"total": 0, "execucoes": []}
    last_ids = select(func.max(Task.id)).where(Task.automation_id.in_(ids)).group_by(Task.automation_id)
    tasks = {
        t.automation_id: t
        for t in db.scalars(
            select(Task)
            .options(selectinload(Task.automation), selectinload(Task.runner))
            .where(Task.id.in_(last_ids))
        )
    }
    result = []
    for automation in sorted(automations, key=lambda a: _automation_name(a) or ""):
        task = tasks.get(automation.id)
        result.append(
            _task_summary(task)
            if task
            else {"automacao": _automation_name(automation), "automacao_id": automation.id, "status": "nunca executou"}
        )
    return {"total": len(result), "execucoes": result}


def resumo_do_dia(db: Session, user: User, args: dict) -> dict:
    day, start, end = _day_bounds(args.get("data"))
    stmt = (
        select(Task)
        .options(selectinload(Task.automation))
        .where(Task.created_at >= start, Task.created_at < end)
    )
    if args.get("automacao"):
        stmt = stmt.where(Task.automation_id == _find_automation(db, args["automacao"]).id)
    tasks = list(db.scalars(stmt))

    by_status = Counter(_status(t.status) for t in tasks)
    per_automation: dict[str, Counter] = {}
    for task in tasks:
        per_automation.setdefault(_automation_name(task.automation) or f"#{task.automation_id}", Counter())[
            _status(task.status)
        ] += 1

    return {
        "data": day.isoformat(),
        "total_tasks": len(tasks),
        "por_status": dict(by_status),
        "com_erro": sum(by_status.get(_status(s), 0) for s in ERROR_STATUSES),
        "por_automacao": {name: dict(counts) for name, counts in sorted(per_automation.items())},
    }


def listar_tasks(db: Session, user: User, args: dict) -> dict:
    stmt = (
        select(Task)
        .options(selectinload(Task.automation), selectinload(Task.runner))
        .order_by(Task.id.desc())
    )
    if args.get("automacao"):
        stmt = stmt.where(Task.automation_id == _find_automation(db, args["automacao"]).id)
    if args.get("maquina"):
        stmt = stmt.where(Task.runner_id == _find_runner(db, args["maquina"]).id)
    status = (args.get("status") or "").strip().lower()
    if status:
        valid = {s.value for s in TaskStatus}
        if status == "com_erro":
            stmt = stmt.where(Task.status.in_(list(ERROR_STATUSES)))
        elif status == "em_execucao":
            stmt = stmt.where(Task.status.in_(list(EXECUTING_STATUSES)))
        elif status in valid:
            stmt = stmt.where(Task.status == TaskStatus(status))
        else:
            raise ValidationException(f"status inválido. Use: com_erro, em_execucao ou {', '.join(sorted(valid))}.")
    if args.get("data"):
        _day, start, end = _day_bounds(args["data"])
        stmt = stmt.where(Task.created_at >= start, Task.created_at < end)
    tasks = list(db.scalars(stmt.limit(_limit(args))))
    return {"total": len(tasks), "tasks": [_task_summary(t) for t in tasks]}


def detalhe_task(db: Session, user: User, args: dict) -> dict:
    task_id = args.get("task_id")
    task = db.get(Task, int(task_id)) if str(task_id or "").isdigit() else None
    if task is None:
        raise NotFoundException(f"Task {task_id} não encontrada.")

    errors = list(
        db.scalars(select(TaskError).where(TaskError.task_id == task.id).order_by(TaskError.id.desc()).limit(5))
    )
    logs = list(
        db.scalars(select(TaskLog).where(TaskLog.task_id == task.id).order_by(TaskLog.id.desc()).limit(_limit(args, 40)))
    )
    summary = _task_summary(task)
    summary.update(
        {
            "itens_processados": task.items_processed,
            "itens_com_falha": task.items_failed,
            "versao_bot": task.bot_version.version if task.bot_version else None,
            "agendamento": task.schedule.name if task.schedule else None,
            "mensagem_final": task.final_message,
            "tem_print_do_erro": any(e.error_screenshot for e in errors),
            "dica": "Use print_do_erro(task_id) para ver a tela no momento do erro." if any(e.error_screenshot for e in errors) else None,
            "erros": [
                {
                    "tipo": e.error_type,
                    "categoria": _status(e.error_category),
                    "codigo": e.code,
                    "mensagem": e.message,
                    "stacktrace": (e.stacktrace or "")[-3000:] or None,
                    "quando": _dt(e.created_at),
                }
                for e in errors
            ],
            "ultimos_logs": [
                {"quando": _dt(log.created_at), "nivel": _status(log.level), "mensagem": (log.message or "")[:1000]}
                for log in reversed(logs)
            ],
        }
    )
    return summary


def _image_payload(raw) -> dict | None:
    """bytes/memoryview/str(base64 ou data-url) -> {"data": base64, "mimeType"}; None se vazio."""
    import base64

    if raw is None:
        return None
    if isinstance(raw, memoryview):
        raw = raw.tobytes()
    if isinstance(raw, str):
        text = raw.split(",", 1)[1] if raw.startswith("data:image") else raw
        try:
            raw = base64.b64decode(text, validate=True)
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(raw, (bytes, bytearray)) or len(raw) == 0:
        return None
    mime = "image/png" if bytes(raw[:8]) == b"\x89PNG\r\n\x1a\n" else "image/jpeg" if bytes(raw[:2]) == b"\xff\xd8" else "image/png"
    return {"data": base64.b64encode(bytes(raw)).decode("ascii"), "mimeType": mime, "bytes": len(raw)}


def print_do_erro(db: Session, user: User, args: dict) -> dict:
    """Print da tela no momento do erro da task (robô com Maestro ou worker), como imagem."""
    task_id = args.get("task_id")
    task = db.get(Task, int(task_id)) if str(task_id or "").isdigit() else None
    if task is None:
        raise NotFoundException(f"Task {task_id} não encontrada.")
    errors = list(
        db.scalars(select(TaskError).where(TaskError.task_id == task.id).order_by(TaskError.id.desc()).limit(10))
    )
    with_image = next((e for e in errors if e.error_screenshot), None)
    base = {
        "task_id": task.id,
        "status": _status(task.status),
        "automacao": _automation_name(task.automation),
        "mensagem_final": (task.final_message or "")[:1500] or None,
    }
    if with_image is None:
        base["print"] = None
        base["aviso"] = (
            "Esta task não tem print do erro. O robô tira o print quando usa o Maestro com "
            "screenshot_on_error=True (ou chama maestro.screenshot())."
        )
        return base
    image = _image_payload(with_image.error_screenshot)
    if image is None:
        base["print"] = None
        base["aviso"] = "O print gravado está corrompido ou vazio."
        return base
    base["print"] = {"erro": with_image.message, "quando": _dt(with_image.created_at), "tamanho_bytes": image["bytes"], "tipo": image["mimeType"]}
    base["_imagens"] = [{"data": image["data"], "mimeType": image["mimeType"]}]
    return base


def tela_da_maquina(db: Session, user: User, args: dict) -> dict:
    """Último print da tela da máquina (o worker manda a cada poucos segundos enquanto roda task)."""
    runner = _find_runner(db, args.get("maquina"))
    base = _runner_state(runner, 0)
    base["ultimo_print_em"] = _dt(runner.last_screenshot_at)
    image = _image_payload(runner.last_screenshot_image)
    if image is None:
        base["print"] = None
        base["aviso"] = "Esta máquina ainda não enviou print de tela (o worker só manda enquanto uma task roda)."
        return base
    age = None
    if runner.last_screenshot_at:
        age = int((datetime.now(UTC) - as_aware(runner.last_screenshot_at)).total_seconds())
    base["print"] = {"idade_segundos": age, "tamanho_bytes": image["bytes"], "tipo": image["mimeType"]}
    if age is not None and age > 600:
        base["aviso"] = "O print tem mais de 10 minutos: pode não refletir a tela atual."
    base["_imagens"] = [{"data": image["data"], "mimeType": image["mimeType"]}]
    return base


def listar_maquinas(db: Session, user: User, args: dict) -> dict:
    runners = list(
        db.scalars(select(Runner).where(Runner.deleted_at.is_(None)).order_by(Runner.name))
    )
    if not args.get("incluir_inativas"):
        runners = [r for r in runners if r.enabled]
    running = dict(
        db.execute(
            select(Task.runner_id, func.count(Task.id))
            .where(Task.status.in_(list(EXECUTING_STATUSES)), Task.runner_id.is_not(None))
            .group_by(Task.runner_id)
        ).all()
    )
    return {"total": len(runners), "maquinas": [_runner_state(r, running.get(r.id, 0)) for r in runners]}


def status_maquina(db: Session, user: User, args: dict) -> dict:
    runner = _find_runner(db, args.get("maquina"))
    executing = list(
        db.scalars(
            select(Task)
            .options(selectinload(Task.automation), selectinload(Task.runner))
            .where(Task.runner_id == runner.id, Task.status.in_(list(EXECUTING_STATUSES)))
        )
    )
    _day, start, end = _day_bounds(None)
    today = Counter(
        _status(s)
        for (s,) in db.execute(
            select(Task.status).where(Task.runner_id == runner.id, Task.created_at >= start, Task.created_at < end)
        ).all()
    )
    state = _runner_state(runner, len(executing))
    state["em_execucao"] = [_task_summary(t) for t in executing]
    state["hoje_por_status"] = dict(today)
    return state


def listar_agendamentos(db: Session, user: User, args: dict) -> dict:
    stmt = select(Schedule).options(selectinload(Schedule.automation)).order_by(Schedule.name)
    if args.get("automacao"):
        stmt = stmt.where(Schedule.automation_id == _find_automation(db, args["automacao"]).id)
    rows = list(db.scalars(stmt.limit(_limit(args, 100))))
    return {
        "total": len(rows),
        "agendamentos": [
            {
                "agendamento_id": s.id,
                "nome": s.name,
                "automacao": _automation_name(s.automation),
                "status": _status(s.status),
                "ativo": s.active,
                "proxima_execucao": _dt(s.next_run_at),
                "ultima_execucao": _dt(s.last_run_at),
                "ultimo_erro": s.last_error,
            }
            for s in rows
        ],
    }


def verificar_versao_bot(db: Session, user: User, args: dict) -> dict:
    bot = _find_bot(db, args.get("bot"))
    preview = BotVersionService(db).git_preview(bot.id)
    return {
        "bot": bot.name,
        "situacao": preview["status"],
        "mensagem": preview["message"],
        "versao_sugerida": preview["suggested_version"],
        "ultima_versao": preview["last_version"],
        "commit": preview["head"]["short"],
        "autor": preview["head"]["author"],
        "data_commit": _dt(preview["head"]["committed_at"]),
        "changelog": preview["changelog"],
    }


def _find_bot(db: Session, ref) -> Bot:
    text = str(ref or "").strip()
    if not text:
        raise ValidationException("Informe o bot (id ou nome).")
    if text.isdigit():
        bot = db.get(Bot, int(text))
        if bot is None:
            raise NotFoundException(f"Bot {text} não encontrado.")
        return bot
    matches = list(db.scalars(select(Bot).where(func.lower(Bot.name).like(f"%{text.lower()}%"))))
    exact = [b for b in matches if b.name.lower() == text.lower()]
    if len(exact) == 1:
        return exact[0]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise NotFoundException(f"Nenhum bot com '{text}'.")
    raise ValidationException(f"Mais de um bot com '{text}': " + ", ".join(f"{b.id}={b.name}" for b in matches[:10]))


# ----------------------------------------------------------------- ações
def criar_task(db: Session, user: User, args: dict) -> dict:
    automation = _find_automation(db, args.get("automacao"))
    runner_id = _find_runner(db, args["maquina"]).id if args.get("maquina") else None

    parameters = []
    if automation.default_parameters_json:
        parameters.append(
            TaskParameterCreate(parameter_name="parameters_json", parameter_value=json.dumps(automation.default_parameters_json))
        )
    runtime = dict(automation.default_runtime_parameters_json or {})
    extra = args.get("parametros")
    if extra:
        if not isinstance(extra, dict):
            raise ValidationException("parametros precisa ser um objeto, ex.: {\"filial\": \"010\"}.")
        runtime.update(extra)
    if runtime:
        parameters.append(
            TaskParameterCreate(parameter_name="runtime_parameters_json", parameter_value=json.dumps(runtime))
        )

    payload = TaskCreate(
        automation_id=automation.id,
        runner_id=runner_id,
        priority=int(args.get("prioridade") or automation.default_priority or 5),
        parameters=parameters,
    )
    created = TaskService(db).create_manual_task(payload=payload, created_by=user.id)
    task = db.get(Task, created["id"])
    return {"mensagem": "Task criada e colocada na fila.", **_task_summary(task)}


def parar_task(db: Session, user: User, args: dict) -> dict:
    task_id = args.get("task_id")
    if not str(task_id or "").isdigit():
        raise ValidationException("Informe task_id.")
    task = TaskService(db).request_stop(int(task_id))
    if task.status == TaskStatus.CANCELED:
        message = "A task ainda estava na fila e foi cancelada."
    else:
        message = "Parada solicitada: a máquina encerra o robô no próximo ciclo."
    return {"mensagem": message, "task_id": task.id, "status": _status(task.status)}


def _schedule(db: Session, args: dict) -> int:
    schedule_id = args.get("agendamento_id")
    if not str(schedule_id or "").isdigit():
        raise ValidationException("Informe agendamento_id (veja em listar_agendamentos).")
    return int(schedule_id)


def pausar_agendamento(db: Session, user: User, args: dict) -> dict:
    schedule = ScheduleService.pause(db, _schedule(db, args))
    return {"mensagem": "Agendamento pausado.", "agendamento_id": schedule.id, "nome": schedule.name, "status": _status(schedule.status)}


def reativar_agendamento(db: Session, user: User, args: dict) -> dict:
    schedule = ScheduleService.reactivate(db, _schedule(db, args))
    return {"mensagem": "Agendamento reativado.", "agendamento_id": schedule.id, "nome": schedule.name, "status": _status(schedule.status)}


def criar_versao_bot(db: Session, user: User, args: dict) -> dict:
    bot = _find_bot(db, args.get("bot"))
    service = BotVersionService(db)
    preview = service.git_preview(bot.id)
    if preview["status"] != "nova_versao":
        return {"criada": False, "mensagem": preview["message"]}
    version = service.create(
        {
            "bot_id": bot.id,
            "version": (args.get("versao") or preview["suggested_version"]).strip(),
            "storage_type": "git",
            "commit_hash": preview["head"]["hash"],
            "branch": preview["branch"],
            "artifact_path": preview["repository"] or None,
            "changelog": preview["changelog"] or None,
            "commit_author": preview["head"]["author"],
            "committed_at": preview["head"]["committed_at"],
            "created_by": user.id,
            "is_active": True,
        }
    )
    return {
        "criada": True,
        "mensagem": f"Versão {version.version} criada do commit {preview['head']['short']}; passa a ser a executada.",
        "versao_id": version.id,
        "versao": version.version,
        "changelog": preview["changelog"],
    }


# ---------------------------------------------------------------- registro
def _schema(properties: dict | None = None, required: list[str] | None = None) -> dict:
    schema: dict = {"type": "object", "properties": properties or {}, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


_AUTOMACAO = {"type": "string", "description": "Id ou nome da automação (aceita parte do nome)."}
_MAQUINA = {"type": "string", "description": "Id ou nome da máquina (runner)."}
_LIMITE = {"type": "integer", "minimum": 1, "maximum": MAX_LIMIT, "description": "Quantidade máxima de itens."}
_DATA = {"type": "string", "description": "Dia no formato AAAA-MM-DD (horário de Brasília). Padrão: hoje."}

TOOLS: list[Tool] = [
    Tool("listar_automacoes", "Listar automações",
         "Lista as automações cadastradas (por padrão só as ativas), com o bot de cada uma. Use para descobrir nomes e ids.",
         _schema({"busca": {"type": "string", "description": "Parte do nome."},
                  "incluir_inativas": {"type": "boolean"}, "limite": _LIMITE}),
         listar_automacoes),
    Tool("ultimas_execucoes", "Última execução de cada automação",
         "Status da última task de cada automação ativa (ou só de uma): sucesso, erro, em execução, mensagem final e horários.",
         _schema({"automacao": _AUTOMACAO}), ultimas_execucoes),
    Tool("resumo_do_dia", "Resumo do dia",
         "Quantas tasks foram criadas num dia, por status e por automação, e quantas deram erro.",
         _schema({"data": _DATA, "automacao": _AUTOMACAO}), resumo_do_dia),
    Tool("listar_tasks", "Listar tasks",
         "Lista execuções (tasks) mais recentes, com filtros por automação, máquina, dia e status "
         "(com_erro, em_execucao, waiting, running, finished, error, timeout, canceled...).",
         _schema({"automacao": _AUTOMACAO, "maquina": _MAQUINA, "data": _DATA,
                  "status": {"type": "string"}, "limite": _LIMITE}),
         listar_tasks),
    Tool("detalhe_task", "Detalhe e erro de uma task",
         "Tudo sobre uma task: status, horários, versão do bot, mensagem final, erros registrados (com traceback) e os últimos logs.",
         _schema({"task_id": {"type": "integer"}, "limite": _LIMITE}, ["task_id"]), detalhe_task),
    Tool("print_do_erro", "Print da tela no momento do erro",
         "Devolve a imagem da tela no momento em que a task falhou (quando o robô tirou o print). Use depois de "
         "detalhe_task quando tem_print_do_erro for true, para enxergar o que o robô via (ex.: tela do SAP).",
         _schema({"task_id": {"type": "integer"}}, ["task_id"]), print_do_erro),
    Tool("tela_da_maquina", "Tela da máquina agora",
         "Devolve o último print da tela da máquina (o worker envia enquanto uma task roda). Serve para ver o que "
         "está acontecendo numa máquina em execução ou travada.",
         _schema({"maquina": _MAQUINA}, ["maquina"]), tela_da_maquina),
    Tool("listar_maquinas", "Listar máquinas",
         "Máquinas (runners) com status, se estão online (sinal recente), último sinal e quantas tasks estão rodando.",
         _schema({"incluir_inativas": {"type": "boolean"}}), listar_maquinas),
    Tool("status_maquina", "Status de uma máquina",
         "Situação de uma máquina: online/offline, o que está executando agora e quantas tasks teve hoje por status.",
         _schema({"maquina": _MAQUINA}, ["maquina"]), status_maquina),
    Tool("listar_agendamentos", "Listar agendamentos",
         "Agendamentos com status, próxima e última execução e último erro. Use antes de pausar ou reativar.",
         _schema({"automacao": _AUTOMACAO, "limite": _LIMITE}), listar_agendamentos),
    Tool("verificar_versao_bot", "Verificar versão do bot no Git",
         "Compara o bot com o Git: diz se há versão nova, qual seria o número e o changelog. Não grava nada.",
         _schema({"bot": {"type": "string", "description": "Id ou nome do bot."}}, ["bot"]), verificar_versao_bot),
    Tool("criar_task", "Executar uma automação agora",
         "Cria uma task manual (entra na fila e roda na próxima máquina livre). Usa os parâmetros padrão da automação; "
         "'parametros' sobrescreve os de execução (ex.: {\"filial\": \"010\"}).",
         _schema({"automacao": _AUTOMACAO, "maquina": _MAQUINA,
                  "parametros": {"type": "object", "description": "Parâmetros de execução extras."},
                  "prioridade": {"type": "integer", "minimum": 1, "maximum": 10}}, ["automacao"]),
         criar_task, read_only=False),
    Tool("parar_task", "Parar uma task",
         "Pede para a máquina encerrar uma task em execução (ou cancela se ainda está na fila).",
         _schema({"task_id": {"type": "integer"}}, ["task_id"]), parar_task, read_only=False, destructive=True),
    Tool("pausar_agendamento", "Pausar agendamento",
         "Pausa um agendamento: ele deixa de criar tasks até ser reativado.",
         _schema({"agendamento_id": {"type": "integer"}}, ["agendamento_id"]), pausar_agendamento,
         read_only=False, destructive=True),
    Tool("reativar_agendamento", "Reativar agendamento",
         "Reativa um agendamento pausado.",
         _schema({"agendamento_id": {"type": "integer"}}, ["agendamento_id"]), reativar_agendamento, read_only=False),
    Tool("criar_versao_bot", "Criar versão do bot a partir do Git",
         "Se o Git estiver à frente, cria a nova versão do bot (commit, changelog) e ela passa a ser a executada.",
         _schema({"bot": {"type": "string", "description": "Id ou nome do bot."},
                  "versao": {"type": "string", "description": "Número da versão (padrão: o sugerido)."}}, ["bot"]),
         criar_versao_bot, read_only=False),
    # --- Tudo o mais que o painel faz: guia + acesso às rotas da API.
    Tool("como_fazer", "Como fazer (guia passo a passo)",
         "Roteiro de cada assunto do OrkaFlow: quais rotas usar e em que ordem. Comece por aqui para cadastrar ou "
         "alterar bot, versão, automação, vínculo de máquina, agendamento, variável, credencial ou notificação. "
         "Sem 'assunto' devolve a visão geral e a lista de assuntos.",
         _schema({"assunto": {"type": "string", "enum": ["geral", *sorted(PLAYBOOKS)],
                              "description": "Assunto do roteiro."}}),
         lambda db, user, args: como_fazer(args.get("assunto"))),
    Tool("buscar_rotas", "Buscar rotas da API",
         "Acha a rota da API para o que precisa ser feito (busca em português nas explicações). Sem argumentos lista "
         "os grupos. Depois use detalhe_rota.",
         _schema({"busca": {"type": "string", "description": "Palavras, ex.: 'vincular maquina automacao'."},
                  "grupo": {"type": "string", "description": "Nome do grupo, ex.: Automations, Schedules."}}),
         api_bridge.buscar_rotas, is_async=True),
    Tool("detalhe_rota", "Detalhe de uma rota da API",
         "Explicação completa de uma rota: o que faz, regras, parâmetros, campos do corpo (obrigatórios, tipos, "
         "valores aceitos) e exemplos. Use antes de chamar_api.",
         _schema({"rota": {"type": "string", "description": "Ex.: \"POST /api/v1/schedules/\"."}}, ["rota"]),
         api_bridge.detalhe_rota, is_async=True),
    Tool("chamar_api", "Executar uma rota da API",
         "Executa qualquer rota do painel (consultar, cadastrar, alterar, ativar/desativar, apagar) com as permissões "
         "do dono do token. Para POST/PUT/PATCH/DELETE mostre ao usuário o que será enviado e espere a confirmação. "
         "Devolve status HTTP e a resposta; em erro, o 'detail' explica o que corrigir.",
         _schema({"metodo": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
                  "caminho": {"type": "string", "description": "Caminho com os ids, ex.: /api/v1/automations/12/runners."},
                  "query": {"type": "object", "description": "Filtros da URL, ex.: {\"automation_id\": 12}."},
                  "corpo": {"description": "Corpo JSON (objeto ou lista) para POST/PUT/PATCH."}},
                 ["metodo", "caminho"]),
         api_bridge.chamar_api, read_only=False, destructive=True, is_async=True),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOLS}


def tool_catalog() -> list[dict]:
    return [
        {
            "name": t.name,
            "title": t.title,
            "description": t.description,
            "input_schema": t.input_schema,
            "kind": "consulta" if t.read_only else "ação",
        }
        for t in TOOLS
    ]
