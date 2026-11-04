"""Tipo dos parâmetros enviados ao SQL Server (nov/2026).

As colunas de status (e demais enums) são VARCHAR, mas o SQLAlchemy envia o valor de um ``Enum`` como NVARCHAR
(o dialeto pyodbc deixa o Enum de fora da regra que manda texto como VARCHAR). No SQL Server, comparar coluna
VARCHAR com parâmetro NVARCHAR obriga a converter a coluna linha a linha: o índice só serve para ``runner_id`` e o
filtro de ``status`` vira varredura. Medido em produção na consulta "esta máquina tem task em execução?":
412 leituras com NVARCHAR contra 9 com VARCHAR (e 284 contra 19 na contagem por agendamento).

O gancho abaixo manda os parâmetros de Enum como VARCHAR. Todos os valores dos enums do sistema são ASCII, então
nada muda no que é gravado ou lido; só o plano de execução melhora.
"""
from __future__ import annotations

from sqlalchemy.types import Enum


def _is_enum(sql_type) -> bool:
    if isinstance(sql_type, Enum):
        return True
    impl = getattr(sql_type, "impl", None)  # TypeDecorator em volta de um Enum
    return isinstance(impl, Enum)


def enum_params_as_varchar(inputsizes, cursor, statement, parameters, context) -> None:
    """Ouvinte de ``do_setinputsizes`` (mssql+pyodbc): parâmetros de Enum vão como VARCHAR."""
    dbapi = getattr(context.dialect, "loaded_dbapi", None)
    varchar = getattr(dbapi, "SQL_VARCHAR", None)
    if varchar is None:
        return

    for bindparam, dbapi_type in list(inputsizes.items()):
        if dbapi_type is None:  # parâmetro que o SQLAlchemy não tipa: não mexe
            continue
        if _is_enum(bindparam.type):
            inputsizes[bindparam] = varchar
