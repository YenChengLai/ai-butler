import os
import logging
from google import genai

logger = logging.getLogger(__name__)

class EmbeddingService:
    """
    固定鎖定向 Gemini (text-embedding-004) 索取 Embedding 向量的服務。
    無論主要的 LLMProvider 使用什麼模型（如 Claude），記憶搜尋的向量空間必須保持完全一致。
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(EmbeddingService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, model_name: str = "gemini-embedding-001"):
        if hasattr(self, "_initialized"):
            return
            
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("❌ GEMINI_API_KEY is not set. Embedding requires Gemini.")
            
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        self._initialized = True
        logger.info("✅ EmbeddingService initialized with fixed model: %s", model_name)

    async def get_embedding(self, text: str) -> list[float]:
        """
        非同步取得文字的 Embedding 向量。
        """
        try:
            result = await self.client.aio.models.embed_content(
                model=self.model_name,
                contents=text,
            )
            if not result.embeddings or not result.embeddings[0].values:
                raise ValueError("No embedding returned from Gemini")
            return result.embeddings[0].values
        except Exception as e:
            logger.error("Embedding generation error: %s", e)
            raise
