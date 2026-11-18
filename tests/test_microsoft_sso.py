"""Login com a conta Microsoft (SSO, nov/2026): o front faz o fluxo Authorization Code + PKCE e entrega o id_token ao
backend, que valida assinatura (chaves públicas da Microsoft), cliente, locatário, validade e nonce, acha o usuário pelo
e-mail e emite os tokens do Regente. Aqui a Microsoft é simulada com um par de chaves RSA gerado na hora."""
import hashlib
import hmac
import time
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt
from jose.utils import base64url_encode, long_to_bytes

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_token, get_password_hash
from app.domain.enums import UserRole
from app.models.user import User
from app.services.microsoft_sso_service import MicrosoftSsoService

from tests.test_concurrency_watchdog import Fixture

TENANT = "b5d994e3-9a81-46d2-8bbe-5fd485d73c6a"
CLIENT = "8d96616f-88e7-47b4-9c10-30d4c752bb95"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"


def make_key(kid):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA", "kid": kid, "use": "sig", "alg": "RS256",
        "n": base64url_encode(long_to_bytes(numbers.n)).decode(),
        "e": base64url_encode(long_to_bytes(numbers.e)).decode(),
    }
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return {"jwk": jwk, "pem": pem, "public_pem": key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()}


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = make_key("kid-1")
        cls.other_key = make_key("kid-1")  # mesma identificação, chave diferente (falsificação)

    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.user = User(name="Maria", login="maria.silva", email="maria.silva@alzgraos.com.br",
                         password_hash=get_password_hash("x"), role=UserRole.ADMIN, active=True)
        self.db.add(self.user)
        self.db.flush()
        self.fetches = []
        self.jwks = {"keys": [self.key["jwk"]]}

    def fetcher(self, tenant, force=False):
        self.fetches.append((tenant, force))
        return self.jwks

    def service(self, **kw):
        base = dict(tenant_id=TENANT, client_id=CLIENT, jwks_fetcher=self.fetcher)
        base.update(kw)
        return MicrosoftSsoService(self.db, **base)

    def token(self, key=None, kid="kid-1", **claims):
        now = int(time.time())
        payload = {
            "iss": ISSUER, "aud": CLIENT, "tid": TENANT, "sub": "abc", "name": "Maria Silva",
            "email": "maria.silva@alzgraos.com.br", "preferred_username": "maria.silva@alzgraos.com.br",
            "nonce": "nonce-1", "iat": now, "nbf": now, "exp": now + 3600,
        }
        payload.update(claims)
        payload = {k: v for k, v in payload.items() if v is not None}
        return jose_jwt.encode(payload, (key or self.key)["pem"], algorithm="RS256", headers={"kid": kid})


class ConfiguracaoTests(_Base):
    def test_sem_configuracao_o_login_fica_desligado(self):
        svc = MicrosoftSsoService(self.db, tenant_id=None, client_id=None, jwks_fetcher=self.fetcher)
        self.assertEqual(svc.public_config(), {"enabled": False, "tenant_id": None, "client_id": None})
        with self.assertRaises(ForbiddenException):
            svc.login(self.token(), "nonce-1")
        self.assertEqual(self.fetches, [])  # nem chega a buscar chaves

    def test_configurado_expoe_so_os_identificadores_publicos(self):
        self.assertEqual(self.service().public_config(), {"enabled": True, "tenant_id": TENANT, "client_id": CLIENT})

    def test_so_um_dos_dois_nao_liga(self):
        self.assertFalse(MicrosoftSsoService(self.db, tenant_id=TENANT, client_id="", jwks_fetcher=self.fetcher).public_config()["enabled"])


class EntradaTests(_Base):
    def test_token_valido_entra_como_o_usuario_do_email(self):
        result = self.service().login(self.token(), "nonce-1")
        self.assertEqual(result["token_type"], "bearer")
        self.assertEqual(decode_token(result["access_token"])["sub"], str(self.user.id))
        self.assertEqual(decode_token(result["refresh_token"])["type"], "refresh")

    def test_email_sem_diferenciar_maiusculas(self):
        result = self.service().login(self.token(email="Maria.Silva@ALZGRAOS.com.br"), "nonce-1")
        self.assertEqual(decode_token(result["access_token"])["sub"], str(self.user.id))

    def test_sem_a_declaracao_email_usa_o_preferred_username(self):
        result = self.service().login(self.token(email=None), "nonce-1")
        self.assertEqual(decode_token(result["access_token"])["sub"], str(self.user.id))

    def test_conta_nao_cadastrada_e_recusada_dizendo_qual_e_o_email(self):
        with self.assertRaises(ForbiddenException) as ctx:
            self.service().login(self.token(email="outra.pessoa@alzgraos.com.br", preferred_username="outra.pessoa@alzgraos.com.br"), "nonce-1")
        self.assertIn("outra.pessoa@alzgraos.com.br", str(ctx.exception.detail))

    def test_usuario_inativo_e_recusado(self):
        self.user.active = False
        self.db.flush()
        with self.assertRaises(ForbiddenException):
            self.service().login(self.token(), "nonce-1")

    def test_nao_entra_por_login_do_regente_so_pelo_email(self):
        # uma identidade sem "@" (igual ao LOGIN de alguém) não abre a conta dessa pessoa
        with self.assertRaises(UnauthorizedException):
            self.service().login(self.token(email="maria.silva", preferred_username="maria.silva"), "nonce-1")


