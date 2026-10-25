# Proposta: versões de bot pelo Git e parâmetros para o robô

> Documento de planejamento (24/10/2026). Nada aqui foi implementado ainda.
> Objetivo: deixar o ciclo de versão e a passagem de parâmetros mais profissionais,
> sem quebrar o que já roda (worker com git forçado, variáveis de ambiente, credenciais).

---

## 1. Como é hoje (verificado no código)

### Versões de bot

| Peça | O que existe |
|---|---|
| `bot_versions` | `version`, `commit_hash`, `branch`, `changelog`, `is_active`, `created_by`. Único por `(bot_id, version)`. |
| Qual versão vale | `TaskRepository.get_latest_bot_version_for_bot`: a **ativa de maior id**; senão a última criada. Usada na criação da task e no sync do worker. |
| Worker sem `auto_update` | Reinstala quando `version`/`commit` esperados mudam e faz `git checkout <commit_hash>` (`bot_installer._checkout_expected_revision`). **Voltar versão já funciona** se a versão tiver `commit_hash`. |
| Worker com `auto_update` | Ignora o commit esperado: `git fetch` + `reset` na branch antes de cada execução e chama `POST /worker/bot-versions/auto`, que cria versão `x.y.z+1` com o commit (sem descrição). |
| Link do repositório | Sempre `bots.source_url` (a versão não guarda link). O worker só usa o link novo ao clonar; pasta existente continua com o `origin` antigo (problema visto em 22/10). |

Dores: a versão é criada à mão, a descrição é digitada, não há "voltar para esta versão" explícito e o `auto_update` gera versões sem informação nenhuma.

### Parâmetros para o robô

Já existem **quatro** caminhos, e esse é o problema (ninguém sabe qual usar):

| Caminho | Onde se cadastra | Como chega ao robô |
|---|---|---|
| `automation_parameters` (nome, tipo, padrão, obrigatório) | API `/automations/{id}/parameters` (sem tela própria) | `task_parameters` → `parameters` / `parameters_map` no arquivo da task |
| `default_runtime_parameters_json` (JSON livre) | Automação; sobrescrito por agendamento e por task manual | `runtime_parameters` no arquivo da task |
| Credenciais (`parameters_json.dados_acesso`) | Automação/task, item de credencial | Resolvidas pelo worker → `credentials_json` no arquivo da task (texto puro em disco) |
| Variáveis de ambiente | Tela Variáveis (global < bot < automação < máquina) | `os.environ` |

O robô recebe o caminho do arquivo em `sys.argv[1]` e em `ORKAFLOW_TASK_FILE` (`C:\OrkaFlow\tmp\task_<id>.json`), e pode devolver resultado em `ORKAFLOW_RESULT_FILE`. Ou seja: **o canal já existe**, mas cada robô lê esse JSON do seu jeito, e o painel só oferece JSON livre.

---

## 2. Proposta A — "Sincronizar com o Git" (versões automáticas e voltar versão)

### Como fica para o usuário

1. Sobe o código no Git, como hoje.
2. Em **Versões de Bot** (ou no detalhe do bot) clica **Sincronizar com o Git**.
3. O sistema compara o último commit da branch com a última versão registrada:
   - igual → "Bot já está na última versão";
   - à frente → cria **uma versão nova** com tudo que o Git informa.
4. Na lista de versões, botão **Usar esta versão** (voltar/avançar). A versão escolhida fica fixada até alguém escolher outra ou clicar "Seguir a mais nova".

### O que a versão passa a guardar

| Campo | Origem |
|---|---|
| `commit_hash` (já existe) | último commit da branch |
| `version` (já existe) | tag do commit (`v1.4.0` → `1.4.0`); sem tag, próximo patch (`1.3.2` → `1.3.3`) |
| `changelog` (já existe) | mensagens dos commits entre a versão anterior e esta (uma por linha, com autor) |
| `committed_at`, `commit_author` (novos) | data e autor do último commit |
| `source` (novo) | `manual`, `git_sync` ou `worker_auto` |

### Como o backend lê o Git

No servidor, um cache por bot em `runtime/git-cache/<bot_id>.git` (clone "bare" sem arquivos, `--filter=blob:none`): rápido e leve.

