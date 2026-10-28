"""Ambientes de Git (out/2026): token por prefixo de URL.

Regra única na hora de usar um link de repositório:
1. Link já com usuário/token (``https://user:token@...``): usa como está. Bots antigos não mudam.
2. Link limpo: procura o ambiente ativo cujo prefixo casa com o começo do link (o mais longo ganha)
   e monta ``https://[user:]token@host/caminho``.
3. Sem ambiente: devolve o link como veio (clone público) e, no cadastro do bot, recusa com mensagem clara.

O token nunca sai do backend em texto: a API devolve só os últimos caracteres (``token_hint``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote, unquote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException, NotFoundException, ValidationException
from app.core.security import decrypt_credential_value, encrypt_credential_value
from app.models.git_environment import GitEnvironment

# Aviso de vencimento com esta antecedência.
EXPIRY_WARNING_DAYS = 15

_SCHEME_RE = re.compile(r"(?i)^([a-z][a-z0-9+.-]*://)(.*)$")


def split_url(url: str | None) -> tuple[str, str | None, str]:
    """``https://user:tok@host/x`` → ('https://', 'user:tok', 'host/x'). Sem userinfo → (scheme, None, resto)."""
    raw = (url or "").strip()
    match = _SCHEME_RE.match(raw)
    if not match:
        return "", None, raw
    scheme, rest = match.group(1), match.group(2)
    authority, _, path = rest.partition("/")
    if "@" not in authority:
        return scheme, None, rest
    userinfo, _, host = authority.rpartition("@")
    return scheme, userinfo, host + ("/" + path if path else "")


def url_has_credentials(url: str | None) -> bool:
    """True só com ``usuario:senha@`` (senha não vazia). O DevOps gera links ``https://alzgraos@dev.azure.com/...``,
    com o usuário sozinho: isso NÃO é token, e o ambiente precisa completar."""
    _, userinfo, _ = split_url(url)
    if not userinfo or ":" not in userinfo:
        return False
    return bool(userinfo.split(":", 1)[1])


def strip_userinfo(url: str | None) -> str:
    scheme, _, rest = split_url(url)
    return f"{scheme}{rest}" if scheme else rest


def normalize_prefix(value: str | None) -> str:
    """Minúsculas, sem %20, sem usuário e com barra no fim, para comparar prefixo com link sem surpresa."""
    text = unquote(strip_userinfo(value)).lower()
    if not text:
        return ""
    return text if text.endswith("/") else text + "/"


def normalize_url_for_match(url: str | None) -> str:
    return unquote(strip_userinfo(url)).lower()


def expiry_info(expires_at: datetime | None, now: datetime | None = None) -> tuple[str, int | None]:
    """('valido' | 'vence_em_breve' | 'vencido', dias até vencer)."""
    if expires_at is None:
        return "valido", None
    now = now or datetime.now(UTC)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    days = (expires_at - now).days
    if expires_at <= now:
        return "vencido", days
    if days <= EXPIRY_WARNING_DAYS:
        return "vence_em_breve", days
    return "valido", days


@dataclass
class ResolvedUrl:
    url: str
    # link | ambiente | nenhum
    token_source: str
    environment: GitEnvironment | None = None


