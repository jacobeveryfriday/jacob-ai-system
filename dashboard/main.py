"""Jacob AI Command Center — 통합 대시보드 + Google Sheets API"""
import json
import os
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict

import httpx
import requests as req_lib
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()
app = FastAPI(title="Command Center")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ===== 기본 인증 (비밀번호 보호) =====
DASH_USER = os.getenv("DASH_USER", "")
DASH_PASS = os.getenv("DASH_PASS", "")
security = HTTPBasic()


def check_auth(credentials: HTTPBasicCredentials = Depends(security)):
    """DASH_USER/DASH_PASS 설정 시 기본 인증 적용. 미설정 시 통과."""
    if not DASH_USER or not DASH_PASS:
        return True
    correct_user = secrets.compare_digest(credentials.username, DASH_USER)
    correct_pass = secrets.compare_digest(credentials.password, DASH_PASS)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True
DATA_DIR = Path(__file__).parent / "data"
CHECKLIST_FILE = DATA_DIR / "checklist.json"
KPI_FILE = DATA_DIR / "kpi_summary.json"

# ===== Google Sheets Config =====
GSHEETS_API_KEY = os.getenv("GOOGLE_SHEETS_API_KEY", "")
SHEET_INBOUND = "1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8"
SHEET_CONTRACT = "1j_3IYME764NlrARbNCZ_TJqzZCyfAMy-N3V-ByRik6Q"
SHEET_INFLUENCER = "1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs"
SHEET_ADS = "1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU"

_cache: Dict[str, list] = {}
_cache_time: Dict[str, float] = {}
CACHE_TTL = 1800  # 30 min

SYSTEMS = [
    {"name": "KPI 집계봇", "icon": "chart", "port": 8001, "desc": "일일 KPI 자동 집계 및 Slack 발송", "company": "공통"},
    {"name": "SNS 스케줄러", "icon": "share", "port": 8002, "desc": "SNS 콘텐츠 자동 발행 관리", "company": "공통"},
    {"name": "카카오 CRM", "icon": "msg", "port": 8003, "desc": "구매 후 메시지 시퀀스 자동화", "company": "Mili Mili"},
    {"name": "리드 파이프라인", "icon": "lead", "port": 8004, "desc": "인바운드 리드 수집 및 등급 분류", "company": "08Liter"},
    {"name": "계약 자동화", "icon": "doc", "port": 8005, "desc": "전자계약 파이프라인", "company": "08Liter"},
    {"name": "광고 모니터링", "icon": "ad", "port": 8006, "desc": "ROAS/CPA/CTR 실시간 추적", "company": "Mili Mili"},
    {"name": "리뷰 모니터링", "icon": "star", "port": 8007, "desc": "리뷰 추적 및 대응 관리", "company": "Mili Mili"},
]


# ===== Google Sheets Reader =====
def fetch_sheet(sheet_id: str, range_name: str, tab_name: str = None) -> list:
    """Google Sheets API v4로 데이터 읽기. API Key 없으면 빈 리스트."""
    if not GSHEETS_API_KEY:
        return []
    range_str = f"{tab_name}!{range_name}" if tab_name else range_name
    cache_key = f"{sheet_id}:{range_str}"
    now = time.time()
    if cache_key in _cache and (now - _cache_time.get(cache_key, 0)) < CACHE_TTL:
        return _cache[cache_key]
    try:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{req_lib.utils.quote(range_str)}?key={GSHEETS_API_KEY}"
        resp = req_lib.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("values", [])
            _cache[cache_key] = data
            _cache_time[cache_key] = now
            return data
    except Exception as e:
        print(f"Sheets API error: {e}")
    return []


