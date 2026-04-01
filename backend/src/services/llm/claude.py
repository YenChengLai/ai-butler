import os
import logging
import anthropic

from src.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)

# Claude 的預設 max_tokens (必填，不像 Gemini 有預設值)
DEFAULT_MAX_TOKENS = 8192


class ClaudeProvider(LLMProvider):
    """
    Anthropic Claude LLM Provider。
    包裝 anthropic SDK，實作 LLMProvider 介面。

    使用前需設定環境變數：
        ANTHROPIC_API_KEY=your_api_key
    """

    def __init__(self, model_name: str, max_tokens: int = DEFAULT_MAX_TOKENS):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("❌ ANTHROPIC_API_KEY is not set in environment variables.")

        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model_name = model_name
        self.max_tokens = max_tokens
        logger.info("✅ ClaudeProvider initialized with model: %s", model_name)

    async def agenerate(self, prompt: str) -> str:
        """
        呼叫 Claude Messages API，非同步回傳純文字回應。
        將完整的 prompt 作為單一 user message 傳入。
        """
        message = await self.client.messages.create(
            model=self.model_name,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        return message.content[0].text
