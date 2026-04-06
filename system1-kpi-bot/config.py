"""KPI Bot 설정 — 환경변수 기반 구성"""
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


# --- Slack ---
SLACK_BOT_TOKEN: Optional[str] = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL: str = os.getenv("SLACK_CHANNEL", "#kpi-daily")
SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")

# --- Google Sheets ---
GOOGLE_SHEETS_API_KEY: Optional[str] = os.getenv("GOOGLE_SHEETS_API_KEY")
GOOGLE_SHEETS_ID: Optional[str] = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_SHEETS_RANGE: str = os.getenv("GOOGLE_SHEETS_RANGE", "KPI!A1:Z100")

# --- 스케줄러 ---
KPI_CRON_HOUR: int = int(os.getenv("KPI_CRON_HOUR", "9"))
KPI_CRON_MINUTE: int = int(os.getenv("KPI_CRON_MINUTE", "0"))
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Seoul")

# --- 임계값 ---
THRESHOLDS = {
    "contract_value": {"min": 400, "label": "계약단가", "unit": "만원"},
    "roas": {"min": 3.5, "label": "ROAS", "unit": "x"},
    "utilization": {"min": 90, "label": "가동률", "unit": "%"},
    "cpa": {"max": 20000, "label": "CPA", "unit": "원"},
}
