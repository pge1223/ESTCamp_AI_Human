from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List

_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    # 앱
    APP_NAME: str = "NodeVelture API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # 데이터베이스
    DATABASE_URL: str = "postgresql+asyncpg://nodevelture:nodevelture@localhost:5432/nodevelture"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL: int = 3600

    # AI 엔진 — .env의 LLM_PROVIDER 로 전환 (gemini | groq | openai)
    LLM_PROVIDER: str = "openai"
    AI_API_KEY: str = ""
    AI_API_BASE_URL: str = ""
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash-lite"
    GEMINI_FALLBACK_MODEL: str = "gemini-2.0-flash"

    USE_VERTEX: bool = False
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: str = "llama-3.1-8b-instant"

    OPENAI_API_KEY: str = ""
    OPENAI_API_KEYS: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_FALLBACK_MODEL: str = ""

    LLM_PROVIDER_CHAIN: str = ""
    GEMINI_API_KEYS: str = ""
    GROQ_API_KEYS: str = ""
    LLM_KEY_COOLDOWN_SEC: int = 600
    LLM_MAX_TRANSIENT_RETRY: int = 2

    # 삽화 생성 (fal.ai — FLUX)
    FAL_KEY: str = ""

    # ELEVENLABS
    ELEVENLABS_API_KEY_1: str = ""
    ELEVENLABS_API_KEY_2: str = ""

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # 보안
    SECRET_KEY: str = "change-me-in-production"

    class Config:
        env_file = str(_ENV_FILE)


settings = Settings()
