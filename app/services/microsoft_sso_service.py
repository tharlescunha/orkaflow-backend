"""Login com a conta Microsoft (SSO, nov/2026).

O front faz o fluxo Authorization Code + PKCE direto com a Microsoft e entrega o ``id_token`` aqui. Este serviço NÃO
confia no que o navegador diz: valida a assinatura com as chaves públicas da Microsoft (RS256), o cliente (``aud``), o
locatário (``iss`` e ``tid``), a validade e o ``nonce`` que o front gerou para aquele login. Só então procura o usuário
pelo **e-mail** (nunca pelo login) e emite os mesmos tokens do login com senha.

Ligado por configuração: ``MS_TENANT_ID`` e ``MS_CLIENT_ID`` (identificadores públicos, sem segredo). Sem os dois, o
botão do painel fica apagado e esta rota recusa tudo.
"""
from __future__ import annotations

import hmac
import json
import logging
import time
import urllib.request
from typing import Callable

from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.models.user import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

JWKS_URL = "https://login.microsoftonline.com/{tenant}/discovery/v2.0/keys"
ISSUER = "https://login.microsoftonline.com/{tenant}/v2.0"
JWKS_TTL_SECONDS = 3600
INVALID_LOGIN = "Não foi possível validar o login com a Microsoft. Tente entrar de novo."

# tenant -> (quando buscou, chaves). A Microsoft troca as chaves de tempos em tempos: chave desconhecida força nova busca.
_JWKS_CACHE: dict[str, tuple[float, dict]] = {}


def fetch_jwks(tenant: str, force: bool = False) -> dict:
    """Chaves públicas do locatário (com cache de 1 hora)."""
    cached = _JWKS_CACHE.get(tenant)
    if cached and not force and time.time() - cached[0] < JWKS_TTL_SECONDS:
        return cached[1]
    with urllib.request.urlopen(JWKS_URL.format(tenant=tenant), timeout=10) as response:  # noqa: S310 (URL fixa https)
        keys = json.loads(response.read().decode("utf-8"))
    _JWKS_CACHE[tenant] = (time.time(), keys)
    return keys


class MicrosoftSsoService:
    def __init__(
        self,
        db: Session,
        *,
        tenant_id: str | None = None,
        client_id: str | None = None,
        jwks_fetcher: Callable[..., dict] | None = None,
    ):
        self.db = db
        # None = usa a configuração do sistema; string vazia desliga (importante nos testes).
        self.tenant_id = (settings.ms_tenant_id if tenant_id is None else tenant_id) or None
        self.client_id = (settings.ms_client_id if client_id is None else client_id) or None
        self._fetch = jwks_fetcher or fetch_jwks

    # ------------------------------------------------------------------ configuração
    @property
    def enabled(self) -> bool:
        return bool(self.tenant_id and self.client_id)

    def public_config(self) -> dict:
        """O que o front precisa para montar o endereço de login (só identificadores públicos)."""
        if not self.enabled:
            return {"enabled": False, "tenant_id": None, "client_id": None}
        return {"enabled": True, "tenant_id": self.tenant_id, "client_id": self.client_id}

    # ------------------------------------------------------------------ validação do token
    def _signing_key(self, kid: str) -> dict:
        for force in (False, True):  # na segunda tentativa busca de novo (a Microsoft pode ter trocado as chaves)
            for key in self._fetch(self.tenant_id, force).get("keys", []):
                if key.get("kid") == kid:
                    return key
        raise UnauthorizedException(INVALID_LOGIN)

    def _validated_claims(self, id_token: str, nonce: str) -> dict:
        try:
            header = jwt.get_unverified_header(id_token)
            # Só RS256: recusa "none" e HS256 (troca de algoritmo assinada com a chave pública).
            if header.get("alg") != "RS256" or not header.get("kid"):
                raise UnauthorizedException(INVALID_LOGIN)
            key = self._signing_key(header["kid"])
            claims = jwt.decode(
                id_token,
                key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=ISSUER.format(tenant=self.tenant_id),
                options={"verify_at_hash": False},
            )
        except UnauthorizedException:
            raise
        except (JWTError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Login Microsoft recusado: token inválido (%s).", type(exc).__name__)
            raise UnauthorizedException(INVALID_LOGIN) from exc
        except Exception:  # noqa: BLE001 (rede fora do ar ao buscar as chaves, etc.)
            logger.exception("Login Microsoft: falha ao validar o token.")
            raise UnauthorizedException(INVALID_LOGIN)

        if claims.get("tid") != self.tenant_id:
            logger.warning("Login Microsoft recusado: locatário diferente.")
            raise UnauthorizedException(INVALID_LOGIN)
        token_nonce = str(claims.get("nonce") or "")
        if not nonce or not token_nonce or not hmac.compare_digest(token_nonce, nonce):
            logger.warning("Login Microsoft recusado: nonce não confere.")
            raise UnauthorizedException(INVALID_LOGIN)
        return claims

    @staticmethod
    def _email_of(claims: dict) -> str:
        for field in ("email", "preferred_username", "upn"):
            value = str(claims.get(field) or "").strip().lower()
            if "@" in value:
                return value
        return ""

    # ------------------------------------------------------------------ entrada
    def login(self, id_token: str, nonce: str) -> dict:
        if not self.enabled:
            raise ForbiddenException("O login com a conta Microsoft não está habilitado.")

        claims = self._validated_claims(id_token, nonce)
        email = self._email_of(claims)
        if not email:
            raise UnauthorizedException(INVALID_LOGIN)

        user = self.db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            logger.warning("Login Microsoft: %s não está cadastrado no Regente.", email)
            raise ForbiddenException(
                f"A conta Microsoft {email} não está cadastrada no Regente. "
                "Peça a um administrador para cadastrar esse e-mail no seu usuário."
            )
        if not user.active:
            raise ForbiddenException("Usuário inativo.")

        logger.info("Login Microsoft: usuário %s (%s) entrou.", user.id, user.login)
        return AuthService(self.db).issue_tokens(user)
