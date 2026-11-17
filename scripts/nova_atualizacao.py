"""Acrescenta uma atualização ao ATUALIZACOES.md (raiz do backend), no topo.

Calcula sozinho a versão (pelo tipo), a data (do último commit) e a lista de arquivos alterados (dos commits, nos três
repositórios). Você informa o tipo, o título, o problema, a solução e os commits.

Exemplo (na raiz do backend):
    python scripts/nova_atualizacao.py --tipo Melhoria --titulo "Health: novo modo Compacto" ^
        --commits frontend:2a95d32 --problema "..." --solucao "..." [--solicitante "Nome"] [--simular]

Os repositórios do frontend e do worker são procurados ao lado do backend (../orkaflow-frontend, ../orkaflow-worker).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.release_notes_service import (  # noqa: E402
    _HEADER,
    RELEASE_FILE,
    TYPES,
    next_version,
    parse_release_notes,
    render_entry,
)

REPOS = {
    "backend": ROOT,
    "frontend": ROOT.parent / "orkaflow-frontend",
    "worker": ROOT.parent / "orkaflow-worker",
}


def _git(repo: str, *args: str) -> str:
    path = REPOS.get(repo)
    if path is None or not path.exists():
        raise SystemExit(f"Repositório '{repo}' não encontrado em {path}.")
    result = subprocess.run(
        ["git", "-C", str(path), *args], capture_output=True, text=True, encoding="utf-8", check=False
    )
    if result.returncode != 0:
        raise SystemExit(f"git falhou em {repo} ({' '.join(args)}): {result.stderr.strip()}")
    return result.stdout


def parse_commit_refs(refs: list[str]) -> list[dict]:
    commits = []
    for ref in refs:
        repo, _, short = ref.partition(":")
        if repo not in REPOS or not short:
            raise SystemExit(f"Commit inválido '{ref}'. Use repositorio:hash (ex.: backend:abc1234).")
        full = _git(repo, "rev-parse", "--short=7", short).strip()
        commits.append({"repo": repo, "hash": full})
    return commits


def data_do_commit(commit: dict) -> str:
    """Data e hora (Brasília, como gravada no commit) no formato AAAA-MM-DD HH:MM."""
    return _git(commit["repo"], "show", "-s", "--format=%ad", "--date=format:%Y-%m-%d %H:%M", commit["hash"]).strip()


def arquivos_dos_commits(commits: list[dict]) -> list[dict]:
    """Arquivos tocados pelos commits, com a situação final de cada um (A novo, M alterado, D removido, R renomeado)."""
    final: dict[tuple[str, str], str] = {}
    for commit in commits:
        out = _git(commit["repo"], "show", "--name-status", "--format=", "-M", commit["hash"])
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            code, path = parts[0][0], parts[-1]
            key = (commit["repo"], path)
            before = final.get(key)
            if code == "R":
                final[key] = "R"
            elif code == "D":
                final[key] = "D"
            elif code == "A":
                final[key] = "A" if before != "D" else "M"
            else:  # M e demais
                final[key] = before if before in ("A", "R") else "M"
    order = {repo: i for i, repo in enumerate(REPOS)}
    return [
        {"status": status, "repo": repo, "path": path}
        for (repo, path), status in sorted(final.items(), key=lambda kv: (order[kv[0][0]], kv[0][1]))
    ]


def inserir_no_topo(text: str, entry_text: str) -> str:
    """Põe a entrada antes da mais nova (ou no fim da apresentação, se ainda não há entradas)."""
    first = _HEADER.search(text)
    if first:
        head, tail = text[: first.start()], text[first.start():]
        if not head.endswith("\n\n"):
            head = head.rstrip("\n") + "\n\n"
        return head + entry_text + "\n---\n\n" + tail
    head = text.rstrip("\n") + "\n\n"
    return head + entry_text + "\n---\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Acrescenta uma atualização ao ATUALIZACOES.md.")
    parser.add_argument("--tipo", required=True, choices=list(TYPES))
    parser.add_argument("--titulo", required=True)
    parser.add_argument("--commits", required=True, nargs="+", help="repositorio:hash (backend|frontend|worker)")
    parser.add_argument("--problema", required=True)
    parser.add_argument("--solucao", required=True)
    parser.add_argument("--solicitante", default=None, help="só quando outra pessoa pediu")
    parser.add_argument("--data", default=None, help="AAAA-MM-DD HH:MM (padrão: a do último commit)")
    parser.add_argument("--simular", action="store_true", help="só mostra o que seria escrito")
    args = parser.parse_args()

    commits = parse_commit_refs(args.commits)
    released_at = args.data or max(data_do_commit(c) for c in commits)
    text = Path(RELEASE_FILE).read_text(encoding="utf-8")
    current = parse_release_notes(text)["current_version"]
    entry = {
        "version": next_version(current, args.tipo),
        "type_label": args.tipo,
        "released_at": released_at,
        "title": args.titulo,
        "requester": args.solicitante,
        "commits": commits,
        "problem": args.problema,
        "solution": args.solucao,
        "files": arquivos_dos_commits(commits),
    }
    entry_text = render_entry(entry)

    if args.simular:
        print(entry_text)
        print(f"(simulação: nada foi gravado; versão seria v{entry['version']})")
        return

    new_text = inserir_no_topo(text, entry_text)
    check = parse_release_notes(new_text)
    if check["current_version"] != entry["version"] or check["total"] != parse_release_notes(text)["total"] + 1:
        raise SystemExit("A entrada gerada não foi lida de volta corretamente; nada foi gravado.")
    Path(RELEASE_FILE).write_text(new_text, encoding="utf-8", newline="\n")
    print(f"ATUALIZACOES.md atualizado: v{entry['version']} ({args.tipo}), {len(entry['files'])} arquivo(s).")


if __name__ == "__main__":
    main()
