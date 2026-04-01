import os
import sys
import logging
import datetime
import pytz

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    PushMessageRequest,
    FlexMessage,
    FlexContainer,
    TextMessage,
)
from src.skills.calendar_skill import CalendarSkills
from src.utils.flex_templates import generate_overview_flex

# 加入專案根目錄以讀取 src 模組
sys.path.append(os.getcwd())


# 設定 Logging 為 INFO，並強制輸出到 stdout (確保 GitHub Actions 也能看到)
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("WeeklyReport")


def main():
    logger.info("🚀 Starting Weekly Report Script (7-Days Scope)...")

    # 1. 讀取環境變數 & 檢查
    access_token = os.getenv("CHANNEL_ACCESS_TOKEN")
    target_id = os.getenv("TARGET_GROUP_ID", "").strip()

    if not access_token or not target_id:
        logger.error("❌ Critical: Missing CHANNEL_ACCESS_TOKEN or TARGET_GROUP_ID")
        return

    # 遮罩顯示 ID (確認讀取正確)
    masked_id = target_id[:4] + "****" + target_id[-4:] if len(target_id) > 8 else "***"
    logger.info("🎯 Target ID: %s", masked_id)

    # 2. 計算時間範圍 (未來 7 天，含今天)
    tw_tz = pytz.timezone("Asia/Taipei")
    now = datetime.datetime.now(tw_tz)

    # 起始時間：現在
    time_min = now.isoformat()

    # 結束時間：今天 + 6 天 (共 7 天) 的 23:59:59
    end_date = now + datetime.timedelta(days=6)
    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=0)
    time_max = end_date.isoformat()

    logger.info(
        "📅 Query Range: %s ~ %s",
        now.strftime("%Y-%m-%d %H:%M"),
        end_date.strftime("%Y-%m-%d %H:%M"),
    )

    # 3. 呼叫 Calendar Skill 查詢行程
    try:
        skills = CalendarSkills()
        result = skills.list_events(time_min=time_min, time_max=time_max)

        if not result["success"]:
            logger.error("❌ Calendar Query Failed: %s", result["message"])
            return

        events = result["events"]
        logger.info("✅ Found %d events.", len(events))

    except Exception as e:
        logger.error("❌ Error during calendar skill execution: %s", e)
        return

    # 4. 準備 LINE 訊息 (Flex Message)
    messages_to_send = []

    if not events:
        # 如果沒行程，傳送簡單文字
        messages_to_send.append(
            TextMessage(
                text="📅 未來七天內沒有安排任何行程。", quickReply=None, quoteToken=None
            )
        )
    else:
        # 有行程，產生漂亮的 Flex Message
        try:
            flex_json = generate_overview_flex(events)

            # 客製化標題：將 "行程總覽" 改為 "未來七天行程"
            # (防呆：檢查結構是否存在)
            if "header" in flex_json and "contents" in flex_json["header"]:
                try:
                    flex_json["header"]["contents"][0]["contents"][0]["text"] = (
                        "未來七天行程"
                    )
                except (IndexError, KeyError):
                    pass

            messages_to_send.append(
                FlexMessage(
                    altText=f"未來七天有 {len(events)} 個行程",
                    contents=FlexContainer.from_dict(flex_json),
                    quickReply=None,
                )
            )
        except Exception as e:
            logger.error("❌ Error generating Flex JSON: %s", e)
            return

    # 5. 發送 Push Message
    configuration = Configuration(access_token=access_token)
    try:
        logger.info("📡 Sending Push Message...")
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(
                    to=target_id,
                    messages=messages_to_send,
                    notificationDisabled=False,
                    customAggregationUnits=None,
                )
            )
        logger.info("✅ Report sent successfully!")

    except Exception as e:
        logger.error("❌ FAILURE! Could not send message.")
        logger.error("💥 Error Details: %s", e)
        body = getattr(e, "body", None)
        if body:
            logger.error("🔍 API Body: %s", body)


if __name__ == "__main__":
    main()
