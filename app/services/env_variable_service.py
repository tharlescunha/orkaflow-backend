# app/services/env_variable_service.py
"""
Variáveis de ambiente do robô, com escopo e herança.

Ordem de precedência (a mais específica vence): global < bot < automation < runner.
O worker busca o resultado da herança de uma task e injeta no ambiente do processo do robô.
Valores secretos são criptografados com a mesma chave das credenciais e nunca saem pela API de
administração (só pelo endpoint do worker, que entrega o valor ao robô).
"""
from __future__ import annotations

import re

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.core.security import decrypt_credential_value, encrypt_credential_value
from app.models.automation import Automation
from app.models.bot import Bot
from app.models.env_variable import EnvVariable
from app.models.runner import Runner

SCOPES = ("global", "bot", "automation", "runner")
SCOPE_ORDER = {scope: index for index, scope in enumerate(SCOPES)}
GLOBAL_SCOPE_ID = 0

NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
RESERVED_PREFIX = "ORKAFLOW_"
RESERVED_NAMES = {
    "PATH", "PATHEXT", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "TEMP", "TMP",
    "USERPROFILE", "USERNAME", "USERDOMAIN", "HOME", "HOMEDRIVE", "HOMEPATH", "APPDATA",
    "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMDATA", "COMPUTERNAME", "OS",
    "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS", "PYTHONPATH", "PYTHONHOME",
    "VIRTUAL_ENV", "LD_PRELOAD", "LD_LIBRARY_PATH",
}


# ---------------------------------------------------------------- validações
def normalize_name(raw: str) -> str:
    name = (raw or "").strip().upper()

    if not name:
        raise ValidationException("Informe o nome da variável.")
    if len(name) > 120:
        raise ValidationException("O nome da variável pode ter no máximo 120 caracteres.")
    if not NAME_RE.match(name):
        raise ValidationException(
            "Nome inválido: use letras, números e _ (não comece com número). Ex.: SAP_URL."
        )
    if name.startswith(RESERVED_PREFIX):
        raise ValidationException(f"Nomes que começam com {RESERVED_PREFIX} são reservados do orquestrador.")
    if name in RESERVED_NAMES:
        raise ValidationException(f"{name} é uma variável do sistema e não pode ser sobrescrita.")

    return name


def _scope_target_label(db: Session, scope_type: str, scope_id: int) -> str | None:
    """Nome do alvo do escopo; None se não existir."""
    if scope_type == "global":
        return "Global"
    if scope_type == "bot":
        bot = db.get(Bot, scope_id)
        return bot.name if bot else None
    if scope_type == "automation":
        automation = db.get(Automation, scope_id)
        return (automation.label or automation.name) if automation else None
    if scope_type == "runner":
        runner = db.get(Runner, scope_id)
        return (runner.label or runner.name) if runner else None
    return None


def _label(db: Session, scope_type: str, scope_id: int) -> str:
    return _scope_target_label(db, scope_type, scope_id) or f"{scope_type} #{scope_id} (removido)"


# --------------------------------------------------------------------- leitura
def to_read(db: Session, var: EnvVariable) -> dict:
    return {
        "id": var.id,
        "name": var.name,
        "scope_type": var.scope_type,
        "scope_id": var.scope_id,
        "scope_label": _label(db, var.scope_type, var.scope_id),
        "is_secret": var.is_secret,
        "value": None if var.is_secret else var.value,
        "description": var.description,
        "active": var.active,
        "updated_at": var.updated_at,
    }


def list_variables(
    db: Session,
    scope_type: str | None = None,
    scope_id: int | None = None,
    search: str | None = None,
) -> list[EnvVariable]:
    stmt = select(EnvVariable)

    if scope_type:
        stmt = stmt.where(EnvVariable.scope_type == scope_type)
    if scope_id is not None:
        stmt = stmt.where(EnvVariable.scope_id == scope_id)
    if search:
        stmt = stmt.where(EnvVariable.name.like(f"%{search.strip().upper()}%"))

    return list(db.scalars(stmt.order_by(EnvVariable.scope_type, EnvVariable.scope_id, EnvVariable.name)))


def get_variable(db: Session, var_id: int) -> EnvVariable:
    var = db.get(EnvVariable, var_id)
    if var is None:
        raise NotFoundException("Variável não encontrada.")
    return var