```text
git clone --bare --filter=blob:none <source_url> runtime/git-cache/26.git   # 1ª vez
git -C runtime/git-cache/26.git fetch origin <branch>                         # demais
git -C ... log <commit_anterior>..origin/<branch> --format=%H|%an|%aI|%s
git -C ... describe --tags --exact-match origin/<branch>                       # tag, se houver
```

Funciona igual para GitHub e Azure DevOps (é git puro, usa o token que já está no link). Precisa de `git` instalado no servidor Linux.

### Voltar versão ("release")

- Nova coluna `bots.pinned_version_id` (nula = seguir a mais nova).
- `get_latest_bot_version_for_bot` passa a ser: **fixada**, senão a ativa mais nova (regra atual).
- No `/worker/sync`, se o bot tiver versão fixada, o backend manda `auto_update=false` + o `commit_hash` dela. O worker **já** faz checkout do commit nesse caso: **sem mudança no worker** para voltar versão.

### O que fazer com o `auto_update`

Duas opções (decidir):

1. **Manter** como está, só marcando as versões dele como `source=worker_auto` e preenchendo o changelog pelo backend (via o mesmo cache git).
2. **Trocar** por "Sincronizar automaticamente a cada N minutos" no backend: o worker deixa de puxar a branch sozinho e sempre roda uma versão registrada. Mais previsível e auditável. Recomendado.

### Mudanças por projeto

| Projeto | Mudança |
|---|---|
| Backend | Migration (`pinned_version_id`, `committed_at`, `commit_author`, `source`); `GitRepoService` (cache bare, log, tags, mascarar token em erro); `POST /bots/{id}/sync-git`; `POST /bots/{id}/pin-version` e `/unpin`; regra de versão fixada no sync. |
| Frontend | Botões **Sincronizar com o Git**, **Usar esta versão**, **Seguir a mais nova**; selo "em uso" na lista; changelog formatado. |
| Worker | Nenhuma obrigatória. Recomendado junto: trocar o `origin` quando o link do bot mudar (`git remote set-url` antes do fetch), resolvendo o problema de 22/10. |

Extra (depois): webhook do GitHub/Azure DevOps no push chamando o sync, sem clicar em nada.

---

## 3. Proposta B — parâmetros dinâmicos para o robô

### Ideia central

Em vez de inventar mais um canal, **padronizar o que já existe**:

1. **Contrato de parâmetros declarado no próprio bot** (o robô diz o que precisa).
2. **Formulário no painel** gerado a partir do contrato (nada de JSON livre).
3. **Biblioteca `orkaflow` no robô** que entrega tudo pronto: parâmetros, variáveis, credenciais, log e resultado.

### B1. Contrato no repositório do bot

Arquivo `orkaflow.yaml` na raiz do repositório:

```yaml
parametros:
  filial:
    tipo: lista
    opcoes: ["001", "002", "010"]
    obrigatorio: true
    descricao: Filial a processar
  safra:
    tipo: texto
    padrao: "2026/27"
    obrigatorio: true
  data_referencia:
    tipo: data
    padrao: "{{ontem}}"
  reprocessar:
    tipo: booleano
    padrao: false
```

- Lido pelo **Sincronizar com o Git** (Proposta A) e gravado junto da versão. Ou seja, cada versão sabe quais parâmetros aceita.
- Tipos: texto, número, booleano, data, lista, multilista, segredo (referência a credencial/variável secreta).
- Padrões dinâmicos simples: `{{hoje}}`, `{{ontem}}`, `{{inicio_mes}}`, resolvidos pelo backend na criação da task.

### B2. Painel: valores por camada

O mesmo formulário aparece em Automação, Agendamento e **Nova Task**, com herança:

```text
padrão do contrato  <  automação  <  agendamento  <  execução manual
```

Exemplo do "Movimentação diária": uma automação por filial, ou uma só com agendamentos diferentes (filial 001 às 6h, filial 010 às 7h), cada um com sua safra. Validação de obrigatórios e tipos **antes** de criar a task.

Reaproveita `automation_parameters` e `task_parameters` (a task continua congelando os valores usados, com auditoria).

### B3. Biblioteca `orkaflow` no robô

Pacote Python pequeno, num repositório próprio (`orkaflow-sdk`), instalado pelo `requirements.txt` do bot:

