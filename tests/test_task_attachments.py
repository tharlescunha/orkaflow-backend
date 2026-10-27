"""Maestro fase 5: arquivos anexados à task pelo robô (attach)."""
import base64
import unittest

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.domain.enums import TaskStatus
from app.services.task_service import TaskService
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class AttachmentTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.db = self.f.db
        self.r = self.f.runner()
        self.auto, self.ver = self.f.automation(runners=[self.r])
        self.task = self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=self.r)
        self.svc = WorkerService(self.db)

    def _payload(self, runner=None, **kw):
        data = dict(filename="pedidos.xlsx", content_type="application/x", description="Pedidos", content_base64=base64.b64encode(b"abc").decode())
        data.update(kw)
        return self.f.payload(runner or self.r, **data)

    def test_worker_uploads_and_panel_lists_and_downloads(self):
        out = self.svc.create_task_attachment(self.task.id, self._payload())
        self.assertEqual(out["size_bytes"], 3)
        items, total = TaskService(self.db).list_task_attachments(self.task.id)
        self.assertEqual(total, 1)
        self.assertEqual((items[0]["filename"], items[0]["description"]), ("pedidos.xlsx", "Pedidos"))
        attachment = TaskService(self.db).get_task_attachment(self.task.id, out["attachment_id"])
        self.assertEqual(attachment.content, b"abc")
        with self.assertRaises(NotFoundException):
            TaskService(self.db).get_task_attachment(self.task.id + 99, out["attachment_id"])

    def test_limits_and_ownership(self):
        other = self.f.runner("r2", host="HOST2")
        with self.assertRaises(ForbiddenException):
            self.svc.create_task_attachment(self.task.id, self._payload(runner=other))
        with self.assertRaises(ValidationException):
            self.svc.create_task_attachment(self.task.id, self._payload(content_base64="nao-e-base64!!"))
        big = base64.b64encode(b"x" * (5 * 1024 * 1024 + 1)).decode()
        with self.assertRaises(ValidationException):
            self.svc.create_task_attachment(self.task.id, self._payload(content_base64=big))
        for i in range(10):
            self.svc.create_task_attachment(self.task.id, self._payload(filename=f"f{i}.txt"))
        with self.assertRaises(ValidationException):
            self.svc.create_task_attachment(self.task.id, self._payload(filename="f11.txt"))

    def test_filename_keeps_only_basename(self):
        out = self.svc.create_task_attachment(self.task.id, self._payload(filename="C:\\robos\\saida\\relatorio.pdf"))
        attachment = TaskService(self.db).get_task_attachment(self.task.id, out["attachment_id"])
        self.assertEqual(attachment.filename, "relatorio.pdf")
