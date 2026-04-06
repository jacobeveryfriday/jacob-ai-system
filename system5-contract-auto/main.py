"""전자계약 → 세금계산서 자동화"""
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
app = FastAPI(title="계약 자동화")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
DATA_FILE = Path(__file__).parent / "data" / "contracts.json"
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK_URL", "")

STAGES = ["입력", "서명", "입금", "세금계산서", "완료"]
PACKAGES = {"Starter": {"min": 100, "max": 200}, "Growth": {"min": 450, "max": 600}, "Enterprise": {"min": 800, "max": 1500}}

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

@app.get("/api/contracts")
async def list_contracts():
    return load_data()

@app.post("/api/contracts")
async def create_contract(request: Request):
    body = await request.json()
    data = load_data()
    body["id"] = "CTR-" + str(uuid.uuid4())[:6].upper()
    body["stage"] = "입력"
    body["stage_index"] = 0
    body["created_at"] = datetime.now().isoformat()
    body["history"] = [{"stage": "입력", "at": datetime.now().isoformat()}]
    data.append(body)
    save_data(data)
    return {"status": "ok", "id": body["id"]}

@app.get("/api/contracts/{contract_id}")
async def get_contract(contract_id: str):
    for c in load_data():
        if c["id"] == contract_id:
            return c
    return {"error": "not found"}

@app.put("/api/contracts/{contract_id}/status")
async def update_stage(contract_id: str, request: Request):
    body = await request.json()
    new_stage = body.get("stage")
    if new_stage not in STAGES:
        return {"error": "invalid stage"}
    data = load_data()
    for c in data:
        if c["id"] == contract_id:
            c["stage"] = new_stage
            c["stage_index"] = STAGES.index(new_stage)
            c.setdefault("history", []).append({"stage": new_stage, "at": datetime.now().isoformat()})
            break
    save_data(data)
    return {"status": "ok"}

@app.get("/api/contracts/{contract_id}/pdf")
async def preview_pdf(contract_id: str):
    data = load_data()
    contract = None
    for c in data:
        if c["id"] == contract_id:
            contract = c
            break
    if not contract:
        return HTMLResponse("<p>계약 없음</p>")
    html = f"""<html><head><style>
    body{{font-family:serif;padding:40px;max-width:800px;margin:0 auto;color:#333}}
    h1{{text-align:center;border-bottom:3px double #333;padding-bottom:20px}}
    table{{width:100%;border-collapse:collapse;margin:20px 0}}
    td{{padding:8px;border:1px solid #ccc}}
    .label{{background:#f5f5f5;font-weight:bold;width:30%}}
    .footer{{margin-top:60px;display:flex;justify-content:space-between}}
    .sign-box{{border-top:1px solid #333;width:200px;text-align:center;padding-top:8px}}
    </style></head><body>
    <h1>마케팅 서비스 계약서</h1>
    <p style='text-align:center'>계약번호: {contract['id']}</p>
    <table>
    <tr><td class='label'>계약 업체</td><td>{contract.get('company','')}</td></tr>
    <tr><td class='label'>담당자</td><td>{contract.get('contact_name','')}</td></tr>
    <tr><td class='label'>이메일</td><td>{contract.get('email','')}</td></tr>
    <tr><td class='label'>패키지</td><td>{contract.get('package','')}</td></tr>
    <tr><td class='label'>계약 금액</td><td>{contract.get('amount',0)}만원 (VAT 별도)</td></tr>
    <tr><td class='label'>시작일</td><td>{contract.get('start_date','')}</td></tr>
    <tr><td class='label'>종료일</td><td>{contract.get('end_date','')}</td></tr>
    </table>
    <p>본 계약서에 명시된 조건에 따라 08Liter Global은 상기 업체에 인플루언서 마케팅 서비스를 제공합니다.</p>
    <div class='footer'>
    <div class='sign-box'>08Liter Global<br>(서명)</div>
    <div class='sign-box'>{contract.get('company','')}<br>(서명)</div>
    </div></body></html>"""
    return HTMLResponse(html)

@app.post("/api/contracts/{contract_id}/sign-request")
async def sign_request(contract_id: str):
    # TODO: 모두싸인 API 연동
    return {"status": "simulation", "note": "서명 요청 이메일 발송 시뮬레이션 완료. 실제 연동 시 모두싸인 API 사용."}

@app.post("/api/contracts/{contract_id}/tax-invoice")
async def tax_invoice(contract_id: str):
    # TODO: 세금계산서 API 연동
    return {"status": "simulation", "note": "세금계산서 발행 요청 시뮬레이션 완료."}

@app.get("/api/stats")
async def get_stats():
    data = load_data()
    total = len(data)
    by_stage = {}
    by_package = {}
    total_amount = 0
    for c in data:
        s = c.get("stage", "입력")
        by_stage[s] = by_stage.get(s, 0) + 1
        p = c.get("package", "기타")
        by_package[p] = by_package.get(p, 0) + 1
        total_amount += c.get("amount", 0)
    avg_amount = round(total_amount / total) if total else 0
    return {"total": total, "by_stage": by_stage, "by_package": by_package, "total_amount": total_amount, "avg_amount": avg_amount}

if __name__ == "__main__":
    import uvicorn
    print("📄 계약 자동화 시작 → http://localhost:8005")
    uvicorn.run(app, host="0.0.0.0", port=8005)