# ===== Dummy Data =====
def _dummy_brand_pipeline():
    today_str = datetime.now().strftime("%Y.%m.%d")
    return {
        "source": "dummy",
        "today": {"inbound": 3, "valid": 12, "meeting": 5, "contract": 1, "renewal": 0},
        "month": {"inbound": 43, "valid": 127, "meeting": 28, "contract": 6, "renewal": 2},
        "prev_month": {"inbound": 38, "valid": 110, "meeting": 25, "contract": 8, "renewal": 3},
        "last_year": {"inbound": 22, "valid": 68, "meeting": 15, "contract": 5, "renewal": 1},
        "conversion": {"valid_rate": 29.5, "meeting_rate": 22.0, "contract_rate": 4.7, "renewal_rate": 0.5},
        "channel_breakdown": [
            {"channel": "SNS(메타)", "inbound": 18, "valid": 6, "rate": 33.3},
            {"channel": "이메일", "inbound": 8, "valid": 3, "rate": 37.5},
            {"channel": "CPC(네이버)", "inbound": 12, "valid": 2, "rate": 16.7},
            {"channel": "기타", "inbound": 5, "valid": 1, "rate": 20.0},
        ],
        "staff_breakdown": [
            {"name": "소필라", "inbound": 20, "valid": 8, "contract": 3, "rate": 40.0},
            {"name": "라이더", "inbound": 15, "valid": 6, "contract": 2, "rate": 40.0},
            {"name": "다엔", "inbound": 8, "valid": 3, "contract": 1, "rate": 37.5},
        ],
        "pipeline": {
            "인입DB": [
                {"name": "뷰티브랜드A", "channel": "인스타그램", "date": today_str, "staff": "미배정"},
                {"name": "코스메틱B", "channel": "구글광고", "date": today_str, "staff": "미배정"},
                {"name": "스킨케어C", "channel": "LinkedIn", "date": today_str, "staff": "미배정"},
            ],
            "유효DB": [
                {"name": "브랜드D", "channel": "카카오톡", "staff": "소필라", "contact_count": 2},
                {"name": "브랜드E", "channel": "이메일", "staff": "라이더", "contact_count": 1},
                {"name": "브랜드F", "channel": "전화", "staff": "다엔", "contact_count": 3, "expected": "450만"},
            ],
            "미팅": [
                {"name": "브랜드G", "meeting_date": "내일 14:00", "stage": "견적 검토중", "amount": "520만", "package": "Growth"},
                {"name": "브랜드H", "meeting_date": "목요일", "stage": "제안서 전달", "amount": "450만", "package": "Growth"},
            ],
            "계약서": [
                {"name": "브랜드I", "stage": "계약서 검토중", "amount": "600만", "package": "Premium"},
                {"name": "브랜드J", "stage": "내부 결재중", "amount": "800만", "package": "Enterprise"},
            ],
            "재계약": [
                {"name": "브랜드K", "date": "4월 1일", "amount": "420만", "package": "Growth", "paid": True},
                {"name": "브랜드L", "date": "3월 25일", "amount": "380만", "package": "Growth", "paid": True},
            ],
        },
    }


def _dummy_influencer_db():
    return {
        "source": "dummy", "total": 1400000, "items": [
            {"date": "2026-04-01", "type": "아웃바운드", "country": "KR", "category": "뷰티", "platform": "Instagram", "account": "@beauty_kr1", "url": "https://instagram.com/beauty_kr1", "followers": "520K", "followers_num": 520000, "email": "", "contact": "", "status": "사례활용가능", "currency": "", "price_collab": "180", "price_wish": "200", "price_krw": "180", "staff": "소필라", "campaign": "3월 캠페인", "note": ""},
            {"date": "2026-04-01", "type": "인바운드", "country": "TH", "category": "패션", "platform": "TikTok", "account": "@style_th", "url": "https://tiktok.com/@style_th", "followers": "380K", "followers_num": 380000, "email": "", "contact": "", "status": "제안발송", "currency": "", "price_collab": "120", "price_wish": "150", "price_krw": "120", "staff": "라이더", "campaign": "2월 캠페인", "note": ""},
            {"date": "2026-03-28", "type": "아웃바운드", "country": "US", "category": "뷰티", "platform": "Instagram", "account": "@skincare_us", "url": "", "followers": "210K", "followers_num": 210000, "email": "", "contact": "", "status": "단순리스트업", "currency": "", "price_collab": "250", "price_wish": "300", "price_krw": "250", "staff": "소필라", "campaign": "", "note": ""},
            {"date": "2026-03-25", "type": "아웃바운드", "country": "JP", "category": "라이프", "platform": "YouTube", "account": "@food_jp", "url": "", "followers": "890K", "followers_num": 890000, "email": "", "contact": "", "status": "사례활용가능", "currency": "", "price_collab": "320", "price_wish": "350", "price_krw": "320", "staff": "라이더", "campaign": "4월 예정", "note": ""},
            {"date": "2026-03-22", "type": "인바운드", "country": "VN", "category": "뷰티", "platform": "TikTok", "account": "@beauty_vn", "url": "", "followers": "190K", "followers_num": 190000, "email": "", "contact": "", "status": "제안발송", "currency": "", "price_collab": "70", "price_wish": "90", "price_krw": "70", "staff": "소필라", "campaign": "3월", "note": ""},
            {"date": "2026-03-20", "type": "아웃바운드", "country": "ID", "category": "피트니스", "platform": "TikTok", "account": "@fit_id", "url": "", "followers": "330K", "followers_num": 330000, "email": "", "contact": "", "status": "단순리스트업", "currency": "", "price_collab": "90", "price_wish": "110", "price_krw": "90", "staff": "라이더", "campaign": "", "note": ""},
        ],
        "stats": {
            "by_country": {"KR": 2, "TH": 1, "US": 1, "JP": 1, "VN": 1, "ID": 1},
            "by_platform": {"Instagram": 3, "TikTok": 3, "YouTube": 1},
            "by_status": {"사례활용가능": 2, "제안발송": 2, "단순리스트업": 2},
            "by_category": {"뷰티": 3, "패션": 1, "라이프": 1, "피트니스": 1},
        },
    }


