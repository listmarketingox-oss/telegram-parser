from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_parser"
    SECRET_KEY: str = "change-me"
    ENCRYPTION_KEY: str = ""
    PARSE_INTERVAL_MINUTES: int = 30
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
