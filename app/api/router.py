# app/api/router.py

# APIRouter é o agrupador de rotas do FastAPI.
# Aqui vamos montar o roteamento principal da aplicação.
from fastapi import APIRouter, Depends

# Dependência que valida o token JWT do usuário autenticado.
# Tudo que estiver no router protegido vai exigir Bearer Token.
from app.api.deps import get_current_user

# =========================
# IMPORTAÇÃO DOS ROUTERS
# =========================

# Router público de health check.
# Normalmente fica aberto para monitoramento da aplicação.
from app.api.v1.health import router as health_router

# Router de autenticação do usuário.
# Login e refresh precisam ficar públicos.
from app.api.v1.auth import router as auth_router

# Routers protegidos por autenticação de usuário.
from app.api.v1.users import router as users_router
from app.api.v1.repositories import router as repositories_router
from app.api.v1.runners import router as runners_router
from app.api.v1.bots import router as bots_router
from app.api.v1.bot_versions import router as bot_versions_router
from app.api.v1.automations import router as automations_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.task_logs import router as task_logs_router
from app.api.v1.task_errors import router as task_errors_router
from app.api.v1.credentials import router as credentials_router

# Routers do worker.
# Aqui eu mantive separado porque, no seu projeto,
# worker pode ter autenticação própria e fluxo próprio.
from app.api.v1.worker_registration import router as worker_registration_router
from app.api.v1.worker_auth import router as worker_auth_router
from app.api.v1.worker_heartbeat import router as worker_heartbeat_router
from app.api.v1.worker_tasks import router as worker_tasks_router
from app.api.v1.worker_logs import router as worker_logs_router
from app.api.v1.worker_errors import router as worker_errors_router
from app.api.v1.worker_sync import router as worker_sync_router


# ==========================================================
# ROUTER PRINCIPAL DA API
# ==========================================================
# Esse é o router raiz que será incluído no main.py.
api_router = APIRouter()


# ==========================================================
# ROUTER PÚBLICO
# ==========================================================
# Esse router agrupa endpoints que NÃO exigem token de usuário.
# Exemplos:
# - health
# - login
# - refresh token
public_router = APIRouter()

# Health check da aplicação.
# Deve continuar público para testes, monitoramento e uptime checks.
public_router.include_router(health_router)

# Rotas de autenticação.
# Login e refresh precisam ser públicos por definição,
# senão o usuário não consegue obter token.
public_router.include_router(auth_router)


# ==========================================================
# ROUTER PRIVADO DE USUÁRIO
# ==========================================================
# Tudo que for incluído aqui passa obrigatoriamente por get_current_user.
# Ou seja:
# - exige header Authorization: Bearer <token>
# - valida token
# - carrega usuário
# - bloqueia usuário inativo
protected_router = APIRouter(
    dependencies=[Depends(get_current_user)]
)

# =========================
# ROTAS DE USUÁRIO
# =========================

# CRUD / operações de usuários.
protected_router.include_router(users_router)

# CRUD / operações de repositórios.
protected_router.include_router(repositories_router)

# CRUD / operações de runners.
protected_router.include_router(runners_router)

# CRUD / operações de bots.
protected_router.include_router(bots_router)

# CRUD / operações de versões dos bots.
protected_router.include_router(bot_versions_router)

# CRUD / operações de automações.
protected_router.include_router(automations_router)

# CRUD / operações de agendas/schedules.
protected_router.include_router(schedules_router)

# CRUD / operações de tasks.
protected_router.include_router(tasks_router)

# Consulta / leitura de logs de task.
protected_router.include_router(task_logs_router)

# Consulta / leitura de erros de task.
protected_router.include_router(task_errors_router)

# CRUD / operações de credenciais.
protected_router.include_router(credentials_router)


# ==========================================================
# ROUTER DO WORKER
# ==========================================================
# Mantido separado do router de usuário.
# Isso é importante porque o worker pode usar autenticação própria,
# como token de máquina, runner token, handshake de registro, etc.
#
# Se no seu projeto essas rotas do worker ainda estiverem abertas,
# você depois protege cada uma com a dependência correta do worker,
# e não com get_current_user.
worker_router = APIRouter()

# Registro inicial do worker/máquina.
worker_router.include_router(worker_registration_router)

# Autenticação específica do worker.
worker_router.include_router(worker_auth_router)

# Heartbeat do worker para informar que está online.
worker_router.include_router(worker_heartbeat_router)

# Rotas para buscar tasks destinadas ao worker.
worker_router.include_router(worker_tasks_router)

# Rotas para envio de logs do worker.
worker_router.include_router(worker_logs_router)

# Rotas para envio de erros do worker.
worker_router.include_router(worker_errors_router)

# Rotas de sincronização do worker.
worker_router.include_router(worker_sync_router)


# ==========================================================
# INCLUSÃO FINAL DOS BLOCOS NO ROUTER PRINCIPAL
# ==========================================================
# Ordem lógica:
# 1. público
# 2. privado de usuário
# 3. worker
api_router.include_router(public_router)
api_router.include_router(protected_router)
api_router.include_router(worker_router)
