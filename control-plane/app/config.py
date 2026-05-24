from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    secret_key: str

    resend_api_key: str = ""
    resend_from: str = "auth@self-heal.dev"
    dashboard_base_url: str = "http://localhost:3000"
    cors_origins: str = "http://localhost:3000"

    magic_link_ttl_minutes: int = 15
    session_ttl_days: int = 30

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
