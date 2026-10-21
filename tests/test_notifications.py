"""Notificação de falhas de agendamento: 3 falhas seguidas -> requisição configurável + pausa."""
import json
import threading
import unittest
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.core.exceptions import ValidationException
from app.domain.enums import (
    CalendarType,
    SchedulePolicy,
    ScheduleStatus,
    ScheduleType,
    TaskStatus,
)
from app.models.notification_channel import NotificationChannel
from app.models.schedule import Schedule
from app.models.task_error import TaskError
from app.services import notification_service as ns

from tests.test_concurrency_watchdog import Fixture


class _Stub(BaseHTTPRequestHandler):
    received: list = []
    status = 201

    def _reply(self, status, payload):
        data = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8")
        _Stub.received.append({"path": self.path, "headers": dict(self.headers), "body": body})

        if self.path == "/login":  # como o desk: chave no cabeçalho + PublicKey no corpo
            try:
                public_key = json.loads(body or "{}").get("PublicKey")
            except ValueError:
                public_key = None
            if self.headers.get("Authorization") == "chave-fixa" and public_key == "pub":
                return self._reply(200, '"TOK-ABC#123"')
            return self._reply(401, '{"erro": "login recusado"}')

        if self.path == "/chamado":
            if self.headers.get("Authorization") != "TOK-ABC#123":
                return self._reply(401, '{"erro": "token invalido"}')
            return self._reply(_Stub.status, "[98765]")

        return self._reply(_Stub.status, '{"id": 77}')

    do_PUT = do_PATCH = do_POST

    def log_message(self, *args):
        pass


class NotificationBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), _Stub)
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/chamados"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        _Stub.received = []
        _Stub.status = 201
        self.f = Fixture()
        self.db = self.f.db
        self.runner = self.f.runner()
        self.auto, self.version = self.f.automation(runners=[self.runner])

        original = ns.SEND_RETRY_DELAYS_SECONDS
        ns.SEND_RETRY_DELAYS_SECONDS = (0, 0)
        self.addCleanup(lambda: setattr(ns, "SEND_RETRY_DELAYS_SECONDS", original))

        self.schedule = Schedule(
            name="Agendamento_Estoque_PO",
            automation_id=self.auto.id,
            schedule_type=ScheduleType.CALENDAR,
            calendar_type=CalendarType.ONCE,
            policy=SchedulePolicy.CREATE_ALWAYS,
            status=ScheduleStatus.ACTIVE,
            active=True,
            timezone="UTC",
            next_run_at=datetime.now(UTC) + timedelta(hours=1),
        )
        self.db.add(self.schedule)
        self.db.flush()

    def channel(self, **overrides):
        channel = ns.get_or_create_channel(self.db)
        channel.enabled = True
        channel.url = self.url
        channel.body_template = (
            '{"titulo": "Falha em {{automacao}}", "descricao": "{{erro}}", "tasks": "{{task_ids}}"}'
        )
        for key, value in overrides.items():
            setattr(channel, key, value)
        self.db.add(channel)
        self.db.flush()
        return channel

    def run_task(self, status, error=None):
        task = self.f.task(self.auto, self.version, status=status, runner=self.runner, schedule_id=self.schedule.id)
        if error:
            self.db.add(TaskError(task_id=task.id, error_type="bot_exit_code", message=error))
            self.db.flush()
        return task


class RenderTests(unittest.TestCase):
    def test_json_body_escapes_quotes_and_line_breaks(self):
        erro = 'Falha no login "SAP"\nlinha 2 \\ barra'
        body = ns.render_template('{"descricao": "{{erro}}"}', {"erro": erro}, "json")
        self.assertEqual(json.loads(body)["descricao"], erro)

    def test_unknown_variable_is_kept_and_url_is_quoted(self):
        self.assertEqual(ns.render_template("{{nao_existe}}", {"erro": "x"}), "{{nao_existe}}")
        self.assertEqual(ns.render_template("q={{erro}}", {"erro": "a b&c"}, "url"), "q=a%20b%26c")

    def test_secret_headers_are_masked_in_preview(self):
        masked = ns.mask_headers({"Authorization": "Bearer abc", "X-Teste": "ok"})
        self.assertEqual(masked, {"Authorization": "***", "X-Teste": "ok"})


