# app/core/config.py
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    app_name: str = Field("OrkaFlow API", alias="APP_NAME")
    app_env: str = Field("development", alias="APP_ENV")
    app_debug: bool = Field(True, alias="APP_DEBUG")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8000, alias="APP_PORT")

    api_prefix: str = Field("/api/v1", alias="API_PREFIX")

    db_host: str = Field(alias="DB_HOST")
    db_port: int = Field(1433, alias="DB_PORT")
    db_name: str = Field(alias="DB_NAME")
    db_user: str = Field(alias="DB_USER")
    db_password: str = Field(alias="DB_PASSWORD")
    db_driver: str = Field("ODBC Driver 18 for SQL Server", alias="DB_DRIVER")
    db_schema: str = Field("dbo", alias="DB_SCHEMA")
    db_trusted_connection: str = Field("no", alias="DB_TRUSTED_CONNECTION")
    db_timeout: int = Field(30, alias="DB_TIMEOUT")

    @property
    def database_url(self) -> str:
        driver = self.DB_DRIVER.replace(" ", "+")
        return (
            f"mssql+pyodbc://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?driver={driver}"
            f"&TrustServerCertificate=yes"
            f"&Encrypt=yes"
            f"&Connection Timeout={self.DB_TIMEOUT}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
