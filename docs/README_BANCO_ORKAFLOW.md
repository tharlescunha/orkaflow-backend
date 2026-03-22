# Documentação do Banco de Dados — OrkaFlow

## Visão geral

O banco do OrkaFlow foi pensado para ser o centro operacional do sistema. Ele precisa sustentar cadastro, execução, agendamento, rastreabilidade, logs, erros, locks e credenciais. A base proposta nos documentos do projeto é composta por 7 blocos: base e segurança, infraestrutura de execução, catálogo de bots, camada operacional, execução, agendamento e segredos. Nessa divisão entram as tabelas `users`, `repositories`, `runners`, `runner_configs`, `bots`, `bot_versions`, `automations`, `automation_runners`, `automation_parameters`, `notifications`, `tasks`, `task_parameters`, `task_logs`, `task_errors`, `locks`, `schedules`, `credentials` e `credential_items`. fileciteturn1file1L1-L25

A arquitetura recomendada para o backend usa FastAPI, SQLAlchemy 2.x, Alembic, SQL Server e `pyodbc`. A ideia é manter `models`, `schemas`, `repositories`, `services` e `api` bem separados, evitando regra de negócio nas rotas e SQL espalhado pelo projeto. fileciteturn1file8L1-L18 fileciteturn1file0L1-L25

---

## Objetivo do banco

O banco precisa resolver cinco coisas principais:

1. guardar a estrutura administrativa do sistema;
2. controlar as máquinas executoras;
3. versionar bots e automações;
4. registrar tarefas, logs, erros e locks;
5. sustentar agendamento e credenciais com segurança.

Pelos documentos do projeto, o backend deve ser o ponto central de decisão: ele controla fila, capacidade, lock, versão do bot, agendamento, rastreabilidade e segurança. fileciteturn1file3L1-L17

---

## Padrões gerais de modelagem

Antes das tabelas, o projeto define alguns padrões importantes:

- quase toda tabela deve ter `id`, `created_at` e `updated_at` quando fizer sentido;
- tabelas operacionais podem ter `active` ou `enabled`;
- datas devem ficar em UTC;
- campos booleanos precisam ser claros;
- status importantes devem virar enum;
- campos de busca precisam de índice;
- campos que não podem repetir devem ter `unique`. fileciteturn1file1L26-L31 fileciteturn1file2L1-L17

Minha recomendação é seguir isso sem inventar muito:

- nome de tabela no plural;
- nome de model no singular;
- soft delete onde fizer sentido, principalmente em `repositories`, `bots`, `automations`, `credentials`, `schedules` e `runners`;
- segredos sempre criptografados ou com hash, nunca em texto puro.

---

## Blocos do banco

## 1. Base e segurança

### `repositories`

Separa bots, credenciais e automações por contexto de negócio, como `DEFAULT`, `CIF-TEGRAM` e outros. O documento recomenda `name` único, `active` para desativação lógica e a possibilidade de existir um repositório `DEFAULT` inicial. Relaciona com `bots`, `automations` e `credentials`. fileciteturn1file1L26-L31

Campos principais:

- `id`
- `name`
- `description`
- `active`
- `created_at`
- `updated_at`

### `users`

Guarda os usuários do painel. O projeto define `login` único, `email` único, senha sempre com hash e `role` controlada por enum ou string fechada. As roles sugeridas são `admin`, `operator` e `viewer`. Relaciona com `tasks`, `notifications` e `bot_versions`. fileciteturn1file7L1-L18

Campos principais:

- `id`
- `name`
- `login`
- `email`
- `password_hash`
- `active`
- `role`
- `created_at`
- `updated_at`

---

## 2. Infraestrutura de execução

### `runners`

Representa as máquinas executoras. O documento destaca `uuid`, `token_hash`, heartbeat, status e dados técnicos da máquina. Um runner desativado não executa tarefa, e runners `offline`, `maintenance` ou `blocked` também não devem receber execução. fileciteturn1file7L19-L41

