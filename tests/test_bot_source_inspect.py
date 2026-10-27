"""Novo bot: validar o link do Git e ler nome, descrição (README), último commit e última tag."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app.core.exceptions import ValidationException
from app.services.git_repo_service import _description_from_readme, _name_from_url, inspect_source

GIT_AVAILABLE = shutil.which("git") is not None


def git(cwd, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Dev Teste", "GIT_AUTHOR_EMAIL": "dev@x",
           "GIT_COMMITTER_NAME": "Dev Teste", "GIT_COMMITTER_EMAIL": "dev@x"}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout


class NameAndDescriptionTests(unittest.TestCase):
    def test_name_from_url_variants(self):
        self.assertEqual(_name_from_url("https://github.com/alz/BOT_Estoque.git"), "BOT_Estoque")
        self.assertEqual(_name_from_url("https://user:tok@dev.azure.com/org/proj/_git/RPA_X"), "RPA_X")
        self.assertEqual(_name_from_url("git@github.com:alz/bot-y.git"), "bot-y")
        self.assertEqual(_name_from_url("file:///tmp/remote/"), "remote")

    def test_description_skips_titles_badges_and_strips_markdown(self):
        readme = "# BOT X\n\n[![build](x)](y)\n\nRobô que **lê** a [planilha](http://p) do SAP.\n\nMais texto."
        self.assertEqual(_description_from_readme(readme), "Robô que lê a planilha do SAP.")
        self.assertIsNone(_description_from_readme("# Só título\n"))


@unittest.skipUnless(GIT_AVAILABLE, "git não instalado")
class InspectSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orka_inspect_"))
        self._old_runtime = os.environ.get("ORKAFLOW_RUNTIME_DIR")
        os.environ["ORKAFLOW_RUNTIME_DIR"] = str(self.tmp / "runtime")
        self.remote = self.tmp / "BOT_Teste"
        self.remote.mkdir()
        git(self.remote, "init", "-b", "main")
        (self.remote / "README.md").write_text("# BOT Teste\n\nExtrai o estoque do SAP todo dia.\n", encoding="utf-8")
        git(self.remote, "add", "-A")
        git(self.remote, "commit", "-m", "primeira versao")
        git(self.remote, "tag", "v1.2.0")
        (self.remote / "main.py").write_text("print(1)\n", encoding="utf-8")
        git(self.remote, "add", "-A")
        git(self.remote, "commit", "-m", "ajuste no main")

    def tearDown(self):
        if self._old_runtime is None:
            os.environ.pop("ORKAFLOW_RUNTIME_DIR", None)
        else:
            os.environ["ORKAFLOW_RUNTIME_DIR"] = self._old_runtime
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_reads_name_description_head_and_tag(self):
        info = inspect_source(self.remote.as_uri())
        self.assertEqual(info.name, "BOT_Teste")
        self.assertEqual(info.description, "Extrai o estoque do SAP todo dia.")
        self.assertEqual(info.branch, "main")
        self.assertEqual(info.head.message, "ajuste no main")
        self.assertEqual(info.latest_tag, "v1.2.0")
        self.assertEqual(info.suggested_version, "1.2.0")

    def test_second_call_reuses_cache_and_sees_new_commits(self):
        inspect_source(self.remote.as_uri())
        (self.remote / "x.txt").write_text("x", encoding="utf-8")
        git(self.remote, "add", "-A")
        git(self.remote, "commit", "-m", "commit novo")
        info = inspect_source(self.remote.as_uri())
        self.assertEqual(info.head.message, "commit novo")

    def test_invalid_url_is_a_friendly_validation_error(self):
        with self.assertRaises(ValidationException) as ctx:
            inspect_source((self.tmp / "nao_existe").as_uri())
        self.assertNotIn("Traceback", str(ctx.exception.detail))

    def test_empty_url(self):
        with self.assertRaises(ValidationException):
            inspect_source("   ")


class HiddenTokenTests(unittest.TestCase):
    """O painel nunca vê o token do link; salvar o link mascarado é recusado."""

    def setUp(self):
        from tests.test_concurrency_watchdog import Fixture
        self.f = Fixture()
        self.db = self.f.db
        self.auto, _ = self.f.automation(runners=[self.f.runner("r1")])

    def test_bot_read_masks_token_and_worker_keeps_it(self):
        from app.models.bot import Bot
        from app.services.bot_service import BotService
        bot = self.db.get(Bot, self.auto.bot_id)
        bot.source_url = "https://alz:tokenSecreto@dev.azure.com/org/proj/_git/RPA_X"
        self.db.commit()
        read = BotService(self.db).get(bot.id)
        self.assertEqual(read["source_url"], "https://***@dev.azure.com/org/proj/_git/RPA_X")
        self.assertIn("tokenSecreto", self.db.get(Bot, bot.id).source_url)

    def test_update_with_masked_url_is_refused(self):
        from app.services.bot_service import BotService
        with self.assertRaises(ValidationException):
            BotService(self.db).update(self.auto.bot_id, {"source_url": "https://***@dev.azure.com/org/_git/RPA_X"})

    def test_version_response_masks_artifact_path(self):
        from app.schemas.bot_version import BotVersionResponse
        from datetime import datetime, timezone
        resp = BotVersionResponse(
            id=1, bot_id=1, version="1.0.0", storage_type="local", is_active=True,
            artifact_path="https://alz:tokenSecreto@dev.azure.com/org/_git/RPA_X",
            created_at=datetime.now(timezone.utc),
        )
        self.assertEqual(resp.artifact_path, "https://***@dev.azure.com/org/_git/RPA_X")
