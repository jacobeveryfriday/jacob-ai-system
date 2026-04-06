"""인바운드 리드 자동 수집 파이프라인"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

load_dotenv()
app = FastAPI(title="리드 파이프라인")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
DATA_FILE = Path(__file__).parent / "data" / "leads.json"
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

def load_data() -> List[Dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []

def save_data(data: List[Dict]):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def grade_lead(lead: dict) -> str:
    budget = lead.get("budget", 0)
    package = lead.get("package_interest", "")
    urgency = lead.get("urgency", "")
    if budget >= 500 or package == "Enterprise" or urgency == "immediate":
        return "HOT"
    if budget >= 300 or package == "Growth" or lead.get("has_meeting"):
        return "WARM"
    return "COLD"

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/leads")
async def list_leads(grade: str = "", channel: str = "", status: str = ""):
    data = load_data()
    if grade:
        data = [d for d in data if d.get("grade") == grade]
    if channel:
        data = [d for d in data if d.get("channel") == channel]
    if status:
        data = [d for d in data if d.get("status") == status]
    return data

@app.post("/api/leads")
async def create_lead(request: Request):
    body = await request.json()
    data = load_data()
    body["id"] = str(uuid.uuid4())[:8]
    body["grade"] = grade_lead(body)
    body.setdefault("status", "new")
    body.setdefault("assigned_to", "")
    body.setdefault("notes", "")
    body["created_at"] = datetime.now().isoformat()
    data.append(body)
    save_data(data)
    return {"status": "ok", "id": body["id"], "grade": body["grade"]}

@app.post("/api/webhook/lead")
async def webhook_lead(request: Request):
    body = await request.json()
    body["channel"] = body.get("channel", "webhook")
    data = load_data()
    body["id"] = str(uuid.uuid4())[:8]
    body["grade"] = grade_lead(body)
    body.setdefault("status", "new")
    body["created_at"] = datetime.now().isoformat()
    data.append(body)
    save_data(data)
    return {"status": "ok", "id": body["id"]}

@app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: str):
    for d in load_data():
        if d["id"] == lead_id:
            return d
    return {"error": "not found"}

@app.put("/api/leads/{lead_id}")
async def update_lead(lead_id: str, request: Request):
    body = await request.json()
    data = load_data()
    for d in data:
        if d["id"] == lead_id:
            d.update(body)
            if "budget" in body or "package_interest" in body or "urgency" in body:
                d["grade"] = grade_lead(d)
            break
    save_data(data)
    return {"status": "ok"}

@app.post("/api/slack/notify/{lead_id}")
async def slack_notify(lead_id: str):
    data = load_data()
    lead = None
    for d in data:
        if d["id"] == lead_id:
            lead = d
            break
    if not lead:
        return {"error": "not found"}
    msg = f"""🆕 *새 리드 알림*
• 회사: {lead.get('company','-')}
• 담당자: {lead.get('contact_name','-')}
• 등급: {lead.get('grade','-')}
• 패키지: {lead.get('package_interest','-')}
• 예산: {lead.get('budget',0)}만원
• 채널: {lead.get('channel','-')}
• 긴급도: {lead.get('urgency','-')}"""
    if not SLACK_WEBHOOK:
        return {"status": "simulation", "message": msg}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(SLACK_WEBHOOK, json={"text": msg})
        return {"status": "sent"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/stats")
async def get_stats():
    data = load_data()
    grades = {"HOT": 0, "WARM": 0, "COLD": 0}
    channels = {}
    statuses = {}
    for d in data:
        g = d.get("grade", "COLD")
        grades[g] = grades.get(g, 0) + 1
        ch = d.get("channel", "기타")
        channels[ch] = channels.get(ch, 0) + 1
        st = d.get("status", "new")
        statuses[st] = statuses.get(st, 0) + 1
    return {"total": len(data), "grades": grades, "channels": channels, "statuses": statuses}

if __name__ == "__main__":
    import uvicorn
    print("🆕 리드 파이프라인 시작 → http://localhost:8004")
    uvicorn.run(app, host="0.0.0.0", port=8004)