class GitEnvironmentService:
    def __init__(self, db: Session):
        self.db = db

    # ----------------------------------------------------------------- CRUD (admin)
    def list(self) -> list[dict]:
        rows = self.db.scalars(select(GitEnvironment).order_by(GitEnvironment.active.desc(), GitEnvironment.name.asc())).all()
        return [self.to_read(row) for row in rows]

    def get(self, environment_id: int) -> GitEnvironment:
        env = self.db.get(GitEnvironment, environment_id)
        if env is None:
            raise NotFoundException("Ambiente de Git não encontrado.")
        return env

    def create(self, data: dict, user_id: int | None = None) -> GitEnvironment:
        token = (data.get("token") or "").strip()
        if not token:
            raise ValidationException("Informe o token do ambiente.")
        prefix = normalize_prefix(data["url_prefix"])
        self._ensure_prefix_free(prefix, exclude_id=None)
        env = GitEnvironment(
            name=data["name"].strip(),
            url_prefix=prefix,
            username=(data.get("username") or "").strip() or None,
            token_encrypted=encrypt_credential_value(token),
            token_hint=_hint(token),
            expires_at=data.get("expires_at"),
            active=bool(data.get("active", True)),
            created_by=user_id,
            updated_by=user_id,
        )
        self.db.add(env)
        self.db.commit()
        self.db.refresh(env)
        return env

    def update(self, environment_id: int, data: dict, user_id: int | None = None) -> GitEnvironment:
        env = self.get(environment_id)
        prefix = normalize_prefix(data["url_prefix"])
        self._ensure_prefix_free(prefix, exclude_id=env.id)
        env.name = data["name"].strip()
        env.url_prefix = prefix
        env.username = (data.get("username") or "").strip() or None
        env.expires_at = data.get("expires_at")
        env.active = bool(data.get("active", True))
        token = (data.get("token") or "").strip()
        if token:
            env.token_encrypted = encrypt_credential_value(token)
            env.token_hint = _hint(token)
        env.updated_by = user_id
        self.db.commit()
        self.db.refresh(env)
        return env

    def delete(self, environment_id: int) -> None:
        env = self.get(environment_id)
        self.db.delete(env)
        self.db.commit()

    def _ensure_prefix_free(self, prefix: str, exclude_id: int | None) -> None:
        if not prefix:
            raise ValidationException("Informe o prefixo do link.")
        stmt = select(GitEnvironment).where(GitEnvironment.url_prefix == prefix)
        if exclude_id is not None:
            stmt = stmt.where(GitEnvironment.id != exclude_id)
        if self.db.scalars(stmt).first() is not None:
            raise ConflictException("Já existe um ambiente com esse prefixo.")

    @staticmethod
    def to_read(env: GitEnvironment) -> dict:
        status, days = expiry_info(env.expires_at)
        return {
            "id": env.id,
            "name": env.name,
            "url_prefix": env.url_prefix,
            "username": env.username,
            "token_hint": env.token_hint,
            "expires_at": env.expires_at,
            "expiry_status": status,
            "days_to_expire": days,
            "active": env.active,
            "created_at": env.created_at,
            "updated_at": env.updated_at,
        }

    # ----------------------------------------------------------------- uso
    def match(self, url: str | None) -> GitEnvironment | None:
        """Ambiente ativo cujo prefixo casa com o link (o prefixo mais longo ganha)."""
        target = normalize_url_for_match(url)
        if not target:
            return None
        best: GitEnvironment | None = None
        for env in self.db.scalars(select(GitEnvironment).where(GitEnvironment.active == True)).all():  # noqa: E712
            prefix = normalize_prefix(env.url_prefix)
            if prefix and target.startswith(prefix) and (best is None or len(prefix) > len(normalize_prefix(best.url_prefix))):
                best = env
        return best

    def resolve(self, url: str | None) -> ResolvedUrl:
        """Link pronto para clonar. Nunca levanta: sem ambiente devolve o link como veio."""
        raw = (url or "").strip()
        if not raw:
            return ResolvedUrl(url=raw, token_source="nenhum")
        if url_has_credentials(raw):
            return ResolvedUrl(url=raw, token_source="link")
        env = self.match(raw)
        if env is None:
            return ResolvedUrl(url=raw, token_source="nenhum")
        try:
            token = decrypt_credential_value(env.token_encrypted)
        except ValueError:
            return ResolvedUrl(url=raw, token_source="nenhum")
        scheme, link_user, rest = split_url(raw)
        # Usuário que já veio no link (ex.: alzgraos@ do DevOps) tem prioridade; senão o do ambiente; senão só o token.
        username = (link_user.split(":", 1)[0] if link_user else "") or env.username or ""
        userinfo = quote(token, safe="")
        if username:
            userinfo = f"{quote(username, safe='')}:{userinfo}"
        return ResolvedUrl(url=f"{scheme}{userinfo}@{rest}", token_source="ambiente", environment=env)

    def resolve_url(self, url: str | None) -> str | None:
        """Atalho para quem só quer o link: worker e prévia de versão."""
        if url is None:
            return None
        return self.resolve(url).url

    def check(self, url: str | None) -> dict:
        """O que o formulário do bot mostra abaixo do link."""
        resolved = self.resolve(url)
        if resolved.token_source == "link":
            return {
                "token_source": "link",
                "environment_id": None,
                "environment_name": None,
                "expiry_status": None,
                "days_to_expire": None,
                "message": "Token do próprio link: vai ser usado como está.",
            }
        if resolved.token_source == "ambiente" and resolved.environment is not None:
            env = resolved.environment
            status, days = expiry_info(env.expires_at)
            if status == "vencido":
                tail = " O token desse ambiente está vencido: troque em Configurações."
            elif status == "vence_em_breve":
                tail = f" O token vence em {days} dia(s)."
            else:
                tail = ""
            return {
                "token_source": "ambiente",
                "environment_id": env.id,
                "environment_name": env.name,
                "expiry_status": status,
                "days_to_expire": days,
                "message": f"Sem token no link: vai usar o token do ambiente {env.name}.{tail}",
            }
        return {
            "token_source": "nenhum",
            "environment_id": None,
            "environment_name": None,
            "expiry_status": None,
            "days_to_expire": None,
            "message": (
                "Nenhum token para esse endereço: cole o link com o token ou cadastre o ambiente "
                "em Configurações → Ambientes de Git."
            ),
        }

    def ensure_usable_for_bot(self, url: str | None) -> None:
        """Cadastro/edição do bot: link limpo só passa se algum ambiente cobrir o endereço."""
        raw = (url or "").strip()
        if not raw or url_has_credentials(raw):
            return
        if self.match(raw) is None:
            raise ValidationException(
                "Nenhum token para esse endereço: cole o link com o token ou cadastre o ambiente "
                "em Configurações → Ambientes de Git."
            )


def _hint(token: str) -> str:
    return token[-4:] if len(token) >= 8 else ""
