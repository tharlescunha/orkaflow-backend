"""Servidor MCP do OrkaFlow (Model Context Protocol, transporte HTTP "streamable").

Endpoint: POST /mcp (fora do /api/v1, para o endereço ficar curto).
Autenticação: Authorization: Bearer <token de integração ork_...> (ou o token de login).
Sem estado: cada requisição JSON-RPC é respondida em JSON; não há stream SSE (GET /mcp = 405).
Métodos: initialize, notifications/*, ping, tools/list, tools/call.
"""
from __future__ import annotations

import inspect
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
SERVER_INFO = {"name": "orkaflow", "title": "OrkaFlow - orquestrador de robôs", "version": "1.2.0"}
INSTRUCTIONS = (
    "Ferramentas do OrkaFlow, o orquestrador de robôs RPA da ALZ Grãos. Você pode consultar e operar tudo que o "
    "painel faz (operação, máquinas, bots, versões, automações, agendamentos, variáveis, credenciais, notificações).\n"
    "- Dia a dia: use as ferramentas prontas (resumo_do_dia, ultimas_execucoes, detalhe_task, listar_maquinas, "
    "status_maquina, listar_agendamentos, criar_task, parar_task, criar_versao_bot...). Descubra nomes e ids com "
    "listar_automacoes/listar_maquinas antes de agir.\n"
    "- Cadastrar ou alterar qualquer coisa: como_fazer(assunto) para o roteiro, buscar_rotas para achar a rota, "
    "detalhe_rota para os campos obrigatórios e exemplo, e chamar_api para executar.\n"
    "- Antes de qualquer ação (criar, alterar, parar, pausar, apagar) mostre ao usuário o que será feito e espere a "
    "confirmação. Prefira desativar a apagar.\n"
    "- Status das tasks: waiting/ready (na fila), scheduled, running, stop_requested, finished (sucesso), "
    "error/timeout/forced_stop (falha), canceled. As ferramentas prontas mostram horário de Brasília; chamar_api "
    "devolve UTC.\n"
    "- Valores de credenciais nunca são mostrados; não peça nem repita senhas além do necessário para gravá-las.\n"
    "- Robô novo é sempre feito com a biblioteca Maestro (como_fazer('maestro')): main.py com "
    "`from maestro import Maestro`, `with maestro:` e success/fail; bot cadastrado com reads_task_file_arg=false. "
    "O jeito antigo (JSON por argumento, print, sys.exit) é só para robôs que já existem.\n"
    "- Novidades de outubro/2026 (eventos, calendários, retentativa, Maestro...): como_fazer('novidades').\n"
    "- Para enxergar telas: print_do_erro(task_id) e tela_da_maquina(maquina) devolvem imagem."
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


def _tool_and_arguments(params: dict):
    name = params.get("name")
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ValueError(f"Ferramenta desconhecida: {name}")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments precisa ser um objeto.")
    return tool, arguments


def _tool_error(message: str) -> dict:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _tool_result(data) -> dict:
    # Ferramentas que devolvem imagem (print do erro, tela da máquina) põem a lista em `_imagens`:
    # vira conteúdo de imagem do MCP (a IA da pessoa enxerga a tela) e sai do JSON de texto.
    images: list[dict] = []
    if isinstance(data, dict) and isinstance(data.get("_imagens"), list):
        data = dict(data)
        images = [img for img in data.pop("_imagens") if isinstance(img, dict) and img.get("data")]
    payload = jsonable_encoder(data)
    # chamar_api devolve ok=false quando a rota respondeu 4xx/5xx: a IA precisa ver como erro.
    failed = isinstance(payload, dict) and payload.get("ok") is False
    content: list[dict] = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}]
    for img in images:
        content.append({"type": "image", "data": img["data"], "mimeType": img.get("mimeType") or "image/png"})
    return {
        "content": content,
        "structuredContent": payload if isinstance(payload, dict) else {"resultado": payload},
        "isError": failed,
    }


def _call_tool(db: Session, user, params: dict) -> dict:
    tool, arguments = _tool_and_arguments(params)
    if tool.is_async:
        raise ValueError(f"{tool.name} só pode ser chamada pelo endpoint /mcp.")
    try:
        data = tool.handler(db, user, arguments)
    except HTTPException as exc:
        # Erros de negócio (não encontrado, validação...) voltam para a IA como resultado com erro,
        # para ela poder corrigir a chamada.
        db.rollback()
        return _tool_error(str(exc.detail))
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("Erro na ferramenta MCP %s", tool.name)
        return _tool_error(f"Erro interno ao executar {tool.name}: {type(exc).__name__}")
    return _tool_result(data)


async def _call_async_tool(request: Request, tool, arguments: dict) -> dict:
    try:
        data = tool.handler(request, arguments)
        if inspect.isawaitable(data):
            data = await data
    except HTTPException as exc:
        return _tool_error(str(exc.detail))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Erro na ferramenta MCP %s", tool.name)
        return _tool_error(f"Erro interno ao executar {tool.name}: {type(exc).__name__}")
    return _tool_result(data)


async def _dispatch(message: Any, request: Request, db: Session, user) -> dict | None:
    """Ferramentas assíncronas (que chamam a API por dentro) rodam no loop; o resto, fora dele."""
    if isinstance(message, dict) and message.get("method") == "tools/call" and "id" in message:
        params = message.get("params") or {}
        tool = TOOLS_BY_NAME.get(params.get("name")) if isinstance(params, dict) else None
        if tool is not None and tool.is_async:
            try:
                _, arguments = _tool_and_arguments(params)
            except ValueError as exc:
                return _error(message.get("id"), INVALID_PARAMS, str(exc))
            return _result(message.get("id"), await _call_async_tool(request, tool, arguments))
    return await run_in_threadpool(_handle, message, db, user)


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
        handled = [await _dispatch(m, request, db, user) for m in body]
        responses = [r for r in handled if r is not None]
        return JSONResponse(responses) if responses else Response(status_code=202)

    response = await _dispatch(body, request, db, user)
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
