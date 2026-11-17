# Atualizações do sistema

Histórico de melhorias, correções e mudanças gerais publicadas em produção no **Regente** (backend, frontend e worker).
Cada entrada conta o problema que existia, a solução entregue, os commits e os arquivos alterados. A tela
**Atualizações** do Regente lê este mesmo arquivo; a versão mais nova fica no topo.

## Como funciona a numeração

A versão tem quatro números, no padrão **3.X.Y.Z**.

O primeiro número (**3**) é a geração do sistema: o Regente é o terceiro orquestrador (depois de uma base de testes e de uma
segunda versão) e esse número não muda. Nos três seguintes, cada tipo de atualização sobe uma casa e zera as casas à direita:

- **Geral** sobe o X: mudanças estruturais ou de infraestrutura.
- **Melhoria** sobe o Y: nova funcionalidade.
- **Correção** sobe o Z: correção pontual.

A numeração parte de **3.3.0.0** (a base de junho/2026). No painel, o menu e a tela de entrada mostram só **v3**; a versão
completa aparece na tela Atualizações.

## Como acrescentar uma atualização

Depois de publicar algo, rode na raiz do backend (ele calcula a versão, a data e a lista de arquivos pelos commits):

```
python scripts/nova_atualizacao.py --tipo Melhoria --titulo "Assunto: o que mudou" --commits backend:abc1234 frontend:def5678 --problema "..." --solucao "..."
```

Use `--solicitante "Nome"` só quando outra pessoa pediu aquilo. Depois faça o commit do `ATUALIZACOES.md` junto com a mudança.

---

## v3.9.5.0 · Melhoria · 2026-11-17 12:23

**Health: modos de visualização Compacto, Médio, Normal e Foco**

- **Commits:** frontend `2a95d32`

**Problema:** Com muitas automações, os cards da Health ocupavam espaço demais e era difícil ver tudo numa tela só.

**Solução:** Novo modo **Compacto** (só nome, status e próxima execução). O antigo Compacto passou a se chamar **Médio**, e existem ainda Normal e Foco. Os botões de visualização ficaram mais baixos e sem o texto embaixo.

<details>
<summary>Arquivos alterados (1)</summary>

- `M` frontend · `src/pages/health/automation-health-page.tsx`

</details>

---

## v3.9.4.0 · Melhoria · 2026-11-17 10:12

**Login: botão "Entrar com a conta Microsoft" (SSO)**

- **Commits:** frontend `387fafb`

**Problema:** O login só aceitava usuário e senha do Regente, sem caminho previsto para o acesso com a conta corporativa Microsoft.

**Solução:** A tela de login ganhou o botão **Entrar com a conta Microsoft** abaixo do Entrar. Ele fica apagado até a TI liberar o acesso (SSO).

<details>
<summary>Arquivos alterados (1)</summary>

- `M` frontend · `src/pages/auth/login-page.tsx`

</details>

---

## v3.9.3.0 · Melhoria · 2026-11-17 10:02

**Tasks: tabela sem a coluna Prioridade e sem rolagem horizontal**

- **Commits:** frontend `d203257`

**Problema:** A tabela de tasks tinha colunas demais e criava rolagem horizontal, o que dificultava a leitura.

**Solução:** A coluna **Prioridade** saiu da tabela. Etapa e pedido continuam visíveis.

<details>
<summary>Arquivos alterados (1)</summary>

- `M` frontend · `src/pages/tasks/tasks-page.tsx`

</details>

---

## v3.9.2.0 · Melhoria · 2026-11-17 09:30

**Liberar acesso: avisar que um usuário bloqueado já está ok**

- **Commits:** backend `f554718` · frontend `296fc1a`

**Problema:** Quando o acesso de um usuário a um sistema era bloqueado, os robôs não tinham como saber que o problema já tinha sido resolvido, e continuavam evitando ou tentando novamente o mesmo login.

**Solução:** Nova tela em **Segurança** para avisar que um usuário bloqueado já está ok, com histórico de quem liberou e quando. Os robôs recebem `LIBERACOES_DE_ACESSO` (login e horário UTC das últimas 48 h) junto com as variáveis. Não foi criada tabela nova: os dados ficam em `system_settings`. Documentação em `LIBERACAO_DE_ACESSO.md`.

<details>
<summary>Arquivos alterados (13)</summary>

- `A` backend · `LIBERACAO_DE_ACESSO.md`
- `M` backend · `app/api/router.py`
- `A` backend · `app/api/v1/access_releases.py`
- `M` backend · `app/integration/api_guide.py`
- `A` backend · `app/schemas/access_release.py`
- `A` backend · `app/services/access_release_service.py`
- `M` backend · `app/services/env_variable_service.py`
- `A` backend · `tests/test_access_releases.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/lib/navigation.ts`
- `A` frontend · `src/pages/access-releases/access-releases-page.tsx`
- `A` frontend · `src/services/api/access-releases.ts`
- `A` frontend · `src/types/access-release.ts`

</details>

---

## v3.9.1.0 · Melhoria · 2026-11-17 08:34

**Credenciais: lista de bloqueadas e botão Desbloquear**

- **Commits:** backend `df374a4` · frontend `54e75e2`

**Problema:** Quando uma credencial era bloqueada (por exemplo, por senha expirada), não havia onde ver todas as bloqueadas de uma vez nem um jeito de desbloquear manualmente. O desbloqueio também não era registrado quando a senha era trocada.

**Solução:** Um cartão de **credenciais bloqueadas** passou a aparecer na lista e no detalhe, com botão **Desbloquear** e confirmação. Trocar a senha também passa a registrar o desbloqueio.

<details>
<summary>Arquivos alterados (12)</summary>

- `M` backend · `app/api/v1/credentials.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/schemas/credential.py`
- `M` backend · `app/services/credential_health_service.py`
- `M` backend · `app/services/credential_service.py`
- `A` backend · `tests/test_credential_unblock.py`
- `A` frontend · `src/pages/credentials/blocked-credentials-card.tsx`
- `M` frontend · `src/pages/credentials/credential-detail-page.tsx`
- `M` frontend · `src/pages/credentials/credentials-page.tsx`
- `A` frontend · `src/pages/credentials/use-unblock-credential.tsx`
- `M` frontend · `src/services/api/credentials.ts`
- `M` frontend · `src/types/credential.ts`

</details>

---

## v3.9.0.1 · Correção · 2026-11-04 22:05

**Deadlocks no DW-ALZ: worker vivo gravado antes de mexer em tasks e locks**

- **Commits:** backend `d4336bb`, `9860170`, `5db54dc`

**Problema:** O banco DW-ALZ registrava deadlocks entre runners, tasks e locks, causados pela ordem em que o worker gravava essas informações no heartbeat. Isso derrubava operações e gerava erros intermitentes.

**Solução:** O "worker vivo" (`last_heartbeat`) agora é gravado e confirmado antes de tocar em tasks e locks, e o heartbeat renova os locks depois de soltar o runner. Foi criado um script para capturar deadlocks, usado na medição e retirado do DW-ALZ ao final. O arquivo `HOLDLOCK.md` registra o que houve, o que mudou, como testar, como desfazer e os próximos passos.

<details>
<summary>Arquivos alterados (4)</summary>

- `A` backend · `HOLDLOCK.md`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `scripts/deadlocks_dwalz.py`
- `A` backend · `tests/test_worker_lock_order.py`

</details>

---

## v3.9.0.0 · Geral · 2026-11-04 18:40

**Database Status dentro do Regente, com alertas dos bancos**

- **Commits:** backend `5b5b910`, `05dcf39` · frontend `ec21220`

**Problema:** O acompanhamento da saúde dos bancos de dados era feito numa ferramenta separada (DatabaseStatus), fora do Regente, com login e visual próprios. Os problemas de banco também não apareciam junto dos demais avisos do painel.

**Solução:** O módulo foi trazido para dentro do backend, com rota protegida para administradores e desligado por padrão. No painel, a página original aparece embutida com as cores do Regente e o login do painel, e o menu **Status** e **Operation** ficou em inglês. A rota de alertas usa o mesmo critério da tela original (conferido contra a função original em 12 casos), com leitura direta como alternativa se o Azure Monitor falhar. Um banco com problema agora aparece ao lado dos avisos de erro, runner e task parada.

<details>
<summary>Arquivos alterados (16)</summary>

- `M` backend · `app/api/router.py`
- `A` backend · `app/api/v1/dbstatus.py`
- `M` backend · `app/core/config.py`
- `A` backend · `app/dbstatus/__init__.py`
- `A` backend · `app/dbstatus/service.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/main.py`
- `A` backend · `tests/test_dbstatus.py`
- `A` frontend · `public/dbstatus/index.html`
- `M` frontend · `public/staticwebapp.config.json`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/components/layout/system-health-banner.tsx`
- `M` frontend · `src/hooks/use-system-health.ts`
- `M` frontend · `src/lib/navigation.ts`
- `A` frontend · `src/pages/dbstatus/database-status-page.tsx`
- `A` frontend · `src/services/api/dbstatus.ts`

</details>

---

## v3.8.15.2 · Correção · 2026-11-04 17:08

**Banco: consulta de tasks por máquina passa a usar o índice até o fim**

- **Commits:** backend `d5e6125`

**Problema:** Em consultas que filtram por status, o parâmetro era enviado ao banco num tipo diferente do da coluna, e o banco não conseguia aproveitar o índice por inteiro. Isso gerava leituras em excesso e carga desnecessária no Azure SQL.

**Solução:** Os parâmetros de status (e similares) passam a ir como texto igual ao da coluna. Na checagem de tasks por máquina, as leituras caíram de 412 para 9.

<details>
<summary>Arquivos alterados (3)</summary>

- `M` backend · `app/core/database.py`
- `A` backend · `app/core/sql_types.py`
- `A` backend · `tests/test_sql_types.py`

</details>

---

## v3.8.15.1 · Correção · 2026-11-04 16:50

**Health: tasks agendadas para o futuro aparecem como "Agendada"**

- **Commits:** backend `7a1abfc` · frontend `2f01a6c`

**Problema:** Uma task agendada para o futuro, que ainda não tinha rodado, aparecia como "Atrasado" na Health, e a coluna de última execução mostrava a hora de criação da task, como se ela já tivesse rodado.

**Solução:** A Health ganhou o status **Agendada** (azul claro, com o horário previsto) para tasks que ainda vão rodar. A última execução fica vazia enquanto nada rodou.

<details>
<summary>Arquivos alterados (7)</summary>

- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/schemas/automation_health.py`
- `M` backend · `app/services/automation_health_service.py`
- `M` backend · `tests/test_health_last_tasks.py`
- `M` frontend · `src/lib/health-visual.ts`
- `M` frontend · `src/pages/health/automation-health-page.tsx`
- `M` frontend · `src/services/api/automation-health.ts`

</details>

---

## v3.8.15.0 · Melhoria · 2026-11-04 12:08

**Dashboard: gráfico de carga por hora do dia (geral e por máquina)**

- **Commits:** backend `5d5208e`, `56b5f96` · frontend `2a8a0af`, `eae8c23`, `da8f6a1`, `61c785e`

**Problema:** O dashboard mostrava as execuções, mas não deixava ver em quais horas do dia o sistema e cada máquina ficavam mais carregados, o que atrapalha distribuir os horários dos robôs.

**Solução:** Novo gráfico de **carga por hora** (horário de Brasília), geral e por máquina, que pode ser lido em minutos rodando ou em tasks iniciadas, com mapa de máquina por hora. Ele segue o período escolhido no topo e entra no botão Atualizar. No período de 24 h usa janela deslizante (de ontem nesta hora até agora), na mesma ordem do gráfico de execuções. O texto explica o que cada número significa e a diferença para o gráfico de execuções.

<details>
<summary>Arquivos alterados (9)</summary>

- `M` backend · `app/api/v1/dashboard.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/repositories/dashboard_repository.py`
- `M` backend · `app/schemas/dashboard.py`
- `M` backend · `app/services/dashboard_service.py`
- `A` backend · `tests/test_dashboard_hourly_load.py`
- `M` frontend · `src/pages/dashboard/dashboard-page.tsx`
- `A` frontend · `src/pages/dashboard/hourly-load-card.tsx`
- `M` frontend · `src/services/api/dashboard.ts`

</details>

---

## v3.8.14.0 · Melhoria · 2026-10-30 13:45

**Sync: tela por usuário com os mesmos cards e filtros da Health**

- **Commits:** frontend `d1ef78d`

**Problema:** Não havia uma forma de conferir, por usuário, se as automações dele estavam sincronizadas e saudáveis. A opção Sync do perfil e a tela inicial ainda não reaproveitavam o visual conhecido da Health.

**Solução:** A tela **Sync** usa a própria tela de Health, com os mesmos cards, cores, filtros e modo Foco, limitada às automações do usuário. Ganhou botões extras e mostra os sistemas externos como cards do mesmo molde.

<details>
<summary>Arquivos alterados (3)</summary>

- `A` frontend · `src/lib/health-visual.ts`
- `M` frontend · `src/pages/health/automation-health-page.tsx`
- `M` frontend · `src/pages/sync/sync-page.tsx`

</details>

---

## v3.8.13.0 · Melhoria · 2026-10-30 13:09

**Configurações: aba Works com versão do worker e atualização pelo painel**

- **Commits:** backend `ff5afd6` · frontend `d01b5d4` · worker `f2af89c`, `e06255d`, `be6909b`

**Problema:** Para saber qual versão do worker estava em cada máquina e atualizá-lo, era preciso acessar as máquinas uma a uma. Além disso, o dispatcher podia sobrescrever uma task que o worker já tinha assumido, o que gerava inconsistências na fila.

**Solução:** As Configurações ganharam as abas **Ambientes** e **Works**. Cada worker informa a versão (commit) no heartbeat, e a aba Works mostra a versão de cada máquina e permite pedir a atualização pelo painel. O worker atende o pedido sem pegar tasks novas, reinicia quando está ocioso (uma vez por pedido) e sai na hora ao atender, também quando está rodando sob o supervisor no Windows. O dispatcher deixou de sobrescrever task já assumida pelo worker.

<details>
<summary>Arquivos alterados (38)</summary>

- `A` backend · `alembic/versions/c0d2e4f6a8b1_worker_versao_e_sync.py`
- `M` backend · `app/api/router.py`
- `M` backend · `app/api/v1/settings.py`
- `A` backend · `app/api/v1/sync.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/models/__init__.py`
- `M` backend · `app/models/runner.py`
- `A` backend · `app/models/sync_check.py`
- `A` backend · `app/models/system_setting.py`
- `M` backend · `app/models/user.py`
- `M` backend · `app/schemas/runner.py`
- `A` backend · `app/schemas/sync.py`
- `M` backend · `app/schemas/user.py`
- `M` backend · `app/schemas/worker.py`
- `A` backend · `app/schemas/worker_release.py`
- `M` backend · `app/services/dispatch_service.py`
- `A` backend · `app/services/sync_service.py`
- `A` backend · `app/services/worker_release_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_dispatch_race.py`
- `A` backend · `tests/test_worker_release_and_sync.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/components/common/command-palette.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/lib/navigation.ts`
- `M` frontend · `src/pages/profile/profile-page.tsx`
- `M` frontend · `src/pages/settings/settings-page.tsx`
- `A` frontend · `src/pages/settings/workers-tab.tsx`
- `A` frontend · `src/pages/sync/sync-page.tsx`
- `M` frontend · `src/services/api/settings.ts`
- `A` frontend · `src/services/api/sync.ts`
- `M` frontend · `src/services/api/users.ts`
- `M` frontend · `src/types/auth.ts`
- `M` worker · `app/runtime/main.py`
- `A` worker · `app/runtime/self_update.py`
- `M` worker · `app/runtime/services.py`
- `M` worker · `app/runtime/task_client.py`
- `A` worker · `tests/test_self_update.py`

</details>

---

## v3.8.12.1 · Correção · 2026-10-30 11:44

**Worker: task que travava ao iniciar agora vira erro com motivo claro**

- **Commits:** backend `3e9cd10` · worker `b6d65fd`

**Problema:** Algumas tasks ficavam presas como "em execução" logo no início, porque o worker travava ao tirar o print de tela, e o sistema só reconhecia a falha quando o timeout inteiro da task terminava. Quem operava ficava sem saber o que tinha acontecido.

**Solução:** O primeiro print passou a ser feito por uma linha de execução separada, e o print final tem prazo e não segura mais o restante do trabalho. O worker registra "Execução local iniciada" como primeiro sinal de vida. No servidor, uma task em execução sem nenhum sinal do worker por 3 minutos passa a ser marcada com erro e um motivo claro, sem esperar o timeout.

<details>
<summary>Arquivos alterados (6)</summary>

- `M` backend · `app/services/task_rules.py`
- `M` backend · `app/services/watchdog_service.py`
- `M` backend · `tests/test_concurrency_watchdog.py`
- `M` worker · `app/runtime/screenshot_reporter.py`
- `M` worker · `app/runtime/task_executor.py`
- `A` worker · `tests/test_screenshot_reporter.py`

</details>

---

## v3.8.12.0 · Melhoria · 2026-10-30 10:22

**Eventos: histórico de disparos abre em janela no centro da tela**

- **Commits:** frontend `d580124`

**Problema:** O histórico de disparos de um evento abria numa gaveta lateral, que ocupava pouco espaço e dificultava a leitura de listas maiores.

