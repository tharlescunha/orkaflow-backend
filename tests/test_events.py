"""Eventos "Quando → Então" (out/2026): gatilho por task, condição sobre o retorno/código de saída,
disparo HTTP com etapas prévias fora da transação da task, e isolamento de erros."""
import json
import threading
import unittest
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.core.exceptions import ValidationException
from app.domain.enums import TaskStatus
from app.models.event_rule import EventRun
from app.models.task_telemetry import TaskTelemetry
from app.services import event_service as svc
from app.services.worker_service import WorkerService

from tests.test_concurrency_watchdog import Fixture


class _Handler(BaseHTTPRequestHandler):
    received: list[dict] = []

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        _Handler.received.append({"path": self.path, "headers": dict(self.headers), "body": body})
        if self.path == "/login":
            payload = b'{"access_token": "tok-123"}'
        elif self.path == "/fail":
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"boom")
            return
        else:
            payload = b'{"ok": true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args):  # silencia o servidor de teste
        return


def _serve():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class EventBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _serve()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        _Handler.received.clear()
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner("r1")
        self.auto, self.ver = self.f.automation(runners=[self.runner])

    def _rule(self, **kw):
        data = dict(
            name="Avisar", description=None, active=True, scope_type="automation", scope_id=self.auto.id,
            trigger_type="task_error", trigger_config={}, pre_steps=[], url=f"{self.base}/hook",
            method="POST", headers={"Content-Type": "application/json"},
            body_template='{"automacao": "{{automacao}}", "erro": "{{erro_resumo}}", "task": "{{task_id}}", "retorno": "{{retorno.status}}"}',
            timeout_seconds=5,
        )
        data.update(kw)
        return svc.create_rule(self.db, data, created_by=self.f.user.id)

    def _finished_task(self, status=TaskStatus.ERROR, **kw):
        return self.f.task(self.auto, self.ver, status=status, runner=self.runner, **kw)

    def _runs(self):
        return list(self.db.query(EventRun).order_by(EventRun.id).all())


class TriggerTests(EventBase):
    def test_error_rule_fires_on_error_not_on_success(self):
        self._rule()
        err = self._finished_task(TaskStatus.ERROR, final_message="RuntimeError: falhou")
        ok = self._finished_task(TaskStatus.FINISHED)
        self.assertEqual(svc.enqueue_for_task(self.db, err), 1)
        self.assertEqual(svc.enqueue_for_task(self.db, ok), 0)
        run = self._runs()[0]
        self.assertEqual(run.status, "pending")
        variables = json.loads(run.variables_json)
        self.assertEqual(variables["erro_resumo"], "RuntimeError: falhou")
        self.assertEqual(variables["automacao"], self.auto.label or self.auto.name)

    def test_scope_all_and_bot(self):
        other, other_ver = self.f.automation(runners=[self.runner])
        self._rule(scope_type="all", scope_id=None)
        self._rule(name="Por bot", scope_type="bot", scope_id=self.auto.bot_id)
        task_other = self.f.task(other, other_ver, status=TaskStatus.ERROR, runner=self.runner)
        self.assertEqual(svc.enqueue_for_task(self.db, task_other), 1)  # só a regra "all"
        task_mine = self._finished_task(TaskStatus.ERROR)
        self.assertEqual(svc.enqueue_for_task(self.db, task_mine), 2)

    def test_result_contains_with_and_without_value(self):
        self._rule(trigger_type="result_contains", trigger_config={"key": "status", "value": "reprovado"})
        self._rule(name="qualquer", trigger_type="result_contains", trigger_config={"key": "lote"})
        task = self._finished_task(TaskStatus.FINISHED, result_json=json.dumps({"status": "Reprovado", "lote": 7}))
        self.assertEqual(svc.enqueue_for_task(self.db, task), 2)
        task2 = self._finished_task(TaskStatus.FINISHED, result_json=json.dumps({"status": "aprovado"}))
        self.assertEqual(svc.enqueue_for_task(self.db, task2), 0)

    def test_exit_code_uses_telemetry(self):
        self._rule(trigger_type="exit_code", trigger_config={"code": 3})
        task = self._finished_task(TaskStatus.ERROR)
        self.db.add(TaskTelemetry(task_id=task.id, exit_code=3, captured_at=datetime.now(UTC)))
        self.db.flush()
        self.assertEqual(svc.enqueue_for_task(self.db, task), 1)
        self.assertEqual(json.loads(self._runs()[0].variables_json)["codigo_saida"], "3")

    def test_inactive_rule_does_not_fire(self):
        self._rule(active=False)
        self.assertEqual(svc.enqueue_for_task(self.db, self._finished_task()), 0)

    def test_validation(self):
        with self.assertRaises(ValidationException):
            self._rule(scope_id=None)
        with self.assertRaises(ValidationException):
            self._rule(trigger_type="result_contains", trigger_config={})
        with self.assertRaises(ValidationException):
            self._rule(trigger_type="exit_code", trigger_config={})


