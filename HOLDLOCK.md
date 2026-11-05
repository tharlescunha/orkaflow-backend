# HOLDLOCK e os deadlocks do banco (DW-ALZ)

Documento de referência. Quando alguém disser "holdlock" numa conversa sobre o banco gargalando, é aqui que se volta.
Escrito em 04/11/2026. Banco: `alzbdsqlbi.database.windows.net` / `DW-ALZ` (Azure SQL, as tabelas do Regente ficam nele).

---

## 1. O que é o HOLDLOCK (resumo)

É uma instrução dentro da consulta SQL: `WITH (UPDLOCK, ROWLOCK, HOLDLOCK)`. Ela diz ao banco: "trava essa região até eu
terminar a transação, mesmo que ainda não exista linha ali". O Regente usa isso nas checagens de **duplicidade**:
"já existe task aberta para esta automação?", "já existe lock ativo com esta chave?". Sem a trava, duas requisições
simultâneas leriam "não existe", e as duas criariam a task. É uma proteção, e ela **fica**.

Efeito colateral conhecido: quando duas checagens (ou uma checagem e uma gravação) se cruzam em ordem diferente, o banco
resolve cancelando uma delas. Isso é um **deadlock**. A cancelada recebe erro e é repetida na rodada seguinte.

Onde o HOLDLOCK está no código:

| Arquivo | Função | Para que serve |
|---|---|---|
| `app/repositories/task_repository.py` | `get_open_task_for_automation` | há task aberta desta automação? |
| `app/repositories/task_repository.py` | `get_reserved_task_for_exclusive_groups` | task reservada em grupo exclusivo? |
| `app/repositories/task_repository.py` | `has_active_lock_for_exclusive_groups` | lock ativo de grupo exclusivo? |
| `app/repositories/lock_repository.py` | `get_active_by_key` | lock ativo com esta chave? |

Rede de segurança no banco (independente do HOLDLOCK): índice único filtrado `uq_tasks_one_open_per_automation`
(migration `2c8e1f4a6b90`). Mesmo que a checagem falhe, o banco impede duas tasks abertas da mesma automação.

---

## 2. O que estava acontecendo

Sintoma: Database Status mostrava o DW-ALZ como **crítico** (≥ 3 deadlocks em 15 min). Antes das correções de
outubro/novembro eram ~2,15 deadlocks por minuto; depois do restart do Linux de 04/11 ainda ~0,5 por minuto.

Capturei os deadlocks de verdade (sessão de Extended Events, ver seção 5) em 04/11/2026, 20:20 a 21:50 (Brasília):

Dos 40 capturados antes do restart de 04/11 (contagem aproximada, agrupada pelo texto dos comandos):

| Quantos | Quem se travava | Causa |
|---|---|---|
| ~15 | `UPDATE runners` (heartbeat) × `UPDATE tasks` | ordem de gravação inconsistente |
| ~14 | `UPDATE locks` (renovação) × `UPDATE runners` (heartbeat) | ordem de gravação inconsistente |
| ~11 | checagem `UPDLOCK, HOLDLOCK` × outra checagem ou gravação em `tasks`/`locks` | HOLDLOCK (o que sobrou depois) |

A causa dominante **não era o HOLDLOCK**. O mesmo worker manda várias chamadas ao mesmo tempo (heartbeat, status, log,
claim). Todas mexem na **mesma linha do runner** e em linhas de `tasks`/`locks`, em ordens diferentes:

- heartbeat: pegava `runners` e, **segurando-a**, atualizava `locks`;
- log / erro / telemetria: atualizavam `tasks` e `locks` e só no fim `runners`;
- status / finalização da task: pegavam `runners`, depois `tasks`, depois `locks`, depois mexiam em `runners` de novo.

Quando duas dessas chamadas coincidiam, cada uma esperava a linha que a outra segurava.

---

## 3. O que foi alterado (commit `d4336bb`, 04/11/2026)

Arquivo: `app/services/worker_service.py`. Nada de migration, nada de schema, nada de fila/dispatcher/claim.

