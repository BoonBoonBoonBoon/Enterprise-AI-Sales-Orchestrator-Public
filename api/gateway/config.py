"""Gateway configuration."""

from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    DEV_LOGIN_ENABLED: bool = False
    DEV_LOGIN_SECRET: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_JWT_SECRET: str = ""

    # Redis (for internal delegation)
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    class Config:
        env_file = str(Path(__file__).resolve().parents[2] / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
