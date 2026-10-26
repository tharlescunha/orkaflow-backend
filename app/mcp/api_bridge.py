"""Ponte do MCP com a API: a IA encontra, entende e chama qualquer rota do painel.

A chamada passa pela própria aplicação (ASGI, sem rede), com o mesmo token de quem
chamou o MCP: valem as mesmas permissões, validações e regras do painel.
Algumas rotas ficam fora de propósito (ver _blocked_reason).
"""
from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import urlencode

from fastapi import Request

from app.core.exceptions import ValidationException
from app.integration.api_guide import GUIDE, TAG_GUIDE

API_PREFIX = "/api/v1"
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
MAX_RESPONSE_CHARS = 60_000
MAX_SEARCH_RESULTS = 40

# Administração fica só para consulta por aqui (alterar usuários/perfis é no painel).
_READ_ONLY_PREFIXES = ("/api/v1/users", "/api/v1/profiles", "/api/v1/permissions")


def _blocked_reason(method: str, template: str) -> str | None:
    if not template.startswith(API_PREFIX + "/"):
        return "Só rotas do painel (/api/v1/...)."
    if template.startswith("/api/v1/worker"):
        return "Rota usada só pelo agente das máquinas."
    if template.startswith(("/api/v1/auth/", "/api/v1/public/")):
        return "Login e downloads não são usados pelo MCP."
    if "api-tokens" in template:
        return "Tokens de integração são gerados e revogados só no painel."
    if template.endswith("/reveal"):
        return "O valor real de credenciais não é exposto à IA."
    if template.endswith("/screenshot"):
        return "Imagem não é suportada por aqui; veja no painel."
    if template == "/api/v1/integration/openapi":
        return "Use buscar_rotas e detalhe_rota."
    if method != "GET" and template.startswith(_READ_ONLY_PREFIXES):
        return "Usuários e perfis só podem ser consultados pelo MCP; altere no painel."
    return None


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").lower()


def _operations(app) -> list[dict]:
    """Rotas da API com o guia (cacheado no app)."""
    cached = getattr(app.state, "mcp_operations", None)
    if cached is not None:
        return cached
    spec = app.openapi()
    ops = []
    for path, item in spec.get("paths", {}).items():
        for method, op in item.items():
            method = method.upper()
            if method not in METHODS:
                continue
            key = f"{method} {path}"
            guide = GUIDE.get(key, {})
            ops.append({
                "key": key,
                "method": method,
                "path": path,
                "regex": re.compile("^" + re.sub(r"\\\{[^/]+?\\\}", "[^/]+", re.escape(path)) + "$"),
                "tag": (op.get("tags") or ["Outros"])[0],
                "summary": guide.get("summary") or op.get("summary") or "",
                "guide": guide,
                "op": op,
                "blocked": _blocked_reason(method, path),
            })
    app.state.mcp_operations = ops
    app.state.mcp_schemas = spec.get("components", {}).get("schemas", {})
    return ops


def _find_operation(app, method: str, path: str) -> dict | None:
    ops = _operations(app)
    exact = [o for o in ops if o["method"] == method and o["path"] == path]
    if exact:
        return exact[0]
    # Caminho concreto (/api/v1/bots/12): casa com o modelo; rota fixa vence a com {id}.
    matches = [o for o in ops if o["method"] == method and o["regex"].match(path)]
    matches.sort(key=lambda o: o["path"].count("{"))
    return matches[0] if matches else None


# ------------------------------------------------------------- esquemas
def _resolve(app, schema: dict | None, depth: int = 0) -> dict:
    if not schema or depth > 8:
        return schema or {}
    ref = schema.get("$ref")
    if ref:
        name = ref.rsplit("/", 1)[-1]
        return _resolve(app, app.state.mcp_schemas.get(name, {}), depth + 1)
    variants = [v for v in (schema.get("anyOf") or schema.get("oneOf") or []) if v.get("type") != "null"]
    if len(variants) == 1:
        resolved = dict(_resolve(app, variants[0], depth + 1))
        resolved["_opcional"] = True
        for key in ("description", "default", "title"):
            if key in schema:
                resolved.setdefault(key, schema[key])
        return resolved
    return schema


