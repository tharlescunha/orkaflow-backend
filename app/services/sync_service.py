"""Tela Sync (out/2026): painel pessoal com automações escolhidas e health de sistemas externos.

O ping só acontece quando a tela aberta pede (``POST /sync/checks/{id}/ping``): nada roda em segundo plano.
"""
import ipaddress
import socket
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.models.automation import Automation
from app.models.sync_check import SyncAutomationPick, SyncCheck
from app.models.user import User

MAX_CHECKS_PER_USER = 50
USER_AGENT = "Regente-Sync/1.0"


def validate_url(url: str) -> str:
    clean = (url or "").strip()
    parsed = urlparse(clean)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValidationException("Informe o endereço completo, começando com http:// ou https://.")
    if parsed.username or parsed.password:
        raise ValidationException("Não coloque usuário ou senha dentro do endereço.")
    return clean


def _blocked_address(host: str) -> str | None:
    """Barra o próprio servidor e os endereços de metadados de nuvem; rede interna da empresa pode."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return None  # sem DNS: o ping falha sozinho com a mensagem certa
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if ip.is_loopback or ip.is_link_local or ip.is_unspecified or ip.is_multicast:
            return f"O endereço {host} aponta para um IP não permitido ({ip})."
    return None


class SyncService:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user

    def ensure_enabled(self) -> None:
        if not getattr(self.user, "sync_enabled", False):
            raise ForbiddenException("A tela Sync está desligada no seu perfil.")

    # ------------------------------------------------------------------ preferência
    def set_preference(self, enabled: bool) -> User:
        self.user.sync_enabled = bool(enabled)
        self.db.commit()
        self.db.refresh(self.user)
        return self.user

    # ------------------------------------------------------------------ estado
    def state(self) -> dict:
        self.ensure_enabled()
        picks = self.db.scalars(
            select(SyncAutomationPick.automation_id).where(SyncAutomationPick.user_id == self.user.id)
        ).all()
        checks = self.db.scalars(
            select(SyncCheck).where(SyncCheck.user_id == self.user.id).order_by(SyncCheck.project, SyncCheck.name)
        ).all()
        return {"automation_ids": sorted(picks), "checks": checks}

    def set_picks(self, automation_ids: list[int]) -> list[int]:
        self.ensure_enabled()
        wanted = sorted(set(automation_ids))
        valid = set(self.db.scalars(select(Automation.id).where(Automation.id.in_(wanted))).all()) if wanted else set()
        self.db.execute(delete(SyncAutomationPick).where(SyncAutomationPick.user_id == self.user.id))
        for automation_id in wanted:
            if automation_id in valid:
                self.db.add(SyncAutomationPick(user_id=self.user.id, automation_id=automation_id))
        self.db.commit()
        return sorted(valid)

    # ------------------------------------------------------------------ sistemas externos
    def _get_check(self, check_id: int) -> SyncCheck:
        check = self.db.get(SyncCheck, check_id)
        if check is None or check.user_id != self.user.id:
            raise NotFoundException("Sistema não encontrado.")
        return check

    def create_check(self, data: dict) -> SyncCheck:
        self.ensure_enabled()
        count = len(self.db.scalars(select(SyncCheck.id).where(SyncCheck.user_id == self.user.id)).all())
        if count >= MAX_CHECKS_PER_USER:
            raise ValidationException(f"Limite de {MAX_CHECKS_PER_USER} sistemas por pessoa.")
        data = {**data, "url": validate_url(data["url"])}
        check = SyncCheck(user_id=self.user.id, **data)
        self.db.add(check)
        self.db.commit()
        self.db.refresh(check)
        return check

    def update_check(self, check_id: int, data: dict) -> SyncCheck:
        self.ensure_enabled()
        check = self._get_check(check_id)
        data = {**data, "url": validate_url(data["url"])}
        for key, value in data.items():
            setattr(check, key, value)
        self.db.commit()
        self.db.refresh(check)
        return check

    def delete_check(self, check_id: int) -> None:
        self.ensure_enabled()
        self.db.delete(self._get_check(check_id))
        self.db.commit()

    def ping(self, check_id: int) -> SyncCheck:
        self.ensure_enabled()
        check = self._get_check(check_id)
        ok, status_code, latency_ms, error = self._request(check)
        check.last_ping_at = datetime.now(UTC)
        check.last_ok = ok
        check.last_status_code = status_code
        check.last_latency_ms = latency_ms
        check.last_error = error
        self.db.commit()
        self.db.refresh(check)
        return check

    @staticmethod
    def _request(check: SyncCheck) -> tuple[bool, int | None, int | None, str | None]:
        host = urlparse(check.url).hostname or ""
        blocked = _blocked_address(host)
        if blocked:
            return False, None, None, blocked

        request = urllib.request.Request(check.url, headers={"User-Agent": USER_AGENT}, method="GET")
        started = time.monotonic()
        status_code: int | None = None
        error: str | None = None
        try:
            with urllib.request.urlopen(request, timeout=check.timeout_seconds) as response:
                status_code = response.status
                response.read(1)  # só prova que respondeu; o corpo não interessa
        except urllib.error.HTTPError as exc:
            status_code = exc.code
        except urllib.error.URLError as exc:
            error = str(exc.reason)[:300]
        except TimeoutError:
            error = f"Sem resposta em {check.timeout_seconds}s."
        except OSError as exc:
            error = str(exc)[:300]
        latency_ms = int((time.monotonic() - started) * 1000)

        if status_code is None:
            return False, None, latency_ms, error or "Sem resposta."

        if check.expected_status is not None:
            ok = status_code == check.expected_status
        else:
            ok = status_code < 400
        return ok, status_code, latency_ms, None if ok else f"Respondeu {status_code}."