**Solução:** O histórico agora abre numa janela (modal) no centro da tela, com mais espaço para consultar os disparos.

<details>
<summary>Arquivos alterados (1)</summary>

- `M` frontend · `src/pages/events/event-runs-drawer.tsx`

</details>

---

## v3.8.11.0 · Melhoria · 2026-10-29 09:28

**Marca Regente: nova identidade visual no painel**

- **Commits:** frontend `ea33745`, `04d8589`, `e216038`

**Problema:** O painel ainda aparecia com o nome e a aparência antigos (OrkaFlow), sem identidade própria na aba do navegador, na barra lateral e na tela de login. Na barra lateral, o nome da marca chegava a ter o topo da letra R cortado.

**Solução:** O sistema passa a se apresentar como **Regente**: favicon, título da página, logo da barra lateral, tela de abertura e tela de login foram renovados. A versão (v3.0) aparece como selo na barra lateral e no login, o painel do login ficou mais escuro e com mais respiro, e o corte no nome foi corrigido.

<details>
<summary>Arquivos alterados (20)</summary>

- `M` frontend · `index.html`
- `A` frontend · `public/apple-touch-icon.png`
- `A` frontend · `public/brand/regente-icone-sobre-escuro.svg`
- `A` frontend · `public/brand/regente-icone.svg`
- `A` frontend · `public/favicon.ico`
- `M` frontend · `public/favicon.svg`
- `D` frontend · `public/favicon2.svg`
- `A` frontend · `public/icon-192.png`
- `A` frontend · `public/icon-512.png`
- `A` frontend · `public/icon-maskable-512.png`
- `D` frontend · `public/icons.svg`
- `D` frontend · `public/icons2.svg`
- `D` frontend · `public/orkaflow-icon.ico`
- `D` frontend · `public/orkaflow-icon.png`
- `A` frontend · `public/site.webmanifest`
- `M` frontend · `src/app/providers/auth-provider.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/lib/navigation.ts`
- `M` frontend · `src/pages/auth/login-page.tsx`
- `M` frontend · `tailwind.config.js`

</details>

---

## v3.8.10.0 · Melhoria · 2026-10-28 18:28

**Ambientes de Git: token por começo de link**

- **Commits:** backend `b9f3ca2`, `ec43411` · frontend `6774670`

**Problema:** O token do Git precisava estar embutido no link de cada bot, repetido em todos eles e visível a quem cadastrava. Links do DevOps com usuário sem senha (como `alzgraos@`) eram tratados como se já tivessem token.

**Solução:** Nova área em Configurações, "ambientes de Git", onde o administrador cadastra o token por começo de link. O bot pode ser cadastrado com o link limpo e usa o token do ambiente, e a tela avisa de onde o token vem. Vale para o worker, a prévia de versão e a inspeção do código. Link do DevOps com usuário sem senha mantém o usuário e o token do ambiente entra depois dele. Links com token dentro continuam funcionando como antes.

<details>
<summary>Arquivos alterados (21)</summary>

- `A` backend · `alembic/versions/b9c1d3e5f7a8_git_environments.py`
- `M` backend · `app/api/router.py`
- `M` backend · `app/api/v1/bots.py`
- `A` backend · `app/api/v1/settings.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/__init__.py`
- `A` backend · `app/models/git_environment.py`
- `A` backend · `app/schemas/git_environment.py`
- `M` backend · `app/services/bot_service.py`
- `M` backend · `app/services/bot_version_service.py`
- `A` backend · `app/services/git_environment_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_git_environments.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/lib/navigation.ts`
- `M` frontend · `src/pages/bots/bot-create-page.tsx`
- `M` frontend · `src/pages/bots/bot-edit-page.tsx`
- `A` frontend · `src/pages/bots/git-token-hint.tsx`
- `A` frontend · `src/pages/settings/settings-page.tsx`
- `A` frontend · `src/services/api/settings.ts`

</details>

---

## v3.8.9.0 · Melhoria · 2026-10-28 17:17

**Eventos com vários alvos e Health com modo Foco**

- **Commits:** frontend `963c64c` · backend `04d055b`

**Problema:** Uma regra de evento ou chamado só valia para um bot ou uma automação, obrigando a repetir a mesma regra várias vezes. O Health também era pouco útil num telão, e o detalhe do card era confuso.

**Solução:** Eventos e chamados podem valer para vários bots ou automações, com seletor múltiplo. O Health tem três modos de visualização (Compacto, Normal e Foco); o Foco mostra só os cards, sem filtros nem botões, para telão, com uma barra discreta para sair (ou Esc). O detalhe do card foi refeito com a situação, o agendamento e a última task lado a lado e ações para abrir a automação, ver a task e executar agora.

<details>
<summary>Arquivos alterados (11)</summary>

- `A` backend · `alembic/versions/a8b0c2d4e6f7_event_rule_scope_ids.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/event_rule.py`
- `M` backend · `app/schemas/event.py`
- `M` backend · `app/services/event_service.py`
- `A` backend · `tests/test_event_scope_ids.py`
- `M` frontend · `src/pages/events/event-form-page.tsx`
- `M` frontend · `src/pages/events/events-page.tsx`
- `M` frontend · `src/pages/health/automation-health-page.tsx`
- `M` frontend · `src/services/api/events.ts`

</details>

---

## v3.8.8.0 · Melhoria · 2026-10-28 17:11

**Runners, Health e MCP: carregamento com a cara da tela real**

- **Commits:** frontend `9355ddf`

**Problema:** Enquanto as telas de Runners, Health e MCP carregavam, o esqueleto não lembrava a tela final e repetia o texto abaixo do título, o que causava um salto visual.

**Solução:** O esqueleto de carregamento dessas telas agora tem o mesmo formato da tela real e sem o texto abaixo do título.

<details>
<summary>Arquivos alterados (4)</summary>

- `M` frontend · `src/components/common/skeleton.tsx`
- `M` frontend · `src/pages/health/automation-health-page.tsx`
- `M` frontend · `src/pages/integration/integration-mcp-page.tsx`
- `M` frontend · `src/pages/runners/runners-page.tsx`

</details>

---

## v3.8.7.0 · Melhoria · 2026-10-28 10:41

**Erro explicado pelo Maestro: mensagem limpa e stacktrace legível**

- **Commits:** worker `9912011`

**Problema:** Quando um robô com Maestro falhava, a mensagem do erro vinha com o código de saída, e o stacktrace misturava as linhas internas do protocolo do Maestro, o que atrapalhava entender a causa.

**Solução:** A mensagem do erro passa a ser só a explicação dada pelo robô. O stacktrace usa o traceback enviado pelo robô, sem as linhas internas do protocolo. Erro de negócio (fail) fica só com a mensagem. Robôs sem Maestro não mudam.

<details>
<summary>Arquivos alterados (3)</summary>

- `M` worker · `app/runtime/maestro_events.py`
- `M` worker · `app/runtime/task_executor.py`
- `A` worker · `tests/test_maestro_error_text.py`

</details>

---

## v3.8.6.0 · Melhoria · 2026-10-28 10:28

**Máquina: usuário de acesso e usuário do Windows do worker**

- **Commits:** backend `12f3f16` · frontend `7a62b0c` · worker `33cdfb2`

**Problema:** Na tela da máquina não era possível registrar com qual usuário se acessa a máquina, e não se sabia em qual usuário do Windows o worker estava de fato rodando. A tela também era difícil de ler.

**Solução:** O cadastro da máquina ganhou o "usuário de acesso" editável no topo, e o worker informa o usuário do Windows (`DOMINIO\usuario`) no sinal de vida. A tela da máquina foi reorganizada: cartões no topo, métricas, execução e histórico na coluna principal, fila, configuração e bots ao lado, e os detalhes técnicos recolhidos. Workers antigos não apagam o valor já informado.

<details>
<summary>Arquivos alterados (15)</summary>

- `A` backend · `alembic/versions/f7a9b1c3d5e6_runner_users.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/runner.py`
- `M` backend · `app/schemas/runner.py`
- `M` backend · `app/schemas/runner_overview.py`
- `M` backend · `app/schemas/worker.py`
- `M` backend · `app/services/runner_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_runner_users.py`
- `M` frontend · `src/pages/runners/runner-detail-page.tsx`
- `M` frontend · `src/services/api/runners.ts`
- `M` worker · `app/runtime/services.py`
- `M` worker · `app/runtime/task_client.py`
- `A` worker · `tests/test_runner_os_user.py`

</details>

---

## v3.8.5.0 · Melhoria · 2026-10-28 09:22

**Repositórios: desativar um repositório desativa seus bots e automações**

- **Commits:** backend `b4c0d69` · frontend `acf1b78`

**Problema:** Desativar um repositório não desativava os bots e automações dele, que seguiam agendados e podiam continuar rodando. A tela também não avisava isso.

**Solução:** Desativar o repositório agora desativa em cascata seus bots e automações. Reativar o repositório não reativa os filhos, que precisam ser religados conscientemente. A tela de Repositórios avisa disso antes de confirmar. O MCP (versão 1.2.0) passou a devolver o print do erro e a tela da máquina como imagem.

<details>
<summary>Arquivos alterados (7)</summary>

- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/mcp/server.py`
- `M` backend · `app/mcp/tools.py`
- `M` backend · `app/services/repository_service.py`
- `A` backend · `tests/test_repository_cascade_and_mcp_images.py`
- `M` frontend · `src/pages/repositories/repositories-page.tsx`

</details>

---

## v3.8.4.0 · Melhoria · 2026-10-27 19:24

**Manutenção: máquina marcada em manutenção devolve a fila**

- **Commits:** backend `195b689`

**Problema:** Ao colocar uma máquina em manutenção, as tasks que já estavam esperando nela continuavam presas àquela máquina, sem poder rodar em outra.

**Solução:** Ao marcar manutenção, as tasks em espera ligadas à máquina voltam para a fila na hora, com motivo e registro no log, para outra máquina pegar. O que já está executando termina normalmente. O MCP foi atualizado (versão 1.1.0) com os assuntos Maestro e novidades de outubro.

<details>
<summary>Arquivos alterados (5)</summary>

- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/mcp/server.py`
- `M` backend · `app/services/runner_service.py`
- `M` backend · `app/services/task_rules.py`
- `M` backend · `tests/test_maintenance_and_chain_guards.py`

</details>

---

## v3.8.3.0 · Melhoria · 2026-10-27 19:11

**Guia do Bot refeito com Maestro e instalação pelo repositório**

- **Commits:** backend `2182019`, `1e9259a` · frontend `47f71af`, `d68bc49`, `b779bfa` · worker `79beefb`

**Problema:** O Guia do Bot estava desatualizado e não explicava o caminho completo, do robô na máquina até a automação agendada. Faltava orientar sobre senha vencida no SAP e sobre como instalar o Maestro.

**Solução:** O guia foi refeito com a jornada em passos (montar a main, testar na máquina, Git, cadastrar bot, automação, rodar ou agendar), exemplos lado a lado com Maestro e com JSON, a seção "Senha vencida no SAP: avise, não insista", o Guia do Maestro com todas as chamadas, um checklist antes de publicar e botão de copiar nos blocos de código. O Maestro passa a ser instalado pelo repositório `github.com/tharlescunha/maestro`, e a documentação explica como instalar e atualizar.

<details>
<summary>Arquivos alterados (9)</summary>