Campos principais:

- `id`
- `uuid`
- `name`
- `label`
- `host_name`
- `ip`
- `os_name`
- `os_version`
- `cpu_arch`
- `memory_total`
- `token_hash`
- `status`
- `last_heartbeat`
- `access_remote`
- `enabled`
- `created_at`
- `updated_at`

Status sugeridos:

- `online`
- `offline`
- `busy`
- `maintenance`
- `blocked` fileciteturn1file5L1-L17

### `runner_configs`

Separa a configuração operacional do runner da identidade da máquina. O documento trata essa decisão como correta e sugere uma relação 1:1 com `runners`. `runner_id` deve ser único. `allowed_parallel_bots` pode começar como JSON. fileciteturn1file7L42-L56

Campos principais:

- `id`
- `runner_id`
- `max_concurrency`
- `allowed_parallel_bots`
- `polling_interval`
- `auto_update_bots`
- `install_all_bots_on_register`
- `maintenance_mode`
- `updated_at`

---

## 3. Catálogo de bots

### `bots`

É o catálogo principal de robôs. O backend proposto define tecnologia, fonte, entrypoint, timeout padrão, repositório e versão atual. fileciteturn1file2L18-L30

Campos principais:

- `id`
- `bot_id`
- `name`
- `technology`
- `repository_id`
- `current_version`
- `release_version`
- `source_type`
- `source_url`
- `entrypoint`
- `requirements_file`
- `timeout_default`
- `active`
- `created_at`
- `updated_at`

### `bot_versions`

É uma tabela crítica para auditoria. Cada execução de task deve registrar a versão usada. O projeto recomenda versionamento formal com `version`, `commit_hash`, `branch`, `artifact_path`, `changelog` e `created_by`. fileciteturn1file2L31-L37 fileciteturn1file5L18-L35

Campos principais:

- `id`
- `bot_id`
- `version`
- `commit_hash`
- `branch`
- `artifact_path`
- `changelog`
- `created_by`
- `created_at`
- `updated_at`

Regra importante:

- `bot_id + version` deve ser único. fileciteturn1file13L19-L31

---

## 4. Camada operacional

### `automations`

Representa a camada operacional do bot. Relaciona o bot a um contexto de execução, com nome, prioridade e tipo de notificação. fileciteturn1file2L37-L48

Campos principais:

- `id`
- `name`
- `label`
- `description`
- `bot_id`
- `repository_id`
- `default_priority`
- `notification_type`
- `active`
- `created_at`
- `updated_at`

### `automation_runners`

Tabela associativa entre automações e runners. O documento reforça a relação N:N entre `Automation` e `Runner`. fileciteturn1file13L1-L18

Campos principais:

- `id`
- `automation_id`
- `runner_id`

Regra importante:

- `automation_id + runner_id` deve ser único. fileciteturn1file13L19-L31

### `automation_parameters`

Define os parâmetros permitidos para cada automação. O projeto sugere tipos controlados por enum, valor padrão, obrigatoriedade e ordem de exibição. `allowed_values` pode começar como JSON. fileciteturn1file5L18-L35

Campos principais:

- `id`
- `automation_id`
- `name`
- `label`
- `description`
- `type`
- `allowed_values`
- `default_value`
- `required`
- `order_index`

### `notifications`

Relaciona usuários com automações para notificação. Pode nascer já no MVP, embora o documento admita empurrar isso para fase 2 se precisar cortar escopo. Os tipos sugeridos são `email`, `panel` e `webhook`. fileciteturn1file13L1-L18 fileciteturn1file5L17-L35

Campos principais:

- `id`
- `automation_id`
- `user_id`
- `notification_type`
- `active`
- `created_at`
- `updated_at`

---

## 5. Execução

### `tasks`