# ------------------------------------------------------------------- escrita
def _find_duplicate(db: Session, scope_type: str, scope_id: int, name: str, ignore_id: int | None = None):
    stmt = select(EnvVariable).where(
        EnvVariable.scope_type == scope_type,
        EnvVariable.scope_id == scope_id,
        EnvVariable.name == name,
    )
    if ignore_id is not None:
        stmt = stmt.where(EnvVariable.id != ignore_id)
    return db.scalars(stmt).first()


def _resolve_scope(db: Session, raw_scope_type: str | None, raw_scope_id) -> tuple[str, int]:
    scope_type = (raw_scope_type or "").strip().lower()
    if scope_type not in SCOPES:
        raise ValidationException("Escopo inválido: use global, bot, automation ou runner.")

    scope_id = GLOBAL_SCOPE_ID if scope_type == "global" else raw_scope_id
    if scope_type != "global":
        if not scope_id:
            raise ValidationException("Escolha o alvo do escopo (bot, automação ou máquina).")
        if _scope_target_label(db, scope_type, int(scope_id)) is None:
            raise NotFoundException("O alvo do escopo não foi encontrado.")

    return scope_type, int(scope_id)


def create_variable(db: Session, data: dict) -> EnvVariable:
    scope_type, scope_id = _resolve_scope(db, data.get("scope_type"), data.get("scope_id"))

    name = normalize_name(data.get("name", ""))

    if _find_duplicate(db, scope_type, int(scope_id), name):
        raise ConflictException(f"Já existe a variável {name} neste escopo.")

    value = data.get("value") or ""
    is_secret = bool(data.get("is_secret"))
    if is_secret and not value:
        raise ValidationException("Informe o valor da variável secreta.")

    var = EnvVariable(
        name=name,
        scope_type=scope_type,
        scope_id=int(scope_id),
        value=encrypt_credential_value(value) if is_secret else value,
        is_secret=is_secret,
        description=(data.get("description") or None),
        active=bool(data.get("active", True)),
    )
    db.add(var)
    db.commit()
    db.refresh(var)
    return var


def update_variable(db: Session, var_id: int, data: dict) -> EnvVariable:
    var = get_variable(db, var_id)

    if data.get("name") is not None:
        name = normalize_name(data["name"])
        if name != var.name:
            if _find_duplicate(db, var.scope_type, var.scope_id, name, ignore_id=var.id):
                raise ConflictException(f"Já existe a variável {name} neste escopo.")
            var.name = name

    new_value = data.get("value")
    want_secret = data.get("is_secret", var.is_secret)
    if want_secret is None:
        want_secret = var.is_secret

    if new_value is not None:
        if want_secret and not new_value:
            raise ValidationException("Informe o valor da variável secreta.")
        var.value = encrypt_credential_value(new_value) if want_secret else new_value
    elif want_secret != var.is_secret:
        if want_secret:
            # passa a ser secreta: criptografa o valor que já existia
            var.value = encrypt_credential_value(var.value or "")
        else:
            raise ValidationException("Informe o novo valor ao deixar de ser secreta.")

    var.is_secret = bool(want_secret)

    if "description" in data:
        var.description = data["description"] or None
    if data.get("active") is not None:
        var.active = bool(data["active"])

    db.add(var)
    db.commit()
    db.refresh(var)
    return var


def import_variables(
    db: Session,
    scope_type: str,
    scope_id: int | None,
    items: list[dict],
    overwrite: bool = False,
) -> dict:
    """
    Importa várias variáveis (ex.: lidas de um arquivo .env) num escopo.

    Cada item passa pelas mesmas regras do cadastro. Itens inválidos não impedem os demais;
    o que já existe no escopo é ignorado, ou atualizado com `overwrite`. Uma única transação.
    """
    scope_type, scope_id = _resolve_scope(db, scope_type, scope_id)

    results: list[dict] = []
    seen: set[str] = set()
    counts = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    def add(name: str, status: str, message: str | None = None):
        counts[status if status != "error" else "errors"] += 1
        results.append({"name": name, "status": status, "message": message})

    for item in items:
        raw_name = item.get("name") or ""
        try:
            name = normalize_name(raw_name)
        except ValidationException as exc:
            add(raw_name.strip() or "(vazio)", "error", exc.detail)
            continue

        if name in seen:
            add(name, "error", "Nome repetido no arquivo: só a primeira ocorrência foi usada.")
            continue
        seen.add(name)

        value = item.get("value") or ""
        is_secret = bool(item.get("is_secret"))
        if is_secret and not value:
            add(name, "error", "Variável secreta sem valor.")
            continue

        stored = encrypt_credential_value(value) if is_secret else value
        existing = _find_duplicate(db, scope_type, scope_id, name)

        if existing is not None:
            if not overwrite:
                add(name, "skipped", "Já existe neste escopo (mantida).")
                continue
            existing.value = stored
            existing.is_secret = is_secret
            db.add(existing)
            add(name, "updated")
            continue

        db.add(
            EnvVariable(
                name=name,
                scope_type=scope_type,
                scope_id=scope_id,
                value=stored,
                is_secret=is_secret,
                description=None,
                active=True,
            )
        )
        add(name, "created")

    db.commit()
    return {**counts, "results": results}