- `M` backend · `docs/GUIA_DO_BOT_AJUSTES.md`
- `M` backend · `docs/MAESTRO_DESENHO.md`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/lib/navigation.ts`
- `A` frontend · `src/pages/guide/bot-guide-code.ts`
- `A` frontend · `src/pages/guide/bot-guide-page.tsx`
- `A` frontend · `src/pages/guide/code-highlight.ts`
- `D` frontend · `src/pages/runner-config/worker-registration-page.tsx`
- `M` worker · `maestro/README.md`

</details>

---

## v3.8.2.0 · Melhoria · 2026-10-27 18:04

**Maestro: anexos da task e chamada de outra automação pelo nome**

- **Commits:** backend `90bf8c8` · frontend `32f8605` · worker `f3734e5`, `820140a`

**Problema:** Os robôs não tinham como devolver arquivos gerados (relatórios, planilhas) para quem acompanha a task, e a chamada de outra automação descartava os padrões de execução da automação de destino. Os contadores de itens processados também não eram preenchidos pelo robô.

**Solução:** O robô pode anexar arquivos à task (até 5 MB cada, 10 por task) e a tela da task mostra a seção "Arquivos anexados pelo robô" com download. Ao chamar outra automação pelo nome, ela leva os parâmetros, credenciais e padrões dela, e o robô só sobrescreve o que quiser. Os itens processados e com falha informados ao encerrar preenchem os contadores da task. O editor passa a mostrar a descrição de cada chamada do `maestro` ao digitar.

<details>
<summary>Arquivos alterados (27)</summary>

- `A` backend · `alembic/versions/e6a8b0c2d4f5_task_attachments.py`
- `M` backend · `app/api/v1/tasks.py`
- `M` backend · `app/api/v1/worker_tasks.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/models/__init__.py`
- `M` backend · `app/models/task.py`
- `A` backend · `app/models/task_attachment.py`
- `M` backend · `app/schemas/task.py`
- `M` backend · `app/schemas/worker.py`
- `M` backend · `app/services/automation_trigger_service.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/worker_service.py`
- `M` backend · `docs/MAESTRO_DESENHO.md`
- `M` backend · `tests/test_maestro_backend.py`
- `A` backend · `tests/test_task_attachments.py`
- `M` frontend · `src/pages/tasks/task-detail-page.tsx`
- `M` frontend · `src/services/api/tasks.ts`
- `M` worker · `app/runtime/maestro_events.py`
- `M` worker · `app/runtime/task_client.py`
- `M` worker · `app/runtime/task_executor.py`
- `M` worker · `maestro/maestro/core.py`
- `M` worker · `maestro/maestro/protocol.py`
- `A` worker · `maestro/maestro/py.typed`
- `M` worker · `maestro/pyproject.toml`
- `M` worker · `tests/test_maestro.py`
- `A` worker · `tests/test_maestro_attach.py`
- `M` worker · `tests/test_maestro_worker.py`

</details>

---

## v3.8.1.0 · Melhoria · 2026-10-27 17:25

**Maestro: etapa da task, print do erro e robô sem argumento de arquivo**

- **Commits:** backend `c037760` · frontend `b1742c4` · worker `842b96b`

**Problema:** Durante a execução não dava para saber em que ponto o robô estava, e quando ele falhava ninguém via a tela do momento do erro. Os robôs novos também eram obrigados a receber um argumento de arquivo que não usam.

**Solução:** A task mostra "Etapa N de M" com o texto enquanto roda, na lista e no detalhe, e o detalhe ganha a seção "Tela no momento do erro" com o print tirado pelo robô. Um robô pode chamar outra automação ativa do mesmo repositório pelo nome. No cadastro do bot, a caixa "Robô lê o arquivo da task por argumento (robô antigo)" vem desmarcada para bots novos; bots existentes continuam como estavam.

<details>
<summary>Arquivos alterados (27)</summary>

- `A` backend · `alembic/versions/d5f7a9b1c3e4_maestro_progress_and_bot_arg.py`
- `M` backend · `app/api/v1/worker_tasks.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/models/bot.py`
- `M` backend · `app/models/task.py`
- `M` backend · `app/models/task_error.py`
- `M` backend · `app/repositories/runner_repository.py`
- `M` backend · `app/schemas/bot.py`
- `M` backend · `app/schemas/task.py`
- `M` backend · `app/schemas/worker.py`
- `M` backend · `app/services/automation_trigger_service.py`
- `M` backend · `app/services/bot_service.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_maestro_backend.py`
- `M` frontend · `src/pages/bots/bot-create-page.tsx`
- `M` frontend · `src/pages/bots/bot-detail-page.tsx`
- `M` frontend · `src/pages/bots/bot-edit-page.tsx`
- `M` frontend · `src/pages/tasks/task-detail-page.tsx`
- `M` frontend · `src/pages/tasks/tasks-page.tsx`
- `M` frontend · `src/services/api/task-errors.ts`
- `M` frontend · `src/services/api/tasks.ts`
- `M` frontend · `src/types/bot.ts`
- `M` worker · `app/core/config_models.py`
- `M` worker · `app/runtime/task_client.py`
- `M` worker · `app/runtime/task_executor.py`
- `M` worker · `app/sync/bot_sync.py`

</details>

---

## v3.8.0.0 · Geral · 2026-10-27 16:53

**Maestro: biblioteca para os robôs e worker que entende as chamadas**

- **Commits:** backend `a8c6b5c` · worker `0c7e752`

**Problema:** Cada robô precisava montar à mão a comunicação com o Regente (logs, resultado, aviso de senha, print do erro), cada um de um jeito, o que dava código repetido e erros difíceis de explicar.

**Solução:** Nova biblioteca `maestro` para o robô, sem dependências: registrar mensagens e etapas, ler parâmetros e credenciais, tirar print, enviar sinal de vida e encerrar com sucesso ou falha, tudo com poucas linhas. O worker interpreta essas chamadas e instala a biblioteca no ambiente de cada bot sem precisar de internet. Há um modo local para testar o robô fora do Regente e um desenho do Maestro documentado. Robôs antigos continuam funcionando sem mudanças.

<details>
<summary>Arquivos alterados (16)</summary>

- `A` backend · `docs/MAESTRO_DESENHO.md`
- `A` worker · `app/runtime/maestro_events.py`
- `M` worker · `app/runtime/task_client.py`
- `M` worker · `app/runtime/task_executor.py`
- `M` worker · `app/sync/bot_installer.py`
- `M` worker · `app/sync/bot_sync.py`
- `A` worker · `app/sync/maestro_install.py`
- `A` worker · `maestro/README.md`
- `A` worker · `maestro/maestro/__init__.py`
- `A` worker · `maestro/maestro/__main__.py`
- `A` worker · `maestro/maestro/capture.py`
- `A` worker · `maestro/maestro/core.py`
- `A` worker · `maestro/maestro/protocol.py`
- `A` worker · `maestro/pyproject.toml`
- `A` worker · `tests/test_maestro.py`
- `A` worker · `tests/test_maestro_worker.py`

</details>

---

## v3.7.17.0 · Melhoria · 2026-10-27 15:56

**Grupos exclusivos: detalhe, edição, exclusão e quem está usando agora**

- **Commits:** backend `6373f77` · frontend `df9e5b6`

**Problema:** Os grupos exclusivos (automações que não podem rodar ao mesmo tempo) só podiam ser criados. Não dava para editar, desativar, excluir nem ver qual task estava segurando o grupo.

**Solução:** Nova tela Automação, Grupos exclusivos, com lista, formulário e a informação "em uso agora" (task, automação, máquina e desde quando), atualizada a cada 15 segundos. Dá para mudar nome, descrição, status e as automações do grupo, e excluir grupos sem membros. Desativar um grupo não derruba nada que esteja em execução.

<details>
<summary>Arquivos alterados (12)</summary>

- `M` backend · `app/api/v1/automations.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/repositories/automation_exclusive_group_repository.py`
- `M` backend · `app/schemas/automation.py`
- `M` backend · `app/services/automation_service.py`
- `A` backend · `tests/test_exclusive_groups.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/lib/navigation.ts`
- `A` frontend · `src/pages/exclusive-groups/exclusive-group-form-page.tsx`
- `A` frontend · `src/pages/exclusive-groups/exclusive-groups-page.tsx`
- `A` frontend · `src/services/api/exclusive-groups.ts`

</details>

---

## v3.7.16.0 · Melhoria · 2026-10-27 15:19

**Eventos: regras "Quando → Então" por robô**

- **Commits:** backend `cf880ac` · frontend `fb86bce`, `4575c97`

**Problema:** Não havia como reagir automaticamente ao resultado de um robô, por exemplo avisar outro sistema quando uma task termina com erro. A tela "Notificações" só abria chamado no desk, o que confundia com o recurso configurável.

**Solução:** Nova tela Eventos, no menu Integração: você escolhe a automação, o bot ou qualquer um, o gatilho (erro, sucesso, timeout, credencial inválida, retorno com determinado valor, código de saída) e o que fazer, que é uma requisição HTTP com variáveis da task e etapas prévias, como um login. Há teste imediato com a última task e histórico de cada disparo. Um erro no disparo nunca afeta a task. O menu "Notificações" passou a se chamar "Chamado de erro".

<details>
<summary>Arquivos alterados (23)</summary>

- `A` backend · `alembic/versions/f1b3d5e7a9c2_event_rules.py`
- `M` backend · `app/api/router.py`
- `A` backend · `app/api/v1/events.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/__init__.py`
- `A` backend · `app/models/event_rule.py`
- `A` backend · `app/schemas/event.py`
- `A` backend · `app/services/event_service.py`
- `M` backend · `app/services/notification_service.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/watchdog_service.py`
- `M` backend · `app/services/worker_service.py`
- `M` backend · `app/workers/notifications_main.py`
- `A` backend · `tests/test_events.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/lib/navigation.ts`
- `A` frontend · `src/pages/events/event-form-page.tsx`
- `A` frontend · `src/pages/events/event-runs-drawer.tsx`
- `A` frontend · `src/pages/events/event-utils.ts`
- `A` frontend · `src/pages/events/events-page.tsx`
- `M` frontend · `src/pages/notifications/notifications-page.tsx`
- `A` frontend · `src/services/api/events.ts`

</details>

---

## v3.7.15.0 · Melhoria · 2026-10-27 15:08

**Fila: motivo da espera e encadeamento de tasks visíveis**

- **Commits:** backend `9ce177d` · frontend `0996569`

**Problema:** Uma task parada na fila não dizia por que não andava (automação já em execução, grupo exclusivo ocupado, nenhuma máquina disponível). Além disso, a task da frente da fila podia travar a fila inteira, e não dava para ver quais tasks foram disparadas por outra.

**Solução:** A lista e o detalhe da task mostram "Por que está na fila", e o orquestrador registra o motivo no log no máximo uma vez por hora. A candidata presa é pulada e deixa de travar as demais. Tasks disparadas pelo gatilho de sucesso mostram "Disparada pela task #N" com link, e a task de origem lista as tasks que ela disparou.

<details>
<summary>Arquivos alterados (17)</summary>

- `A` backend · `alembic/versions/c4e6a8b0d2f3_task_waiting_reason.py`
- `M` backend · `app/domain/enums.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/task.py`
- `M` backend · `app/repositories/task_repository.py`
- `M` backend · `app/schemas/task.py`
- `M` backend · `app/services/automation_trigger_service.py`
- `M` backend · `app/services/dispatch_service.py`
- `A` backend · `app/services/queue_reasons.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_queue_reasons.py`
- `M` frontend · `src/components/common/task-stuck-badge.tsx`
- `M` frontend · `src/pages/tasks/task-detail-page.tsx`
- `M` frontend · `src/pages/tasks/tasks-page.tsx`
- `M` frontend · `src/services/api/tasks.ts`

</details>

---

## v3.7.14.0 · Melhoria · 2026-10-27 14:15

**Agendamento: "no N-ésimo dia útil do mês às HH:MM"**

- **Commits:** backend `d724f30` · frontend `d7e05f9`

**Problema:** Rotinas de fechamento, que rodam por exemplo no 5º dia útil do mês, não podiam ser agendadas. Era preciso corrigir a data à mão todo mês.

**Solução:** O agendamento ganhou a opção "No N-ésimo dia útil do mês" (do 1º ao 23º) com horário. Os dias úteis e feriados vêm do calendário do agendamento, ou de segunda a sexta se não houver calendário. O Health mostra "Dia útil N do mês às HH:MM". Ao criar o agendamento ele não roda na hora, só na primeira ocorrência futura.

<details>
<summary>Arquivos alterados (13)</summary>

- `M` backend · `alembic/versions/b3d5f7a9c1e2_calendars.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/schedule.py`
- `M` backend · `app/schemas/schedule.py`
- `M` backend · `app/services/automation_health_service.py`
- `M` backend · `app/services/calendar_service.py`
- `M` backend · `app/services/schedule_service.py`
- `M` backend · `app/services/scheduler_engine_service.py`
- `A` backend · `tests/test_business_day.py`
- `M` frontend · `src/pages/schedules/schedule-form-page.tsx`
- `M` frontend · `src/pages/schedules/schedules-page.tsx`
- `M` frontend · `src/types/schedule.ts`

</details>

---

## v3.7.13.0 · Melhoria · 2026-10-27 13:57

**Calendários: dias úteis, feriados e janelas proibidas nos agendamentos**

- **Commits:** backend `58824b5` · frontend `a6e3fae`

**Problema:** Os agendamentos rodavam em qualquer dia e horário, inclusive em feriados e fora do expediente. Não havia como dizer que um robô não deve rodar em certos dias ou horários.

**Solução:** Nova tela de Calendários em Administração, com dias úteis da semana, feriados (com importação dos feriados nacionais do ano) e janelas de horário proibidas. No agendamento você escolhe o calendário e a política: adiar para o próximo horário permitido ou pular a execução. O Health não marca "atrasado" em dia não permitido. Agendamentos sem calendário continuam como antes.

<details>
<summary>Arquivos alterados (23)</summary>

- `A` backend · `alembic/versions/b3d5f7a9c1e2_calendars.py`
- `M` backend · `app/api/router.py`
- `A` backend · `app/api/v1/calendars.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/__init__.py`
- `A` backend · `app/models/calendar.py`
- `M` backend · `app/models/schedule.py`
- `A` backend · `app/schemas/calendar.py`
- `M` backend · `app/schemas/schedule.py`
- `M` backend · `app/services/automation_health_service.py`
- `A` backend · `app/services/calendar_service.py`
- `M` backend · `app/services/schedule_service.py`
- `M` backend · `app/services/scheduler_engine_service.py`
- `A` backend · `tests/test_calendars.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/lib/navigation.ts`
- `A` frontend · `src/pages/calendars/calendar-form-page.tsx`
- `A` frontend · `src/pages/calendars/calendar-utils.ts`
- `A` frontend · `src/pages/calendars/calendars-page.tsx`
- `M` frontend · `src/pages/schedules/schedule-form-page.tsx`
- `A` frontend · `src/services/api/calendars.ts`
- `M` frontend · `src/types/schedule.ts`

</details>

---

## v3.7.12.0 · Melhoria · 2026-10-27 13:36

**Agendamento: retentativa automática depois de erro ou timeout**

- **Commits:** backend `7821cd8` · frontend `5f3becc`

**Problema:** Quando uma execução agendada falhava por uma instabilidade passageira, ela só rodava de novo no próximo horário, ou alguém precisava disparar manualmente.

**Solução:** Cada agendamento tem agora o bloco "Retentativa automática": de 0 a 5 tentativas extras, tempo de espera e em quais falhas repetir (erro e/ou timeout). A nova tentativa usa os mesmos parâmetros e aparece na lista de tasks como "tentativa N". Não repete task cancelada, parada à força, com credencial inválida ou quando o agendamento está inativo, e o sistema recusa salvar se tentativas e espera não couberem no intervalo do agendamento.

<details>
<summary>Arquivos alterados (17)</summary>

- `A` backend · `alembic/versions/a2c4e6f8b0d1_automation_retry.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/schedule.py`
- `M` backend · `app/schemas/schedule.py`
- `M` backend · `app/schemas/task.py`
- `A` backend · `app/services/retry_service.py`
- `M` backend · `app/services/schedule_service.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/watchdog_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_retry.py`
- `M` frontend · `src/pages/schedules/schedule-form-page.tsx`
- `M` frontend · `src/pages/tasks/task-detail-page.tsx`
- `M` frontend · `src/pages/tasks/tasks-page.tsx`
- `M` frontend · `src/services/api/tasks.ts`
- `M` frontend · `src/types/schedule.ts`

</details>

---

## v3.7.11.0 · Melhoria · 2026-10-27 12:05

**Credenciais: o robô avisa senha vencida e o sistema pausa o que depende dela**

- **Commits:** worker `f66054b` · backend `47ec1b9` · frontend `f657fed`
- **Solicitante:** Fernando

**Problema:** Quando a senha de um sistema (como o SAP) vencia ou ficava bloqueada, o robô insistia e novas execuções continuavam sendo disparadas, o que podia bloquear o usuário. Ninguém via no sistema qual credencial estava com problema. Além disso, qualquer máquina conseguia resolver qualquer credencial pelo número.

**Solução:** O robô agora avisa o Regente quando a credencial está inválida. A credencial ganha status (válida, não verificada, senha incorreta, senha expirada, usuário bloqueado) com motivo, data e link para a task que detectou. Os agendamentos das automações que a usam são pausados e novas tasks são recusadas até a senha ser trocada, quando tudo volta sozinho. A lista de Credenciais, o detalhe da automação e o Health mostram o aviso. Senhas resolvidas aparecem como `***` no log, e a máquina e o repositório da automação passam a ser conferidos ao resolver uma credencial.

<details>
<summary>Arquivos alterados (35)</summary>

- `A` backend · `alembic/versions/e4a7c9d1b3f5_credential_health.py`
- `M` backend · `app/api/v1/worker_tasks.py`
- `M` backend · `app/domain/enums.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/models/credential.py`
- `M` backend · `app/models/schedule.py`
- `M` backend · `app/schemas/automation.py`
- `M` backend · `app/schemas/automation_health.py`
- `M` backend · `app/schemas/credential.py`
- `M` backend · `app/schemas/schedule.py`
- `M` backend · `app/schemas/worker.py`
- `M` backend · `app/services/automation_health_service.py`
- `M` backend · `app/services/automation_service.py`
- `A` backend · `app/services/credential_health_service.py`
- `M` backend · `app/services/credential_service.py`
- `M` backend · `app/services/scheduler_engine_service.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `docs/BIBLIOTECA_DO_BOT.md`
- `A` backend · `docs/GUIA_DO_BOT_AJUSTES.md`
- `M` backend · `tests/test_automation_list_queries.py`
- `A` backend · `tests/test_credential_health.py`
- `A` frontend · `src/components/common/credential-status.tsx`
- `A` frontend · `src/lib/credential-status.ts`
- `M` frontend · `src/pages/automations/automation-detail-page.tsx`
- `M` frontend · `src/pages/credentials/credential-detail-page.tsx`
- `M` frontend · `src/pages/credentials/credentials-page.tsx`
- `M` frontend · `src/pages/health/automation-health-page.tsx`
- `M` frontend · `src/services/api/automation-health.ts`
- `M` frontend · `src/services/api/automations.ts`
- `M` frontend · `src/types/credential.ts`
- `M` worker · `app/runtime/task_client.py`
- `M` worker · `app/runtime/task_executor.py`
- `M` worker · `tests/test_worker_core.py`

</details>

---

## v3.7.10.1 · Correção · 2026-10-27 10:38

**Modo manutenção da máquina vale de verdade e encadeamento não derruba a task**

- **Commits:** backend `7868cd5`

**Problema:** A caixa "Modo manutenção" do Runner Config só era gravada: a máquina continuava recebendo tasks. Além disso, um erro dentro do gatilho de sucesso podia desfazer a task já finalizada, e uma cadeia de automações em ciclo (A chama B que chama A) não era barrada.

**Solução:** Máquina em manutenção não recebe mais task nova (despacho, próxima task, assumir e criação manual) e aparece como "Manutenção" em vez de "Ocupada". O erro dentro de um gatilho de sucesso fica registrado no log e não desfaz a task concluída, e ciclos entre automações são barrados. O Dashboard também passou a mostrar série por hora ou por dia sem quebrar com datas sem fuso.

<details>
<summary>Arquivos alterados (11)</summary>

- `M` backend · `app/repositories/dashboard_repository.py`
- `M` backend · `app/schemas/dashboard.py`
- `M` backend · `app/services/automation_trigger_service.py`
- `M` backend · `app/services/dashboard_service.py`
- `M` backend · `app/services/dispatch_service.py`
- `M` backend · `app/services/runner_service.py`
- `M` backend · `app/services/task_rules.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/watchdog_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_maintenance_and_chain_guards.py`

</details>

---

## v3.7.10.0 · Melhoria · 2026-10-27 10:29

**Dashboard: tela operacional refeita em uma coluna só**

- **Commits:** frontend `533be1e`

**Problema:** O Dashboard repartia a informação em abas e repetia dados (taxa de sucesso e fila média apareciam em dois lugares, legendas duplicadas, várias cores por célula). Era difícil ver rápido o que estava acontecendo e o que pedia ação.

**Solução:** O Dashboard virou uma leitura de cima para baixo: "Agora" (executando, fila, máquinas, erros nas últimas 24 h), "Precisa de atenção" com link para cada item, gráfico por hora ou por dia no horário de Brasília, tabelas de máquinas (problemas primeiro) e de bots (mais falhas primeiro) e as últimas execuções. A taxa de sucesso passa a considerar só tasks concluídas.

<details>
<summary>Arquivos alterados (2)</summary>

- `M` frontend · `src/pages/dashboard/dashboard-page.tsx`
- `M` frontend · `src/services/api/dashboard.ts`

</details>

---

## v3.7.9.1 · Correção · 2026-10-27 08:17

**Bots: o token do link do Git deixa de aparecer no painel**

- **Commits:** backend `5294e21` · frontend `1dd5050`

**Problema:** Ao abrir ou editar um bot, o link do repositório Git aparecia com o token de acesso embutido. Qualquer pessoa com acesso à tela podia ver e copiar esse token.

**Solução:** O painel agora mostra o link com o token escondido (`***`) na lista, no detalhe e na edição, inclusive para versões antigas. O worker continua recebendo o link completo para baixar o robô. Salvar o bot com o link mascarado é recusado, para não apagar o token sem querer; o link só é reenviado quando você o troca.

<details>
<summary>Arquivos alterados (4)</summary>

- `M` backend · `app/schemas/bot_version.py`
- `M` backend · `app/services/bot_service.py`
- `M` backend · `tests/test_bot_source_inspect.py`
- `M` frontend · `src/pages/bots/bot-edit-page.tsx`

</details>

---

## v3.7.9.0 · Melhoria · 2026-10-26 22:45

**Novo bot: colar o link do Git, sincronizar e o painel preenche nome, descrição e versão**

- **Commits:** backend `dcbb843` · frontend `4f7b0a6`, `4489620`

**Problema:** Cadastrar um bot exigia preencher tudo à mão (nome, descrição, versão inicial), e um link do Git inválido ou sem acesso só dava erro depois, na máquina que ia executar o robô. Com a API do servidor desatualizada, a tela mostrava apenas "Method Not Allowed".

