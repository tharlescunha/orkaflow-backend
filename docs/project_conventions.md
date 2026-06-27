# Convenções do Projeto - OrkaFlow Backend

## Objetivo
Este documento define as convenções de organização, nomenclatura e arquitetura
do backend do OrkaFlow.

---

## 1. Convenções de pastas

### `app/api/`
Responsável pelas rotas da aplicação.

- Define endpoints HTTP
- Recebe requisições
- Retorna respostas
- Não deve conter regra de negócio

### `app/api/v1/`
Versão 1 da API.

Exemplo:
- health
- auth
- runners
- automations

### `app/core/`
Núcleo técnico da aplicação.

Responsabilidades:
- configuração
- conexão com banco
- logging
- exceções
- constantes
- segurança
- utilidades centrais

### `app/models/`
Modelos ORM do SQLAlchemy.

Regras:
- cada model representa uma tabela
- nome da classe no singular
- nome da tabela no plural

Exemplo:
- classe: `User`
- tabela: `users`

### `app/schemas/`
Schemas de entrada e saída da API.

Responsabilidades:
- validação com Pydantic
- contratos de request/response
- serialização dos dados

### `app/repositories/`
Camada de acesso ao banco.

Responsabilidades:
- queries
- filtros
- persistência
- leitura/escrita no banco

Não deve:
- aplicar regra de negócio
- retornar HTTP response

### `app/services/`
Camada de regra de negócio.

Responsabilidades:
- orquestrar fluxo
- aplicar validações de negócio
- chamar repository
- levantar exceções de negócio

Não deve:
- montar resposta HTTP diretamente
- acessar banco de forma solta sem repository

### `app/workers/`
Responsável por execuções assíncronas, integrações e tarefas de runner/worker.

---

## 2. Convenções de nomenclatura

### Arquivos
Usar `snake_case`.

Exemplos:
- `health_check.py`
- `user_service.py`
- `automation_repository.py`

### Classes
Usar `PascalCase`.

Exemplos:
- `UserService`
- `AutomationRepository`
- `BusinessRuleException`

### Funções e variáveis
Usar `snake_case`.

Exemplos:
- `get_user_by_id`
- `create_automation`
- `db_session`

### Constantes
Usar `UPPER_SNAKE_CASE`.

Exemplos:
- `DEFAULT_PAGE_SIZE`
- `MAX_RETRY_ATTEMPTS`

---

## 3. Convenções de arquitetura

## Regras principais

### A rota não faz regra de negócio
A rota deve:
- receber a requisição
- validar entrada
- chamar service
- devolver resposta

A rota não deve:
- conter regra operacional complexa
- acessar banco diretamente
- misturar lógica de negócio

### Service não monta resposta HTTP
A camada de service deve trabalhar com dados e regras de negócio.

Ela não deve:
- retornar `JSONResponse`
- usar status code HTTP diretamente
- decidir detalhes de transporte HTTP

### Repository não decide regra operacional
Repository é para acesso a dados.

Ele não deve:
- decidir fluxo de negócio
- aplicar regra de autorização
- retornar mensagens de API

### Configuração centralizada
Toda configuração deve sair de `app/core/config.py`.

Não espalhar:
- host
- porta
- nome de banco
- schema
- flags de ambiente

---

## 4. Convenções de growth do projeto

Quando o projeto crescer, seguir este padrão por domínio:

- `models/user.py`
- `schemas/user.py`
- `repositories/user_repository.py`
- `services/user_service.py`
- `api/v1/users.py`

Ou seja, separar por responsabilidade e manter o domínio consistente.

---

## 5. Padrão de imports

Preferir imports absolutos a partir de `app`.

Exemplo:
```python
from app.core.config import settings
from app.services.user_service import UserService