class ExtractTests(unittest.TestCase):
    def test_extract_paths(self):
        self.assertEqual(ns.extract_value('"abc#1"', ""), "abc#1")  # JSON string
        self.assertEqual(ns.extract_value("abc#1\n", "$"), "abc#1")  # texto cru
        self.assertEqual(ns.extract_value('{"data": {"token": "x"}}', "data.token"), "x")
        self.assertEqual(ns.extract_value("[98765]", "0"), "98765")
        self.assertEqual(ns.extract_value('{"itens": [{"id": 5}]}', "itens.0.id"), "5")

    def test_extract_missing_returns_none(self):
        self.assertIsNone(ns.extract_value('{"a": 1}', "b"))
        self.assertIsNone(ns.extract_value("[1]", "3"))
        self.assertIsNone(ns.extract_value("", ""))
        self.assertIsNone(ns.extract_value("null", ""))


class DeskLikeAuthFlowTests(NotificationBase):
    """Desk que exige login (token) antes de abrir o chamado."""

    base = ""

    def desk_channel(self, **overrides):
        base = self.url.rsplit("/", 1)[0]
        steps = [{
            "name": "Autenticar",
            "method": "POST",
            "url": f"{base}/login",
            "headers": {"Authorization": "chave-fixa"},
            "body_template": '{"PublicKey": "pub"}',
            "extract": [{"variable": "token", "path": ""}],
        }]
        channel = self.channel(
            url=f"{base}/chamado",
            method="PUT",
            headers_json=json.dumps({"Authorization": "{{token}}"}),
            body_template='{"TChamado": {"Assunto": "ERRO {{automacao}}", "Descricao": "{{erro}}"}}',
            pre_steps_json=json.dumps(steps),
        )
        for key, value in overrides.items():
            setattr(channel, key, value)
        self.db.flush()
        return channel

    def test_login_then_ticket_uses_the_token(self):
        self.desk_channel()

        result = ns.send_test(self.db)

        self.assertTrue(result["ok"], result)
        self.assertEqual([r["path"] for r in _Stub.received], ["/login", "/chamado"])
        self.assertEqual(_Stub.received[1]["headers"]["Authorization"], "TOK-ABC#123")
        self.assertIn("Automacao_Estoque_PO", _Stub.received[1]["body"])
        self.assertEqual(result["steps"], [
            {"name": "Autenticar", "ok": True, "status_code": 200, "error": None, "extracted": ["token"]},
        ])
        self.assertEqual(result["response_snippet"], "[98765]")

    def test_token_never_leaks_into_result_or_history(self):
        self.desk_channel()
        result = ns.send_test(self.db)

        self.assertNotIn("TOK-ABC#123", json.dumps(result))
        self.assertEqual(result["request_preview"]["headers"]["Authorization"], "***")
        for entry in ns.list_logs(self.db):
            self.assertNotIn("TOK-ABC", f"{entry.error} {entry.response_snippet}")

    def test_login_refused_stops_before_the_ticket(self):
        channel = self.desk_channel()
        steps = json.loads(channel.pre_steps_json)
        steps[0]["headers"] = {"Authorization": "chave-errada"}
        channel.pre_steps_json = json.dumps(steps)
        self.db.flush()

        result = ns.send_test(self.db)

        self.assertFalse(result["ok"])
        self.assertIn("Etapa 'Autenticar' falhou", result["error"])
        self.assertIn("login recusado", result["error"])
        self.assertIn("não foi executado", result["error"])
        self.assertEqual([r["path"] for r in _Stub.received], ["/login"], "o chamado não pode ser tentado")
        self.assertFalse(result["steps"][0]["ok"])

    def test_extract_not_found_fails_the_step(self):
        channel = self.desk_channel()
        steps = json.loads(channel.pre_steps_json)
        steps[0]["extract"] = [{"variable": "token", "path": "campo.inexistente"}]
        channel.pre_steps_json = json.dumps(steps)
        self.db.flush()

        result = ns.send_test(self.db)

        self.assertFalse(result["ok"])
        self.assertIn("Não encontrei", result["steps"][0]["error"])
        self.assertEqual([r["path"] for r in _Stub.received], ["/login"])

    def test_alert_flow_logs_in_on_every_attempt_and_pauses(self):
        self.desk_channel()
        for i in range(3):
            self.run_task(TaskStatus.ERROR, f"e{i}")

        self.assertEqual(ns.evaluate_failures(self.db), 1)

        self.assertEqual([r["path"] for r in _Stub.received], ["/login", "/chamado"])
        self.assertEqual(self.schedule.status, ScheduleStatus.PAUSED)
        self.assertTrue(ns.list_logs(self.db)[0].ok)

    def test_failed_attempts_redo_the_login(self):
        _Stub.status = 500  # o chamado falha: cada tentativa refaz o login (token pode ter vencido)
        self.desk_channel()
        for i in range(3):
            self.run_task(TaskStatus.ERROR, f"e{i}")

        ns.evaluate_failures(self.db)

        paths = [r["path"] for r in _Stub.received]
        self.assertEqual(paths.count("/login"), ns.SEND_ATTEMPTS)
        self.assertEqual(paths.count("/chamado"), ns.SEND_ATTEMPTS)

    def test_pre_steps_are_saved_and_returned(self):
        steps = [{
            "name": "Autenticar", "method": "post", "url": "http://x/login", "headers": {"A": "b"},
            "body_template": "{}", "extract": [{"variable": "token", "path": ""}],
        }]
        from app.schemas.notification import NotificationChannelUpdate

        payload = NotificationChannelUpdate(url=self.url, pre_steps=steps).model_dump(exclude_unset=True)
        read = ns.channel_to_read(ns.update_channel(self.db, payload))

        self.assertEqual(read["pre_steps"][0]["method"], "POST")
        self.assertEqual(read["pre_steps"][0]["extract"], [{"variable": "token", "path": ""}])

    def test_step_schema_validation(self):
        from pydantic import ValidationError

        from app.schemas.notification import NotificationStep

        with self.assertRaises(ValidationError):
            NotificationStep(url="ftp://x")
        with self.assertRaises(ValidationError):
            NotificationStep(url="http://x", extract=[{"variable": "1ruim", "path": ""}])
        with self.assertRaises(ValidationError):
            NotificationStep(url="http://x", method="DELETE")