**Solução:** O primeiro passo agora é colar o link do repositório e clicar em **Sincronizar**: o sistema faz o mesmo clone que a máquina fará e traz nome, descrição (do README), último commit e última tag, usando a tag como versão inicial. Link inválido ou sem acesso aparece já nessa tela, os demais campos só liberam depois de validar o link, e mudar o link exige sincronizar de novo. Quando a API do servidor está desatualizada, a tela mostra uma mensagem clara.

<details>
<summary>Arquivos alterados (10)</summary>

- `M` backend · `app/api/v1/bots.py`
- `M` backend · `app/integration/api_guide.py`
- `M` backend · `app/mcp/playbooks.py`
- `M` backend · `app/schemas/bot.py`
- `M` backend · `app/services/git_repo_service.py`
- `A` backend · `tests/test_bot_source_inspect.py`
- `M` frontend · `src/lib/api-error.ts`
- `M` frontend · `src/pages/bots/bot-create-page.tsx`
- `M` frontend · `src/services/api/bots.ts`
- `M` frontend · `src/types/bot.ts`

</details>

---

## v3.7.8.0 · Melhoria · 2026-10-26 22:16

**Painel recarrega sozinho quando sai versão nova**

- **Commits:** frontend `0083115`

**Problema:** Depois de uma publicação, quem já estava com o painel aberto continuava usando a versão antiga e precisava forçar a atualização do navegador (Ctrl+Shift+R) para ver as mudanças ou evitar erros.

**Solução:** O painel compara a versão a cada minuto, ao voltar para a aba e ao trocar de tela, e recarrega sozinho na próxima troca de tela quando há versão nova. O `index.html` e o arquivo de versão deixam de ficar em cache, e há um histórico das cores anteriores e atuais para trocar depois.

<details>
<summary>Arquivos alterados (7)</summary>

- `M` frontend · `docs/MOMENTOS.md`
- `M` frontend · `orkaflow-frontend.md`
- `M` frontend · `public/staticwebapp.config.json`
- `M` frontend · `src/components/layout/app-shell.tsx`
- `A` frontend · `src/hooks/use-version-check.ts`
- `A` frontend · `src/vite-env.d.ts`
- `M` frontend · `vite.config.ts`

</details>

---

## v3.7.7.1 · Correção · 2026-10-26 22:06

**Tela de login e cores: fundo gelo, painel da marca em azul e paleta do protótipo ALZ**

- **Commits:** frontend `99a1eaa`, `81df4cd`

**Problema:** Na tela de login, o painel da marca ficava branco sobre fundo branco e o texto sumia. A paleta geral ainda diferia da definida no protótipo ALZ.

**Solução:** O login usa fundo gelo e o painel da marca em azul, legível. O painel adotou as cores do protótipo ALZ: fundo `#F8F7F4`, menu branco e item ativo `#F7EDDF`.

<details>
<summary>Arquivos alterados (5)</summary>

- `M` frontend · `src/app/providers/auth-provider.tsx`
- `M` frontend · `src/components/layout/app-shell.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/index.css`
- `M` frontend · `src/pages/auth/login-page.tsx`

</details>

---

## v3.7.7.0 · Melhoria · 2026-10-26 21:41

**Acabamento visual: campos arredondados, Novo bot mais enxuto, login claro e detalhes do menu**

- **Commits:** frontend `accee49`, `3d3f214`, `8c3aeb6`, `6c41f9b`

**Problema:** Campos de seleção com busca tinham formato diferente dos demais, e a lista podia abrir para cima e pular. O badge de erros do menu continuava depois de abrir Erros, o ID da task competia com o estado na tabela, o Novo bot tinha quatro blocos de texto para o tipo de execução e o login destoava do painel.

**Solução:** Todos os campos ficaram arredondados, com a mesma borda e foco, e a lista de seleção abre para baixo sempre que couber. O badge de erros some ao abrir Erros, o menu ganhou marca maior e uma linha separadora, e a tabela de Tasks mostra o ID discreto e o estado em destaque. No Novo bot e na edição, o tipo de execução virou dois cartões curtos (Background e Foreground), e o login ficou em padrão claro.

<details>
<summary>Arquivos alterados (15)</summary>

- `M` frontend · `src/components/common/api-tokens-card.tsx`
- `A` frontend · `src/components/common/execution-mode-picker.tsx`
- `M` frontend · `src/components/common/searchable-multi-select.tsx`
- `M` frontend · `src/components/common/searchable-select.tsx`
- `M` frontend · `src/components/common/status-badge.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/lib/ui.ts`
- `M` frontend · `src/pages/app-error-page.tsx`
- `M` frontend · `src/pages/auth/login-page.tsx`
- `M` frontend · `src/pages/bots/bot-create-page.tsx`
- `M` frontend · `src/pages/bots/bot-edit-page.tsx`
- `M` frontend · `src/pages/integration/api-docs-tab.tsx`
- `M` frontend · `src/pages/notifications/log-detail-drawer.tsx`
- `M` frontend · `src/pages/tasks/task-detail-page.tsx`
- `M` frontend · `src/pages/tasks/tasks-page.tsx`

</details>

---

## v3.7.6.1 · Correção · 2026-10-26 21:40

**Variáveis de ambiente: lista demorava uma consulta por linha**

- **Commits:** backend `1c40616`

**Problema:** A lista de variáveis de ambiente buscava o nome do alvo (automação, bot ou máquina) uma linha por vez, e a tela ficava lenta conforme a quantidade de variáveis.

**Solução:** Os nomes dos alvos passam a ser buscados de uma vez só para toda a lista, e a tela carrega mais rápido. Há teste cobrindo essa busca em lote.

<details>
<summary>Arquivos alterados (3)</summary>

- `M` backend · `app/api/v1/env_variables.py`
- `M` backend · `app/services/env_variable_service.py`
- `M` backend · `tests/test_env_variables.py`

</details>

---

## v3.7.6.0 · Melhoria · 2026-10-26 20:53

**Cores no padrão ALZ, menu maior e correção da tela escura dos modais**

- **Commits:** frontend `9c738c5`, `fec8625`, `4ac2ae4`, `e5a690d`

**Problema:** As cores do painel ainda não seguiam o padrão visual da ALZ, o menu era pequeno e o cabeçalho das tabelas pouco marcado. Os modais do Health, Nova Task e automação escureciam só um pedaço da tela em vez dela inteira.

**Solução:** Cores em tons de gelo e cinza neutro no padrão ALZ, itens do menu maiores e em negrito, cabeçalho de tabela mais marcado e linhas mais espaçadas; a tela de abertura "Conectando..." segue o mesmo fundo. Os modais passaram a ser desenhados sobre a página toda, e o fundo escuro cobre a tela inteira.

<details>
<summary>Arquivos alterados (9)</summary>

- `A` frontend · `docs/MOMENTOS.md`
- `M` frontend · `src/app/providers/auth-provider.tsx`
- `M` frontend · `src/components/layout/app-shell.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/index.css`
- `M` frontend · `src/lib/ui.ts`
- `M` frontend · `src/pages/automations/automation-form-page.tsx`
- `M` frontend · `src/pages/health/automation-health-page.tsx`
- `M` frontend · `src/pages/tasks/task-create-page.tsx`

</details>

---

## v3.7.5.0 · Melhoria · 2026-10-26 20:05

**Visual "claro e leve" com busca global Ctrl+K**

- **Commits:** frontend `5277ce2`

**Problema:** O painel tinha contraste pesado (menu escuro sobre fundo branco), uma barra superior que ocupava espaço sem função e nenhuma forma rápida de ir a uma tela ou localizar uma task.

**Solução:** Novo visual com menu claro, marca no topo e usuário no rodapé; o topo mostra só o caminho da tela, com cards de cantos arredondados e sombra suave. A **busca global** (Ctrl+K) abre qualquer tela pelo nome ou uma task pelo número. As telas entram com uma transição curta, e o selo "parada há X" ficou compacto na tabela.

<details>
<summary>Arquivos alterados (13)</summary>

- `A` frontend · `src/components/common/command-palette.tsx`
- `M` frontend · `src/components/common/filter-bar.tsx`
- `M` frontend · `src/components/common/page-header.tsx`
- `M` frontend · `src/components/common/task-stuck-badge.tsx`
- `M` frontend · `src/components/layout/app-header.tsx`
- `M` frontend · `src/components/layout/app-shell.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/components/layout/connection-banner.tsx`
- `M` frontend · `src/components/layout/system-health-banner.tsx`
- `M` frontend · `src/components/layout/user-menu.tsx`
- `M` frontend · `src/index.css`
- `A` frontend · `src/lib/navigation.ts`
- `M` frontend · `src/lib/ui.ts`

</details>

---

## v3.7.4.0 · Melhoria · 2026-10-26 19:49

**Menu e tabelas: item ativo correto, cabeçalho claro e linhas tracejadas; tela de Integração no padrão**

- **Commits:** frontend `8063c52`, `e722f4d`, `5faf3d1`, `c3477c3`, `c23bd23`

**Problema:** No menu, Automações acendia junto com Health. A tela de Integração (MCP e API) tinha aparência diferente do resto do sistema, e as linhas das tabelas eram difíceis de separar visualmente.

**Solução:** O menu passa a destacar só a tela atual, a tela de Integração usa cabeçalho, cards, botões e cores do restante do sistema, e as tabelas ganharam uma linha tracejada fina entre as linhas, com o tom ajustado para ficar visível sem pesar.

<details>
<summary>Arquivos alterados (8)</summary>

- `M` frontend · `src/components/common/api-tokens-card.tsx`
- `M` frontend · `src/components/layout/app-header.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/lib/ui.ts`
- `M` frontend · `src/pages/integration/api-docs-tab.tsx`
- `M` frontend · `src/pages/integration/integration-api-page.tsx`
- `M` frontend · `src/pages/integration/integration-mcp-page.tsx`
- `M` frontend · `src/pages/integration/mcp-tab.tsx`

</details>

---

## v3.7.3.0 · Melhoria · 2026-10-26 19:29

**Usabilidade nas demais telas: agendamentos, usuários, credenciais, máquinas, Health e outras**

- **Commits:** frontend `e2da9b4`, `3ed48c0`, `2cafe95`, `5827b8e`

**Problema:** Agendamentos, repositórios, usuários, perfis, credenciais, versões, variáveis, máquinas, dashboard, Health e notificações seguiam padrões diferentes. Editar uma credencial mostrava todos os segredos ao abrir, formulários podiam sobrescrever o que a pessoa digitava, o aviso "Ignorado" do agendamento podia ser antigo e o cadastro de variáveis usava um painel lateral fora do padrão.

**Solução:** Todas as telas ganharam o mesmo padrão: filtros com busca e "Limpar filtros", tabela clicável com menu ⋮, carregando, erro e vazio claros e validação embaixo do campo. Na edição de credencial, o segredo só aparece ao clicar no olho e só o que mudou é enviado. Agendamentos mostram o "Ignorado" apenas se for mais novo que a última execução, a próxima execução em tempo relativo e uma prévia em texto do cron. No Health, os contadores viram filtros e há "Executar agora" no card. O dashboard ganhou cards, período em botões e gráfico sucesso × erro por bot, e as permissões dos perfis são agrupadas por módulo. O cadastro de variáveis passou a abrir em janela centralizada.

<details>
<summary>Arquivos alterados (49)</summary>

- `M` frontend · `src/components/ui/button.tsx`
- `M` frontend · `src/pages/bot-versions/bot-version-create-page.tsx`
- `M` frontend · `src/pages/bot-versions/bot-version-detail-page.tsx`
- `M` frontend · `src/pages/bot-versions/bot-versions-page.tsx`
- `M` frontend · `src/pages/credentials/credential-create-page.tsx`
- `M` frontend · `src/pages/credentials/credential-detail-page.tsx`
- `M` frontend · `src/pages/credentials/credential-edit-page.tsx`
- `M` frontend · `src/pages/credentials/credentials-page.tsx`
- `M` frontend · `src/pages/dashboard/dashboard-page.tsx`
- `M` frontend · `src/pages/env-variables/effective-tab.tsx`
- `M` frontend · `src/pages/env-variables/env-variables-page.tsx`
- `M` frontend · `src/pages/env-variables/import-env-dialog.tsx`
- `M` frontend · `src/pages/env-variables/scope-badge.tsx`
- `M` frontend · `src/pages/env-variables/variable-form-sheet.tsx`
- `M` frontend · `src/pages/env-variables/variable-groups.tsx`
- `M` frontend · `src/pages/env-variables/variables-table.tsx`
- `M` frontend · `src/pages/health/automation-health-page.tsx`
- `M` frontend · `src/pages/notifications/extract-editor.tsx`
- `M` frontend · `src/pages/notifications/headers-editor.tsx`
- `M` frontend · `src/pages/notifications/json-block.tsx`
- `M` frontend · `src/pages/notifications/log-detail-drawer.tsx`
- `M` frontend · `src/pages/notifications/notification-logs-card.tsx`
- `M` frontend · `src/pages/notifications/notifications-page.tsx`
- `M` frontend · `src/pages/notifications/step-card.tsx`
- `M` frontend · `src/pages/notifications/steps-editor.tsx`
- `M` frontend · `src/pages/notifications/test-result.tsx`
- `M` frontend · `src/pages/notifications/variable-chips.tsx`
- `M` frontend · `src/pages/profile/profile-page.tsx`
- `M` frontend · `src/pages/profiles/profile-create-page.tsx`
- `M` frontend · `src/pages/profiles/profile-detail-page.tsx`
- `M` frontend · `src/pages/profiles/profile-edit-page.tsx`
- `M` frontend · `src/pages/profiles/profiles-page.tsx`
- `M` frontend · `src/pages/repositories/repositories-page.tsx`
- `M` frontend · `src/pages/repositories/repository-detail-page.tsx`
- `M` frontend · `src/pages/repositories/repository-form-page.tsx`
- `M` frontend · `src/pages/runner-config/runner-config-detail-page.tsx`
- `M` frontend · `src/pages/runner-config/runner-config-edit-page.tsx`
- `M` frontend · `src/pages/runner-config/runner-configs-page.tsx`
- `M` frontend · `src/pages/runner-config/worker-registration-page.tsx`
- `M` frontend · `src/pages/runner-logs/runner-logs-page.tsx`
- `M` frontend · `src/pages/runners/runner-detail-page.tsx`
- `M` frontend · `src/pages/runners/runners-page.tsx`
- `M` frontend · `src/pages/schedules/schedule-detail-page.tsx`
- `M` frontend · `src/pages/schedules/schedule-form-page.tsx`
- `M` frontend · `src/pages/schedules/schedules-page.tsx`
- `M` frontend · `src/pages/users/user-create-page.tsx`
- `M` frontend · `src/pages/users/user-detail-page.tsx`
- `M` frontend · `src/pages/users/user-edit-page.tsx`
- `M` frontend · `src/pages/users/users-page.tsx`

</details>

---

## v3.7.2.0 · Melhoria · 2026-10-26 19:12

**Tasks e Erros: "Rodar de novo", filtros na URL e detalhe mais claro**

- **Commits:** frontend `146d0c1`

**Problema:** Os filtros de Tasks se perdiam ao voltar do detalhe e não podiam ser compartilhados. Repetir uma task exigia recriá-la à mão e as ações perigosas usavam confirmações simples do navegador. O JSON da Nova Task só dava erro ao salvar e a tela de Erros era difícil de ler.

**Solução:** Os filtros de Tasks ficam na URL (link compartilhável que sobrevive ao voltar). O menu ⋮ e o detalhe ganharam Ver, Parar, Parada forçada (exige digitar o id), Cancelar e **Rodar de novo** (mesmos parâmetros, ligada à task original), todos com confirmação em diálogo. A Nova Task valida o JSON ao digitar e a tela de Erros destaca tipo e mensagem, com stacktrace recolhível e botão para a task.

<details>
<summary>Arquivos alterados (5)</summary>

- `M` frontend · `src/pages/errors/task-error-detail-page.tsx`
- `M` frontend · `src/pages/errors/task-errors-page.tsx`
- `M` frontend · `src/pages/tasks/task-create-page.tsx`
- `M` frontend · `src/pages/tasks/task-detail-page.tsx`
- `M` frontend · `src/pages/tasks/tasks-page.tsx`

</details>

---

## v3.7.1.0 · Melhoria · 2026-10-26 19:04

**Automações e bots: botão "Executar agora" e telas no novo padrão**

- **Commits:** frontend `b2a1e75`

**Problema:** Para rodar uma automação era preciso abrir a tela de Nova Task e preencher tudo. As telas de automações e bots seguiam padrões diferentes das outras, com formulários que podiam sobrescrever o que a pessoa digitava e validação pouco clara.

**Solução:** **Executar agora** na lista (menu ⋮) e como ação principal do detalhe da automação, com confirmação e usando os parâmetros padrão; a task criada é aberta em seguida e o erro "já existe task aberta" aparece como aviso. As telas ganharam cabeçalho, filtros com busca sem acento, tabela clicável e validação embaixo de cada campo.

<details>
<summary>Arquivos alterados (7)</summary>

- `M` frontend · `src/pages/automations/automation-detail-page.tsx`
- `M` frontend · `src/pages/automations/automation-form-page.tsx`
- `M` frontend · `src/pages/automations/automations-page.tsx`
- `M` frontend · `src/pages/bots/bot-create-page.tsx`
- `M` frontend · `src/pages/bots/bot-detail-page.tsx`
- `M` frontend · `src/pages/bots/bot-edit-page.tsx`
- `M` frontend · `src/pages/bots/bots-page.tsx`

</details>

---

