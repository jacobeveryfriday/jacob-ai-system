"""SNS 콘텐츠 자동 발행 스케줄러"""
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

load_dotenv()
app = FastAPI(title="SNS 스케줄러")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
DATA_FILE = Path(__file__).parent / "data" / "contents.json"
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

def load_data() -> List[Dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []

def save_data(data: List[Dict]):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/contents")
async def list_contents():
    return load_data()

@app.post("/api/contents")
async def create_content(request: Request):
    body = await request.json()
    data = load_data()
    body["id"] = str(uuid.uuid4())[:8]
    body["status"] = "pending"
    body["created_at"] = datetime.now().isoformat()
    body.setdefault("performance", {})
    data.append(body)
    save_data(data)
    return {"status": "ok", "id": body["id"]}

@app.put("/api/contents/{content_id}/status")
async def update_status(content_id: str, request: Request):
    body = await request.json()
    data = load_data()
    for item in data:
        if item["id"] == content_id:
            item["status"] = body.get("status", item["status"])
            break
    save_data(data)
    return {"status": "ok"}

@app.post("/api/contents/{content_id}/publish")
async def publish_content(content_id: str):
    data = load_data()
    for item in data:
        if item["id"] == content_id:
            # Simulation mode
            item["status"] = "published"
            item["published_at"] = datetime.now().isoformat()
            break
    save_data(data)
    return {"status": "published", "mode": "simulation", "note": "API 미연동 — 시뮬레이션 모드로 발행 처리됨"}

@app.post("/api/performance/{content_id}")
async def update_performance(content_id: str, request: Request):
    body = await request.json()
    data = load_data()
    for item in data:
        if item["id"] == content_id:
            item["performance"] = body
            break
    save_data(data)
    return {"status": "ok"}

@app.get("/api/stats")
async def get_stats():
    data = load_data()
    total = len(data)
    published = sum(1 for d in data if d.get("status") == "published")
    pending = sum(1 for d in data if d.get("status") == "pending")
    failed = sum(1 for d in data if d.get("status") == "failed")
    platforms = {}
    for d in data:
        p = d.get("platform", "기타")
        platforms[p] = platforms.get(p, 0) + 1
    total_reach = sum(d.get("performance", {}).get("reach", 0) for d in data)
    total_engagement = sum(d.get("performance", {}).get("engagement", 0) for d in data)
    return {"total": total, "published": published, "pending": pending, "failed": failed,
            "platforms": platforms, "total_reach": total_reach, "total_engagement": total_engagement}

if __name__ == "__main__":
    import uvicorn
    print("📱 SNS 스케줄러 시작 → http://localhost:8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)