class SqlServerCompatibilityTests(unittest.TestCase):
    """O sqlite aceita `IS 1`; o SQL Server não. Compila as consultas no dialeto do SQL Server."""

    def test_queries_compile_without_boolean_is_for_mssql(self):
        from sqlalchemy.dialects import mssql

        for stmt in (ns.enabled_channel_stmt(), ns.active_schedules_stmt()):
            sql = str(stmt.compile(dialect=mssql.dialect(), compile_kwargs={"literal_binds": True}))
            self.assertNotIn(" IS 1", sql)
            self.assertNotIn(" IS 0", sql)
            self.assertIn("= 1", sql)


class FailureStreakTests(NotificationBase):
    def test_disabled_channel_does_nothing(self):
        self.channel(enabled=False)
        for _ in range(3):
            self.run_task(TaskStatus.ERROR, "erro")
        self.assertEqual(ns.evaluate_failures(self.db), 0)
        self.assertEqual(_Stub.received, [])
        self.assertEqual(self.schedule.status, ScheduleStatus.ACTIVE)

    def test_three_failures_send_request_and_pause_schedule(self):
        self.channel(headers_json=json.dumps({"X-Token": "segredo-{{agendamento_id}}"}))
        ids = [self.run_task(TaskStatus.ERROR, f'Falha no login "SAP" #{i}').id for i in range(3)]

        self.assertEqual(ns.evaluate_failures(self.db), 1)

        self.assertEqual(len(_Stub.received), 1)
        request = _Stub.received[0]
        sent = json.loads(request["body"])  # JSON válido mesmo com aspas no erro
        self.assertIn("Falha em", sent["titulo"])
        self.assertIn('Falha no login "SAP" #2', sent["descricao"])
        self.assertEqual(sent["tasks"], ",".join(str(i) for i in ids))
        self.assertEqual(request["headers"]["X-Token"], f"segredo-{self.schedule.id}")

        self.db.refresh(self.schedule)
        self.assertEqual(self.schedule.status, ScheduleStatus.PAUSED)
        self.assertFalse(self.schedule.active)
        self.assertIn("pausado", self.schedule.last_error)

        logs = ns.list_logs(self.db)
        self.assertEqual(len(logs), 1)
        self.assertTrue(logs[0].ok and logs[0].paused_schedule)
        self.assertEqual(logs[0].status_code, 201)

    def test_success_in_the_middle_breaks_the_streak(self):
        self.channel()
        self.run_task(TaskStatus.ERROR, "e1")
        self.run_task(TaskStatus.ERROR, "e2")
        self.run_task(TaskStatus.FINISHED)
        self.run_task(TaskStatus.ERROR, "e3")
        self.assertEqual(ns.evaluate_failures(self.db), 0)
        self.assertEqual(self.schedule.status, ScheduleStatus.ACTIVE)

    def test_timeout_counts_as_failure_and_threshold_is_configurable(self):
        self.channel(failure_threshold=2)
        self.run_task(TaskStatus.TIMEOUT, "demorou")
        self.run_task(TaskStatus.ERROR, "erro")
        self.assertEqual(ns.evaluate_failures(self.db), 1)

    def test_same_failures_do_not_alert_again_after_reactivation(self):
        self.channel()
        for i in range(3):
            self.run_task(TaskStatus.ERROR, f"e{i}")
        ns.evaluate_failures(self.db)

        self.schedule.status = ScheduleStatus.ACTIVE
        self.schedule.active = True
        self.db.flush()

        self.assertEqual(ns.evaluate_failures(self.db), 0, "mesmas 3 falhas não podem realertar")

        for i in range(3):
            self.run_task(TaskStatus.ERROR, f"novo{i}")
        self.assertEqual(ns.evaluate_failures(self.db), 1, "3 falhas NOVAS alertam de novo")
        self.assertEqual(len(_Stub.received), 2)

    def test_send_failure_is_logged_retried_and_schedule_is_still_paused(self):
        _Stub.status = 500
        self.channel()
        for i in range(3):
            self.run_task(TaskStatus.ERROR, f"e{i}")

        ns.evaluate_failures(self.db)

        self.assertEqual(len(_Stub.received), ns.SEND_ATTEMPTS, "tenta 3 vezes")
        entry = ns.list_logs(self.db)[0]
        self.assertFalse(entry.ok)
        self.assertEqual(entry.status_code, 500)
        self.assertTrue(entry.paused_schedule)
        self.assertIn("falha ao notificar", self.schedule.last_error)

    def test_failures_from_before_enabling_do_not_count(self):
        hour_ago = datetime.now(UTC) - timedelta(hours=1)
        for i in range(3):
            task = self.run_task(TaskStatus.ERROR, f"antiga{i}")
            task.created_at = hour_ago
        self.db.flush()

        ns.update_channel(self.db, {"url": self.url, "enabled": True})  # ativa agora

        self.assertEqual(ns.evaluate_failures(self.db), 0, "falhas antigas não abrem chamado")
        self.assertEqual(_Stub.received, [])
        self.assertEqual(self.schedule.status, ScheduleStatus.ACTIVE)

        for i in range(3):
            self.run_task(TaskStatus.ERROR, f"nova{i}")

        self.assertEqual(ns.evaluate_failures(self.db), 1, "3 falhas depois de ativar alertam")

    def test_pause_options(self):
        self.channel(pause_schedule=False, deactivate_automation=True)
        for i in range(3):
            self.run_task(TaskStatus.ERROR, f"e{i}")
        ns.evaluate_failures(self.db)

        self.assertEqual(self.schedule.status, ScheduleStatus.ACTIVE, "pausar é opcional")
        self.db.refresh(self.auto)
        self.assertFalse(self.auto.active, "pode desativar a automação junto")


