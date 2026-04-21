from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.permission_repository import PermissionRepository


DEFAULT_PERMISSIONS: list[dict[str, str | None]] = [
    {"module": "dashboard", "action": "view", "description": "Visualizar dashboard"},
    {"module": "users", "action": "view", "description": "Visualizar usuários"},
    {"module": "users", "action": "create", "description": "Criar usuários"},
    {"module": "users", "action": "edit", "description": "Editar usuários"},
    {"module": "users", "action": "block", "description": "Bloquear e desbloquear usuários"},
    {"module": "users", "action": "admin", "description": "Administrar usuários"},
    {"module": "profiles", "action": "view", "description": "Visualizar perfis"},
    {"module": "profiles", "action": "create", "description": "Criar perfis"},
    {"module": "profiles", "action": "edit", "description": "Editar perfis"},
    {"module": "profiles", "action": "admin", "description": "Administrar perfis"},
    {"module": "repositories", "action": "view", "description": "Visualizar repositórios"},
    {"module": "repositories", "action": "create", "description": "Criar repositórios"},
    {"module": "repositories", "action": "edit", "description": "Editar repositórios"},
    {"module": "runners", "action": "view", "description": "Visualizar runners"},
    {"module": "runners", "action": "edit", "description": "Editar runners"},
    {"module": "bots", "action": "view", "description": "Visualizar bots"},
    {"module": "bots", "action": "create", "description": "Criar bots"},
    {"module": "bots", "action": "edit", "description": "Editar bots"},
    {"module": "bot_versions", "action": "view", "description": "Visualizar versões de bot"},
    {"module": "bot_versions", "action": "create", "description": "Criar versões de bot"},
    {"module": "automations", "action": "view", "description": "Visualizar automações"},
    {"module": "automations", "action": "create", "description": "Criar automações"},
    {"module": "automations", "action": "edit", "description": "Editar automações"},
    {"module": "schedules", "action": "view", "description": "Visualizar agendamentos"},
    {"module": "schedules", "action": "create", "description": "Criar agendamentos"},
    {"module": "schedules", "action": "edit", "description": "Editar agendamentos"},
    {"module": "tasks", "action": "view", "description": "Visualizar tasks"},
    {"module": "tasks", "action": "create", "description": "Criar tasks"},
    {"module": "tasks", "action": "edit", "description": "Editar tasks"},
    {"module": "credentials", "action": "view", "description": "Visualizar credenciais"},
    {"module": "credentials", "action": "create", "description": "Criar credenciais"},
    {"module": "credentials", "action": "edit", "description": "Editar credenciais"},
    {"module": "audit", "action": "view", "description": "Visualizar auditoria"},
]


class PermissionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = PermissionRepository(db)

    def list(self):
        return self.repo.list_all()

    def seed_defaults(self):
        created = 0

        for item in DEFAULT_PERMISSIONS:
            existing = self.repo.get_by_module_action(
                module=str(item["module"]),
                action=str(item["action"]),
            )
            if existing:
                continue

            self.repo.create(
                module=str(item["module"]),
                action=str(item["action"]),
                description=item["description"],
            )
            created += 1

        return {
            "created": created,
            "total": len(self.repo.list_all()),
        }
    