class RecusaTests(_Base):
    def assertRecusa(self, token, nonce="nonce-1", **kw):
        with self.assertRaises(UnauthorizedException):
            self.service(**kw).login(token, nonce)

    def test_outro_cliente_audience(self):
        self.assertRecusa(self.token(aud="00000000-0000-0000-0000-000000000000"))

    def test_outro_locatario_emissor(self):
        self.assertRecusa(self.token(iss="https://login.microsoftonline.com/11111111-1111-1111-1111-111111111111/v2.0"))

    def test_outro_locatario_tid(self):
        self.assertRecusa(self.token(tid="11111111-1111-1111-1111-111111111111"))

    def test_token_vencido(self):
        agora = int(time.time())
        self.assertRecusa(self.token(exp=agora - 120, iat=agora - 4000, nbf=agora - 4000))

    def test_nonce_diferente(self):
        self.assertRecusa(self.token(), nonce="outro-nonce")

    def test_nonce_nao_informado(self):
        self.assertRecusa(self.token(), nonce="")

    def test_token_sem_nonce(self):
        self.assertRecusa(self.token(nonce=None))

    def test_assinatura_falsificada_com_a_mesma_identificacao_de_chave(self):
        self.assertRecusa(self.token(key=self.other_key))

    def test_troca_de_algoritmo_hs256_assinado_com_a_chave_publica(self):
        # A biblioteca se recusa a montar este token; o atacante o montaria à mão, como aqui.
        cab = base64url_encode(b'{"alg":"HS256","typ":"JWT","kid":"kid-1"}').decode()
        corpo = base64url_encode(
            ('{"iss":"%s","aud":"%s","tid":"%s","email":"maria.silva@alzgraos.com.br","nonce":"nonce-1","exp":%d}'
             % (ISSUER, CLIENT, TENANT, int(time.time()) + 3600)).encode()
        ).decode()
        assinatura = base64url_encode(
            hmac.new(self.key["public_pem"].encode(), f"{cab}.{corpo}".encode(), hashlib.sha256).digest()
        ).decode()
        self.assertRecusa(f"{cab}.{corpo}.{assinatura}")

    def test_algoritmo_none(self):
        cab = base64url_encode(b'{"alg":"none","typ":"JWT","kid":"kid-1"}').decode()
        corpo = base64url_encode(
            ('{"iss":"%s","aud":"%s","tid":"%s","email":"maria.silva@alzgraos.com.br","nonce":"nonce-1","exp":%d}'
             % (ISSUER, CLIENT, TENANT, int(time.time()) + 3600)).encode()
        ).decode()
        self.assertRecusa(f"{cab}.{corpo}.")

    def test_texto_qualquer(self):
        self.assertRecusa("isto-nao-e-um-token")

    def test_falha_ao_buscar_as_chaves_da_microsoft(self):
        def quebra(tenant, force=False):
            raise OSError("sem rede")
        self.assertRecusa(self.token(), jwks_fetcher=quebra)

    def test_mensagem_de_recusa_nao_vaza_detalhes_tecnicos(self):
        with self.assertRaises(UnauthorizedException) as ctx:
            self.service().login(self.token(aud="outro"), "nonce-1")
        detalhe = str(ctx.exception.detail).lower()
        for termo in ("audience", "signature", "jwt", "iss"):
            self.assertNotIn(termo, detalhe)


class RotacaoDeChavesTests(_Base):
    def test_chave_desconhecida_busca_de_novo_uma_vez_e_aceita_a_nova(self):
        novo = make_key("kid-2")
        respostas = [{"keys": [self.key["jwk"]]}, {"keys": [self.key["jwk"], novo["jwk"]]}]

        def girando(tenant, force=False):
            self.fetches.append((tenant, force))
            return respostas[min(len(self.fetches) - 1, 1)]

        result = self.service(jwks_fetcher=girando).login(self.token(key=novo, kid="kid-2"), "nonce-1")
        self.assertEqual(decode_token(result["access_token"])["sub"], str(self.user.id))
        self.assertEqual(self.fetches, [(TENANT, False), (TENANT, True)])

    def test_chave_que_continua_desconhecida_e_recusada_sem_insistir(self):
        with self.assertRaises(UnauthorizedException):
            self.service().login(self.token(kid="kid-que-nao-existe"), "nonce-1")
        self.assertEqual(len(self.fetches), 2)


if __name__ == "__main__":
    unittest.main()
