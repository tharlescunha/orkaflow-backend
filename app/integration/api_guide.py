"""Explicação em português de cada rota da API, mostrada na aba Integração do painel.

Chave: "MÉTODO /caminho" exatamente como no OpenAPI (ex.: "GET /api/v1/tasks/").
Campos:
- summary: título curto (uma linha).
- description: o que faz, quando usar, regras e cuidados (markdown simples).
- example_request: exemplo de corpo JSON (dict, só em rotas com corpo; opcional).
- example_response: exemplo de resposta (dict ou list; opcional).

Os exemplos usam valores fictícios: nunca coloque tokens, senhas ou segredos reais aqui.
"""

GUIDE: dict[str, dict] = {}

# Texto de cada grupo (tag do OpenAPI) mostrado no topo da seção.
TAG_GUIDE: dict[str, str] = {}


# Trechos repetidos nas descrições.
_BEARER = "Exige `Authorization: Bearer <token>` (token de login ou token de integração `ork_...`)."
_ADMIN = (
    "Exige `Authorization: Bearer <token>` de um **administrador** (role legada `admin` "
    "ou perfil com a permissão `users:admin`); outros usuários recebem 403."
)
_WORKER = (
    "**Rota do worker** (agente instalado nas máquinas): autentica pelo `uuid` e `token` do runner "
    "enviados no corpo, **não** por Bearer. Integrações normalmente não usam esta rota.\n\n"
)
_WORKER_AUTH_ERRORS = (
    "\n\nErros de autenticação do runner: 401 se o `uuid` não existe ou o token não confere; "
    "403 se o runner foi removido do painel ou está desativado."
)

_TS = "2026-10-21T13:45:00Z"

_TASK_EXAMPLE = {
    "id": 42723,
    "automation_id": 12,
    "automation_name": "Estoque PO",
    "bot_version_id": 87,
    "bot_version_label": "1.4.2",
    "runner_id": 5,
    "runner_name": "SRVRPA14",
    "runner_label": "RPA 14",
    "runner_display_name": "RPA 14",
    "created_by": None,
    "created_by_name": None,
    "schedule_id": 18,
    "schedule_name": "Estoque PO - a cada hora",
    "parent_task_id": None,
    "priority": 5,
    "status": "finished",
    "requested_start_at": None,
    "started_at": "2026-10-21T13:40:02Z",
    "finished_at": "2026-10-21T13:45:14Z",
    "last_update_at": "2026-10-21T13:45:14Z",
    "final_message": "120 itens processados.",
    "result_json": None,
    "items_processed": 120,
    "items_failed": 0,
    "timeout_seconds": 3600,
    "retry_count": 0,
    "execution_mode": "scheduled",
    "dispatch_attempts": 1,
    "stop_requested": False,
    "correlation_id": None,
    "queue_name": None,
    "inactivity_timeout_seconds": None,
    "runner_claimed_at": "2026-10-21T13:40:00Z",
    "created_at": "2026-10-21T13:39:58Z",
    "updated_at": "2026-10-21T13:45:14Z",
    "execution_duration_seconds": 312,
    "parameters": [
        {
            "id": 9001,
            "task_id": 42723,
            "parameter_name": "runtime_parameters_json",
            "parameter_value": "{\"filial\": \"010\"}",
            "is_secret": False,
            "resolved_from_credential_item_id": None,
        }
    ],
    "telemetry": None,
    "runner_details": None,
    "runner_usage": None,
}

_USER_EXAMPLE = {
    "id": 7,
    "name": "Maria Souza",
    "login": "maria.souza",
    "email": "maria.souza@empresa.com.br",
    "active": True,
    "role": "operator",
    "profile_id": 2,
    "profile": {
        "id": 2,
        "name": "Operação",
        "description": "Opera tasks e agendamentos",
        "active": True,
        "permissions": [{"id": 27, "module": "tasks", "action": "view", "description": "Visualizar tasks"}],
    },
    "created_at": "2026-03-02T12:00:00Z",
    "updated_at": "2026-10-01T09:30:00Z",
}

_REPOSITORY_EXAMPLE = {
    "id": 3,
    "name": "Suprimentos",
    "description": "Robôs da área de suprimentos",
    "active": True,
    "created_at": "2026-02-10T12:00:00Z",
    "updated_at": None,
}

_RUNNER_CONFIG_EXAMPLE = {
    "id": 5,
    "runner_id": 5,
    "max_concurrency": 2,
    "allowed_parallel_bots": None,
    "polling_interval": 15,
    "auto_update_bots": True,
    "install_all_bots_on_register": False,
    "maintenance_mode": False,
    "created_at": "2026-04-01T10:00:00Z",
    "updated_at": "2026-09-15T08:00:00Z",
}

_RUNNER_EXAMPLE = {
    "id": 5,
    "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
    "name": "SRVRPA14",
    "label": "RPA 14",
    "host_name": "SRVRPA14",
    "ip": "10.0.0.14",
    "os_name": "Windows",
    "os_version": "10.0.20348",
    "cpu_arch": "AMD64",
    "memory_total": 17179869184,
    "access_remote": True,
    "enabled": True,
    "status": "online",
    "last_heartbeat": _TS,
    "created_at": "2026-04-01T10:00:00Z",
    "updated_at": _TS,
    "config": _RUNNER_CONFIG_EXAMPLE,
    "running_tasks_count": 0,
    "has_running_task": False,
    "linked_bots_count": 4,
    "last_screenshot_at": "2026-10-21T13:44:30Z",
    "has_screenshot": True,
    "deleted_at": None,
}

_BOT_EXAMPLE = {
    "id": 9,
    "name": "BOT_ETL_Estoque_PO",
    "description": "Extrai o estoque de pedidos de compra",
    "technology": "python",
    "repository_id": 3,
    "repository_name": "Suprimentos",
    "source_type": "git",
    "execution_mode": "background",
    "source_url": "https://git.exemplo.com/rpa/bot-estoque-po.git",
    "entrypoint": "main.py",
    "requirements_file": "requirements.txt",
    "timeout_default": 3600,
    "active": True,
    "auto_update": False,
    "current_version": "1.4.2",
    "release_version": "1.0.0",
    "created_at": "2026-05-04T12:00:00Z",
    "updated_at": "2026-10-10T17:20:00Z",
}

_BOT_VERSION_EXAMPLE = {
    "id": 87,
    "bot_id": 9,
    "bot_name": "BOT_ETL_Estoque_PO",
    "version": "1.4.2",
    "storage_type": "git",
    "commit_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
    "branch": "main",
    "artifact_path": "https://git.exemplo.com/rpa/bot-estoque-po.git",
    "changelog": "- Corrige leitura da planilha (a1b2c3d, Maria, 10/10/2026 17:10)",
    "checksum": None,
    "commit_author": "Maria Souza",
    "committed_at": "2026-10-10T17:10:00Z",
    "created_by": 7,
    "is_active": True,
    "created_at": "2026-10-10T17:20:00Z",
    "updated_at": None,
    "in_use": True,
    "pinned": False,
}

_AUTOMATION_EXAMPLE = {
    "id": 12,
    "name": "Estoque PO",
    "label": "Estoque de pedidos de compra",
    "description": "Atualiza o estoque de PO no SAP",
    "bot_id": 9,
    "bot_name": "BOT_ETL_Estoque_PO",
    "repository_id": 3,
    "repository_name": "Suprimentos",
    "default_priority": 5,
    "notification_type": None,
    "active": True,
    "exclusive_group_ids": [2],
    "exclusive_groups": [
        {
            "id": 2,
            "name": "sap-suprimentos",
            "label": "SAP Suprimentos",
            "description": "Só um robô por vez no SAP de suprimentos",
            "capacity": 1,
            "active": True,
            "automation_ids": [12, 15],
            "created_at": "2026-05-01T12:00:00Z",
            "updated_at": None,
        }
    ],
    "success_trigger_automation_ids": [15],
    "success_triggers": [
        {
            "id": 4,
            "source_automation_id": 12,
            "target_automation_id": 15,
            "target_automation_name": "Relatório Estoque",
            "priority_override": None,
            "inherit_parent_parameters": True,
            "active": True,
            "created_at": "2026-05-01T12:00:00Z",
            "updated_at": None,
        }
    ],
    "default_parameters_json": {"empresa": "1000"},
    "default_runtime_parameters_json": {"filial": "010"},
    "created_at": "2026-05-01T12:00:00Z",
    "updated_at": "2026-09-30T18:00:00Z",
}

_PARAMETER_EXAMPLE = {
    "id": 31,
    "automation_id": 12,
    "name": "filial",
    "label": "Filial",
    "description": "Código da filial a processar",
    "type": "select",
    "allowed_values": ["010", "020", "030"],
    "default_value": "010",
    "required": True,
    "order_index": 0,
}

_SCHEDULE_EXAMPLE = {
    "id": 18,
    "name": "Estoque PO - a cada hora",
    "automation_id": 12,
    "priority": 5,
    "schedule_type": "cron",
    "calendar_type": None,
    "cron_expression": "0 7-18 * * 1-5",
    "policy": "ignore_if_running",
    "runtime_parameters_json": {"filial": "010"},
    "use_default_runtime_parameters": True,
    "timezone": "America/Sao_Paulo",
    "active": True,
    "interval_value": None,
    "interval_unit": None,
    "status": "active",
    "start_at": None,
    "end_at": None,
    "last_run_at": "2026-10-21T13:00:00Z",
    "next_run_at": "2026-10-21T14:00:00Z",
    "misfire_policy": None,
    "last_error": None,
    "last_skipped_reason": None,
    "last_skipped_at": None,
    "created_at": "2026-05-01T12:00:00Z",
    "updated_at": "2026-10-21T13:00:01Z",
}

_CREDENTIAL_EXAMPLE = {
    "id": 4,
    "repository_id": 3,
    "label": "SAP - usuário de serviço",
    "active": True,
    "created_at": "2026-05-01T12:00:00Z",
    "updated_at": None,
}

_CREDENTIAL_ITEM_EXAMPLE = {
    "id": 11,
    "credential_id": 4,
    "key": "senha",
    "value_type": "password",
    "masked_preview": "se****lo",
    "created_at": "2026-05-01T12:00:00Z",
    "updated_at": None,
}

_PROFILE_EXAMPLE = {
    "id": 2,
    "name": "Operação",
    "description": "Opera tasks e agendamentos",
    "active": True,
    "permissions": [
        {"id": 27, "module": "tasks", "action": "view", "description": "Visualizar tasks"},
        {"id": 28, "module": "tasks", "action": "create", "description": "Criar tasks"},
    ],
    "created_at": "2026-03-01T12:00:00Z",
    "updated_at": None,
}

_TOKEN_EXAMPLE = {
    "id": 3,
    "name": "Claude da Maria",
    "token_prefix": "ork_AbCdEfGh",
    "status": "ativo",
    "created_at": "2026-10-01T12:00:00Z",
    "expires_at": "2027-10-01T12:00:00Z",
    "last_used_at": "2026-10-21T13:40:00Z",
    "revoked_at": None,
}

_ENV_VAR_EXAMPLE = {
    "id": 21,
    "name": "SAP_URL",
    "scope_type": "automation",
    "scope_id": 12,
    "scope_label": "Estoque de pedidos de compra",
    "is_secret": False,
    "value": "https://sap.exemplo.com",
    "description": "Endereço do SAP de produção",
    "active": True,
    "updated_at": "2026-10-01T12:00:00Z",
}

_NOTIFICATION_CHANNEL_EXAMPLE = {
    "id": 1,
    "name": "Chamado",
    "enabled": True,
    "url": "https://chamados.exemplo.com/api/tickets",
    "method": "POST",
    "headers": {"Content-Type": "application/json", "Authorization": "Bearer {{token}}"},
    "body_template": "{\n  \"titulo\": \"Falha na automação {{automacao}}\",\n  \"descricao\": \"{{erro}}\"\n}",
    "timeout_seconds": 15,
    "failure_threshold": 3,
    "pause_schedule": True,
    "deactivate_automation": False,
    "panel_base_url": "https://orkaflow.exemplo.com",
    "pre_steps": [
        {
            "name": "Login",
            "method": "POST",
            "url": "https://chamados.exemplo.com/api/login",
            "headers": {"Content-Type": "application/json"},
            "body_template": "{\"usuario\": \"robo\", \"senha\": \"senha-exemplo\"}",
            "extract": [{"variable": "token", "path": "data.token"}],
        }
    ],
    "updated_at": "2026-10-01T12:00:00Z",
}


# ---------------------------------------------------------------------- Health
GUIDE.update({
    "GET /api/v1/health": {
        "summary": "Saúde da API, do banco e dos serviços de fundo",
        "description": (
            "Verifica se a API está de pé. **Público** (não precisa de token); ideal para monitoramento "
            "e balanceadores.\n\n"
            "- Testa o banco com `SELECT 1`.\n"
            "- Na instalação completa (`mode: full`), lê também o último ciclo dos serviços de fundo "
            "(agendador, dispatcher, watchdog...). Na cópia \"só painel\" (`mode: panel_only`) só o banco conta.\n\n"
            "Respostas:\n"
            "- **200 `ok`**: tudo certo.\n"
            "- **200 `degraded`**: banco ok, mas algum serviço de fundo sem sinal (`unknown`), ex.: rodando em outro servidor.\n"
            "- **503 `unhealthy`**: banco com erro ou algum serviço de fundo parado há mais de 3x seu intervalo (`stale`)."
        ),
        "example_response": {
            "status": "ok",
            "timestamp": _TS,
            "app_name": "OrkaFlow",
            "environment": "production",
            "mode": "full",
            "database": "ok",
            "components": {
                "database": {"status": "ok"},
                "scheduler": {"status": "ok", "last_ok_at": "2026-10-21T13:44:55Z"},
            },
            "last_cycle": {"scheduler": "2026-10-21T13:44:55Z"},
            "supervisor": None,
        },
    },
})


# ------------------------------------------------------------------------ Auth
GUIDE.update({
    "POST /api/v1/auth/login": {
        "summary": "Login com usuário e senha (gera access e refresh token)",
        "description": (
            "Autentica um usuário pelo **login ou e-mail** e senha. **Público.**\n\n"
            "Devolve um `access_token` (JWT de curta duração) para usar em `Authorization: Bearer <access_token>` "
            "e um `refresh_token` para renovar a sessão em `POST /api/v1/auth/refresh`.\n\n"
            "- 401: login ou senha inválidos.\n"
            "- 403: usuário inativo (bloqueado).\n\n"
            "Para scripts e IAs prefira um **token de integração** (`ork_...`), que não expira em minutos: "
            "veja o grupo *Tokens de integração*."
        ),
        "example_request": {"login": "maria.souza", "password": "senha-exemplo"},
        "example_response": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.exemplo.assinatura",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.exemplo-refresh.assinatura",
            "token_type": "bearer",
        },
    },
    "POST /api/v1/auth/refresh": {
        "summary": "Renova o access token a partir do refresh token",
        "description": (
            "Troca um `refresh_token` válido por um novo par `access_token` + `refresh_token`. **Público** "
            "(o próprio refresh token é a credencial).\n\n"
            "- 401: refresh token vencido, inválido ou de outro tipo (ex.: mandar um access token aqui).\n"
            "- 403: o usuário foi desativado depois do login.\n\n"
            "Guarde sempre o novo `refresh_token` devolvido."
        ),
        "example_request": {"refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.exemplo-refresh.assinatura"},
        "example_response": {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.novo.assinatura",
            "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.novo-refresh.assinatura",
            "token_type": "bearer",
        },
    },
    "GET /api/v1/auth/me": {
        "summary": "Dados do usuário dono do token",
        "description": (
            "Retorna quem está autenticado pelo token enviado. Útil para validar um token de integração "
            "ou descobrir o `id` do usuário.\n\n" + _BEARER
        ),
        "example_response": {
            "id": 7,
            "name": "Maria Souza",
            "login": "maria.souza",
            "email": "maria.souza@empresa.com.br",
            "role": "operator",
            "active": True,
        },
    },
    "POST /api/v1/auth/logout": {
        "summary": "Logout lógico (o cliente descarta os tokens)",
        "description": (
            "Apenas confirma o logout: o backend **não** invalida o JWT (ele continua válido até expirar). "
            "O cliente deve apagar o access e o refresh token. Para cortar o acesso de um token de "
            "integração use `DELETE /api/v1/api-tokens/{token_id}`.\n\nPúblico, sem corpo."
        ),
        "example_response": {"message": "Logout lógico realizado com sucesso."},
    },
})


