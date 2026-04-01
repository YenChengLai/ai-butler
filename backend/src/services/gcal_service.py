import os
import logging
import datetime
import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GCalService:
    def __init__(self):
        self.calendar_id = os.getenv("CALENDAR_ID")
        self.creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        self.service = build("calendar", "v3", credentials=self.creds)

    def create_event(self, event_data):
        """建立單一行程"""
        try:
            event = {
                "summary": event_data.get("title"),
                "location": event_data.get("location", ""),
                "description": event_data.get("description", ""),
                "start": {
                    "dateTime": event_data["startTime"],
                    "timeZone": "Asia/Taipei",
                },
                "end": {
                    "dateTime": event_data["endTime"],
                    "timeZone": "Asia/Taipei",
                },
            }
            created_event = (
                self.service.events()
                .insert(calendarId=self.calendar_id, body=event)
                .execute()
            )
            return {
                "success": True,
                "id": created_event.get("id"),
                "link": created_event.get("htmlLink"),
            }
        except HttpError as error:
            logger.error("An error occurred: %s", error)
            return {"success": False, "message": str(error)}

    def list_events(self, time_min, time_max=None):
        """查詢行程 (用於查詢與刪除前的搜尋)"""
        try:
            # 時區處理防呆
            if (
                time_min
                and "T" in time_min
                and "+" not in time_min
                and "Z" not in time_min
            ):
                time_min += "+08:00"
            if (
                time_max
                and "T" in time_max
                and "+" not in time_max
                and "Z" not in time_max
            ):
                time_max += "+08:00"

            if not time_max:
                # 預設查 30 天 (為了涵蓋一般改期需求)
                dt_min = datetime.datetime.fromisoformat(time_min)
                dt_max = dt_min + datetime.timedelta(days=30)
                time_max = dt_max.isoformat()

            events_result = (
                self.service.events()
                .list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])
            return {"success": True, "events": events}
        except Exception as e:
            logger.error("GCal List Error: %s", e)
            return {"success": False, "message": str(e)}

    def delete_event(self, event_id):
        """刪除行程 (為未來 Delete 功能做準備)"""
        try:
            self.service.events().delete(
                calendarId=self.calendar_id, eventId=event_id
            ).execute()
            return {"success": True}
        except HttpError as error:
            logger.error("GCal Delete Error: %s", error)
            return {"success": False, "message": str(error)}
