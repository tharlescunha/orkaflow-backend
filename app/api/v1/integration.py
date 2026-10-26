"""Aba Integração: documentação da API (só logado) e dados para configurar o MCP."""
import copy

from fastapi import APIRouter, Request

from app.core.config import settings
from app.integration.api_guide import GUIDE, TAG_GUIDE

router = APIRouter(prefix="/integration", tags=["Integração"])

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def build_documented_openapi(app) -> dict:
    """OpenAPI da aplicação com a explicação em português de cada rota (x-orkaflow-guide)."""
    spec = copy.deepcopy(app.openapi())
    for path, operations in spec.get("paths", {}).items():
        for method, operation in operations.items():
            if method not in _HTTP_METHODS:
                continue
            guide = GUIDE.get(f"{method.upper()} {path}")
            if guide:
                operation["x-orkaflow-guide"] = guide
                if guide.get("summary"):
                    operation["summary"] = guide["summary"]
    tags = []
    for tag in sorted({t for ops in spec.get("paths", {}).values() for op in ops.values() if isinstance(op, dict) for t in op.get("tags", [])}):
        tags.append({"name": tag, "description": TAG_GUIDE.get(tag, "")})
    spec["tags"] = tags
    return spec


@router.get("/openapi")
def documented_openapi(request: Request):
    """Documentação completa da API (OpenAPI 3.1) com as explicações da aba Integração."""
    return build_documented_openapi(request.app)


@router.get("/mcp-info")
def mcp_info(request: Request):
    """Endereço do servidor MCP deste backend e as ferramentas disponíveis para a IA."""
    from app.mcp.tools import tool_catalog

    base = str(request.base_url).rstrip("/")
    # Atrás do proxy do Azure o esquema chega como http; o endereço público é https.
    forwarded_proto = request.headers.get("x-forwarded-proto")
    if forwarded_proto and base.startswith("http://"):
        base = f"{forwarded_proto}://" + base[len("http://"):]
    return {
        "enabled": settings.enable_mcp,
        "url": f"{base}/mcp",
        "api_base_url": f"{base}{settings.api_prefix}",
        "tools": tool_catalog(),
    }
