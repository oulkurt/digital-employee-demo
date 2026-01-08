"""Chat model client using LangChain ChatOpenAI."""

from langchain_openai import ChatOpenAI

from src.config import get_settings


def get_chat_model(
    model: str | None = None,
    temperature: float = 0.7,
    streaming: bool = True,
) -> ChatOpenAI:
    """
    Create a ChatOpenAI instance configured for OpenRouter.

    Args:
        model: Model name (e.g., "anthropic/claude-3.5-sonnet"). Defaults to settings.
        temperature: Sampling temperature.
        streaming: Enable streaming responses.

    Returns:
        Configured ChatOpenAI instance.
    """
    settings = get_settings()

    return ChatOpenAI(
        model=model or settings.default_model,
        openai_api_key=settings.openrouter_api_key,
        openai_api_base=settings.openrouter_base_url,
        temperature=temperature,
        streaming=streaming,
    )