def _dummy_ads_performance():
    return {
        "source": "dummy",
        "month": {
            "meta": {"spend": 9000000, "db": 18, "cpa": 500000, "roas": 0},
            "google": {"spend": 5000000, "db": 9, "cpa": 556000, "roas": 0},
            "naver": {"spend": 8000000, "db": 12, "cpa": 667000, "roas": 0},
            "kakao": {"spend": 2000000, "db": 4, "cpa": 500000, "roas": 0},
            "total": {"spend": 24000000, "db": 43, "cpa": 558000, "roas": 9.41},
        },
        "monthly_trend": [
            {"month": "2025.09", "contracts": 26, "revenue": 124800000, "spend": 22000000, "roas": 5.67, "avg_price": 4800000},
            {"month": "2025.10", "contracts": 26, "revenue": 135200000, "spend": 21000000, "roas": 6.44, "avg_price": 5200000},
            {"month": "2025.11", "contracts": 43, "revenue": 249400000, "spend": 25000000, "roas": 9.98, "avg_price": 5800000},
            {"month": "2025.12", "contracts": 45, "revenue": 157500000, "spend": 18000000, "roas": 8.75, "avg_price": 3500000},
            {"month": "2026.01", "contracts": 32, "revenue": 121600000, "spend": 23420000, "roas": 5.19, "avg_price": 3800000},
            {"month": "2026.02", "contracts": 30, "revenue": 99000000, "spend": 15870000, "roas": 6.24, "avg_price": 3300000},
            {"month": "2026.03", "contracts": 47, "revenue": 155100000, "spend": 17431000, "roas": 8.90, "avg_price": 3300000},
            {"month": "2026.04", "contracts": 6, "revenue": 22200000, "spend": 24000000, "roas": 0.93, "avg_price": 3700000},
        ],
    }


# ===== Live Sheets Parsing (2026-04-06 컬럼 확인 반영) =====
def _parse_inbound(rows):
    """인바운드 파센문의 탭 파싱. A=국가,B=월,C=날짜,D=유입채널,...P=컨택현황"""
    today = datetime.now()
    this_month = f"{today.year}.{today.month:02d}"
    today_day = f"{today.month}/{today.day}"
    today_day2 = f"{today.month}/{today.day:02d}"
    skip_kw = ["국가", "주의사항", "본 리스트", "[ ", "*"]
    result = {"today_inbound": 0, "month_inbound": 0, "today_valid": 0, "month_valid": 0,
              "channel_stats": {}, "staff_stats": {}, "source_stats": {},
              "pipeline_items": {"인입DB": [], "유효DB": [], "미팅": [], "계약서": [], "재계약": []}}
    for row in rows:
        if not row or len(row) < 3:
            continue
        country = str(row[0]).strip()
        if not country or any(k in country for k in skip_kw):
            continue
        month_val = str(row[1]).strip() if len(row) > 1 else ""
        date_val = str(row[2]).strip() if len(row) > 2 else ""
        channel = str(row[3]).strip() if len(row) > 3 else ""
        brand = str(row[4]).strip() if len(row) > 4 else ""
        source = str(row[10]).strip() if len(row) > 10 else ""
        staff = str(row[13]).strip() if len(row) > 13 else ""
        status = str(row[15]).strip() if len(row) > 15 else ""
        is_month = this_month in month_val
        is_today = (date_val == today_day or date_val == today_day2)
        is_valid = "워킹" in status
        ch = channel.lower()
        if any(k in ch for k in ["sns", "메타", "insta", "meta"]):
            ch_key = "SNS(메타)"
        elif any(k in ch for k in ["email", "이메일", "mail"]):
            ch_key = "이메일"
        elif any(k in ch for k in ["cpc", "네이버", "naver", "검색"]):
            ch_key = "CPC(네이버)"
        else:
            ch_key = channel[:8] if channel else "기타"
        if is_month:
            result["month_inbound"] += 1
            result["channel_stats"][ch_key] = result["channel_stats"].get(ch_key, 0) + 1
            if source:
                result["source_stats"][source] = result["source_stats"].get(source, 0) + 1
            if staff:
                if staff not in result["staff_stats"]:
                    result["staff_stats"][staff] = {"inbound": 0, "valid": 0}
                result["staff_stats"][staff]["inbound"] += 1
            card = {"name": brand, "channel": ch_key, "staff": staff or "미배정", "date": date_val, "source": source}
            if is_valid:
                result["month_valid"] += 1
                if staff and staff in result["staff_stats"]:
                    result["staff_stats"][staff]["valid"] += 1
                result["pipeline_items"]["유효DB"].append(card)
            else:
                result["pipeline_items"]["인입DB"].append(card)
        if is_today:
            result["today_inbound"] += 1
            if is_valid:
                result["today_valid"] += 1
    return result


