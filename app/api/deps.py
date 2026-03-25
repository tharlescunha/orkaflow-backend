# app/api/deps.py

# Depends:
# usado pelo FastAPI para injetar dependências automaticamente nas rotas.
from fastapi import Depends

# HTTPAuthorizationCredentials:
# representa o conteúdo do header Authorization já interpretado pelo FastAPI.
#
# HTTPBearer:
# cria o esquema de autenticação Bearer para uso nas rotas
# e também ajuda a documentar isso no Swagger.
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Session:
# sessão do SQLAlchemy para acessar o banco de dados.
from sqlalchemy.orm import Session

# get_db:
# dependência que entrega a sessão do banco para cada request.
from app.core.database import get_db

# Exceções personalizadas da aplicação.
from app.core.exceptions import ForbiddenException, UnauthorizedException

# Função responsável por decodificar e validar o JWT.
from app.core.security import decode_token

# Repositório de usuários para buscar o usuário autenticado no banco.
from app.repositories.user_repository import UserRepository


# ==========================================================
# ESQUEMA DE AUTENTICAÇÃO BEARER
# ==========================================================
# Esse objeto:
# 1. lê o header Authorization
# 2. espera o padrão "Bearer <token>"
# 3. faz o Swagger mostrar que a API usa autenticação Bearer
#
# auto_error=True:
# se o header Authorization não for enviado, o FastAPI já acusa erro.
#
# bearerFormat="JWT":
# ajuda a documentação a indicar que o Bearer Token é um JWT.
#
# description:
# texto mostrado na documentação para orientar o uso do token.
bearer_scheme = HTTPBearer(
    auto_error=True,
    bearerFormat="JWT",
    description="Informe o token no header Authorization no formato: Bearer <seu_access_token>",
)


# ==========================================================
# DEPENDÊNCIA: USUÁRIO AUTENTICADO
# ==========================================================
# Essa função é a base da proteção das rotas privadas.
#
# O fluxo dela é:
# 1. captura o token enviado no Authorization
# 2. decodifica o token JWT
# 3. valida se é token de acesso
# 4. obtém o usuário pelo ID presente no token
# 5. valida se o usuário existe e está ativo
# 6. retorna o usuário autenticado
#
# Sempre que uma rota usar:
# Depends(get_current_user)
# ela exigirá token Bearer válido.
def get_current_user(
    # credentials:
    # recebe automaticamente o Authorization Bearer enviado na request.
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),

    # db:
    # recebe automaticamente a sessão do banco.
    db: Session = Depends(get_db),
):
    # Extrai apenas o valor do token, sem a palavra "Bearer".
    token = credentials.credentials

    # Tenta decodificar e validar o token JWT.
    try:
        payload = decode_token(token)

    # Se o token for inválido, expirado ou malformado,
    # dispara erro de não autorizado.
    except ValueError as exc:
        raise UnauthorizedException(str(exc)) from exc

    # Garante que o token usado seja um token de acesso.
    # Isso evita usar refresh token em endpoint protegido.
    if payload.get("type") != "access":
        raise UnauthorizedException("Token de acesso inválido.")

    # Recupera o ID do usuário a partir do claim "sub".
    user_id = payload.get("sub")

    # Se não houver identificador no token, ele é inválido.
    if not user_id:
        raise UnauthorizedException("Token inválido.")

    # Busca o usuário no banco.
    user = UserRepository(db).get_by_id(int(user_id))

    # Se não encontrar o usuário, o token não serve mais.
    if not user:
        raise UnauthorizedException("Usuário não encontrado.")

    # Se o usuário estiver inativo, bloqueia o acesso.
    if not user.active:
        raise ForbiddenException("Usuário inativo.")

    # Retorna o usuário autenticado para ser usado na rota.
    return user


# ==========================================================
# DEPENDÊNCIA: USUÁRIO ADMINISTRADOR
# ==========================================================
# Essa função depende primeiro de get_current_user.
# Então:
# - já exige token válido
# - já garante que o usuário existe
# - já garante que está ativo
#
# Depois disso, ela valida se o role do usuário é admin.
#
# Use essa dependência em endpoints administrativos.
def require_admin(current_user=Depends(get_current_user)):
    # Verifica se o papel do usuário permite acesso administrativo.
    if current_user.role not in {"admin"}:
        raise ForbiddenException("Acesso permitido apenas para administradores.")

    # Se passar, retorna o usuário autenticado.
    return current_user