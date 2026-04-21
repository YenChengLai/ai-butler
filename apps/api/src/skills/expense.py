import os
import sys
import json
import base64
import logging
import datetime
import gspread
from google.oauth2.service_account import Credentials

# 修正 Python 搜尋路徑
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

logger = logging.getLogger(__name__)


class ExpenseSkills:
    def __init__(self):
        self.spreadsheet_id = os.getenv("SPREADSHEET_ID")
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        self.creds = None

        # 定義可能的金鑰路徑
        possible_paths = [
            "service_account.json",
            "/secrets/service_account.json",
        ]

        # 1. 嘗試從檔案讀取
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    self.creds = Credentials.from_service_account_file(
                        path, scopes=self.scopes
                    )
                    logger.info(f"✅ Loaded credentials from: {path}")
                    break
                except Exception as e:
                    logger.error(f"❌ Error loading {path}: {e}")

        # 2. (備用) Base64 環境變數
        if not self.creds:
            sa_base64 = os.getenv("GCP_SA_KEY_BASE64")
            if sa_base64:
                try:
                    creds_json = base64.b64decode(sa_base64).decode("utf-8")
                    creds_dict = json.loads(creds_json)
                    self.creds = Credentials.from_service_account_info(
                        creds_dict, scopes=self.scopes
                    )
                    logger.info("✅ Loaded credentials from BASE64 env var")
                except Exception as e:
                    logger.error(f"❌ Error loading BASE64 credentials: {e}")

        if not self.creds:
            logger.error(
                "❌ Critical: No credentials found in local, secrets, or env vars."
            )

    def _get_client(self):
        if not self.creds:
            return None
        return gspread.authorize(self.creds)

    def _get_worksheet(self, sheet_name):
        """內部 helper：取得指定名稱的 Worksheet"""
        client = self._get_client()
        if not client:
            return None

        sh = client.open_by_key(self.spreadsheet_id)
        try:
            return sh.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            return None

    def query_expenses(self, start_date: str, end_date: str):
        """
        查詢特定日期範圍的消費記錄。
        目前邏輯：根據 start_date 決定要讀取哪一個月份的 Sheet。
        (暫不支援跨月份 Sheet 查詢，例如 1/31 ~ 2/1)
        """
        # 1. 決定要讀哪個 Sheet (YYYY-MM)
        # 取 start_date 的前 7 碼 (YYYY-MM)
        target_month = start_date[:7]
        ws = self._get_worksheet(target_month)

        if not ws:
            logger.warning(f"⚠️ Sheet {target_month} not found.")
            return []

        try:
            # 2. 讀取所有資料 (假設第一列是 Header)
            # get_all_records 會回傳 List[Dict]，key 是 Header 名稱
            records = ws.get_all_records()

            # 3. 進行日期篩選
            filtered_data = []
            for row in records:
                row_date = row.get("Date")  # 需對應 Sheet 第一列標題
                # 簡單字串比較日期 YYYY-MM-DD
                if row_date and start_date <= row_date <= end_date:
                    filtered_data.append(row)

            return filtered_data

        except Exception as e:
            logger.error(f"❌ Query failed: {e}")
            return []

    def add_expense(
        self,
        date_str: str,
        category: str,
        item: str,
        amount: int,
        project: str = "",
        payer: str = "",
        note: str = "",
    ):
        """
        新增消費記錄
        """
        client = self._get_client()
        if not client:
            return {"success": False, "message": "Google Sheets Auth Failed"}

        try:
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            sheet_name = dt.strftime("%Y-%m")
            sh = client.open_by_key(self.spreadsheet_id)

            # 取得或建立分頁
            try:
                worksheet = sh.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                logger.info("✨ Creating new sheet: %s", sheet_name)
                try:
                    template_ws = sh.worksheet("Template")
                    worksheet = template_ws.duplicate(new_sheet_name=sheet_name)
                except gspread.WorksheetNotFound:
                    return {"success": False, "message": "Template sheet missing"}

            # 寫入資料
            row_data = [
                date_str,
                category,
                item,
                amount,
                project,
                payer,
                note,
                str(datetime.datetime.now()),
            ]
            worksheet.append_row(row_data)

            logger.info("✅ Expense: %s | %s $%s", date_str, item, amount)
            return {
                "success": True,
                "message": f"Recorded: {item} ${amount}",
                "sheet": sheet_name,
            }

        except Exception as e:
            logger.error("❌ Add Expense Failed: %s", e)
            return {"success": False, "message": str(e)}


if __name__ == "__main__":
    # 本地測試用
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    skill = ExpenseSkills()
    # 測試查詢 (請確保你的 Sheet 裡有 2025-01 的資料且有標題列)
    # print(skill.query_expenses("2025-01-01", "2025-01-31"))
