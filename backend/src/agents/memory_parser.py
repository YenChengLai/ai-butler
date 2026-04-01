import json
import logging
from src.services.llm.factory import create_llm_provider

logger = logging.getLogger(__name__)

class MemoryParser:
    """
    負責解析並抽取使用者訊息中的資訊，轉換為標準的儲存格式（摘要、標籤、類型）。
    """
    def __init__(self):
        # 記憶整理需要較強的理解力，因此這裡使用 agent 權重的 LLM
        self.llm = create_llm_provider(role="agent")
        
    def _get_prompt(self, user_text: str) -> str:
        return f"""
You are an expert knowledge extractor. Your task is to analyze the user's message and extract key information to be stored in a memory database.

RULES:
1. "summary" should be a concise 1-2 sentence description of the core information or fact.
2. "tags" should be an array of 2-5 relevant keyword tags (string).
3. "memory_type" MUST be exactly one of the following strings:
   - "technical_log": For bug fixes, code issues, server configurations, or technical observations.
   - "personal_fact": For user's personal details, family, preferences, health, or static facts.
   - "task_note": For to-dos, reminders, or actionable items.
   - "daily_log": For general observations, thoughts, or non-technical logs.

USER MESSAGE:
"{user_text}"

OUTPUT FORMAT:
Return ONLY valid JSON matching this structure exactly:
{{
    "summary": "...",
    "tags": ["...", "..."],
    "memory_type": "..."
}}
"""

    async def parse_memory(self, user_text: str) -> dict:
        """
        非同步呼叫 LLM 抽取記憶欄位。
        """
        prompt = self._get_prompt(user_text)
        try:
            result = await self.llm.aparse_json_response(prompt)
            # 確保欄位皆存在
            summary = result.get("summary", "User note")
            tags = result.get("tags", [])
            memory_type = result.get("memory_type", "daily_log")
            
            return {
                "summary": summary,
                "tags": tags,
                "memory_type": memory_type
            }
        except Exception as e:
            logger.error("❌ Memory Parser failed: %s", e)
            return {
                "summary": user_text[:100],  # Fallback
                "tags": ["uncategorized"],
                "memory_type": "daily_log"
            }
