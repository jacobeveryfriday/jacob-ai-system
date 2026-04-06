"""일일 KPI 자동 집계봇 — 08Liter Global & Mili Mili"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from config import (
    SLACK_WEBHOOK_URL,
    GOOGLE_SHEETS_API_KEY,
    GOOGLE_SHEETS_ID,
    GOOGLE_SHEETS_RANGE,
    KPI_CRON_HOUR,
    KPI_CRON_MINUTE,
    TIMEZONE,
    THRESHOLDS,
)
from slack_notifier import SlackBotNotifier

load_dotenv()

app = FastAPI(title="KPI 집계봇")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
DATA_FILE = Path(__file__).parent / "data" / "kpi_history.json"
slack_notifier = SlackBotNotifier()

# --- Data helpers ---


def load_data() -> List[Dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []


def save_data(data: List[Dict]):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_sales_data(entry: dict) -> dict:
    """매출 데이터에서 new_revenue(신규매출)를 포함한 핵심 지표를 추출한다."""
    liter = entry.get("liter", {})
    mili = entry.get("mili", {})
    return {
        "date": entry.get("date"),
        "liter": {
            "revenue": liter.get("revenue", 0),
            "new_revenue": liter.get("new_revenue", 0),
            "contracts": liter.get("contracts", 0),
            "contract_value": liter.get("contract_value", 0),
            "organic_ratio": liter.get("organic_ratio", 0),
            "conversion": liter.get("conversion", 0),
            "lead_cpa": liter.get("lead_cpa", 0),
            "utilization": liter.get("utilization", 0),
        },
        "mili": {
            "revenue": mili.get("revenue", 0),
            "new_revenue": mili.get("new_revenue", 0),
            "repurchase": mili.get("repurchase", 0),
            "roas": mili.get("roas", 0),
            "cpa": mili.get("cpa", 0),
            "rating": mili.get("rating", 0),
            "kakao_growth": mili.get("kakao_growth", 0),
        },
    }


def _find_entry_by_date(data: List[Dict], target_date: str) -> Optional[dict]:
    """날짜 문자열로 해당 일자 엔트리를 찾는다."""
    for d in data:
        if d.get("date") == target_date:
            return d
    return None


def _get_previous_month_entry(data: List[Dict], current_date: str) -> Optional[dict]:
    """전월 동일자 데이터를 찾는다."""
    dt = datetime.strptime(current_date, "%Y-%m-%d")
    prev_month = dt.replace(day=1) - timedelta(days=1)
    try:
        target = prev_month.replace(day=dt.day)
    except ValueError:
        target = prev_month  # 말일 보정
    return _find_entry_by_date(data, target.strftime("%Y-%m-%d"))


def _get_yoy_entry(data: List[Dict], current_date: str) -> Optional[dict]:
    """전년 동월 동일자 데이터를 찾는다."""
    dt = datetime.strptime(current_date, "%Y-%m-%d")
    try:
        target = dt.replace(year=dt.year - 1)
    except ValueError:
        target = dt.replace(year=dt.year - 1, day=28)  # 윤년 보정
    return _find_entry_by_date(data, target.strftime("%Y-%m-%d"))


def detect_anomalies(entry: dict) -> List[Dict]:
    alerts = []
    liter = entry.get("liter", {})
    mili = entry.get("mili", {})
    if liter.get("contract_value", 999) < 400:
        alerts.append({"metric": "계약단가", "value": liter["contract_value"], "threshold": 400, "company": "08Liter"})
    if mili.get("roas", 999) < 3.5:
        alerts.append({"metric": "ROAS", "value": mili["roas"], "threshold": 3.5, "company": "Mili Mili"})
    if liter.get("utilization", 999) < 90:
        alerts.append({"metric": "가동률", "value": liter["utilization"], "threshold": 90, "company": "08Liter"})
    if mili.get("cpa", 0) > 20000:
        alerts.append({"metric": "CPA", "value": mili["cpa"], "threshold": 20000, "company": "Mili Mili"})
    return alerts


def _calc_change(current: float, previous: float) -> str:
    if previous == 0:
        return "N/A"
    pct = ((current - previous) / abs(previous)) * 100
    if pct > 0:
        return f"+{pct:.1f}%↑"
    elif pct < 0:
        return f"{pct:.1f}%↓"
    return "0%→"


def _build_comparison_row(label: str, unit: str, cur_val, prev_month_val, yoy_val) -> str:
    """비교표 한 행을 생성한다."""
    cur_str = f"{cur_val}{unit}" if cur_val is not None else "-"
    mom_str = _calc_change(cur_val, prev_month_val) if prev_month_val is not None and cur_val is not None else "-"
    yoy_str = _calc_change(cur_val, yoy_val) if yoy_val is not None and cur_val is not None else "-"
    return f"  {label}: {cur_str}  |  전월비: {mom_str}  |  전년비: {yoy_str}"


def build_comparison_report(
    current: dict,
    prev_month: Optional[dict],
    yoy: Optional[dict],
    alerts: list,
) -> str:
    """전월 대비 + 전년 동월 대비 비교표 형식 리포트를 생성한다."""
    date = current.get("date", "N/A")
    l = current.get("liter", {})
    m = current.get("mili", {})
    lm = (prev_month or {}).get("liter", {})
    mm = (prev_month or {}).get("mili", {})
    ly = (yoy or {}).get("liter", {})
    my = (yoy or {}).get("mili", {})

    alert_text = ""
    if alerts:
        alert_text = "\n\n:rotating_light: *이상 감지:*\n" + "\n".join(
            f"  - [{a['company']}] {a['metric']}: {a['value']} (기준: {a['threshold']})" for a in alerts
        )

    msg = f""":bar_chart: *Jacob Daily KPI Report — {date}*
