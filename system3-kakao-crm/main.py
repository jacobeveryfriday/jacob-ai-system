"""Mili Mili 카카오 CRM 자동화"""
import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

load_dotenv()
app = FastAPI(title="카카오 CRM")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
DATA_FILE = Path(__file__).parent / "data" / "customers.json"
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

PRODUCTS = ["500달톤 히알루론산 세럼", "500달톤 콜라겐 크림", "500달톤 비타민C 앰플", "500달톤 레티놀 에센스", "500달톤 나이아신아마이드 토너"]

MESSAGE_TEMPLATES = {
    0: {"label": "T+0 감사 메시지", "template": "밀리밀리 500달톤 {product}을 선택해주셔서 감사합니다! 🎉\n\n최적의 효과를 위한 사용법을 안내드립니다:\n1. 세안 후 토너로 피부결 정돈\n2. 적당량을 얼굴 전체에 부드럽게 도포\n3. 가볍게 두드려 흡수시켜주세요\n\n500달톤 저분자 기술로 피부 깊숙이 전달됩니다 💧"},
    7: {"label": "T+7 만족도 체크", "template": "{name}님, 밀리밀리 제품 사용 일주일이 되었어요! 💧\n\n피부 변화가 느껴지시나요?\n보통 7일 차부터 피부 수분감 향상을 체감하실 수 있습니다.\n\n혹시 사용 중 궁금한 점이 있으시면 언제든 문의해주세요!\n⭐ 사용 후기를 남겨주시면 감사 포인트 500P를 드립니다!"},
    30: {"label": "T+30 재구매 쿠폰", "template": "한 달간 밀리밀리와 함께해주셨어요! 🎁\n\n{name}님의 피부가 더 건강해졌길 바랍니다.\n감사의 마음을 담아 재구매 시 20% 할인 쿠폰을 드립니다!\n\n🎟️ 쿠폰코드: MILI30-{code}\n⏰ 유효기간: 14일\n\n밀리밀리와 계속 함께해주세요 💕"},
    90: {"label": "T+90 VIP 초대", "template": "{name}님은 밀리밀리 VIP 고객이세요! ✨\n\n3개월간 밀리밀리를 사랑해주셔서 진심으로 감사합니다.\nVIP 고객님께 특별한 혜택을 준비했습니다:\n\n🎁 신제품 사전 체험 기회\n💰 VIP 전용 25% 상시 할인\n📦 무료 배송 영구 적용\n\n밀리 스킨 팬클럽에도 초대합니다!"}
}

SEQUENCE_DAYS = [0, 7, 30, 90]

def load_data() -> List[Dict]:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return []

def save_data(data: List[Dict]):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_sequence_status(customer: dict) -> List[Dict]:
    purchase = datetime.fromisoformat(customer["purchase_date"])
    today = datetime.now()
    days_since = (today - purchase).days
    sent = customer.get("sent_steps", [])
    result = []
    for day in SEQUENCE_DAYS:
        status = "completed" if day in sent else ("ready" if days_since >= day else "waiting")
        msg = MESSAGE_TEMPLATES[day]["template"].format(
            product=customer.get("product", "제품"),
            name=customer.get("name", "고객"),
            code=customer.get("id", "XXX")[:6].upper()
        )
        result.append({"day": day, "label": MESSAGE_TEMPLATES[day]["label"], "status": status, "message": msg})
    return result

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/customers")
async def list_customers():
    data = load_data()
    for c in data:
        c["sequence"] = get_sequence_status(c)
    return data

@app.post("/api/customers")
async def create_customer(request: Request):
    body = await request.json()
    data = load_data()
    body["id"] = str(uuid.uuid4())[:8]
    body["sent_steps"] = []
    body["created_at"] = datetime.now().isoformat()
    data.append(body)
    save_data(data)
    return {"status": "ok", "id": body["id"]}

@app.get("/api/customers/{customer_id}")
async def get_customer(customer_id: str):
    data = load_data()
    for c in data:
        if c["id"] == customer_id:
            c["sequence"] = get_sequence_status(c)
            return c
    return {"error": "not found"}

@app.post("/api/messages/{customer_id}/send")
async def send_message(customer_id: str, request: Request):
    body = await request.json()
    step = body.get("step", 0)
    data = load_data()
    for c in data:
        if c["id"] == customer_id:
            if step not in c.get("sent_steps", []):
                c.setdefault("sent_steps", []).append(step)
            save_data(data)
            # TODO: 카카오 API 연동 시 실제 발송
            return {"status": "simulation", "note": "카카오 API 미연동 — 시뮬레이션 발송 완료", "step": step}
    return {"error": "not found"}

@app.get("/api/stats")
async def get_stats():
    data = load_data()
    total = len(data)
    all_sent = sum(len(c.get("sent_steps", [])) for c in data)
    completed = sum(1 for c in data if set(SEQUENCE_DAYS).issubset(set(c.get("sent_steps", []))))
    pending = total - completed
    return {"total_customers": total, "total_messages_sent": all_sent, "completed_sequences": completed, "pending": pending}

@app.get("/api/products")
async def get_products():
    return PRODUCTS

if __name__ == "__main__":
    import uvicorn
    print("💌 카카오 CRM 시작 → http://localhost:8003")
    uvicorn.run(app, host="0.0.0.0", port=8003)
