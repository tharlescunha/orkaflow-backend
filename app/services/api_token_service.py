"""Tokens pessoais de integração (MCP, scripts, outras IAs).

O token vale com as permissões do próprio usuário. Só o hash fica no banco; o valor
completo aparece uma única vez, na criação. Formato: ``ork_<aleatório>``.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, ValidationException
from app.models.api_token import ApiToken
from app.models.user import User
from app.services.task_rules import as_aware

TOKEN_PREFIX = "ork_"
MAX_ACTIVE_TOKENS_PER_USER = 20
# Gravar "último uso" a cada chamada geraria um UPDATE por requisição do MCP.
LAST_USED_RESOLUTION = timedelta(minutes=5)


def is_api_token(raw: str | None) -> bool:
    return bool(raw) and raw.startswith(TOKEN_PREFIX)


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def to_read(token: ApiToken) -> dict:
    now = datetime.now(UTC)
    expires_at = as_aware(token.expires_at)
    if token.revoked_at is not None:
        status = "revogado"
    elif expires_at is not None and expires_at <= now:
        status = "expirado"
    else:
        status = "ativo"
    return {
        "id": token.id,
        "name": token.name,
        "token_prefix": token.token_prefix,
        "status": status,
        "created_at": token.created_at,
        "expires_at": token.expires_at,
        "last_used_at": token.last_used_at,
        "revoked_at": token.revoked_at,
    }


def list_tokens(db: Session, user_id: int) -> list[ApiToken]:
    return list(
        db.scalars(
            select(ApiToken).where(ApiToken.user_id == user_id).order_by(ApiToken.id.desc())
        )
    )


def create_token(db: Session, user: User, name: str, expires_in_days: int | None) -> tuple[ApiToken, str]:
    name = (name or "").strip()
    if not name:
        raise ValidationException("Dê um nome ao token (ex.: Claude do Tharles).")
    if expires_in_days is not None and not (1 <= expires_in_days <= 3650):
        raise ValidationException("A validade deve ser entre 1 e 3650 dias (ou sem validade).")

    active = [t for t in list_tokens(db, user.id) if to_read(t)["status"] == "ativo"]
    if len(active) >= MAX_ACTIVE_TOKENS_PER_USER:
        raise ValidationException(
            f"Limite de {MAX_ACTIVE_TOKENS_PER_USER} tokens ativos. Revogue algum que não use mais."
        )

    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    token = ApiToken(
        user_id=user.id,
        name=name[:120],
        token_prefix=raw[:12],
        token_hash=_hash(raw),
        expires_at=(datetime.now(UTC) + timedelta(days=expires_in_days)) if expires_in_days else None,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, raw


def revoke_token(db: Session, user_id: int, token_id: int) -> ApiToken:
    token = db.get(ApiToken, token_id)
    if token is None or token.user_id != user_id:
        raise NotFoundException("Token não encontrado.")
    if token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        db.commit()
        db.refresh(token)
    return token


def authenticate(db: Session, raw: str) -> User | None:
    """Usuário dono do token, ou None se o token não existe, foi revogado ou expirou."""
    token = db.scalar(select(ApiToken).where(ApiToken.token_hash == _hash(raw)))
    if token is None or not hmac.compare_digest(token.token_hash, _hash(raw)):
        return None
    if token.revoked_at is not None:
        return None

    now = datetime.now(UTC)
    expires_at = as_aware(token.expires_at)
    if expires_at is not None and expires_at <= now:
        return None

    last_used = as_aware(token.last_used_at)
    if last_used is None or now - last_used >= LAST_USED_RESOLUTION:
        token.last_used_at = now
        db.commit()

    return db.get(User, token.user_id)
