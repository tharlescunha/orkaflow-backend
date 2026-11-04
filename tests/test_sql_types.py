"""Nov/2026: parâmetros de Enum vão ao SQL Server como VARCHAR (igual à coluna), para o índice de status valer."""
import unittest
from types import SimpleNamespace

from sqlalchemy import Integer, String, bindparam
from sqlalchemy.types import Enum, TypeDecorator

from app.core.sql_types import enum_params_as_varchar
from app.domain.enums import TaskStatus

SQL_VARCHAR = 12
SQL_WVARCHAR = -9


def _context(has_driver=True):
    dbapi = SimpleNamespace(SQL_VARCHAR=SQL_VARCHAR) if has_driver else None
    return SimpleNamespace(dialect=SimpleNamespace(loaded_dbapi=dbapi))


class _EnumEnvolvido(TypeDecorator):
    impl = Enum
    cache_ok = True


class EnumComoVarcharTests(unittest.TestCase):
    def test_enum_vira_varchar_e_o_resto_fica_como_estava(self):
        status = bindparam("status", type_=Enum(TaskStatus, name="task_status"))
        texto = bindparam("texto", type_=String(50))
        numero = bindparam("numero", type_=Integer())
        sem_tipo = bindparam("sem_tipo", type_=Enum(TaskStatus, name="task_status"))
        inputsizes = {status: SQL_WVARCHAR, texto: SQL_VARCHAR, numero: 4, sem_tipo: None}

        enum_params_as_varchar(inputsizes, None, "", (), _context())

        self.assertEqual(inputsizes[status], SQL_VARCHAR)
        self.assertEqual(inputsizes[texto], SQL_VARCHAR)  # já era
        self.assertEqual(inputsizes[numero], 4)  # inteiro não muda
        self.assertIsNone(inputsizes[sem_tipo])  # parâmetro que o SQLAlchemy não tipa fica de fora

    def test_enum_dentro_de_type_decorator_tambem(self):
        envolvido = bindparam("status", type_=_EnumEnvolvido(TaskStatus, name="task_status"))
        inputsizes = {envolvido: SQL_WVARCHAR}
        enum_params_as_varchar(inputsizes, None, "", (), _context())
        self.assertEqual(inputsizes[envolvido], SQL_VARCHAR)

    def test_sem_driver_carregado_nao_mexe_em_nada(self):
        status = bindparam("status", type_=Enum(TaskStatus, name="task_status"))
        inputsizes = {status: SQL_WVARCHAR}
        enum_params_as_varchar(inputsizes, None, "", (), _context(has_driver=False))
        self.assertEqual(inputsizes[status], SQL_WVARCHAR)

    def test_valores_dos_enums_sao_ascii(self):
        """O envio como VARCHAR só é seguro porque nenhum valor de Enum do sistema tem acento."""
        from app.domain import enums

        for nome in dir(enums):
            classe = getattr(enums, nome)
            if isinstance(classe, type) and issubclass(classe, enums.Enum) and classe is not enums.Enum:
                for membro in classe:
                    self.assertTrue(str(membro.name).isascii(), f"{nome}.{membro.name}")
                    self.assertTrue(str(membro.value).isascii(), f"{nome}.{membro.name}={membro.value}")


if __name__ == "__main__":
    unittest.main()
