"""Atualizações do sistema (nov/2026): o ATUALIZACOES.md (raiz do backend) é a fonte única do histórico de versões.
A tela do Regente lê esse arquivo pela API; quem abre o repositório lê o mesmo texto."""
import unittest
from pathlib import Path

from app.services.release_notes_service import (
    RELEASE_FILE,
    ReleaseNotesService,
    next_version,
    parse_release_notes,
    render_entry,
)

AMOSTRA = """# Atualizações do sistema

Texto de apresentação que o leitor ignora.

---

## v3.3.2.0 · Melhoria · 2026-11-17 14:20

**Liberar acesso: avisar que um usuário bloqueado já está ok**

- **Commits:** backend `f554718` · frontend `296fc1a`, `387fafb`
- **Solicitante:** Fernando

**Problema:** O robô suspendia o aprovador por 24 horas.

Mesmo depois de corrigido, ninguém conseguia liberar.

**Solução:** Nova tela Liberar acesso.

<details>
<summary>Arquivos alterados (2)</summary>

- `A` backend · `app/services/access_release_service.py`
- `M` frontend · `src/lib/navigation.ts`

</details>

---

## v3.3.1.1 · Correção · 2026-11-04 09:05

**Fila: task não fica mais travada**

- **Commits:** backend `d4336bb`

**Problema:** Tasks ficavam presas.

**Solução:** Corrigida a ordem das gravações.

---

## v3.3.1.0 · Melhoria · 2026-10-30 18:00

**Health: modo foco**

- **Commits:** frontend `1112223`

**Problema:** Não cabia no telão.

**Solução:** Novo modo Foco.

---

## v3.3.0.0 · Geral · 2026-06-27 10:00

**Base do sistema**

- **Commits:** backend `aaaaaaa`, worker `bbbbbbb`

**Problema:** Não havia orquestrador.

**Solução:** Primeira versão.
"""


class LeitorTests(unittest.TestCase):
    def setUp(self):
        self.notas = parse_release_notes(AMOSTRA)

    def test_totais_versao_atual_e_ultimo_deploy(self):
        self.assertEqual(self.notas["total"], 4)
        self.assertEqual(self.notas["current_version"], "3.3.2.0")
        self.assertEqual(self.notas["last_release_at"], "2026-11-17T14:20:00-03:00")
        self.assertEqual(self.notas["counts"], {"geral": 1, "melhoria": 2, "correcao": 1})

    def test_ordem_do_arquivo_e_mantida_mais_nova_primeiro(self):
        self.assertEqual([i["version"] for i in self.notas["items"]], ["3.3.2.0", "3.3.1.1", "3.3.1.0", "3.3.0.0"])

    def test_campos_da_entrada_completa(self):
        item = self.notas["items"][0]
        self.assertEqual(item["type"], "melhoria")
        self.assertEqual(item["type_label"], "Melhoria")
        self.assertEqual(item["title"], "Liberar acesso: avisar que um usuário bloqueado já está ok")
        self.assertEqual(item["requester"], "Fernando")
        self.assertEqual(item["released_at"], "2026-11-17T14:20:00-03:00")
        self.assertEqual(item["commits"], [
            {"repo": "backend", "hash": "f554718"},
            {"repo": "frontend", "hash": "296fc1a"},
            {"repo": "frontend", "hash": "387fafb"},
        ])
        self.assertEqual(item["problem"], "O robô suspendia o aprovador por 24 horas.\n\nMesmo depois de corrigido, ninguém conseguia liberar.")
        self.assertEqual(item["solution"], "Nova tela Liberar acesso.")
        self.assertEqual(item["files"], [
            {"status": "A", "repo": "backend", "path": "app/services/access_release_service.py"},
            {"status": "M", "repo": "frontend", "path": "src/lib/navigation.ts"},
        ])

    def test_solicitante_e_arquivos_sao_opcionais(self):
        item = self.notas["items"][1]
        self.assertIsNone(item["requester"])
        self.assertEqual(item["files"], [])
        self.assertEqual(item["type"], "correcao")

    def test_entrada_malformada_e_ignorada_sem_derrubar_a_leitura(self):
        texto = AMOSTRA + "\n---\n\n## v3.x.y.z · Melhoria · quando der\n\n**Quebrada**\n"
        self.assertEqual(parse_release_notes(texto)["total"], 4)

    def test_texto_vazio(self):
        vazio = parse_release_notes("")
        self.assertEqual((vazio["total"], vazio["current_version"], vazio["items"]), (0, None, []))


