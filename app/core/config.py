from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET = "change-me-in-production"


class Settings(BaseSettings):
    app_name: str = "City Complaint Portal API"
    app_version: str = "1.0.0"
    environment: str = "development"

    database_url: str = "sqlite:///./ccp.db"

    secret_key: str = _DEFAULT_SECRET
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    first_admin_name: str = "System Administrator"
    first_admin_email: str = "admin@ccp-portal.example.com"
    first_admin_password: str = "Admin@12345"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _forbid_default_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.secret_key == _DEFAULT_SECRET:
            raise ValueError("SECRET_KEY must be set to a strong random value in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