# ------------------------------------------------------------ Public Downloads
GUIDE.update({
    "GET /api/v1/public/downloads/{filename}": {
        "summary": "Baixa um arquivo público de apoio (ex.: nssm.exe)",
        "description": (
            "Entrega arquivos auxiliares usados na instalação do worker nas máquinas. **Público.**\n\n"
            "Só arquivos da lista permitida são servidos (hoje: `nssm.exe`, usado para instalar o worker "
            "como serviço do Windows). Qualquer outro nome devolve 404 `Arquivo não permitido.`\n\n"
            "A resposta é o binário (`application/octet-stream`), não JSON."
        ),
    },
})


# ----------------------------------------------------------------------- Users
GUIDE.update({
    "GET /api/v1/users/": {
        "summary": "Lista usuários (com filtros e paginação)",
        "description": (
            "Lista os usuários do painel com o perfil e as permissões de cada um.\n\n"
            "Parâmetros (query):\n"
            "- `skip` / `limit` (1–500, padrão 100): paginação.\n"
            "- `active`: `true` só ativos, `false` só bloqueados.\n"
            "- `profile_id`: só usuários desse perfil (404 se o perfil não existe).\n"
            "- `search`: busca por nome/login/e-mail.\n\n" + _BEARER + " Qualquer usuário logado pode listar."
        ),
        "example_response": [_USER_EXAMPLE],
    },
    "POST /api/v1/users/": {
        "summary": "Cria um usuário (administrador)",
        "description": (
            "Cadastra um usuário do painel. A senha (mín. 6 caracteres) é gravada só como hash.\n\n"
            "- `login` (3–80) e `email` precisam ser únicos (409 se já existirem).\n"
            "- `role` é a role legada (`admin`, `operator`, `viewer`); `admin` libera tudo.\n"
            "- `profile_id` (opcional) define as permissões finas; 404 se o perfil não existe.\n\n" + _ADMIN
        ),
        "example_request": {
            "name": "Maria Souza",
            "login": "maria.souza",
            "email": "maria.souza@empresa.com.br",
            "password": "senha-exemplo",
            "role": "operator",
            "profile_id": 2,
            "active": True,
        },
        "example_response": _USER_EXAMPLE,
    },
    "GET /api/v1/users/{user_id}": {
        "summary": "Detalhe de um usuário",
        "description": "Retorna um usuário pelo `id`, com perfil e permissões. 404 se não existe.\n\n" + _BEARER,
        "example_response": _USER_EXAMPLE,
    },
    "PUT /api/v1/users/{user_id}": {
        "summary": "Atualiza um usuário (administrador)",
        "description": (
            "Atualização parcial: só os campos enviados mudam. Enviar `password` troca a senha.\n\n"
            "- 409 se o novo `login` ou `email` já pertence a outro usuário.\n"
            "- 404 se o `profile_id` informado não existe.\n\n" + _ADMIN
        ),
        "example_request": {"profile_id": 3, "email": "maria.souza@empresa.com.br"},
        "example_response": _USER_EXAMPLE,
    },
    "DELETE /api/v1/users/{user_id}": {
        "summary": "Exclui (desativa) um usuário (administrador)",
        "description": (
            "Exclusão **lógica**: o usuário fica com `active=false` e não consegue mais logar nem usar "
            "seus tokens (inclusive os de integração). O registro e o histórico continuam no banco; "
            "dá para reativar com `/unblock`.\n\n" + _ADMIN
        ),
        "example_response": {**_USER_EXAMPLE, "active": False},
    },
    "PATCH /api/v1/users/{user_id}/status": {
        "summary": "Ativa ou bloqueia um usuário (administrador)",
        "description": (
            "Define `active` diretamente. `false` bloqueia o login e todos os tokens do usuário; "
            "`true` libera de novo. Equivale a `/block` e `/unblock`.\n\n" + _ADMIN
        ),
        "example_request": {"active": False},
        "example_response": {**_USER_EXAMPLE, "active": False},
    },
    "POST /api/v1/users/{user_id}/block": {
        "summary": "Bloqueia um usuário (administrador)",
        "description": (
            "Marca o usuário como inativo: login e tokens (JWT e `ork_...`) passam a ser recusados com 403. "
            "Sem corpo.\n\n" + _ADMIN
        ),
        "example_response": {**_USER_EXAMPLE, "active": False},
    },
    "POST /api/v1/users/{user_id}/unblock": {
        "summary": "Desbloqueia um usuário (administrador)",
        "description": (
            "Reativa o usuário (`active=true`). Tokens de integração ainda válidos voltam a funcionar. "
            "Sem corpo.\n\n" + _ADMIN
        ),
        "example_response": _USER_EXAMPLE,
    },
})