class VersaoTests(unittest.TestCase):
    """O primeiro número (3) é a geração do sistema e nunca muda; os três seguintes seguem o padrão X.Y.Z."""

    def test_numeracao_geral_sobe_o_primeiro_dos_tres(self):
        self.assertEqual(next_version("3.9.5.2", "Geral"), "3.10.0.0")

    def test_numeracao_melhoria_sobe_o_segundo_dos_tres(self):
        self.assertEqual(next_version("3.9.5.2", "Melhoria"), "3.9.6.0")

    def test_numeracao_correcao_sobe_o_terceiro_dos_tres(self):
        self.assertEqual(next_version("3.9.5.2", "Correção"), "3.9.5.3")

    def test_a_geracao_3_nunca_muda(self):
        for tipo in ("Geral", "Melhoria", "Correção"):
            self.assertTrue(next_version("3.9.5.2", tipo).startswith("3."))

    def test_sem_versao_anterior_comeca_em_3_3_0_0(self):
        self.assertEqual(next_version(None, "Melhoria"), "3.3.0.0")

    def test_tipo_desconhecido_e_recusado(self):
        with self.assertRaises(ValueError):
            next_version("3.3.0.0", "Outro")


class RenderTests(unittest.TestCase):
    def test_o_que_o_script_escreve_o_leitor_entende(self):
        entrada = {
            "version": "3.9.6.0", "type_label": "Melhoria", "released_at": "2026-12-01 10:30",
            "title": "Algo novo", "requester": "Thiago",
            "commits": [{"repo": "backend", "hash": "abc1234"}, {"repo": "frontend", "hash": "def5678"}, {"repo": "frontend", "hash": "1112223"}],
            "problem": "Faltava algo.\n\nSegundo parágrafo.", "solution": "Agora tem.",
            "files": [{"status": "A", "repo": "backend", "path": "app/x.py"}, {"status": "M", "repo": "frontend", "path": "src/y.tsx"}],
        }
        lido = parse_release_notes(render_entry(entrada))["items"][0]
        self.assertEqual(lido["version"], "3.9.6.0")
        self.assertEqual(lido["type"], "melhoria")
        self.assertEqual(lido["requester"], "Thiago")
        self.assertEqual(lido["commits"], entrada["commits"])
        self.assertEqual(lido["problem"], entrada["problem"])
        self.assertEqual(lido["solution"], entrada["solution"])
        self.assertEqual(lido["files"], entrada["files"])
        self.assertEqual(lido["released_at"], "2026-12-01T10:30:00-03:00")


class ArquivoRealTests(unittest.TestCase):
    """O ATUALIZACOES.md do repositório precisa estar sempre legível e completo: este teste protege o arquivo."""

    def test_o_arquivo_existe_e_todas_as_entradas_estao_completas(self):
        self.assertTrue(Path(RELEASE_FILE).exists(), "ATUALIZACOES.md precisa existir na raiz do backend")
        texto = Path(RELEASE_FILE).read_text(encoding="utf-8")
        notas = parse_release_notes(texto)
        cabecalhos = texto.count("\n## v")
        self.assertEqual(notas["total"], cabecalhos, "há entrada com cabeçalho fora do padrão (não foi lida)")
        versoes = [i["version"] for i in notas["items"]]
        self.assertEqual(len(versoes), len(set(versoes)), "versão repetida")
        for item in notas["items"]:
            for campo in ("title", "problem", "solution", "released_at"):
                self.assertTrue(item[campo], f"v{item['version']}: falta {campo}")
            self.assertTrue(item["commits"], f"v{item['version']}: falta a lista de commits")

    def test_do_mais_novo_para_o_mais_antigo(self):
        itens = ReleaseNotesService().read()["items"]
        datas = [i["released_at"] for i in itens]
        self.assertEqual(datas, sorted(datas, reverse=True))


if __name__ == "__main__":
    unittest.main()
