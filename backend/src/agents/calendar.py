import logging
import datetime
import pathlib
from linebot.v3.messaging import TextMessage, FlexMessage, FlexContainer
from src.utils.flex_templates import (
    generate_create_success_flex,
    generate_overview_flex,
)
from src.skills.calendar_skill import CalendarSkills
from src.services.llm.factory import create_llm_provider

logger = logging.getLogger(__name__)

# LINE 單次回覆上限為 5 則訊息
MAX_LINE_MESSAGES = 5


class CalendarAgent:
    def __init__(self):
        self.skills = CalendarSkills()
        self.llm = create_llm_provider(role="agent")

        # ✅ 優化：在初始化時就讀入 Prompt，之後重複使用
        self.prompt_template = self._load_prompt()

    def _load_prompt(self):
        """
        讀取 Prompt 檔案內容。
        """
        current_dir = pathlib.Path(__file__).parent.parent
        prompt_path = current_dir / "prompts" / "calendar_agent.txt"

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                logger.info(
                    "✅ Calendar Prompt loaded successfully from %s", prompt_path
                )
                return f.read()
        except Exception as e:
            logger.error("❌ Error reading calendar prompt: %s", e)
            return ""

    def _normalize_args(self, args):
        """
        [資料清洗] 強制將 LLM 可能給錯的 key 轉回我們 Skill 支援的 key
        """
        new_args = args.copy()

        # 1. 處理標題 (title vs summary)
        if "summary" in new_args and "title" not in new_args:
            new_args["title"] = new_args.pop("summary")

        # 2. 處理時間 (camelCase vs snake_case 防呆)
        if "startTime" in new_args and "start_time" not in new_args:
            new_args["start_time"] = new_args.pop("startTime")
        if "endTime" in new_args and "end_time" not in new_args:
            new_args["end_time"] = new_args.pop("endTime")

        # 3. 處理 Reschedule 的欄位
        if "new_summary" in new_args and "new_title" not in new_args:
            new_args["new_title"] = new_args.pop("new_summary")

        return new_args

    async def handle_message(self, user_msg):
        # 1. 檢查 Prompt 是否載入成功
        if not self.prompt_template:
            return [TextMessage(text="❌ 系統錯誤：Prompt 載入失敗，請檢查 Log")]

        # 2. 替換變數
        dt_now = datetime.datetime.now().isoformat()
        prompt = self.prompt_template.replace("{{USER_INPUT}}", user_msg).replace(
            "{{CURRENT_TIME}}", dt_now
        )

        # 3. Call LLM (Parsing)
        actions_list = []
        try:
            parsed_data = await self.llm.aparse_json_response(prompt)

            # 防呆：如果 AI 還是只回傳單一 Dict (偶爾會發生)，把它包成 List
            if isinstance(parsed_data, dict):
                actions_list = [parsed_data]
            elif isinstance(parsed_data, list):
                actions_list = parsed_data
            else:
                raise ValueError("AI returned neither Dict nor List")

            logger.info("🤖 LLM Parsed Actions List: %s", actions_list)

        except Exception as e:
            logger.error("LLM parsing failed: %s", e)
            return [TextMessage(text="😵‍💫 抱歉，我不確定您的指令，請再試一次。")]

        # 4. Dispatch Skills (Loop Processing)
        reply_messages = []

        # 遍歷每一個 Action
        for action_data in actions_list:
            skill = action_data.get("skill")
            raw_args = action_data.get("args", {})

            # 參數清洗
            args = self._normalize_args(raw_args)

            logger.info("⚡ Executing Skill: %s | Args: %s", skill, args)

            try:
                if skill == "create_event":
                    result = self.skills.create_event(**args)
                    if result["success"]:
                        ui_data = {
                            "title": args.get("title"),
                            "startTime": args.get("start_time"),
                            "endTime": args.get("end_time"),
                            "location": args.get("location", ""),
                        }
                        flex_json = generate_create_success_flex(ui_data)
                        reply_messages.append(
                            FlexMessage(
                                alt_text=f"行程已建立: {args.get('title')}",
                                contents=FlexContainer.from_dict(flex_json),
                            )
                        )
                    else:
                        reply_messages.append(
                            TextMessage(
                                text=f"❌ 建立失敗 ({args.get('title')}): {result.get('message')}"
                            )
                        )

                elif skill == "batch_create":
                    # Batch 處理 (如果 Prompt 回傳這種類型)
                    # 註：新的 Prompt 通常會直接展開成多個 create_event，但保留此邏輯以防萬一
                    raw_events = args.get("events", [])
                    if not isinstance(raw_events, list):
                        raw_events = [args]

                    success_count = 0
                    for evt in raw_events:
                        clean_evt = self._normalize_args(evt)
                        if self.skills.create_event(**clean_evt)["success"]:
                            success_count += 1

                    reply_messages.append(
                        TextMessage(
                            text=f"✅ 批量建立完成！共建立 {success_count} 筆行程"
                        )
                    )

                elif skill == "list_events":
                    result = self.skills.list_events(**args)
                    if result["success"]:
                        flex_json = generate_overview_flex(result["events"])
                        reply_messages.append(
                            FlexMessage(
                                alt_text="行程總覽",
                                contents=FlexContainer.from_dict(flex_json),
                            )
                        )
                    else:
                        reply_messages.append(
                            TextMessage(text=f"❌ 查詢失敗: {result.get('message')}")
                        )

                elif skill == "delete_event":
                    result = self.skills.delete_event_by_query(**args)
                    if result["success"]:
                        deleted_title = result["deleted_event"].get("summary", "行程")
                        reply_messages.append(
                            TextMessage(text=f"🗑️ 已刪除：{deleted_title}")
                        )
                    else:
                        reply_messages.append(
                            TextMessage(text=f"⚠️ 刪除失敗：{result['message']}")
                        )

                elif skill == "reschedule_event":
                    result = self.skills.reschedule_event(**args)

                    status_msg = ""
                    if result["delete_status"]["success"]:
                        status_msg += "🗑️ 舊行程已刪除\n"
                    else:
                        status_msg += "⚠️ 找不到舊行程 (直接建立新行程)\n"

                    if result["create_status"]["success"]:
                        ui_data = {
                            "title": args.get("new_title"),
                            "startTime": args.get("new_start_time"),
                            "endTime": args.get("new_end_time"),
                        }
                        flex_json = generate_create_success_flex(ui_data)
                        reply_messages.append(
                            FlexMessage(
                                alt_text="行程已改期",
                                contents=FlexContainer.from_dict(flex_json),
                            )
                        )
                    else:
                        status_msg += "❌ 新行程建立失敗"
                        reply_messages.append(TextMessage(text=status_msg))

                else:
                    reply_messages.append(TextMessage(text=f"🤔 未知指令: {skill}"))

            except TypeError as te:
                logger.error("Parameter Mismatch in %s: %s", skill, te)
                reply_messages.append(TextMessage(text=f"❌ {skill} 參數錯誤"))
            except Exception as e:
                logger.error("Skill execution failed (%s): %s", skill, e)
                reply_messages.append(TextMessage(text=f"❌ 執行 {skill} 時發生錯誤"))

        # 限制回傳訊息數量 (LINE 上限為 MAX_LINE_MESSAGES 則)
        if len(reply_messages) > MAX_LINE_MESSAGES:
            reply_messages = reply_messages[: MAX_LINE_MESSAGES - 1]
            reply_messages.append(
                TextMessage(
                    text=f"⚠️ 指令過多，僅顯示前 {MAX_LINE_MESSAGES - 1} 筆結果。"
                )
            )

        # 如果沒有任何結果 (例如解析出來是空陣列)
        if not reply_messages:
            return [TextMessage(text="❓ 系統無法識別任何有效操作")]

        return reply_messages