def _parse_contracts(rows):
    """계산서발행 탭 파싱. B(idx0)=작성일자,D(idx2)=작성월,G(idx5)=신규/재계약,I(idx7)=상호,T(idx18)=공급가액"""
    today = datetime.now()
    this_month = f"{today.year}.{today.month:02d}"
    prev_dt = today.replace(day=1) - timedelta(days=1)
    prev_month = f"{prev_dt.year}.{prev_dt.month:02d}"
    ly_month = f"{today.year - 1}.{today.month:02d}"
    today_ymd = today.strftime("%Y%m%d")
    result = {"today_contract": 0, "month_contract": 0, "prev_month_contract": 0,
              "last_year_contract": 0, "month_renewal": 0, "prev_month_renewal": 0,
              "today_revenue": 0, "month_revenue": 0, "prev_month_revenue": 0,
              "last_year_revenue": 0, "brands": [], "today_brands": []}
    for row in rows:
        if not row or len(row) < 3:
            continue
        date_b = str(row[0]).strip() if len(row) > 0 else ""
        month_d = str(row[2]).strip() if len(row) > 2 else ""
        staff = str(row[3]).strip() if len(row) > 3 else ""
        ctype = str(row[5]).strip() if len(row) > 5 else ""
        brand = str(row[7]).strip() if len(row) > 7 else ""
        revenue_raw = str(row[18]).strip() if len(row) > 18 else "0"
        try:
            revenue = int(float(revenue_raw.replace(",", "").replace("\u20a9", ""))) if revenue_raw and revenue_raw not in ["-", ""] else 0
        except (ValueError, TypeError):
            revenue = 0
        if revenue < 0:
            revenue = 0
        date_clean = date_b.replace("-", "").replace(".", "").replace("/", "")
        if len(date_clean) < 6 or not date_clean[:6].isdigit():
            continue
        is_today_row = (date_clean[:8] == today_ymd)
        is_this_month = (this_month in month_d or date_clean[:6] == f"{today.year}{today.month:02d}")
        is_prev_month = prev_month in month_d
        is_last_year = ly_month in month_d
        is_renewal = (ctype and "신규" not in ctype and "확인필요" not in ctype and ctype != "-")
        brand_card = {"name": brand, "type": "재계약" if is_renewal else "신규", "staff": staff, "date": date_b, "revenue": revenue}
        if is_today_row:
            result["today_contract"] += 1
            result["today_revenue"] += revenue
            result["today_brands"].append(brand_card)
        if is_this_month:
            result["month_contract"] += 1
            result["month_revenue"] += revenue
            if is_renewal:
                result["month_renewal"] += 1
            result["brands"].append(brand_card)
        if is_prev_month:
            result["prev_month_contract"] += 1
            result["prev_month_revenue"] += revenue
            if is_renewal:
                result["prev_month_renewal"] += 1
        if is_last_year:
            result["last_year_contract"] += 1
            result["last_year_revenue"] += revenue
    return result