# -------------------------------------------------------- Tokens de integração
GUIDE.update({
    "GET /api/v1/api-tokens/": {
        "summary": "Lista meus tokens de integração",
        "description": (
            "Tokens de integração (`ork_...`) do usuário logado, do mais novo ao mais antigo. O valor completo "
            "**nunca** volta: só o `token_prefix` (12 primeiros caracteres) para identificar.\n\n"
            "`status`: `ativo`, `revogado` ou `expirado`. `last_used_at` é atualizado no máximo a cada 5 minutos.\n\n"
            + _BEARER
        ),
        "example_response": [_TOKEN_EXAMPLE],
    },
    "POST /api/v1/api-tokens/": {
        "summary": "Gera um token de integração para mim",
        "description": (
            "Cria um token pessoal para MCP, IAs e scripts. Ele vale com **as mesmas permissões do usuário** "
            "e é usado como `Authorization: Bearer ork_...`.\n\n"
            "- `name`: identificação (ex.: \"Claude da Maria\").\n"
            "- `expires_in_days`: 1–3650 (padrão 365); `null` = sem validade.\n"
            "- Limite de 20 tokens ativos por usuário (400 ao passar).\n\n"
            "**Copie o campo `token` na hora**: ele aparece só nesta resposta (o banco guarda apenas o hash).\n\n"
            + _BEARER
        ),
        "example_request": {"name": "Claude da Maria", "expires_in_days": 365},
        "example_response": {**_TOKEN_EXAMPLE, "last_used_at": None, "token": "ork_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"},
    },
    "DELETE /api/v1/api-tokens/{token_id}": {
        "summary": "Revoga um token meu",
        "description": (
            "Revoga o token na hora: chamadas com ele passam a receber 401. Só revoga tokens do próprio "
            "usuário (404 para token de outra pessoa). Revogar de novo não dá erro.\n\n" + _BEARER
        ),
        "example_response": {**_TOKEN_EXAMPLE, "status": "revogado", "revoked_at": _TS},
    },
    "GET /api/v1/users/{user_id}/api-tokens": {
        "summary": "Lista os tokens de integração de um usuário (admin)",
        "description": (
            "Mesma listagem de `GET /api/v1/api-tokens/`, mas de outro usuário (tela de Usuários). "
            "404 se o usuário não existe.\n\n" + _ADMIN
        ),
        "example_response": [_TOKEN_EXAMPLE],
    },
    "POST /api/v1/users/{user_id}/api-tokens": {
        "summary": "Gera um token de integração para um usuário (admin)",
        "description": (
            "Cria um token em nome de outro usuário (ex.: um usuário de serviço para uma integração). "
            "O token vale com **as permissões desse usuário**, não as do administrador. Mesmas regras de "
            "`POST /api/v1/api-tokens/` (validade, limite de 20 ativos). O valor completo aparece só nesta resposta.\n\n"
            + _ADMIN
        ),
        "example_request": {"name": "Integração ERP", "expires_in_days": None},
        "example_response": {
            **_TOKEN_EXAMPLE,
            "name": "Integração ERP",
            "expires_at": None,
            "last_used_at": None,
            "token": "ork_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        },
    },
    "DELETE /api/v1/users/{user_id}/api-tokens/{token_id}": {
        "summary": "Revoga um token de um usuário (admin)",
        "description": (
            "Revoga um token de outro usuário; ele para de funcionar na hora. 404 se o usuário não existe "
            "ou o token não é dele.\n\n" + _ADMIN
        ),
        "example_response": {**_TOKEN_EXAMPLE, "status": "revogado", "revoked_at": _TS},
    },
})


# -------------------------------------------------------------------- Profiles
GUIDE.update({
    "GET /api/v1/profiles/": {
        "summary": "Lista perfis de acesso",
        "description": (
            "Perfis com suas permissões (`modulo:acao`). Query: `skip`, `limit` (1–500) e `active`.\n\n" + _BEARER
        ),
        "example_response": [_PROFILE_EXAMPLE],
    },
    "POST /api/v1/profiles/": {
        "summary": "Cria um perfil de acesso (administrador)",
        "description": (
            "Cria um perfil e vincula as permissões por id (`permission_ids`, ver `GET /api/v1/permissions/`).\n\n"
            "- 409 se já existe perfil com o mesmo `name`.\n"
            "- 404 se algum id de permissão não existe.\n\n" + _ADMIN
        ),
        "example_request": {
            "name": "Operação",
            "description": "Opera tasks e agendamentos",
            "active": True,
            "permission_ids": [27, 28],
        },
        "example_response": _PROFILE_EXAMPLE,
    },
    "GET /api/v1/profiles/{profile_id}": {
        "summary": "Detalhe de um perfil",
        "description": "Retorna um perfil e suas permissões. 404 se não existe.\n\n" + _BEARER,
        "example_response": _PROFILE_EXAMPLE,
    },
    "PUT /api/v1/profiles/{profile_id}": {
        "summary": "Atualiza um perfil (administrador)",
        "description": (
            "Atualização parcial. Se enviar `permission_ids`, a lista **substitui** as permissões atuais "
            "(envie a lista completa). 409 para nome repetido; 404 para permissão inexistente.\n\n" + _ADMIN
        ),
        "example_request": {"permission_ids": [27, 28, 29]},
        "example_response": _PROFILE_EXAMPLE,
    },
    "POST /api/v1/profiles/{profile_id}/activate": {
        "summary": "Ativa um perfil (administrador)",
        "description": "Marca o perfil como ativo; os usuários dele voltam a conseguir acessar. Sem corpo.\n\n" + _ADMIN,
        "example_response": _PROFILE_EXAMPLE,
    },
    "POST /api/v1/profiles/{profile_id}/deactivate": {
        "summary": "Desativa um perfil (administrador)",
        "description": (
            "Marca o perfil como inativo. **Efeito colateral:** todo usuário vinculado a ele passa a "
            "receber 403 (\"perfil inativo\") em qualquer rota protegida, inclusive com token de integração. "
            "Sem corpo.\n\n" + _ADMIN
        ),
        "example_response": {**_PROFILE_EXAMPLE, "active": False},
    },
})


# ----------------------------------------------------------------- Permissions
GUIDE.update({
    "GET /api/v1/permissions/": {
        "summary": "Lista as permissões disponíveis",
        "description": (
            "Catálogo de permissões (`module` + `action`) usadas nos perfis, ex.: `tasks:view`, "
            "`automations:edit`, `users:admin`. As padrões são criadas automaticamente na subida da API. "
            "Use os `id` em `permission_ids` ao criar/editar perfis.\n\n"
            "Observação: hoje a maioria das rotas só exige estar logado; `users:admin` é a permissão que "
            "libera as rotas de administrador.\n\n" + _BEARER
        ),
        "example_response": [
            {"id": 1, "module": "dashboard", "action": "view", "description": "Visualizar dashboard"},
            {"id": 6, "module": "users", "action": "admin", "description": "Administrar usuários"},
        ],
    },
})


# ---------------------------------------------------------------- Repositories
GUIDE.update({
    "GET /api/v1/repositories/": {
        "summary": "Lista repositórios (áreas que agrupam bots)",
        "description": (
            "Repositórios são agrupadores de bots, automações e credenciais (ex.: uma área de negócio). "
            "Query: `skip`, `limit` (1–500, padrão 100), `active`.\n\n" + _BEARER
        ),
        "example_response": [_REPOSITORY_EXAMPLE],
    },
    "POST /api/v1/repositories/": {
        "summary": "Cria um repositório",
        "description": "Cria um repositório. `name` (1–100) é único: 409 se já existir.\n\n" + _BEARER,
        "example_request": {"name": "Suprimentos", "description": "Robôs da área de suprimentos", "active": True},
        "example_response": _REPOSITORY_EXAMPLE,
    },
    "GET /api/v1/repositories/{repository_id}": {
        "summary": "Detalhe de um repositório",
        "description": "Retorna um repositório pelo id. 404 se não existe.\n\n" + _BEARER,
        "example_response": _REPOSITORY_EXAMPLE,
    },
    "PUT /api/v1/repositories/{repository_id}": {
        "summary": "Atualiza um repositório",
        "description": "Atualização parcial (`name`, `description`, `active`). 409 se o novo nome já existe.\n\n" + _BEARER,
        "example_request": {"description": "Robôs de compras e estoque"},
        "example_response": _REPOSITORY_EXAMPLE,
    },
    "DELETE /api/v1/repositories/{repository_id}": {
        "summary": "Desativa um repositório (exclusão lógica)",
        "description": (
            "Não apaga: marca `active=false` e devolve o repositório. Bots e automações vinculados "
            "**não** são alterados.\n\n" + _BEARER
        ),
        "example_response": {**_REPOSITORY_EXAMPLE, "active": False},
    },
})


# --------------------------------------------------------------------- Runners
GUIDE.update({
    "GET /api/v1/runners/": {
        "summary": "Lista as máquinas (runners)",
        "description": (
            "Runners são as máquinas com o worker instalado, que executam os robôs.\n\n"
            "Query:\n"
            "- `skip` / `limit` (1–500).\n"
            "- `enabled`: filtra habilitadas/desabilitadas.\n"
            "- `status`: `online`, `offline`, `busy`, `maintenance`.\n"
            "- `removed=true`: lista só as removidas do painel (histórico); padrão lista as ativas.\n\n"
            "O `status` mostrado é derivado: `busy` quando há task executando nela. `last_heartbeat` é o "
            "último sinal do worker (sem sinal por ~3 min a máquina vira `offline`).\n\n" + _BEARER
        ),
        "example_response": [_RUNNER_EXAMPLE],
    },
    "POST /api/v1/runners/": {
        "summary": "Cria um runner manualmente (uso raro)",
        "description": (
            "Cadastra um runner direto pelo painel. **O caminho normal é o worker se registrar sozinho** "
            "(`POST /api/v1/worker/registration/`), que gera `uuid` e token. Aqui o `uuid` é gerado pelo "
            "servidor e `token_hash` precisa ser informado já em hash; `config` é opcional.\n\n"
            "409 se já existe runner com o mesmo `name`.\n\n" + _BEARER
        ),
        "example_request": {
            "name": "SRVRPA15",
            "label": "RPA 15",
            "host_name": "SRVRPA15",
            "token_hash": "hash-exemplo",
            "enabled": True,
            "config": {"max_concurrency": 1, "polling_interval": 15},
        },
        "example_response": {**_RUNNER_EXAMPLE, "id": 6, "name": "SRVRPA15", "label": "RPA 15", "status": "offline"},
    },
    "GET /api/v1/runners/overview": {
        "summary": "Resumo de todas as máquinas (contagens e uso)",
        "description": (
            "Uma linha por runner com tasks em execução/na fila, totais executados, sucessos, falhas, "
            "% de utilização e a última execução. Base da tela de Máquinas.\n\n"
            "Query: `skip`, `limit`, `enabled`, `status` (do runner) e filtros das tasks contadas: "
            "`date_from`, `date_to` (ISO 8601), `task_status`, `automation_id`.\n\n"
            "- `error_total_count` = error + timeout + forced_stop.\n"
            "- `utilization_percent` = tempo executando / tempo desde o cadastro (ou `date_from`).\n\n" + _BEARER
        ),
        "example_response": {
            "items": [
                {
                    "runner_id": 5,
                    "runner_name": "SRVRPA14",
                    "runner_label": "RPA 14",
                    "status": "online",
                    "enabled": True,
                    "linked_bots_count": 4,
                    "running_tasks_count": 0,
                    "waiting_tasks_count": 1,
                    "executed_total_count": 380,
                    "success_total_count": 371,
                    "error_total_count": 7,
                    "utilization_percent": 23.5,
                    "last_execution_at": "2026-10-21T13:40:02Z",
                    "last_execution_status": "finished",
                }
            ],
            "total": 1,
        },
    },
    "GET /api/v1/runners/{runner_id}": {
        "summary": "Detalhe de uma máquina",
        "description": (
            "Dados da máquina, configuração (`config`), contagem de tasks em execução, bots vinculados e se "
            "há screenshot. 404 se não existe.\n\n" + _BEARER
        ),
        "example_response": _RUNNER_EXAMPLE,
    },
    "PUT /api/v1/runners/{runner_id}": {
        "summary": "Atualiza dados de uma máquina",
        "description": (
            "Atualização parcial dos dados cadastrais (`label`, `enabled`, `access_remote`, `status`...).\n\n"
            "- `enabled=false` **desativa** a máquina: o worker passa a ser recusado (403) e não pega tasks.\n"
            "- `status=maintenance` impede a máquina de assumir novas tasks.\n"
            "- 409 se o novo `name` já existe.\n\n" + _BEARER
        ),
        "example_request": {"label": "RPA 14 - Suprimentos", "enabled": True},
        "example_response": _RUNNER_EXAMPLE,
    },
    "DELETE /api/v1/runners/{runner_id}": {
        "summary": "Remove a máquina do painel",
        "description": (
            "Remoção lógica (`deleted_at` preenchido): a máquina some das telas, perde os vínculos com "
            "automações e o worker dela passa a ser recusado (403) até ser registrado de novo "
            "(`configurar_worker.bat`).\n\n"
            "409 se houver task em execução nela: aguarde ou pare a task antes. Chamar de novo numa "
            "máquina já removida apenas devolve os dados.\n\n" + _BEARER
        ),
        "example_response": {**_RUNNER_EXAMPLE, "deleted_at": _TS},
    },
    "GET /api/v1/runners/{runner_id}/screenshot": {
        "summary": "Último print de tela da máquina (PNG)",
        "description": (
            "Devolve a última captura de tela enviada pelo worker, como imagem `image/png` (não JSON), "
            "sem cache. 404 se a máquina não existe ou ainda não enviou screenshot. Veja `last_screenshot_at` "
            "no detalhe do runner para saber quando foi tirada.\n\n" + _BEARER
        ),
    },
    "GET /api/v1/runners/{runner_id}/config": {
        "summary": "Configuração de execução da máquina",
        "description": (
            "Parâmetros que o worker usa:\n"
            "- `max_concurrency`: tasks BACKGROUND simultâneas (1–5). FOREGROUND é sempre 1 por máquina.\n"
            "- `polling_interval`: segundos entre buscas de task (mín. 5).\n"
            "- `auto_update_bots`, `install_all_bots_on_register`, `maintenance_mode`.\n\n"
            "404 se a máquina ou a configuração não existem.\n\n" + _BEARER
        ),
        "example_response": _RUNNER_CONFIG_EXAMPLE,
    },
    "PUT /api/v1/runners/{runner_id}/config": {
        "summary": "Altera a configuração de execução da máquina",
        "description": (
            "Atualização parcial da configuração. Validações: `max_concurrency` entre 1 e 5; "
            "`polling_interval` ≥ 5. O worker aplica na próxima sincronização.\n\n" + _BEARER
        ),
        "example_request": {"max_concurrency": 2, "polling_interval": 15},
        "example_response": _RUNNER_CONFIG_EXAMPLE,
    },
    "GET /api/v1/runners/{runner_id}/overview": {
        "summary": "Painel completo de uma máquina",
        "description": (
            "Visão detalhada de um runner: contagem de tasks por status, utilização, fila (task mais antiga "
            "esperando), última execução, bots vinculados, tasks rodando agora e as 10 mais recentes.\n\n"
            "Query: `date_from`, `date_to` (ISO 8601), `task_status`, `automation_id` filtram as contagens e "
            "a lista de recentes. 404 se a máquina não existe.\n\n" + _BEARER
        ),
        "example_response": {
            "runner": {
                "id": 5, "uuid": "6f1c2a9e-0000-4000-8000-000000000005", "name": "SRVRPA14", "label": "RPA 14",
                "host_name": "SRVRPA14", "ip": "10.0.0.14", "os_name": "Windows", "os_version": "10.0.20348",
                "cpu_arch": "AMD64", "memory_total": 17179869184, "access_remote": True, "enabled": True,
                "status": "online", "created_at": "2026-04-01T10:00:00Z", "updated_at": _TS, "last_heartbeat": _TS,
            },
            "summary": {
                "linked_bots_count": 4, "running_tasks_count": 0, "waiting_tasks_count": 1,
                "scheduled_tasks_count": 0, "ready_tasks_count": 0, "stop_requested_tasks_count": 0,
                "finished_tasks_count": 371, "error_tasks_count": 5, "timeout_tasks_count": 1,
                "canceled_tasks_count": 2, "forced_stop_tasks_count": 1, "executed_total_count": 380,
                "success_total_count": 371, "error_total_count": 7,
            },
            "utilization": {"registered_seconds": 17280000, "execution_seconds": 4060800, "utilization_percent": 23.5},
            "queue": {
                "waiting_tasks_count": 1, "oldest_waiting_task_id": 42730,
                "oldest_waiting_automation_name": "Estoque PO", "oldest_waiting_since": "2026-10-21T13:44:00Z",
                "oldest_waiting_seconds": 60,
            },
            "last_execution": {
                "task_id": 42723, "automation_id": 12, "automation_name": "Estoque PO", "status": "finished",
                "started_at": "2026-10-21T13:40:02Z", "finished_at": "2026-10-21T13:45:14Z",
                "execution_duration_seconds": 312, "final_message": "120 itens processados.",
            },
            "linked_bots": [{"bot_id": 9, "bot_name": "BOT_ETL_Estoque_PO"}],
            "running_tasks": [],
            "recent_tasks": [],
        },
    },
})


# ------------------------------------------------------------------------ Bots
GUIDE.update({
    "GET /api/v1/bots/": {
        "summary": "Lista bots (robôs) com paginação",
        "description": (
            "Bots são os robôs (código) que as automações executam.\n\n"
            "Query: `skip`, `limit` (1–100, **padrão 10**), `search` (nome), `repository_id`, `active`. "
            "A resposta traz `items` e `total` para paginar.\n\n"
            "`current_version` é a versão mais nova registrada; a versão realmente executada pode estar "
            "fixada por Release (veja *Bot Versions*).\n\n" + _BEARER
        ),
        "example_response": {
            "items": [
                {
                    "id": 9, "name": "BOT_ETL_Estoque_PO", "description": "Extrai o estoque de pedidos de compra",
                    "repository_id": 3, "repository_name": "Suprimentos", "execution_mode": "background",
                    "current_version": "1.4.2", "release_version": "1.0.0", "active": True,
                    "auto_update": False, "created_at": "2026-05-04T12:00:00Z",
                }
            ],
            "total": 1,
        },
    },
    "POST /api/v1/bots/": {
        "summary": "Cadastra um bot e sua versão inicial",
        "description": (
            "Cria o bot e, junto, a primeira versão (`initial_version`, ex.: `1.0.0`). O criador é o usuário "
            "do token.\n\n"
            "Campos principais:\n"
            "- `technology` (ex.: `python`), `source_type` (ex.: `git`), `source_url` (repositório Git).\n"
            "- `entrypoint`: arquivo que o worker executa (ex.: `main.py`); `requirements_file` opcional.\n"
            "- `execution_mode`: `background` (sem tela, pode rodar em paralelo) ou `foreground` "
            "(usa a tela; 1 por máquina).\n"
            "- `timeout_default`: segundos, usado quando a task não informa timeout.\n"
            "- `auto_update`: o worker acompanha a branch do Git automaticamente.\n\n"
            "404 se o repositório não existe; 409 se já existe bot com o mesmo nome no repositório.\n\n" + _BEARER
        ),
        "example_request": {
            "name": "BOT_ETL_Estoque_PO",
            "description": "Extrai o estoque de pedidos de compra",
            "technology": "python",
            "repository_id": 3,
            "source_type": "git",
            "execution_mode": "background",
            "source_url": "https://git.exemplo.com/rpa/bot-estoque-po.git",
            "entrypoint": "main.py",
            "requirements_file": "requirements.txt",
            "timeout_default": 3600,
            "active": True,
            "auto_update": False,
            "initial_version": "1.0.0",
        },
        "example_response": {**_BOT_EXAMPLE, "current_version": "1.0.0"},
    },
    "GET /api/v1/bots/{bot_id}": {
        "summary": "Detalhe de um bot",
        "description": "Retorna o cadastro completo do bot. 404 se não existe.\n\n" + _BEARER,
        "example_response": _BOT_EXAMPLE,
    },
    "PUT /api/v1/bots/{bot_id}": {
        "summary": "Atualiza um bot",
        "description": (
            "Atualização parcial. Ex.: trocar `entrypoint`, `timeout_default`, `execution_mode`, ativar/desativar.\n\n"
            "- `active=false`: o bot deixa de ser sincronizado nas máquinas e não aceita novas tasks/versões.\n"
            "- 404 se o novo `repository_id` não existe.\n\n" + _BEARER
        ),
        "example_request": {"timeout_default": 5400, "auto_update": True},
        "example_response": {**_BOT_EXAMPLE, "timeout_default": 5400, "auto_update": True},
    },
    "DELETE /api/v1/bots/{bot_id}": {
        "summary": "Apaga um bot (definitivo)",
        "description": (
            "**Exclusão física** do bot. Pode falhar se houver automações, versões ou tasks ligadas a ele. "
            "Na dúvida, prefira desativar com `PUT /api/v1/bots/{bot_id}` e `active=false`.\n\n" + _BEARER
        ),
        "example_response": {"message": "Bot removido com sucesso."},
    },
})


# ---------------------------------------------------------------- Bot Versions
GUIDE.update({
    "GET /api/v1/bot-versions/": {
        "summary": "Lista todas as versões de todos os bots",
        "description": (
            "Todas as versões cadastradas, sem paginação nem filtro. Cada item indica:\n"
            "- `in_use`: é a versão que as novas tasks vão executar hoje.\n"
            "- `pinned`: foi fixada por Release (o bot não segue mais a mais nova).\n\n"
            "Regra da versão em uso: a fixada por Release; senão a ativa mais nova; senão a mais nova.\n\n" + _BEARER
        ),
        "example_response": [_BOT_VERSION_EXAMPLE],
    },
    "POST /api/v1/bot-versions/": {
        "summary": "Registra uma nova versão de um bot",
        "description": (
            "Cria uma versão (normalmente com os dados sugeridos por `GET /api/v1/bot-versions/git-preview`).\n\n"
            "- `version` no formato `X.Y.Z` e única por bot (409 se repetir).\n"
            "- 409 se o bot está inativo ou se o `commit_hash` já está em outra versão (use Release nela).\n"
            "- `created_by` é preenchido com o usuário do token.\n\n"
            "**Efeito colateral:** se o bot tinha uma versão fixada por Release, a fixação é removida e a "
            "nova versão passa a ser a executada.\n\n" + _BEARER
        ),
        "example_request": {
            "bot_id": 9,
            "version": "1.4.3",
            "storage_type": "git",
            "commit_hash": "b2c3d4e5f60718293a4b5c6d7e8f901234567890",
            "branch": "main",
            "changelog": "- Ajusta timeout do SAP",
            "is_active": True,
        },
        "example_response": {**_BOT_VERSION_EXAMPLE, "id": 88, "version": "1.4.3"},
    },
    "GET /api/v1/bot-versions/git-preview": {
        "summary": "Compara o bot com o Git e sugere a próxima versão",
        "description": (
            "Lê o repositório Git do bot (`source_url`) e monta a versão que seria criada. **Não grava nada.**\n\n"
            "Query obrigatória: `bot_id`.\n\n"
            "`status` da resposta:\n"
            "- `nova_versao`: o Git está à frente; use `suggested_version`, `head` e `changelog` em `POST /api/v1/bot-versions/`.\n"
            "- `sincronizado`: o último commit já é a versão mais nova.\n"
            "- `ja_registrado`: o último commit está numa versão antiga (`existing_version_id`); use Release nela.\n\n"
            "A URL do repositório volta sem usuário/token.\n\n" + _BEARER
        ),
        "example_response": {
            "bot_id": 9,
            "bot_name": "BOT_ETL_Estoque_PO",
            "status": "nova_versao",
            "message": "O Git está à frente: commit b2c3d4e de Maria Souza.",
            "branch": "main",
            "repository": "https://git.exemplo.com/rpa/bot-estoque-po.git",
            "head": {
                "hash": "b2c3d4e5f60718293a4b5c6d7e8f901234567890",
                "short": "b2c3d4e",
                "author": "Maria Souza",
                "committed_at": "2026-10-20T16:00:00Z",
                "message": "Ajusta timeout do SAP",
            },
            "commits": [],
            "suggested_version": "1.4.3",
            "changelog": "- Ajusta timeout do SAP (b2c3d4e, Maria Souza, 20/10/2026 16:00)",
            "last_version": "1.4.2",
            "last_commit": "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
            "existing_version_id": None,
            "existing_version": None,
        },
    },
    "POST /api/v1/bot-versions/{bot_version_id}/release": {
        "summary": "Passa a executar esta versão (Release/rollback)",
        "description": (
            "Define qual versão as **novas** tasks do bot vão executar (tasks já criadas mantêm a delas).\n\n"
            "- Numa versão antiga: fixa essa versão (rollback); o bot deixa de seguir a mais nova e o "
            "auto-update do worker fica suspenso.\n"
            "- Na versão mais nova: remove a fixação e o bot volta a seguir sempre a mais nova.\n\n"
            "A versão também é marcada como ativa. Sem corpo.\n\n" + _BEARER
        ),
        "example_response": {**_BOT_VERSION_EXAMPLE, "version": "1.4.1", "id": 85, "pinned": True, "in_use": True},
    },
    "GET /api/v1/bot-versions/{bot_version_id}": {
        "summary": "Detalhe de uma versão de bot",
        "description": "Retorna uma versão com `in_use` e `pinned`. 404 se não existe.\n\n" + _BEARER,
        "example_response": _BOT_VERSION_EXAMPLE,
    },
    "PUT /api/v1/bot-versions/{bot_version_id}": {
        "summary": "Atualiza dados de uma versão",
        "description": (
            "Atualização parcial (`version`, `changelog`, `artifact_path`, `checksum`, `is_active`...). "
            "Commit e branch não mudam por aqui. 409 se o novo número já existe no bot.\n\n"
            "`is_active=false` tira a versão da escolha automática (a menos que esteja fixada por Release).\n\n" + _BEARER
        ),
        "example_request": {"changelog": "- Ajusta timeout do SAP\n- Melhora logs"},
        "example_response": _BOT_VERSION_EXAMPLE,
    },
    "DELETE /api/v1/bot-versions/{bot_version_id}": {
        "summary": "Apaga uma versão de bot (definitivo)",
        "description": (
            "**Exclusão física** da versão. Pode falhar se houver tasks que a usaram. Para só tirá-la de uso, "
            "prefira `is_active=false` ou Release em outra versão.\n\n" + _BEARER
        ),
        "example_response": {"message": "Versão do bot removida com sucesso."},
    },
})


# ----------------------------------------------------------------- Automations
GUIDE.update({
    "GET /api/v1/automations/": {
        "summary": "Lista automações",
        "description": (
            "Automação = um bot + parâmetros padrão + máquinas onde pode rodar. É o que se executa (gera tasks).\n\n"
            "Query (todas opcionais): `active`, `repository_id`, `bot_id`. Sem paginação.\n\n"
            "Cada item traz grupos exclusivos (`exclusive_groups`) e gatilhos de sucesso (`success_triggers`).\n\n" + _BEARER
        ),
        "example_response": [_AUTOMATION_EXAMPLE],
    },
    "POST /api/v1/automations/": {
        "summary": "Cria uma automação",
        "description": (
            "Cria uma automação para um bot.\n\n"
            "- `bot_id` precisa pertencer ao `repository_id` (400 se não pertencer; 404 se não existirem).\n"
            "- `name` único por repositório (409).\n"
            "- `default_priority`: 1–10 (padrão 5).\n"
            "- `exclusive_group_ids`: grupos ativos em que só uma task roda por vez entre as automações do grupo.\n"
            "- `success_trigger_automation_ids`: automações disparadas automaticamente quando uma task desta termina com sucesso.\n"
            "- `default_parameters_json` / `default_runtime_parameters_json`: parâmetros padrão enviados ao robô.\n\n"
            "Depois de criar, vincule as máquinas em `POST /api/v1/automations/{automation_id}/runners`: sem "
            "máquina vinculada nenhuma task roda.\n\n" + _BEARER
        ),
        "example_request": {
            "name": "Estoque PO",
            "label": "Estoque de pedidos de compra",
            "description": "Atualiza o estoque de PO no SAP",
            "bot_id": 9,
            "repository_id": 3,
            "default_priority": 5,
            "active": True,
            "exclusive_group_ids": [2],
            "success_trigger_automation_ids": [15],
            "default_parameters_json": {"empresa": "1000"},
            "default_runtime_parameters_json": {"filial": "010"},
        },
        "example_response": _AUTOMATION_EXAMPLE,
    },
    "GET /api/v1/automations/exclusive-groups/": {
        "summary": "Lista grupos exclusivos",
        "description": (
            "Grupos exclusivos impedem que automações concorrentes rodem ao mesmo tempo (ex.: duas que usam "
            "o mesmo login do SAP). Query: `active`. Cada grupo traz `automation_ids` vinculados.\n\n" + _BEARER
        ),
        "example_response": [_AUTOMATION_EXAMPLE["exclusive_groups"][0]],
    },
    "POST /api/v1/automations/exclusive-groups/": {
        "summary": "Cria um grupo exclusivo",
        "description": (
            "Cria um grupo; depois vincule automações a ele via `exclusive_group_ids` na automação.\n\n"
            "- `name` único (409).\n"
            "- `capacity` só aceita **1** nesta versão (400 para outro valor).\n\n"
            "Não há rota para editar ou apagar grupos pela API.\n\n" + _BEARER
        ),
        "example_request": {
            "name": "sap-suprimentos",
            "label": "SAP Suprimentos",
            "description": "Só um robô por vez no SAP de suprimentos",
            "capacity": 1,
            "active": True,
        },
        "example_response": {**_AUTOMATION_EXAMPLE["exclusive_groups"][0], "automation_ids": []},
    },
    "GET /api/v1/automations/{automation_id}": {
        "summary": "Detalhe de uma automação",
        "description": "Retorna a automação com bot, repositório, grupos e gatilhos. 404 se não existe.\n\n" + _BEARER,
        "example_response": _AUTOMATION_EXAMPLE,
    },
    "PUT /api/v1/automations/{automation_id}": {
        "summary": "Atualiza uma automação",
        "description": (
            "Atualização parcial. Mesmas validações da criação (bot do repositório, nome único).\n\n"
            "- `exclusive_group_ids` e `success_trigger_automation_ids`, quando enviados, **substituem** a lista "
            "atual (envie `[]` para limpar). Omitidos, ficam como estão.\n"
            "- Uma automação não pode disparar a si mesma (400).\n\n" + _BEARER
        ),
        "example_request": {"default_priority": 3, "success_trigger_automation_ids": []},
        "example_response": {**_AUTOMATION_EXAMPLE, "default_priority": 3, "success_trigger_automation_ids": [], "success_triggers": []},
    },
    "POST /api/v1/automations/{automation_id}/activate": {
        "summary": "Ativa uma automação",
        "description": "Marca a automação como ativa: volta a aceitar tasks manuais e agendadas. Sem corpo.\n\n" + _BEARER,
        "example_response": _AUTOMATION_EXAMPLE,
    },
    "POST /api/v1/automations/{automation_id}/deactivate": {
        "summary": "Desativa uma automação",
        "description": (
            "Marca a automação como inativa: novas tasks são recusadas (400) e as máquinas deixam de "
            "sincronizar o bot por ela. Tasks já em andamento não são paradas. Sem corpo.\n\n" + _BEARER
        ),
        "example_response": {**_AUTOMATION_EXAMPLE, "active": False},
    },
    "GET /api/v1/automations/{automation_id}/runners": {
        "summary": "Lista as máquinas vinculadas à automação",
        "description": (
            "Máquinas onde a automação pode rodar. O `id` de cada item é o **id do vínculo** (use-o para "
            "desvincular), e `runner_id` é a máquina. 404 se a automação não existe.\n\n" + _BEARER
        ),
        "example_response": [
            {
                "id": 40,
                "automation_id": 12,
                "runner_id": 5,
                "runner_name": "SRVRPA14",
                "runner_label": "RPA 14",
                "runner_status": "online",
                "runner_enabled": True,
                "created_at": "2026-05-01T12:00:00Z",
            }
        ],
    },
    "POST /api/v1/automations/{automation_id}/runners": {
        "summary": "Vincula uma máquina à automação",
        "description": (
            "Permite que a automação rode na máquina informada. A máquina passa a instalar/sincronizar o bot.\n\n"
            "- 404 se a automação ou a máquina não existem (ou a máquina foi removida).\n"
            "- 409 se o vínculo já existe.\n\n" + _BEARER
        ),
        "example_request": {"runner_id": 5},
        "example_response": {
            "id": 40,
            "automation_id": 12,
            "runner_id": 5,
            "runner_name": "SRVRPA14",
            "runner_label": "RPA 14",
            "runner_status": "online",
            "runner_enabled": True,
            "created_at": _TS,
        },
    },
    "DELETE /api/v1/automations/{automation_id}/runners/{link_id}": {
        "summary": "Desvincula uma máquina da automação",
        "description": (
            "Remove o vínculo (`link_id` = `id` retornado na listagem de máquinas da automação, **não** o id "
            "da máquina). Resposta 204 sem corpo. 404 se o vínculo não é desta automação.\n\n" + _BEARER
        ),
    },
    "GET /api/v1/automations/{automation_id}/parameters": {
        "summary": "Lista os parâmetros declarados da automação",
        "description": (
            "Parâmetros que a automação espera (formulário de execução): nome, tipo, valor padrão, "
            "obrigatoriedade e valores permitidos. Usados para validar `POST /api/v1/tasks/`.\n\n" + _BEARER
        ),
        "example_response": [_PARAMETER_EXAMPLE],
    },
    "POST /api/v1/automations/{automation_id}/parameters": {
        "summary": "Declara um parâmetro na automação",
        "description": (
            "Cria um parâmetro.\n\n"
            "- `type`: `string`, `integer`, `float`, `boolean`, `datetime`, `json`, `select`, `secret_ref`.\n"
            "- `select` exige `allowed_values` (400).\n"
            "- `required=true` sem `default_value` obriga quem cria a task a informar o valor.\n"
            "- `name` único na automação (409).\n\n" + _BEARER
        ),
        "example_request": {
            "name": "filial",
            "label": "Filial",
            "description": "Código da filial a processar",
            "type": "select",
            "allowed_values": ["010", "020", "030"],
            "default_value": "010",
            "required": True,
            "order_index": 0,
        },
        "example_response": _PARAMETER_EXAMPLE,
    },
    "PUT /api/v1/automations/{automation_id}/parameters/{parameter_id}": {
        "summary": "Atualiza um parâmetro da automação",
        "description": (
            "Atualização parcial. Mantém as regras: nome único na automação (409) e `select` com "
            "`allowed_values` (400). 404 se o parâmetro não é desta automação.\n\n" + _BEARER
        ),
        "example_request": {"default_value": "020"},
        "example_response": {**_PARAMETER_EXAMPLE, "default_value": "020"},
    },
    "DELETE /api/v1/automations/{automation_id}/parameters/{parameter_id}": {
        "summary": "Remove um parâmetro da automação",
        "description": (
            "Apaga a declaração do parâmetro. Tasks antigas mantêm os valores que já gravaram. "
            "Resposta 204 sem corpo.\n\n" + _BEARER
        ),
    },
})


# ----------------------------------------------------------- Automation Health
GUIDE.update({
    "GET /api/v1/automation-health/": {
        "summary": "Saúde de cada automação (última execução e atraso)",
        "description": (
            "Painel de monitoramento: para cada automação, a última task, o agendamento principal e um "
            "semáforo:\n"
            "- `error` (vermelho): a última task falhou.\n"
            "- `running` (verde claro): está executando agora.\n"
            "- `warning` (amarelo): está atrasada em relação ao agendamento (`is_overdue`) ou sem execução conhecida.\n"
            "- `success` (verde): última execução com sucesso e no prazo.\n\n"
            "Query: `repository_id`, `bot_id`, `active` (**padrão `true`**: só automações ativas).\n\n" + _BEARER
        ),
        "example_response": {
            "items": [
                {
                    "automation_id": 12,
                    "automation_name": "Estoque PO",
                    "automation_label": "Estoque de pedidos de compra",
                    "automation_description": None,
                    "automation_active": True,
                    "repository_id": 3,
                    "repository_name": "Suprimentos",
                    "bot_id": 9,
                    "bot_name": "BOT_ETL_Estoque_PO",
                    "bot_active": True,
                    "health_status": "success",
                    "health_label": "Success",
                    "status_color": "green",
                    "monitored_at": _TS,
                    "last_execution_at": "2026-10-21T13:40:02Z",
                    "is_overdue": False,
                    "has_recent_success": True,
                    "has_recent_error": False,
                    "has_running_task": False,
                    "machine_name": "SRVRPA14",
                    "machine_label": "RPA 14",
                    "machine_display_name": "RPA 14",
                    "schedule": None,
                    "last_task": {
                        "id": 42723, "status": "finished", "runner_id": 5, "runner_name": "SRVRPA14",
                        "runner_label": "RPA 14", "runner_display_name": "RPA 14",
                        "started_at": "2026-10-21T13:40:02Z", "finished_at": "2026-10-21T13:45:14Z",
                        "last_update_at": "2026-10-21T13:45:14Z", "final_message": "120 itens processados.",
                        "execution_duration_seconds": 312,
                    },
                }
            ],
            "total": 1,
        },
    },
})


# ------------------------------------------------------------------- Schedules
GUIDE.update({
    "GET /api/v1/schedules/": {
        "summary": "Lista agendamentos",
        "description": (
            "Agendamentos criam tasks automaticamente. Query: `automation_id`, `active`, `status` "
            "(`active`, `inactive`, `paused`, `error`). Cada item traz `next_run_at`, `last_run_at`, "
            "`last_error` e o último motivo de execução pulada (`last_skipped_reason`).\n\n" + _BEARER
        ),
        "example_response": [_SCHEDULE_EXAMPLE],
    },
    "POST /api/v1/schedules/": {
        "summary": "Cria um agendamento para uma automação",
        "description": (
            "Dois tipos:\n"
            "- `schedule_type=cron`: exige `cron_expression` (ex.: `0 7-18 * * 1-5`).\n"
            "- `schedule_type=calendar`: exige `calendar_type` (`once`, `second`, `minute`, `hour`, `day`, "
            "`week`, `month`); os recorrentes exigem `interval_value` > 0 (ex.: a cada 2 horas).\n\n"
            "`policy` define o que fazer quando chega a hora:\n"
            "- `create_always`: cria a task sempre.\n"
            "- `ignore_if_running`: pula se a automação já está executando.\n"
            "- `enqueue_if_none_pending`: pula se já há task na fila ou executando.\n"
            "- `run_if_missed`: se o horário passou (ex.: serviço parado), executa assim que possível.\n"
            "- `skip_if_missed`: se o horário passou da tolerância, pula.\n\n"
            "Outros campos: `timezone` (IANA, ex.: `America/Sao_Paulo`; padrão `UTC`), `priority` 1–10, "
            "`runtime_parameters_json` (parâmetros de execução) e `use_default_runtime_parameters`.\n\n"
            "404 se a automação não existe; 409 se já há agendamento com o mesmo nome nela; 400 para "
            "timezone inválido ou campos obrigatórios faltando.\n\n" + _BEARER
        ),
        "example_request": {
            "name": "Estoque PO - a cada hora",
            "automation_id": 12,
            "priority": 5,
            "schedule_type": "cron",
            "cron_expression": "0 7-18 * * 1-5",
            "policy": "ignore_if_running",
            "runtime_parameters_json": {"filial": "010"},
            "use_default_runtime_parameters": True,
            "timezone": "America/Sao_Paulo",
            "active": True,
        },
        "example_response": _SCHEDULE_EXAMPLE,
    },
    "GET /api/v1/schedules/{schedule_id}": {
        "summary": "Detalhe de um agendamento",
        "description": "Retorna o agendamento com próximas/últimas execuções e último erro. 404 se não existe.\n\n" + _BEARER,
        "example_response": _SCHEDULE_EXAMPLE,
    },
    "PUT /api/v1/schedules/{schedule_id}": {
        "summary": "Atualiza um agendamento",
        "description": (
            "Atualização parcial com as mesmas validações da criação (sobre o resultado final). Ao trocar "
            "o tipo, os campos do outro tipo são limpos (ex.: virar `calendar` apaga `cron_expression`).\n\n"
            "Também aceita `start_at`/`end_at` (janela de validade) e `status`. Para pausar/reativar prefira "
            "as rotas próprias.\n\n" + _BEARER
        ),
        "example_request": {"cron_expression": "0 6-20 * * 1-6", "policy": "enqueue_if_none_pending"},
        "example_response": {**_SCHEDULE_EXAMPLE, "cron_expression": "0 6-20 * * 1-6", "policy": "enqueue_if_none_pending"},
    },
    "POST /api/v1/schedules/{schedule_id}/pause": {
        "summary": "Pausa um agendamento",
        "description": (
            "Deixa o agendamento `paused` (`active=false`): ele para de criar tasks até ser reativado. "
            "Tasks já criadas não são afetadas. É o mesmo estado aplicado automaticamente pelas notificações "
            "de falha. Sem corpo.\n\n" + _BEARER
        ),
        "example_response": {**_SCHEDULE_EXAMPLE, "status": "paused", "active": False},
    },
    "POST /api/v1/schedules/{schedule_id}/reactivate": {
        "summary": "Reativa um agendamento",
        "description": "Volta o agendamento para `active` (`active=true`); ele volta a criar tasks. Sem corpo.\n\n" + _BEARER,
        "example_response": _SCHEDULE_EXAMPLE,
    },
    "POST /api/v1/schedules/{schedule_id}/deactivate": {
        "summary": "Desativa um agendamento",
        "description": (
            "Deixa o agendamento `inactive` (`active=false`). Mesmo efeito prático da pausa (não cria tasks), "
            "mas indica desligamento intencional e não temporário. Não há exclusão pela API. Sem corpo.\n\n" + _BEARER
        ),
        "example_response": {**_SCHEDULE_EXAMPLE, "status": "inactive", "active": False},
    },
})


# ----------------------------------------------------------------------- Tasks
GUIDE.update({
    "GET /api/v1/tasks/filter-options": {
        "summary": "Opções para filtros de tasks (automações, máquinas, status)",
        "description": (
            "Listas prontas para montar filtros: automações e máquinas ativas (id, nome, label) e todos os "
            "status possíveis de task.\n\n" + _BEARER
        ),
        "example_response": {
            "automations": [{"id": 12, "name": "Estoque PO", "label": "Estoque de pedidos de compra"}],
            "runners": [{"id": 5, "name": "SRVRPA14", "label": "RPA 14"}],
            "statuses": [
                "waiting", "scheduled", "ready", "running", "stop_requested",
                "forced_stop", "canceled", "finished", "error", "timeout",
            ],
        },
    },
    "GET /api/v1/tasks/": {
        "summary": "Lista tasks (execuções) com filtros",
        "description": (
            "Lista as execuções, mais recentes primeiro, com `items` e `total` para paginar.\n\n"
            "Query:\n"
            "- `skip` / `limit` (1–500, padrão 100).\n"
            "- `status` ou `statuses` (repetível: `?statuses=error&statuses=timeout`).\n"
            "- `automation_id` ou `automation_ids` (repetível); `runner_id` ou `runner_ids`; `created_by`.\n"
            "Quando a forma plural é enviada, a singular é ignorada.\n\n"
            "Status: `waiting`/`ready` (fila), `scheduled` (aguardando `requested_start_at`), `running`, "
            "`stop_requested` (parada pedida), `finished` (sucesso), `error`/`timeout`/`forced_stop` (falha), "
            "`canceled`.\n\n" + _BEARER
        ),
        "example_response": {
            "items": [
                {k: _TASK_EXAMPLE[k] for k in (
                    "id", "automation_id", "automation_name", "bot_version_id", "bot_version_label", "runner_id",
                    "runner_name", "runner_label", "runner_display_name", "created_by", "created_by_name",
                    "schedule_id", "schedule_name", "priority", "status", "requested_start_at", "started_at",
                    "finished_at", "last_update_at", "created_at", "items_processed", "items_failed",
                    "execution_mode", "stop_requested", "correlation_id", "queue_name", "final_message",
                    "execution_duration_seconds",
                )}
            ],
            "total": 1,
        },
    },
    "POST /api/v1/tasks/": {
        "summary": "Cria uma task (executa uma automação)",
        "description": (
            "Coloca uma execução da automação na fila; a próxima máquina vinculada e livre a assume. "
            "O dono do token fica registrado como \"Criado por\".\n\n"
            "Campos principais:\n"
            "- `automation_id` (obrigatório).\n"
            "- `runner_id`: força uma máquina (precisa estar vinculada à automação, senão 400).\n"
            "- `priority` (padrão 5), `timeout_seconds` (padrão: o do bot), `inactivity_timeout_seconds`.\n"
            "- `requested_start_at`: com fuso (ex.: `2026-10-22T08:00:00-03:00`); a task fica `scheduled` até a hora. "
            "Sem fuso dá 400.\n"
            "- `bot_version_id`: omitido, usa a versão em uso do bot (Release > ativa mais nova).\n"
            "- `execution_mode`: `manual` (padrão), `api`, `retry`, `reprocess`, `scheduled`.\n"
            "- `correlation_id`: id livre para você rastrear a execução no seu sistema.\n"
            "- `parameters`: lista de `parameter_name`/`parameter_value`. Os nomes especiais "
            "`parameters_json` (JSON válido) e `runtime_parameters_json` (objeto JSON) são entregues ao robô; "
            "parâmetros obrigatórios da automação podem vir como chave dentro de `runtime_parameters_json`. "
            "Parâmetros não informados recebem o `default_value` declarado.\n\n"
            "Erros comuns (400): automação ou bot inativo, parâmetro obrigatório faltando, JSON inválido, "
            "bot sem versão, e **já existe task aberta para a automação** (só uma por vez, exceto quando "
            "`parent_task_id` é informado). 404 se a automação não existe.\n\n" + _BEARER
        ),
        "example_request": {
            "automation_id": 12,
            "priority": 5,
            "execution_mode": "api",
            "correlation_id": "erp-pedido-998877",
            "parameters": [
                {"parameter_name": "runtime_parameters_json", "parameter_value": "{\"filial\": \"010\"}"}
            ],
        },
        "example_response": {
            "message": "Task criada com sucesso.",
            "task": {
                **_TASK_EXAMPLE,
                "status": "waiting",
                "schedule_id": None,
                "schedule_name": None,
                "execution_mode": "api",
                "correlation_id": "erp-pedido-998877",
                "runner_id": None,
                "runner_name": None,
                "runner_label": None,
                "runner_display_name": None,
                "started_at": None,
                "finished_at": None,
                "runner_claimed_at": None,
                "final_message": None,
                "items_processed": 0,
                "dispatch_attempts": 0,
                "execution_duration_seconds": None,
            },
        },
    },
    "GET /api/v1/tasks/{task_id}": {
        "summary": "Detalhe completo de uma task",
        "description": (
            "Tudo sobre uma execução: status, horários, mensagem final (`final_message`), resultado "
            "(`result_json`), contadores de itens, parâmetros, telemetria (CPU/memória), dados da máquina "
            "(`runner_details`) e uso da máquina (`runner_usage`). `execution_duration_seconds` conta até agora "
            "se ainda está rodando.\n\n"
            "Para acompanhar uma task criada via API, consulte esta rota até o status ser final "
            "(`finished`, `error`, `timeout`, `forced_stop` ou `canceled`). 404 se não existe.\n\n" + _BEARER
        ),
        "example_response": _TASK_EXAMPLE,
    },
    "GET /api/v1/tasks/{task_id}/parameters": {
        "summary": "Parâmetros gravados na task",
        "description": (
            "Os parâmetros finais com que a task foi criada (informados + padrões da automação). "
            "404 se a task não existe.\n\n" + _BEARER
        ),
        "example_response": {"items": _TASK_EXAMPLE["parameters"], "total": 1},
    },
    "POST /api/v1/tasks/{task_id}/request-stop": {
        "summary": "Pede para a task parar (parada gentil)",
        "description": (
            "Forma recomendada de interromper uma execução:\n"
            "- Task `waiting`: é **cancelada** na hora (`canceled`), pois nenhuma máquina a assumiu.\n"
            "- Task `ready`/`running`: vira `stop_requested`; o worker percebe no próximo ciclo, encerra o robô "
            "e finaliza a task.\n\n"
            "400 se a task já está finalizada ou em estado que não permite parada (ex.: `scheduled`, use cancel). "
            "Sem corpo.\n\n" + _BEARER
        ),
        "example_response": {"message": "Solicitação de parada registrada com sucesso.", "task_id": 42723, "status": "stop_requested"},
    },
    "POST /api/v1/tasks/{task_id}/force-stop": {
        "summary": "Força a parada da task (marca forced_stop na hora)",
        "description": (
            "Finaliza a task imediatamente como `forced_stop` e libera os locks, sem esperar o worker. "
            "O worker, ao consultar o status, encerra o processo local. Use quando a parada gentil não "
            "resolveu (máquina travada, worker sem resposta).\n\n"
            "Permitido em `ready`, `running` e `stop_requested`; 400 nos demais. Sem corpo.\n\n" + _BEARER
        ),
        "example_response": {"message": "Parada forçada aplicada com sucesso.", "task_id": 42723, "status": "forced_stop"},
    },
    "POST /api/v1/tasks/{task_id}/cancel": {
        "summary": "Cancela uma task que ainda não começou",
        "description": (
            "Marca como `canceled` uma task que ainda não executou (`waiting`, `scheduled` ou `ready`) e libera "
            "os locks. Para task em execução use `request-stop`. 400 para task finalizada ou rodando. "
            "Sem corpo.\n\n" + _BEARER
        ),
        "example_response": {"message": "Task cancelada com sucesso.", "task_id": 42730, "status": "canceled"},
    },
})


# ------------------------------------------------------------------- Task Logs
GUIDE.update({
    "GET /api/v1/task-logs/task/{task_id}": {
        "summary": "Logs (eventos) de uma task",
        "description": (
            "Linhas de log estruturadas da execução, enviadas pelo worker e pelo próprio orquestrador "
            "(claim, parada, reinício do worker...).\n\n"
            "Query: `skip`, `limit` (1–500, padrão 100), `level` (`debug`, `info`, `warning`, `error`, `critical`).\n\n"
            "`source` indica a origem (`worker`, `system`, `panel`, `backend`, `scheduler`, `dispatcher`) e "
            "`event_code` um código estável do evento. Para a saída bruta do console do robô veja *Runner Logs*.\n\n" + _BEARER
        ),
        "example_response": {
            "items": [
                {
                    "id": 880001,
                    "task_id": 42723,
                    "level": "info",
                    "message": "Login no SAP realizado.",
                    "reference": None,
                    "error_type": None,
                    "source": "worker",
                    "sequence_number": 3,
                    "runner_id": 5,
                    "event_code": None,
                    "created_at": "2026-10-21T13:40:30Z",
                }
            ],
            "total": 1,
        },
    },
    "GET /api/v1/task-logs/{log_id}": {
        "summary": "Detalhe de uma linha de log",
        "description": "Retorna uma linha de log pelo id. 404 se não existe.\n\n" + _BEARER,
        "example_response": {
            "id": 880001,
            "task_id": 42723,
            "level": "info",
            "message": "Login no SAP realizado.",
            "reference": None,
            "error_type": None,
            "source": "worker",
            "sequence_number": 3,
            "runner_id": 5,
            "event_code": None,
            "created_at": "2026-10-21T13:40:30Z",
            "updated_at": None,
        },
    },
})


# ----------------------------------------------------------------- Task Errors
_TASK_ERROR_RICH = {
    "id": 5012,
    "task_id": 42719,
    "error_type": "RuntimeError",
    "message": "Falha no login SAP: senha incorreta",
    "stacktrace": "Traceback (most recent call last):\n  ...\nRuntimeError: Falha no login SAP: senha incorreta",
    "error_category": "business",
    "is_retryable": False,
    "source": "worker",
    "code": "SAP_LOGIN",
    "created_at": "2026-10-21T12:41:10Z",
    "error_screenshot_base64": None,
    "task_status": "error",
    "automation_id": 12,
    "automation_name": "Estoque PO",
    "automation_label": "Estoque de pedidos de compra",
    "bot_id": 9,
    "bot_name": "BOT_ETL_Estoque_PO",
    "bot_version_id": 87,
    "bot_version_label": "1.4.2",
    "repository_id": 3,
    "repository_name": "Suprimentos",
    "runner_id": 5,
    "runner_name": "SRVRPA14",
    "runner_label": "RPA 14",
    "created_by": None,
    "created_by_name": None,
    "final_message": "Falha no login SAP: senha incorreta",
    "task_created_at": "2026-10-21T12:39:58Z",
    "task_started_at": "2026-10-21T12:40:02Z",
    "task_finished_at": "2026-10-21T12:41:11Z",
    "execution_duration_seconds": 69,
}

GUIDE.update({
    "GET /api/v1/task-errors": {
        "summary": "Busca erros de todas as tasks (com contexto)",
        "description": (
            "Lista erros registrados, mais recentes primeiro, já com dados da task, automação, bot, versão e "
            "máquina. Ideal para relatórios de falhas.\n\n"
            "Query:\n"
            "- `skip` / `limit` (1–500, **padrão 10**).\n"
            "- `q`: texto livre (mensagem/tipo).\n"
            "- `task_id`, `automation_id`, `error_type`, `code`, `source`, `is_retryable`.\n"
            "- `error_category`: `technical`, `business`, `timeout`, `lock`, `validation`, `dependency`, `network`.\n"
            "- `start_date` / `end_date` (ISO 8601).\n\n"
            "`error_screenshot_base64` pode trazer o print da tela no momento do erro (pode ser grande).\n\n" + _BEARER
        ),
        "example_response": {"items": [_TASK_ERROR_RICH], "total": 1},
    },
    "GET /api/v1/task-errors/task/{task_id}": {
        "summary": "Erros de uma task",
        "description": (
            "Erros registrados para uma task específica (tipo, mensagem, traceback, categoria). Query: `skip`, "
            "`limit` (1–500), `error_type`. 404 se a task não existe.\n\n" + _BEARER
        ),
        "example_response": {
            "items": [{k: _TASK_ERROR_RICH[k] for k in (
                "id", "task_id", "error_type", "message", "stacktrace", "error_category", "is_retryable",
                "source", "code", "created_at", "error_screenshot_base64",
            )}],
            "total": 1,
        },
    },
    "GET /api/v1/task-errors/{error_id}": {
        "summary": "Detalhe de um erro (com contexto da task)",
        "description": "Um erro pelo id, no mesmo formato rico da busca geral. 404 se não existe.\n\n" + _BEARER,
        "example_response": _TASK_ERROR_RICH,
    },
})


# ----------------------------------------------------------------- Credentials
GUIDE.update({
    "GET /api/v1/credentials/": {
        "summary": "Lista credenciais (cofre de acessos dos robôs)",
        "description": (
            "Credenciais agrupam itens secretos (usuário, senha, token...) usados pelos robôs. A listagem não "
            "traz os itens. Query: `skip`, `limit` (1–500), `active`, `repository_id`.\n\n" + _BEARER
        ),
        "example_response": [_CREDENTIAL_EXAMPLE],
    },
    "POST /api/v1/credentials/": {
        "summary": "Cria uma credencial",
        "description": (
            "Cria o agrupador; os valores entram depois como itens. `label` é único no sistema (409); "
            "404 se o repositório não existe.\n\n" + _BEARER
        ),
        "example_request": {"repository_id": 3, "label": "SAP - usuário de serviço", "active": True},
        "example_response": _CREDENTIAL_EXAMPLE,
    },
    "GET /api/v1/credentials/{credential_id}": {
        "summary": "Detalhe da credencial com itens (mascarados)",
        "description": (
            "Credencial com seus itens. Os valores **não** vêm: só `masked_preview` (ex.: `se****lo`). "
            "Para o valor real use `/reveal`.\n\n" + _BEARER
        ),
        "example_response": {**_CREDENTIAL_EXAMPLE, "items": [_CREDENTIAL_ITEM_EXAMPLE]},
    },
    "PUT /api/v1/credentials/{credential_id}": {
        "summary": "Atualiza uma credencial",
        "description": "Atualização parcial (`label`, `repository_id`, `active`). 409 para label repetido.\n\n" + _BEARER,
        "example_request": {"label": "SAP - usuário de serviço (PRD)"},
        "example_response": {**_CREDENTIAL_EXAMPLE, "label": "SAP - usuário de serviço (PRD)"},
    },
    "DELETE /api/v1/credentials/{credential_id}": {
        "summary": "Desativa uma credencial (exclusão lógica)",
        "description": (
            "Marca `active=false`. Os itens continuam guardados, mas o worker passa a receber erro (400 "
            "\"Credencial está inativa\") ao tentar usá-la.\n\n" + _BEARER
        ),
        "example_response": {**_CREDENTIAL_EXAMPLE, "active": False},
    },
    "GET /api/v1/credentials/{credential_id}/items": {
        "summary": "Lista os itens da credencial (mascarados)",
        "description": (
            "Itens (chave, tipo e prévia mascarada). Os valores reais não são devolvidos. O filtro `active` "
            "é aceito mas hoje não altera o resultado.\n\n" + _BEARER
        ),
        "example_response": [_CREDENTIAL_ITEM_EXAMPLE],
    },
    "POST /api/v1/credentials/{credential_id}/items": {
        "summary": "Adiciona um item secreto à credencial",
        "description": (
            "Grava um par chave/valor. O valor é **criptografado** no banco e só uma prévia mascarada fica visível.\n\n"
            "- `key`: nome que o robô usa (ex.: `usuario`, `senha`); único na credencial (409).\n"
            "- `value_type`: `string`, `password`, `token`, `json` ou `secret` (padrão).\n\n" + _BEARER
        ),
        "example_request": {"key": "senha", "value_type": "password", "value": "senha-exemplo"},
        "example_response": _CREDENTIAL_ITEM_EXAMPLE,
    },
    "PUT /api/v1/credentials/{credential_id}/items/{item_id}": {
        "summary": "Atualiza um item da credencial",
        "description": (
            "Atualização parcial. Envie `value` para trocar o segredo (é recriptografado); omitido, o valor "
            "atual é mantido. 409 se a nova `key` já existe na credencial.\n\n" + _BEARER
        ),
        "example_request": {"value": "nova-senha-exemplo"},
        "example_response": {**_CREDENTIAL_ITEM_EXAMPLE, "masked_preview": "no****lo", "updated_at": _TS},
    },
    "DELETE /api/v1/credentials/{credential_id}/items/{item_id}": {
        "summary": "Apaga um item da credencial (definitivo)",
        "description": "Remove o item e seu valor criptografado. Devolve os dados do item removido.\n\n" + _BEARER,
        "example_response": _CREDENTIAL_ITEM_EXAMPLE,
    },
    "GET /api/v1/credentials/{credential_id}/items/{item_id}/reveal": {
        "summary": "Revela o valor real de um item (sensível)",
        "description": (
            "Descriptografa e devolve o valor em texto puro. **Rota sensível**: use só quando precisar de fato "
            "do valor e nunca grave a resposta em logs. 404 se o item não é desta credencial.\n\n" + _BEARER
        ),
        "example_response": {"id": 11, "credential_id": 4, "key": "senha", "value_type": "password", "value": "senha-exemplo"},
    },
})


# ------------------------------------------------------------------- Dashboard
_DASH_PERIOD = (
    "Query: `period` = `1d` (padrão), `7d`, `15d` ou `30d` (janela até agora), e filtros opcionais "
    "`repository_id`, `runner_id`, `bot_id`."
)

GUIDE.update({
    "GET /api/v1/dashboard/overview": {
        "summary": "Indicadores gerais do período",
        "description": (
            "Resumo da operação: máquinas online/ocupadas, tasks por resultado, taxa de sucesso, tempo médio "
            "na fila e de execução, tasks por hora e as tasks mais recentes.\n\n" + _DASH_PERIOD + "\n\n" + _BEARER
        ),
        "example_response": {
            "period": "1d",
            "date_from": "2026-10-20T13:45:00Z",
            "date_to": _TS,
            "summary": {
                "total_runners": 6, "online_runners": 5, "offline_runners": 1, "busy_runners": 2,
                "total_bots": 14, "total_tasks": 240, "success_tasks": 228, "error_tasks": 7,
                "running_tasks": 2, "queued_tasks": 3, "success_rate_percent": 97.0,
                "avg_queue_seconds": 18.4, "avg_execution_seconds": 245.1,
            },
            "tasks_per_hour": [{"hour_label": "13:00", "total_tasks": 12, "execution_seconds": 2900}],
            "recent_tasks": [
                {
                    "task_id": 42723, "automation_id": 12, "automation_name": "Estoque PO", "bot_id": 9,
                    "bot_name": "BOT_ETL_Estoque_PO", "runner_id": 5, "runner_name": "SRVRPA14",
                    "status": "finished", "created_at": "2026-10-21T13:39:58Z",
                    "started_at": "2026-10-21T13:40:02Z", "finished_at": "2026-10-21T13:45:14Z",
                    "queue_seconds": 4, "execution_duration_seconds": 312, "final_message": "120 itens processados.",
                }
            ],
        },
    },
    "GET /api/v1/dashboard/runners": {
        "summary": "Indicadores por máquina no período",
        "description": (
            "Uma linha por máquina: tasks por resultado, % de utilização, tempos médios, hora de pico, bots "
            "vinculados e a última execução.\n\n" + _DASH_PERIOD + "\n\n" + _BEARER
        ),
        "example_response": {
            "period": "7d",
            "date_from": "2026-10-14T13:45:00Z",
            "date_to": _TS,
            "items": [
                {
                    "runner_id": 5, "runner_name": "SRVRPA14", "runner_label": "RPA 14", "status": "online",
                    "enabled": True, "last_heartbeat": _TS, "linked_bots_count": 4,
                    "linked_bots": [{"bot_id": 9, "bot_name": "BOT_ETL_Estoque_PO"}],
                    "total_tasks": 410, "success_tasks": 401, "error_tasks": 6, "running_tasks": 0,
                    "queued_tasks": 1, "utilization_percent": 31.2, "avg_queue_seconds": 12.0,
                    "avg_execution_seconds": 230.5, "hottest_hour_label": "09:00", "hottest_hour_tasks": 22,
                    "last_execution": None,
                }
            ],
            "total": 1,
        },
    },
    "GET /api/v1/dashboard/bots": {
        "summary": "Indicadores por bot no período",
        "description": (
            "Uma linha por bot: tasks por resultado, taxa de sucesso, tempos médios, máquinas em que rodou e "
            "o status da última execução.\n\n" + _DASH_PERIOD + "\n\n" + _BEARER
        ),
        "example_response": {
            "period": "30d",
            "date_from": "2026-09-21T13:45:00Z",
            "date_to": _TS,
            "items": [
                {
                    "bot_id": 9, "bot_name": "BOT_ETL_Estoque_PO", "execution_mode": "background",
                    "current_version": "1.4.2", "active": True, "total_tasks": 620, "success_tasks": 611,
                    "error_tasks": 9, "running_tasks": 0, "queued_tasks": 0, "avg_queue_seconds": 10.2,
                    "avg_execution_seconds": 301.7, "success_rate_percent": 98.5,
                    "runners": [{"runner_id": 5, "runner_name": "SRVRPA14"}],
                    "last_execution_status": "finished", "last_execution_at": "2026-10-21T13:45:14Z",
                }
            ],
            "total": 1,
        },
    },
})


# --------------------------------------------------------------- Notifications
GUIDE.update({
    "GET /api/v1/notifications/channel": {
        "summary": "Configuração do aviso de falhas (canal HTTP)",
        "description": (
            "Há um único canal de notificação. Quando um agendamento **ativo** falha `failure_threshold` vezes "
            "seguidas (error/timeout), o orquestrador faz a requisição HTTP configurada (ex.: abrir chamado) e, "
            "conforme `pause_schedule` / `deactivate_automation`, pausa o agendamento e/ou desativa a automação.\n\n"
            "`body_template` e cabeçalhos aceitam variáveis `{{nome}}` (ver `/notifications/variables`). "
            "`pre_steps` são até 5 requisições anteriores (ex.: login) cujos valores extraídos viram variáveis.\n\n"
            "Se o canal ainda não existe, é criado desligado com um modelo padrão.\n\n" + _ADMIN
        ),
        "example_response": _NOTIFICATION_CHANNEL_EXAMPLE,
    },
    "PUT /api/v1/notifications/channel": {
        "summary": "Altera a configuração do aviso de falhas",
        "description": (
            "Atualização parcial do canal.\n\n"
            "- `method` do envio principal: `POST`, `PUT` ou `PATCH`; etapas aceitam também `GET`.\n"
            "- URLs precisam começar com `http://` ou `https://`.\n"
            "- `timeout_seconds` 1–120; `failure_threshold` 1–50; até 5 `pre_steps`.\n"
            "- `headers` e `pre_steps`, quando enviados, substituem os atuais.\n"
            "- Ativar (`enabled=true`) exige URL (400) e **zera a contagem**: só falhas a partir de agora notificam.\n\n"
            + _ADMIN
        ),
        "example_request": {
            "enabled": True,
            "url": "https://chamados.exemplo.com/api/tickets",
            "method": "POST",
            "headers": {"Content-Type": "application/json", "Authorization": "Bearer {{token}}"},
            "failure_threshold": 3,
            "pause_schedule": True,
            "deactivate_automation": False,
            "panel_base_url": "https://orkaflow.exemplo.com",
        },
        "example_response": _NOTIFICATION_CHANNEL_EXAMPLE,
    },
    "POST /api/v1/notifications/channel/test": {
        "summary": "Envia um teste com a configuração salva",
        "description": (
            "Executa as etapas e o envio principal usando a configuração **salva** e dados de exemplo "
            "(não pausa nada). Salve antes de testar. O resultado mostra a requisição (cabeçalhos sensíveis "
            "mascarados), o status HTTP e o começo da resposta, e fica registrado no histórico (`kind=test`). "
            "Sem corpo.\n\n" + _ADMIN
        ),
        "example_response": {
            "ok": True,
            "status_code": 201,
            "response_snippet": "{\"id\": 5531, \"status\": \"aberto\"}",
            "error": None,
            "request_preview": {
                "url": "https://chamados.exemplo.com/api/tickets",
                "method": "POST",
                "headers": {"Content-Type": "application/json", "Authorization": "***"},
                "body": "{\"titulo\": \"Falha na automação Automacao_Estoque_PO\"}",
            },
            "steps": [{"name": "Login", "ok": True, "status_code": 200}],
        },
    },
    "GET /api/v1/notifications/logs": {
        "summary": "Histórico de envios de notificação",
        "description": (
            "Últimos envios (reais e testes), do mais novo ao mais antigo. Query: `limit` (1–500, padrão 50). "
            "Mostra se deu certo, status HTTP, erro e se o agendamento foi pausado.\n\n" + _ADMIN
        ),
        "example_response": [
            {
                "id": 77,
                "created_at": "2026-10-21T12:41:30Z",
                "kind": "failure",
                "schedule_id": 18,
                "schedule_name": "Estoque PO - a cada hora",
                "automation_name": "Estoque PO",
                "task_ids": "42711,42715,42719",
                "ok": True,
                "status_code": 201,
                "error": None,
                "response_snippet": "{\"id\": 5531}",
                "paused_schedule": True,
            }
        ],
    },
    "GET /api/v1/notifications/logs/{log_id}": {
        "summary": "Detalhe de um envio de notificação",
        "description": (
            "Envio completo: requisição (cabeçalhos sensíveis mascarados), resultado de cada etapa e a resposta "
            "inteira. Valores extraídos nas etapas (ex.: token) aparecem como `***`. 404 se não existe.\n\n" + _ADMIN
        ),
        "example_response": {
            "id": 77,
            "created_at": "2026-10-21T12:41:30Z",
            "kind": "failure",
            "schedule_id": 18,
            "schedule_name": "Estoque PO - a cada hora",
            "automation_name": "Estoque PO",
            "task_ids": "42711,42715,42719",
            "ok": True,
            "status_code": 201,
            "error": None,
            "response_snippet": "{\"id\": 5531}",
            "paused_schedule": True,
            "request": {"url": "https://chamados.exemplo.com/api/tickets", "method": "POST", "headers": {"Authorization": "***"}},
            "steps": [{"name": "Login", "ok": True, "status_code": 200}],
            "response_body": "{\"id\": 5531, \"status\": \"aberto\"}",
        },
    },
    "GET /api/v1/notifications/variables": {
        "summary": "Variáveis disponíveis nos modelos de notificação",
        "description": (
            "Lista as variáveis que podem ser usadas como `{{nome}}` no corpo, cabeçalhos e URL do canal "
            "(ex.: `{{erro}}`, `{{automacao}}`, `{{tentativas}}`, `{{link_task}}`), com descrição e exemplo.\n\n" + _ADMIN
        ),
        "example_response": [
            {"name": "erro", "description": "Mensagem e trecho do erro da última falha", "example": "RuntimeError: Falha no login SAP"},
            {"name": "automacao", "description": "Nome da automação", "example": "Automacao_Estoque_PO"},
        ],
    },
})


# --------------------------------------------------------------- Env Variables
GUIDE.update({
    "GET /api/v1/env-variables/": {
        "summary": "Lista variáveis de ambiente dos robôs",
        "description": (
            "Variáveis injetadas no ambiente do processo do robô. Têm escopo e herança: "
            "`global` < `bot` < `automation` < `runner` (a mais específica vence).\n\n"
            "Query: `scope_type`, `scope_id`, `search` (parte do nome). Variáveis **secretas** voltam com "
            "`value: null`: o valor nunca sai pela API de administração.\n\n" + _ADMIN
        ),
        "example_response": [_ENV_VAR_EXAMPLE],
    },
    "POST /api/v1/env-variables/": {
        "summary": "Cria uma variável de ambiente",
        "description": (
            "- `name`: convertido para MAIÚSCULAS; letras, números e `_`, sem começar com número. Prefixo "
            "`ORKAFLOW_` e variáveis do sistema (PATH, TEMP, PYTHONPATH...) são proibidos (400).\n"
            "- `scope_type`: `global`, `bot`, `automation` ou `runner`; `scope_id` é o id do alvo (ignorado no global; "
            "404 se o alvo não existe).\n"
            "- `is_secret=true` criptografa o valor e exige valor não vazio.\n"
            "- 409 se o nome já existe no mesmo escopo.\n\n" + _ADMIN
        ),
        "example_request": {
            "name": "SAP_URL",
            "scope_type": "automation",
            "scope_id": 12,
            "value": "https://sap.exemplo.com",
            "is_secret": False,
            "description": "Endereço do SAP de produção",
            "active": True,
        },
        "example_response": _ENV_VAR_EXAMPLE,
    },
    "GET /api/v1/env-variables/effective": {
        "summary": "Valores finais com a herança aplicada",
        "description": (
            "Mostra o que o robô receberia: para cada nome, o valor vencedor, de qual escopo veio e quais "
            "escopos ele sobrescreveu (`overrides`). Só variáveis ativas.\n\n"
            "Query: `automation_id` (obrigatório) e `runner_id` (opcional, inclui o escopo da máquina). "
            "Secretas vêm sem valor. 404 se a automação não existe.\n\n" + _ADMIN
        ),
        "example_response": [
            {
                "name": "SAP_URL",
                "value": "https://sap.exemplo.com",
                "is_secret": False,
                "scope_type": "automation",
                "scope_id": 12,
                "scope_label": "Estoque de pedidos de compra",
                "overrides": [{"scope_type": "global", "scope_label": "Global"}],
            }
        ],
    },
    "POST /api/v1/env-variables/import": {
        "summary": "Importa várias variáveis de uma vez (ex.: de um .env)",
        "description": (
            "Cria até 500 variáveis num mesmo escopo, com as mesmas regras do cadastro individual.\n\n"
            "- Itens inválidos ou nomes repetidos no lote viram `error` sem impedir os demais.\n"
            "- Nomes que já existem no escopo são `skipped`, ou `updated` com `overwrite=true` (troca valor e `is_secret`).\n"
            "- O valor é gravado exatamente como enviado (sem remover espaços).\n\n"
            "A resposta traz os totais e o resultado de cada item.\n\n" + _ADMIN
        ),
        "example_request": {
            "scope_type": "bot",
            "scope_id": 9,
            "overwrite": False,
            "variables": [
                {"name": "SAP_URL", "value": "https://sap.exemplo.com"},
                {"name": "SAP_SENHA", "value": "senha-exemplo", "is_secret": True},
            ],
        },
        "example_response": {
            "created": 1,
            "updated": 0,
            "skipped": 1,
            "errors": 0,
            "results": [
                {"name": "SAP_URL", "status": "skipped", "message": "Já existe neste escopo (mantida)."},
                {"name": "SAP_SENHA", "status": "created", "message": None},
            ],
        },
    },
    "PUT /api/v1/env-variables/{var_id}": {
        "summary": "Atualiza uma variável de ambiente",
        "description": (
            "Atualização parcial; o escopo não muda.\n\n"
            "- `value` omitido ou `null` mantém o valor atual (útil para secretas, cujo valor não é exibido).\n"
            "- Tornar secreta (`is_secret=true`) criptografa o valor atual; deixar de ser secreta exige informar o novo `value` (400).\n"
            "- 409 se o novo nome já existe no escopo.\n\n" + _ADMIN
        ),
        "example_request": {"value": "https://sap-qas.exemplo.com", "active": True},
        "example_response": {**_ENV_VAR_EXAMPLE, "value": "https://sap-qas.exemplo.com"},
    },
    "DELETE /api/v1/env-variables/{var_id}": {
        "summary": "Apaga uma variável de ambiente (definitivo)",
        "description": (
            "Remove a variável; a próxima task já não a recebe (ou recebe a de um escopo mais geral). "
            "Para suspender sem apagar use `active=false`. Resposta 204 sem corpo.\n\n" + _ADMIN
        ),
    },
})


# ----------------------------------------------------------------- Runner Logs
GUIDE.update({
    "GET /api/v1/runner-logs/": {
        "summary": "Log bruto da máquina (worker e saída dos robôs)",
        "description": (
            "Linhas do `worker.log` enviadas pela máquina, incluindo a saída do console dos robôs "
            "(`source=bot`, com `task_id`). Guardadas por `retention_days` dias.\n\n"
            "Query:\n"
            "- `runner_id` (obrigatório).\n"
            "- `after_id`: só linhas depois deste id. Para acompanhar ao vivo, chame de novo passando o "
            "`last_id` da resposta anterior (polling).\n"
            "- `limit` (1–1000, padrão 300), `source` (`worker` ou `bot`), `task_id`, `level` (`INFO`, `ERROR`...), "
            "`search` (texto).\n\n"
            "404 se a máquina não existe.\n\n" + _BEARER
        ),
        "example_response": {
            "items": [
                {
                    "id": 1500231,
                    "runner_id": 5,
                    "logged_at": "2026-10-21T13:40:31Z",
                    "level": "INFO",
                    "source": "bot",
                    "task_id": 42723,
                    "message": "Lendo planilha de estoque...",
                }
            ],
            "last_id": 1500231,
            "retention_days": 7,
        },
    },
})


# ------------------------------------------------------------------ Integração
GUIDE.update({
    "GET /api/v1/integration/openapi": {
        "summary": "Documentação completa da API (OpenAPI + guia)",
        "description": (
            "OpenAPI 3.1 desta API com as explicações em português de cada rota no campo `x-orkaflow-guide` "
            "(e a descrição de cada grupo em `tags`). É a fonte da aba Integração e pode ser entregue a IAs ou "
            "geradores de cliente.\n\n" + _BEARER
        ),
        "example_response": {
            "openapi": "3.1.0",
            "info": {"title": "OrkaFlow", "version": "1.0.0"},
            "paths": {"/api/v1/tasks/": {"get": {"summary": "Lista tasks (execuções) com filtros", "x-orkaflow-guide": {}}}},
            "tags": [{"name": "Tasks", "description": "..."}],
        },
    },
    "GET /api/v1/integration/mcp-info": {
        "summary": "Endereço do servidor MCP e ferramentas para IA",
        "description": (
            "Dados para configurar uma IA (Claude, etc.) via MCP: se o MCP está ligado (`enabled`), a URL "
            "pública do endpoint (`url`, termina em `/mcp`), a base da API REST e o catálogo de ferramentas "
            "(`kind`: `consulta` ou `ação`).\n\n" + _BEARER
        ),
        "example_response": {
            "enabled": True,
            "public_url_configured": False,
            "url": "https://orkaflow.exemplo.com/mcp",
            "api_base_url": "https://orkaflow.exemplo.com/api/v1",
            "tools": [
                {
                    "name": "listar_automacoes",
                    "title": "Listar automações",
                    "description": "Lista as automações cadastradas (por padrão só as ativas), com o bot de cada uma.",
                    "input_schema": {"type": "object", "properties": {"busca": {"type": "string"}}},
                    "kind": "consulta",
                }
            ],
        },
    },
})


# ------------------------------------------------------------------------- MCP
GUIDE.update({
    "POST /mcp": {
        "summary": "Endpoint MCP (JSON-RPC 2.0) para IAs",
        "description": (
            "Servidor MCP (Model Context Protocol, transporte HTTP \"streamable\" sem estado). Fica fora do "
            "`/api/v1`. Autenticação: `Authorization: Bearer ork_...` (token de integração; o de login também "
            "funciona). Sem token válido: 401.\n\n"
            "Métodos: `initialize`, `ping`, `tools/list`, `tools/call` e `notifications/*` (respondidas com 202). "
            "Aceita uma mensagem ou um lote (lista). Erros de negócio de uma ferramenta voltam como resultado "
            "com `isError: true` para a IA corrigir a chamada.\n\n"
            "As ferramentas agem com as permissões do dono do token (consultas, criar/parar task, "
            "pausar/reativar agendamento, criar versão de bot). Normalmente quem chama esta rota é o cliente "
            "MCP da IA, não você."
        ),
        "example_request": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "ultimas_execucoes", "arguments": {"automacao": "Estoque PO"}},
        },
        "example_response": {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": "{\"automacao\": \"Estoque PO\", \"status\": \"finished\"}"}],
                "structuredContent": {"automacao": "Estoque PO", "status": "finished"},
                "isError": False,
            },
        },
    },
    "GET /mcp": {
        "summary": "Sem stream SSE (sempre 405)",
        "description": (
            "O servidor MCP é sem estado e não abre stream SSE: responde **405** com `Allow: POST`. Clientes MCP "
            "entendem isso e seguem só com POST."
        ),
    },
    "DELETE /mcp": {
        "summary": "Sem sessão para encerrar (sempre 405)",
        "description": (
            "Não há sessão MCP para encerrar: responde **405** com `Allow: POST`. Existe só para clientes que "
            "tentam fechar a sessão ao sair."
        ),
    },
})