def _type_label(app, schema: dict, depth: int = 0) -> str:
    s = _resolve(app, schema)
    if "enum" in s:
        label = " | ".join(json.dumps(v, ensure_ascii=False) for v in s["enum"])
    elif s.get("type") == "array":
        label = f"lista de {_type_label(app, s.get('items') or {}, depth + 1)}" if depth < 3 else "lista"
    elif s.get("properties"):
        label = f"objeto {s.get('title') or ''}".strip()
    elif s.get("format") == "date-time":
        label = "data/hora ISO 8601"
    else:
        label = {"integer": "inteiro", "number": "número", "boolean": "true/false", "string": "texto",
                 "object": "objeto (JSON livre)"}.get(s.get("type"), "qualquer")
    return label + (" ou null" if s.get("_opcional") else "")


def _fields(app, schema: dict | None, depth: int = 0) -> list[dict]:
    s = _resolve(app, schema)
    required = set(s.get("required") or [])
    fields = []
    for name, prop in (s.get("properties") or {}).items():
        resolved = _resolve(app, prop)
        field = {
            "nome": name,
            "tipo": _type_label(app, prop),
            "obrigatorio": name in required,
        }
        description = resolved.get("description") or prop.get("description")
        if description:
            field["descricao"] = description
        if "default" in resolved and resolved["default"] is not None:
            field["padrao"] = resolved["default"]
        for key, label in (("minimum", "minimo"), ("maximum", "maximo"), ("maxLength", "max_caracteres")):
            if key in resolved:
                field[label] = resolved[key]
        item_schema = _resolve(app, resolved.get("items")) if resolved.get("type") == "array" else resolved
        if depth < 1 and item_schema.get("properties"):
            field["campos"] = _fields(app, item_schema, depth + 1)
        fields.append(field)
    return fields


# ------------------------------------------------------------ ferramentas
def buscar_rotas(request: Request, args: dict) -> dict:
    ops = [o for o in _operations(request.app) if not o["blocked"]]
    term = _normalize(str(args.get("busca") or "")).strip()
    group = _normalize(str(args.get("grupo") or "")).strip()

    if not term and not group:
        groups: dict[str, int] = {}
        for o in ops:
            groups[o["tag"]] = groups.get(o["tag"], 0) + 1
        return {
            "dica": "Passe 'grupo' para ver as rotas de um grupo ou 'busca' com palavras (ex.: 'vincular maquina').",
            "grupos": [{"grupo": tag, "rotas": count, "sobre": TAG_GUIDE.get(tag, "")[:240]}
                       for tag, count in sorted(groups.items())],
        }

    # Radical da palavra: "criar" acha "Cria", "vincular" acha "Vincula", "agendamentos" acha "agendamento".
    words = [w if len(w) <= 4 else w[: max(4, len(w) - 3)] for w in term.split()]
    found = []
    for o in ops:
        if group and _normalize(o["tag"]) != group:
            continue
        haystack = _normalize(" ".join([o["key"], o["tag"], o["summary"], o["guide"].get("description", "")]))
        if all(word in haystack for word in words):
            # Mais relevante: palavra no resumo/rota antes de só na explicação.
            head = _normalize(o["key"] + " " + o["summary"])
            found.append((-sum(word in head for word in words), o))
    found.sort(key=lambda pair: pair[0])
    return {
        "total": len(found),
        "rotas": [
            {"rota": o["key"], "grupo": o["tag"], "resumo": o["summary"],
             "tipo": "consulta" if o["method"] == "GET" else "alteração"}
            for _, o in found[:MAX_SEARCH_RESULTS]
        ],
        "proximo_passo": "Use detalhe_rota com a 'rota' escolhida antes de chamar_api.",
    }


def detalhe_rota(request: Request, args: dict) -> dict:
    method, path = _split_route(args.get("rota"))
    operation = _find_operation(request.app, method, path) or _find_operation(
        request.app, method, path[:-1] if path.endswith("/") else path + "/"
    )
    if operation is None:
        raise ValidationException(f"Rota {method} {path} não existe. Use buscar_rotas.")
    if operation["blocked"]:
        raise ValidationException(f"Rota indisponível no MCP: {operation['blocked']}")

    app = request.app
    op = operation["op"]
    guide = operation["guide"]
    params = [
        {
            "nome": p["name"],
            "onde": {"path": "no caminho", "query": "query"}.get(p["in"], p["in"]),
            "tipo": _type_label(app, p.get("schema") or {}),
            "obrigatorio": bool(p.get("required")),
            **({"descricao": p["description"]} if p.get("description") else {}),
        }
        for p in op.get("parameters", [])
        if p["in"] in ("path", "query")
    ]
    body_schema = (op.get("requestBody") or {}).get("content", {}).get("application/json", {}).get("schema")
    result = {
        "rota": operation["key"],
        "grupo": operation["tag"],
        "resumo": operation["summary"],
        "explicacao": guide.get("description") or op.get("description") or "",
        "tipo": "consulta" if method == "GET" else "alteração (confirme com o usuário antes)",
        "parametros": params,
    }
    if body_schema:
        result["corpo"] = _fields(app, body_schema)
        if guide.get("example_request") is not None:
            result["exemplo_corpo"] = guide["example_request"]
    if guide.get("example_response") is not None:
        example = json.dumps(guide["example_response"], ensure_ascii=False)
        result["exemplo_resposta"] = guide["example_response"] if len(example) < 4000 else example[:4000] + "..."
    return result


