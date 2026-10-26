"""Servidor MCP do OrkaFlow (Model Context Protocol, transporte HTTP "streamable").

Endpoint: POST /mcp (fora do /api/v1, para o endereço ficar curto).
Autenticação: Authorization: Bearer <token de integração ork_...> (ou o token de login).
Sem estado: cada requisição JSON-RPC é respondida em JSON; não há stream SSE (GET /mcp = 405).
Métodos: initialize, notifications/*, ping, tools/list, tools/call.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.deps import user_from_token
from app.core.database import get_db
from app.mcp.tools import TOOLS, TOOLS_BY_NAME

logger = logging.getLogger(__name__)

router = APIRouter(tags=["MCP"])

SUPPORTED_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
SERVER_INFO = {"name": "orkaflow", "title": "OrkaFlow - orquestrador de robôs", "version": "1.0.0"}
INSTRUCTIONS = (
    "Ferramentas do OrkaFlow, o orquestrador de robôs RPA da ALZ Grãos. "
    "Use listar_automacoes/listar_maquinas para descobrir nomes e ids antes de agir. "
    "Status das tasks: waiting/ready (na fila), running (rodando), finished (sucesso), "
    "error/timeout/forced_stop (falha), canceled. Horários estão no horário de Brasília. "
    "Antes de ações (criar_task, parar_task, pausar/reativar agendamento, criar_versao_bot), "
    "confirme com o usuário o que será feito."
)

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def _error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _result(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _unauthorized(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"detail": message},
        headers={"WWW-Authenticate": 'Bearer realm="orkaflow-mcp"'},
    )


def _tool_list() -> list[dict]:
    return [
        {
            "name": tool.name,
            "title": tool.title,
            "description": tool.description,
            "inputSchema": tool.input_schema,
            "annotations": {
                "title": tool.title,
                "readOnlyHint": tool.read_only,
                "destructiveHint": tool.destructive,
                "openWorldHint": False,
            },
        }
        for tool in TOOLS
    ]


def _call_tool(db: Session, user, params: dict) -> dict:
    name = params.get("name")
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ValueError(f"Ferramenta desconhecida: {name}")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments precisa ser um objeto.")

    try:
        data = tool.handler(db, user, arguments)
    except HTTPException as exc:
        # Erros de negócio (não encontrado, validação...) voltam para a IA como resultado com erro,
        # para ela poder corrigir a chamada.
        db.rollback()
        return {"content": [{"type": "text", "text": str(exc.detail)}], "isError": True}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Erro na ferramenta MCP %s", name)
        return {"content": [{"type": "text", "text": f"Erro interno ao executar {name}: {type(exc).__name__}"}], "isError": True}

    payload = jsonable_encoder(data)
    return {
        "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
        "structuredContent": payload if isinstance(payload, dict) else {"resultado": payload},
        "isError": False,
    }


def _handle(message: Any, db: Session, user) -> dict | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or "method" not in message:
        return _error(message.get("id") if isinstance(message, dict) else None, INVALID_REQUEST, "Requisição JSON-RPC inválida.")

    method = message["method"]
    request_id = message.get("id")
    params = message.get("params") or {}
    is_notification = "id" not in message

    if method.startswith("notifications/"):
        return None
    if is_notification:
        return None

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[0]
        return _result(
            request_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
                "instructions": INSTRUCTIONS,
            },
        )
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": _tool_list()})
    if method == "tools/call":
        try:
            return _result(request_id, _call_tool(db, user, params))
        except ValueError as exc:
            return _error(request_id, INVALID_PARAMS, str(exc))
    if method in ("resources/list", "prompts/list"):
        key = "resources" if method == "resources/list" else "prompts"
        return _result(request_id, {key: []})

    return _error(request_id, METHOD_NOT_FOUND, f"Método não suportado: {method}")


@router.post("/mcp")
async def mcp_endpoint(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return _unauthorized("Envie o token de integração no header Authorization: Bearer ork_...")
    try:
        user = await run_in_threadpool(user_from_token, auth[7:].strip(), db)
    except HTTPException as exc:
        return _unauthorized(str(exc.detail))

    try:
        body = json.loads(await request.body() or b"null")
    except json.JSONDecodeError:
        return JSONResponse(_error(None, PARSE_ERROR, "JSON inválido."), status_code=400)

    # As ferramentas usam o banco de forma síncrona: roda fora do loop para não travar a API.
    if isinstance(body, list):
        handled = [await run_in_threadpool(_handle, m, db, user) for m in body]
        responses = [r for r in handled if r is not None]
        return JSONResponse(responses) if responses else Response(status_code=202)

    response = await run_in_threadpool(_handle, body, db, user)
    if response is None:
        return Response(status_code=202)
    return JSONResponse(response)


@router.get("/mcp")
def mcp_no_stream():
    # Servidor sem estado: não abre stream SSE (o cliente segue só com POST).
    return Response(status_code=405, headers={"Allow": "POST"})


@router.delete("/mcp")
def mcp_no_session():
    return Response(status_code=405, headers={"Allow": "POST"})