## v3.7.0.1 · Correção · 2026-10-26 19:04

**Lista de tasks: duração com data sem fuso derrubava a listagem**

- **Commits:** backend `e756d01`

**Problema:** Se uma task tivesse data sem fuso horário, o cálculo da duração falhava e a lista de tasks inteira deixava de carregar.

**Solução:** O cálculo da duração passou a tolerar datas sem fuso, e a listagem carrega normalmente.

<details>
<summary>Arquivos alterados (1)</summary>

- `M` backend · `app/services/task_service.py`

</details>

---

## v3.7.0.0 · Geral · 2026-10-26 18:53

**Base de usabilidade: páginas de erro e 404, boot, menu no celular, login e componentes comuns**

- **Commits:** frontend `bea92fd`, `fb93744`, `58bf4b3`

**Problema:** Um erro dentro de uma tela mostrava a mensagem crua "Unexpected Application Error!". Se a API demorasse na abertura, o painel ficava sem explicação, no celular não havia menu de navegação e cada tela tinha seus próprios botões, tabelas, datas e confirmações, com aparência e comportamento diferentes. O login tinha opções que não funcionavam ("lembrar acesso", "esqueci").

**Solução:** Erro de tela mostra uma página do próprio painel (com o menu) e URL inexistente mostra "Página não encontrada". A abertura mostra "Conectando ao servidor..." com **Tentar de novo**, e no celular o botão do menu abre a navegação lateral. Foi criado um kit visual único (azul do logo como destaque) e componentes comuns (confirmação, estado vazio, cabeçalho, filtros, paginação, "Atualizado há X s", menu ⋮), com guia de interface. O login ficou simples, o menu do usuário encerra a sessão também no servidor e o rodapé mostra o ambiente real.

<details>
<summary>Arquivos alterados (24)</summary>

- `A` frontend · `docs/UI_GUIDE.md`
- `M` frontend · `index.html`
- `M` frontend · `src/app/providers/auth-provider.tsx`
- `M` frontend · `src/app/router/index.tsx`
- `A` frontend · `src/components/common/actions-menu.tsx`
- `A` frontend · `src/components/common/confirm-dialog.tsx`
- `A` frontend · `src/components/common/empty-state.tsx`
- `A` frontend · `src/components/common/filter-bar.tsx`
- `A` frontend · `src/components/common/page-header.tsx`
- `M` frontend · `src/components/common/query-error.tsx`
- `A` frontend · `src/components/common/refresh-indicator.tsx`
- `A` frontend · `src/components/common/skeleton.tsx`
- `M` frontend · `src/components/common/status-badge.tsx`
- `M` frontend · `src/components/layout/app-header.tsx`
- `M` frontend · `src/components/layout/app-shell.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/components/layout/user-menu.tsx`
- `M` frontend · `src/layouts/app-layout.tsx`
- `A` frontend · `src/lib/format.ts`
- `M` frontend · `src/lib/query-client.ts`
- `A` frontend · `src/lib/run-task.ts`
- `A` frontend · `src/lib/ui.ts`
- `A` frontend · `src/pages/app-error-page.tsx`
- `M` frontend · `src/pages/auth/login-page.tsx`

</details>

---

## v3.6.4.2 · Correção · 2026-10-26 18:16

**Agendamento: o aviso "ignorado" ficava para sempre**

- **Commits:** backend `d9c2aa1`

**Problema:** Quando um agendamento era ignorado (por exemplo, por já existir task aberta), o aviso "ignorado" permanecia mesmo depois de ele voltar a criar tasks normalmente, passando a impressão de que continuava com problema.

**Solução:** Quando o agendamento volta a criar task, o motivo do "ignorado" é limpo e o aviso deixa de aparecer.

<details>
<summary>Arquivos alterados (1)</summary>

- `M` backend · `app/services/scheduler_engine_service.py`

</details>

---

## v3.6.4.1 · Correção · 2026-10-26 17:52

**Telas lentas no Azure: automações, Health, máquinas e dashboard; regra "Manual" no Health**

- **Commits:** backend `27042af` · frontend `2cff7a4`

**Problema:** Automações, Health, Máquinas e Dashboard demoravam muito no Azure porque faziam consultas demais (73 consultas para 32 automações) e carregavam junto, em cada task, o print de tela da máquina (cerca de 0,7 MB). O Health levava 7,9 s. Além disso, automação sem agendamento aparecia como "Atrasada", e uma falha de carregamento não explicava o motivo nem oferecia nova tentativa.

**Solução:** As consultas foram agrupadas (de 73 para 5 em 32 automações), o print de tela só é carregado quando necessário e a última task por automação é buscada de forma mais leve: o Health passou de 7,9 s para 0,4 s. A lista de Máquinas também ficou mais leve. Automação sem agendamento passa a ter a regra **Manual**, sem o selo "Atrasado", e a tela de Automações mostra o motivo do erro com o botão **Tentar de novo**.

<details>
<summary>Arquivos alterados (10)</summary>

- `M` backend · `app/models/runner.py`
- `M` backend · `app/repositories/runner_repository.py`
- `M` backend · `app/services/automation_health_service.py`
- `M` backend · `app/services/automation_service.py`
- `M` backend · `app/services/runner_service.py`
- `A` backend · `tests/test_automation_list_queries.py`
- `A` backend · `tests/test_health_last_tasks.py`
- `A` frontend · `src/components/common/query-error.tsx`
- `M` frontend · `src/pages/automations/automations-page.tsx`
- `M` frontend · `src/pages/health/automation-health-page.tsx`

</details>

---

## v3.6.4.0 · Melhoria · 2026-10-26 15:38

**Integração: MCP para IA, documentação da API e tokens de acesso**

- **Commits:** backend `fb0199f`, `b26f7b1`, `f11bed5` · frontend `6879775`, `2327dcc`, `36c6edc`

**Problema:** Não havia forma segura de usar o Regente a partir de uma IA ou de outro sistema: nenhum token de acesso para integração, nenhuma documentação da API em português e a documentação técnica ficava aberta a qualquer pessoa. Tasks criadas pelo painel não registravam quem as criou.

**Solução:** Nova tela **Integração** com passo a passo do **MCP** (servidor para IA, com configuração pronta para Claude Code, Claude Desktop, Cursor, VS Code e outras), documentação da API com busca, exemplos e curl, e **tokens de integração** (gerar, copiar uma vez, revogar, com validade e último uso) no Perfil e no detalhe do usuário. A IA consulta status, erros, máquinas e agendamentos e também executa ações, com as permissões de quem gerou o token, usando um guia de "como fazer" e acesso às rotas do painel. As páginas `/docs` e `/redoc` deixam de ser públicas, e a task criada pelo painel passa a gravar "Criado por".

<details>
<summary>Arquivos alterados (34)</summary>

- `A` backend · `alembic/versions/d3f5b7c9e1a2_api_tokens.py`
- `M` backend · `app/api/deps.py`
- `M` backend · `app/api/router.py`
- `A` backend · `app/api/v1/api_tokens.py`
- `A` backend · `app/api/v1/integration.py`
- `M` backend · `app/api/v1/tasks.py`
- `M` backend · `app/core/config.py`
- `A` backend · `app/integration/__init__.py`
- `A` backend · `app/integration/api_guide.py`
- `M` backend · `app/main.py`
- `A` backend · `app/mcp/__init__.py`
- `A` backend · `app/mcp/api_bridge.py`
- `A` backend · `app/mcp/playbooks.py`
- `A` backend · `app/mcp/server.py`
- `A` backend · `app/mcp/tools.py`
- `M` backend · `app/models/__init__.py`
- `A` backend · `app/models/api_token.py`
- `A` backend · `app/schemas/api_token.py`
- `A` backend · `app/services/api_token_service.py`
- `A` backend · `tests/test_integration_mcp.py`
- `A` backend · `tests/test_mcp_api_bridge.py`
- `M` frontend · `src/app/router/index.tsx`
- `A` frontend · `src/components/common/api-tokens-card.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `A` frontend · `src/lib/clipboard.ts`
- `A` frontend · `src/pages/integration/api-docs-tab.tsx`
- `A` frontend · `src/pages/integration/integration-page.tsx`
- `A` frontend · `src/pages/integration/mcp-tab.tsx`
- `A` frontend · `src/pages/integration/openapi-utils.ts`
- `A` frontend · `src/pages/integration/simple-markdown.tsx`
- `M` frontend · `src/pages/profile/profile-page.tsx`
- `M` frontend · `src/pages/tasks/task-log-console.tsx`
- `M` frontend · `src/pages/users/user-detail-page.tsx`
- `A` frontend · `src/services/api/integration.ts`

</details>

---

## v3.6.3.0 · Melhoria · 2026-10-26 14:27

**Tela da task mais limpa: log único estilo console e novo menu Integração**

- **Commits:** frontend `c29dfc6`

**Problema:** O resultado da task repetia a mensagem final em vários lugares e dividia o log em blocos, o que dificultava a leitura de uma execução com erro. O resumo mostrava campos técnicos demais, e MCP, API e Notificações não tinham um lugar próprio no menu.

**Solução:** O resultado virou um log único, no estilo console das máquinas, com cores por nível, filtro de avisos e erros, busca, cópia e acompanhamento ao vivo, sem repetir a mensagem final. O cabeçalho mostra a mensagem final e a exceção, o resumo ficou enxuto com "Criado por" (usuário ou agendamento), máquina e automação com link, e os campos técnicos ficam num bloco recolhível. O menu ganhou o grupo **Integração** com MCP, API e Notificações em páginas separadas.

<details>
<summary>Arquivos alterados (13)</summary>

- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/components/common/api-tokens-card.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `A` frontend · `src/pages/integration/api-base.ts`
- `A` frontend · `src/pages/integration/integration-api-page.tsx`
- `A` frontend · `src/pages/integration/integration-mcp-page.tsx`
- `D` frontend · `src/pages/integration/integration-page.tsx`
- `M` frontend · `src/pages/integration/mcp-tab.tsx`
- `M` frontend · `src/pages/tasks/task-detail-page.tsx`
- `A` frontend · `src/pages/tasks/task-log-console.tsx`
- `A` frontend · `src/pages/tasks/task-log-utils.ts`
- `M` frontend · `src/services/api/integration.ts`
- `M` frontend · `src/services/api/tasks.ts`

</details>

---

## v3.6.2.1 · Correção · 2026-10-25 17:33

**Versões de bot: lista de versões estourava o tempo no Azure**

- **Commits:** backend `79d0599`

**Problema:** O selo "Em uso" da lista de versões fazia de 2 a 3 consultas ao banco por bot. Com 34 bots eram 103 consultas e cerca de 17 segundos, estourando o tempo limite da tela no Azure.

**Solução:** A lista agora busca tudo em 2 consultas para todos os bots, mantendo a mesma regra de qual versão está em uso (fixada, depois a ativa mais nova, depois a mais nova). Há teste comparando com a regra antiga e limitando o número de consultas.

<details>
<summary>Arquivos alterados (2)</summary>

- `M` backend · `app/services/bot_version_service.py`
- `M` backend · `tests/test_bot_version_git.py`

</details>

---

## v3.6.2.0 · Melhoria · 2026-10-25 16:55

**Variáveis de ambiente: importar .env e lista agrupada por automação, bot ou máquina**

- **Commits:** backend `beef92d` · frontend `243227b`, `97ae829`

**Problema:** Cadastrar muitas variáveis de ambiente exigia criar uma por uma. A tela também abria com a lista de todas as variáveis misturadas, difícil de localizar o que pertence a cada automação, bot ou máquina.

**Solução:** Novo botão **Importar .env**: escolhe-se o alvo, carrega-se o arquivo (ou cola o conteúdo) e o sistema mostra uma prévia (nova, já existe, inválida, repetida), marcando como secretos nomes com senha, token ou key. Variáveis inválidas ou repetidas não impedem as demais. A tela agora abre com a lista de alvos que têm variáveis (com contagem de variáveis e de secretas) e, ao abrir um alvo, mostra só as dele, já com Nova variável e Importar nesse alvo. Escopo Global deixou de ser oferecido no cadastro.

<details>
<summary>Arquivos alterados (12)</summary>

- `M` backend · `app/api/v1/env_variables.py`
- `M` backend · `app/schemas/env_variable.py`
- `M` backend · `app/services/env_variable_service.py`
- `M` backend · `tests/test_env_variables.py`
- `A` frontend · `src/lib/dotenv.ts`
- `M` frontend · `src/pages/env-variables/env-variables-page.tsx`
- `A` frontend · `src/pages/env-variables/group-utils.ts`
- `A` frontend · `src/pages/env-variables/import-env-dialog.tsx`
- `M` frontend · `src/pages/env-variables/variable-form-sheet.tsx`
- `A` frontend · `src/pages/env-variables/variable-groups.tsx`
- `M` frontend · `src/pages/env-variables/variables-table.tsx`
- `M` frontend · `src/services/api/env-variables.ts`

</details>

---

## v3.6.1.0 · Melhoria · 2026-10-25 16:22

**Nova Versão com busca no bot, Dispensar nos avisos de erro e aviso de conexão mais calmo**

- **Commits:** frontend `b85338f`

**Problema:** O campo de bot da Nova Versão não tinha busca. O aviso vermelho de erros (erros em 24 h, máquinas, tasks paradas) ficava na tela o tempo todo, e uma única resposta lenta do servidor, como num reinício, já mostrava "Sem conexão".

**Solução:** O campo de bot da Nova Versão aceita busca por nome ou repositório. O aviso vermelho ganhou o botão **Dispensar** (some até aparecer um item novo) e o aviso de conexão só aparece se a verificação falhar de novo após uma segunda tentativa, em amarelo e com texto de reconexão.

<details>
<summary>Arquivos alterados (4)</summary>

- `M` frontend · `src/components/layout/connection-banner.tsx`
- `M` frontend · `src/components/layout/system-health-banner.tsx`
- `M` frontend · `src/hooks/use-api-connection.ts`
- `M` frontend · `src/pages/bot-versions/bot-version-create-page.tsx`

</details>

---

## v3.6.0.0 · Geral · 2026-10-25 15:48

**Painel no Azure: publicação do front e da API em modo "só painel"**

- **Commits:** backend `991fc4f`, `c15fe83` · frontend `38060f1`, `b4eb9d8`

**Problema:** Não existia uma cópia do painel hospedada no Azure. Para isso o sistema precisava de ajustes: a API fixava os endereços permitidos, expunha as rotas das máquinas mesmo onde nenhuma máquina conecta, e o `/health` exigia os processos de fundo que rodam apenas no servidor Linux. Acessar um link direto como `/tasks/123` no Azure daria erro 404.

**Solução:** O backend passou a aceitar por variável os endereços permitidos (`CORS_ORIGINS`), desligar as rotas do worker (`ENABLE_WORKER_API`) e considerar só o banco no `/health` (`HEALTH_CHECK_BACKGROUND_WORKERS`); sem as variáveis tudo continua como antes. O front ganhou a publicação automática no Azure Static Web Apps (com endereço da API, Node 22 e regra para qualquer rota abrir o painel), e o backend a publicação no Azure App Service.

<details>
<summary>Arquivos alterados (9)</summary>

- `A` backend · `.github/workflows/main_orkaflow-backend.yml`
- `M` backend · `app/api/router.py`
- `M` backend · `app/api/v1/health.py`
- `M` backend · `app/core/config.py`
- `M` backend · `app/main.py`
- `A` backend · `tests/test_panel_only_mode.py`
- `A` frontend · `.github/workflows/azure-static-web-apps-witty-plant-01725a90f.yml`
- `M` frontend · `package.json`
- `A` frontend · `public/staticwebapp.config.json`

</details>

---

## v3.5.7.0 · Melhoria · 2026-10-25 14:07

**Filtros e listas: seleção com busca em todas as telas e padrão "só ativos"**

- **Commits:** frontend `68da742`

**Problema:** Os filtros de lista (automação, bot, máquina, status, usuário) eram selects comuns, difíceis de usar com muitas opções. As listas abriam misturando itens inativos, nomes longos ficavam cortados sem como ler o texto inteiro, e algumas telas (Health "Todas", Variáveis, Versões) mostravam só parte dos dados ou ficavam vazias porque pediam bots demais de uma vez.

**Solução:** Filtros e campos de seleção ganharam **busca** (ignora acento e maiúscula, funciona pelo teclado e dentro de modais) em Tasks, Nova Task, Bots, Automações, Agendamentos, Health, Credenciais, Usuários, Variáveis e Logs. As listas passaram a abrir só com os itens ativos, nomes e descrições longos mostram o texto completo ao passar o mouse, a tela Nova Task foi reorganizada em seções e o Health "Todas" volta a mostrar ativas e inativas.

<details>
<summary>Arquivos alterados (30)</summary>

- `A` frontend · `src/components/common/searchable-multi-select.tsx`
- `A` frontend · `src/components/common/searchable-select.tsx`
- `A` frontend · `src/lib/search.ts`
- `M` frontend · `src/pages/automations/automation-detail-page.tsx`
- `M` frontend · `src/pages/automations/automation-form-page.tsx`
- `M` frontend · `src/pages/automations/automations-page.tsx`
- `M` frontend · `src/pages/bot-versions/bot-version-create-page.tsx`
- `M` frontend · `src/pages/bot-versions/bot-version-detail-page.tsx`
- `M` frontend · `src/pages/bot-versions/bot-versions-page.tsx`
- `M` frontend · `src/pages/bots/bot-create-page.tsx`
- `M` frontend · `src/pages/bots/bot-edit-page.tsx`
- `M` frontend · `src/pages/bots/bots-page.tsx`
- `M` frontend · `src/pages/credentials/credential-create-page.tsx`
- `M` frontend · `src/pages/credentials/credential-edit-page.tsx`
- `M` frontend · `src/pages/credentials/credentials-page.tsx`
- `M` frontend · `src/pages/env-variables/effective-tab.tsx`
- `M` frontend · `src/pages/env-variables/env-variables-page.tsx`
- `M` frontend · `src/pages/env-variables/use-scope-options.ts`
- `M` frontend · `src/pages/env-variables/variable-form-sheet.tsx`
- `M` frontend · `src/pages/health/automation-health-page.tsx`
- `M` frontend · `src/pages/runner-config/runner-configs-page.tsx`
- `M` frontend · `src/pages/runner-logs/runner-logs-page.tsx`
- `M` frontend · `src/pages/runners/runners-page.tsx`
- `M` frontend · `src/pages/schedules/schedule-detail-page.tsx`
- `M` frontend · `src/pages/schedules/schedule-form-page.tsx`
- `M` frontend · `src/pages/schedules/schedules-page.tsx`
- `M` frontend · `src/pages/tasks/task-create-page.tsx`
- `M` frontend · `src/pages/tasks/tasks-page.tsx`
- `M` frontend · `src/pages/users/users-page.tsx`
- `M` frontend · `src/services/api/bots.ts`

</details>

---

## v3.5.6.0 · Melhoria · 2026-10-24 23:45

**Versões de bot: sincronizar com o Git e Release para fixar a versão executada**

- **Commits:** backend `6439c62` · frontend `3ddcdf2`

**Problema:** Ao cadastrar uma nova versão de bot, número, commit, autor e changelog eram digitados à mão, com risco de erro e de registrar duas vezes o mesmo commit. Também não havia como fixar qual versão as máquinas devem executar: o robô sempre seguia a mais nova.

**Solução:** Ao escolher o bot na tela de Nova Versão, o sistema lê o repositório Git e já preenche a versão sugerida (última + 1, editável), commit, branch, autor, data e changelog, avisando quando já está sincronizado ou o commit já foi registrado. Na lista de versões surgiram a coluna Commit, o selo "Em uso" e a ação **Release**, que fixa a versão que tasks e máquinas passam a executar (a máquina faz checkout exato do commit). Criar uma versão nova ou dar Release na mais recente solta a fixação.

<details>
<summary>Arquivos alterados (16)</summary>

- `A` backend · `alembic/versions/c2e4a6b8d0f1_bot_version_git_sync_and_release.py`
- `M` backend · `app/api/v1/bot_versions.py`
- `M` backend · `app/models/bot.py`
- `M` backend · `app/models/bot_version.py`
- `M` backend · `app/repositories/bot_repository.py`
- `M` backend · `app/repositories/task_repository.py`
- `M` backend · `app/schemas/bot_version.py`
- `M` backend · `app/services/bot_version_service.py`
- `A` backend · `app/services/git_repo_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `docs/PROPOSTA_VERSOES_E_PARAMETROS.md`
- `A` backend · `tests/test_bot_version_git.py`
- `M` frontend · `src/pages/bot-versions/bot-version-create-page.tsx`
- `M` frontend · `src/pages/bot-versions/bot-version-detail-page.tsx`
- `M` frontend · `src/pages/bot-versions/bot-versions-page.tsx`
- `M` frontend · `src/services/api/bot-versions.ts`