def _split_route(raw) -> tuple[str, str]:
    text = str(raw or "").strip()
    parts = text.split(None, 1)
    if len(parts) != 2 or parts[0].upper() not in METHODS:
        raise ValidationException('Informe a rota como "MÉTODO /api/v1/...", ex.: "POST /api/v1/bots/".')
    return parts[0].upper(), parts[1].split("?", 1)[0].strip()


async def chamar_api(request: Request, args: dict) -> dict:
    method = str(args.get("metodo") or "").strip().upper()
    if method not in METHODS:
        raise ValidationException(f"metodo deve ser um de: {', '.join(METHODS)}.")
    path = str(args.get("caminho") or "").strip()
    if "?" in path:
        raise ValidationException("Passe os filtros em 'query', não no caminho.")
    if not path.startswith(API_PREFIX + "/") or ".." in path or "//" in path:
        raise ValidationException("caminho deve começar com /api/v1/ (ex.: /api/v1/bots/12).")

    operation = _find_operation(request.app, method, path)
    if operation is None:
        # "/api/v1/bots" e "/api/v1/bots/" são a mesma coisa para quem chama.
        alternative = path[:-1] if path.endswith("/") else path + "/"
        operation = _find_operation(request.app, method, alternative)
        if operation is not None:
            path = alternative
    if operation is None:
        raise ValidationException(f"Rota {method} {path} não existe. Use buscar_rotas para achar a certa.")
    if operation["blocked"]:
        raise ValidationException(f"Rota indisponível no MCP: {operation['blocked']}")

    query = args.get("query") or {}
    if not isinstance(query, dict):
        raise ValidationException("query precisa ser um objeto, ex.: {\"automation_id\": 12}.")
    query = {k: (str(v).lower() if isinstance(v, bool) else v) for k, v in query.items() if v is not None}
    body = args.get("corpo")
    if body is not None and method == "GET":
        raise ValidationException("GET não leva corpo; use 'query'.")

    status, payload = await _asgi_call(
        request.app, method, path, urlencode(query, doseq=True), body, request.headers.get("authorization", "")
    )
    text = json.dumps(payload, ensure_ascii=False, default=str)
    result: dict = {"rota": operation["key"], "status": status, "ok": 200 <= status < 300}
    if len(text) > MAX_RESPONSE_CHARS:
        result["resposta_truncada"] = text[:MAX_RESPONSE_CHARS]
        result["aviso"] = "Resposta grande cortada: use filtros/paginação (limit, skip) para ver menos itens."
    else:
        result["resposta"] = payload
    return result


async def _asgi_call(app, method: str, path: str, query_string: str, body, authorization: str):
    raw_body = b"" if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = [(b"host", b"orkaflow-mcp"), (b"accept", b"application/json")]
    if authorization:
        headers.append((b"authorization", authorization.encode("latin-1")))
    if body is not None:
        headers += [(b"content-type", b"application/json"), (b"content-length", str(len(raw_body)).encode())]
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "root_path": "",
        "query_string": query_string.encode("utf-8"),
        "headers": headers,
        "client": ("mcp", 0),
        "server": ("orkaflow-mcp", 80),
    }
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": raw_body, "more_body": False}

    status = 500
    chunks: list[bytes] = []
    content_type = ""

    async def send(message):
        nonlocal status, content_type
        if message["type"] == "http.response.start":
            status = message["status"]
            for key, value in message.get("headers", []):
                if key.lower() == b"content-type":
                    content_type = value.decode("latin-1")
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    data = b"".join(chunks)
    if not data:
        return status, None
    if "json" in content_type:
        try:
            return status, json.loads(data)
        except ValueError:
            pass
    return status, {"conteudo": data[:2000].decode("utf-8", "replace"), "tipo": content_type}
