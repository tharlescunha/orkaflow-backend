# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.base import Base

# Teto para timeout de conexão/login (s), independente do DB_TIMEOUT do .env
# (que pode estar em valores absurdos, ex.: 1040s, e travar workers/API quando o banco cai).
MAX_CONNECT_TIMEOUT_SECONDS = 30

DATABASE_URL = settings.database_url
_url = make_url(DATABASE_URL)
_backend = _url.get_backend_name()

CONNECT_TIMEOUT = max(1, min(int(settings.db_timeout), MAX_CONNECT_TIMEOUT_SECONDS))

_engine_kwargs: dict = {
    "pool_pre_ping": True,
    "future": True,
}
_connect_args: dict = {}

if _backend == "mssql":
    # Config.database_url embute "Connection Timeout=<DB_TIMEOUT>"; sobrescreve com o valor limitado.
    _query = dict(_url.query)
    for _key in list(_query):
        if _key.replace(" ", "").lower() in ("connectiontimeout", "logintimeout"):
            _query.pop(_key)
    _query["Connection Timeout"] = str(CONNECT_TIMEOUT)
    DATABASE_URL = _url.set(query=_query)
    if _url.drivername.endswith("pyodbc"):
        # pyodbc: "timeout" no connect() = login timeout (SQL_ATTR_LOGIN_TIMEOUT)
        _connect_args["timeout"] = CONNECT_TIMEOUT

if _backend != "sqlite":
    _engine_kwargs.update(
        pool_recycle=settings.db_pool_recycle_seconds,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=30,
    )
else:
    # SQLite (testes): sem parâmetros de pool nem connect timeout específicos de servidor.
    _engine_kwargs["connect_args"] = {"check_same_thread": False}

if _connect_args:
    _engine_kwargs["connect_args"] = _connect_args

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
