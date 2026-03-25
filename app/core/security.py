# app/core/security.py

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets
from typing import Any
import base64

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

from cryptography.fernet import Fernet, InvalidToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str | int, extra_data: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )

    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "exp": expire,
    }

    if extra_data:
        to_encode.update(extra_data)

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(subject: str | int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )

    to_encode = {
        "sub": str(subject),
        "type": "refresh",
        "exp": expire,
    }

    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError as exc:
        raise ValueError("Token inválido ou expirado.") from exc


def generate_runner_token() -> str:
    return secrets.token_urlsafe(48)


def get_runner_token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def verify_runner_token(token: str, token_hash: str | None) -> bool:
    if not token_hash:
        return False
    return get_runner_token_hash(token) == token_hash

def _get_credential_cipher() -> Fernet:
    raw_key = settings.jwt_secret_key.encode("utf-8")
    key = base64.urlsafe_b64encode(sha256(raw_key).digest())
    return Fernet(key)


def encrypt_credential_value(value: str) -> str:
    cipher = _get_credential_cipher()
    return cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_credential_value(encrypted_value: str) -> str:
    cipher = _get_credential_cipher()
    try:
        return cipher.decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Valor criptografado inválido.") from exc


def build_masked_preview(value: str) -> str:
    if not value:
        return "••••"
    if len(value) <= 4:
        return "•" * len(value)
    return f"{'•' * (len(value) - 4)}{value[-4:]}"