class ChannelApiTests(NotificationBase):
    def test_test_endpoint_sends_sample_without_pausing(self):
        self.channel()
        for i in range(3):
            self.run_task(TaskStatus.ERROR, f"e{i}")

        result = ns.send_test(self.db)

        self.assertTrue(result["ok"])
        self.assertEqual(len(_Stub.received), 1)
        self.assertEqual(self.schedule.status, ScheduleStatus.ACTIVE)
        self.assertEqual(ns.list_logs(self.db)[0].kind, "test")
        self.assertIn("Automacao_Estoque_PO", result["request_preview"]["body"])

    def test_cannot_enable_without_url(self):
        with self.assertRaises(ValidationException):
            ns.update_channel(self.db, {"enabled": True, "url": ""})

    def test_update_saves_headers_and_fields(self):
        channel = ns.update_channel(
            self.db,
            {"url": self.url, "headers": {"Authorization": "Bearer x"}, "failure_threshold": 5, "enabled": True},
        )
        read = ns.channel_to_read(channel)
        self.assertEqual(read["headers"], {"Authorization": "Bearer x"})
        self.assertEqual(read["failure_threshold"], 5)

    def test_schema_rejects_bad_url_and_method(self):
        from pydantic import ValidationError

        from app.schemas.notification import NotificationChannelUpdate

        with self.assertRaises(ValidationError):
            NotificationChannelUpdate(url="ftp://x")
        with self.assertRaises(ValidationError):
            NotificationChannelUpdate(method="GET")
        self.assertEqual(NotificationChannelUpdate(method="put").method, "PUT")


if __name__ == "__main__":
    unittest.main()
