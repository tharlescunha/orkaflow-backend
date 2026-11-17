"""Atualizações do sistema (nov/2026).

O ``ATUALIZACOES.md`` (raiz do backend) é a fonte única do histórico de versões do Regente. Quem abre o repositório lê o
mesmo texto que a tela "Atualizações" mostra: o backend lê o arquivo e entrega estruturado em ``GET /api/v1/releases/``.

Formato de cada entrada (do mais novo para o mais antigo, separadas por ``---``)::

    ## v3.9.5.0 · Melhoria · 2026-11-17 14:20

    **Título curto**

    - **Commits:** backend `f554718` · frontend `296fc1a`
    - **Solicitante:** Fulano            (linha opcional)

    **Problema:** ...

    **Solução:** ...

    <details>
    <summary>Arquivos alterados (2)</summary>

    - `A` backend · `app/x.py`
    - `M` frontend · `src/y.tsx`

    </details>

Numeração ``3.X.Y.Z``: o primeiro número (3) é a geração do sistema (o terceiro orquestrador) e nunca muda. Nos três
seguintes, ``Geral`` sobe o X (e zera Y e Z), ``Melhoria`` sobe o Y (e zera Z) e ``Correção`` sobe o Z.
A primeira entrada é 3.3.0.0. Horários em Brasília (UTC-3). Para acrescentar uma entrada use ``scripts/nova_atualizacao.py``.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

RELEASE_FILE = Path(__file__).resolve().parents[2] / "ATUALIZACOES.md"

TYPES = {"Geral": "geral", "Melhoria": "melhoria", "Correção": "correcao"}
TYPE_LABELS = {value: key for key, value in TYPES.items()}
BRT = "-03:00"
# O 3 é a geração do sistema (terceiro orquestrador) e nunca muda. A numeração parte de 3.3.0.0.
GENERATION = 3
FIRST_VERSION = "3.3.0.0"

_HEADER = re.compile(
    r"^## v(\d+)\.(\d+)\.(\d+)\.(\d+) · (Geral|Melhoria|Correção) · (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})[ \t]*$",
    re.MULTILINE,
)
_BODY_END = re.compile(r"^(?:---[ \t]*$|## )", re.MULTILINE)
_TITLE = re.compile(r"^\*\*([^*\n]+)\*\*[ \t]*$", re.MULTILINE)
_COMMITS = re.compile(r"^- \*\*Commits:\*\* (.+)$", re.MULTILINE)
_REQUESTER = re.compile(r"^- \*\*Solicitante:\*\* (.+)$", re.MULTILINE)
_HASH = re.compile(r"`([0-9a-f]{6,40})`")
_FILE = re.compile(r"^- `([AMDR])` (\w+) · `(.+)`[ \t]*$", re.MULTILINE)
_DETAILS = re.compile(r"<details>.*?</details>", re.DOTALL)


# ------------------------------------------------------------------------- numeração
def next_version(current: str | None, kind: str) -> str:
    """Próxima versão (3.X.Y.Z) a partir da atual e do tipo (Geral/Melhoria/Correção). Sem anterior: 3.3.0.0."""
    if kind not in TYPES:
        raise ValueError(f"Tipo inválido: {kind!r}. Use Geral, Melhoria ou Correção.")
    if not current:
        return FIRST_VERSION
    _generation, x, y, z = (int(part) for part in current.split("."))
    if kind == "Geral":
        return f"{GENERATION}.{x + 1}.0.0"
    if kind == "Melhoria":
        return f"{GENERATION}.{x}.{y + 1}.0"
    return f"{GENERATION}.{x}.{y}.{z + 1}"


# ------------------------------------------------------------------------- leitura
def _parse_commits(line: str) -> list[dict]:
    commits: list[dict] = []
    for part in line.split("·"):
        repo = re.match(r"\s*(\w+)\b", part)
        if not repo:
            continue
        for found in _HASH.findall(part):
            commits.append({"repo": repo.group(1), "hash": found})
    return commits


def _parse_entry(header: re.Match, body: str) -> dict | None:
    title = _TITLE.search(body)
    problem_at = body.find("**Problema:**")
    solution_at = body.find("**Solução:**")
    if not title or problem_at < 0 or solution_at < 0 or solution_at < problem_at:
        return None

    details_at = body.find("<details>")
    solution_end = details_at if details_at > solution_at else len(body)
    commits_line = _COMMITS.search(body)
    requester = _REQUESTER.search(body)
    details = _DETAILS.search(body)
    kind = TYPES[header.group(5)]

    return {
        "version": ".".join(header.group(i) for i in (1, 2, 3, 4)),
        "type": kind,
        "type_label": header.group(5),
        "released_at": f"{header.group(6)}T{header.group(7)}:00{BRT}",
        "title": title.group(1).strip(),
        "requester": requester.group(1).strip() if requester else None,
        "commits": _parse_commits(commits_line.group(1)) if commits_line else [],
        "problem": body[problem_at + len("**Problema:**"):solution_at].strip(),
        "solution": body[solution_at + len("**Solução:**"):solution_end].strip(),
        "files": [
            {"status": m.group(1), "repo": m.group(2), "path": m.group(3)}
            for m in _FILE.finditer(details.group(0))
        ]
        if details
        else [],
    }


def parse_release_notes(text: str) -> dict:
    """Lê o texto do ATUALIZACOES.md. Entrada fora do padrão é ignorada (e registrada), nunca derruba a leitura."""
    items: list[dict] = []
    headers = list(_HEADER.finditer(text or ""))
    for header in headers:
        rest = text[header.end():]
        end = _BODY_END.search(rest)
        body = rest[: end.start()] if end else rest
        try:
            entry = _parse_entry(header, body)
        except Exception:  # noqa: BLE001
            logger.exception("Entrada v%s.%s.%s.%s do ATUALIZACOES.md ilegível.", *header.group(1, 2, 3, 4))
            entry = None
        if entry is None:
            logger.warning("Entrada %s do ATUALIZACOES.md incompleta: ignorada.", header.group(0))
            continue
        items.append(entry)

    counts = {kind: 0 for kind in TYPES.values()}
    for item in items:
        counts[item["type"]] += 1
    return {
        "total": len(items),
        "current_version": items[0]["version"] if items else None,
        "last_release_at": items[0]["released_at"] if items else None,
        "counts": counts,
        "items": items,
    }


# ------------------------------------------------------------------------- escrita (usada pelo script)
def _commits_text(commits: list[dict]) -> str:
    by_repo: dict[str, list[str]] = {}
    for commit in commits:
        by_repo.setdefault(commit["repo"], []).append(f"`{commit['hash']}`")
    return " · ".join(f"{repo} {', '.join(hashes)}" for repo, hashes in by_repo.items())


def render_entry(entry: dict) -> str:
    """Texto Markdown de uma entrada, no formato que ``parse_release_notes`` lê."""
    lines = [
        f"## v{entry['version']} · {entry['type_label']} · {entry['released_at']}",
        "",
        f"**{entry['title'].strip()}**",
        "",
        f"- **Commits:** {_commits_text(entry['commits'])}",
    ]
    if entry.get("requester"):
        lines.append(f"- **Solicitante:** {entry['requester'].strip()}")
    lines += ["", f"**Problema:** {entry['problem'].strip()}", "", f"**Solução:** {entry['solution'].strip()}"]
    files = entry.get("files") or []
    if files:
        lines += ["", "<details>", f"<summary>Arquivos alterados ({len(files)})</summary>", ""]
        lines += [f"- `{f['status']}` {f['repo']} · `{f['path']}`" for f in files]
        lines += ["", "</details>"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------- serviço
class ReleaseNotesService:
    """Lê o arquivo e guarda o resultado até ele mudar (cache pela data de modificação)."""

    _cache: tuple[float, dict] | None = None

    def read(self) -> dict:
        path = Path(RELEASE_FILE)
        try:
            mtime = path.stat().st_mtime
        except OSError:
            logger.warning("ATUALIZACOES.md não encontrado em %s", path)
            return parse_release_notes("")
        cached = ReleaseNotesService._cache
        if cached and cached[0] == mtime:
            return cached[1]
        notes = parse_release_notes(path.read_text(encoding="utf-8"))
        ReleaseNotesService._cache = (mtime, notes)
        return notes

    def latest(self) -> dict:
        notes = self.read()
        return {"version": notes["current_version"], "released_at": notes["last_release_at"]}
