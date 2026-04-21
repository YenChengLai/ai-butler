import os
import json
import logging
import asyncio
import functions_framework
import pathlib
from dotenv import load_dotenv

from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    AsyncApiClient,
    AsyncMessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.webhook import WebhookParser

# 引入你的 Agent 與 Services
from src.agents.calendar import CalendarAgent
from src.agents.expense import ExpenseAgent
from src.agents.chat import ChatAgent
from src.agents.memory_parser import MemoryParser
from src.services.llm.factory import create_llm_provider
from src.services.llm.embedding import EmbeddingService
from src.services.firestore_service import AsyncFirestoreService

# 1. Setup & Config
load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("MainRouter")

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    logger.critical("❌ Critical Error: Missing LINE environment variables (CHANNEL_ACCESS_TOKEN / CHANNEL_SECRET)!")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)

# ✅ 冷啟動優化：Module-level 初始化，避免每次 Request 重新分配資源
# aiohttp connector 需要在 event loop 內初始化，Cloud Run Gen2 原生支援 async，
# functions_framework 會在有 event loop 的環境中 import，所以這裡是安全的。
parser = WebhookParser(CHANNEL_SECRET)
_async_api_client = AsyncApiClient(configuration)
line_bot_api = AsyncMessagingApi(_async_api_client)

router_llm = create_llm_provider(role="router")
calendar_agent = CalendarAgent()
expense_agent = ExpenseAgent()
chat_agent = ChatAgent()
memory_parser = MemoryParser()

# Singleton 實例
embedding_service = EmbeddingService()
firestore_service = AsyncFirestoreService()

# ✅ Prompt 快取：讀一次之後不再重複 I/O
_router_prompt_template: str | None = None

def _get_router_prompt_template() -> str:
    global _router_prompt_template
    if _router_prompt_template is None:
        prompt_path = pathlib.Path(__file__).parent / "src" / "prompts" / "system_prompt.txt"
        _router_prompt_template = prompt_path.read_text(encoding="utf-8")
    return _router_prompt_template


# ✅ Background task 的錯誤處理 callback（module level，避免 exception 被靜默吞掉）
def _on_memory_task_done(task: asyncio.Task) -> None:
    exc = task.exception() if not task.cancelled() else None
    if exc:
        logger.error("❌ Memory workflow failed: %s", exc)


async def get_router_intent(user_text) -> tuple[str, bool]:
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


# ========================================================
# 2. Cloud Function Entry (Native Async Handler)
# ========================================================
@functions_framework.http
async def webhook(request):
    signature = request.headers.get("X-Line-Signature")
    try:
        body = request.get_data(as_text=True)
        return await process_webhook_async(body, signature)
    except InvalidSignatureError:
        return "Invalid signature", 400
    except Exception as e:
        logger.error("Webhook Error: %s", e)
        return "Error", 500


async def process_webhook_async(body, signature):
    events = parser.parse(body, signature)

    tasks = []
    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            tasks.append(handle_message(event))

    if tasks:
        await asyncio.gather(*tasks)
    return "OK", 200


# 3. Message Handler (Async)
async def handle_message(event):
    user_msg = event.message.text.strip()
    source_type = event.source.type
    user_id = event.source.user_id

    # 群組喚醒檢查 (在群組內必須加 "管家")
    is_group = source_type in ["group", "room"]
    trigger_word = "管家"

    if is_group:
        if not user_msg.startswith(trigger_word):
            return
        user_msg = user_msg[len(trigger_word):].strip()

    logger.info("📨 Processing: %s", user_msg)

    # ==========================
    # 並發處理 Intent 與 Embedding
    # ==========================
    embedding_task = asyncio.create_task(embedding_service.get_embedding(user_msg))
    intent_task = asyncio.create_task(get_router_intent(user_msg))

    # A & B 平行執行
    embedding, (intent, needs_memory) = await asyncio.gather(embedding_task, intent_task)

    logger.info("🚦 Router Intent: %s, Needs Memory: %s", intent, needs_memory)

    reply_messages = []

    try:
        # ==========================
        # Action 分發
        # ==========================
        if intent == "CALENDAR":
            reply_messages = await calendar_agent.handle_message(user_msg)

        elif intent == "EXPENSE":
            reply_messages = await expense_agent.handle_message(
                user_msg, user_id=user_id
            )

        else:
            # CHAT 或 未知，先去 DB 撈回憶
            memories = await firestore_service.search_memories(
                query_embedding=embedding,
                user_id=user_id,
                limit=3
            )
            # 整合並發送給 Chat Agent
            reply_messages = await chat_agent.handle_message(user_msg, memories)

        # 若是一般對話或功能，但需要紀錄 Memory
        if needs_memory:
            # 啟動背景 Task 提取記憶與存入 DB，不阻礙回應
            async def memory_workflow():
                parsed_mem = await memory_parser.parse_memory(user_msg)
                await firestore_service.save_memory(
                    user_id=user_id,
                    content=user_msg,
                    summary=parsed_mem['summary'],
                    tags=parsed_mem['tags'],
                    memory_type=parsed_mem['memory_type'],
                    embedding=embedding
                )

            task = asyncio.create_task(memory_workflow())
            task.add_done_callback(_on_memory_task_done)

        # ==========================
        # 回覆 LINE
        # ==========================
        if reply_messages:
            await line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token, messages=reply_messages
                )
            )

    except Exception as e:
        logger.error("❌ Dispatch Error: %s", e)