```text
orkaflow-sdk @ git+https://github.com/tharlescunha/orkaflow-sdk@v1.0.0
```

```python
from orkaflow import Contexto

ctx = Contexto()                      # lê ORKAFLOW_TASK_FILE; fora do orquestrador usa um JSON local de teste

filial = ctx.parametro("filial")      # já convertido para o tipo do contrato
safra = ctx.parametro("safra")
url_sap = ctx.variavel("SAP_URL")     # variáveis de ambiente
login = ctx.credencial("SAP_PRD")     # {"usuario": ..., "senha": ...}

ctx.log.info("Processando filial %s", filial)
ctx.progresso(processados=120, falhas=2)
ctx.resultado({"notas": 120})         # grava ORKAFLOW_RESULT_FILE
```

Por que assim:

- **Funciona com o worker atual**: lê o arquivo da task e o ambiente que já são entregues hoje.
- Esconde o formato interno do JSON: se o arquivo mudar, só a biblioteca muda, não os robôs.
- Modo local para desenvolver: `Contexto(arquivo="teste.json")`, sem orquestrador.
- Erro claro: `ctx.parametro("filial")` sem valor levanta "Parâmetro obrigatório 'filial' não informado".

### B4. Evolução (opcional, depois): o robô consulta o orquestrador

Para buscar dados **durante** a execução (ex.: segredo só quando precisar, progresso ao vivo, pedir mais itens):

- O worker passa um **token curto da task** (`ORKAFLOW_TASK_TOKEN`, vale só enquanto a task roda).
- A biblioteca chama `GET /api/v1/bot-api/context` e `POST /api/v1/bot-api/progress` com esse token.
- Vantagem: credenciais deixam de ir em texto puro para `C:\OrkaFlow\tmp\task_<id>.json`.
- Custo: rota nova e autenticação nova no backend. Fazer depois de B1–B3 estarem estáveis.

### Quando usar cada coisa (regra para documentar no Guia do Bot)

| Preciso passar... | Use |
|---|---|
| Algo que muda por execução/agendamento (filial, safra, data) | **Parâmetro** (contrato + formulário) |
| Configuração fixa do ambiente (URL, pasta, servidor) | **Variável de ambiente** |
| Usuário e senha | **Credencial** (ou variável secreta) |

### Mudanças por projeto

| Projeto | Mudança |
|---|---|
| Backend | Ler `orkaflow.yaml` no sync git e guardar o contrato na versão; validar/resolver valores por camada na criação da task; endpoint do formulário. |
| Frontend | Componente de formulário a partir do contrato, em Automação, Agendamento e Nova Task; esconder o JSON livre atrás de "avançado". |
| Worker | Nenhuma obrigatória para B1–B3 (arquivo da task já tem os parâmetros). B4 exige token da task. |
| Novo repositório | `orkaflow-sdk` (biblioteca do robô) com testes e exemplo. |

---

## 4. Ordem sugerida

| Fase | Entrega | Risco |
|---|---|---|
| 1 | Biblioteca `orkaflow-sdk` lendo o arquivo da task atual (B3) + regra "quando usar cada coisa" | Baixo: nada muda no orquestrador |
| 2 | Sincronizar com o Git + Usar esta versão (A) + troca de `origin` no worker | Médio: precisa de git no servidor |
| 3 | Contrato `orkaflow.yaml` + formulário por camada (B1, B2) | Médio |
| 4 | Token da task e API para o robô (B4); webhook do Git | Maior: autenticação nova |

Começar pela fase 1 dá ganho imediato no "Movimentação diária": parâmetros (`filial`, `safra`) no `runtime_parameters` da automação/agendamento e lidos com `ctx.parametro(...)`, sem variável de ambiente.

## 5. Decisões em aberto

1. `auto_update`: manter (opção 1) ou trocar por sync automático no backend (opção 2)?
2. Número da versão: usar tags do Git (exige criar tag ao publicar) ou só incremento automático?
3. Formato do contrato: `orkaflow.yaml` no repositório (versionado com o código) ou cadastro só no painel?
4. Biblioteca: repositório próprio `orkaflow-sdk` (recomendado) ou pasta dentro do worker?