É o centro da operação. O documento trata `tasks` como a entidade mais importante da execução. Ela precisa amarrar automação, versão do bot, runner, status, prioridade, timeout, retry, modo de execução e timestamps da execução. fileciteturn1file2L48-L60

Campos principais:

- `id`
- `automation_id`
- `bot_version_id`
- `runner_id`
- `created_by`
- `schedule_id`
- `parent_task_id`
- `priority`
- `status`
- `requested_start_at`
- `started_at`
- `finished_at`
- `last_update_at`
- `final_message`
- `items_processed`
- `items_failed`
- `timeout_seconds`
- `retry_count`
- `execution_mode`
- `created_at`

Status sugeridos:

- `waiting`
- `scheduled`
- `ready`
- `running`
- `stop_requested`
- `canceled`
- `finished`
- `error`
- `timeout` fileciteturn1file5L1-L17

Modos de execução sugeridos:

- `manual`
- `scheduled`
- `retry`
- `reprocess`
- `api` fileciteturn1file5L17-L35

### `task_parameters`

Guarda o valor final dos parâmetros de uma task. Isso é importante porque a execução precisa congelar o que foi usado naquele momento, inclusive quando veio de credencial. fileciteturn1file5L18-L35

Campos principais:

- `id`
- `task_id`
- `parameter_name`
- `parameter_value`
- `is_secret`
- `resolved_from_credential_item_id`

### `task_logs`

Guarda logs estruturados por task. O projeto recomenda isso para rastreabilidade. Deve haver índice em `task_id` e `created_at`. fileciteturn1file2L60-L66 fileciteturn1file5L1-L8

Campos principais:

- `id`
- `task_id`
- `level`
- `message`
- `reference`
- `error_type`
- `source`
- `sequence_number`
- `runner_id`
- `event_code`
- `created_at`

### `task_errors`

Separa erro técnico e erro de negócio dos logs comuns. O documento considera isso correto e importante. Deve haver índice em `task_id`, `created_at` e `error_type`. fileciteturn1file2L60-L66 fileciteturn1file5L1-L8

Campos principais:

- `id`
- `task_id`
- `error_type`
- `message`
- `stacktrace`
- `error_category`
- `is_retryable`
- `source`
- `code`
- `created_at`

### `locks`

É essencial para não encavalar execução. O sistema precisa respeitar locks por runner, automação, bot, sistema externo, credencial ou recurso de negócio. Deve haver índice em `lock_key`, `scope_type`, `active` e `expires_at`. fileciteturn1file2L66-L71 fileciteturn1file5L8-L17

Campos principais:

- `id`
- `lock_key`
- `scope_type`
- `owner_task_id`
- `runner_id`
- `acquired_at`
- `expires_at`
- `released_at`
- `active`

---

## 6. Agendamento

### `schedules`

Gera tasks automaticamente. O scheduler precisa suportar calendário e cron, e respeitar política de criação para evitar duplicidade. Os tipos sugeridos são `calendar` e `cron`. Os status sugeridos são `active`, `inactive`, `paused` e `error`. fileciteturn1file8L18-L35 fileciteturn1file5L17-L25

Campos principais:

- `id`
- `name`
- `automation_id`
- `priority`
- `schedule_type`
- `calendar_type`
- `cron_expression`
- `policy`
- `parameters_json`
- `timezone`
- `active`
- `start_at`
- `end_at`
- `last_run_at`
- `next_run_at`
- `status`
- `created_at`
- `updated_at`

Índices importantes:

- `automation_id`
- `active`
- `next_run_at` fileciteturn1file5L1-L8

---

## 7. Segredos

### `credentials`

Representa o agrupador da credencial. Fica vinculado a um `repository` e precisa suportar desativação lógica. O documento recomenda `repository_id + label` como combinação única. fileciteturn1file5L8-L16

Campos principais:

- `id`
- `label`
- `repository_id`
- `active`
- `created_at`
- `updated_at`

