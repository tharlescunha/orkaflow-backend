"""Liberar acesso (nov/2026).

Alguns robôs se protegem sozinhos: depois de recusas de login (ex.: 2 em 24 h do SAP) eles deixam de tentar com
aquele usuário para não bloqueá-lo no sistema de destino. Essa suspensão é calculada dentro do robô e o Regente
não a enxerga. Quando alguém corrige o usuário (troca a senha, o TI desbloqueia no SAP), é aqui que se avisa:
"este usuário já está ok, pode continuar".

Como funciona:
- cada liberação (usuário, sistema, observação, quem e quando) fica em ``system_settings`` (sem tabela nova);
- o robô recebe, junto com as outras variáveis de ambiente da task, ``LIBERACOES_DE_ACESSO``: um JSON
  ``{"LOGIN": "2026-11-17T14:10:00Z"}`` (horário UTC) com as liberações das últimas 48 h. Quem o lê passa a
  ignorar as recusas de login desse usuário anteriores ao horário. Sem liberação valendo, a variável não existe.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.models.system_setting import SystemSetting

logger = logging.getLogger(__name__)

SETTING_KEY = "access_releases"
# Nome da variável de ambiente entregue aos robôs.
ENV_NAME = "LIBERACOES_DE_ACESSO"
# Quanto tempo uma liberação é entregue aos robôs (a regra dos robôs conta as últimas 24 h).
ACTIVE_HOURS = 48
MAX_ENTRIES = 300
_ISO = "%Y-%m-%dT%H:%M:%SZ"
_LOGIN_RE = re.compile(r"^\S{1,80}$")


def normalize_login(raw: str | None) -> str:
    login = (raw or "").strip().upper()
    if not _LOGIN_RE.match(login):
        raise ValidationException("Informe o usuário (sem espaços, até 80 caracteres).")
    return login


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(_ISO)


def _parse(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(value or "", _ISO).replace(tzinfo=UTC)
    except ValueError:
        return None


class AccessReleaseService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ armazenamento
    def _row(self) -> SystemSetting | None:
        return self.db.scalar(select(SystemSetting).where(SystemSetting.key == SETTING_KEY))

    def _load(self) -> list[dict]:
        row = self._row()
        if row is None or not row.value:
            return []
        try:
            data = json.loads(row.value)
        except ValueError:
            logger.warning("Registro %s ilegível; tratado como vazio.", SETTING_KEY)
            return []
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    def _save(self, items: list[dict]) -> None:
        text = json.dumps(items, ensure_ascii=False)
        row = self._row()
        if row is None:
            self.db.add(SystemSetting(key=SETTING_KEY, value=text))
        else:
            row.value = text

    # ------------------------------------------------------------------ consultas
    def list(self, now: datetime | None = None) -> "list[dict]":
        """Histórico, da mais nova para a mais antiga; `active` = ainda é entregue aos robôs."""
        limit = (now or datetime.now(UTC)) - timedelta(hours=ACTIVE_HOURS)
        rows = []
        for item in self._load():
            released = _parse(item.get("released_at"))
            if released is None:
                continue
            rows.append({**item, "active": released >= limit, "_at": released})
        rows.sort(key=lambda r: r["_at"], reverse=True)
        for row in rows:
            del row["_at"]
        return rows

    def env_value(self, now: datetime | None = None) -> dict[str, str]:
        """login -> horário (UTC) da liberação mais nova, só das últimas 48 h."""
        result: dict[str, str] = {}
        for row in self.list(now):  # da mais nova para a mais antiga: a primeira de cada login vale
            if row["active"] and row.get("login") and row["login"] not in result:
                result[row["login"]] = row["released_at"]
        return result

    def env_json(self, now: datetime | None = None) -> str | None:
        value = self.env_value(now)
        return json.dumps(value, ensure_ascii=False, sort_keys=True) if value else None

    # ------------------------------------------------------------------ liberar
    def release(self, login: str, user, *, system: str | None = None, note: str | None = None,
                now: datetime | None = None) -> dict:
        item = {
            "login": normalize_login(login),
            "system": (system or "").strip()[:60] or None,
            "note": (note or "").strip()[:300] or None,
            "released_at": _iso(now or datetime.now(UTC)),
            "released_by_id": getattr(user, "id", None),
            "released_by_name": getattr(user, "name", None) or getattr(user, "login", None),
        }
        items = self._load()
        items.append(item)
        items.sort(key=lambda i: i.get("released_at") or "")
        self._save(items[-MAX_ENTRIES:])
        self.db.commit()
        logger.info("Acesso de %s liberado por %s.", item["login"], item["released_by_name"])
        return item