| O que | Antes | Depois |
|---|---|---|
| Novo auxiliar `_mark_alive_now` | não existia | `_mark_alive` + `commit` na hora: grava o "worker vivo" sozinho e solta a linha do runner |
| `heartbeat` | runner + renovação de locks na mesma transação | confirma o runner sozinho (alive + versão + status), **depois** renova os locks em outra transação |
| `create_task_log` | tasks/locks primeiro, runner no fim | `_mark_alive_now` logo após validar a posse da task |
| `create_task_error` | idem | idem |
| `create_task_telemetry` | idem | idem |
| `update_task_status` | runner na mesma transação das tasks/locks | `_mark_alive_now` antes de qualquer escrita em tasks/locks |
| `finish_task` | idem | idem |
| `release_startup_locks` | idem | `_mark_alive_now` no início |

Intocados de propósito: `claim_task` (já confirma o "vivo" antes e depois segura o runner para serializar a capacidade),
`get_next_task`, `sync_runner`, dispatcher, watchdog, todas as checagens com HOLDLOCK.

Também no commit: `scripts/deadlocks_dwalz.py` (captura/leitura) e `tests/test_worker_lock_order.py` (teste da ordem).

**Resultado medido** (restart do Linux ~21:29 Brasília):

| | Deadlocks por 10 min |
|---|---|
| Antes | 4, 2, 5, 12, 4, 4, 9 (média ≈ 6) |
| Depois | 2, 1, 1 (média ≈ 1,5) |

Queda de ~75%. Os cruzamentos de runner com tasks/locks **sumiram**. Sobraram 4, todos na checagem com HOLDLOCK
(≈ 0,15 por minuto). Decisão: **não mexer nesses**, porque é a proteção contra task duplicada.

Mudanças anteriores que ajudaram o banco no mesmo período (contexto): `d5e6125` (parâmetros Enum como VARCHAR, a consulta
"máquina tem task rodando?" foi de 191 para 9 leituras).

---

## 4. Como desfazer

Só a mudança do worker (mantém o script e o teste), a forma mais limpa:

```bash
git checkout 05dcf39 -- app/services/worker_service.py
```

Depois remova `tests/test_worker_lock_order.py` (ele passaria a falhar, porque testa justamente a ordem nova) ou
reverta tudo de uma vez:

```bash
git revert d4336bb
```

Publicar: `git push origin <branch>:main` (o Azure atualiza sozinho). No Linux (`10.50.156.202`):

```bash
cd /home/tharles.cunha/Projects/orkaflow-backend && git pull && sudo systemctl restart orkaflow-api orkaflow-workers
```

Não há dado nem schema para desfazer. Efeito de reverter: os deadlocks de heartbeat voltam (~6 por 10 min).

---

## 5. Como testar, passo a passo

### 5.1 Teste automático (ordem das gravações)

Na pasta do backend (PowerShell):

```powershell
.venv\Scripts\python.exe -m unittest tests.test_worker_lock_order
```

Esperado: `Ran 5 tests ... OK`. O teste registra os comandos SQL de cada chamada do worker e exige que o
`UPDATE runners ... last_heartbeat` venha **primeiro** e seja confirmado (COMMIT) **antes** de qualquer escrita em
`tasks`/`locks`. Roda em SQLite, então prova a **ordem**, não o comportamento real do Azure. Suíte completa
(310 testes, ~7 min):

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

### 5.2 Medição no banco real (captura de deadlocks)

Usa Extended Events do Azure SQL. **O que escreve no banco:** só a definição de uma sessão chamada `regente_deadlocks`
e um buffer de até 4 MB em memória. Nenhuma tabela, nenhum disco, nenhuma tabela do sistema alterada. O evento só dispara
quando um deadlock acontece. Usa o login do `az` (Entra); precisa ser administrador do banco.
O caminho do `az` está no topo do script (`AZ = ...\azcli\Scripts\az.bat`).