### `credential_items`

Guarda os itens da credencial. O valor deve ir criptografado. A combinação `credential_id + key_name` deve ser única. fileciteturn1file2L66-L71 fileciteturn1file5L8-L16

Campos principais:

- `id`
- `credential_id`
- `key_name`
- `encrypted_value`
- `value_type`
- `masked_preview`
- `created_at`
- `updated_at`

---

## Relacionamentos gerais do sistema

O mapa resumido recomendado no documento é este: `Repository 1:N Bot`, `Repository 1:N Automation`, `Repository 1:N Credential`, `User 1:N Task`, `User 1:N BotVersion`, `User 1:N Notification`, `Runner 1:1 RunnerConfig`, `Runner 1:N Task`, `Runner 1:N Lock`, `Bot 1:N BotVersion`, `Bot 1:N Automation`, `Automation N:N Runner via AutomationRunner`, `Automation 1:N AutomationParameter`, `Automation 1:N Task`, `Automation 1:N Schedule`, `Automation 1:N Notification`, `BotVersion 1:N Task`, `Task 1:N TaskParameter`, `Task 1:N TaskLog`, `Task 1:N TaskError`, `Task 1:N Lock` e `Credential 1:N CredentialItem`. fileciteturn1file13L1-L18

---

## Índices e constraints importantes

O projeto já sugere alguns índices e unicidades que não devem ser esquecidos:

- `repositories.name` único;
- `users.login` único;
- `users.email` único;
- `runners.uuid` único;
- `runner_configs.runner_id` único;
- `bots.bot_id` único;
- `bot_versions (bot_id, version)` único;
- `automation_runners (automation_id, runner_id)` único;
- `credentials (repository_id, label)` único;
- `credential_items (credential_id, key_name)` único;
- índices em `tasks` para `(status, priority, requested_start_at)` e `runner_id`;
- índices em `task_logs.task_id`, `task_errors.task_id`, `schedules.next_run_at`, `locks.lock_key`, `locks.expires_at`. fileciteturn1file5L1-L16

---

## Enums recomendados

Os documentos sugerem criar logo no começo enums para:

- `RunnerStatus`
- `TaskStatus`
- `ScheduleStatus`
- `ScheduleType`
- `ExecutionMode`
- `LockScopeType`
- `NotificationType`
- `ParameterType` fileciteturn1file5L16-L35

Isso evita string solta pelo sistema inteiro, o que também é reforçado no documento de backend. fileciteturn1file2L71-L74

---

## Seeds iniciais obrigatórios

Na primeira subida do sistema, a recomendação é criar pelo menos:

- repositório `DEFAULT`;
- usuário `admin` inicial;
- roles básicas por código, não por tabela, se você mantiver enum. fileciteturn1file5L8-L17

---

## Ordem correta de criação dos models

Para não se enrolar com foreign key, a ordem recomendada é:

1. `Repository`
2. `User`
3. `Runner`
4. `RunnerConfig`
5. `Bot`
6. `BotVersion`
7. `Automation`
8. `AutomationRunner`
9. `AutomationParameter`
10. `Notification`
11. `Schedule`
12. `Credential`
13. `CredentialItem`
14. `Task`
15. `TaskParameter`
16. `TaskLog`
17. `TaskError`
18. `Lock` fileciteturn1file13L19-L31

---

## Ordem recomendada das migrations

No Alembic, a ordem indicada é:

### Migration 001
- `repositories`
- `users`

### Migration 002
- `runners`
- `runner_configs`

### Migration 003
- `bots`
- `bot_versions`

### Migration 004
- `automations`
- `automation_runners`
- `automation_parameters`
- `notifications`

### Migration 005
- `schedules`

### Migration 006
- `credentials`
- `credential_items`

### Migration 007
- `tasks`
- `task_parameters`
- `task_logs`
- `task_errors`
- `locks`

