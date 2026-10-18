from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str
    secret_key: str = Field(min_length=32)
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(default=15, gt=0)
    refresh_token_expire_days: int = Field(default=7, gt=0)
    # Cookie do refresh token: ative (true) sempre que servir a aplicação via HTTPS.
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:5173"]
    rate_limit_enabled: bool = True
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def require_psycopg_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL deve usar o driver postgresql+psycopg://")
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.secret_key.startswith("change-me"):
            raise ValueError("SECRET_KEY de exemplo não pode ser usada em produção")
        if not self.cookie_secure:
            raise ValueError("COOKIE_SECURE deve ser true em produção")
        if "*" in self.cors_origins:
            raise ValueError("CORS_ORIGINS não pode conter '*' em produção")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