</details>

---

## v3.5.5.1 · Correção · 2026-10-22 12:21

**Launcher do worker: janela fechava sem log no dia seguinte**

- **Commits:** worker `e9b5da4`

**Problema:** A cópia temporária do `iniciar_worker.bat` mantinha a data do arquivo original, e a limpeza de sobras apagava essa própria cópia em uso a partir do dia seguinte. O worker fechava de repente com a mensagem "The batch file cannot be found". Além disso, correções no launcher só chegavam às máquinas quando elas eram configuradas de novo.

**Solução:** A cópia agora é criada com a data de agora e deixa de ser apagada em uso. A cada partida, o `iniciar_worker.bat` do atalho é atualizado a partir do repositório, então correções do launcher chegam sozinhas às máquinas. Os arquivos `.bat` ficam sempre no formato de linha do Windows.

<details>
<summary>Arquivos alterados (2)</summary>

- `A` worker · `.gitattributes`
- `M` worker · `iniciar_worker.bat`

</details>

---

## v3.5.5.0 · Melhoria · 2026-10-22 11:52

**Remover runner e tela de Logs das máquinas em tempo real**

- **Commits:** backend `2310875` · frontend `f5a9dbf` · worker `1ab2957`

**Problema:** Máquinas desativadas ou trocadas continuavam nas listas de runners, e não havia como removê-las. Para ver o que o worker estava fazendo era preciso entrar na máquina e abrir o arquivo `worker.log`. Além disso, usuário e token de links do git podiam aparecer nos logs.

**Solução:** Runners e Runner Config ganharam a ação Remover, com confirmação, que desfaz os vínculos, devolve as tasks em espera para a fila e recusa se houver task em execução. Há um filtro "Removidos (histórico)", e uma máquina removida volta quando for registrada de novo. A nova tela Logs mostra o `worker.log` da máquina escolhida ao vivo, com filtros por origem (worker ou robôs), task, nível e texto, além de pausar e ir para o fim. Os logs são guardados por 3 dias. Credenciais em URLs, como `https://usuario:token@`, passam a aparecer como `https://***@` nos arquivos, no painel e nas mensagens de erro.

<details>
<summary>Arquivos alterados (35)</summary>

- `A` backend · `alembic/versions/b9d1f3a5c7e2_runner_removal_and_log_lines.py`
- `M` backend · `app/api/router.py`
- `A` backend · `app/api/v1/runner_logs.py`
- `M` backend · `app/api/v1/runners.py`
- `A` backend · `app/api/v1/worker_runner_logs.py`
- `M` backend · `app/core/config.py`
- `M` backend · `app/main.py`
- `M` backend · `app/models/__init__.py`
- `M` backend · `app/models/runner.py`
- `A` backend · `app/models/runner_log_line.py`
- `M` backend · `app/repositories/dashboard_repository.py`
- `A` backend · `app/repositories/runner_log_repository.py`
- `M` backend · `app/repositories/runner_repository.py`
- `M` backend · `app/repositories/task_repository.py`
- `M` backend · `app/schemas/runner.py`
- `A` backend · `app/schemas/runner_log.py`
- `M` backend · `app/services/automation_runner_service.py`
- `A` backend · `app/services/runner_log_service.py`
- `M` backend · `app/services/runner_service.py`
- `M` backend · `app/services/worker_service.py`
- `M` backend · `app/workers/watchdog_main.py`
- `A` backend · `tests/test_runner_removal_and_logs.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `M` frontend · `src/pages/runner-config/runner-configs-page.tsx`
- `A` frontend · `src/pages/runner-logs/runner-logs-page.tsx`
- `M` frontend · `src/pages/runners/runners-page.tsx`
- `A` frontend · `src/services/api/runner-logs.ts`
- `M` frontend · `src/services/api/runners.ts`
- `A` worker · `app/core/log_masking.py`
- `M` worker · `app/core/logging_config.py`
- `A` worker · `app/runtime/log_shipper.py`
- `M` worker · `app/runtime/main.py`
- `M` worker · `app/sync/bot_installer.py`
- `A` worker · `tests/test_log_shipper.py`

</details>

---

## v3.5.4.0 · Melhoria · 2026-10-21 17:31

**Variáveis de ambiente dos robôs por escopo, com segredos protegidos**

- **Commits:** backend `744ac56` · worker `096fac2` · frontend `b50846b`

**Problema:** Valores que os robôs precisam (endereços, chaves, senhas de serviços) ficavam dentro dos próprios robôs ou em arquivos nas máquinas, difíceis de trocar e de proteger. Mudar um valor exigia mexer em cada robô ou em cada máquina.

**Solução:** Nova tela de variáveis de ambiente, cadastradas por escopo: global, bot, automação ou máquina, com herança entre eles (o mais específico vale). Existe uma aba que mostra os valores finais e de onde cada um vem. Segredos são guardados criptografados, aparecem mascarados e nunca saem pela API. O worker busca as variáveis da task antes de iniciar o robô e as injeta no ambiente dele, e os valores secretos viram `***` nos logs. Nomes do sistema e os que começam com `ORKAFLOW_` são reservados e não podem ser sobrescritos.

<details>
<summary>Arquivos alterados (23)</summary>

- `A` backend · `alembic/versions/a8c0e2f4b6d9_add_env_variables.py`
- `M` backend · `app/api/router.py`
- `A` backend · `app/api/v1/env_variables.py`
- `M` backend · `app/api/v1/worker_tasks.py`
- `M` backend · `app/models/__init__.py`
- `A` backend · `app/models/env_variable.py`
- `A` backend · `app/schemas/env_variable.py`
- `A` backend · `app/services/env_variable_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_env_variables.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `A` frontend · `src/pages/env-variables/effective-tab.tsx`
- `A` frontend · `src/pages/env-variables/env-variables-page.tsx`
- `A` frontend · `src/pages/env-variables/scope-badge.tsx`
- `A` frontend · `src/pages/env-variables/scope-labels.ts`
- `A` frontend · `src/pages/env-variables/use-scope-options.ts`
- `A` frontend · `src/pages/env-variables/variable-form-sheet.tsx`
- `A` frontend · `src/pages/env-variables/variables-table.tsx`
- `A` frontend · `src/services/api/env-variables.ts`
- `M` worker · `app/runtime/task_client.py`
- `M` worker · `app/runtime/task_executor.py`
- `M` worker · `tests/test_worker_core.py`

</details>

---

## v3.5.3.1 · Correção · 2026-10-21 17:09

**Layout: faixa escura e rolagem extra no fim das páginas**

- **Commits:** frontend `c41fc2f`

**Problema:** Em algumas telas aparecia uma faixa escura no fim da página e uma rolagem extra desnecessária, por causa de elementos posicionados fora da área principal.

**Solução:** A área principal do painel passou a conter esses elementos, então a faixa escura e a rolagem extra desapareceram.

<details>
<summary>Arquivos alterados (1)</summary>

- `M` frontend · `src/components/layout/app-shell.tsx`

</details>

---

## v3.5.3.0 · Melhoria · 2026-10-21 16:47

**Notificações: login antes do envio e histórico com requisição e resposta completas**

- **Commits:** backend `288f351`, `cb872ea` · frontend `4a96953`, `5b1c5bc`

**Problema:** O sistema de chamados exige autenticação, então a requisição de abertura não funcionava sem antes fazer login e obter um token. Além disso, quando um envio falhava, o histórico não mostrava o que foi enviado nem o que o outro sistema respondeu, o que dificultava descobrir o motivo.

**Solução:** Agora é possível cadastrar etapas antes do envio (por exemplo, um login), que guardam partes da resposta em variáveis como `{{token}}`. O login é refeito a cada tentativa e, se uma etapa falhar, o envio não acontece. O histórico ganhou o botão "Ver detalhes", que mostra a requisição (com cabeçalhos mascarados), o resultado de cada etapa e a resposta completa. Valores secretos, como o token, são trocados por `***` antes de serem gravados.

<details>
<summary>Arquivos alterados (18)</summary>

- `A` backend · `alembic/versions/e5a7b9c1d2f4_add_notification_pre_steps.py`
- `A` backend · `alembic/versions/f6b8c0d2e3a5_add_notification_log_details.py`
- `M` backend · `app/api/v1/notifications.py`
- `M` backend · `app/models/notification_channel.py`
- `M` backend · `app/schemas/notification.py`
- `M` backend · `app/services/notification_service.py`
- `M` backend · `tests/test_notifications.py`
- `A` frontend · `src/pages/notifications/extract-editor.tsx`
- `A` frontend · `src/pages/notifications/json-block.tsx`
- `A` frontend · `src/pages/notifications/log-detail-drawer.tsx`
- `M` frontend · `src/pages/notifications/notification-logs-card.tsx`
- `M` frontend · `src/pages/notifications/notifications-page.tsx`
- `A` frontend · `src/pages/notifications/step-card.tsx`
- `A` frontend · `src/pages/notifications/step-utils.ts`
- `A` frontend · `src/pages/notifications/steps-editor.tsx`
- `M` frontend · `src/pages/notifications/test-result.tsx`
- `M` frontend · `src/pages/notifications/variable-chips.tsx`
- `M` frontend · `src/services/api/notifications.ts`

</details>

---

## v3.5.2.0 · Melhoria · 2026-10-21 16:09

**Notificações: falhas seguidas de um agendamento abrem chamado e pausam o agendamento**

- **Commits:** backend `82ca850`, `eac529c` · frontend `e791918`

**Problema:** Quando um agendamento falhava várias vezes seguidas, ninguém era avisado automaticamente e ele continuava rodando e falhando. A equipe só percebia olhando o painel.

**Solução:** Novo módulo de Notificações, com tela própria. Depois de N falhas seguidas (padrão 3) de um agendamento ativo, o sistema envia uma requisição configurável para abrir um chamado (URL, método, cabeçalhos e corpo com variáveis como `{{erro}}` e `{{automacao}}`), com 3 tentativas, pausa o agendamento e registra o envio. A tela permite configurar o destino, fazer um envio de teste e ver o histórico. Só contam falhas ocorridas depois de ativar o canal, para não alertar de novo falhas antigas.

<details>
<summary>Arquivos alterados (21)</summary>