### Migration 008
- índices adicionais
- unique constraints finos
- seeds iniciais fileciteturn1file13L19-L31

Essa ordem é boa porque reduz retrabalho e evita dependência quebrada.

---

## Como organizar isso no projeto FastAPI

A estrutura recomendada para os models no backend é:

```text
app/
├── core/
│   ├── config.py
│   ├── database.py
│   └── exceptions.py
├── models/
│   ├── base.py
│   ├── repository.py
│   ├── user.py
│   ├── runner.py
│   ├── runner_config.py
│   ├── bot.py
│   ├── bot_version.py
│   ├── automation.py
│   ├── automation_runner.py
│   ├── automation_parameter.py
│   ├── schedule.py
│   ├── credential.py
│   ├── credential_item.py
│   ├── task.py
│   ├── task_parameter.py
│   ├── task_log.py
│   ├── task_error.py
│   ├── lock.py
│   └── notification.py
└── main.py
```

Essa organização também acompanha a separação entre `models`, `schemas`, `repositories`, `services` e `api`. fileciteturn1file13L31-L37 fileciteturn1file0L1-L25

---

## Como rodar o projeto com o banco — passo a passo

## Pré-requisitos

Antes de rodar, você precisa confirmar:

- Python configurado;
- ambiente virtual ativo;
- SQL Server acessível;
- porta `1433` liberada;
- usuário e senha válidos;
- driver `ODBC Driver 17 for SQL Server` ou `ODBC Driver 18 for SQL Server` instalado na máquina. fileciteturn1file11L1-L18

## 1. Instalar dependências

No ambiente virtual:

```bash
pip install fastapi uvicorn sqlalchemy alembic pyodbc pydantic pydantic-settings passlib python-jose cryptography
```

A stack sugerida pelo documento usa exatamente FastAPI, SQLAlchemy, Alembic, SQL Server e `pyodbc`, com bibliotecas auxiliares para hash, JWT e criptografia. fileciteturn1file8L1-L18

## 2. Configurar o `.env`

O projeto recomenda centralizar tudo em variável de ambiente, sem espalhar string de conexão no código. Exemplo esperado:

```env
APP_NAME=OrkaFlow API
APP_ENV=development
APP_DEBUG=true
APP_HOST=0.0.0.0
APP_PORT=8000
DB_HOST=SEU_SERVIDOR
DB_PORT=1433
DB_NAME=SEU_BANCO
DB_USER=SEU_USUARIO
DB_PASSWORD=SUA_SENHA
DB_DRIVER=ODBC Driver 18 for SQL Server
API_PREFIX=/api/v1
JWT_SECRET_KEY=sua_chave
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
RUNNER_TOKEN_SECRET=sua_chave_runner
CREDENTIAL_ENCRYPTION_KEY=sua_chave_credencial
```

O `config.py` deve ser o ponto central para ler essas variáveis. O `database.py` deve montar a URL, criar o engine, criar a `SessionLocal` e expor `get_db()`. fileciteturn1file10L1-L18 fileciteturn1file14L1-L18

## 3. Garantir que a API sobe

Antes de mexer em migration, a documentação recomenda validar a base da API:

```bash
uvicorn app.main:app --reload
```

