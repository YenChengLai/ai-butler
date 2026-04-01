import os
import logging
from google import genai
from google.genai import types

from src.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """
    Google Gemini LLM Provider。
    包裝 google.genai SDK，實作 LLMProvider 介面。
    """

    def __init__(self, model_name: str, generation_config: dict | None = None):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("❌ GEMINI_API_KEY is not set in environment variables.")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self.generation_config = generation_config
        logger.info("✅ GeminiProvider initialized with model: %s", model_name)

    async def agenerate(self, prompt: str) -> str:
        """非同步呼叫 Gemini API，回傳純文字回應。"""
        config = None
        if self.generation_config:
            config = types.GenerateContentConfig(**self.generation_config)
            
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )
        return response.text or ""
