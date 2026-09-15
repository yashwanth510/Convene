from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from pydantic import field_validator


class Config(BaseSettings):
    OPENROUTER_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    MISTRAL_API_KEY: str = ""
    TAVILY_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    MOONSHOT_API_KEY: str = ""
    CEREBRAS_API_KEY: str = ""
    SAMBANOVA_API_KEY: str = ""

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8001
    DEBUG: bool = False
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite+aiosqlite:///data/convene.db"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    INVITE_CODE: str = ""
    DAILY_RUN_LIMIT: int = 15
    MAX_ACTIVE_RUNS: int = 3
    RUN_TOKEN_BUDGET: int = 48000
    RUN_CALL_BUDGET: int = 18
    SEARCH_BUDGET: int = 2
    SESSION_DAYS: int = 7

    @field_validator("DEBUG", mode="before")
    @classmethod
    def debug_mode(cls, value):
        return False if value == "release" else value

    COUNCIL_MODE: str = "reliable"
    CHAIRMAN_MODEL: str = "groq_llama"
    COMPLEX_CHAIRMAN_MODEL: str = "mistral_large"
    TITLE_MODEL: str = "groq_llama"
    SEARCH_PLANNER_MODEL: str = "groq_llama"
    REQUEST_TIMEOUT: int = 120
    COMPLEX_REQUEST_TIMEOUT: int = 300
    MAX_CONCURRENT_REQUESTS: int = 3
    STAGE2_MAX_REVIEWERS: int = 8
    DEBATE_PANEL_SIZE: int = 4
    COMPLEX_PROMPT_CHAR_THRESHOLD: int = 4000

    STORAGE_TYPE: str = "json"
    STORAGE_PATH: str = "data/conversations/"
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_SECONDS: List[int] = [8, 20, 45]
    WEB_SEARCH_ENABLED: bool = True

    # IDs are stable application aliases for saved settings/conversations.
    # api_model is the single source of truth for the provider's current slug.
    MODELS: List[dict] = [
        {
            "id": "groq_llama",
            "provider": "groq",
            "name": "GPT-OSS 120B (Groq)",
            "api_model": "openai/gpt-oss-120b",
            "context_window": 131072,
            "status": "active",
        },
        {
            "id": "openrouter_gpt_oss_120b",
            "provider": "openrouter",
            "name": "OpenRouter Free Router",
            "api_model": "openrouter/free",
            "context_window": 200000,
            "status": "active",
        },
        {
            "id": "openrouter_gpt_oss_20b",
            "provider": "openrouter",
            "name": "Nemotron 3 Super 120B (free)",
            "api_model": "nvidia/nemotron-3-super-120b-a12b:free",
            "context_window": 262144,
            "status": "active",
        },
        {
            "id": "openrouter_owl_alpha",
            "provider": "openrouter",
            "name": "Nemotron 3.5 Lightning (free)",
            "api_model": "nvidia/nemotron-3.5-lightning:free",
            "context_window": 1000000,
            "status": "active",
        },
        {
            "id": "mistral_large",
            "provider": "mistral",
            "name": "Mistral Medium",
            "api_model": "mistral-medium-latest",
            "context_window": 262144,
            "status": "active",
        },
        {
            "id": "cerebras_gpt_oss_120b",
            "provider": "cerebras",
            "name": "GPT-OSS 120B (Cerebras; billing required)",
            "api_model": "gpt-oss-120b",
            "status": "inactive",
        },
        {
            "id": "sambanova_deepseek_v32",
            "provider": "sambanova",
            "name": "DeepSeek V3.2 (SambaNova; billing required)",
            "api_model": "DeepSeek-V3.2",
            "status": "inactive",
        },
    ]

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


config = Config()