def delete_variable(db: Session, var_id: int) -> None:
    var = get_variable(db, var_id)
    db.delete(var)
    db.commit()


# ------------------------------------------------------------------- herança
def _plain_value(var: EnvVariable) -> str:
    if not var.is_secret:
        return var.value or ""
    try:
        return decrypt_credential_value(var.value)
    except ValueError as exc:
        raise ValidationException(
            f"Não foi possível descriptografar a variável {var.name} "
            f"({var.scope_type} #{var.scope_id}). A chave de criptografia mudou?"
        ) from exc


def active_rows_stmt(automation: Automation | None, runner_id: int | None):
    """Variáveis ativas que se aplicam a (automação, máquina). `== True`: SQL Server não aceita `IS 1`."""
    targets = [and_(EnvVariable.scope_type == "global", EnvVariable.scope_id == GLOBAL_SCOPE_ID)]

    if automation is not None:
        targets.append(and_(EnvVariable.scope_type == "bot", EnvVariable.scope_id == automation.bot_id))
        targets.append(and_(EnvVariable.scope_type == "automation", EnvVariable.scope_id == automation.id))
    if runner_id:
        targets.append(and_(EnvVariable.scope_type == "runner", EnvVariable.scope_id == runner_id))

    return select(EnvVariable).where(EnvVariable.active == True, or_(*targets))  # noqa: E712


def _active_rows(db: Session, automation: Automation | None, runner_id: int | None) -> list[EnvVariable]:
    rows = list(db.scalars(active_rows_stmt(automation, runner_id)))
    rows.sort(key=lambda v: (SCOPE_ORDER.get(v.scope_type, 99), v.name))
    return rows


def _merge(rows: list[EnvVariable]) -> dict[str, tuple[EnvVariable, list[EnvVariable]]]:
    """name -> (variável vencedora, variáveis de níveis inferiores que ela sobrescreveu)."""
    merged: dict[str, tuple[EnvVariable, list[EnvVariable]]] = {}
    for var in rows:  # do mais geral ao mais específico: o último vence
        previous = merged.get(var.name)
        overridden = ([previous[0]] + previous[1]) if previous else []
        merged[var.name] = (var, overridden)
    return merged


def effective_variables(db: Session, automation_id: int, runner_id: int | None = None) -> list[dict]:
    """Valores finais (com origem) para o painel. Segredos nunca trazem o valor."""
    automation = db.get(Automation, automation_id)
    if automation is None:
        raise NotFoundException("Automação não encontrada.")

    result = []
    for name, (var, overridden) in sorted(_merge(_active_rows(db, automation, runner_id)).items()):
        result.append(
            {
                "name": name,
                "value": None if var.is_secret else var.value,
                "is_secret": var.is_secret,
                "scope_type": var.scope_type,
                "scope_id": var.scope_id,
                "scope_label": _label(db, var.scope_type, var.scope_id),
                "overrides": [
                    {"scope_type": o.scope_type, "scope_label": _label(db, o.scope_type, o.scope_id)}
                    for o in overridden
                ],
            }
        )
    return result


def resolve_for_task(db: Session, task) -> dict:
    """
    Variáveis finais da task, com valores em texto puro, para o worker injetar no ambiente do
    robô. Devolve também os nomes dos secretos, para o worker mascará-los nos logs.
    """
    automation = db.get(Automation, task.automation_id)
    merged = _merge(_active_rows(db, automation, task.runner_id))

    variables: dict[str, str] = {}
    secret_names: list[str] = []

    for name, (var, _overridden) in merged.items():
        variables[name] = _plain_value(var)
        if var.is_secret:
            secret_names.append(name)

    return {"variables": variables, "secret_names": sorted(secret_names)}