Depois testar:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/api/v1/health` fileciteturn1file11L1-L18

## 4. Preparar a conexão com SQL Server

A conexão deve ser criada em um único lugar, normalmente `app/core/database.py`, usando `mssql+pyodbc`, engine única, session factory e `get_db()`. Também é recomendado usar `pool_pre_ping=True` e timeout configurado. fileciteturn1file14L1-L18

## 5. Criar os models ORM

Depois da base pronta, você cria os models na ordem correta mostrada acima. Cada model precisa ter:

- nome da tabela;
- colunas e tipos;
- índices;
- unique constraints;
- foreign keys;
- relationships. fileciteturn1file13L31-L37

## 6. Inicializar o Alembic

```bash
alembic init alembic
```

Depois ajuste o `alembic/env.py` para apontar para o metadata dos seus models e usar a URL do banco. O documento é claro ao recomendar migrações desde o começo. fileciteturn1file3L1-L17

## 7. Gerar a primeira migration

```bash
alembic revision --autogenerate -m "create initial schema"
```

Minha recomendação é revisar o arquivo gerado antes de aplicar, principalmente por estar usando SQL Server.

## 8. Aplicar a migration

```bash
alembic upgrade head
```

Isso vai criar a estrutura do banco de forma versionada.

## 9. Criar seeds iniciais

Depois da migration, você sobe ao menos:

- `DEFAULT` em `repositories`;
- admin inicial em `users`. fileciteturn1file5L8-L17

## 10. Validar o banco

Depois de aplicar tudo, confira no SQL Server ou DBeaver:

- se as tabelas foram criadas;
- se os índices apareceram;
- se os `unique` ficaram corretos;
- se as foreign keys estão corretas;
- se os seeds iniciais existem.

---

## Fluxo recomendado de desenvolvimento

A ordem prática sugerida pelo documento é esta:

### Etapa 1
- `Repository`
- `User`
- config do banco
- base ORM
- Alembic

### Etapa 2
- `Runner`
- `RunnerConfig`
- auth do painel
- auth do worker

### Etapa 3
- `Bot`
- `BotVersion`

### Etapa 4
- `Automation`
- `AutomationRunner`
- `AutomationParameter`

### Etapa 5
- `Task`
- `TaskParameter`
- `TaskLog`
- `TaskError`
- `Lock`

### Etapa 6
- `Schedule`

### Etapa 7
- `Credential`
- `CredentialItem`

### Etapa 8
- `Notification` fileciteturn1file4L1-L17

---

## Regras críticas que o banco já precisa suportar

Estas regras aparecem como fundamentais no material do projeto:

- worker só executa o que o painel permitir;
- bot deve ser sincronizado e atualizado quando houver divergência;
- timeout deve encerrar processo e subprocessos;
- locks precisam ser respeitados;
- toda execução precisa registrar a versão do bot usada;
- scheduler deve suportar calendário e cron;
- credenciais precisam ser criptografadas;
- logs nunca podem expor segredo;
- runner desativado não executa tarefa. fileciteturn1file5L17-L35

Essas regras impactam diretamente a modelagem e justificam campos como `bot_version_id`, `timeout_seconds`, `status`, `lock_key`, `scope_type`, `encrypted_value`, `token_hash` e `runner_config.max_concurrency`. fileciteturn1file5L17-L35

---

## O que evitar

A recomendação do documento é evitar:

- conexão aberta manualmente em cada arquivo;
- SQL cru espalhado no projeto;
- procedure para tudo logo no começo;
- microserviços cedo demais;
- event bus complexo antes do básico funcionar. fileciteturn1file14L1-L18 fileciteturn1file3L1-L17

Minha opinião direta: para o teu caso, o melhor é seguir com **SQLAlchemy + Alembic** e deixar o banco nascer por migration. Fica mais profissional, mais rastreável e muito mais fácil de manter.

---

## Resumo final

O banco do OrkaFlow deve nascer orientado a execução real, com foco em rastreabilidade, versionamento, segurança e controle operacional. A estrutura base recomendada é formada por `repositories`, `users`, `runners`, `runner_configs`, `bots`, `bot_versions`, `automations`, `automation_runners`, `automation_parameters`, `notifications`, `tasks`, `task_parameters`, `task_logs`, `task_errors`, `locks`, `schedules`, `credentials` e `credential_items`. A forma correta de subir isso é organizar os models, configurar o SQLAlchemy, preparar o Alembic, gerar migrations, aplicar no SQL Server e criar seeds iniciais. fileciteturn1file1L1-L25 fileciteturn1file3L1-L17
