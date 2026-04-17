import os
import asyncio
import logging
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

# 引入你的 Agent 與 Services
from src.agents.calendar import CalendarAgent
from src.agents.expense import ExpenseAgent
from src.agents.chat import ChatAgent
from src.agents.memory_parser import MemoryParser
from src.services.llm.factory import create_llm_provider
from src.services.llm.embedding import EmbeddingService
from src.services.firestore_service import AsyncFirestoreService

# ============================================================
# 1. Setup & Config
# ============================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MainRouter")

# ============================================================
# 2. Singletons（Module-level，冷啟動優化）
# ============================================================
router_llm = create_llm_provider(role="router")
calendar_agent = CalendarAgent()
expense_agent = ExpenseAgent()
chat_agent = ChatAgent()
memory_parser = MemoryParser()
embedding_service = EmbeddingService()
firestore_service = AsyncFirestoreService()

# Prompt 快取：讀一次之後不再重複 I/O
_router_prompt_template: str | None = None


def _get_router_prompt_template() -> str:
    global _router_prompt_template
    if _router_prompt_template is None:
        prompt_path = pathlib.Path(__file__).parent / "src" / "prompts" / "system_prompt.txt"
        _router_prompt_template = prompt_path.read_text(encoding="utf-8")
    return _router_prompt_template


# Background task 錯誤處理 callback
def _on_memory_task_done(task: asyncio.Task) -> None:
    exc = task.exception() if not task.cancelled() else None
    if exc:
        logger.error("❌ Memory workflow failed: %s", exc)


# ============================================================
# 3. FastAPI App
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 AI Butler FastAPI starting up...")
    yield
    logger.info("🛑 AI Butler FastAPI shutting down...")


app = FastAPI(
    title="AI Butler",
    description="Local dev endpoint for AI Butler — no LINE or ngrok required.",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# 4. Request / Response Models
# ============================================================
class ChatRequest(BaseModel):
    user_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    intent: str


# ============================================================
# 5. Router Intent Helper
# ============================================================
async def get_router_intent(user_text: str) -> tuple[str, bool]:
    """
    [Router] 非同步意圖分類
    回傳: intent (str), needs_memory (bool)
    """
    template = _get_router_prompt_template()
    prompt = template.replace("{{USER_INPUT}}", user_text).replace(
        "{{CURRENT_TIME}}", ""
    )

    try:
        data = await router_llm.aparse_json_response(prompt)
        intent = data.get("intent", "CHAT")
        needs_memory = data.get("needs_memory", False)
        return intent, needs_memory
    except Exception as e:
        logger.error("❌ Router Decision Error: %s", e)
        return "CHAT", False


# ============================================================
# 6. Core Message Handling Logic
# ============================================================
async def handle_message(user_id: str, message: str) -> tuple[str, str]:
    """
    核心 dispatch 邏輯（從 main.py handle_message 移植，移除 LINE 依賴）
    回傳: (reply_text, intent)
    """
    user_msg = message.strip()
    logger.info("📨 Processing: %s", user_msg)

    # 並發處理 Intent 與 Embedding
    embedding_task = asyncio.create_task(embedding_service.get_embedding(user_msg))
    intent_task = asyncio.create_task(get_router_intent(user_msg))

    embedding, (intent, needs_memory) = await asyncio.gather(embedding_task, intent_task)

    logger.info("🚦 Router Intent: %s, Needs Memory: %s", intent, needs_memory)

    reply_messages = []

    try:
        # Action 分發
        if intent == "CALENDAR":
            reply_messages = await calendar_agent.handle_message(user_msg)

        elif intent == "EXPENSE":
            reply_messages = await expense_agent.handle_message(
                user_msg, user_id=user_id
            )

        else:
            # CHAT 或未知，先去 DB 撈回憶
            memories = await firestore_service.search_memories(
                query_embedding=embedding,
                user_id=user_id,
                limit=3,
            )
            reply_messages = await chat_agent.handle_message(user_msg, memories)

        # 若需要紀錄 Memory，背景執行不阻礙回應
        if needs_memory:
            async def memory_workflow():
                parsed_mem = await memory_parser.parse_memory(user_msg)
                await firestore_service.save_memory(
                    user_id=user_id,
                    content=user_msg,
                    summary=parsed_mem["summary"],
                    tags=parsed_mem["tags"],
                    memory_type=parsed_mem["memory_type"],
                    embedding=embedding,
                )

            task = asyncio.create_task(memory_workflow())
            task.add_done_callback(_on_memory_task_done)

    except Exception as e:
        logger.error("❌ Dispatch Error: %s", e)
        return "很抱歉，處理您的訊息時發生了錯誤。", intent

    # 將 reply_messages（TextMessage list）轉成純文字回傳
    if reply_messages:
        # 相容 linebot TextMessage object 或純字串
        parts = []
        for m in reply_messages:
            if hasattr(m, "text"):
                parts.append(m.text)
            elif hasattr(m, "alt_text"):  # FlexMessage
                parts.append(m.alt_text)
            else:
                parts.append(str(m))
        return "\n".join(parts), intent

    return "", intent


# ============================================================
# 7. Endpoints
# ============================================================
@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    reply, intent = await handle_message(user_id=req.user_id, message=req.message)
    return ChatResponse(reply=reply, intent=intent)


# ============================================================
# 8. Entrypoint
# ============================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
