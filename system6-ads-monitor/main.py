"""Mili Mili 광고 성과 모니터링봇"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

load_dotenv()
app = FastAPI(title="광고 모니터링")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
DATA_FILE = Path(__file__).parent / "data" / "ads_data.json"
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

THRESHOLDS = {
    "roas_warning": 3.5, "roas_critical": 3.0,
    "cpa_warning": 20000, "cpa_critical": 25000,
    "ctr_warning": 1.0
}

def load_data() -> List[Dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []

def save_data(data: List[Dict]):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def check_anomalies(entry: dict) -> List[Dict]:
    alerts = []
    roas = entry.get("roas", 999)
    cpa = entry.get("cpa", 0)
    ctr = entry.get("ctr", 999)
    if roas < THRESHOLDS["roas_critical"]:
        alerts.append({"level": "critical", "metric": "ROAS", "value": roas, "threshold": THRESHOLDS["roas_critical"]})
    elif roas < THRESHOLDS["roas_warning"]:
        alerts.append({"level": "warning", "metric": "ROAS", "value": roas, "threshold": THRESHOLDS["roas_warning"]})
    if cpa > THRESHOLDS["cpa_critical"]:
        alerts.append({"level": "critical", "metric": "CPA", "value": cpa, "threshold": THRESHOLDS["cpa_critical"]})
    elif cpa > THRESHOLDS["cpa_warning"]:
        alerts.append({"level": "warning", "metric": "CPA", "value": cpa, "threshold": THRESHOLDS["cpa_warning"]})
    if ctr < THRESHOLDS["ctr_warning"]:
        alerts.append({"level": "warning", "metric": "CTR", "value": ctr, "threshold": THRESHOLDS["ctr_warning"]})
    return alerts

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/ads")
async def list_ads(platform: str = ""):
    data = load_data()
    if platform:
        data = [d for d in data if d.get("platform") == platform]
    return data

@app.post("/api/ads")
async def add_ad(request: Request):
    body = await request.json()
    data = load_data()
    body["id"] = str(uuid.uuid4())[:8]
    # Auto-calc derived metrics
    clicks = body.get("clicks", 0)
    impressions = body.get("impressions", 1)
    conversions = body.get("conversions", 0)
    spend = body.get("spend", 0)
    revenue = body.get("revenue", 0)
    body["ctr"] = round((clicks / impressions * 100) if impressions else 0, 2)
    body["cpa"] = round(spend / conversions) if conversions else 0
    body["roas"] = round(revenue / spend, 2) if spend else 0
    body["alerts"] = check_anomalies(body)
    data.append(body)
    save_data(data)
    return {"status": "ok", "id": body["id"]}

@app.post("/api/ads/csv")
async def upload_csv(request: Request):
    body = await request.json()
    rows = body.get("rows", [])
    data = load_data()
    for row in rows:
        row["id"] = str(uuid.uuid4())[:8]
        clicks = row.get("clicks", 0)
        impressions = row.get("impressions", 1)
        conversions = row.get("conversions", 0)
        spend = row.get("spend", 0)
        revenue = row.get("revenue", 0)
        row["ctr"] = round((clicks / impressions * 100) if impressions else 0, 2)
        row["cpa"] = round(spend / conversions) if conversions else 0
        row["roas"] = round(revenue / spend, 2) if spend else 0
        row["alerts"] = check_anomalies(row)
        data.append(row)
    save_data(data)
    return {"status": "ok", "count": len(rows)}

@app.get("/api/ads/alerts")
async def get_alerts():
    data = load_data()
    all_alerts = []
    for d in data:
        alerts = check_anomalies(d)
        if alerts:
            all_alerts.append({"campaign": d.get("campaign_name", ""), "creative": d.get("creative_name", ""), "platform": d.get("platform", ""), "alerts": alerts})
    return all_alerts

@app.post("/api/slack/send")
async def slack_send(request: Request):
    body = await request.json()
    msg = body.get("message", "")
    if not SLACK_WEBHOOK:
        return {"status": "simulation", "note": "SLACK_WEBHOOK_URL 미설정"}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(SLACK_WEBHOOK, json={"text": msg})
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/stats")
async def get_stats():
    data = load_data()
    by_platform = {}
    for d in data:
        p = d.get("platform", "기타")
        if p not in by_platform:
            by_platform[p] = {"spend": 0, "revenue": 0, "clicks": 0, "impressions": 0, "conversions": 0, "count": 0}
        by_platform[p]["spend"] += d.get("spend", 0)
        by_platform[p]["revenue"] += d.get("revenue", 0)
        by_platform[p]["clicks"] += d.get("clicks", 0)
        by_platform[p]["impressions"] += d.get("impressions", 0)
        by_platform[p]["conversions"] += d.get("conversions", 0)
        by_platform[p]["count"] += 1
    for p in by_platform:
        s = by_platform[p]
        s["roas"] = round(s["revenue"] / s["spend"], 2) if s["spend"] else 0
        s["cpa"] = round(s["spend"] / s["conversions"]) if s["conversions"] else 0
        s["ctr"] = round(s["clicks"] / s["impressions"] * 100, 2) if s["impressions"] else 0
    return by_platform

# 6시간 주기 체크 (시뮬레이션)
scheduler = BackgroundScheduler(timezone="Asia/Seoul")
def check_job():
    data = load_data()
    for d in data:
        d["alerts"] = check_anomalies(d)
    save_data(data)
scheduler.add_job(check_job, "interval", hours=6)
scheduler.start()

if __name__ == "__main__":
    import uvicorn
    print("📣 광고 모니터링 시작 → http://localhost:8006")
    uvicorn.run(app, host="0.0.0.0", port=8006)
