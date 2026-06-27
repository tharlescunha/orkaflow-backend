import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.enums import ExecutionMode, TaskLogLevel, TaskLogSource, TaskStatus
from app.models.task import Task
from app.repositories.automation_success_trigger_repository import (
    AutomationSuccessTriggerRepository,
)
from app.repositories.task_log_repository import TaskLogRepository
from app.repositories.task_repository import TaskRepository


class AutomationTriggerService:
    def __init__(self, db: Session):
        self.db = db
        self.task_repository = TaskRepository(db)
        self.task_log_repository = TaskLogRepository(db)

    def create_success_followups(self, parent_task: Task) -> list[Task]:
        if parent_task.status != TaskStatus.FINISHED:
            return []

        triggers = list(
            AutomationSuccessTriggerRepository.list_for_source(
                self.db,
                parent_task.automation_id,
                active=True,
            )
        )
        if not triggers:
            return []

        workflow_requests = self._parse_result_workflow(parent_task)
        requests_by_target: dict[int, dict[str, Any]] | None = None

        if workflow_requests is not None:
            requests_by_target = {
                item["automation_id"]: item for item in workflow_requests
            }
            allowed_target_ids = {trigger.target_automation_id for trigger in triggers}
            ignored_ids = sorted(set(requests_by_target) - allowed_target_ids)
            for ignored_id in ignored_ids:
                self._log_parent_warning(
                    parent_task,
                    "Workflow do result_json ignorou automacao "
                    f"#{ignored_id}: destino nao esta cadastrado como gatilho permitido.",
                )

            triggers = [
                trigger
                for trigger in triggers
                if trigger.target_automation_id in requests_by_target
            ]

        created_tasks: list[Task] = []
        for trigger in triggers:
            extra_parameters = None
            if requests_by_target is not None:
                extra_parameters = requests_by_target.get(
                    trigger.target_automation_id,
                    {},
                ).get("parameters")

            child_task = self._create_followup_task(
                parent_task=parent_task,
                trigger=trigger,
                extra_parameters=extra_parameters,
            )
            if child_task:
                created_tasks.append(child_task)

        return created_tasks

    def _create_followup_task(
        self,
        *,
        parent_task: Task,
        trigger,
        extra_parameters: dict[str, Any] | None,
    ) -> Task | None:
        target_automation = self.task_repository.get_automation_by_id(
            trigger.target_automation_id
        )
        if not target_automation or not target_automation.active:
            self._log_parent_warning(
                parent_task,
                f"Gatilho de sucesso ignorado: automacao destino #{trigger.target_automation_id} inativa ou inexistente.",
            )
            return None

        bot = target_automation.bot
        if not bot or not bot.active:
            self._log_parent_warning(
                parent_task,
                f"Gatilho de sucesso ignorado: bot da automacao #{target_automation.id} inativo ou inexistente.",
            )
            return None

        existing_child = self.task_repository.get_child_task_for_parent_and_automation(
            parent_task.id,
            target_automation.id,
        )
        if existing_child:
            return None

        existing_open_target = self.task_repository.get_open_task_for_automation(
            target_automation.id
        )
        if existing_open_target:
            self._log_parent_warning(
                parent_task,
                "Gatilho de sucesso aguardando: automacao destino "
                f"#{target_automation.id} ja possui task aberta #{existing_open_target.id}.",
            )
            return None

        latest_bot_version = self.task_repository.get_latest_bot_version_for_bot(
            target_automation.bot_id
        )
        if not latest_bot_version:
            self._log_parent_warning(
                parent_task,
                f"Gatilho de sucesso ignorado: automacao #{target_automation.id} sem bot version disponivel.",
            )
            return None

        parameters = self._build_child_parameters(
            parent_task,
            target_automation.id,
            trigger,
            extra_parameters=extra_parameters,
        )
        if parameters is None:
            return None

        now = datetime.now(UTC)
        child_task = self.task_repository.create(
            {
                "automation_id": target_automation.id,
                "bot_version_id": latest_bot_version.id,
                "runner_id": None,
                "created_by": None,
                "schedule_id": None,
                "parent_task_id": parent_task.id,
                "priority": trigger.priority_override or target_automation.default_priority,
                "status": TaskStatus.WAITING,
                "requested_start_at": None,
                "timeout_seconds": bot.timeout_default or 3600,
                "execution_mode": ExecutionMode.API,
                "correlation_id": parent_task.correlation_id,
                "queue_name": parent_task.queue_name,
                "inactivity_timeout_seconds": parent_task.inactivity_timeout_seconds,
                "last_update_at": now,
                "created_at": now,
            }
        )

        if parameters:
            self.task_repository.create_parameters_bulk(child_task.id, parameters)

        self._log_parent_info(
            parent_task,
            f"Gatilho de sucesso criou task #{child_task.id} para automacao #{target_automation.id}.",
        )
        return child_task

    def _parse_result_workflow(self, parent_task: Task) -> list[dict[str, Any]] | None:
        raw_result = (parent_task.result_json or "").strip()
        if not raw_result:
            return None

        try:
            result = json.loads(raw_result)
        except Exception:
            self._log_parent_warning(parent_task, "result_json invalido; workflow dinamico ignorado.")
            return []

        if not isinstance(result, dict):
            self._log_parent_warning(parent_task, "result_json precisa ser objeto JSON; workflow dinamico ignorado.")
            return []

        workflow = result.get("orkaflow")
        if workflow is None:
            workflow = result.get("workflow")

        if not isinstance(workflow, dict):
            return None

        raw_items = (
            workflow.get("next_automations")
            or workflow.get("trigger_automations")
            or workflow.get("next_automation_ids")
        )

        if raw_items is None:
            return None

        if not isinstance(raw_items, list):
            self._log_parent_warning(parent_task, "Lista de proximas automacoes invalida no result_json.")
            return []

        parsed_items: list[dict[str, Any]] = []
        for item in raw_items:
            if isinstance(item, int):
                parsed_items.append({"automation_id": item, "parameters": None})
                continue

            if not isinstance(item, dict):
                self._log_parent_warning(parent_task, "Item de workflow invalido no result_json; item ignorado.")
                continue

            automation_id = item.get("automation_id")
            if not isinstance(automation_id, int):
                self._log_parent_warning(parent_task, "Item de workflow sem automation_id numerico; item ignorado.")
                continue

            parameters = item.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                self._log_parent_warning(parent_task, "Parametros de workflow precisam ser objeto JSON; parametros ignorados.")
                parameters = None

            parsed_items.append(
                {
                    "automation_id": automation_id,
                    "parameters": parameters,
                }
            )

        return parsed_items

    def _build_child_parameters(
        self,
        parent_task: Task,
        target_automation_id: int,
        trigger,
        *,
        extra_parameters: dict[str, Any] | None,
    ):
        target_automation = self.task_repository.get_automation_by_id(target_automation_id)
        target_parameters = self.task_repository.get_automation_parameters(target_automation_id)
        final_parameters_by_name: dict[str, dict] = {}

        if trigger.inherit_parent_parameters:
            for parent_param in self.task_repository.get_parameters(parent_task.id):
                final_parameters_by_name[parent_param.parameter_name] = {
                    "parameter_name": parent_param.parameter_name,
                    "parameter_value": parent_param.parameter_value,
                    "is_secret": parent_param.is_secret,
                    "resolved_from_credential_item_id": parent_param.resolved_from_credential_item_id,
                }

        if extra_parameters:
            runtime_parameters = self._load_runtime_parameters(final_parameters_by_name)
            runtime_parameters.update(extra_parameters)
            final_parameters_by_name["runtime_parameters_json"] = {
                "parameter_name": "runtime_parameters_json",
                "parameter_value": json.dumps(runtime_parameters, ensure_ascii=False),
                "is_secret": False,
                "resolved_from_credential_item_id": None,
            }

        # Aplica defaults da automação destino para parâmetros ainda ausentes
        if target_automation is not None:
            if "parameters_json" not in final_parameters_by_name:
                default_params = getattr(target_automation, "default_parameters_json", None)
                if isinstance(default_params, dict) and default_params:
                    final_parameters_by_name["parameters_json"] = {
                        "parameter_name": "parameters_json",
                        "parameter_value": json.dumps(default_params, ensure_ascii=False),
                        "is_secret": False,
                        "resolved_from_credential_item_id": None,
                    }

            if "runtime_parameters_json" not in final_parameters_by_name:
                default_runtime = getattr(target_automation, "default_runtime_parameters_json", None)
                if isinstance(default_runtime, dict) and default_runtime:
                    final_parameters_by_name["runtime_parameters_json"] = {
                        "parameter_name": "runtime_parameters_json",
                        "parameter_value": json.dumps(default_runtime, ensure_ascii=False),
                        "is_secret": False,
                        "resolved_from_credential_item_id": None,
                    }

        for target_param in target_parameters:
            if (
                target_param.name not in final_parameters_by_name
                and getattr(target_param, "default_value", None) not in (None, "")
            ):
                final_parameters_by_name[target_param.name] = {
                    "parameter_name": target_param.name,
                    "parameter_value": target_param.default_value,
                    "is_secret": False,
                    "resolved_from_credential_item_id": None,
                }

        runtime_parameters = self._load_runtime_parameters(final_parameters_by_name)
        missing_required = [
            target_param.name
            for target_param in target_parameters
            if getattr(target_param, "required", False)
            and target_param.name not in final_parameters_by_name
            and target_param.name not in runtime_parameters
        ]
        if missing_required:
            self._log_parent_warning(
                parent_task,
                "Gatilho de sucesso ignorado: automacao destino exige parametros sem valor: "
                + ", ".join(missing_required),
            )
            return None

        return list(final_parameters_by_name.values())

    def _load_runtime_parameters(self, parameters_by_name: dict[str, dict]) -> dict[str, Any]:
        runtime_param = parameters_by_name.get("runtime_parameters_json")
        if not runtime_param:
            return {}

        raw_value = runtime_param.get("parameter_value")
        if not raw_value:
            return {}

        try:
            parsed_value = json.loads(raw_value)
        except Exception:
            return {}

        return parsed_value if isinstance(parsed_value, dict) else {}

    def _log_parent_info(self, parent_task: Task, message: str) -> None:
        self._log_parent(parent_task, TaskLogLevel.INFO, message)

    def _log_parent_warning(self, parent_task: Task, message: str) -> None:
        self._log_parent(parent_task, TaskLogLevel.WARNING, message)

    def _log_parent(self, parent_task: Task, level: TaskLogLevel, message: str) -> None:
        self.task_log_repository.create(
            {
                "task_id": parent_task.id,
                "level": level,
                "message": message,
                "source": TaskLogSource.BACKEND,
                "runner_id": parent_task.runner_id,
                "event_code": "success_trigger",
            }
        )