_전월 대비 (MoM) / 전년 동월 대비 (YoY) 비교표_

*:orange_circle: 08Liter Global*
{_build_comparison_row("매출", "만원", l.get("revenue"), lm.get("revenue"), ly.get("revenue"))}
{_build_comparison_row("신규매출", "만원", l.get("new_revenue"), lm.get("new_revenue"), ly.get("new_revenue"))}
{_build_comparison_row("계약 건수", "건", l.get("contracts"), lm.get("contracts"), ly.get("contracts"))}
{_build_comparison_row("평균 계약단가", "만원", l.get("contract_value"), lm.get("contract_value"), ly.get("contract_value"))}
{_build_comparison_row("오가닉 리드", "%", l.get("organic_ratio"), lm.get("organic_ratio"), ly.get("organic_ratio"))}
{_build_comparison_row("미팅→계약 전환율", "%", l.get("conversion"), lm.get("conversion"), ly.get("conversion"))}
{_build_comparison_row("리드 CPA", "만원", l.get("lead_cpa"), lm.get("lead_cpa"), ly.get("lead_cpa"))}
{_build_comparison_row("가동률", "%", l.get("utilization"), lm.get("utilization"), ly.get("utilization"))}

*:blue_heart: Mili Mili*
{_build_comparison_row("매출", "만원", m.get("revenue"), mm.get("revenue"), my.get("revenue"))}
{_build_comparison_row("신규매출", "만원", m.get("new_revenue"), mm.get("new_revenue"), my.get("new_revenue"))}
{_build_comparison_row("재구매율", "%", m.get("repurchase"), mm.get("repurchase"), my.get("repurchase"))}
{_build_comparison_row("ROAS", "x", m.get("roas"), mm.get("roas"), my.get("roas"))}
{_build_comparison_row("CPA", "원", m.get("cpa"), mm.get("cpa"), my.get("cpa"))}
{_build_comparison_row("플랫폼 평점", "", m.get("rating"), mm.get("rating"), my.get("rating"))}
{_build_comparison_row("카카오 순증", "명", m.get("kakao_growth"), mm.get("kakao_growth"), my.get("kakao_growth"))}
{alert_text}"""
    return msg


# --- Core orchestrator ---


async def run_daily_kpi():
    """일일 KPI 집계 → 비교표 생성 → Slack 발송 전체 파이프라인."""
    data = load_data()
    if not data:
        return {"status": "no_data"}

    latest = data[-1]
    current_date = latest.get("date", "")

    # 매출 데이터 추출 (new_revenue 포함)
    sales = get_sales_data(latest)

    # 전월 동일자 / 전년 동월(YoY) 데이터 조회
    prev_month = _get_previous_month_entry(data, current_date)
    yoy = _get_yoy_entry(data, current_date)

    # 이상 감지
    alerts = detect_anomalies(sales)

    # 비교표 형식 리포트 생성 (전월 + YoY)
    report = build_comparison_report(
        current=sales,
        prev_month=prev_month,
        yoy=yoy,
        alerts=alerts,
    )

    # Slack 발송 (Bot Token 우선, Webhook 폴백)
    if slack_notifier.is_configured:
        result = await slack_notifier.send_message(report)
    elif SLACK_WEBHOOK_URL:
        async with httpx.AsyncClient() as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": report})
            result = {"status": "webhook_sent", "code": resp.status_code}
    else:
        result = {"status": "simulation", "note": "Slack 미설정 — 시뮬레이션 모드"}

    return {"status": "ok", "report": report, "slack_result": result, "alerts": alerts}


# --- API routes ---


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/kpi/history")
async def get_history():
    return load_data()


@app.post("/api/kpi/submit")
async def submit_kpi(request: Request):
    body = await request.json()
    data = load_data()
    data = [d for d in data if d.get("date") != body.get("date")]
    data.append(body)
    data.sort(key=lambda x: x.get("date", ""))
    save_data(data)
    return {"status": "ok", "count": len(data)}


@app.post("/api/slack/preview")
async def slack_preview(request: Request):
    body = await request.json()
    data = load_data()
    current_date = body.get("date", "")
    prev_month = _get_previous_month_entry(data, current_date)
    yoy = _get_yoy_entry(data, current_date)
    sales = get_sales_data(body)
    alerts = detect_anomalies(sales)
    report = build_comparison_report(
        current=sales,
        prev_month=prev_month,
        yoy=yoy,
        alerts=alerts,
    )
    return {"message": report, "alerts": alerts}


@app.post("/api/slack/send")
async def slack_send(request: Request):
    body = await request.json()
    message = body.get("message", "")
    if slack_notifier.is_configured:
        result = await slack_notifier.send_message(message)
        return {"status": "sent", "result": result}
    if SLACK_WEBHOOK_URL:
        async with httpx.AsyncClient() as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": message})
            return {"status": "sent", "slack_status": resp.status_code}
    return {"status": "simulation", "note": "Slack 미설정 — 시뮬레이션 모드"}


@app.post("/api/kpi/run")
async def trigger_kpi(request: Request):
    """수동 트리거 엔드포인트."""
    result = await run_daily_kpi()
    return result


# --- Scheduler ---


def daily_kpi_job():
    """매일 지정 시각 실행 — Slack 자동 발송."""
    import asyncio
    asyncio.run(run_daily_kpi())


scheduler = BackgroundScheduler(timezone=TIMEZONE)
scheduler.add_job(daily_kpi_job, "cron", hour=KPI_CRON_HOUR, minute=KPI_CRON_MINUTE)
scheduler.start()

if __name__ == "__main__":
    import uvicorn
    print("📊 KPI 집계봇 시작 → http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
