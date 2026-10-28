"""Out/2026: ambientes de Git (token por prefixo de URL) e o link limpo no cadastro do bot."""
import unittest
from datetime import UTC, datetime, timedelta

from app.core.exceptions import ConflictException, ValidationException
from app.core.security import decrypt_credential_value
from app.services.bot_service import BotService
from app.services.git_environment_service import GitEnvironmentService, normalize_prefix, url_has_credentials

from tests.test_concurrency_watchdog import Fixture

DEVOPS = "https://dev.azure.com/alzgraos/PPI%20-%20ALZ%20Gr%C3%A3os/_git/RPA_INSUMOS_APROV_OV"
GITHUB = "https://github.com/tharlescunha/maestro.git"


class GitEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.svc = GitEnvironmentService(self.db)

    def _env(self, name, prefix, token="tok-1234-5678", **kw):
        data = dict(name=name, url_prefix=prefix, username=None, token=token, expires_at=None, active=True)
        data.update(kw)
        return self.svc.create(data, user_id=self.f.user.id)

    def test_prefix_is_normalized_and_token_is_encrypted(self):
        env = self._env("DevOps", "https://dev.azure.com/ALZGRAOS")
        self.assertEqual(env.url_prefix, "https://dev.azure.com/alzgraos/")
        self.assertNotIn("tok-1234", env.token_encrypted)
        self.assertEqual(decrypt_credential_value(env.token_encrypted), "tok-1234-5678")
        self.assertEqual(env.token_hint, "5678")
        read = self.svc.to_read(env)
        self.assertNotIn("token", read)
        self.assertNotIn("token_encrypted", read)

    def test_clean_link_gets_the_environment_token_and_link_with_token_is_untouched(self):
        self._env("DevOps", "https://dev.azure.com/alzgraos/")
        resolved = self.svc.resolve(DEVOPS)
        self.assertEqual(resolved.token_source, "ambiente")
        self.assertTrue(resolved.url.startswith("https://tok-1234-5678@dev.azure.com/alzgraos/"))
        self.assertTrue(resolved.url.endswith("/_git/RPA_INSUMOS_APROV_OV"))

        with_token = "https://user:abc@dev.azure.com/alzgraos/x/_git/y"
        self.assertEqual(self.svc.resolve(with_token).url, with_token)
        self.assertEqual(self.svc.resolve(with_token).token_source, "link")

    def test_username_goes_before_the_token(self):
        self._env("GitHub", "https://github.com/tharlescunha/", username="x-access-token")
        self.assertTrue(self.svc.resolve(GITHUB).url.startswith("https://x-access-token:tok-1234-5678@github.com/"))

    def test_longest_prefix_wins_and_github_is_per_account(self):
        self._env("GitHub genérico", "https://github.com/", token="generico")
        self._env("GitHub tharles", "https://github.com/tharlescunha/", token="do-tharles")
        self.assertTrue(self.svc.resolve(GITHUB).url.startswith("https://do-tharles@"))
        self.assertTrue(self.svc.resolve("https://github.com/fernando/robo.git").url.startswith("https://generico@"))

    def test_without_environment_link_stays_clean_and_bot_creation_is_refused(self):
        resolved = self.svc.resolve(GITHUB)
        self.assertEqual(resolved.token_source, "nenhum")
        self.assertEqual(resolved.url, GITHUB)
        with self.assertRaises(ValidationException):
            self.svc.ensure_usable_for_bot(GITHUB)
        # Link com token passa mesmo sem ambiente (bots antigos).
        self.svc.ensure_usable_for_bot("https://u:t@github.com/qualquer/coisa.git")

    def test_check_describes_the_source_and_expiry(self):
        self.assertEqual(self.svc.check(GITHUB)["token_source"], "nenhum")
        self._env("DevOps", "https://dev.azure.com/alzgraos/", expires_at=datetime.now(UTC) + timedelta(days=3))
        info = self.svc.check(DEVOPS)
        self.assertEqual(info["token_source"], "ambiente")
        self.assertEqual(info["environment_name"], "DevOps")
        self.assertEqual(info["expiry_status"], "vence_em_breve")
        self.assertIn("vence em", info["message"])
        self.assertEqual(self.svc.check("https://u:t@x.com/r.git")["token_source"], "link")

    def test_expired_environment_still_resolves_but_is_flagged(self):
        env = self._env("DevOps", "https://dev.azure.com/alzgraos/", expires_at=datetime.now(UTC) - timedelta(days=1))
        self.assertEqual(self.svc.to_read(env)["expiry_status"], "vencido")
        self.assertEqual(self.svc.resolve(DEVOPS).token_source, "ambiente")

    def test_duplicate_prefix_is_refused_and_update_keeps_token_when_blank(self):
        env = self._env("DevOps", "https://dev.azure.com/alzgraos/")
        with self.assertRaises(ConflictException):
            self._env("Outro", "https://DEV.azure.com/alzgraos")
        self.svc.update(env.id, dict(name="DevOps ALZ", url_prefix=env.url_prefix, username=None, token="", expires_at=None, active=True))
        self.db.refresh(env)
        self.assertEqual(env.name, "DevOps ALZ")
        self.assertEqual(decrypt_credential_value(env.token_encrypted), "tok-1234-5678")

    def test_helpers(self):
        self.assertTrue(url_has_credentials("https://a:b@host/x"))
        self.assertFalse(url_has_credentials("https://host/x@y"))
        self.assertEqual(normalize_prefix("https://dev.azure.com/alzgraos/PPI%20-%20ALZ"), "https://dev.azure.com/alzgraos/ppi - alz/")

    def test_bot_service_refuses_clean_link_without_environment_and_accepts_with(self):
        bots = BotService(self.db)
        data = dict(
            name="RPA_X", description=None, technology="python", repository_id=self.f.repo.id, source_type="git",
            execution_mode="background", source_url=DEVOPS, entrypoint="main.py", requirements_file=None,
            timeout_default=60, active=True, auto_update=False, reads_task_file_arg=False,
            initial_version="1.0.0", created_by=self.f.user.id,
        )
        with self.assertRaises(ValidationException):
            bots.create(dict(data))
        self._env("DevOps", "https://dev.azure.com/alzgraos/")
        bot = bots.create(dict(data))
        # O bot guarda o link limpo; o token entra só na hora de usar.
        self.assertEqual(bot.source_url, DEVOPS)
        self.assertTrue(self.svc.resolve_url(bot.source_url).startswith("https://tok-1234-5678@"))