```powershell
cd C:\Projetos\orkaflow-backend
.venv\Scripts\python.exe scripts\deadlocks_dwalz.py criar            # só MOSTRA o que faria
.venv\Scripts\python.exe scripts\deadlocks_dwalz.py criar --confirmo  # cria e liga a captura
.venv\Scripts\python.exe scripts\deadlocks_dwalz.py ler               # resume (só leitura)
.venv\Scripts\python.exe scripts\deadlocks_dwalz.py remover --confirmo  # para e apaga
.venv\Scripts\python.exe scripts\deadlocks_dwalz.py teste             # testa a leitura com um exemplo
```

Como ler a saída de `ler`:
- **PADRÕES**: quais pares de comandos se travam, com a quantidade, e quem foi a vítima (a que foi cancelada).
- **O QUE ESTAVA TRAVADO**: tipo de recurso e índice.
- **ÚLTIMO DEADLOCK**: o detalhe (máquina, aplicação, SQL).

Para ver o ritmo, o timestamp de cada evento é UTC (Brasília = UTC-3). O buffer guarda só os últimos 4 MB: leia
periodicamente se a captura ficar muito tempo ligada.

Estado em 04/11/2026 (22:10 Brasília): a captura `regente_deadlocks` foi **removida** do DW-ALZ depois da medição final
(47 deadlocks capturados de 20:20 a 22:04; depois do restart, ≈ 1 a 2 por 10 min). O banco está sem nada extra.
Para medir de novo, `criar --confirmo`. Para conferir se existe: `scripts\deadlocks_dwalz.py ler` (diz "A captura não
existe" se não estiver criada).

### 5.3 Conferência pela tela

Database Status → DW-ALZ: o cartão de deadlocks (janela de 15 min) e o gráfico de deadlocks por minuto. Crítico =
3 ou mais em 15 min. Referência depois da correção: ≈ 2 por 15 min (≈ 0,15/min).

### 5.4 Roteiro de comparação (antes/depois de qualquer mudança)

1. `ler` e anotar a hora e a contagem atual.
2. Publicar a mudança e reiniciar o Linux (`orkaflow-api` e `orkaflow-workers`).
3. Esperar 30 a 40 minutos de operação normal.
4. `ler` de novo e contar só os deadlocks com horário **depois** do restart (blocos de 10 min).
5. Comparar com a base: **≈ 6 por 10 min** (código antigo) e **≈ 1,5 por 10 min** (código atual).
6. Conferir também: nenhuma máquina OFFLINE, nenhuma task aberta há mais de 8 min, nenhum timeout novo.

---

## 6. Próxima etapa se o banco voltar a gargalar

Fazer nesta ordem, parando quando resolver:

1. **Medir de novo.** Ligar a captura (5.2) e ler após 30 min. Ver se o padrão ainda é o do HOLDLOCK ou se apareceu
   um novo (por exemplo, o `claim_task`).
2. **Se continuar o HOLDLOCK (checagem de duplicidade) e incomodar:** repetir a checagem uma vez quando o banco devolver
   o erro de deadlock (código 1205), em vez de deixar a rodada seguinte repetir. É a opção mais segura: não afrouxa
   proteção nenhuma. Pontos: as quatro funções da tabela da seção 1 e quem as chama (dispatcher e `claim_task`).
3. **Se o `claim_task` aparecer nos deadlocks:** ele segura a linha do runner de propósito para não aceitar duas
   tasks acima da capacidade. Alternativa: trocar essa trava por um `UPDATE` condicional de capacidade. Mudança maior,
   exige teste de concorrência de verdade.
4. **Só em último caso:** tirar o `HOLDLOCK` e depender do índice único `uq_tasks_one_open_per_automation`, tratando o erro
   de violação como "outra requisição ganhou". Reduz deadlock, mas muda o comportamento de duplicidade: exige revisão
   cuidadosa e teste em staging antes de produção.
5. **Fora dos deadlocks:** se o problema for DTU alto (e não deadlock), o pico de 100% de DTU aparece toda hora cheia do dia.
   Investigar as consultas mais caras pelo Database Status (aba Queries) e pelo Query Store.

Regra que vale para tudo isso: o orquestrador não pode parar. Mudar, testar localmente, publicar, medir, e reverter
na hora se algo estranho aparecer (seção 4).
