"""Jacob AI Command Center — 통합 대시보드 + Google Sheets API + Anthropic AI Agents"""
import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from zoneinfo import ZoneInfo

import httpx
import requests as req_lib
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv(override=False)  # OS 환경변수(Railway)가 .env보다 우선
app = FastAPI(title="Command Center")
KST = ZoneInfo("Asia/Seoul")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ===== 로그인 인증 (쿠키 세션 방식) =====
DASH_USER = os.getenv("DASH_USER", "")
DASH_PASS = os.getenv("DASH_PASS", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))


def _make_token(user: str) -> str:
    return hashlib.sha256(f"{user}:{SESSION_SECRET}".encode()).hexdigest()


@app.get("/health")
async def health_check():
    """향상된 헬스체크 — sheets/openai/slack 상태 포함"""
    status = {"status": "ok", "timestamp": datetime.now().isoformat()}
    # Sheets
    status["sheets"] = "connected" if GSHEETS_API_KEY else "not_configured"
    # OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", "")
    status["openai"] = "connected" if openai_key else "not_configured"
    # Slack
    slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
    status["slack"] = "connected" if slack_url else "not_configured"
    # Resend Email
    status["email"] = "connected" if os.getenv("RESEND_API_KEY") else "not_configured"
    # Anthropic
    status["anthropic"] = "connected" if os.getenv("ANTHROPIC_API_KEY", "") else "not_configured"
    # Cache stats
    status["cache_entries"] = len(_cache)
    return status


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """로그인 폼 페이지"""
    if not DASH_USER or not DASH_PASS:
        return RedirectResponse("/", status_code=302)
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login — Jacob AI</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
display:flex;align-items:center;justify-content:center;min-height:100vh}}
.card{{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:40px;width:360px;text-align:center}}
h1{{font-size:24px;margin-bottom:8px;color:#f0883e}}
.sub{{color:#8b949e;margin-bottom:24px;font-size:14px}}
input{{width:100%;padding:12px 16px;margin-bottom:12px;background:#0d1117;border:1px solid #30363d;
border-radius:8px;color:#e6edf3;font-size:15px;outline:none}}
input:focus{{border-color:#f0883e}}
button{{width:100%;padding:12px;background:#f0883e;color:#fff;border:none;border-radius:8px;
font-size:16px;font-weight:600;cursor:pointer;margin-top:4px}}
button:hover{{background:#d97706}}
.err{{color:#f85149;font-size:13px;margin-bottom:12px}}
</style></head><body>
<div class="card">
<h1>⚡ Jacob AI</h1>
<p class="sub">Command Center</p>
{"<p class='err'>아이디 또는 비밀번호가 틀렸습니다.</p>" if error else ""}
<form method="post" action="/login">
<input name="username" placeholder="아이디" required autocomplete="username">
<input name="password" type="password" placeholder="비밀번호" required autocomplete="current-password">
<button type="submit">로그인</button>
</form></div></body></html>"""
    return HTMLResponse(html)


@app.post("/login")
async def login_submit(request: Request):
    """로그인 처리"""
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    if secrets.compare_digest(str(username), DASH_USER) and secrets.compare_digest(str(password), DASH_PASS):
        resp = RedirectResponse("/", status_code=302)
        resp.set_cookie("session", _make_token(DASH_USER), httponly=True, samesite="lax", max_age=86400 * 7)
        return resp
    return RedirectResponse("/login?error=1", status_code=302)


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=302)
    resp.delete_cookie("session")
    return resp


def is_authenticated(request: Request) -> bool:
    """쿠키 세션 기반 인증 확인. DASH_USER 미설정 시 항상 True."""
    if not DASH_USER or not DASH_PASS:
        return True
    token = request.cookies.get("session", "")
    return bool(token and secrets.compare_digest(token, _make_token(DASH_USER)))
DATA_DIR = Path(__file__).parent / "data"
CHECKLIST_FILE = DATA_DIR / "checklist.json"
KPI_FILE = DATA_DIR / "kpi_summary.json"

# ===== Google Sheets Config =====
GSHEETS_API_KEY = os.getenv("GOOGLE_SHEETS_API_KEY", "")
SHEET_INBOUND = os.getenv("INBOUND_SHEET_ID", "1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8")
SHEET_CONTRACT = os.getenv("GOOGLE_SHEETS_ID", "1j_3IYME764NlrARbNCZ_TJqzZCyfAMy-N3V-ByRik6Q")
SHEET_INFLUENCER = "1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs"
SHEET_ADS = "1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU"

_cache: Dict[str, list] = {}
_cache_time: Dict[str, float] = {}
CACHE_TTLS = {
    "inbound": 300,      # 5 min - 인바운드는 빠르게 갱신
    "contract": 3600,    # 1 hour
    "influencer": 21600, # 6 hours
    "ads": 3600,         # 1 hour
    "default": 1800,     # 30 min fallback
}

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
def fetch_sheet(sheet_id: str, range_name: str, tab_name: str = None, ttl_key: str = "default") -> list:
    """Google Sheets API v4로 데이터 읽기. API Key 없으면 빈 리스트."""
    if not GSHEETS_API_KEY:
        return []
    range_str = f"{tab_name}!{range_name}" if tab_name else range_name
    cache_key = f"{sheet_id}:{range_str}"
    now = time.time()
    ttl = CACHE_TTLS.get(ttl_key, CACHE_TTLS["default"])
    if cache_key in _cache and (now - _cache_time.get(cache_key, 0)) < ttl:
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
        "today": {"inbound": 3, "valid": 12, "meeting": 5, "contract": 1, "renewal": 0, "unhandled": 2, "handled": 1},
        "month": {"inbound": 43, "valid": 127, "meeting": 28, "contract": 6, "renewal": 2, "unhandled": 15},
        "unhandled_brands": [{"name": "샘플브랜드A", "channel": "SNS(메타)", "source": "", "date": "오늘", "reason": "담당자 없음"}],
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


# ===== 날짜/채널 헬퍼 =====
def _is_date_today(date_val: str, now: datetime) -> bool:
    """날짜 문자열이 오늘(KST)인지 판단. 5가지 형식 지원."""
    if not date_val:
        return False
    td, tm = now.day, now.month
    for p in [f"{tm}/{td}", f"{tm}/{td:02d}", f"{tm:02d}/{td}", f"{tm:02d}/{td:02d}"]:
        if date_val == p:
            return True
    today_iso = now.strftime("%Y-%m-%d")
    if date_val.startswith(today_iso):
        return True
    today_ymd = now.strftime("%Y%m%d")
    clean = date_val.replace("-", "").replace(".", "").replace("/", "").replace(" ", "")
    if clean.startswith(today_ymd):
        return True
    return False


def _is_date_this_month(date_val: str, now: datetime) -> bool:
    """날짜 문자열이 이번 달인지 판단."""
    if not date_val:
        return False
    try:
        if "/" in date_val:
            return int(date_val.split("/")[0]) == now.month
        elif "-" in date_val:
            parts = date_val.split("-")
            if len(parts) >= 2 and len(parts[0]) == 4:
                return int(parts[0]) == now.year and int(parts[1]) == now.month
    except (ValueError, IndexError):
        pass
    return False


def _classify_channel(channel: str) -> str:
    """유입채널 분류."""
    if not channel:
        return "기타"
    ch = channel.lower()
    if any(k in ch for k in ["sns", "메타", "insta", "meta", "facebook", "fb"]):
        return "SNS(메타)"
    if any(k in ch for k in ["email", "이메일", "mail"]):
        return "이메일"
    if any(k in ch for k in ["cpc", "네이버", "naver", "검색", "search"]):
        return "CPC(네이버)"
    if any(k in ch for k in ["google_sa", "google", "구글"]):
        return "구글(SA)"
    if any(k in ch for k in ["brandthumb", "브랜드썸"]):
        return "브랜드썸"
    if any(k in ch for k in ["blog", "블로그", "youtube", "유튜브"]):
        return "블로그/유튜브"
    return channel[:10] if channel else "기타"


def _find_col(headers, *keywords):
    """헤더 리스트에서 키워드 포함 컬럼 인덱스 반환. 줄바꿈 제거 후 매칭."""
    for i, h in enumerate(headers):
        h_clean = h.replace("\n", " ")
        for kw in keywords:
            if kw in h_clean:
                return i
    return None


def _find_header_row(rows, *marker_keywords):
    """시트에서 실제 헤더 행 찾기. marker_keywords 중 하나를 포함하는 첫 번째 행 반환."""
    for ri, row in enumerate(rows[:10]):
        row_text = " ".join(str(c).replace("\n", " ") for c in row)
        for kw in marker_keywords:
            if kw in row_text:
                return ri
    return 0


def _auto_detect_date_col(headers, sample_rows):
    """날짜 컬럼 자동 감지: 헤더명 우선, 없으면 데이터 패턴으로."""
    for i, h in enumerate(headers):
        h_clean = h.replace("\n", " ")
        if any(k in h_clean for k in ['날짜', 'date', '일자', '일시', 'Date']):
            return i
    for row in sample_rows[:5]:
        for ci in range(min(len(row), 15)):
            val = str(row[ci]).strip()
            if re.match(r'^\d{1,2}/\d{1,2}$', val) or re.match(r'^\d{4}-\d{2}-\d{2}', val):
                return ci
    return None


# ===== Live Sheets Parsing (헤더 기반 자동 감지) =====
def _parse_inbound(rows):
    """인바운드 시트 파싱 — 헤더 기반 컬럼 자동 감지. 컨텍현황='워킹 중' → 유효DB."""
    now = datetime.now(KST)
    this_month_str = f"{now.year}.{now.month:02d}"

    result = {"today_inbound": 0, "today_valid": 0, "today_unhandled": 0, "today_handled": 0,
              "month_inbound": 0, "month_valid": 0, "month_unhandled": 0,
              "cumul_inbound": 0, "cumul_valid": 0, "cumul_invalid": 0,
              "channel_stats": {}, "staff_stats": {}, "source_stats": {},
              "unhandled_brands": [],
              "pipeline_items": {"인입DB": [], "유효DB": [], "미팅": [], "계약서": [], "재계약": []}}

    if not rows or len(rows) < 3:
        return result

    # 실제 헤더 행 자동 감지 (인바운드 시트: "국가"/"월"/"날짜" 포함 행)
    hdr_idx = _find_header_row(rows, "국가", "컨택현황", "컨텍현황", "담당자")
    headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
    data_rows = rows[hdr_idx + 1:]

    date_idx = _auto_detect_date_col(headers, data_rows[:5])
    contact_status_idx = _find_col(headers, "컨텍현황", "컨택현황", "consulting")
    brand_idx = _find_col(headers, "업체명", "브랜드", "상호", "brand name")
    channel_idx = _find_col(headers, "유입채널")
    staff_idx = _find_col(headers, "담당자")
    month_idx = _find_col(headers, "월")
    source_idx = _find_col(headers, "유입소재", "유입경로", "소스")

    # 폴백: 기존 하드코딩 인덱스 (파센문의 탭)
    if brand_idx is None and len(headers) > 4:
        brand_idx = 4
    if channel_idx is None and len(headers) > 9:
        channel_idx = 9
    if staff_idx is None and len(headers) > 14:
        staff_idx = 14
    if contact_status_idx is None and len(headers) > 16:
        contact_status_idx = 16
    if date_idx is None and len(headers) > 2:
        date_idx = 2
    if month_idx is None and len(headers) > 1:
        month_idx = 1

    skip_kw = ["국가", "주의사항", "본 리스트", "[ ", "*", "brand name"]
    this_year_month_prefix = f"{now.year}.{now.month:02d}"  # "2026.04"
    this_year_iso_prefix = f"{now.year}-{now.month:02d}"     # "2026-04"

    def _is_current_year_month(month_val: str, date_val: str) -> bool:
        """월 컬럼 또는 날짜 컬럼이 현재 연월(2026.04)에 해당하는지 판단."""
        if this_year_month_prefix in month_val:
            return True
        # 월 컬럼에 ISO 타임스탬프가 들어간 경우 (예: "2026-04-07 12:12:45")
        if month_val.startswith(this_year_iso_prefix):
            return True
        # 월 컬럼이 비어있을 때 날짜 컬럼으로 판단
        if not month_val and date_val and date_val.startswith(f"{now.year}-{now.month:02d}"):
            return True
        return False

    for row in data_rows:
        if not row or len(row) < 3:
            continue
        first_cell = str(row[0]).strip()
        if not first_cell or any(k in first_cell for k in skip_kw):
            continue

        def _g(idx):
            return str(row[idx]).strip() if idx is not None and idx < len(row) else ""

        date_val = _g(date_idx)
        brand = _g(brand_idx)
        channel = _g(channel_idx)
        staff = _g(staff_idx)
        status = _g(contact_status_idx)
        month_val = _g(month_idx)
        source = _g(source_idx)

        # 누적 (전체 기간, 날짜 필터 없음)
        result["cumul_inbound"] += 1
        if status in ("워킹 중", "워킹중"):
            result["cumul_valid"] += 1

        # 이번 달 판단: 월 컬럼이 현재 연월인지 확인 (연도 교차 방지)
        is_month = _is_current_year_month(month_val, date_val)
        # 오늘 판단: 날짜 매칭 AND 월이 현재 연월 (2020/4/7 등 과거 제외)
        is_today = _is_date_today(date_val, now) and is_month

        # 유효DB = 컨텍현황 "워킹중" (trim 후 비교)
        is_valid = status in ("워킹 중", "워킹중")
        is_unhandled = (not staff) or (not status)
        ch_key = _classify_channel(channel)

        card = {"name": brand, "channel": ch_key, "staff": staff or "미배정", "date": date_val,
                "source": source, "status": status if status else "미처리", "unhandled": is_unhandled}

        if is_month:
            result["month_inbound"] += 1
            result["channel_stats"][ch_key] = result["channel_stats"].get(ch_key, 0) + 1
            if source:
                result["source_stats"][source] = result["source_stats"].get(source, 0) + 1
            if staff:
                if staff not in result["staff_stats"]:
                    result["staff_stats"][staff] = {"inbound": 0, "valid": 0, "unhandled": 0}
                result["staff_stats"][staff]["inbound"] += 1
            if is_valid:
                result["month_valid"] += 1
                if staff and staff in result["staff_stats"]:
                    result["staff_stats"][staff]["valid"] += 1
                result["pipeline_items"]["유효DB"].append(card)
            else:
                result["pipeline_items"]["인입DB"].append(card)
            if is_unhandled:
                result["month_unhandled"] += 1

        if is_today:
            result["today_inbound"] += 1
            if is_valid:
                result["today_valid"] += 1
            if is_unhandled:
                result["today_unhandled"] += 1
                result["unhandled_brands"].append({"name": brand, "channel": ch_key, "source": source,
                                                    "date": date_val, "reason": "담당자 없음" if not staff else "컨택현황 미입력"})
            else:
                result["today_handled"] += 1

    result["cumul_invalid"] = result["cumul_inbound"] - result["cumul_valid"]
    return result


def _parse_contracts(rows):
    """세금계산서 시트 파싱 — 헤더 기반. 등록기준일/공급가액/공급받는자 상호."""
    now = datetime.now(KST)
    today_ymd = now.strftime("%Y%m%d")
    today_iso = now.strftime("%Y-%m-%d")
    this_ym = f"{now.year}{now.month:02d}"
    this_month_dot = f"{now.year}.{now.month:02d}"
    prev_dt = now.replace(day=1) - timedelta(days=1)
    prev_ym = f"{prev_dt.year}{prev_dt.month:02d}"
    prev_month_dot = f"{prev_dt.year}.{prev_dt.month:02d}"
    ly_ym = f"{now.year - 1}{now.month:02d}"

    result = {"today_contract": 0, "month_contract": 0, "prev_month_contract": 0,
              "last_year_contract": 0, "month_renewal": 0, "prev_month_renewal": 0,
              "today_revenue": 0, "month_revenue": 0, "prev_month_revenue": 0,
              "last_year_revenue": 0, "brands": [], "today_brands": [], "brand_list": []}

    if not rows or len(rows) < 2:
        return result

    # 실제 헤더 행 자동 감지 (계산서: "작성일자"/"공급가액"/"공급받는자" 포함 행)
    hdr_idx = _find_header_row(rows, "작성일자", "공급가액", "공급받는자")
    headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
    data_rows = rows[hdr_idx + 1:]

    date_idx = _find_col(headers, "작성일자", "등록기준일", "발행일")
    amount_idx = _find_col(headers, "공급가액")
    brand_idx = _find_col(headers, "공급받는자 상호")  # 구체적 매칭 (등록번호 제외)
    type_idx = _find_col(headers, "신규/", "재계약", "신규")
    staff_idx = _find_col(headers, "요청담당자", "담당자")
    month_idx = _find_col(headers, "작성월", "월매출")

    # 폴백 (기존 B:U 기준)
    if date_idx is None:
        date_idx = 1  # B열 = 작성일자
    if amount_idx is None and len(headers) > 19:
        amount_idx = 19  # T열 (A=0기준)
    if brand_idx is None and len(headers) > 8:
        brand_idx = 8  # I열
    if type_idx is None and len(headers) > 6:
        type_idx = 6  # G열

    brand_set = set()

    for row in data_rows:
        if not row or len(row) < 3:
            continue

        def _g(idx):
            return str(row[idx]).strip() if idx is not None and idx < len(row) else ""

        date_raw = _g(date_idx)
        revenue_raw = _g(amount_idx)
        brand = _g(brand_idx)
        ctype = _g(type_idx)
        staff = _g(staff_idx)
        month_val = _g(month_idx)

        # 금액 파싱
        try:
            revenue = int(float(revenue_raw.replace(",", "").replace("₩", "").replace(" ", ""))) if revenue_raw and revenue_raw not in ["-", ""] else 0
        except (ValueError, TypeError):
            revenue = 0
        if revenue < 0:
            revenue = 0

        # 날짜 정리
        date_clean = date_raw.replace("-", "").replace(".", "").replace("/", "").replace(" ", "")
        if len(date_clean) < 6 or not date_clean[:6].isdigit():
            continue

        if brand:
            brand_set.add(brand)

        is_today = (date_clean[:8] == today_ymd) or date_raw.startswith(today_iso)
        is_this_month = (date_clean[:6] == this_ym) or (this_month_dot in month_val)
        is_prev_month = (date_clean[:6] == prev_ym) or (prev_month_dot in month_val)
        is_last_year = date_clean[:6] == ly_ym
        is_renewal = (ctype and "신규" not in ctype and "확인필요" not in ctype and ctype != "-")

        brand_card = {"name": brand, "type": "재계약" if is_renewal else "신규",
                      "staff": staff, "date": date_raw, "revenue": revenue}

        if is_today:
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

    result["brand_list"] = sorted(brand_set)
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
async def dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
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
async def api_brand_pipeline(brand_filter: Optional[str] = Query(None)):
    """브랜드 파이프라인 (Google Sheets 연동 or 더미). 헤더 기반 자동 감지."""
    if not GSHEETS_API_KEY:
        dummy = _dummy_brand_pipeline()
        dummy["note"] = "GOOGLE_SHEETS_API_KEY 미입력"
        dummy["not_connected"] = ["광고CPA", "CS", "유효DB(컨택현황 업데이트 필요)"]
        return dummy
    try:
        inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", "파센문의", ttl_key="inbound")
        contract_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "계산서발행", ttl_key="contract")
        ib = _parse_inbound(inbound_rows) if inbound_rows else {}
        ct = _parse_contracts(contract_rows) if contract_rows else {}

        # 브랜드 필터 적용
        brands_data = ct.get("brands", [])
        today_brands_data = ct.get("today_brands", [])
        if brand_filter:
            brands_data = [b for b in brands_data if b.get("name") == brand_filter]
            today_brands_data = [b for b in today_brands_data if b.get("name") == brand_filter]
            filtered_month_revenue = sum(b["revenue"] for b in brands_data)
            filtered_today_revenue = sum(b["revenue"] for b in today_brands_data)
        else:
            filtered_month_revenue = ct.get("month_revenue", 0)
            filtered_today_revenue = ct.get("today_revenue", 0)

        return {
            "source": "live",
            "today": {
                "inbound": ib.get("today_inbound", 0),
                "valid": ib.get("today_valid", 0),
                "unhandled": ib.get("today_unhandled", 0),
                "handled": ib.get("today_handled", 0),
                "contract": ct.get("today_contract", 0),
                "revenue": filtered_today_revenue,
            },
            "month": {
                "inbound": ib.get("month_inbound", 0),
                "valid": ib.get("month_valid", 0),
                "unhandled": ib.get("month_unhandled", 0),
                "contract": ct.get("month_contract", 0),
                "revenue": filtered_month_revenue,
                "renewal": ct.get("month_renewal", 0),
            },
            "cumul": {
                "inbound": ib.get("cumul_inbound", 0),
                "valid": ib.get("cumul_valid", 0),
                "invalid": ib.get("cumul_invalid", 0),
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
            "unhandled_brands": ib.get("unhandled_brands", []),
            "brand_list": ct.get("brand_list", []),
            "today_brands": today_brands_data,
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
        rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", "현황시트(수동매칭)", ttl_key="influencer")
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
        rows = fetch_sheet(SHEET_ADS, "A1:O", "공팔리터B2B", ttl_key="ads")
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
    cumul = brand.get("cumul", {})
    return {
        "source": brand.get("source", "dummy"),
        "not_connected": brand.get("not_connected", []),
        "today": {
            "revenue": today.get("revenue", 0),
            "inbound_db": today.get("inbound", 0),
            "valid_db": today.get("valid", 0),
            "unhandled_db": today.get("unhandled", 0),
            "handled_db": today.get("handled", 0),
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
        "cumul": {
            "inbound": cumul.get("inbound", 0),
            "valid": cumul.get("valid", 0),
            "invalid": cumul.get("invalid", 0),
        },
        "prev_month": {"revenue": prev.get("revenue", 0), "contract": prev.get("contract", 0)},
        "last_year": {"revenue": ly.get("revenue", 0), "contract": ly.get("contract", 0)},
        "monthly_trend": trend,
    }


@app.get("/api/brand-comparison")
async def api_brand_comparison():
    """기간별 비교표"""
    brand = await api_brand_pipeline()
    t = brand.get("today", {})
    m = brand.get("month", {})
    p = brand.get("prev_month", {})
    ly = brand.get("last_year", {})

    def pct(cur, prev):
        return round((cur - prev) / max(prev, 1) * 100, 1) if prev else 0

    return {"comparison": [
        {"metric": "인입 DB", "today": t.get("inbound", 0), "month": m.get("inbound", 0), "prev_month": p.get("inbound", 0), "mom_pct": pct(m.get("inbound", 0), p.get("inbound", 1)), "last_year": ly.get("inbound", 0), "yoy_pct": pct(m.get("inbound", 0), ly.get("inbound", 1))},
        {"metric": "유효 DB", "today": t.get("valid", 0), "month": m.get("valid", 0), "prev_month": p.get("valid", 0), "mom_pct": pct(m.get("valid", 0), p.get("valid", 1)), "last_year": ly.get("valid", 0), "yoy_pct": pct(m.get("valid", 0), ly.get("valid", 1))},
        {"metric": "미팅", "today": t.get("meeting", 0), "month": m.get("meeting", 0), "prev_month": p.get("meeting", 0), "mom_pct": pct(m.get("meeting", 0), p.get("meeting", 1)), "last_year": ly.get("meeting", 0), "yoy_pct": pct(m.get("meeting", 0), ly.get("meeting", 1))},
        {"metric": "계약서", "today": t.get("contract", 0), "month": m.get("contract", 0), "prev_month": p.get("contract", 0), "mom_pct": pct(m.get("contract", 0), p.get("contract", 1)), "last_year": ly.get("contract", 0), "yoy_pct": pct(m.get("contract", 0), ly.get("contract", 1))},
        {"metric": "재계약", "today": t.get("renewal", 0), "month": m.get("renewal", 0), "prev_month": p.get("renewal", 0), "mom_pct": pct(m.get("renewal", 0), p.get("renewal", 1)), "last_year": ly.get("renewal", 0), "yoy_pct": pct(m.get("renewal", 0), ly.get("renewal", 1))},
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


# ===== AI Agent (Anthropic Claude — 7 Personas) =====
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

AGENT_PERSONAS = {
    "overview": {
        "name": "카일",
        "system": """당신은 공팔리터글로벌 총괄 KPI 에이전트 카일입니다.
냉철한 데이터 전략가로서 매일 KPI를 점검하고 병목을 찾아냅니다.
현재 KPI: 금일 인입DB {금일인입DB}건 / 금일 유효DB {금일유효DB}건 / 무대응 {무대응건}건 / 이번달 계약 {계약건수}건(목표 38건) / 금일매출 {당일매출}원 / 이번달매출 {이번달매출}원(목표 1.6억) / CPA {CPA}원
답변 규칙:
1) 현황분석 2) 원인진단 3) 오늘/이번주/이번달 액션 각 1가지
AT RISK 항목은 ⚠️ 강조 표시. 한국어로 답변.
사용자가 "무대응 건 처리해줘"라고 하면 무대응 리스트를 보여주고 건별 담당자 배정 제안 + 1차 응대 스크립트를 생성하세요."""
    },
    "kpi": {
        "name": "카일",
        "system": """당신은 공팔리터글로벌 총괄 KPI 에이전트 카일입니다.
냉철한 데이터 전략가로서 매일 KPI를 점검하고 병목을 찾아냅니다.
현재 KPI: 금일 인입DB {금일인입DB}건 / 금일 유효DB {금일유효DB}건 / 무대응 {무대응건}건 / 이번달 계약 {계약건수}건(목표 38건) / 금일매출 {당일매출}원 / 이번달매출 {이번달매출}원(목표 1.6억) / CPA {CPA}원
답변 규칙:
1) 현황분석 2) 원인진단 3) 오늘/이번주/이번달 액션 각 1가지
AT RISK 항목은 ⚠️ 강조 표시. 한국어.
사용자가 "무대응 건 처리해줘"라고 하면 무대응 리스트를 보여주고 건별 담당자 배정 제안 + 1차 응대 스크립트를 생성하세요."""
    },
    "brand": {
        "name": "루나",
        "system": """당신은 공팔리터글로벌 브랜드 영업 에이전트 루나입니다.
브랜드 클라이언트 관계와 파이프라인 관리 전문가입니다.
현재 KPI: 금일매출 {당일매출}원 / 이번달매출 {이번달매출}원(목표 1.6억) / 계약건수 {계약건수}건 / 평균계약단가 {계약단가}원 / 재접촉 대상 {재접촉건수}건
미처리 파이프라인과 오늘 컨텍 우선순위를 먼저 안내하세요.
사용자가 "재접촉 메시지 작성해줘" 또는 "제안서 보내줘"라고 하면:
1) 재접촉 대상 업체명/이전 컨텍 내용 기반 맞춤 제안 메시지 자동 생성
2) 이메일 / 카카오톡 / 문자 3가지 버전으로 각각 생성
답변 마지막에 반드시 '오늘/이번주/이번달 액션 각 1가지'. AT RISK 항목은 ⚠️. 한국어."""
    },
    "influencer": {
        "name": "피치",
        "system": """당신은 공팔리터글로벌 인플루언서 매칭 에이전트 피치입니다.
수백만 인플루언서 데이터를 분석해 최적 매칭을 찾는 큐레이터입니다.
현재 KPI: 인플루언서 풀 {풀수}명(목표 155만) / 국가별: {국가별현황} / 플랫폼별: {플랫폼별현황}
부족한 카테고리/국가를 진단하고 확보 전략을 제안하세요.
답변 마지막에 반드시 '오늘/이번주/이번달 액션 각 1가지'. AT RISK는 ⚠️. 한국어."""
    },
    "ads": {
        "name": "맥스",
        "system": """당신은 공팔리터글로벌 광고센터 에이전트 맥스입니다.
ROI에 집착하는 퍼포먼스 마케터입니다.
현재 KPI: CPA {CPA}원(목표 5만원 이하) / 오가닉 리드 {오가닉리드}건/일(목표 15건) / 채널별: {채널별효율}
채널별 효율 분석과 예산 재배분을 제안하세요.
답변 마지막에 반드시 '오늘/이번주/이번달 액션 각 1가지'. AT RISK는 ⚠️. 한국어."""
    },
    "sns": {
        "name": "소피",
        "system": """당신은 공팔리터글로벌 SNS 운영 에이전트 소피입니다.
공팔리터의 브랜드 목소리를 지키는 콘텐츠 전략가입니다.
현재 KPI: {채널별현황} / 이번주 콘텐츠: {이번주콘텐츠현황}
이번 주 추천 콘텐츠 주제 3가지와 성과 분석을 제공하세요.
답변 마지막에 반드시 '오늘/이번주/이번달 액션 각 1가지'. AT RISK는 ⚠️. 한국어."""
    },
    "management": {
        "name": "레이",
        "system": """당신은 공팔리터글로벌 경영지원 에이전트 레이입니다.
CEO 시간을 지키는 운영 전문가로 행정 이슈를 선제적으로 챙깁니다.
현재 현황: 미처리 세금계산서 {미처리건}건 / 입금 미확인 {미확인건}건 / 이번주 체크리스트: 세금계산서 발행, 미수금 확인, 정부지원 마감 점검
이번 주 경영지원 우선순위 체크리스트를 제공하세요.
답변 마지막에 반드시 '오늘/이번주/이번달 액션 각 1가지'. AT RISK는 ⚠️. 한국어."""
    },
    "cs": {
        "name": "하나",
        "system": """당신은 공팔리터글로벌 CS 에이전트 하나입니다.
클라이언트 만족을 최우선으로 하는 따뜻하고 신속한 전문가입니다.
현재 현황: 미응답 CS {미응답건}건 / 재계약률 {재계약률}% / 오늘 처리 우선순위: 미응답 건 즉시 배정
미처리 CS 우선순위와 응대 스크립트를 제공하세요.
답변 마지막에 반드시 '오늘/이번주/이번달 액션 각 1가지'. AT RISK는 ⚠️. 한국어."""
    },
}


async def _gather_kpi_context() -> dict:
    """실시간 KPI 데이터를 수집하여 에이전트 system prompt에 주입할 변수 딕셔너리 반환."""
    ctx = {}
    try:
        brand = await api_brand_pipeline()
        t = brand.get("today", {})
        m = brand.get("month", {})
        ctx["금일인입DB"] = t.get("inbound", 0)
        ctx["금일유효DB"] = t.get("valid", 0)
        ctx["무대응건"] = t.get("unhandled", 0)
        ctx["인입DB"] = m.get("inbound", 0)
        ctx["유효DB"] = m.get("valid", 0)
        ctx["계약건수"] = m.get("contract", 0)
        ctx["매출"] = f"{m.get('revenue', 0):,}"
        ctx["당일매출"] = f"{t.get('revenue', 0):,}"
        ctx["이번달매출"] = f"{m.get('revenue', 0):,}"
        ctx["파이프라인건수"] = m.get("inbound", 0)
        ctx["계약단가"] = f"{int(m.get('revenue', 0) / max(m.get('contract', 1), 1)):,}"
        ctx["미처리건"] = t.get("unhandled", 0)
        ctx["미확인건"] = 0
        # 재접촉 건수
        ctx["재접촉건수"] = len(brand.get("unhandled_brands", []))
    except Exception:
        pass
    try:
        inf = await api_influencer_db()
        ctx["풀수"] = f"{inf.get('total', 0):,}"
        stats = inf.get("stats", {})
        bc = stats.get("by_country", {})
        bp = stats.get("by_platform", {})
        ctx["국가별현황"] = " / ".join(f"{k}:{v}" for k, v in sorted(bc.items(), key=lambda x: -x[1])[:5])
        ctx["플랫폼별현황"] = " / ".join(f"{k}:{v}" for k, v in sorted(bp.items(), key=lambda x: -x[1])[:5])
    except Exception:
        ctx["풀수"] = "0"
        ctx["국가별현황"] = "데이터 없음"
        ctx["플랫폼별현황"] = "데이터 없음"
    try:
        ads = await api_ads_performance()
        mt = ads.get("month", {}).get("total", {})
        ctx["CPA"] = f"{mt.get('cpa', 0):,}"
        ctx["오가닉리드"] = 6
        ctx["채널별효율"] = "Meta/네이버/구글/카카오"
    except Exception:
        ctx["CPA"] = "0"
        ctx["오가닉리드"] = 0
        ctx["채널별효율"] = "데이터 없음"
    try:
        sns = await api_sns_performance()
        channels = sns.get("channels", {})
        parts = []
        for k, v in channels.items():
            f_count = v.get("followers", v.get("subscribers", 0))
            parts.append(f"{k}: {f_count:,}")
        ctx["채널별현황"] = " / ".join(parts) if parts else "데이터 없음"
        ctx["이번주콘텐츠현황"] = "릴스 2건, TikTok 1건, 뉴스레터 1건 예정"
    except Exception:
        ctx["채널별현황"] = "데이터 없음"
        ctx["이번주콘텐츠현황"] = "데이터 없음"
    ctx.setdefault("미응답건", 4)
    ctx.setdefault("재계약률", 65)
    ctx.setdefault("금일인입DB", 0)
    ctx.setdefault("금일유효DB", 0)
    ctx.setdefault("무대응건", 0)
    ctx.setdefault("재접촉건수", 0)
    return ctx


@app.post("/api/chat")
async def api_chat(request: Request):
    """AI 에이전트 채팅 — Anthropic Claude (7 페르소나). API키 없으면 룰베이스 폴백."""
    body = await request.json()
    user_msg = body.get("message", "").strip()
    page = body.get("page", "overview")
    is_briefing = body.get("briefing", False)

    if not user_msg and not is_briefing:
        return {"reply": "질문을 입력해 주세요.", "source": "system"}

    # KPI 컨텍스트 수집
    kpi = await _gather_kpi_context()

    # 페르소나 선택
    persona = AGENT_PERSONAS.get(page, AGENT_PERSONAS["overview"])
    agent_name = persona["name"]

    # system prompt에 실시간 KPI 주입
    try:
        all_keys = ["인입DB", "유효DB", "계약건수", "매출", "당일매출", "이번달매출",
             "파이프라인건수", "계약단가", "풀수", "국가별현황", "플랫폼별현황", "CPA", "오가닉리드",
             "채널별현황", "채널별효율", "이번주콘텐츠현황", "미처리건", "미확인건", "미응답건", "재계약률",
             "금일인입DB", "금일유효DB", "무대응건", "재접촉건수"]
        system_prompt = persona["system"].format(**{k: kpi.get(k, "N/A") for k in all_keys})
    except (KeyError, IndexError):
        system_prompt = persona["system"]

    if is_briefing:
        user_msg = "페이지에 처음 진입했습니다. 현재 핵심 KPI와 오늘의 우선순위를 간결하게 브리핑해주세요."

    if not ANTHROPIC_API_KEY:
        reply = _rule_based_reply(user_msg, kpi, page)
        return {"reply": reply, "source": "rule-based", "agent": agent_name}

    # Anthropic Messages API 호출
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_msg}],
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                reply = data["content"][0]["text"]
                return {"reply": reply, "source": "claude-sonnet", "agent": agent_name}
            else:
                err_detail = resp.text[:200]
                print(f"Anthropic API error {resp.status_code}: {err_detail}")
                return {"reply": _rule_based_reply(user_msg, kpi, page),
                        "source": "fallback", "agent": agent_name}
    except Exception as e:
        print(f"Anthropic API exception: {e}")
        return {"reply": _rule_based_reply(user_msg, kpi, page),
                "source": "fallback", "agent": agent_name}


def _rule_based_reply(msg: str, kpi: dict, page: str) -> str:
    """Anthropic API 키 없을 때 룰베이스 폴백"""
    persona = AGENT_PERSONAS.get(page, AGENT_PERSONAS["overview"])
    name = persona["name"]
    ctx = f"인입DB {kpi.get('인입DB', 0)}건 / 유효DB {kpi.get('유효DB', 0)}건 / 계약 {kpi.get('계약건수', 0)}건 / 매출 {kpi.get('매출', '0')}원"

    msg_lower = msg.lower() if msg else ""
    if any(k in msg_lower for k in ["현황", "요약", "상태", "보고", "브리핑", "진입"]):
        return f"[{name}] 현재 현황입니다.\n\n{ctx}\n\n📌 오늘 액션: 미처리 건 우선 대응\n📌 이번주 액션: 파이프라인 정리\n📌 이번달 액션: 목표 달성률 점검\n\nANTHROPIC_API_KEY를 설정하면 더 정확한 AI 분석을 받을 수 있습니다."
    if any(k in msg_lower for k in ["미처리", "대응", "긴급"]):
        return f"[{name}] 미처리 현황: {kpi.get('미처리건', 0)}건\n\n{ctx}\n\n📌 오늘: 미처리 건 즉시 배정\n📌 이번주: 응답 시간 10분 이내 달성\n📌 이번달: SLA 준수율 95% 목표"
    if any(k in msg_lower for k in ["매출", "계약", "실적"]):
        return f"[{name}] 매출/계약 현황\n\n{ctx}\n\n📌 오늘: 견적 발송 우선\n📌 이번주: 미팅 전환율 개선\n📌 이번달: 계약 목표 38건 달성 집중"
    return f"[{name}] {ctx}\n\n📌 오늘 액션: 핵심 미처리 건 대응\n📌 이번주 액션: 주간 리뷰 준비\n📌 이번달 액션: KPI 목표 달성 점검"


# ===== Slack Webhook =====
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

@app.post("/api/slack/test")
async def slack_test():
    """Slack 웹훅 테스트 발송"""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 미설정"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={
                "text": f"[Jacob AI] 테스트 메시지 — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            })
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/slack/kpi-report")
async def slack_kpi_report():
    """KPI 리포트 Slack 발송 (09:00 스케줄 또는 수동 트리거)"""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 미설정. .env에 추가 필요."}
    try:
        brand = await api_brand_pipeline()
        t = brand.get("today", {})
        m = brand.get("month", {})
        text = f"""📊 *[Jacob AI] 오전 KPI 리포트* — {datetime.now().strftime('%Y-%m-%d %H:%M')}

*오늘*: 인입DB {t.get('inbound',0)}건 | 유효DB {t.get('valid',0)}건 | 계약 {t.get('contract',0)}건 | 매출 {t.get('revenue',0):,}원
*이번달*: 인입DB {m.get('inbound',0)}건 | 유효DB {m.get('valid',0)}건 | 계약 {m.get('contract',0)}건 | 매출 {m.get('revenue',0):,}원
*미처리*: {t.get('unhandled',0)}건 {'⚠️ 즉시 대응 필요' if t.get('unhandled',0) > 0 else '✅ 양호'}"""

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": text})
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== SNS Performance =====
@app.get("/api/sns-performance")
async def api_sns_performance():
    """SNS 운영 현황 (향후 실데이터 연동 예정, 현재 더미)"""
    return {
        "source": "dummy",
        "note": "SNS API 연동 준비중 — Instagram/TikTok Business API 연동 예정",
        "channels": {
            "instagram": {"followers": 8420, "growth": 320, "posts": 28, "engagement": 3.8, "reach": 45000},
            "tiktok": {"followers": 12800, "growth": 680, "videos": 15, "engagement": 5.2, "avg_views": 12400},
            "youtube": {"subscribers": 2150, "growth": 185, "videos": 4, "avg_views": 3200, "watch_time": "4:30"},
            "newsletter": {"subscribers": 20000, "growth": 120, "sent": 4, "open_rate": 21, "click_rate": 3.2},
        },
        "total_followers": 43370,
        "monthly_growth": 1305,
        "today_new": 60,
        "organic_leads": {"today": 6, "month": 125, "target": 330},
    }


# ===== 재접촉 대상 추출 API =====
@app.get("/api/recontact-leads")
async def api_recontact_leads():
    """최근 6개월 유효DB 중 계약 미체결 브랜드 추출."""
    try:
        now = datetime.now(KST)
        six_months_ago = now - timedelta(days=180)
        inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", "파센문의", ttl_key="inbound")
        contract_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "계산서발행", ttl_key="contract")
        # 계약 브랜드 Set
        ct_hdr = _find_header_row(contract_rows, "작성일자", "공급가액", "공급받는자")
        ct_headers = [str(h).replace("\n", " ").strip() for h in contract_rows[ct_hdr]]
        ct_brand_idx = _find_col(ct_headers, "공급받는자 상호")
        if ct_brand_idx is None:
            ct_brand_idx = 8
        contracted = set()
        for row in contract_rows[ct_hdr + 1:]:
            if ct_brand_idx < len(row):
                b = str(row[ct_brand_idx]).strip()
                if b:
                    contracted.add(b.lower())
        # 인바운드 유효DB 중 미계약
        ib_hdr = _find_header_row(inbound_rows, "국가", "컨택현황", "컨텍현황", "담당자")
        ib_headers = [str(h).replace("\n", " ").strip() for h in inbound_rows[ib_hdr]]
        brand_idx = _find_col(ib_headers, "업체명", "브랜드") or 4
        status_idx = _find_col(ib_headers, "컨텍현황", "컨택현황") or 16
        email_idx = _find_col(ib_headers, "이메일") or 6
        contact_idx = _find_col(ib_headers, "연락처") or 5
        date_idx = 2
        month_idx = 1
        leads = []
        seen = set()
        for row in inbound_rows[ib_hdr + 1:]:
            if len(row) < 5:
                continue
            status = str(row[status_idx]).strip() if status_idx < len(row) else ""
            if status not in ("워킹 중", "워킹중"):
                continue
            brand = str(row[brand_idx]).strip() if brand_idx < len(row) else ""
            if not brand or brand.lower() in contracted or brand.lower() in seen:
                continue
            email = str(row[email_idx]).strip() if email_idx < len(row) else ""
            contact = str(row[contact_idx]).strip() if contact_idx < len(row) else ""
            date_val = str(row[date_idx]).strip() if date_idx < len(row) else ""
            month_val = str(row[month_idx]).strip() if month_idx < len(row) else ""
            seen.add(brand.lower())
            leads.append({"name": brand, "email": email, "contact": contact, "date": date_val,
                          "month": month_val, "status": status})
        return {"count": len(leads), "leads": leads[:100]}
    except Exception as e:
        return {"count": 0, "leads": [], "error": str(e)}


# ===== 무대응 건 추출 API =====
@app.get("/api/no-response-leads")
async def api_no_response_leads():
    """금일 무대응 건 (담당자 없거나 컨텍현황 미입력) 추출."""
    brand = await api_brand_pipeline()
    unhandled = brand.get("unhandled_brands", [])
    return {"count": len(unhandled), "leads": unhandled}


# ===== 이메일 발송 (Resend HTTP API) =====


def _build_pitch_html(brand_name: str, body_text: str) -> str:
    """브랜드 색상 #FF6B00 HTML 이메일 템플릿."""
    # body_text 내 줄바꿈을 <br>로 변환하되 XSS 방지
    safe_brand = brand_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_body = body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#ffffff">
<tr><td style="background:#FF6B00;padding:24px 32px">
<h1 style="margin:0;color:#ffffff;font-size:20px">공팔리터글로벌</h1>
<p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px">인플루언서 마케팅 파트너</p>
</td></tr>
<tr><td style="padding:32px">
<p style="margin:0 0 8px;color:#333;font-size:15px;font-weight:600">{safe_brand} 담당자님께</p>
<div style="margin:16px 0;color:#555;font-size:14px;line-height:1.7">{safe_body}</div>
<table cellpadding="0" cellspacing="0" style="margin:24px 0"><tr>
<td style="background:#FF6B00;border-radius:6px;padding:12px 28px">
<a href="https://08liter.com" style="color:#ffffff;text-decoration:none;font-size:14px;font-weight:600">상담 예약하기</a>
</td></tr></table>
</td></tr>
<tr><td style="background:#f9f9f9;padding:20px 32px;border-top:1px solid #eee">
<p style="margin:0;color:#999;font-size:11px">공팔리터글로벌 | luna@08liter.com | 02-000-0000</p>
<p style="margin:4px 0 0;color:#bbb;font-size:10px">본 메일은 발신 전용입니다.</p>
</td></tr></table></body></html>"""


def _send_email(to_email: str, subject: str, html: str) -> dict:
    """Resend HTTP API로 이메일 1건 발송."""
    api_key = os.getenv("RESEND_API_KEY", "")
    from_email = os.getenv("RESEND_FROM_EMAIL", "luna@08liter.com")
    sender_name = os.getenv("SENDER_NAME", "루나 (공팔리터글로벌 브랜드팀)")
    if not api_key:
        return {"status": "error", "message": "RESEND_API_KEY 미설정. Railway Variables에 추가 필요."}
    try:
        resp = req_lib.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "from": f"{sender_name} <{from_email}>",
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
            timeout=15,
        )
        data = resp.json()
        if resp.status_code == 200:
            return {"status": "ok", "to": to_email, "id": data.get("id", ""), "method": "resend"}
        return {"status": "error", "message": data.get("message", resp.text[:200]), "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/send-email")
async def api_send_email(request: Request):
    """Resend API로 이메일 1건 발송. body에 raw HTML 또는 brand_name+body_text로 템플릿 사용."""
    body = await request.json()
    to_email = body.get("to", "").strip()
    subject = body.get("subject", "").strip()
    if not to_email or not subject:
        return {"status": "error", "message": "to, subject 필수"}
    html = body.get("html", "")
    if not html:
        brand_name = body.get("brand_name", "")
        body_text = body.get("body_text", body.get("body", ""))
        html = _build_pitch_html(brand_name, body_text)
    return _send_email(to_email, subject, html)


@app.get("/api/test-email")
async def api_test_email():
    """발신 이메일로 테스트 메일 발송 (Resend API)."""
    from_email = os.getenv("RESEND_FROM_EMAIL", "luna@08liter.com")
    html = _build_pitch_html(
        "테스트",
        "안녕하세요!\n\n이 메일은 Jacob AI Command Center에서 Resend API를 통해 발송한 테스트 이메일입니다.\n"
        "이메일 연동이 정상적으로 작동하고 있습니다.\n\n"
        f"발송 시각: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} (KST)"
    )
    result = _send_email(from_email, "[Jacob AI] Resend 테스트 이메일", html)
    result["sent_to"] = from_email
    return result


@app.post("/api/campaign/recontact")
async def api_campaign_recontact(request: Request):
    """루나 재접촉 캠페인 실행: 미계약 유효DB에 맞춤 이메일 발송."""
    body = await request.json()
    dry_run = body.get("dry_run", True)  # 기본 미리보기 모드
    limit = min(body.get("limit", 10), 50)

    # 1. 재접촉 대상 추출
    leads_data = await api_recontact_leads()
    leads = leads_data.get("leads", [])
    if not leads:
        return {"status": "no_leads", "message": "재접촉 대상이 없습니다.", "count": 0}

    targets = [l for l in leads if l.get("email") and "@" in l.get("email", "")][:limit]
    if not targets:
        return {"status": "no_email", "message": f"재접촉 대상 {len(leads)}건 중 이메일 보유 건이 없습니다.", "count": len(leads)}

    # 2. 맞춤 메시지 생성 (Anthropic API)
    results = []
    for lead in targets:
        brand_name = lead["name"]
        pitch_body = (
            f"안녕하세요, 공팔리터글로벌 브랜드 파트너십 팀 루나입니다.\n\n"
            f"지난번 {brand_name} 관련 문의를 주셨을 때 좋은 대화를 나눴었는데요,\n"
            f"이후 진행 상황이 궁금하여 다시 연락드립니다.\n\n"
            f"최근 저희는 인플루언서 마케팅 분야에서 새로운 성과를 거두고 있으며,\n"
            f"{brand_name}에 최적화된 캠페인 전략을 준비했습니다.\n\n"
            f"편하신 시간에 15분만 투자해 주시면 맞춤 제안을 드리겠습니다.\n"
            f"아래 버튼을 클릭하시면 바로 상담 예약이 가능합니다.\n\n"
            f"감사합니다.\n루나 드림"
        )
        subject = f"[공팔리터글로벌] {brand_name} 맞춤 인플루언서 마케팅 제안"
        html = _build_pitch_html(brand_name, pitch_body)

        entry = {
            "brand": brand_name,
            "email": lead["email"],
            "subject": subject,
            "preview": pitch_body[:100] + "...",
        }

        if dry_run:
            entry["status"] = "preview"
        else:
            send_result = _send_email(lead["email"], subject, html)
            entry["status"] = send_result["status"]
            entry["detail"] = send_result.get("message", "")

        results.append(entry)

    sent = sum(1 for r in results if r["status"] == "ok")
    return {
        "status": "ok",
        "dry_run": dry_run,
        "total_leads": len(leads),
        "targeted": len(targets),
        "sent": sent,
        "results": results,
    }


@app.get("/api/cache-clear")
async def api_cache_clear():
    """캐시 초기화"""
    _cache.clear()
    _cache_time.clear()
    return {"status": "cleared"}


@app.get("/api/debug-env")
async def api_debug_env():
    """환경변수 로딩 상태 디버그. 값은 마스킹 처리."""
    keys = [
        "RESEND_API_KEY", "RESEND_FROM_EMAIL",
        "ANTHROPIC_API_KEY", "GOOGLE_SHEETS_API_KEY",
        "NAVER_WORKS_SMTP_PASSWORD", "SENDER_NAME",
        "SLACK_WEBHOOK_URL", "DASH_USER",
    ]
    result = {}
    for k in keys:
        val = os.environ.get(k)
        if val is None:
            result[k] = "NOT_IN_OS_ENVIRON"
        elif val == "":
            result[k] = "EMPTY_STRING"
        else:
            result[k] = f"SET({len(val)}chars):{val[:4]}***"
    # .env 파일 존재 여부
    env_path = Path(__file__).parent / ".env"
    result["_dotenv_file_exists"] = env_path.exists()
    if env_path.exists():
        env_text = env_path.read_text()
        result["_dotenv_has_RESEND_API_KEY"] = "RESEND_API_KEY" in env_text
    return result


if __name__ == "__main__":
    import uvicorn
    print("Jacob AI Command Center -> http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
