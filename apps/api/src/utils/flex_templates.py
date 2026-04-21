import datetime
import pytz

TW_TZ = pytz.timezone("Asia/Taipei")


def _format_time(iso_str):
    """輔助函式：處理時間格式與時區"""
    # 處理 Gemini 可能沒給時區的情況
    if iso_str and not iso_str.endswith("Z") and "+" not in iso_str:
        iso_str += "+08:00"

    try:
        dt = datetime.datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.datetime.now(TW_TZ)

    # 轉回台灣時間
    dt_tw = dt.astimezone(TW_TZ)

    date_key = dt_tw.strftime("%Y-%m-%d")
    display_date = dt_tw.strftime("%m/%d (%a)")
    display_time = dt_tw.strftime("%H:%M")

    return date_key, display_date, display_time


def generate_create_success_flex(event_data):
    """建立成功卡片"""
    _, display_date, display_time = _format_time(event_data["startTime"])

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "✅ 行程已建立",
                    "weight": "bold",
                    "color": "#1DB446",
                    "size": "sm",
                },
                {
                    "type": "text",
                    "text": event_data["title"],
                    "weight": "bold",
                    "size": "xl",
                    "margin": "md",
                    "wrap": True,
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": display_date,
                            "size": "sm",
                            "color": "#666666",
                            "flex": 0,
                        },
                        {
                            "type": "text",
                            "text": display_time,
                            "size": "sm",
                            "color": "#111111",
                            "weight": "bold",
                            "align": "end",
                        },
                    ],
                },
            ],
            "paddingAll": "20px",
        },
    }


def generate_overview_flex(events):
    """查詢結果 (Timeline 風格)"""
    if not events:
        return {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [{"type": "text", "text": "📅 查無行程"}],
            },
        }

    # 1. Group by Date
    grouped_events = {}
    for event in events:
        start = event["start"].get("dateTime", event["start"].get("date"))
        date_key, display_date, display_time = _format_time(start)

        if date_key not in grouped_events:
            grouped_events[date_key] = {"label": display_date, "items": []}

        is_important = "重要" in event.get("summary", "") or "Important" in event.get(
            "summary", ""
        )

        grouped_events[date_key]["items"].append(
            {
                "time": "All Day" if "date" in event["start"] else display_time,
                "title": event.get("summary", "(No Title)"),
                "location": event.get("location"),
                "is_important": is_important,
            }
        )

    # 2. Build UI Components
    body_contents = []
    sorted_keys = sorted(grouped_events.keys())

    for idx, key in enumerate(sorted_keys):
        group = grouped_events[key]

        # Date Header
        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "margin": "none" if idx == 0 else "xl",
                "contents": [
                    {
                        "type": "text",
                        "text": group["label"],
                        "weight": "bold",
                        "size": "sm",
                        "color": "#2B3467",
                    },
                    {"type": "separator", "margin": "sm", "color": "#2B3467"},
                ],
            }
        )

        # Events in this date
        for item in group["items"]:
            title_color = "#E63946" if item["is_important"] else "#111111"
            time_color = "#E63946" if item["is_important"] else "#888888"

            row_contents = [
                {
                    "type": "text",
                    "text": item["time"],
                    "size": "sm",
                    "color": time_color,
                    "flex": 0,
                    "gravity": "top",
                    "weight": "bold",
                    "margin": "xs",
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "flex": 1,
                    "margin": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": item["title"],
                            "size": "sm",
                            "color": title_color,
                            "wrap": True,
                            "weight": "bold" if item["is_important"] else "regular",
                        }
                    ],
                },
            ]

            if item["location"]:
                row_contents[1]["contents"].append(
                    {
                        "type": "text",
                        "text": item["location"],
                        "size": "xs",
                        "color": "#aaaaaa",
                        "margin": "xs",
                        "wrap": True,
                    }
                )

            body_contents.append(
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "lg",
                    "contents": row_contents,
                }
            )

    # 3. Final Bubble
    date_range = f"{grouped_events[sorted_keys[0]]['label']} - {grouped_events[sorted_keys[-1]]['label']}"

    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#2B3467",
            "paddingAll": "20px",
            "paddingBottom": "15px",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "未來行程總覽",
                            "weight": "bold",
                            "color": "#ffffff",
                            "size": "lg",
                            "flex": 1,
                        }
                    ],
                },
                {
                    "type": "text",
                    "text": date_range,
                    "color": "#b7c0ce",
                    "size": "xs",
                    "margin": "sm",
                },
            ],
        },
        "body": {"type": "box", "layout": "vertical", "contents": body_contents},
        "footer": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#f8f9fa",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "打開 Google 日曆",
                        "uri": "https://calendar.google.com",
                    },
                    "style": "primary",
                    "color": "#2B3467",
                    "height": "sm",
                }
            ],
        },
    }