# ===== Helpers =====
def load_checklist() -> List[Dict]:
    if CHECKLIST_FILE.exists():
        return json.loads(CHECKLIST_FILE.read_text(encoding="utf-8"))
    return []

def save_checklist(data: List[Dict]):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHECKLIST_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ===== Routes =====
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, auth=Depends(check_auth)):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def check_status():
    results = []
    async with httpx.AsyncClient(timeout=2.0) as client:
        for sys in SYSTEMS:
            try:
                resp = await client.get(f"http://localhost:{sys['port']}/")
                results.append({**sys, "status": "online" if resp.status_code == 200 else "error"})
            except Exception:
                results.append({**sys, "status": "offline"})
    return results

@app.get("/api/alerts")
async def get_alerts():
    alerts = []
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            resp = await client.get("http://localhost:8006/api/ads/alerts")
            if resp.status_code == 200:
                for a in resp.json():
                    alerts.append({"system": "광고", "detail": f"{a.get('creative', '')} - {len(a.get('alerts', []))}건"})
        except Exception:
            pass
        try:
            resp = await client.get("http://localhost:8007/api/alerts")
            if resp.status_code == 200:
                urgent = [r for r in resp.json() if r.get("rating", 5) <= 3]
                if urgent:
                    alerts.append({"system": "리뷰", "detail": f"긴급 대응 {len(urgent)}건"})
        except Exception:
            pass
    return alerts

@app.get("/api/checklist")
async def get_checklist():
    return load_checklist()

@app.post("/api/checklist")
async def update_checklist(request: Request):
    body = await request.json()
    save_checklist(body)
    return {"status": "ok"}

@app.post("/api/checklist/add")
async def add_checklist_item(request: Request):
    body = await request.json()
    data = load_checklist()
    data.append({"text": body.get("text", ""), "done": False, "created_at": datetime.now().isoformat()})
    save_checklist(data)
    return {"status": "ok"}


# ===== Google Sheets API Endpoints =====
@app.get("/api/brand-pipeline")
async def api_brand_pipeline():
    """브랜드 파이프라인 (Google Sheets 연동 or 더미). 2026-04-06 컬럼 확인 반영."""
    if not GSHEETS_API_KEY:
        dummy = _dummy_brand_pipeline()
        dummy["note"] = "GOOGLE_SHEETS_API_KEY 미입력"
        dummy["not_connected"] = ["광고CPA", "CS", "유효DB(컨택현황 업데이트 필요)"]
        return dummy
    try:
        inbound_rows = fetch_sheet(SHEET_INBOUND, "A:R", "파센문의")
        contract_rows = fetch_sheet(SHEET_CONTRACT, "B:U", "계산서발행")
        ib = _parse_inbound(inbound_rows) if inbound_rows else {}
        ct = _parse_contracts(contract_rows) if contract_rows else {}
        return {
            "source": "live",
            "today": {
                "inbound": ib.get("today_inbound", 0),
                "valid": ib.get("today_valid", 0),
                "contract": ct.get("today_contract", 0),
                "revenue": ct.get("today_revenue", 0),
            },
            "month": {
                "inbound": ib.get("month_inbound", 0),
                "valid": ib.get("month_valid", 0),
                "contract": ct.get("month_contract", 0),
                "revenue": ct.get("month_revenue", 0),
                "renewal": ct.get("month_renewal", 0),
            },
            "prev_month": {
                "contract": ct.get("prev_month_contract", 0),
                "revenue": ct.get("prev_month_revenue", 0),
                "renewal": ct.get("prev_month_renewal", 0),
            },
            "last_year": {
                "contract": ct.get("last_year_contract", 0),
                "revenue": ct.get("last_year_revenue", 0),
            },
            "channel_breakdown": [
                {"channel": k, "inbound": v, "valid": 0}
                for k, v in ib.get("channel_stats", {}).items()
            ],
            "staff_breakdown": [
                {"name": k, "inbound": v.get("inbound", 0), "valid": v.get("valid", 0),
                 "rate": round(v.get("valid", 0) / max(v.get("inbound", 1), 1) * 100, 1)}
                for k, v in ib.get("staff_stats", {}).items()
            ],
            "pipeline": ib.get("pipeline_items", {}),
            "not_connected": ["광고CPA", "CS"],
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"source": "error", "error": str(e)}


