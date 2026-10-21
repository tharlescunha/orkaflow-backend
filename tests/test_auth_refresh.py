"""Refresh token inválido ou expirado deve virar 401 (sessão expirada), nunca erro 500."""
import unittest

from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, create_refresh_token
from app.services.auth_service import AuthService

from tests.test_concurrency_watchdog import Fixture


class RefreshTokenTests(unittest.TestCase):
    def setUp(self):
        self.service = AuthService(Fixture().db)

    def test_lixo_vira_401(self):
        with self.assertRaises(UnauthorizedException):
            self.service.refresh_token("isto-nao-e-um-jwt")

    def test_access_token_nao_serve_como_refresh(self):
        with self.assertRaises(UnauthorizedException):
            self.service.refresh_token(create_access_token(subject=1))

    def test_usuario_inexistente_vira_401(self):
        with self.assertRaises(UnauthorizedException):
            self.service.refresh_token(create_refresh_token(subject=999999))


if __name__ == "__main__":
    unittest.main()