class DeliveryTests(EventBase):
    def test_pending_run_is_delivered_with_rendered_body(self):
        self._rule()
        task = self._finished_task(TaskStatus.ERROR, final_message="erro X", result_json='{"status": "reprovado"}')
        svc.enqueue_for_task(self.db, task)
        self.db.commit()
        self.assertEqual(svc.process_pending(self.db), 1)
        run = self._runs()[0]
        self.assertEqual(run.status, "success")
        self.assertTrue(run.ok)
        self.assertEqual(run.status_code, 200)
        body = json.loads(_Handler.received[-1]["body"])
        self.assertEqual(body["erro"], "erro X")
        self.assertEqual(body["task"], str(task.id))
        self.assertEqual(body["retorno"], "reprovado")

    def test_pre_step_token_is_used_and_masked_in_history(self):
        self._rule(
            pre_steps=[{"name": "Login", "method": "POST", "url": f"{self.base}/login", "headers": {},
                        "body_template": "{}", "extract": [{"variable": "token", "path": "access_token"}]}],
            headers={"Authorization": "Bearer {{token}}", "Content-Type": "application/json"},
        )
        svc.enqueue_for_task(self.db, self._finished_task())
        self.db.commit()
        svc.process_pending(self.db)
        self.assertEqual(_Handler.received[-1]["headers"].get("Authorization"), "Bearer tok-123")
        run = self._runs()[0]
        self.assertNotIn("tok-123", run.details_json or "")

    def test_failed_delivery_is_recorded_not_raised(self):
        self._rule(url=f"{self.base}/fail")
        svc.enqueue_for_task(self.db, self._finished_task())
        self.db.commit()
        svc.process_pending(self.db)
        run = self._runs()[0]
        self.assertEqual(run.status, "error")
        self.assertFalse(run.ok)
        self.assertEqual(run.status_code, 500)

    def test_run_test_uses_last_task_of_scope(self):
        rule = self._rule()
        task = self._finished_task(TaskStatus.ERROR, final_message="ultimo")
        self.db.commit()
        run = svc.run_test(self.db, rule.id)
        self.assertEqual(run.task_id, task.id)
        self.assertEqual(run.status, "test")
        self.assertIn("ultimo", _Handler.received[-1]["body"])


class WorkerHookTests(EventBase):
    def test_finish_task_enqueues_event_and_credential_alert_fires_credential_rule(self):
        self._rule(name="erro")
        self._rule(name="cred", trigger_type="credential_invalid",
                   body_template='{"cred": "{{credencial}}", "motivo": "{{motivo}}"}')
        task = self.f.task(self.auto, self.ver, status=TaskStatus.RUNNING, runner=self.runner)
        svc_worker = WorkerService(self.db)
        svc_worker.finish_task(task.id, self.f.payload(self.runner, status=TaskStatus.ERROR, final_message="x",
                                                       result_json=None, items_processed=None, items_failed=None))
        runs = self._runs()
        self.assertEqual([r.trigger_type for r in runs], ["task_error"])