@app.get("/api/influencer-db")
async def api_influencer_db(
    country: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_followers: Optional[int] = Query(0),
    status: Optional[str] = Query(None),
):
    """인플루언서 DB (Google Sheets 연동 or 더미)"""
    if not GSHEETS_API_KEY:
        return _dummy_influencer_db()
    try:
        rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", "현황시트(수동매칭)")
        if not rows:
            return _dummy_influencer_db()
        items = []
        stats = {"by_country": {}, "by_platform": {}, "by_status": {}, "by_category": {}}
        for row in rows:
            if len(row) < 5:
                continue
            item = {
                "date": row[0] if len(row) > 0 else "",
                "type": row[1] if len(row) > 1 else "",
                "country": row[2] if len(row) > 2 else "",
                "category": row[3] if len(row) > 3 else "",
                "platform": row[4] if len(row) > 4 else "",
                "account": row[5] if len(row) > 5 else "",
                "url": row[6] if len(row) > 6 else "",
                "followers": row[7] if len(row) > 7 else "0",
                "email": row[8] if len(row) > 8 else "",
                "contact": row[9] if len(row) > 9 else "",
                "status": row[10] if len(row) > 10 else "",
                "currency": row[11] if len(row) > 11 else "",
                "price_collab": row[12] if len(row) > 12 else "",
                "price_wish": row[13] if len(row) > 13 else "",
                "price_krw": row[14] if len(row) > 14 else "",
                "staff": row[15] if len(row) > 15 else "",
                "campaign": row[16] if len(row) > 16 else "",
                "note": row[17] if len(row) > 17 else "",
            }
            fw_str = str(item["followers"]).replace(",", "").strip().upper()
            fw = 0
            try:
                if "M" in fw_str:
                    fw = float(fw_str.replace("M", "")) * 1000000
                elif "K" in fw_str:
                    fw = float(fw_str.replace("K", "")) * 1000
                else:
                    fw = float(fw_str) if fw_str else 0
            except ValueError:
                pass
            item["followers_num"] = fw
            if country and item["country"] != country:
                continue
            if platform and platform.lower() not in item["platform"].lower():
                continue
            if category and item["category"] != category:
                continue
            if min_followers and fw < min_followers * 1000:
                continue
            if status and status not in item.get("status", ""):
                continue
            items.append(item)
            c = item["country"]
            stats["by_country"][c] = stats["by_country"].get(c, 0) + 1
            p = item["platform"][:12]
            stats["by_platform"][p] = stats["by_platform"].get(p, 0) + 1
            s = item["status"][:12] if item["status"] else "미분류"
            stats["by_status"][s] = stats["by_status"].get(s, 0) + 1
            cat = item["category"]
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        return {"source": "live", "total": len(items), "items": items[:200], "stats": stats}
    except Exception as e:
        print(f"influencer-db error: {e}")
        return _dummy_influencer_db()


@app.get("/api/ads-performance")
async def api_ads_performance():
    """광고 성과 (Google Sheets 연동 or 더미)"""
    if not GSHEETS_API_KEY:
        return _dummy_ads_performance()
    try:
        rows = fetch_sheet(SHEET_ADS, "A1:O", "공팔리터B2B")
        if not rows:
            return _dummy_ads_performance()
        monthly = []
        for row in rows:
            if not row or len(row) < 8:
                continue
            month_str = str(row[5]).strip() if len(row) > 5 else ""
            if "20" not in month_str or "." not in month_str:
                continue
            try:
                def parse_int(v):
                    return int(str(v).replace(",", "").replace("₩", "").strip()) if v else 0
                contracts = parse_int(row[6]) if len(row) > 6 else 0
                revenue = parse_int(row[7]) if len(row) > 7 else 0
                spend = parse_int(row[10]) if len(row) > 10 else 0
                roas_str = str(row[11]).replace("%", "").strip() if len(row) > 11 and row[11] else "0"
                roas = float(roas_str) / 100 if float(roas_str) > 1 else float(roas_str)
                avg_price = parse_int(row[12]) if len(row) > 12 else 0
                monthly.append({"month": month_str, "contracts": contracts, "revenue": revenue,
                                "spend": spend, "roas": round(roas, 2), "avg_price": avg_price})
            except Exception:
                continue
        result = _dummy_ads_performance()
        result["source"] = "live"
        if monthly:
            result["monthly_trend"] = monthly[-12:]
        return result
    except Exception as e:
        print(f"ads-performance error: {e}")
        return _dummy_ads_performance()


