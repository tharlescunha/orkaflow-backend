# OrkaFlow Backend

Backend do orquestrador de automações OrkaFlow.

## Objetivo

Este projeto tem como objetivo fornecer a base backend para o sistema OrkaFlow,
centralizando:

- gerenciamento de automações
- gerenciamento de runners
- gerenciamento de execuções
- credenciais
- agendamentos
- monitoramento futuro da operação

Neste momento, o foco está na fundação técnica do projeto.

---

## Stack principal

- Python 3.11
- FastAPI
- SQLAlchemy
- Pydantic
- Pydantic Settings
- PyODBC
- SQL Server / Azure SQL
- Uvicorn
- Alembic

---

## Estrutura inicial

```text
orkaflow-backend/
│
├── app/
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       └── health.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   │
│   └── main.py
│
├── docs/
│   └── project_conventions.md
│
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
└── requirements.txt