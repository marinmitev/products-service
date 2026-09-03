from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str = "postgresql+asyncpg://products:products@localhost:5433/products_test"
    migrate_database_url: str = (
        "postgresql+asyncpg://products:products@localhost:5433/products_migrate"
    )
    sql_echo: bool = False
    max_page_size: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()