@app.get("/api/kpi-summary")
async def api_kpi_summary():
    """총괄 KPI 요약 (brand + ads 합산). 매출은 계산서발행 T열(공급가액) 기준."""
    brand = await api_brand_pipeline()
    ads = await api_ads_performance()
    today = brand.get("today", {})
    month = brand.get("month", {})
    prev = brand.get("prev_month", {})
    ly = brand.get("last_year", {})
    trend = ads.get("monthly_trend", [])
    last_roas = trend[-1].get("roas", 0) if trend else 0
    month_revenue = month.get("revenue", 0)
    month_contract = month.get("contract", 0)
    return {
        "source": brand.get("source", "dummy"),
        "not_connected": brand.get("not_connected", []),
        "today": {
            "revenue": today.get("revenue", 0),
            "inbound_db": today.get("inbound", 0),
            "valid_db": today.get("valid", 0),
            "contract": today.get("contract", 0),
        },
        "month": {
            "revenue": month_revenue,
            "contract": month_contract,
            "avg_price": int(month_revenue / max(month_contract, 1)),
            "inbound_db": month.get("inbound", 0),
            "valid_db": month.get("valid", 0),
            "renewal": month.get("renewal", 0),
            "roas": last_roas,
            "influencer_pool": 1400000,
        },
        "prev_month": {"revenue": prev.get("revenue", 0), "contract": prev.get("contract", 0)},
        "last_year": {"revenue": ly.get("revenue", 0), "contract": ly.get("contract", 0)},
        "monthly_trend": trend,
    }


@app.get("/api/brand-comparison")
async def api_brand_comparison():
    """기간별 비교표"""
    brand = await api_brand_pipeline()
    m = brand.get("month", {})
    p = brand.get("prev_month", {})
    ly = brand.get("last_year", {})

    def pct(cur, prev):
        return round((cur - prev) / max(prev, 1) * 100, 1) if prev else 0

    return {"comparison": [
        {"metric": "인입 DB", "today": brand["today"]["inbound"], "month": m["inbound"], "prev_month": p.get("inbound", 0), "mom_pct": pct(m["inbound"], p.get("inbound", 1)), "last_year": ly.get("inbound", 0), "yoy_pct": pct(m["inbound"], ly.get("inbound", 1))},
        {"metric": "유효 DB", "today": brand["today"]["valid"], "month": m["valid"], "prev_month": p.get("valid", 0), "mom_pct": pct(m["valid"], p.get("valid", 1)), "last_year": ly.get("valid", 0), "yoy_pct": pct(m["valid"], ly.get("valid", 1))},
        {"metric": "미팅", "today": brand["today"]["meeting"], "month": m["meeting"], "prev_month": p.get("meeting", 0), "mom_pct": pct(m["meeting"], p.get("meeting", 1)), "last_year": ly.get("meeting", 0), "yoy_pct": pct(m["meeting"], ly.get("meeting", 1))},
        {"metric": "계약서", "today": brand["today"]["contract"], "month": m["contract"], "prev_month": p.get("contract", 0), "mom_pct": pct(m["contract"], p.get("contract", 1)), "last_year": ly.get("contract", 0), "yoy_pct": pct(m["contract"], ly.get("contract", 1))},
        {"metric": "재계약", "today": brand["today"]["renewal"], "month": m["renewal"], "prev_month": p.get("renewal", 0), "mom_pct": pct(m["renewal"], p.get("renewal", 1)), "last_year": ly.get("renewal", 0), "yoy_pct": pct(m["renewal"], ly.get("renewal", 1))},
    ]}


@app.get("/api/sheets-status")
async def api_sheets_status():
    """Google Sheets 연동 상태 확인"""
    api_key = os.getenv("GOOGLE_SHEETS_API_KEY", "")
    return {
        "connected": bool(api_key),
        "source": "live" if api_key else "dummy",
        "sheets": {
            "inbound": SHEET_INBOUND,
            "contract": SHEET_CONTRACT,
            "influencer": SHEET_INFLUENCER,
            "ads": SHEET_ADS,
        },
        "guide": "" if api_key else "console.cloud.google.com에서 Sheets API 활성화 후 API 키 발급 -> .env에 GOOGLE_SHEETS_API_KEY=키값 입력",
    }


@app.get("/api/cache-clear")
async def api_cache_clear():
    """캐시 초기화"""
    _cache.clear()
    _cache_time.clear()
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    print("Jacob AI Command Center -> http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
