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


# 強制輸出 Log，方便 GitHub Actions 除錯
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger("DailyReport")


def main():
    logger.info("🚀 Starting Daily Report Script (Tomorrow's Schedule)...")

    access_token = os.getenv("CHANNEL_ACCESS_TOKEN")
    target_id = os.getenv("TARGET_GROUP_ID", "").strip()

    if not access_token or not target_id:
        logger.error("❌ Critical: Missing CHANNEL_ACCESS_TOKEN or TARGET_GROUP_ID")
        return

    # 1. 計算時間範圍 (明天整天)
    tw_tz = pytz.timezone("Asia/Taipei")
    now = datetime.datetime.now(tw_tz)

    # 明天
    tomorrow = now + datetime.timedelta(days=1)

    # 設定區間：明天 00:00:00 ~ 23:59:59
    start_time = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = tomorrow.replace(hour=23, minute=59, second=59, microsecond=0)

    time_min = start_time.isoformat()
    time_max = end_time.isoformat()

    date_str = start_time.strftime("%Y-%m-%d (%a)")
    logger.info("📅 Querying events for Tomorrow: %s", date_str)

    # 2. 呼叫 Skill
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

    # 3. 準備訊息
    messages_to_send = []

    if not events:
        # 如果明天沒事，也回報一下，讓人安心
        messages_to_send.append(
            TextMessage(text=f"📅 明天 {date_str} 目前沒有安排行程，好好休息！")
        )
    else:
        try:
            flex_json = generate_overview_flex(events)

            # 客製化標題
            if "header" in flex_json and "contents" in flex_json["header"]:
                try:
                    flex_json["header"]["contents"][0]["contents"][0]["text"] = (
                        f"明天行程 ({date_str})"
                    )
                except (IndexError, KeyError):
                    pass

            messages_to_send.append(
                FlexMessage(
                    alt_text=f"明天有 {len(events)} 個行程",
                    contents=FlexContainer.from_dict(flex_json),
                )
            )
        except Exception as e:
            logger.error("❌ Error generating Flex JSON: %s", e)
            return

    # 4. 發送
    configuration = Configuration(access_token=access_token)
    try:
        logger.info("📡 Sending Push Message...")
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.push_message(
                PushMessageRequest(to=target_id, messages=messages_to_send)
            )
        logger.info("✅ Daily report sent successfully!")

    except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("❌ FAILURE! Could not send message.")
        sys.exit(1)


if __name__ == "__main__":
    main()