- `A` backend · `alembic/versions/c9d1e5f7a2b4_add_notification_channels.py`
- `A` backend · `alembic/versions/d4f6a8c0b1e3_add_notification_counting_since.py`
- `M` backend · `app/api/router.py`
- `A` backend · `app/api/v1/notifications.py`
- `M` backend · `app/models/__init__.py`
- `A` backend · `app/models/notification_channel.py`
- `A` backend · `app/schemas/notification.py`
- `A` backend · `app/services/notification_service.py`
- `M` backend · `app/services/system_heartbeat_service.py`
- `M` backend · `app/workers/main.py`
- `A` backend · `app/workers/notifications_main.py`
- `A` backend · `tests/test_notifications.py`
- `M` frontend · `src/app/router/index.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `A` frontend · `src/pages/notifications/header-utils.ts`
- `A` frontend · `src/pages/notifications/headers-editor.tsx`
- `A` frontend · `src/pages/notifications/notification-logs-card.tsx`
- `A` frontend · `src/pages/notifications/notifications-page.tsx`
- `A` frontend · `src/pages/notifications/test-result.tsx`
- `A` frontend · `src/pages/notifications/variable-chips.tsx`
- `A` frontend · `src/services/api/notifications.ts`

</details>

---

## v3.5.1.0 · Melhoria · 2026-10-21 15:17

**Worker: limpeza automática de SAP, CIGAM e Citrix antes e depois de tasks com foco**

- **Commits:** worker `0052d09`, `f143d7a`

**Problema:** Depois de uma falha, processos como SAP, CIGAM e Citrix podiam ficar abertos na máquina e atrapalhar a próxima task com foco, que então falhava também.

**Solução:** O worker encerra automaticamente os processos `sap*`, `cigam*` e `citrix*` antes de iniciar uma task com foco e depois de qualquer falha de task com foco. Nada é encerrado enquanto outra task com foco estiver rodando. As regras ficam em `cleanup_rules.json`, que pode ser ajustado por máquina; arquivos antigos são guardados como `.bak` e recebem os novos padrões.

<details>
<summary>Arquivos alterados (3)</summary>

- `A` worker · `app/runtime/cleanup.py`
- `M` worker · `app/runtime/task_executor.py`
- `A` worker · `tests/test_cleanup.py`

</details>

---

## v3.5.0.2 · Correção · 2026-10-21 14:51

**Worker: "Bot não encontrado" em máquina nova e log da task mais limpo**

- **Commits:** worker `aedabd2`, `d29a193`

**Problema:** Em uma máquina recém-configurada, as primeiras tasks falhavam com "Bot não encontrado", porque o worker ainda não tinha a lista de bots. Além disso, as mensagens do sincronizador de bots apareciam misturadas no log da próxima task, e a sincronização de fundo instalava todos os bots, disputando rede e processador.

**Solução:** O worker carrega a lista de bots ao iniciar, antes de pegar tasks, e, se uma task chegar com um bot desconhecido, atualiza a lista e instala só aquele bot. As mensagens do sincronizador deixam de aparecer no log da task. A sincronização em segundo plano só atualiza bots já instalados, e os que nunca foram usados na máquina são instalados pela primeira task que precisar.

<details>
<summary>Arquivos alterados (4)</summary>

- `M` worker · `app/runtime/main.py`
- `M` worker · `app/runtime/task_executor.py`
- `M` worker · `app/sync/bot_sync.py`
- `M` worker · `tests/test_worker_core.py`

</details>

---

## v3.5.0.1 · Correção · 2026-10-21 14:33

**Sessão vencida sem como renovar agora desloga em vez de dar erro 500**

- **Commits:** backend `fc49868` · frontend `6314edd`

**Problema:** Quando a renovação da sessão (refresh token) estava inválida ou vencida, o servidor devolvia erro 500 e o painel ficava preso, com a tela quebrando em vez de pedir um novo login.

**Solução:** O servidor passou a responder 401 nesses casos e o painel, ao receber um 401 sem como renovar a sessão, desloga o usuário e volta para a tela de login.

<details>
<summary>Arquivos alterados (3)</summary>

- `M` backend · `app/services/auth_service.py`
- `A` backend · `tests/test_auth_refresh.py`
- `M` frontend · `src/services/api/client.ts`

</details>

---

## v3.5.0.0 · Geral · 2026-10-20 14:26

**Configuração da máquina por configurar_worker.bat, sem instalador .exe**

- **Commits:** worker `9de792d`, `488ce77` · backend `d1ee8e1`

**Problema:** Preparar uma máquina nova dependia de um instalador `.exe` grande (cerca de 40 MB, hospedado no servidor), que era difícil de manter e quando dava erro não mostrava o que tinha acontecido. O worker também carregava muitas dependências que só o instalador usava.

**Solução:** A máquina agora é configurada pelo `configurar_worker.bat`, que cria o ambiente, instala as dependências e abre uma tela de configuração com andamento e erros, gravando um `setup.log` e oferecendo atalho opcional como administrador. O instalador antigo e o arquivo `.exe` do servidor foram removidos, as dependências do worker ficaram só as necessárias e o README foi atualizado.

<details>
<summary>Arquivos alterados (12)</summary>

- `M` backend · `app/api/v1/public_downloads.py`
- `D` backend · `app/static/downloads/OrkaFlowWorker-Setup.exe`
- `M` worker · `.gitignore`
- `A` worker · `README.md`
- `M` worker · `app/core/constants.py`
- `M` worker · `app/installer/runner_registration.py`
- `A` worker · `app/installer/setup_window.py`
- `D` worker · `app/main.py`
- `D` worker · `app/ui/app_window.py`
- `A` worker · `configurar_worker.bat`
- `D` worker · `requirements-installer.txt`
- `M` worker · `requirements.txt`

</details>

---

## v3.4.2.0 · Melhoria · 2026-10-20 13:38

**Worker: encerra robô que fica 10 minutos sem nenhuma saída**

- **Commits:** worker `7fc9e7f`

**Problema:** Um robô travado, sem escrever nada na saída, podia ficar rodando indefinidamente e ocupar a máquina (principalmente quando exigia foco), bloqueando as demais tasks.

**Solução:** O worker encerra o robô que passa 10 minutos sem nenhuma saída, registra o erro `INACTIVITY_TIMEOUT` e marca a task como timeout. O padrão é 10 minutos, mas cada task pode definir outro limite em `inactivity_timeout_seconds`.

<details>
<summary>Arquivos alterados (3)</summary>

- `M` worker · `app/core/constants.py`
- `M` worker · `app/runtime/task_executor.py`
- `M` worker · `tests/test_worker_core.py`

</details>

---

## v3.4.1.0 · Melhoria · 2026-10-20 12:51

**Painel: avisos de saúde mais claros e sem poluir a tela**

- **Commits:** frontend `d81a43b`, `5cf4281`

**Problema:** O aviso de API degradada só dizia que algo estava errado, sem indicar qual serviço estava sem sinal. O aviso de falhas ocupava muito espaço, os erros apareciam em texto técnico e não era claro por que uma task estava parada sem máquina.

**Solução:** O aviso passa a informar qual serviço está sem sinal. O aviso de falhas ficou compacto, os erros aparecem traduzidos para linguagem simples, o atraso é mostrado em dias quando for grande e a task sem máquina exibe o motivo. A tela de saúde das automações também recebeu ajustes.

<details>
<summary>Arquivos alterados (6)</summary>

- `M` frontend · `src/components/common/task-stuck-badge.tsx`
- `M` frontend · `src/components/layout/connection-banner.tsx`
- `M` frontend · `src/components/layout/system-health-banner.tsx`
- `M` frontend · `src/hooks/use-api-connection.ts`
- `M` frontend · `src/lib/api-error.ts`
- `M` frontend · `src/pages/health/automation-health-page.tsx`

</details>

---

## v3.4.0.1 · Correção · 2026-10-20 12:42

**Cadastro de usuário aceita e-mail de domínio interno (.local)**

- **Commits:** backend `20f195d`

**Problema:** Ao cadastrar um usuário com e-mail de domínio interno da rede, como `empresa.local`, o sistema recusava o endereço como inválido. Esses usuários não conseguiam ser criados.

**Solução:** A validação do e-mail passou a aceitar domínios reservados como `.local`, comuns em rede corporativa. O cadastro funciona normalmente para esses endereços.

<details>
<summary>Arquivos alterados (1)</summary>

- `M` backend · `app/schemas/user.py`

</details>

---

## v3.4.0.0 · Geral · 2026-10-20 12:10

**Estabilidade da fila: concorrência por máquina, saúde do sistema e watchdog**

- **Commits:** backend `91f456d` · frontend `cc7844c` · worker `32222ee`, `6111bb4`

**Problema:** O sistema de junho tinha limitações que causavam parada e confusão: uma máquina só podia ter uma task aberta por vez, o watchdog e o agendador marcavam erro ou pediam parada de tasks só porque não havia máquina livre, o worker não se recuperava bem de queda de token ou de reinício, e o painel não avisava quando algum serviço do sistema estava fora do ar.

**Solução:** O backend passou a controlar a capacidade de cada máquina (várias tasks em segundo plano e 1 com foco por máquina), com reserva atômica da task, supervisão das threads, rota de saúde que devolve 503 quando algo está parado e registro em log com tempos limite no banco. Falta de máquina livre deixa de gerar erro: a task só espera. O worker ganhou supervisor, atualização forçada e reinício automático pelo `.bat`, diferenciação entre erro 401 e 403, e logs com rotação. O painel ganhou o aviso de saúde do sistema, avisos de erro na tela, selos de status das máquinas e "parada há N min" nas tasks. Os agendamentos passam a guardar o último erro e a última task ignorada. Há uma migration de banco que só adiciona colunas, sem mexer nos dados.

<details>
<summary>Arquivos alterados (128)</summary>

- `M` backend · `.gitignore`
- `A` backend · `alembic/versions/b7e4c2a91f10_concurrency_locks_indexes_events.py`
- `M` backend · `app/api/router.py`
- `M` backend · `app/api/v1/health.py`
- `M` backend · `app/api/v1/runners.py`
- `M` backend · `app/api/v1/worker_registration.py`
- `M` backend · `app/core/database.py`
- `M` backend · `app/core/logging.py`
- `M` backend · `app/main.py`
- `M` backend · `app/models/lock.py`
- `M` backend · `app/models/schedule.py`
- `M` backend · `app/models/worker_runtime_event.py`
- `M` backend · `app/repositories/lock_repository.py`
- `M` backend · `app/repositories/runner_repository.py`
- `M` backend · `app/repositories/task_repository.py`
- `M` backend · `app/schemas/schedule.py`
- `M` backend · `app/schemas/worker.py`
- `M` backend · `app/services/automation_health_service.py`
- `A` backend · `app/services/capacity_service.py`
- `M` backend · `app/services/dispatch_service.py`
- `M` backend · `app/services/lock_service.py`
- `M` backend · `app/services/runner_service.py`
- `M` backend · `app/services/scheduler_engine_service.py`
- `D` backend · `app/services/scheduler_service.py`
- `A` backend · `app/services/system_heartbeat_service.py`
- `A` backend · `app/services/task_events.py`
- `A` backend · `app/services/task_rules.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/watchdog_service.py`
- `D` backend · `app/services/worker_error_service.py`
- `D` backend · `app/services/worker_log_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `app/workers/_loop.py`
- `M` backend · `app/workers/dispatcher_main.py`
- `M` backend · `app/workers/main.py`
- `M` backend · `app/workers/scheduler_engine_main.py`
- `M` backend · `app/workers/scheduler_main.py`
- `M` backend · `app/workers/scheduler_runtime_main.py`
- `M` backend · `app/workers/watchdog_main.py`
- `M` backend · `orkaflow-backend.md`
- `A` backend · `tests/__init__.py`
- `A` backend · `tests/test_concurrency_watchdog.py`
- `A` backend · `tests/test_integracao_junho.py`
- `A` frontend · `.env.example`
- `D` frontend · `iniciar`
- `M` frontend · `orkaflow-frontend.md`
- `M` frontend · `package-lock.json`
- `M` frontend · `package.json`
- `D` frontend · `src/App.css`
- `M` frontend · `src/app/providers/auth-provider.tsx`
- `M` frontend · `src/app/router/index.tsx`
- `D` frontend · `src/assets/hero.png`
- `D` frontend · `src/assets/react.svg`
- `D` frontend · `src/assets/vite.svg`
- `A` frontend · `src/components/common/runner-badges.tsx`
- `M` frontend · `src/components/common/status-badge.tsx`
- `A` frontend · `src/components/common/task-stuck-badge.tsx`
- `A` frontend · `src/components/common/toaster.tsx`
- `M` frontend · `src/components/layout/app-shell.tsx`
- `M` frontend · `src/components/layout/app-sidebar.tsx`
- `A` frontend · `src/components/layout/connection-banner.tsx`
- `A` frontend · `src/components/layout/system-health-banner.tsx`
- `A` frontend · `src/hooks/use-api-connection.ts`
- `A` frontend · `src/hooks/use-system-health.ts`
- `A` frontend · `src/lib/api-error.ts`
- `A` frontend · `src/lib/health.ts`
- `A` frontend · `src/lib/query-client.ts`
- `M` frontend · `src/main.tsx`
- `M` frontend · `src/pages/auth/login-page.tsx`
- `M` frontend · `src/pages/automations/automation-detail-page.tsx`
- `M` frontend · `src/pages/automations/automation-form-page.tsx`
- `M` frontend · `src/pages/bot-versions/bot-version-create-page.tsx`
- `M` frontend · `src/pages/bots/bot-create-page.tsx`
- `M` frontend · `src/pages/bots/bot-edit-page.tsx`
- `M` frontend · `src/pages/bots/bots-page.tsx`
- `M` frontend · `src/pages/credentials/credential-create-page.tsx`
- `M` frontend · `src/pages/credentials/credential-detail-page.tsx`
- `M` frontend · `src/pages/credentials/credential-edit-page.tsx`
- `M` frontend · `src/pages/credentials/credentials-page.tsx`
- `M` frontend · `src/pages/errors/task-error-detail-page.tsx`
- `M` frontend · `src/pages/errors/task-errors-page.tsx`
- `M` frontend · `src/pages/profile/profile-page.tsx`
- `M` frontend · `src/pages/profiles/profile-detail-page.tsx`
- `M` frontend · `src/pages/profiles/profile-edit-page.tsx`
- `M` frontend · `src/pages/profiles/profiles-page.tsx`
- `M` frontend · `src/pages/repositories/repository-form-page.tsx`
- `M` frontend · `src/pages/runner-config/runner-config-edit-page.tsx`
- `M` frontend · `src/pages/runner-config/runner-configs-page.tsx`
- `M` frontend · `src/pages/runners/runner-detail-page.tsx`
- `M` frontend · `src/pages/runners/runners-page.tsx`
- `M` frontend · `src/pages/schedules/schedule-detail-page.tsx`
- `M` frontend · `src/pages/schedules/schedule-form-page.tsx`
- `M` frontend · `src/pages/schedules/schedules-page.tsx`
- `M` frontend · `src/pages/tasks/task-detail-page.tsx`
- `M` frontend · `src/pages/tasks/tasks-page.tsx`
- `M` frontend · `src/pages/users/user-create-page.tsx`
- `M` frontend · `src/pages/users/user-detail-page.tsx`
- `M` frontend · `src/pages/users/user-edit-page.tsx`
- `M` frontend · `src/pages/users/users-page.tsx`
- `M` frontend · `src/services/api/bots.ts`
- `M` frontend · `src/services/api/client.ts`
- `M` frontend · `src/services/api/tasks.ts`
- `A` frontend · `src/store/toast-store.ts`
- `M` frontend · `src/types/schedule.ts`
- `M` frontend · `tsconfig.json`
- `A` worker · `PLANO_DE_ACAO_2026-10-20.md`
- `A` worker · `SEGURANCA_MELHORIAS_FUTURAS.md`
- `M` worker · `app/core/config_models.py`
- `M` worker · `app/core/constants.py`
- `M` worker · `app/core/exceptions.py`
- `M` worker · `app/core/http_client.py`
- `M` worker · `app/core/logging_config.py`
- `M` worker · `app/installer/runner_registration.py`
- `A` worker · `app/runtime/auth_refresh.py`
- `A` worker · `app/runtime/bot_usage.py`
- `A` worker · `app/runtime/events.py`
- `M` worker · `app/runtime/main.py`
- `M` worker · `app/runtime/screenshot_reporter.py`
- `A` worker · `app/runtime/services.py`
- `A` worker · `app/runtime/supervisor.py`
- `M` worker · `app/runtime/task_client.py`
- `M` worker · `app/runtime/task_executor.py`
- `M` worker · `app/runtime/task_manager.py`
- `M` worker · `app/sync/bot_installer.py`
- `M` worker · `app/sync/bot_sync.py`
- `M` worker · `iniciar_worker.bat`
- `A` worker · `tests/test_supervisor.py`
- `A` worker · `tests/test_worker_core.py`

</details>

---

## v3.3.1.0 · Melhoria · 2026-10-20 12:08

**Runner: o sistema nunca bloqueia uma máquina**

- **Commits:** backend `b69f293`

**Problema:** Depois de uma parada forçada, o sistema colocava o runner (a máquina) em estado BLOCKED e ele deixava de receber tasks. Era preciso alguém liberar manualmente, e a fila ficava parada por causa de uma proteção do próprio sistema.

**Solução:** A parada forçada deixa de bloquear o runner. Runners que já estavam BLOCKED voltam sozinhos para ONLINE assim que o worker da máquina responde. Só o administrador pode desativar uma máquina ou colocá-la em manutenção.

<details>
<summary>Arquivos alterados (5)</summary>

- `M` backend · `app/services/capacity_service.py`
- `M` backend · `app/services/task_service.py`
- `M` backend · `app/services/watchdog_service.py`
- `M` backend · `app/services/worker_service.py`
- `A` backend · `tests/test_runner_nunca_bloqueado.py`

</details>

---

## v3.3.0.0 · Geral · 2026-06-27 20:07

**Base do sistema: ponto de partida de 27/06**

- **Commits:** worker `02b08f2` · backend `2862001` · frontend `99acf4a`, `95d9328`

**Problema:** Estes commits formam o ponto de partida do histórico: o retrato do sistema que estava em produção em 27/06/2026. Antes das melhorias de outubro não havia registro de versões, então tudo o que já existia entra aqui como base.

**Solução:** O Regente (então chamado OrkaFlow) já tinha o backend em FastAPI com banco Azure SQL, o painel em React e o worker que executa os robôs nas máquinas Windows. Já existiam cadastro de robôs, versões e repositórios, automações com agendamentos, tasks e fila, runners (máquinas), credenciais, perfis e permissões, erros, logs, telemetria, saúde das automações, grupos de exclusão, gatilhos de sucesso, parâmetros de execução dos agendamentos, atualização automática de bots e instalador do worker.

<details>
<summary>Arquivos alterados (333)</summary>

