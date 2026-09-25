"""Backend settings and the supported model catalog."""

from urllib.parse import urlsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    QWEN_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL: str = "qwen-plus"

    APP_ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite+aiosqlite:///data/convene.db"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    INVITE_CODE: str = ""
    ADMIN_USER_IDS: list[str] = []
    SESSION_DAYS: int = 7
    DAILY_RUN_LIMIT: int = 15
    MAX_ACTIVE_RUNS: int = 2
    MAX_CONCURRENT_REQUESTS: int = 3
    RUN_TOKEN_BUDGET: int = 48000
    RUN_CALL_BUDGET: int = 18
    SEARCH_BUDGET: int = 1
    REQUEST_TIMEOUT: int = 120
    COMPLEX_REQUEST_TIMEOUT: int = 300
    DEBATE_PANEL_SIZE: int = 4

    @field_validator("DEBUG", mode="before")
    @classmethod
    def debug_mode(cls, value):
        return False if value == "release" else value

    @field_validator("QWEN_BASE_URL")
    @classmethod
    def qwen_endpoint(cls, value):
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("QWEN_BASE_URL must be an HTTPS API base URL")
        return value.rstrip("/")

    @property
    def MODELS(self) -> list[dict]:
        return [
            {
                "id": "groq_gpt_oss",
                "provider": "groq",
                "name": "GPT-OSS 120B",
                "api_model": "openai/gpt-oss-120b",
                "status": "active",
            },
            {
                "id": "nemotron_lightning",
                "provider": "openrouter",
                "name": "Nemotron 3.5 Lightning",
                "api_model": "nvidia/nemotron-3.5-lightning:free",
                "status": "active",
            },
            {
                "id": "openrouter_free",
                "provider": "openrouter",
                "name": "OpenRouter Free Router",
                "api_model": "openrouter/free",
                "status": "active",
            },
            {
                "id": "qwen_plus",
                "provider": "qwen",
                "name": "Qwen Plus",
                "api_model": self.QWEN_MODEL,
                "status": "active",
            },
        ]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Config()
