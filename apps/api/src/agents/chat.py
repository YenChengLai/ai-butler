import logging
import pathlib
from src.services.llm.factory import create_llm_provider
from linebot.v3.messaging import TextMessage

logger = logging.getLogger(__name__)

class ChatAgent:
    def __init__(self):
        self.llm = create_llm_provider(role="agent")
        
        # 讀取 prompt
        current_dir = pathlib.Path(__file__).parent.parent
        prompt_path = current_dir / "prompts" / "chat_agent.txt"
        
        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()
            logger.info("✅ Chat prompt loaded from %s", prompt_path)
        except Exception as e:
            logger.error("❌ Error reading chat prompt: %s", e)
            self.prompt_template = ""

    async def handle_message(self, user_text: str, memories: list[dict]) -> list[TextMessage]:
        if not self.prompt_template:
            return [TextMessage(text="❌ Chat Agent Prompt 遺失")]

        # 將 memory_payload 轉化為可讀文本
        if memories:
            memory_ctx = "以下是你擁有的相關背景記憶：\n"
            for idx, m in enumerate(memories):
                # m 包含: summary, tags, created_at, memory_type
                date_str = m.get("created_at", "")[:10]
                summary = m.get("summary", "")
                tags = ", ".join(m.get("tags", []))
                memory_ctx += f"[{idx+1}] ({date_str}) [{tags}] {summary}\n"
        else:
            memory_ctx = "目前沒有找到相關的背景記憶。"

        prompt = self.prompt_template.replace("{{USER_INPUT}}", user_text).replace(
            "{{MEMORY_CONTEXT}}", memory_ctx
        )

        try:
            # 一般對話不需要 JSON 格式，直接利用 agenerate 生成文字
            reply_text = await self.llm.agenerate(prompt)
            return [TextMessage(text=reply_text)]
        except Exception as e:
            logger.error("❌ Chat Agent failed: %s", e)
            return [TextMessage(text="😵‍💫 抱歉，聊天系統發生錯誤。")]