# ---------------------------------------------------------------------- Worker
GUIDE.update({
    "POST /api/v1/worker/registration/": {
        "summary": "Registra (ou re-registra) a máquina e gera o token",
        "description": (
            _WORKER.replace("autentica pelo `uuid` e `token` do runner enviados no corpo, **não** por Bearer",
                            "é a única rota do worker **sem autenticação**: é ela que gera o token")
            + "Chamado pelo instalador (`configurar_worker.bat`). Faz *upsert*: procura a máquina pelo `uuid`, "
            "depois pelo `name`; se achar, atualiza dados, troca o `uuid`, **gera um token novo** (o anterior "
            "deixa de valer) e reativa (inclusive se tinha sido removida); senão cria.\n\n"
            "Guarde o `token` devolvido: o worker o usa em todas as outras chamadas."
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "name": "SRVRPA14",
            "label": "RPA 14",
            "host_name": "SRVRPA14",
            "ip": "10.0.0.14",
            "os_name": "Windows",
            "os_version": "10.0.20348",
            "cpu_arch": "AMD64",
            "memory_total": 17179869184,
            "access_remote": True,
        },
        "example_response": {
            "runner_id": 5,
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "name": "SRVRPA14",
            "status": "online",
            "enabled": True,
            "token": "token-do-runner-exemplo",
            "polling_interval": 15,
            "max_concurrency": 1,
        },
    },
    "POST /api/v1/worker/auth/login": {
        "summary": "Valida uuid + token do runner",
        "description": _WORKER + "Confere as credenciais do runner e devolve id, status e se está habilitado." + _WORKER_AUTH_ERRORS,
        "example_request": {"uuid": "6f1c2a9e-0000-4000-8000-000000000005", "token": "token-do-runner-exemplo"},
        "example_response": {
            "authenticated": True,
            "runner_id": 5,
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "status": "online",
            "enabled": True,
        },
    },
    "POST /api/v1/worker/heartbeat/": {
        "summary": "Sinal de vida da máquina",
        "description": (
            _WORKER + "Enviado periodicamente. Atualiza `last_heartbeat` (e o IP, se informado) e volta a máquina "
            "para `online` se estava `offline`. `running_tasks` é só informativo: o status `busy` é calculado "
            "pelas tasks no banco. Sem heartbeat por ~3 minutos a máquina vira `offline`." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "ip": "10.0.0.14",
            "running_tasks": 1,
        },
        "example_response": {"ok": True, "runner_id": 5, "status": "busy", "server_time": _TS, "running_tasks": 1},
    },
    "POST /api/v1/worker/tasks/next": {
        "summary": "Procura a próxima task que a máquina pode assumir",
        "description": (
            _WORKER + "Devolve o primeiro candidato realmente assumível do modo pedido (`execution_mode`: "
            "`background` ou `foreground`), respeitando capacidade da máquina, vínculos e locks. Não reserva "
            "nada: em seguida o worker chama `/claim`. `found=false` quando não há task, a máquina está "
            "desabilitada, em manutenção ou offline.\n\n"
            "Os parâmetros da task vêm resolvidos (inclusive os ligados a credenciais)." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "execution_mode": "background",
        },
        "example_response": {
            "found": True,
            "task_id": 42730,
            "automation_id": 12,
            "bot_id": 9,
            "bot_version_id": 87,
            "execution_mode": "background",
            "priority": 5,
            "status": "waiting",
            "correlation_id": None,
            "queue_name": None,
            "requested_start_at": None,
            "timeout_seconds": 3600,
            "inactivity_timeout_seconds": None,
            "parameters": [
                {
                    "parameter_name": "runtime_parameters_json",
                    "parameter_value": "{\"filial\": \"010\"}",
                    "is_secret": False,
                    "resolved_from_credential_item_id": None,
                }
            ],
        },
    },
    "POST /api/v1/worker/tasks/active": {
        "summary": "Tasks abertas atribuídas a esta máquina",
        "description": (
            _WORKER + "Lista as tasks não finalizadas vinculadas ao runner (com a chave de lock), usado pelo worker "
            "para reconciliar o que está rodando localmente." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {"uuid": "6f1c2a9e-0000-4000-8000-000000000005", "token": "token-do-runner-exemplo"},
        "example_response": {
            "items": [{"id": 42730, "automation_id": 12, "runner_id": 5, "status": "running", "lock_key": "automation:12"}],
            "total": 1,
        },
    },
    "POST /api/v1/worker/tasks/release-startup-locks": {
        "summary": "Recuperação ao reiniciar o worker",
        "description": (
            _WORKER + "Chamado quando o worker sobe. Tudo que estava `ready`/`running`/`stop_requested` nesta máquina "
            "não existe mais no processo local, então essas tasks viram **`error`** (\"worker foi reiniciado\", "
            "com TaskError `WORKER_RESTARTED` marcado como reprocessável) e os locks da máquina são liberados. "
            "A máquina não é bloqueada." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {"uuid": "6f1c2a9e-0000-4000-8000-000000000005", "token": "token-do-runner-exemplo"},
        "example_response": {
            "message": "Recuperação inicial do worker concluída com sucesso.",
            "runner_id": 5,
            "tasks_finalized": 1,
            "task_locks_released": 1,
            "runner_locks_released": 0,
        },
    },
    "POST /api/v1/worker/tasks/{task_id}/claim": {
        "summary": "Assume (reserva) uma task para a máquina",
        "description": (
            _WORKER + "Reserva atômica: a task passa de `waiting` para `ready`, vinculada a este runner, e os locks "
            "são criados. Repetir o claim da mesma task pela mesma máquina é idempotente.\n\n"
            "Recusas (400/403): task fora de `waiting`, já de outra máquina, automação não vinculada à máquina, "
            "outra task da automação aberta, grupo exclusivo ocupado, máquina em manutenção ou sem capacidade "
            "(N BACKGROUND + 1 FOREGROUND por máquina)." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {"uuid": "6f1c2a9e-0000-4000-8000-000000000005", "token": "token-do-runner-exemplo"},
        "example_response": {"task_id": 42730, "runner_id": 5, "status": "ready"},
    },
    "POST /api/v1/worker/tasks/{task_id}/status": {
        "summary": "Consulta o status da task (e se deve parar)",
        "description": (
            _WORKER + "O worker consulta durante a execução. `stop_requested=true` quando o painel pediu parada ou "
            "quando a task já foi finalizada pelo backend (timeout, cancelamento, parada forçada): nesse caso o "
            "worker deve encerrar o processo do robô. 403 se a task não pertence a esta máquina." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {"uuid": "6f1c2a9e-0000-4000-8000-000000000005", "token": "token-do-runner-exemplo"},
        "example_response": {"task_id": 42730, "status": "stop_requested", "stop_requested": True, "runner_id": 5, "exists": True},
    },
    "PATCH /api/v1/worker/tasks/{task_id}/status": {
        "summary": "Informa progresso ou mudança de status da task",
        "description": (
            _WORKER + "Atualiza status e contadores. Aceita `ready`, `running`, `stop_requested` (progresso) e "
            "`finished`, `error`, `canceled`, `timeout` (finais).\n\n"
            "Regras: precisa do claim antes (task em `waiting` → 400); `stop_requested` não volta para "
            "`running`; `running` não volta para `ready`; status final não muda mais (a chamada é ignorada e "
            "registrada em log). A primeira vez em `running` grava `started_at`. Ao virar `finished`, dispara os "
            "gatilhos de sucesso da automação." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "status": "running",
            "items_processed": 40,
            "items_failed": 0,
        },
        "example_response": {**_TASK_EXAMPLE, "status": "running", "finished_at": None, "items_processed": 40},
    },
    "POST /api/v1/worker/tasks/{task_id}/env": {
        "summary": "Variáveis de ambiente finais da task (com segredos)",
        "description": (
            _WORKER + "Entrega as variáveis de ambiente com a herança aplicada (global < bot < automação < máquina) "
            "**com os valores secretos em texto puro**, para o worker injetar no processo do robô. "
            "`secret_names` lista quais são secretas, para o worker mascarar nos logs. 403 se a task não é "
            "desta máquina." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {"uuid": "6f1c2a9e-0000-4000-8000-000000000005", "token": "token-do-runner-exemplo"},
        "example_response": {
            "variables": {"SAP_URL": "https://sap.exemplo.com", "SAP_SENHA": "senha-exemplo"},
            "secret_names": ["SAP_SENHA"],
        },
    },
    "POST /api/v1/worker/tasks/{task_id}/finish": {
        "summary": "Finaliza a task com o resultado",
        "description": (
            _WORKER + "Encerra a execução com `finished`, `error`, `canceled` ou `timeout` (outros → 400). Grava "
            "`final_message`, `result_json` e contadores (nulos não sobrescrevem os já gravados), libera os locks "
            "e, em `finished`, cria as tasks dos gatilhos de sucesso. `error` sem mensagem recebe uma mensagem "
            "padrão. Se a task já estava finalizada, a chamada é ignorada (200)." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "status": "finished",
            "final_message": "120 itens processados.",
            "result_json": "{\"arquivo\": \"estoque_20261021.xlsx\"}",
            "items_processed": 120,
            "items_failed": 0,
        },
        "example_response": {**_TASK_EXAMPLE, "result_json": "{\"arquivo\": \"estoque_20261021.xlsx\"}"},
    },
    "POST /api/v1/worker/tasks/{task_id}/logs": {
        "summary": "Envia uma linha de log da task",
        "description": (
            _WORKER + "Registra um evento da execução (aparece em *Task Logs*). `level`: `debug`, `info`, `warning`, "
            "`error`, `critical`. Também conta como atividade da task (evita timeout por inatividade). 403 se a "
            "task não é desta máquina." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "level": "info",
            "message": "Login no SAP realizado.",
            "source": "worker",
            "sequence_number": 3,
        },
        "example_response": {"message": "Log registrado com sucesso.", "task_id": 42730},
    },
    "POST /api/v1/worker/tasks/{task_id}/errors": {
        "summary": "Registra um erro da task",
        "description": (
            _WORKER + "Grava o erro detalhado (tipo, mensagem, traceback, categoria, código e, opcionalmente, o print "
            "da tela em base64). Não muda o status da task: para finalizar use `/finish`. Aparece em *Task Errors*."
            + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "error_type": "RuntimeError",
            "message": "Falha no login SAP: senha incorreta",
            "stacktrace": "Traceback (most recent call last): ...",
            "error_category": "business",
            "is_retryable": False,
            "source": "worker",
            "code": "SAP_LOGIN",
        },
        "example_response": {"message": "Erro registrado com sucesso.", "task_id": 42730},
    },
    "POST /api/v1/worker/sync": {
        "summary": "Sincroniza configuração e bots da máquina",
        "description": (
            _WORKER + "Devolve a configuração (polling, concorrência) e a lista de bots que a máquina deve ter "
            "instalados: bots ativos de automações ativas vinculadas a ela, cada um com a versão em uso (commit, "
            "branch) e se deve se auto-atualizar (`auto_update` é desligado quando há versão fixada por Release). "
            "Também atualiza host/IP e marca a máquina como viva." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "host_name": "SRVRPA14",
            "ip": "10.0.0.14",
        },
        "example_response": {
            "runner_id": 5,
            "status": "online",
            "enabled": True,
            "polling_interval": 15,
            "max_concurrency": 2,
            "message": "sync successful",
            "bots": [
                {
                    "bot_id": 9,
                    "bot_version_id": 87,
                    "name": "BOT_ETL_Estoque_PO",
                    "technology": "python",
                    "source_type": "git",
                    "source_url": "https://git.exemplo.com/rpa/bot-estoque-po.git",
                    "entrypoint": "main.py",
                    "version": "1.4.2",
                    "commit_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
                    "branch": "main",
                    "execution_mode": "background",
                    "auto_update": False,
                }
            ],
        },
    },
    "POST /api/v1/worker/bot-versions/auto": {
        "summary": "Cria versão automática a partir de um commit",
        "description": (
            _WORKER + "Usado quando o worker detecta um commit novo de um bot com auto-update. Se já existe versão com "
            "o mesmo `commit_hash`, devolve ela; senão cria a próxima versão (incrementa o patch, ex.: 1.4.2 → 1.4.3) "
            "com `storage_type=git`. 401 se o runner não autentica; 409 se o bot está inativo."
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "bot_id": 9,
            "commit_hash": "b2c3d4e5f60718293a4b5c6d7e8f901234567890",
            "branch": "main",
        },
        "example_response": {
            **_BOT_VERSION_EXAMPLE,
            "id": 88,
            "version": "1.4.3",
            "commit_hash": "b2c3d4e5f60718293a4b5c6d7e8f901234567890",
            "changelog": None,
            "commit_author": None,
            "committed_at": None,
            "created_by": 1,
        },
    },
    "POST /api/v1/worker/credentials/{credential_id}/resolve": {
        "summary": "Entrega os valores de uma credencial ao robô",
        "description": (
            _WORKER + "Descriptografa os itens da credencial e devolve em `dados_acesso` (chave → valor em texto puro). "
            "`keys` opcional limita aos itens pedidos. 404 se a credencial não existe; 400 se está inativa."
            + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "keys": ["usuario", "senha"],
        },
        "example_response": {"dados_acesso": {"usuario": "robo.sap", "senha": "senha-exemplo"}},
    },
    "POST /api/v1/worker/tasks/{task_id}/telemetry": {
        "summary": "Envia métricas de recurso da execução",
        "description": (
            _WORKER + "Grava (ou substitui) a telemetria da task: duração, CPU e memória (média/pico), disco, rede, "
            "código de saída. Aparece em `telemetry` no detalhe da task. Uma telemetria por task." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "captured_at": "2026-10-21T13:45:14Z",
            "execution_started_at": "2026-10-21T13:40:02Z",
            "execution_finished_at": "2026-10-21T13:45:14Z",
            "duration_seconds": 312.4,
            "cpu_percent_avg": 18.5,
            "cpu_percent_peak": 64.0,
            "memory_used_mb_peak": 5120.0,
            "process_memory_mb_peak": 410.2,
            "exit_code": 0,
            "telemetry_status": "ok",
        },
        "example_response": {"message": "Telemetria registrada com sucesso.", "task_id": 42723},
    },
    "POST /api/v1/worker/parameters/{key}": {
        "summary": "Lê um parâmetro global do worker",
        "description": (
            _WORKER + "Devolve parâmetros que o worker precisa saber do servidor (hoje só `worker-url`: endereço do "
            "repositório do próprio worker, usado para atualização). 404 para chave desconhecida." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {"uuid": "6f1c2a9e-0000-4000-8000-000000000005", "token": "token-do-runner-exemplo"},
        "example_response": {"key": "worker-url", "value": "https://git.exemplo.com/rpa/worker.git"},
    },
    "POST /api/v1/worker/screenshot/": {
        "summary": "Envia o print de tela atual da máquina",
        "description": (
            _WORKER + "Recebe a captura de tela em base64 (`image_base64`) e guarda como a última da máquina "
            "(substitui a anterior). O painel a exibe via `GET /api/v1/runners/{runner_id}/screenshot`. 400 se o "
            "base64 é inválido." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            "content_type": "image/png",
        },
        "example_response": {"message": "Screenshot do runner atualizado com sucesso.", "runner_id": 5, "last_screenshot_at": _TS},
    },
    "POST /api/v1/worker/runtime-events/": {
        "summary": "Registra um evento operacional do worker",
        "description": (
            _WORKER + "Eventos de funcionamento do worker, com ou sem task: `sync_failed`, `bot_install_failed`, "
            "`bot_auto_update_failed`, `credential_resolve_failed`, etc. `task_id`, `automation_id` e `bot_id` são "
            "opcionais; referências inexistentes não derrubam o evento (vão para `extra`). Campos longos são "
            "truncados em vez de recusados." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "event_type": "bot_install_failed",
            "bot_id": 9,
            "reason": "pip_install_error",
            "message": "Falha ao instalar requirements.txt",
            "extra": {"exit_code": 1},
        },
        "example_response": {"message": "Evento de runtime registrado com sucesso.", "event_id": 3021, "runner_id": 5},
    },
    "POST /api/v1/worker/runner-logs/": {
        "summary": "Envia um lote de linhas do worker.log",
        "description": (
            _WORKER + "Recebe até 500 linhas por lote (cada uma com `logged_at`, `level`, `message`; mensagens até "
            "4000 caracteres). Linhas no formato `[BOT][task_id=123] ...` são classificadas como saída do robô "
            "daquela task. Consultadas em `GET /api/v1/runner-logs/`." + _WORKER_AUTH_ERRORS
        ),
        "example_request": {
            "uuid": "6f1c2a9e-0000-4000-8000-000000000005",
            "token": "token-do-runner-exemplo",
            "lines": [
                {"logged_at": "2026-10-21T13:40:31Z", "level": "INFO", "message": "[BOT][task_id=42723] Lendo planilha de estoque..."},
                {"logged_at": "2026-10-21T13:40:32Z", "level": "INFO", "message": "Heartbeat enviado."},
            ],
        },
        "example_response": {"accepted": 2},
    },
})


# ------------------------------------------------------------------- Grupos
TAG_GUIDE.update({
    "Auth": (
        "Login de usuários do painel. Rotas protegidas usam `Authorization: Bearer <token>`, onde o token pode "
        "ser o `access_token` do `POST /api/v1/auth/login` (curta duração, renovado com `/auth/refresh`) ou um "
        "**token de integração `ork_...`**, gerado na tela de Usuários/Perfil ou em `POST /api/v1/api-tokens/`. "
        "Para scripts, sistemas e IAs prefira o token de integração: ele vale com as permissões do usuário dono "
        "e pode ser revogado a qualquer momento."
    ),
    "Public Downloads": (
        "Arquivos públicos de apoio à instalação do worker nas máquinas (ex.: `nssm.exe`). Não exigem token e "
        "só servem nomes da lista permitida."
    ),
    "Users": (
        "Usuários do painel. Qualquer usuário logado pode listar e consultar; criar, editar, bloquear e excluir "
        "exige administrador. Excluir é lógico (desativa) e bloqueia também os tokens de integração do usuário."
    ),
    "Tokens de integração": (
        "Tokens pessoais `ork_...` para MCP, IAs e scripts, usados como `Authorization: Bearer ork_...`. Valem "
        "com as permissões do usuário dono, aparecem completos só uma vez (na criação) e podem expirar ou ser "
        "revogados. Cada usuário gerencia os seus; administradores gerenciam os de qualquer usuário."
    ),
    "Profiles": (
        "Perfis de acesso: conjuntos de permissões (`modulo:acao`) atribuídos aos usuários. Leitura para "
        "qualquer usuário logado; alterações só para administradores. Desativar um perfil bloqueia todos os "
        "usuários dele."
    ),
    "Permissions": (
        "Catálogo das permissões que podem ser colocadas nos perfis. A permissão `users:admin` (ou a role "
        "legada `admin`) é a que libera as rotas de administrador."
    ),
    "Repositories": (
        "Repositórios agrupam bots, automações e credenciais de uma área. Excluir é lógico (desativa) e não "
        "afeta os itens vinculados."
    ),
    "Runners": (
        "Runners são as máquinas com o worker do OrkaFlow instalado, que executam os robôs. Aqui você consulta "
        "status, uso, último print de tela e ajusta a configuração (concorrência, polling, manutenção). As "
        "máquinas normalmente se cadastram sozinhas pelo worker."
    ),
    "Bots": (
        "Bots são os robôs (código em um repositório Git) que as automações executam. O cadastro define como o "
        "worker instala e roda o robô (entrypoint, requirements, modo background/foreground, timeout padrão)."
    ),
    "Bot Versions": (
        "Versões de cada bot (commit/branch do Git). Por padrão as tasks usam a versão mais nova; com Release "
        "é possível fixar uma versão antiga (rollback) e depois voltar a seguir a mais nova. `git-preview` "
        "compara com o Git sem gravar nada."
    ),
    "Automations": (
        "Automação = um bot com parâmetros padrão e as máquinas onde pode rodar; é o que gera tasks. Também "
        "define grupos exclusivos (não rodar em paralelo com outras) e gatilhos de sucesso (disparar outra "
        "automação quando esta termina bem). Sem máquina vinculada, nenhuma task executa."
    ),
    "Automation Health": (
        "Semáforo de monitoramento por automação: última execução, se está atrasada em relação ao agendamento "
        "e se está rodando agora. Bom ponto de partida para alertas e painéis externos."
    ),
    "Schedules": (
        "Agendamentos criam tasks automaticamente por expressão cron ou calendário (a cada N minutos/horas/dias "
        "etc.), com políticas para quando já há execução em andamento ou o horário foi perdido. Podem ser "
        "pausados e reativados (também são pausados automaticamente pelas notificações de falha)."
    ),
    "Tasks": (
        "Task é uma execução de uma automação. Status: `waiting`/`ready` (na fila), `scheduled` (aguardando "
        "horário), `running`, `stop_requested` (parada pedida), `finished` (sucesso), `error`/`timeout`/"
        "`forced_stop` (falha) e `canceled`. Para disparar um robô por integração use `POST /api/v1/tasks/` e "
        "acompanhe com `GET /api/v1/tasks/{task_id}` até um status final."
    ),
    "Task Logs": (
        "Eventos estruturados de cada execução, enviados pelo worker e pelo orquestrador, com nível, origem e "
        "código do evento. A saída bruta do console do robô fica em Runner Logs."
    ),
    "Task Errors": (
        "Erros detalhados das execuções (tipo, mensagem, traceback, categoria, código e print da tela). A busca "
        "geral já traz o contexto da task, automação, bot, versão e máquina, útil para relatórios de falhas."
    ),
    "Credentials": (
        "Cofre de acessos usados pelos robôs (usuários, senhas, tokens). Os valores ficam criptografados e as "
        "listagens mostram só uma prévia mascarada; o valor real sai apenas pela rota `reveal` e para o worker "
        "durante a execução."
    ),
    "Dashboard": (
        "Indicadores agregados para painéis: visão geral, por máquina e por bot, em janelas de 1, 7, 15 ou 30 "
        "dias, com filtros por repositório, máquina e bot."
    ),
    "Notifications": (
        "Aviso automático de falhas: quando um agendamento ativo falha N vezes seguidas, o OrkaFlow chama uma "
        "URL configurável (ex.: abrir chamado), com corpo e cabeçalhos montados por variáveis, e pode pausar o "
        "agendamento. Todas as rotas exigem administrador."
    ),
    "Env Variables": (
        "Variáveis de ambiente injetadas no processo dos robôs, com herança global < bot < automação < máquina "
        "(a mais específica vence). Valores secretos são criptografados e nunca saem por estas rotas. Todas as "
        "rotas exigem administrador."
    ),
    "Runner Logs": (
        "Log bruto das máquinas (worker.log), incluindo a saída do console dos robôs por task. Suporta polling "
        "incremental com `after_id` para acompanhar ao vivo."
    ),
    "Integração": (
        "Recursos para quem integra com o OrkaFlow: esta documentação em formato OpenAPI (com as explicações em "
        "português) e os dados para conectar uma IA pelo MCP. Exige estar autenticado."
    ),
    "MCP": (
        "Servidor MCP (Model Context Protocol) em `/mcp` para IAs como o Claude consultarem e operarem o "
        "OrkaFlow com ferramentas prontas (listar automações, ver erros, criar/parar task, pausar agendamento...). "
        "Autentique com `Authorization: Bearer ork_...`; as ações respeitam as permissões do dono do token."
    ),
    "Worker Registration": (
        "Registro da máquina pelo instalador do worker; gera o `uuid`/token usados nas demais rotas Worker. "
        "Uso interno do agente: integrações normalmente não usam."
    ),
    "Worker Auth": (
        "Validação das credenciais do runner (`uuid` + `token` no corpo, não Bearer). Uso interno do worker."
    ),
    "Worker Heartbeat": (
        "Sinal de vida periódico das máquinas, que mantém o status online/offline. Uso interno do worker "
        "(autenticação por `uuid` + `token` no corpo)."
    ),
    "Worker Tasks": (
        "Ciclo de execução visto pela máquina: buscar a próxima task, assumir (claim), informar progresso, "
        "consultar se deve parar, obter variáveis de ambiente e finalizar. Uso interno do worker, autenticado por "
        "`uuid` + `token` do runner no corpo; integrações devem usar as rotas de Tasks."
    ),
    "Worker Logs": (
        "Envio de logs estruturados da task pela máquina. Uso interno do worker (`uuid` + `token` no corpo)."
    ),
    "Worker Errors": (
        "Envio de erros detalhados da task pela máquina. Uso interno do worker (`uuid` + `token` no corpo)."
    ),
    "Worker Sync": (
        "Sincronização da máquina (configuração e bots a instalar) e criação automática de versões por commit. "
        "Uso interno do worker (`uuid` + `token` no corpo)."
    ),
    "Worker Credentials": (
        "Entrega dos valores de credenciais ao robô durante a execução. Uso interno do worker (`uuid` + `token` "
        "no corpo); devolve segredos em texto puro."
    ),
    "Worker Telemetry": (
        "Métricas de CPU, memória, disco e rede de cada execução, enviadas pela máquina. Uso interno do worker."
    ),
    "Worker Parameters": (
        "Parâmetros globais que o worker lê do servidor (ex.: endereço do próprio worker para atualização). "
        "Uso interno do worker."
    ),
    "Worker Screenshot": (
        "Envio do print de tela atual da máquina, exibido no painel. Uso interno do worker."
    ),
    "Worker Runtime Events": (
        "Eventos operacionais do worker (falha de sync, de instalação de bot, de credencial...). Uso interno do "
        "worker (`uuid` + `token` no corpo)."
    ),
    "Worker Runner Logs": (
        "Envio em lote das linhas do worker.log da máquina para a tela de Logs. Uso interno do worker."
    ),
})
