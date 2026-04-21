import logging

from src.services.llm.base import LLMProvider
from src.config import (
    LLM_PROVIDER,
    GEMINI_ROUTER_MODEL_NAME,
    GEMINI_AGENT_MODEL_NAME,
    GEMINI_GENERATION_CONFIG,
    CLAUDE_ROUTER_MODEL_NAME,
    CLAUDE_AGENT_MODEL_NAME,
    CLAUDE_MAX_TOKENS,
)

logger = logging.getLogger(__name__)


def create_llm_provider(role: str = "agent") -> LLMProvider:
    """
    LLM Provider 工廠函式。
    根據環境變數 LLM_PROVIDER 決定使用哪個 Provider，
    並根據 role 決定使用哪個模型（router 求快，agent 求準）。

    Args:
        role: "router" 或 "agent"。
              router 通常使用速度較快、成本較低的模型。
              agent 使用能力較強的模型進行語意解析。

    Returns:
        LLMProvider 實例

    Raises:
        ValueError: 若 LLM_PROVIDER 設定為不支援的值
    """
    provider = LLM_PROVIDER.lower()
    logger.info("🏭 Creating LLM Provider: provider=%s, role=%s", provider, role)

    if provider == "gemini":
        from src.services.llm.gemini import GeminiProvider

        model_name = (
            GEMINI_ROUTER_MODEL_NAME if role == "router" else GEMINI_AGENT_MODEL_NAME
        )
        return GeminiProvider(
            model_name=model_name,
            generation_config=GEMINI_GENERATION_CONFIG,
        )

    elif provider == "claude":
        from src.services.llm.claude import ClaudeProvider

        model_name = (
            CLAUDE_ROUTER_MODEL_NAME if role == "router" else CLAUDE_AGENT_MODEL_NAME
        )
        return ClaudeProvider(model_name=model_name, max_tokens=CLAUDE_MAX_TOKENS)

    else:
        raise ValueError(
            f"❌ Unknown LLM_PROVIDER: '{provider}'. "
            f"Supported values: 'gemini', 'claude'."
        )