- `A` backend · `.env.example`
- `A` backend · `.gitignore`
- `A` backend · `README.md`
- `A` backend · `alembic.ini`
- `A` backend · `alembic/README`
- `A` backend · `alembic/env.py`
- `A` backend · `alembic/script.py.mako`
- `A` backend · `alembic/versions/05a6b64d45a3_add_storage_type_to_bot_versions.py`
- `A` backend · `alembic/versions/06ef2dd0892f_add_task_telemetries.py`
- `A` backend · `alembic/versions/1b0cfef23990_create_worker_runtime_events_table.py`
- `A` backend · `alembic/versions/2b04d2128741_check_changes.py`
- `A` backend · `alembic/versions/2c8e1f4a6b90_add_unique_open_task_guards.py`
- `A` backend · `alembic/versions/327249154b7b_ajustes_de_campos_de_datas.py`
- `A` backend · `alembic/versions/32faa1309976_add_checksum_and_is_active_to_bot_.py`
- `A` backend · `alembic/versions/3f7b2e9c1d40_add_task_result_json.py`
- `A` backend · `alembic/versions/40af40d590b3_add_runner_status_history.py`
- `A` backend · `alembic/versions/4138c14a08de_add_error_screenshot_to_task_errors.py`
- `A` backend · `alembic/versions/48f716671eb2_add_updated_at_to_locks.py`
- `A` backend · `alembic/versions/521c04d773fb_add_description_to_bots.py`
- `A` backend · `alembic/versions/54c7a0e9b2d1_add_automation_exclusive_groups.py`
- `A` backend · `alembic/versions/6e2f91b7a0c4_add_automation_success_triggers.py`
- `A` backend · `alembic/versions/7f3d2a91c8e4_add_unique_active_lock_key.py`
- `A` backend · `alembic/versions/8b6e2a4d9c31_add_schedule_runtime_parameters.py`
- `A` backend · `alembic/versions/9b1a6c4f2d10_add_queue_operation_indexes.py`
- `A` backend · `alembic/versions/9d4b7c2e1a30_add_automation_health_indexes.py`
- `A` backend · `alembic/versions/a1b2c3d4_profiles_permissions.py`
- `A` backend · `alembic/versions/a3f2e8b1c4d5_add_auto_update_to_bots.py`
- `A` backend · `alembic/versions/b7d3e1f2a9c5_add_automation_default_parameters.py`
- `A` backend · `alembic/versions/c4e8f1a2b3d6_add_schedule_use_default_runtime_params.py`
- `A` backend · `alembic/versions/cc2d58f688e7_campo_relacionamento_status_runner.py`
- `A` backend · `alembic/versions/cd348b178bab_add_created_at_to_permissions.py`
- `A` backend · `alembic/versions/d2fe89a1917e_add_audit_logs_table.py`
- `A` backend · `alembic/versions/e96953f7de5e_create_bots_table.py`
- `A` backend · `alembic/versions/ec2b2d47ce7a_add_screenshot_fields_to_runners.py`
- `A` backend · `alembic/versions/ee675d945755_fix_bots_remove_bot_id.py`
- `A` backend · `alembic/versions/f593523eef6b_create_initial_orkaflow_schema.py`
- `A` backend · `alembic/versions/f6c3c7baa892_adjust_sql_server_foreign_keys.py`
- `A` backend · `alembic/versions/fdaa24e3c4f8_cria_nova_tabela_metadado.py`
- `A` backend · `api.json`
- `A` backend · `app/api/deps.py`
- `A` backend · `app/api/router.py`
- `A` backend · `app/api/v1/auth.py`
- `A` backend · `app/api/v1/automation_health.py`
- `A` backend · `app/api/v1/automations.py`
- `A` backend · `app/api/v1/bot_versions.py`
- `A` backend · `app/api/v1/bots.py`
- `A` backend · `app/api/v1/credentials.py`
- `A` backend · `app/api/v1/dashboard.py`
- `A` backend · `app/api/v1/health.py`
- `A` backend · `app/api/v1/permissions.py`
- `A` backend · `app/api/v1/profiles.py`
- `A` backend · `app/api/v1/public_downloads.py`
- `A` backend · `app/api/v1/repositories.py`
- `A` backend · `app/api/v1/runners.py`
- `A` backend · `app/api/v1/schedules.py`
- `A` backend · `app/api/v1/task_errors.py`
- `A` backend · `app/api/v1/task_logs.py`
- `A` backend · `app/api/v1/tasks.py`
- `A` backend · `app/api/v1/users.py`
- `A` backend · `app/api/v1/worker_auth.py`
- `A` backend · `app/api/v1/worker_credentials.py`
- `A` backend · `app/api/v1/worker_errors.py`
- `A` backend · `app/api/v1/worker_heartbeat.py`
- `A` backend · `app/api/v1/worker_logs.py`
- `A` backend · `app/api/v1/worker_parameters.py`
- `A` backend · `app/api/v1/worker_registration.py`
- `A` backend · `app/api/v1/worker_runtime_events.py`
- `A` backend · `app/api/v1/worker_screenshot.py`
- `A` backend · `app/api/v1/worker_sync.py`
- `A` backend · `app/api/v1/worker_tasks.py`
- `A` backend · `app/api/v1/worker_telemetry.py`
- `A` backend · `app/core/config.py`
- `A` backend · `app/core/database.py`
- `A` backend · `app/core/exceptions.py`
- `A` backend · `app/core/logging.py`
- `A` backend · `app/core/security.py`
- `A` backend · `app/domain/enums.py`
- `A` backend · `app/main.py`
- `A` backend · `app/models/__init__.py`
- `A` backend · `app/models/access_control.py`
- `A` backend · `app/models/audit_log.py`
- `A` backend · `app/models/automation.py`
- `A` backend · `app/models/automation_exclusive_group.py`
- `A` backend · `app/models/automation_parameter.py`
- `A` backend · `app/models/automation_runner.py`
- `A` backend · `app/models/automation_success_trigger.py`
- `A` backend · `app/models/base.py`
- `A` backend · `app/models/bot.py`
- `A` backend · `app/models/bot_version.py`
- `A` backend · `app/models/credential.py`
- `A` backend · `app/models/credential_item.py`
- `A` backend · `app/models/lock.py`
- `A` backend · `app/models/notification.py`
- `A` backend · `app/models/repository.py`
- `A` backend · `app/models/runner.py`
- `A` backend · `app/models/runner_config.py`
- `A` backend · `app/models/runner_status_history.py`
- `A` backend · `app/models/schedule.py`
- `A` backend · `app/models/task.py`
- `A` backend · `app/models/task_error.py`
- `A` backend · `app/models/task_log.py`
- `A` backend · `app/models/task_parameter.py`
- `A` backend · `app/models/task_telemetry.py`
- `A` backend · `app/models/user.py`
- `A` backend · `app/models/worker_runtime_event.py`
- `A` backend · `app/repositories/__init__.py`
- `A` backend · `app/repositories/audit_log_repository.py`
- `A` backend · `app/repositories/automation_exclusive_group_repository.py`
- `A` backend · `app/repositories/automation_parameter_repository.py`
- `A` backend · `app/repositories/automation_repository.py`
- `A` backend · `app/repositories/automation_runner_repository.py`
- `A` backend · `app/repositories/automation_success_trigger_repository.py`
- `A` backend · `app/repositories/bot_repository.py`
- `A` backend · `app/repositories/bot_version_repository.py`
- `A` backend · `app/repositories/credential_repository.py`
- `A` backend · `app/repositories/dashboard_repository.py`
- `A` backend · `app/repositories/lock_repository.py`
- `A` backend · `app/repositories/permission_repository.py`
- `A` backend · `app/repositories/profile_repository.py`
- `A` backend · `app/repositories/repository_repository.py`
- `A` backend · `app/repositories/runner_repository.py`
- `A` backend · `app/repositories/schedule_repository.py`
- `A` backend · `app/repositories/task_error_repository.py`
- `A` backend · `app/repositories/task_error_repository_extended.py`
- `A` backend · `app/repositories/task_log_repository.py`
- `A` backend · `app/repositories/task_repository.py`
- `A` backend · `app/repositories/task_telemetry_repository.py`
- `A` backend · `app/repositories/user_repository.py`
- `A` backend · `app/repositories/worker_runtime_event_repository.py`
- `A` backend · `app/schemas/__init__.py`
- `A` backend · `app/schemas/auth.py`
- `A` backend · `app/schemas/automation.py`
- `A` backend · `app/schemas/automation_health.py`
- `A` backend · `app/schemas/bot.py`
- `A` backend · `app/schemas/bot_version.py`
- `A` backend · `app/schemas/common.py`
- `A` backend · `app/schemas/credential.py`
- `A` backend · `app/schemas/dashboard.py`
- `A` backend · `app/schemas/profile.py`
- `A` backend · `app/schemas/repository.py`
- `A` backend · `app/schemas/runner.py`
- `A` backend · `app/schemas/runner_overview.py`
- `A` backend · `app/schemas/schedule.py`
- `A` backend · `app/schemas/task.py`
- `A` backend · `app/schemas/task_error.py`
- `A` backend · `app/schemas/task_log.py`
- `A` backend · `app/schemas/user.py`
- `A` backend · `app/schemas/worker.py`
- `A` backend · `app/schemas/worker_parameter.py`
- `A` backend · `app/services/audit_log_service.py`
- `A` backend · `app/services/auth_service.py`
- `A` backend · `app/services/automation_health_service.py`
- `A` backend · `app/services/automation_parameter_service.py`
- `A` backend · `app/services/automation_runner_service.py`
- `A` backend · `app/services/automation_service.py`
- `A` backend · `app/services/automation_trigger_service.py`
- `A` backend · `app/services/bot_service.py`
- `A` backend · `app/services/bot_version_service.py`
- `A` backend · `app/services/credential_service.py`
- `A` backend · `app/services/dashboard_service.py`
- `A` backend · `app/services/dispatch_service.py`
- `A` backend · `app/services/lock_service.py`
- `A` backend · `app/services/permission_service.py`
- `A` backend · `app/services/profile_service.py`
- `A` backend · `app/services/repository_service.py`
- `A` backend · `app/services/runner_service.py`
- `A` backend · `app/services/schedule_service.py`
- `A` backend · `app/services/scheduler_engine_service.py`
- `A` backend · `app/services/scheduler_runtime_service.py`
- `A` backend · `app/services/scheduler_service.py`
- `A` backend · `app/services/task_error_service.py`
- `A` backend · `app/services/task_log_service.py`
- `A` backend · `app/services/task_service.py`
- `A` backend · `app/services/user_service.py`
- `A` backend · `app/services/watchdog_service.py`
- `A` backend · `app/services/worker_error_service.py`
- `A` backend · `app/services/worker_log_service.py`
- `A` backend · `app/services/worker_service.py`
- `A` backend · `app/static/downloads/OrkaFlowWorker-Setup.exe`
- `A` backend · `app/static/downloads/nssm.exe`
- `A` backend · `app/workers/dispatcher_main.py`
- `A` backend · `app/workers/main.py`
- `A` backend · `app/workers/scheduler_engine_main.py`
- `A` backend · `app/workers/scheduler_main.py`
- `A` backend · `app/workers/scheduler_runtime_main.py`
- `A` backend · `app/workers/watchdog_main.py`
- `A` backend · `docs/README_BANCO_ORKAFLOW.md`
- `A` backend · `docs/project_conventions.md`
- `A` backend · `inciar`
- `A` backend · `orkaflow-backend.md`
- `A` backend · `pyproject.toml`
- `A` backend · `requirements.txt`
- `A` backend · `scripts/migrate_schedule_params_to_automation.py`
- `A` backend · `scripts/migrate_schedule_use_default_flag.py`
- `A` backend · `security.py`
- `A` frontend · `.env`
- `A` frontend · `.gitignore`
- `A` frontend · `README.md`
- `A` frontend · `components.json`
- `A` frontend · `eslint.config.js`
- `A` frontend · `index.html`
- `A` frontend · `iniciar`
- `A` frontend · `orkaflow-frontend.md`
- `A` frontend · `package-lock.json`
- `A` frontend · `package.json`
- `A` frontend · `postcss.config.js`
- `A` frontend · `public/favicon.svg`
- `A` frontend · `public/favicon2.svg`
- `A` frontend · `public/icons.svg`
- `A` frontend · `public/icons2.svg`
- `A` frontend · `public/orkaflow-icon.ico`
- `A` frontend · `public/orkaflow-icon.png`
- `A` frontend · `src/App.css`
- `A` frontend · `src/App.tsx`
- `A` frontend · `src/app/providers/auth-provider.tsx`
- `A` frontend · `src/app/router/index.tsx`
- `A` frontend · `src/assets/hero.png`
- `A` frontend · `src/assets/react.svg`
- `A` frontend · `src/assets/vite.svg`
- `A` frontend · `src/components/common/status-badge.tsx`
- `A` frontend · `src/components/layout/app-header.tsx`
- `A` frontend · `src/components/layout/app-shell.tsx`
- `A` frontend · `src/components/layout/app-sidebar.tsx`
- `A` frontend · `src/components/layout/user-menu.tsx`
- `A` frontend · `src/components/ui/button.tsx`
- `A` frontend · `src/components/ui/dropdown-menu.tsx`
- `A` frontend · `src/components/ui/separator.tsx`
- `A` frontend · `src/components/ui/sheet.tsx`
- `A` frontend · `src/components/ui/tooltip.tsx`
- `A` frontend · `src/index.css`
- `A` frontend · `src/layouts/app-layout.tsx`
- `A` frontend · `src/layouts/auth-layout.tsx`
- `A` frontend · `src/lib/utils.ts`
- `A` frontend · `src/main.tsx`
- `A` frontend · `src/pages/auth/login-page.tsx`
- `A` frontend · `src/pages/automations/automation-detail-page.tsx`
- `A` frontend · `src/pages/automations/automation-form-page.tsx`
- `A` frontend · `src/pages/automations/automations-page.tsx`
- `A` frontend · `src/pages/bot-versions/bot-version-create-page.tsx`
- `A` frontend · `src/pages/bot-versions/bot-version-detail-page.tsx`
- `A` frontend · `src/pages/bot-versions/bot-versions-page.tsx`
- `A` frontend · `src/pages/bots/bot-create-page.tsx`
- `A` frontend · `src/pages/bots/bot-detail-page.tsx`
- `A` frontend · `src/pages/bots/bot-edit-page.tsx`
- `A` frontend · `src/pages/bots/bots-page.tsx`
- `A` frontend · `src/pages/credentials/credential-create-page.tsx`
- `A` frontend · `src/pages/credentials/credential-detail-page.tsx`
- `A` frontend · `src/pages/credentials/credential-edit-page.tsx`
- `A` frontend · `src/pages/credentials/credentials-page.tsx`
- `A` frontend · `src/pages/dashboard/dashboard-page.tsx`
- `A` frontend · `src/pages/errors/task-error-detail-page.tsx`
- `A` frontend · `src/pages/errors/task-errors-page.tsx`
- `A` frontend · `src/pages/health/automation-health-page.tsx`
- `A` frontend · `src/pages/profile/profile-page.tsx`
- `A` frontend · `src/pages/profiles/profile-create-page.tsx`
- `A` frontend · `src/pages/profiles/profile-detail-page.tsx`
- `A` frontend · `src/pages/profiles/profile-edit-page.tsx`
- `A` frontend · `src/pages/profiles/profiles-page.tsx`
- `A` frontend · `src/pages/repositories/repositories-page.tsx`
- `A` frontend · `src/pages/repositories/repository-detail-page.tsx`
- `A` frontend · `src/pages/repositories/repository-form-page.tsx`
- `A` frontend · `src/pages/runner-config/runner-config-detail-page.tsx`
- `A` frontend · `src/pages/runner-config/runner-config-edit-page.tsx`
- `A` frontend · `src/pages/runner-config/runner-configs-page.tsx`
- `A` frontend · `src/pages/runner-config/runners-page.tsx`
- `A` frontend · `src/pages/runner-config/worker-registration-page.tsx`
- `A` frontend · `src/pages/runners/runner-detail-page.tsx`
- `A` frontend · `src/pages/runners/runners-page.tsx`
- `A` frontend · `src/pages/schedules/schedule-detail-page.tsx`
- `A` frontend · `src/pages/schedules/schedule-form-page.tsx`
- `A` frontend · `src/pages/schedules/schedules-page.tsx`
- `A` frontend · `src/pages/tasks/task-create-page.tsx`
- `A` frontend · `src/pages/tasks/task-detail-page.tsx`
- `A` frontend · `src/pages/tasks/tasks-page.tsx`
- `A` frontend · `src/pages/users/user-create-page.tsx`
- `A` frontend · `src/pages/users/user-detail-page.tsx`
- `A` frontend · `src/pages/users/user-edit-page.tsx`
- `A` frontend · `src/pages/users/users-page.tsx`
- `A` frontend · `src/services/api/auth.ts`
- `A` frontend · `src/services/api/automation-health.ts`
- `A` frontend · `src/services/api/automations.ts`
- `A` frontend · `src/services/api/bot-versions.ts`
- `A` frontend · `src/services/api/bots.ts`
- `A` frontend · `src/services/api/client.ts`
- `A` frontend · `src/services/api/credentials.ts`
- `A` frontend · `src/services/api/dashboard.ts`
- `A` frontend · `src/services/api/permissions.ts`
- `A` frontend · `src/services/api/profiles.ts`
- `A` frontend · `src/services/api/repositories.ts`
- `A` frontend · `src/services/api/runners.ts`
- `A` frontend · `src/services/api/schedules.ts`
- `A` frontend · `src/services/api/task-errors.ts`
- `A` frontend · `src/services/api/tasks.ts`
- `A` frontend · `src/services/api/users.ts`
- `A` frontend · `src/store/auth-store.ts`
- `A` frontend · `src/types/auth.ts`
- `A` frontend · `src/types/bot-version.ts`
- `A` frontend · `src/types/bot.ts`
- `A` frontend · `src/types/credential.ts`
- `A` frontend · `src/types/runner.ts`
- `A` frontend · `src/types/schedule.ts`
- `A` frontend · `tailwind.config.js`
- `A` frontend · `tsconfig.app.json`
- `A` frontend · `tsconfig.json`
- `A` frontend · `tsconfig.node.json`
- `A` frontend · `vite.config.ts`
- `A` worker · `.gitignore`
- `A` worker · `app/__init__.py`
- `A` worker · `app/core/config_models.py`
- `A` worker · `app/core/constants.py`
- `A` worker · `app/core/exceptions.py`
- `A` worker · `app/core/http_client.py`
- `A` worker · `app/core/json_store.py`
- `A` worker · `app/core/logging_config.py`
- `A` worker · `app/core/machine_info.py`
- `A` worker · `app/core/paths.py`
- `A` worker · `app/core/security.py`
- `A` worker · `app/diagnostics/prereq_checks.py`
- `A` worker · `app/installer/bootstrap.py`
- `A` worker · `app/installer/runner_registration.py`
- `A` worker · `app/installer/runtime_setup.py`
- `A` worker · `app/main.py`
- `A` worker · `app/runtime/__init__.py`
- `A` worker · `app/runtime/main.py`
- `A` worker · `app/runtime/screenshot_reporter.py`
- `A` worker · `app/runtime/task_client.py`
- `A` worker · `app/runtime/task_executor.py`
- `A` worker · `app/runtime/task_manager.py`
- `A` worker · `app/sync/bot_installer.py`
- `A` worker · `app/sync/bot_sync.py`
- `A` worker · `app/ui/app_window.py`
- `A` worker · `iniciar_worker.bat`
- `A` worker · `requirements.txt`

</details>
