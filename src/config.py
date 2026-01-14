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
    # openrouter_api_key: str = "a948c007713c44eabbb2fcaec42e60be.V0rm1tJVTebSI9ws"
    openrouter_api_key: str = "ms-337f22b1-ecd1-48ec-94ea-04ccde03d486"
    # openrouter_base_url: str = "https://api.z.ai/api/coding/paas/v4"
    openrouter_base_url: str = "https://api-inference.modelscope.cn/v1"
    default_model: str = "ZhipuAI/GLM-4.7"

    # Embedding & Reranker
    siliconflow_api_key: str = "sk-dzawcmfodnzatlywnqxihrqhtzmakicwvrmfbdaqslnrjugj"
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # Tavily (Search)
    tavily_api_key: str = "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"

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
