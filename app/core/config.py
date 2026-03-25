# app/core/config.py
from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        populate_by_name=True,
    )

    # App
    app_name: str = Field("OrkaFlow API", alias="APP_NAME")
    app_env: str = Field("development", alias="APP_ENV")
    app_debug: bool = Field(True, alias="APP_DEBUG")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")

    api_prefix: str = Field("/api/v1", alias="API_PREFIX")

    # Database
    db_host: str = Field(alias="DB_HOST")
    db_port: int = Field(1433, alias="DB_PORT")
    db_name: str = Field(alias="DB_NAME")
    db_user: str = Field(alias="DB_USER")
    db_password: str = Field(alias="DB_PASSWORD")
    db_driver: str = Field("ODBC Driver 18 for SQL Server", alias="DB_DRIVER")
    db_schema: str = Field("orkaflow", alias="DB_SCHEMA")  # 🔥 ajuste aqui
    db_trusted_connection: str = Field("no", alias="DB_TRUSTED_CONNECTION")
    db_timeout: int = Field(30, alias="DB_TIMEOUT")

    
    # Auth
    jwt_secret_key: str = Field(alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(30, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(7, alias="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    @property
    def database_url(self) -> str:
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_password)
        driver = quote_plus(self.db_driver)

        return (
            f"mssql+pyodbc://{user}:{password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?driver={driver}"
            f"&TrustServerCertificate=yes"
            f"&Encrypt=yes"
            f"&Connection Timeout={self.db_timeout}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()