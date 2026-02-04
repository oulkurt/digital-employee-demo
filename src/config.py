"""Configuration management using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Chat LLM
    # Use OPENROUTER_API_KEY / OPENROUTER_BASE_URL / DEFAULT_MODEL in `.env`.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "anthropic/claude-3.5-sonnet"

    # Embedding & Reranker
    # Use SILICONFLOW_API_KEY / SILICONFLOW_BASE_URL in `.env`.
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Tavily (Search)
    # Use TAVILY_API_KEY in `.env`.
    tavily_api_key: str = ""

    # PostgreSQL
    database_url: str = "postgresql://user:password@localhost:5432/digital_employee"

    # WeCom App (optional)
    wecom_corp_id: str = ""
    wecom_agent_id: str = ""
    wecom_secret: str = ""
    wecom_token: str = ""
    wecom_encoding_aes_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
