"""Versões pelo Git (prévia de sincronização) e Release (fixar versão). Usa um repositório git local como remoto."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.core.exceptions import ConflictException, ValidationException
from app.models.bot import Bot
from app.repositories.bot_repository import BotRepository
from app.repositories.task_repository import TaskRepository
from app.services.bot_version_service import BotVersionService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture

GIT_AVAILABLE = shutil.which("git") is not None


def git(cwd, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "Dev Teste", "GIT_AUTHOR_EMAIL": "dev@x",
           "GIT_COMMITTER_NAME": "Dev Teste", "GIT_COMMITTER_EMAIL": "dev@x"}
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, env=env).stdout


@unittest.skipUnless(GIT_AVAILABLE, "git não instalado")
class GitVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="orka_git_"))
        self._old_runtime = os.environ.get("ORKAFLOW_RUNTIME_DIR")
        os.environ["ORKAFLOW_RUNTIME_DIR"] = str(self.tmp / "runtime")

        self.remote = self.tmp / "remote"
        self.remote.mkdir()
        git(self.remote, "init", "-b", "main")
        self.commit("main.py: primeira versao")
        self.commit("corrige leitura da planilha")

        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner("r1")
        self.auto, self.first_version = self.f.automation(runners=[self.runner])
        self.bot = self.db.get(Bot, self.auto.bot_id)
        # A fixture cria uma versão "1" sem commit (como as versões antigas, cadastradas à mão).
        self.first_version.version = "1.0.0"
        self.bot.source_url = self.remote.as_uri()
        self.db.commit()
        self.svc = BotVersionService(self.db)

    def tearDown(self):
        if self._old_runtime is None:
            os.environ.pop("ORKAFLOW_RUNTIME_DIR", None)
        else:
            os.environ["ORKAFLOW_RUNTIME_DIR"] = self._old_runtime
        shutil.rmtree(self.tmp, ignore_errors=True)

    def commit(self, message):
        (self.remote / "log.txt").write_text(message + "\n", encoding="utf-8")
        git(self.remote, "add", "-A")
        git(self.remote, "commit", "-m", message)
        return git(self.remote, "rev-parse", "HEAD").strip()

    def save_from_preview(self, preview, version=None):
        return self.svc.create({
            "bot_id": self.bot.id,
            "version": version or preview["suggested_version"],
            "storage_type": "git",
            "commit_hash": preview["head"]["hash"],
            "branch": preview["branch"],
            "changelog": preview["changelog"],
            "commit_author": preview["head"]["author"],
            "committed_at": preview["head"]["committed_at"],
            "created_by": self.f.user.id,
        })

    def test_first_sync_suggests_next_version_and_brings_commits(self):
        preview = self.svc.git_preview(self.bot.id)

        self.assertEqual(preview["status"], "nova_versao")
        self.assertEqual(preview["branch"], "main")
        self.assertEqual(preview["suggested_version"], "1.0.1", "incrementa a última versão (1.0.0)")
        self.assertEqual(preview["head"]["message"], "corrige leitura da planilha")
        self.assertEqual(preview["head"]["author"], "Dev Teste")
        self.assertIn("corrige leitura da planilha", preview["changelog"])
        self.assertIn("main.py: primeira versao", preview["changelog"])

    def test_after_saving_it_is_in_sync_and_next_commit_only_brings_new_messages(self):
        saved = self.save_from_preview(self.svc.git_preview(self.bot.id))
        self.assertEqual(saved.commit_author, "Dev Teste")
        self.assertIsNotNone(saved.committed_at)

        in_sync = self.svc.git_preview(self.bot.id)
        self.assertEqual(in_sync["status"], "sincronizado")

        self.commit("salvar como pelo teclado")
        ahead = self.svc.git_preview(self.bot.id)
        self.assertEqual(ahead["status"], "nova_versao")
        self.assertEqual(ahead["suggested_version"], "1.0.2")
        self.assertEqual([c["message"] for c in ahead["commits"]], ["salvar como pelo teclado"])

    def test_tag_on_head_is_used_as_version(self):
        git(self.remote, "tag", "v2.0.0")
        self.assertEqual(self.svc.git_preview(self.bot.id)["suggested_version"], "2.0.0")

    def test_same_commit_twice_is_refused(self):
        preview = self.svc.git_preview(self.bot.id)
        self.save_from_preview(preview)
        with self.assertRaises(ConflictException):
            self.save_from_preview(preview, version="9.9.9")

    def test_old_commit_already_registered_points_to_release(self):
        old = self.save_from_preview(self.svc.git_preview(self.bot.id))
        self.commit("nova funcionalidade")
        self.save_from_preview(self.svc.git_preview(self.bot.id))
        git(self.remote, "reset", "--hard", "HEAD~1")  # Git voltou para o commit antigo

        preview = self.svc.git_preview(self.bot.id)
        self.assertEqual(preview["status"], "ja_registrado")
        self.assertEqual(preview["existing_version_id"], old.id)

    def test_url_change_is_followed(self):
        self.svc.git_preview(self.bot.id)  # cria o cache com a URL antiga
        other = self.tmp / "other"
        shutil.copytree(self.remote, other)
        (other / "log.txt").write_text("x", encoding="utf-8")
        git(other, "add", "-A")
        git(other, "commit", "-m", "commit so no repositorio novo")
        self.bot.source_url = other.as_uri()
        self.db.commit()

        self.assertEqual(self.svc.git_preview(self.bot.id)["head"]["message"], "commit so no repositorio novo")

    def test_bad_url_gives_clear_error_without_token(self):
        self.bot.source_url = "https://usuario:TOKENSECRETO@127.0.0.1:9/naoexiste.git"
        self.db.commit()
        with self.assertRaises(ValidationException) as ctx:
            self.svc.git_preview(self.bot.id)
        self.assertNotIn("TOKENSECRETO", ctx.exception.detail)

    def test_release_pins_version_for_tasks_and_worker(self):
        v1 = self.save_from_preview(self.svc.git_preview(self.bot.id))
        self.commit("versao com bug")
        v2 = self.save_from_preview(self.svc.git_preview(self.bot.id))
        self.bot.auto_update = True
        self.db.commit()
        task_repo = TaskRepository(self.db)
        self.assertEqual(task_repo.get_latest_bot_version_for_bot(self.bot.id).id, v2.id)

        released = self.svc.release(v1.id)

        self.assertTrue(released.in_use)
        self.assertTrue(released.pinned)
        self.assertEqual(task_repo.get_latest_bot_version_for_bot(self.bot.id).id, v1.id)
        self.assertEqual(BotRepository.get_latest_versions_map(self.db, [self.bot.id])[self.bot.id], v1.version)

        sync = WorkerService(self.db).sync_runner(SimpleNamespace(uuid=self.runner.uuid, token=self.f.token, host_name="HOST1", ip=None))
        payload = next(b for b in sync.bots if b.get("bot_id") == self.bot.id) if isinstance(sync.bots[0], dict) else None
        if payload is None:
            payload = next(b.model_dump() for b in sync.bots if b.bot_id == self.bot.id)
        self.assertEqual(payload["commit_hash"], v1.commit_hash)
        self.assertFalse(payload["auto_update"], "com Release o worker faz checkout do commit, não puxa a branch")

        listed = {v.id: v for v in self.svc.list()}
        self.assertTrue(listed[v1.id].in_use)
        self.assertFalse(listed[v2.id].in_use)

    def test_release_on_newest_unpins_and_new_version_unpins(self):
        v1 = self.save_from_preview(self.svc.git_preview(self.bot.id))
        self.commit("outra")
        v2 = self.save_from_preview(self.svc.git_preview(self.bot.id))

        self.svc.release(v1.id)
        self.assertEqual(self.bot.pinned_version_id, v1.id)
        self.svc.release(v2.id)
        self.assertIsNone(self.bot.pinned_version_id)

        self.svc.release(v1.id)
        self.commit("mais uma")
        v3 = self.save_from_preview(self.svc.git_preview(self.bot.id))
        self.assertIsNone(self.bot.pinned_version_id, "versão nova solta o Release")
        self.assertTrue(v3.in_use)


if __name__ == "__main__":
    unittest.main()
