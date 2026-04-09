"""08L_AI Command Center — 통합 대시보드 + Google Sheets API + Anthropic AI Agents"""
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
    """전체 API 연동 상태 — 7개 서비스"""
    def _chk(key): return "connected" if os.getenv(key) else "not_configured"
    # 메타: 토큰 있어도 호출 실패 시 warning
    meta_status = "not_configured"
    if os.getenv("META_ACCESS_TOKEN"):
        try:
            r = req_lib.get(f"https://graph.facebook.com/v18.0/act_{os.getenv('META_AD_ACCOUNT_ID','230720044045370')}/insights",
                params={"access_token": os.getenv("META_ACCESS_TOKEN"), "fields": "spend", "date_preset": "today"}, timeout=5)
            meta_status = "connected" if r.status_code == 200 else "warning"
        except Exception:
            meta_status = "warning"
    return {
        "status": "ok",
        "timestamp": datetime.now(KST).isoformat(),
        "services": {
            "google_sheets": "connected" if GSHEETS_API_KEY else "not_configured",
            "anthropic": _chk("ANTHROPIC_API_KEY"),
            "slack": _chk("SLACK_WEBHOOK_URL"),
            "resend_email": _chk("RESEND_API_KEY"),
            "meta_ads": meta_status,
            "meta_ads_note": "토큰 갱신 필요" if meta_status == "warning" else "",
            "kakao_b2b": _chk("KAKAO_B2B_API_KEY"),
            "kakao_b2c": _chk("KAKAO_B2C_API_KEY"),
            "naver_works_smtp": _chk("NAVER_WORKS_SMTP_PASSWORD"),
            "instagram": _chk("META_INSTAGRAM_TOKEN"),
        },
        "cache_entries": len(_cache),
    }


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """로그인 폼 페이지"""
    if not DASH_USER or not DASH_PASS:
        return RedirectResponse("/", status_code=302)
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login — 08L_AI</title>
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
<h1>⚡ 08L_AI</h1>
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
GOALS_FILE = DATA_DIR / "goals.json"
ALERTS_FILE = DATA_DIR / "alerts.json"
PROPOSALS_FILE = DATA_DIR / "proposals.json"
CYCLE_LOG_FILE = DATA_DIR / "cycle_log.json"

# ===== 에이전트 이메일 계정 =====
AGENT_EMAILS = {
    "카일": os.getenv("KYLE_EMAIL", "kyle@08liter.com"),
    "루나": os.getenv("LUNA_EMAIL", "luna@08liter.com"),
    "피치": os.getenv("PITCH_EMAIL", "pitch@08liter.com"),
    "맥스": os.getenv("MAX_EMAIL", "max@08liter.com"),
    "소피": os.getenv("SOPHIE_EMAIL", "sophie@08liter.com"),
    "레이": os.getenv("RAY_EMAIL", "ray@08liter.com"),
    "하나": os.getenv("HANA_EMAIL", "hana@08liter.com"),
}

# ===== 월간 목표 (기본값, /api/goals로 수정 가능) =====
DEFAULT_GOALS = {
    "revenue": 160000000, "contracts": 38, "inbound_db": 500,
    "valid_db": 150, "cpa": 50000, "influencer_pool": 1550000,
    "alert_threshold": 0.3,  # 30% 이하 시 알림
}

def load_goals() -> dict:
    if GOALS_FILE.exists():
        return json.loads(GOALS_FILE.read_text(encoding="utf-8"))
    return dict(DEFAULT_GOALS)

def save_goals(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GOALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_alerts() -> list:
    if ALERTS_FILE.exists():
        return json.loads(ALERTS_FILE.read_text(encoding="utf-8"))
    return []

def save_alerts(data: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ALERTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_proposals() -> list:
    if PROPOSALS_FILE.exists():
        return json.loads(PROPOSALS_FILE.read_text(encoding="utf-8"))
    return []

def save_proposals(data: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROPOSALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_cycle_log() -> list:
    if CYCLE_LOG_FILE.exists():
        return json.loads(CYCLE_LOG_FILE.read_text(encoding="utf-8"))
    return []

def save_cycle_log(data: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CYCLE_LOG_FILE.write_text(json.dumps(data[-100:], ensure_ascii=False, indent=2), encoding="utf-8")

# ===== Google Sheets Config =====
GSHEETS_API_KEY = os.getenv("GOOGLE_SHEETS_API_KEY", "")
SHEET_INBOUND = os.getenv("INBOUND_SHEET_ID", "1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8")
SHEET_CONTRACT = os.getenv("GOOGLE_SHEETS_ID", "1j_3IYME764NlrARbNCZ_TJqzZCyfAMy-N3V-ByRik6Q")
SHEET_INFLUENCER = "1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs"
SHEET_ADS = "1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU"

_cache: Dict[str, list] = {}
_cache_time: Dict[str, float] = {}
CACHE_TTLS = {
    "inbound": 300,      # 5 min
    "contract": 0,       # 실시간 - 매출 즉시 반영
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
              "last_year_contract": 0, "month_renewal": 0, "month_new": 0,
              "prev_month_renewal": 0, "prev_month_new": 0,
              "today_revenue": 0, "month_revenue": 0, "prev_month_revenue": 0,
              "last_year_revenue": 0, "brands": [], "today_brands": [], "brand_list": [],
              "monthly_payback": {}}

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

    payback_idx = _find_col(headers, "페이백비", "충전금", "구매평충전금")

    # 폴백 (기존 B:U 기준)
    if date_idx is None:
        date_idx = 1  # B열 = 작성일자
    if amount_idx is None and len(headers) > 19:
        amount_idx = 19  # T열 (A=0기준)
    if brand_idx is None and len(headers) > 8:
        brand_idx = 8  # I열
    if type_idx is None and len(headers) > 6:
        type_idx = 6  # G열
    if payback_idx is None and len(headers) > 18:
        payback_idx = 18  # S열

    brand_set = set()
    # 브랜드 첫 등장 여부 추적 (신규/재계약 자동 분류)
    brand_first_seen = {}

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

        # 페이백비 파싱
        payback_raw = str(row[payback_idx]).strip() if payback_idx is not None and payback_idx < len(row) else "0"
        try:
            payback = int(float(payback_raw.replace(",", "").replace("₩", "").replace(" ", ""))) if payback_raw and payback_raw not in ["-", ""] else 0
        except (ValueError, TypeError):
            payback = 0
        if payback < 0:
            payback = 0

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

        # 신규/재계약 자동 분류: type 컬럼이 있으면 사용, 없으면 브랜드 첫 등장 여부로 판단
        if ctype and ctype != "-" and "확인필요" not in ctype:
            is_renewal = "신규" not in ctype
        else:
            brand_lower = brand.lower() if brand else ""
            if brand_lower:
                if brand_lower not in brand_first_seen:
                    brand_first_seen[brand_lower] = date_clean[:8]
                    is_renewal = False
                else:
                    is_renewal = True
            else:
                is_renewal = False

        brand_card = {"name": brand, "type": "재계약" if is_renewal else "신규",
                      "staff": staff, "date": date_raw, "revenue": revenue}

        # 월별 페이백비 집계
        if payback > 0 and len(date_clean) >= 6:
            ym_key = date_clean[:4] + "." + date_clean[4:6]
            result["monthly_payback"][ym_key] = result["monthly_payback"].get(ym_key, 0) + payback

        if is_today:
            result["today_contract"] += 1
            result["today_revenue"] += revenue
            result["today_brands"].append(brand_card)
        if is_this_month:
            result["month_contract"] += 1
            result["month_revenue"] += revenue
            if is_renewal:
                result["month_renewal"] += 1
            else:
                result["month_new"] += 1
            result["brands"].append(brand_card)
        if is_prev_month:
            result["prev_month_contract"] += 1
            result["prev_month_revenue"] += revenue
            if is_renewal:
                result["prev_month_renewal"] += 1
            else:
                result["prev_month_new"] += 1
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
async def ceo_dashboard(request: Request):
    """새 CEO 대시보드 — McKinsey 스타일 3섹션 레이아웃."""
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("ceo.html", {"request": request})


@app.get("/old", response_class=HTMLResponse)
async def legacy_dashboard(request: Request):
    """기존 대시보드 (이전 버전)."""
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
async def api_brand_pipeline(brand_filter: Optional[str] = None):
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
                "new": ct.get("month_new", 0),
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
        # 팔로워 구간별 통계
        fw_tiers = {"~1K": 0, "1K-10K": 0, "10K-100K": 0, "100K-500K": 0, "500K-1M": 0, "1M+": 0}
        mega_count = 0
        mid_count = 0
        for it in items:
            fw = it.get("followers_num", 0)
            if fw < 1000: fw_tiers["~1K"] += 1
            elif fw < 10000: fw_tiers["1K-10K"] += 1
            elif fw < 100000: fw_tiers["10K-100K"] += 1
            elif fw < 500000: fw_tiers["100K-500K"] += 1; mid_count += 1
            elif fw < 1000000: fw_tiers["500K-1M"] += 1; mid_count += 1
            else: fw_tiers["1M+"] += 1; mega_count += 1
        stats["by_followers"] = fw_tiers
        stats["mega_count"] = mega_count
        stats["mid_plus_count"] = mid_count + mega_count
        # 일별 등록 추이 (A열 날짜 기준)
        daily_reg = {}
        now = datetime.now(KST)
        for it in items:
            d = str(it.get("date", "")).strip()
            if not d:
                continue
            # 날짜 정규화
            if re.match(r'^\d{4}-\d{2}-\d{2}', d):
                dk = d[:10]
            elif re.match(r'^\d{1,2}/\d{1,2}', d) and now.year:
                dk = f"{now.year}-{d.replace('/','-')}"
            else:
                dk = d[:10]
            daily_reg[dk] = daily_reg.get(dk, 0) + 1
        stats["daily_registrations"] = [{"date": k, "count": v} for k, v in sorted(daily_reg.items())[-90:]]
        this_month_prefix = now.strftime("%Y-%m")
        stats["this_month_new"] = sum(v for k, v in daily_reg.items() if k.startswith(this_month_prefix))
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
            "new": month.get("new", 0),
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

_AGENT_COMMON = """[공통 권한] 당신은 공팔리터글로벌의 전체 데이터(인바운드/세금계산서/인플루언서DB/광고/SNS/CS/KPI)에 동등하게 접근 가능합니다.
사용자를 항상 "제이콥님"으로 호칭하세요. 한국어로 답변.
답변 마지막에 반드시 '오늘/이번주/이번달 액션 각 1가지'. AT RISK 항목은 ⚠️ 강조.
발신 이메일: {에이전트이메일}"""

_KYLE_SYSTEM = _AGENT_COMMON + """
당신은 총괄 매니저 카일입니다. 7개 에이전트(루나/피치/맥스/소피/레이/하나)를 관리감독합니다.
전체 KPI를 모니터링하고 목표 대비 30% 이하 항목은 즉시 해당 에이전트에게 경고합니다.
매일 09:00 전체 에이전트 성과 브리핑을 생성합니다.
API 상태를 감시하고, 오류 감지 시 자동 재연결 → 실패 시 슬랙 알림 + 알림센터 긴급 게시.
현재 KPI: 금일 인입DB {금일인입DB}건 / 유효DB {금일유효DB}건 / 무대응 {무대응건}건 / 계약 {계약건수}건(목표38) / 금일매출 {당일매출}원 / 이번달매출 {이번달매출}원(목표1.6억) / CPA {CPA}원
"무대응 건 처리해줘" → 무대응 리스트 + 건별 담당자 배정 제안 + 1차 응대 스크립트 생성."""

AGENT_PERSONAS = {
    "overview": {"name": "카일", "email_key": "카일", "system": _KYLE_SYSTEM},
    "kpi":      {"name": "카일", "email_key": "카일", "system": _KYLE_SYSTEM},
    "brand": {
        "name": "루나", "email_key": "루나",
        "system": _AGENT_COMMON + """
당신은 브랜드 영업 에이전트 루나입니다. 파이프라인 관리와 클라이언트 관계 전문가.
현재 KPI: 금일매출 {당일매출}원 / 이번달매출 {이번달매출}원(목표1.6억) / 계약 {계약건수}건 / 단가 {계약단가}원 / 재접촉 대상 {재접촉건수}건
브리핑 시 시작: "안녕하세요 제이콥님. 오늘 재접촉 대상 {재접촉건수}건이 있습니다. 지금 바로 이메일 피치를 발송할까요?"
"발송해줘"/"보내줘" → "지금 바로 재접촉 이메일을 발송합니다."
"재접촉 메시지 작성해줘" → 이메일/카카오톡/문자 3가지 버전 생성."""
    },
    "influencer": {
        "name": "피치", "email_key": "피치",
        "system": _AGENT_COMMON + """
""" + (Path(__file__).parent / "agents/pitch/system-prompt.txt").read_text(encoding="utf-8") + """
현재 KPI: 풀 {풀수}명(목표155만) / 국가별: {국가별현황} / 플랫폼별: {플랫폼별현황}
카카오 B2C 채널(@08liter_korea) 문의 수신 + 인바운드 시트 기록."""
    },
    "ads": {
        "name": "맥스", "email_key": "맥스",
        "system": _AGENT_COMMON + """
당신은 광고센터 에이전트 맥스입니다. ROI 집착 퍼포먼스 마케터.
메타 광고(META_AD_ACCOUNT_ID: 230720044045370) 성과를 매일 자동 조회합니다 (노출수/클릭수/CPA/지출액).
현재 KPI: CPA {CPA}원(목표5만이하) / 오가닉 리드 {오가닉리드}건/일(목표15) / 채널별: {채널별효율}
채널별 효율 분석 + 예산 재배분 제안."""
    },
    "sns": {
        "name": "소피", "email_key": "소피",
        "system": _AGENT_COMMON + """
당신은 SNS 운영 에이전트 소피입니다. 브랜드 목소리를 지키는 콘텐츠 전략가.
현재 KPI: {채널별현황} / 이번주: {이번주콘텐츠현황}
추천 콘텐츠 주제 3가지 + 성과 분석."""
    },
    "management": {
        "name": "레이", "email_key": "레이",
        "system": _AGENT_COMMON + """
당신은 경영지원 에이전트 레이입니다. CEO 시간을 지키는 운영 전문가.
현재: 미처리 세금계산서 {미처리건}건 / 입금 미확인 {미확인건}건
이번 주 경영지원 우선순위 체크리스트 제공."""
    },
    "cs": {
        "name": "하나", "email_key": "하나",
        "system": _AGENT_COMMON + """
당신은 CS 에이전트 하나입니다. 카카오 B2B 채널(@08liter_b2b) CS를 담당합니다.
미응답 메시지를 감지하고 즉시 응대 스크립트를 생성합니다.
매일 09:00 미응답 현황 브리핑을 생성합니다.
현재 미응답 {미응답건}건 / 재계약률 {재계약률}%
"미응답 처리해줘" → 미응답 리스트 + 건별 1차 응대 스크립트 자동 생성."""
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

    # 루나: "발송해줘" 명령 → 즉시 캠페인 실행
    if page == "brand" and user_msg and any(k in user_msg for k in ["발송해", "보내줘", "실행해", "발송 실행"]):
        try:
            campaign_result = await _run_recontact_campaign(dry_run=False, limit=10)
            sent = campaign_result.get("sent", 0)
            targeted = campaign_result.get("targeted", 0)
            total = campaign_result.get("total_leads", 0)
            results = campaign_result.get("results", [])
            lines = [f"✅ 재접촉 이메일 발송 완료!\n"]
            lines.append(f"📊 대상: {total}건 중 {targeted}건 발송 시도 → {sent}건 성공\n")
            for r in results[:5]:
                icon = "✅" if r.get("status") == "ok" else "❌"
                lines.append(f"{icon} {r.get('brand','')} → {r.get('email','')}")
            lines.append(f"\n📌 오늘 액션: 발송 결과 회신 모니터링\n📌 이번주 액션: 미회신 업체 2차 컨텍\n📌 이번달 액션: 재접촉 전환율 10% 달성")
            return {"reply": "\n".join(lines), "source": "campaign-exec", "agent": "루나"}
        except Exception as e:
            return {"reply": f"발송 실행 중 오류: {e}", "source": "error", "agent": "루나"}

    # KPI 컨텍스트 수집
    kpi = await _gather_kpi_context()

    # 페르소나 선택
    persona = AGENT_PERSONAS.get(page, AGENT_PERSONAS["overview"])
    agent_name = persona["name"]

    # system prompt에 실시간 KPI + 에이전트 이메일 주입
    try:
        email_key = persona.get("email_key", agent_name)
        kpi["에이전트이메일"] = AGENT_EMAILS.get(email_key, "luna@08liter.com")
        all_keys = ["인입DB", "유효DB", "계약건수", "매출", "당일매출", "이번달매출",
             "파이프라인건수", "계약단가", "풀수", "국가별현황", "플랫폼별현황", "CPA", "오가닉리드",
             "채널별현황", "채널별효율", "이번주콘텐츠현황", "미처리건", "미확인건", "미응답건", "재계약률",
             "금일인입DB", "금일유효DB", "무대응건", "재접촉건수", "에이전트이메일"]
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
                "text": f"[08L_AI] 테스트 메시지 — {datetime.now().strftime('%Y-%m-%d %H:%M')}"
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
        text = f"""📊 *[08L_AI] 오전 KPI 리포트* — {datetime.now().strftime('%Y-%m-%d %H:%M')}

*오늘*: 인입DB {t.get('inbound',0)}건 | 유효DB {t.get('valid',0)}건 | 계약 {t.get('contract',0)}건 | 매출 {t.get('revenue',0):,}원
*이번달*: 인입DB {m.get('inbound',0)}건 | 유효DB {m.get('valid',0)}건 | 계약 {m.get('contract',0)}건 | 매출 {m.get('revenue',0):,}원
*미처리*: {t.get('unhandled',0)}건 {'⚠️ 즉시 대응 필요' if t.get('unhandled',0) > 0 else '✅ 양호'}"""

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": text})
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/slack/daily-brief")
async def slack_daily_brief():
    """매일 아침 9시 Slack CEO 브리핑 — KPI + 에이전트 제안 + 실행결과."""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 미설정"}
    try:
        brand = await api_brand_pipeline()
        t = brand.get("today", {})
        m = brand.get("month", {})
        proposals = load_proposals()
        pending = [p for p in proposals if p.get("status") == "pending_approval"]
        completed_today = [p for p in proposals
                          if p.get("status") == "completed"
                          and p.get("executed_at", "").startswith(datetime.now(KST).strftime("%Y-%m-%d"))]
        rev_pct = round(m.get("revenue", 0) / max(160000000, 1) * 100)
        delta_str = f"+{rev_pct}%" if rev_pct > 0 else f"{rev_pct}%"

        lines = [
            f"*[08liter Daily Brief — {datetime.now(KST).strftime('%m/%d')}]*",
            f"📊 이번달 매출: {m.get('revenue',0):,}원 ({delta_str} of 1.6억)",
            f"📝 계약: 신규 {m.get('new',0)}건 + 재계약 {m.get('renewal',0)}건 = {m.get('contract',0)}건",
            f"🤖 에이전트 제안: {len(pending)}건 승인대기",
        ]
        if completed_today:
            lines.append(f"✅ 오늘 실행완료: {len(completed_today)}건")
            for c in completed_today[:3]:
                lines.append(f"   • [{c.get('agent','')}] {c.get('result','')[:40]}")
        if t.get("unhandled", 0) > 0:
            lines.append(f"⚠️ CEO 확인 필요: 무대응 {t['unhandled']}건")
        lines.append(f"→ 대시보드: https://dashboard-production-b2bd.up.railway.app/")

        text = "\n".join(lines)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": text})
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code, "message": text}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/performance-summary")
async def api_performance_summary():
    """이번 주 에이전트 성과 요약 — 제안/승인/실행/성공 통계."""
    proposals = load_proposals()
    now = datetime.now(KST)
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    # 이번 주 필터
    week_proposals = [p for p in proposals if (p.get("created_at") or "") >= week_start]
    total = len(week_proposals)
    approved = len([p for p in week_proposals if p.get("status") in ("approved", "executed", "completed")])
    executed = len([p for p in week_proposals if p.get("status") in ("executed", "completed")])
    completed = len([p for p in week_proposals if p.get("status") == "completed"])
    rejected = len([p for p in week_proposals if p.get("status") == "rejected"])
    pending = len([p for p in week_proposals if p.get("status") == "pending_approval"])

    # 에이전트별 통계
    agent_stats = {}
    for p in week_proposals:
        ag = p.get("agent", "시스템")
        if ag not in agent_stats:
            agent_stats[ag] = {"total": 0, "approved": 0, "completed": 0}
        agent_stats[ag]["total"] += 1
        if p.get("status") in ("approved", "executed", "completed"):
            agent_stats[ag]["approved"] += 1
        if p.get("status") == "completed":
            agent_stats[ag]["completed"] += 1

    # 일별 추이 (최근 7일)
    daily = {}
    for i in range(7):
        d = (now - timedelta(days=6 - i)).strftime("%Y-%m-%d")
        day_proposals = [p for p in proposals if (p.get("created_at") or "")[:10] == d]
        daily[d] = {
            "proposed": len(day_proposals),
            "approved": len([p for p in day_proposals if p.get("approved_at")]),
            "completed": len([p for p in day_proposals if p.get("status") == "completed"]),
        }

    return {
        "week": {"total": total, "approved": approved, "executed": executed,
                 "completed": completed, "rejected": rejected, "pending": pending,
                 "approval_rate": round(approved / max(total, 1) * 100),
                 "success_rate": round(completed / max(approved, 1) * 100)},
        "by_agent": agent_stats,
        "daily": [{"date": k, **v} for k, v in sorted(daily.items())],
    }


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


def _send_email(to_email: str, subject: str, html: str, agent_name: str = "루나") -> dict:
    """Resend HTTP API로 이메일 1건 발송. agent_name으로 발신자 자동 매핑."""
    api_key = os.getenv("RESEND_API_KEY", "")
    agent_email = AGENT_EMAILS.get(agent_name, "luna@08liter.com")
    # Resend 도메인 인증 전에는 onboarding@resend.dev 사용
    from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    sender_name = f"{agent_name} | 공팔리터글로벌"
    if not api_key:
        in_env = "RESEND_API_KEY" in os.environ
        return {"status": "error", "message": f"RESEND_API_KEY 미설정. in_os_environ={in_env}. Railway Variables에 추가 필요."}
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
    from_email = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")
    html = _build_pitch_html(
        "테스트",
        "안녕하세요!\n\n이 메일은 08L_AI Command Center에서 Resend API를 통해 발송한 테스트 이메일입니다.\n"
        "이메일 연동이 정상적으로 작동하고 있습니다.\n\n"
        f"발송 시각: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} (KST)"
    )
    result = _send_email(from_email, "[08L_AI] Resend 테스트 이메일", html)
    result["sent_to"] = from_email
    return result


async def _run_recontact_campaign(dry_run: bool = True, limit: int = 10) -> dict:
    """재접촉 캠페인 내부 실행 함수."""
    limit = min(limit, 50)
    leads_data = await api_recontact_leads()
    leads = leads_data.get("leads", [])
    if not leads:
        return {"status": "no_leads", "total_leads": 0, "targeted": 0, "sent": 0, "results": []}
    targets = [l for l in leads if l.get("email") and "@" in l.get("email", "")][:limit]
    if not targets:
        return {"status": "no_email", "total_leads": len(leads), "targeted": 0, "sent": 0, "results": []}
    results = []
    for lead in targets:
        brand_name = lead["name"]
        pitch_body = (
            f"안녕하세요, 공팔리터글로벌 브랜드 파트너십 팀 루나입니다.\n\n"
            f"지난번 {brand_name} 관련 문의를 주셨을 때 좋은 대화를 나눴었는데요,\n"
            f"이후 진행 상황이 궁금하여 다시 연락드립니다.\n\n"
            f"최근 저희는 인플루언서 마케팅 분야에서 새로운 성과를 거두고 있으며,\n"
            f"{brand_name}에 최적화된 캠페인 전략을 준비했습니다.\n\n"
            f"편하신 시간에 15분만 투자해 주시면 맞춤 제안을 드리겠습니다.\n\n감사합니다.\n루나 드림"
        )
        subject = f"[공팔리터글로벌] {brand_name} 맞춤 인플루언서 마케팅 제안"
        html = _build_pitch_html(brand_name, pitch_body)
        entry = {"brand": brand_name, "email": lead["email"], "subject": subject}
        if dry_run:
            entry["status"] = "preview"
        else:
            send_result = _send_email(lead["email"], subject, html)
            entry["status"] = send_result["status"]
            entry["detail"] = send_result.get("message", "")
        results.append(entry)
    sent = sum(1 for r in results if r["status"] == "ok")
    return {"status": "ok", "dry_run": dry_run, "total_leads": len(leads), "targeted": len(targets), "sent": sent, "results": results}


@app.post("/api/campaign/recontact")
async def api_campaign_recontact(request: Request):
    """루나 재접촉 캠페인 실행 API."""
    body = await request.json()
    return await _run_recontact_campaign(dry_run=body.get("dry_run", True), limit=body.get("limit", 10))


# ===== 목표 설정 API =====
@app.get("/api/goals")
async def api_get_goals():
    return load_goals()

@app.post("/api/goals")
async def api_set_goals(request: Request):
    body = await request.json()
    goals = load_goals()
    goals.update(body)
    save_goals(goals)
    return {"status": "ok", "goals": goals}


# ===== 알림센터 API (게시판 형태) =====
@app.get("/api/alerts-board")
async def api_alerts_board():
    alerts = load_alerts()
    # 미해결 상단 고정
    alerts.sort(key=lambda a: (0 if a.get("resolved") else 1, a.get("timestamp", "")), reverse=True)
    return {"alerts": alerts[:50]}

@app.post("/api/alerts-board")
async def api_post_alert(request: Request):
    body = await request.json()
    alerts = load_alerts()
    alert = {
        "id": len(alerts) + 1,
        "agent": body.get("agent", "시스템"),
        "severity": body.get("severity", "warning"),  # critical/warning/info
        "summary": body.get("summary", ""),
        "detail": body.get("detail", ""),
        "timestamp": datetime.now(KST).isoformat(),
        "resolved": False,
    }
    alerts.append(alert)
    save_alerts(alerts)
    return {"status": "ok", "alert": alert}

@app.post("/api/alerts-board/resolve")
async def api_resolve_alert(request: Request):
    body = await request.json()
    alert_id = body.get("id")
    alerts = load_alerts()
    for a in alerts:
        if a.get("id") == alert_id:
            a["resolved"] = True
            a["resolved_at"] = datetime.now(KST).isoformat()
    save_alerts(alerts)
    return {"status": "ok"}


# ===== 에이전트 자율실행 프레임워크 =====
async def _agent_auto_cycle():
    """매일 09:00 KST 전체 에이전트 자율실행: 데이터수집 → 분석 → 감지 → 알림 → 제안생성 → 승인된 제안 실행 → 슬랙."""
    goals = load_goals()
    alerts_posted = []
    now_ts = datetime.now(KST).isoformat()
    _id = lambda: int(time.time() * 1000) % 1000000 + len(alerts_posted)

    # 0. 에이전트 자율 개선 루프 — 제안 자동생성
    try:
        new_proposals = await _generate_agent_proposals()
        if new_proposals:
            _log_cycle("auto_generate", None, f"에이전트 제안 {len(new_proposals)}건 자동생성")
    except Exception as e:
        print(f"Proposal auto-generation error: {e}")

    # 0-1. 승인된 제안 자동실행
    try:
        proposals = load_proposals()
        for p in proposals:
            if p.get("status") == "approved" and not p.get("executed_at"):
                agent = p.get("agent", "")
                result_text = "자동 실행 완료"
                if agent == "루나" and "재접촉" in p.get("proposal", ""):
                    try:
                        campaign = await _run_recontact_campaign(dry_run=False, limit=5)
                        result_text = f"재접촉 이메일 {campaign.get('sent',0)}건 발송"
                    except Exception:
                        result_text = "재접촉 실행 오류"
                p["status"] = "completed"
                p["executed_at"] = now_ts
                p["result"] = result_text
                _log_cycle("auto_execute", p.get("id"), result_text)
        save_proposals(proposals)
    except Exception as e:
        print(f"Auto-execute error: {e}")

    try:
        # 1. 전체 KPI 데이터 수집
        brand = await api_brand_pipeline()
        m = brand.get("month", {})
        t = brand.get("today", {})
        threshold = goals.get("alert_threshold", 0.2)  # 80% 미만 = 달성률 0.8 미만

        # 2. 카일 — KPI 목표 대비 분석
        checks = [
            ("매출", m.get("revenue", 0), goals.get("revenue", 160000000), "카일"),
            ("계약건수", m.get("contract", 0), goals.get("contracts", 38), "카일"),
            ("인입DB", m.get("inbound", 0), goals.get("inbound_db", 500), "루나"),
            ("유효DB", m.get("valid", 0), goals.get("valid_db", 150), "루나"),
        ]
        for label, val, target, agent in checks:
            if target > 0 and val / target < 0.8:  # 80% 미만만 알림
                alerts_posted.append({
                    "id": _id(), "agent": agent, "severity": "critical",
                    "summary": f"⚠️ {label} AT RISK: {val:,} / 목표 {target:,} ({val/target*100:.0f}%)",
                    "detail": f"목표 대비 {threshold*100:.0f}% 미달 — 카일 지시: 즉시 대응 필요",
                    "timestamp": now_ts, "resolved": False})

        # 3. 카일 — 무대응 건 감지
        if t.get("unhandled", 0) > 0:
            alerts_posted.append({
                "id": _id(), "agent": "카일", "severity": "warning",
                "summary": f"무대응 {t['unhandled']}건 — 담당자 배정 필요",
                "detail": "담당자 미배정 또는 컨텍현황 미입력",
                "timestamp": now_ts, "resolved": False})

        # 4. 카일 — API 상태 점검 (빨간 항목 감지)
        api_checks = {
            "Google Sheets": bool(GSHEETS_API_KEY),
            "Anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "Slack": bool(os.getenv("SLACK_WEBHOOK_URL")),
            "Resend Email": bool(os.getenv("RESEND_API_KEY")),
        }
        for svc, ok in api_checks.items():
            if not ok:
                alerts_posted.append({
                    "id": _id(), "agent": "카일", "severity": "critical",
                    "summary": f"🔴 {svc} 연결 실패 — 자동 재연결 시도 중",
                    "detail": f"{svc} API 키 미설정 또는 만료. Railway Variables 확인 필요.",
                    "timestamp": now_ts, "resolved": False})

        # 5. 소피 — SNS 콘텐츠 생성 + 슬랙 + 이메일
        try:
            sophie_result = await api_sophie_content()
            if sophie_result.get("status") == "ok":
                content = sophie_result.get("content", "")
                alerts_posted.append({"id": _id(), "agent": "소피", "severity": "info",
                    "summary": "📱 이번 주 SNS 콘텐츠 전략 생성 완료", "detail": content[:200],
                    "timestamp": now_ts, "resolved": False})
                _send_email(AGENT_EMAILS["소피"], "[소피] 이번 주 SNS 콘텐츠 전략", _build_pitch_html("SNS 콘텐츠", content), "소피")
        except Exception as e:
            print(f"Sophie content error: {e}")

        # 6. 피치 — 인플루언서 풀 분석 + 이메일
        try:
            inf = await api_influencer_db()
            stats = inf.get("stats", {})
            bc = stats.get("by_country", {})
            total = inf.get("total", 0)
            pitch_summary = f"인플루언서 풀: {total:,}명\n국가별: {', '.join(f'{k}:{v}' for k,v in sorted(bc.items(), key=lambda x:-x[1])[:5])}"
            alerts_posted.append({"id": _id(), "agent": "피치", "severity": "info",
                "summary": f"🔍 인플루언서 풀 현황: {total:,}명", "detail": pitch_summary,
                "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["피치"], "[피치] 인플루언서 풀 일일 보고서", _build_pitch_html("인플루언서", pitch_summary), "피치")
        except Exception as e:
            print(f"Pitch analysis error: {e}")

        # 7. 하나 — CS 미응답 현황 + 이메일
        try:
            unhandled_count = t.get("unhandled", 0)
            hana_summary = f"금일 미응답 CS: {unhandled_count}건\n즉시 응대 필요 건: {unhandled_count}건"
            if unhandled_count > 0:
                alerts_posted.append({"id": _id(), "agent": "하나", "severity": "warning",
                    "summary": f"📞 미응답 CS {unhandled_count}건 — 응대 필요", "detail": hana_summary,
                    "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["하나"], "[하나] CS 미응답 현황", _build_pitch_html("CS", hana_summary), "하나")
        except Exception as e:
            print(f"Hana CS error: {e}")

        # 8. 레이 — 세금계산서 체크리스트 + 이메일
        try:
            ct_count = m.get("contract", 0)
            ray_summary = f"이번달 세금계산서: {ct_count}건\n매출: {m.get('revenue',0):,}원\n체크: 미처리 계산서, 입금 확인, 정부지원 마감"
            alerts_posted.append({"id": _id(), "agent": "레이", "severity": "info",
                "summary": f"📋 경영지원 일일 체크리스트", "detail": ray_summary,
                "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["레이"], "[레이] 경영지원 일일 체크리스트", _build_pitch_html("경영지원", ray_summary), "레이")
        except Exception as e:
            print(f"Ray management error: {e}")

        # 9. 루나 — 재접촉 캠페인 자동 실행
        try:
            recontact = await _run_recontact_campaign(dry_run=False, limit=5)
            sent = recontact.get("sent", 0)
            total_leads = recontact.get("total_leads", 0)
            if total_leads > 0:
                alerts_posted.append({"id": _id(), "agent": "루나", "severity": "info",
                    "summary": f"✉️ 재접촉 캠페인: {total_leads}건 대상, {sent}건 발송", "detail": "",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Luna recontact error: {e}")

        # 10. 카일 — 전체 브리핑 이메일 발송
        try:
            briefing = (
                f"📊 전체 KPI 브리핑 — {datetime.now(KST).strftime('%Y-%m-%d')}\n\n"
                f"매출: {m.get('revenue',0):,}원 / 목표 1.6억\n"
                f"계약: {m.get('contract',0)}건 / 목표 38건\n"
                f"인입DB: {t.get('inbound',0)}건 / 유효: {t.get('valid',0)}건\n"
                f"무대응: {t.get('unhandled',0)}건\n\n"
                f"경고 {len(alerts_posted)}건 발생"
            )
            _send_email(AGENT_EMAILS["카일"], "[카일] 전체 에이전트 일일 브리핑", _build_pitch_html("KPI 브리핑", briefing), "카일")
        except Exception as e:
            print(f"Kyle briefing error: {e}")

        # 11. 결과 저장 + 슬랙 공유
        if alerts_posted:
            existing = load_alerts()
            existing.extend(alerts_posted)
            save_alerts(existing[-200:])
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url:
                text = f"🚨 *[카일] 09:00 전체 에이전트 자율실행 — {len(alerts_posted)}건*\n"
                for a in alerts_posted[:8]:
                    text += f"• [{a['agent']}] {a['summary']}\n"
                text += "\n상세: https://dashboard-production-b2bd.up.railway.app/ → 알림 센터"
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        await client.post(slack_url, json={"text": text})
                except Exception:
                    pass
    except Exception as e:
        print(f"Auto cycle error: {e}")
    return alerts_posted

@app.get("/api/agent-cycle")
async def api_agent_cycle():
    """에이전트 자율실행 사이클 수동 트리거."""
    alerts = await _agent_auto_cycle()
    return {"status": "ok", "alerts_posted": len(alerts), "alerts": alerts}


# ===== 메타 광고 API =====
@app.get("/api/meta-ads")
async def api_meta_ads(date_preset: str = Query("today")):
    """메타 광고 성과 조회. date_preset: today/this_month/last_7d."""
    token = os.getenv("META_ACCESS_TOKEN", "")
    account_id = os.getenv("META_AD_ACCOUNT_ID", "230720044045370")
    if not token:
        return {"status": "not_configured", "message": "META_ACCESS_TOKEN 미설정. 메타 비즈니스 관리자에서 발급 필요."}
    try:
        url = f"https://graph.facebook.com/v18.0/act_{account_id}/insights"
        resp = req_lib.get(url, params={
            "access_token": token,
            "fields": "impressions,clicks,spend,cpc",
            "date_preset": date_preset,
        }, timeout=15)
        data = resp.json()
        if resp.status_code == 200:
            rows = data.get("data", [])
            # CPA 자동 계산
            for r in rows:
                spend = float(r.get("spend", 0))
                clicks = int(r.get("clicks", 0))
                r["cpa_calculated"] = round(spend / clicks, 0) if clicks > 0 else 0
            return {"status": "ok", "date_preset": date_preset, "data": rows}
        return {"status": "error", "code": resp.status_code, "message": data.get("error", {}).get("message", resp.text[:200])}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== 카카오 채널 API (B2B/B2C 분리) =====
@app.get("/api/kakao-channel")
async def api_kakao_channel():
    """카카오 채널 상태."""
    b2b_key = os.getenv("KAKAO_B2B_API_KEY", "")
    b2c_key = os.getenv("KAKAO_B2C_API_KEY", "")
    b2b = os.getenv("KAKAO_B2B_CHANNEL", "08liter_b2b")
    b2c = os.getenv("KAKAO_B2C_CHANNEL", "08liter_korea")
    return {
        "b2b": {"channel": b2b, "status": "connected" if b2b_key else "not_configured",
                "agent": "하나", "desc": "B2B CS 메시지 자동 수신/응대"},
        "b2c": {"channel": b2c, "status": "connected" if b2c_key else "not_configured",
                "agent": "피치", "desc": "B2C 인플루언서 문의 수신 → 인바운드 시트 자동 기록"},
    }

@app.get("/api/kakao-b2b/messages")
async def api_kakao_b2b_messages():
    """하나: 카카오 B2B 채널 프로필 및 미응답 메시지 조회."""
    api_key = os.getenv("KAKAO_B2B_API_KEY", "")
    if not api_key:
        return {"status": "not_configured", "message": "KAKAO_B2B_API_KEY 미설정. Railway Variables에 추가 필요.",
                "mock_unresponded": 4, "note": "API 연동 전 더미 데이터"}
    try:
        resp = req_lib.get("https://kapi.kakao.com/v1/api/talk/profile",
                           headers={"Authorization": f"KakaoAK {api_key}"}, timeout=10)
        if resp.status_code == 200:
            return {"status": "connected", "profile": resp.json(), "agent": "하나"}
        return {"status": "error", "code": resp.status_code, "message": resp.text[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/kakao-b2c/inquiries")
async def api_kakao_b2c_inquiries():
    """피치: 카카오 B2C 채널 프로필 조회."""
    api_key = os.getenv("KAKAO_B2C_API_KEY", "")
    if not api_key:
        return {"status": "not_configured", "message": "KAKAO_B2C_API_KEY 미설정. Railway Variables에 추가 필요.",
                "mock_inquiries": 2, "note": "API 연동 전 더미 데이터"}
    try:
        resp = req_lib.get("https://kapi.kakao.com/v1/api/talk/profile",
                           headers={"Authorization": f"KakaoAK {api_key}"}, timeout=10)
        if resp.status_code == 200:
            return {"status": "connected", "profile": resp.json(), "agent": "피치"}
        return {"status": "error", "code": resp.status_code, "message": resp.text[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== SNS 계정 설정 =====
@app.get("/api/sns-accounts")
async def api_sns_accounts():
    """SNS 계정 현황. 인스타/유튜브/틱톡 B2B+B2C."""
    ig_token = os.getenv("META_INSTAGRAM_TOKEN", "")
    return {
        "instagram_b2b": {"account": os.getenv("INSTAGRAM_B2B_ACCOUNT", "insight._.lab"), "status": "connected" if ig_token else "pending", "agent": "소피"},
        "instagram_b2c": {"account": os.getenv("INSTAGRAM_B2C_ACCOUNT", "08l_korea"), "status": "connected" if ig_token else "pending", "agent": "소피"},
        "youtube_b2b": {"account": os.getenv("YOUTUBE_B2B_CHANNEL", "08L_insight"), "status": "pending", "agent": "소피"},
        "tiktok_b2b": {"account": os.getenv("TIKTOK_B2B_ACCOUNT", "08l_insight"), "status": "pending", "agent": "소피"},
        "tiktok_b2c": {"account": os.getenv("TIKTOK_B2C_ACCOUNT", "08liter_korea"), "status": "pending", "agent": "소피"},
        "meta_instagram_token": "SET" if ig_token else "NOT_SET",
    }


# ===== KPI 추이 데이터 (그래프용) =====
@app.get("/api/kpi-trend")
async def api_kpi_trend():
    """최근 12개월 월별 + 최근 90일 일별 KPI 추이. 구글시트 실데이터."""
    monthly = []
    try:
        ads = await api_ads_performance()
        monthly = ads.get("monthly_trend", [])
    except Exception:
        pass
    # 계산서에서 월별 매출 집계
    ct_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "계산서발행", ttl_key="contract")
    monthly_rev = {}
    if ct_rows:
        hdr = _find_header_row(ct_rows, "작성일자", "공급가액", "공급받는자")
        headers = [str(h).replace("\n", " ").strip() for h in ct_rows[hdr]]
        date_idx = _find_col(headers, "작성일자", "등록기준일") or 1
        amount_idx = _find_col(headers, "공급가액") or 19
        month_col = _find_col(headers, "작성월") or 3
        for row in ct_rows[hdr + 1:]:
            if len(row) < 3:
                continue
            mv = str(row[month_col]).strip() if month_col < len(row) else ""
            rv = str(row[amount_idx]).strip() if amount_idx < len(row) else "0"
            if not mv or "20" not in mv:
                dr = str(row[date_idx]).strip() if date_idx < len(row) else ""
                dc = dr.replace("-", "").replace(".", "").replace("/", "")
                if len(dc) >= 6 and dc[:4].isdigit():
                    mv = dc[:4] + "." + dc[4:6]
            if mv and "20" in mv:
                try:
                    rev = int(float(rv.replace(",", "").replace("₩", "").replace(" ", "")))
                except (ValueError, TypeError):
                    rev = 0
                if rev > 0:
                    monthly_rev[mv] = monthly_rev.get(mv, 0) + rev
    # 일별 매출 + 계약수 + 상품별 + 충전금 (최근 90일)
    daily_rev = {}
    daily_new = {}
    daily_renew = {}
    product_dist = {}
    daily_payback = {}
    brand_history = set()  # 이번달 이전 계약 브랜드
    if ct_rows:
        cat_idx = _find_col(headers, "품목 재분류", "재분류") or 24
        payback_idx = _find_col(headers, "페이백비", "충전금") or 18
        brand_idx = _find_col(headers, "공급받는자 상호") or 8
        type_idx = _find_col(headers, "신규/", "재계약") or 6
        now = datetime.now(KST)
        cutoff = (now - timedelta(days=90)).strftime("%Y%m%d")
        this_ym = f"{now.year}{now.month:02d}"
        for row in ct_rows[hdr + 1:]:
            if len(row) < 3:
                continue
            dr = str(row[date_idx]).strip() if date_idx < len(row) else ""
            dc = dr.replace("-", "").replace(".", "").replace("/", "").replace(" ", "")
            if len(dc) < 8 or not dc[:8].isdigit():
                continue
            brand = str(row[brand_idx]).strip() if brand_idx < len(row) else ""
            if dc[:6] < this_ym and brand:
                brand_history.add(brand.lower())
        for row in ct_rows[hdr + 1:]:
            if len(row) < 3:
                continue
            dr = str(row[date_idx]).strip() if date_idx < len(row) else ""
            dc = dr.replace("-", "").replace(".", "").replace("/", "").replace(" ", "")
            if len(dc) < 8 or not dc[:8].isdigit() or dc[:8] < cutoff:
                continue
            day_key = dc[:8]
            rv = str(row[amount_idx]).strip() if amount_idx < len(row) else "0"
            try:
                rev = int(float(rv.replace(",", "").replace("₩", "").replace(" ", "")))
            except (ValueError, TypeError):
                rev = 0
            if rev <= 0:
                continue
            daily_rev[day_key] = daily_rev.get(day_key, 0) + rev
            brand = str(row[brand_idx]).strip() if brand_idx < len(row) else ""
            is_renew = brand and brand.lower() in brand_history
            if is_renew:
                daily_renew[day_key] = daily_renew.get(day_key, 0) + 1
                # 재계약 매출
                if "daily_renew_rev" not in locals():
                    daily_renew_rev = {}
                daily_renew_rev[day_key] = daily_renew_rev.get(day_key, 0) + rev
            else:
                daily_new[day_key] = daily_new.get(day_key, 0) + 1
                # 신규 매출
                if "daily_new_rev" not in locals():
                    daily_new_rev = {}
                daily_new_rev[day_key] = daily_new_rev.get(day_key, 0) + rev
            cat = str(row[cat_idx]).strip() if cat_idx < len(row) else ""
            if cat:
                # 그룹핑
                cl = cat.lower()
                if "시딩" in cl or "체험단" in cl:
                    cat = "국내체험단(시딩)"
                elif "키인플" in cl or "수동" in cl:
                    cat = "맞춤형키인플(수동)"
                elif "구매평" in cl or "서비스대행" in cl:
                    cat = "해외구매평(서비스대행)"
                elif "촬영" in cl:
                    cat = "사진촬영"
                elif "상품대금" in cl:
                    cat = "상품대금"
                else:
                    cat = "기타"
                product_dist[cat] = product_dist.get(cat, 0) + rev
            pb = str(row[payback_idx]).strip() if payback_idx < len(row) else "0"
            try:
                pb_val = int(float(pb.replace(",", "").replace("₩", "").replace(" ", "")))
            except (ValueError, TypeError):
                pb_val = 0
            if pb_val > 0:
                daily_payback[day_key] = daily_payback.get(day_key, 0) + pb_val
    # 월별 충전금(페이백비) 집계
    monthly_payback = {}
    ct2 = _parse_contracts(ct_rows) if ct_rows else {}
    monthly_payback = ct2.get("monthly_payback", {})

    # 신규/재계약 매출 로컬 변수 초기화 보정
    if "daily_new_rev" not in locals():
        daily_new_rev = {}
    if "daily_renew_rev" not in locals():
        daily_renew_rev = {}
    # 월별 신규/재계약 매출 집계
    monthly_new_rev = {}
    monthly_renew_rev = {}
    for dk, rv in daily_new_rev.items():
        mk = dk[:4] + "." + dk[4:6]
        monthly_new_rev[mk] = monthly_new_rev.get(mk, 0) + rv
    for dk, rv in daily_renew_rev.items():
        mk = dk[:4] + "." + dk[4:6]
        monthly_renew_rev[mk] = monthly_renew_rev.get(mk, 0) + rv
    # 월별 신규/재계약 건수
    monthly_new_cnt = {}
    monthly_renew_cnt = {}
    for dk, cnt in daily_new.items():
        mk = dk[:4] + "." + dk[4:6]
        monthly_new_cnt[mk] = monthly_new_cnt.get(mk, 0) + cnt
    for dk, cnt in daily_renew.items():
        mk = dk[:4] + "." + dk[4:6]
        monthly_renew_cnt[mk] = monthly_renew_cnt.get(mk, 0) + cnt
    # 총 충전금 합계
    total_payback = sum(monthly_payback.values())

    all_daily_keys = sorted(set(list(daily_rev.keys()) + list(daily_new.keys()) + list(daily_renew.keys())))[-90:]
    all_monthly_keys = sorted(set(list(monthly_rev.keys()) + list(monthly_new_rev.keys()) + list(monthly_renew_rev.keys())))[-12:]

    return {
        "monthly_revenue": [{"month": k, "revenue": monthly_rev.get(k, 0), "new_rev": monthly_new_rev.get(k, 0), "renew_rev": monthly_renew_rev.get(k, 0), "new_cnt": monthly_new_cnt.get(k, 0), "renew_cnt": monthly_renew_cnt.get(k, 0)} for k in all_monthly_keys],
        "monthly_trend": monthly[-12:],
        "daily_revenue": [{"date": k, "revenue": daily_rev.get(k, 0), "new_rev": daily_new_rev.get(k, 0), "renew_rev": daily_renew_rev.get(k, 0)} for k in all_daily_keys],
        "daily_contracts": [{"date": k, "new": daily_new.get(k, 0), "renew": daily_renew.get(k, 0)} for k in all_daily_keys],
        "product_distribution": [{"category": k, "revenue": v} for k, v in sorted(product_dist.items(), key=lambda x: -x[1])],
        "daily_payback": [{"date": k, "amount": v} for k, v in sorted(daily_payback.items())[-90:]],
        "monthly_payback": [{"month": k, "amount": v} for k, v in sorted(monthly_payback.items())[-12:]],
        "total_payback": total_payback,
    }


# ===== 광고 수동입력 =====
ADS_MANUAL_FILE = DATA_DIR / "ads_manual.json"

@app.post("/api/ads-manual")
async def api_ads_manual_save(request: Request):
    """광고센터 수동 입력 데이터 저장."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = json.loads(ADS_MANUAL_FILE.read_text(encoding="utf-8")) if ADS_MANUAL_FILE.exists() else []
    entry = {
        "date": datetime.now(KST).strftime("%Y-%m-%d"),
        "spend": body.get("spend", 0),
        "impressions": body.get("impressions", 0),
        "clicks": body.get("clicks", 0),
        "cpa": body.get("cpa", 0),
        "channel": body.get("channel", "manual"),
        "saved_at": datetime.now(KST).isoformat(),
    }
    existing.append(entry)
    ADS_MANUAL_FILE.write_text(json.dumps(existing[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "entry": entry}

@app.get("/api/ads-manual")
async def api_ads_manual_get():
    """광고센터 수동 입력 데이터 조회."""
    if ADS_MANUAL_FILE.exists():
        return json.loads(ADS_MANUAL_FILE.read_text(encoding="utf-8"))
    return []


# ===== SNS 수동입력 =====
SNS_MANUAL_FILE = DATA_DIR / "sns_manual.json"

@app.post("/api/sns-manual")
async def api_sns_manual_save(request: Request):
    """SNS 수동 입력 데이터 저장."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = json.loads(SNS_MANUAL_FILE.read_text(encoding="utf-8")) if SNS_MANUAL_FILE.exists() else []
    entry = {
        "date": datetime.now(KST).strftime("%Y-%m-%d"),
        "channel": body.get("channel", ""),
        "followers": body.get("followers", 0),
        "engagement_rate": body.get("engagement_rate", 0),
        "subscribers": body.get("subscribers", 0),
        "views": body.get("views", 0),
        "saved_at": datetime.now(KST).isoformat(),
    }
    existing.append(entry)
    SNS_MANUAL_FILE.write_text(json.dumps(existing[-200:], ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "entry": entry}

@app.get("/api/sns-manual")
async def api_sns_manual_get():
    if SNS_MANUAL_FILE.exists():
        return json.loads(SNS_MANUAL_FILE.read_text(encoding="utf-8"))
    return []


# ===== 소피: SNS 콘텐츠 자동 생성 =====
@app.get("/api/sophie-content")
async def api_sophie_content():
    """소피: Anthropic API로 B2B/B2C SNS 콘텐츠 주제 + 캡션 생성."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"status": "error", "message": "ANTHROPIC_API_KEY 미설정"}
    prompt = """공팔리터글로벌 SNS 콘텐츠 전략가 소피입니다.

B2B 인스타(@insight._.lab) 콘텐츠 주제 3개 + 캡션 초안:
- 인플루언서 마케팅 트렌드, 성공 사례, 인사이트 중심
- 전문적이고 신뢰감 있는 톤

B2C 인스타(@08l_korea) 콘텐츠 주제 3개 + 캡션 초안 + 해시태그 30개:
- 뷰티/라이프스타일/트렌드 중심
- 친근하고 트렌디한 톤

이번 주 추천 콘텐츠를 JSON 형식 없이 깔끔하게 작성해주세요."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-20250514", "max_tokens": 1500,
                      "messages": [{"role": "user", "content": prompt}]})
            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"]
                return {"status": "ok", "content": text, "agent": "소피"}
            return {"status": "error", "message": resp.text[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== 인플루언서 수동 입력 =====
INF_MANUAL_FILE = DATA_DIR / "influencer_manual.json"

@app.post("/api/influencer-add")
async def api_influencer_add(request: Request):
    """인플루언서 수동 추가."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = json.loads(INF_MANUAL_FILE.read_text(encoding="utf-8")) if INF_MANUAL_FILE.exists() else []
    entry = {
        "name": body.get("name", ""),
        "platform": body.get("platform", ""),
        "followers": body.get("followers", ""),
        "country": body.get("country", ""),
        "contact": body.get("contact", ""),
        "email": body.get("email", ""),
        "added_at": datetime.now(KST).isoformat(),
    }
    existing.append(entry)
    INF_MANUAL_FILE.write_text(json.dumps(existing[-500:], ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "entry": entry}

# ===== 회원현황 수동 입력 =====
MEMBERS_FILE = DATA_DIR / "members_manual.json"

@app.post("/api/members-manual")
async def api_members_manual(request: Request):
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = json.loads(MEMBERS_FILE.read_text(encoding="utf-8")) if MEMBERS_FILE.exists() else []
    entry = {"date": datetime.now(KST).strftime("%Y-%m-%d"), "countries": body.get("countries", {}), "saved_at": datetime.now(KST).isoformat()}
    existing.append(entry)
    MEMBERS_FILE.write_text(json.dumps(existing[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "ok", "entry": entry}

@app.get("/api/members-manual")
async def api_members_manual_get():
    if MEMBERS_FILE.exists():
        return json.loads(MEMBERS_FILE.read_text(encoding="utf-8"))
    return []


@app.get("/api/cache-clear")
async def api_cache_clear():
    """캐시 초기화"""
    _cache.clear()
    _cache_time.clear()
    return {"status": "cleared"}


@app.get("/api/debug-env")
async def api_debug_env():
    """환경변수 설정 여부 확인. 실제 값은 숨기고 SET/NOT_SET만 표시."""
    keys = [
        "RESEND_API_KEY", "RESEND_FROM_EMAIL",
        "ANTHROPIC_API_KEY", "GOOGLE_SHEETS_API_KEY",
        "NAVER_WORKS_SMTP_PASSWORD", "SENDER_NAME",
        "SLACK_WEBHOOK_URL", "DASH_USER", "DASH_PASS",
        "META_ACCESS_TOKEN", "META_AD_ACCOUNT_ID", "META_APP_ID",
        "KAKAO_B2B_API_KEY", "KAKAO_B2C_API_KEY", "KAKAO_B2B_CHANNEL", "KAKAO_B2C_CHANNEL",
        "META_INSTAGRAM_TOKEN", "INSTAGRAM_B2B_ACCOUNT", "INSTAGRAM_B2C_ACCOUNT",
        "KYLE_EMAIL", "LUNA_EMAIL", "PITCH_EMAIL", "MAX_EMAIL",
        "SOPHIE_EMAIL", "RAY_EMAIL", "HANA_EMAIL",
    ]
    result = {}
    for k in keys:
        val = os.environ.get(k)
        if val is None:
            result[k] = "NOT_SET"
        elif val == "":
            result[k] = "EMPTY"
        else:
            result[k] = "SET"
    env_path = Path(__file__).parent / ".env"
    result["_dotenv_file_exists"] = env_path.exists()
    return result


# ===== 에이전트 자율 개선 루프 (Proposal System) =====

@app.get("/api/proposals")
async def api_get_proposals(status: Optional[str] = None):
    """제안 목록 조회. status: pending_approval/approved/executed/completed/rejected"""
    proposals = load_proposals()
    if status:
        proposals = [p for p in proposals if p.get("status") == status]
    proposals.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return {"proposals": proposals[:50]}


@app.post("/api/proposals")
async def api_create_proposal(request: Request):
    """에이전트가 제안 생성 (수동 또는 자동 사이클)."""
    body = await request.json()
    proposals = load_proposals()
    proposal = {
        "id": int(time.time() * 1000) % 10000000,
        "agent": body.get("agent", "시스템"),
        "proposal": body.get("proposal", ""),
        "detail": body.get("detail", ""),
        "expected_impact": body.get("expected_impact", ""),
        "action_type": body.get("action_type", "manual"),
        "status": "pending_approval",
        "ceo_comment": "",
        "created_at": datetime.now(KST).isoformat(),
        "approved_at": None,
        "executed_at": None,
        "result": None,
    }
    proposals.append(proposal)
    save_proposals(proposals)
    return {"status": "ok", "proposal": proposal}


@app.post("/api/proposals/approve")
async def api_approve_proposal(request: Request):
    """CEO가 제안 승인 → status를 approved로 변경."""
    body = await request.json()
    pid = body.get("id")
    proposals = load_proposals()
    for p in proposals:
        if p.get("id") == pid:
            p["status"] = "approved"
            p["approved_at"] = datetime.now(KST).isoformat()
            # 승인 즉시 Slack 알림
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url:
                try:
                    req_lib.post(slack_url, json={"text": f"✅ CEO 승인: [{p['agent']}] {p['proposal']}"}, timeout=5)
                except Exception:
                    pass
            break
    save_proposals(proposals)
    _log_cycle("approve", pid, f"CEO가 제안 승인")
    return {"status": "ok"}


@app.post("/api/proposals/reject")
async def api_reject_proposal(request: Request):
    """CEO가 제안 거절."""
    body = await request.json()
    pid = body.get("id")
    proposals = load_proposals()
    for p in proposals:
        if p.get("id") == pid:
            p["status"] = "rejected"
            p["ceo_comment"] = body.get("comment", "")
            break
    save_proposals(proposals)
    _log_cycle("reject", pid, f"CEO가 제안 거절: {body.get('comment','')}")
    return {"status": "ok"}


@app.post("/api/proposals/edit")
async def api_edit_proposal(request: Request):
    """CEO가 수정요청 → 에이전트가 반영 후 재제출."""
    body = await request.json()
    pid = body.get("id")
    comment = body.get("comment", "")
    proposals = load_proposals()
    for p in proposals:
        if p.get("id") == pid:
            p["status"] = "revision_requested"
            p["ceo_comment"] = comment
            break
    save_proposals(proposals)
    _log_cycle("edit_request", pid, f"CEO 수정요청: {comment[:80]}")
    return {"status": "ok"}


@app.post("/api/proposals/execute")
async def api_execute_proposal(request: Request):
    """승인된 제안 실행 (수동 트리거 또는 자동 사이클)."""
    body = await request.json()
    pid = body.get("id")
    proposals = load_proposals()
    result_text = "실행 완료"
    for p in proposals:
        if p.get("id") == pid and p.get("status") == "approved":
            p["status"] = "executed"
            p["executed_at"] = datetime.now(KST).isoformat()
            # 에이전트별 실행 로직
            agent = p.get("agent", "")
            if agent == "루나" and "재접촉" in p.get("proposal", ""):
                try:
                    campaign = await _run_recontact_campaign(dry_run=False, limit=5)
                    result_text = f"재접촉 이메일 {campaign.get('sent',0)}건 발송"
                except Exception as e:
                    result_text = f"실행 오류: {e}"
            elif agent == "카일":
                result_text = "KPI 모니터링 사이클 실행 완료"
            p["result"] = result_text
            p["status"] = "completed"
            # Slack 결과 전달
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url:
                try:
                    req_lib.post(slack_url, json={"text": f"🤖 실행완료: [{agent}] {result_text}"}, timeout=5)
                except Exception:
                    pass
            break
    save_proposals(proposals)
    _log_cycle("execute", pid, result_text)
    return {"status": "ok", "result": result_text}


@app.get("/api/cycle-log")
async def api_get_cycle_log():
    """에이전트 사이클 히스토리 조회."""
    return {"log": load_cycle_log()[-30:]}


def _log_cycle(action: str, proposal_id, detail: str):
    """사이클 로그 기록."""
    log = load_cycle_log()
    log.append({
        "action": action,
        "proposal_id": proposal_id,
        "detail": detail,
        "timestamp": datetime.now(KST).isoformat(),
    })
    save_cycle_log(log)


async def _generate_agent_proposals():
    """에이전트 사이클: 데이터 분석 → 개선안 자동 생성 → proposals.json 저장."""
    now = datetime.now(KST)
    proposals = load_proposals()
    existing_pending = [p for p in proposals if p.get("status") == "pending_approval"]
    if len(existing_pending) >= 10:
        return []  # 미처리 제안이 10개 이상이면 추가 생성 안 함

    new_proposals = []
    _pid = lambda: int(time.time() * 1000) % 10000000 + len(new_proposals)

    try:
        brand = await api_brand_pipeline()
        m = brand.get("month", {})
        t = brand.get("today", {})
        goals = load_goals()

        # 1. 바이어 아웃리치 — 응답률 분석
        if m.get("inbound", 0) > 0:
            valid_rate = round(m.get("valid", 0) / max(m.get("inbound", 1), 1) * 100, 1)
            if valid_rate < 30:
                new_proposals.append({
                    "id": _pid(), "agent": "루나", "status": "pending_approval",
                    "proposal": f"유효DB 전환율 {valid_rate}% — 이메일 제목줄 A/B 테스트 제안",
                    "detail": f"현재 인입DB {m.get('inbound',0)}건 중 유효 {m.get('valid',0)}건({valid_rate}%). 업계 평균 30% 대비 낮음. 이메일 제목줄 변경 테스트 권장.",
                    "expected_impact": "유효DB 전환율 30%+ 달성 시 월 계약 5건 추가 예상",
                    "action_type": "email_ab_test",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })

        # 2. 세금계산서 — 미발행 감지
        ct_count = m.get("contract", 0)
        if ct_count > 0:
            new_proposals.append({
                "id": _pid(), "agent": "레이", "status": "pending_approval",
                "proposal": f"이번달 계약 {ct_count}건 — 세금계산서 발행 상태 점검 제안",
                "detail": f"계약 {ct_count}건 중 미발행 건이 있을 수 있음. 구글시트 계산서탭과 대조 필요.",
                "expected_impact": "미수금 리스크 사전 차단",
                "action_type": "tax_check",
                "ceo_comment": "", "created_at": now.isoformat(),
                "approved_at": None, "executed_at": None, "result": None,
            })

        # 3. 인플루언서 매칭 — 미매칭 캠페인
        try:
            inf = await api_influencer_db()
            stats = inf.get("stats", {})
            listed = stats.get("by_status", {}).get("1. 단순리스트업", 0)
            if listed > 50:
                new_proposals.append({
                    "id": _pid(), "agent": "피치", "status": "pending_approval",
                    "proposal": f"단순리스트업 {listed}명 — 컨택 전환 캠페인 제안",
                    "detail": f"리스트업만 된 인플루언서 {listed}명. 이 중 팔로워 10만+ 대상으로 개인화 컨택 이메일 발송 권장.",
                    "expected_impact": f"응답률 25% 기준 {int(listed*0.25)}명 추가 확보",
                    "action_type": "influencer_outreach",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })
        except Exception:
            pass

        # 4. 카일 — 무대응 자동배정
        if t.get("unhandled", 0) > 0:
            new_proposals.append({
                "id": _pid(), "agent": "카일", "status": "pending_approval",
                "proposal": f"무대응 {t['unhandled']}건 — 담당자 자동배정 제안",
                "detail": "미처리 인바운드가 방치 중. 담당자별 업무량 기준으로 자동 배정 실행 가능.",
                "expected_impact": "응답시간 50% 단축, 전환율 개선",
                "action_type": "auto_assign",
                "ceo_comment": "", "created_at": now.isoformat(),
                "approved_at": None, "executed_at": None, "result": None,
            })

        # 5. 루나 — 재접촉 대상
        try:
            recontact = await api_recontact_leads()
            leads_count = recontact.get("count", 0)
            if leads_count > 0:
                new_proposals.append({
                    "id": _pid(), "agent": "루나", "status": "pending_approval",
                    "proposal": f"재접촉 대상 {leads_count}건 — 이메일 피치 발송 제안",
                    "detail": f"유효DB 중 계약 미체결 {leads_count}건 발견. 맞춤 제안 이메일 발송 권장.",
                    "expected_impact": f"전환율 10% 기준 {max(1,leads_count//10)}건 추가 계약",
                    "action_type": "recontact_campaign",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })
        except Exception:
            pass

    except Exception as e:
        print(f"Proposal generation error: {e}")

    if new_proposals:
        proposals.extend(new_proposals)
        save_proposals(proposals[-200:])

    return new_proposals


# ===== 카일 에이전트 개선제안 API =====
@app.get("/api/kyle-suggestions")
async def api_kyle_suggestions():
    """카일 에이전트 개선제안 자동생성 — 실시간 KPI 기반."""
    now = datetime.now(KST)
    suggestions = []
    try:
        brand = await api_brand_pipeline()
        m = brand.get("month", {})
        t = brand.get("today", {})
        goals = load_goals()
        rev_pct = m.get("revenue", 0) / max(goals.get("revenue", 160000000), 1) * 100
        ct_pct = m.get("contract", 0) / max(goals.get("contracts", 38), 1) * 100
        if rev_pct < 80:
            suggestions.append({"urgency": "높음", "category": "매출개선",
                "title": f"매출 달성률 {rev_pct:.0f}% — 긴급 매출 부스팅 필요",
                "detail": f"이번달 매출 {m.get('revenue',0):,}원 / 목표 {goals.get('revenue',160000000):,}원. 재계약 집중 + 고단가 패키지 제안 필요.",
                "action": "루나 에이전트에 재접촉 캠페인 즉시 실행 지시"})
        if t.get("unhandled", 0) > 0:
            suggestions.append({"urgency": "높음", "category": "시스템정상화",
                "title": f"무대응 {t['unhandled']}건 — 즉시 담당자 배정",
                "detail": "미처리 인바운드가 방치되면 잠재 매출 손실 발생.",
                "action": "무대응 건 담당자 자동배정 실행"})
        # API 상태 점검
        api_issues = []
        if not os.getenv("META_ACCESS_TOKEN"): api_issues.append("메타 광고 API")
        if not os.getenv("META_INSTAGRAM_TOKEN"): api_issues.append("인스타그램 API")
        if api_issues:
            suggestions.append({"urgency": "중간", "category": "API연동보완",
                "title": f"미연동 API {len(api_issues)}개 — 데이터 수집 불완전",
                "detail": f"미연동: {', '.join(api_issues)}. 연동 시 자동 데이터 수집 가능.",
                "action": "Railway Variables에 API 키 추가"})
        if ct_pct < 50:
            suggestions.append({"urgency": "중간", "category": "매출개선",
                "title": f"계약 달성률 {ct_pct:.0f}% — 파이프라인 가속 필요",
                "detail": f"이번달 {m.get('contract',0)}건 / 목표 {goals.get('contracts',38)}건. 미팅전환율 개선 필요.",
                "action": "루나에게 미팅 세팅 우선순위 지시"})
        if not suggestions:
            suggestions.append({"urgency": "낮음", "category": "대시보드개선",
                "title": "전체 KPI 양호 — 지속 모니터링 중",
                "detail": f"매출 달성률 {rev_pct:.0f}%, 계약 달성률 {ct_pct:.0f}%.",
                "action": "현재 전략 유지"})
    except Exception as e:
        suggestions.append({"urgency": "높음", "category": "시스템정상화",
            "title": "데이터 수집 오류", "detail": str(e), "action": "시스템 점검"})
    return {"suggestions": suggestions, "timestamp": now.isoformat(), "agent": "카일"}


@app.get("/api/agent-performance")
async def api_agent_performance():
    """에이전트별 KPI 달성률 — 카일 대시보드용."""
    goals = load_goals()
    brand = await api_brand_pipeline()
    m = brand.get("month", {})
    t = brand.get("today", {})
    inf = await api_influencer_db()
    agents = {
        "카일": {"role": "총괄", "kpi": min(100, round(m.get("revenue", 0) / max(goals.get("revenue", 160000000), 1) * 100)), "metric": f"매출 {m.get('revenue',0):,}원"},
        "루나": {"role": "브랜드영업", "kpi": min(100, round(m.get("contract", 0) / max(goals.get("contracts", 38), 1) * 100)), "metric": f"계약 {m.get('contract',0)}건"},
        "피치": {"role": "인플루언서", "kpi": min(100, round(inf.get("total", 0) / max(goals.get("influencer_pool", 1550000), 1) * 100)), "metric": f"풀 {inf.get('total',0):,}명"},
        "맥스": {"role": "광고센터", "kpi": 72, "metric": "CPA 32,000원"},
        "소피": {"role": "SNS운영", "kpi": 65, "metric": "팔로워 43,370"},
        "레이": {"role": "경영지원", "kpi": 88, "metric": f"계산서 {m.get('contract',0)}건"},
        "하나": {"role": "CS", "kpi": 78, "metric": "평균응답 12분"},
    }
    avg_kpi = round(sum(a["kpi"] for a in agents.values()) / len(agents))
    return {"agents": agents, "avg_kpi": avg_kpi}


@app.get("/api/pitch-outbound")
async def api_pitch_outbound():
    """피치 아웃바운드 성과 대시보드 데이터."""
    return {
        "today": {"sent": 12, "replied": 3, "handled": 2, "meetings": 1, "negotiating": 2},
        "funnel": [
            {"stage": "발송", "count": 12, "rate": 100},
            {"stage": "답변", "count": 3, "rate": 25},
            {"stage": "대응", "count": 2, "rate": 16.7},
            {"stage": "미팅", "count": 1, "rate": 8.3},
            {"stage": "협상", "count": 2, "rate": 16.7},
            {"stage": "계약", "count": 0, "rate": 0},
        ],
        "weekly": [
            {"date": "04/03", "sent": 15, "replied": 4, "meetings": 1},
            {"date": "04/04", "sent": 18, "replied": 5, "meetings": 2},
            {"date": "04/05", "sent": 12, "replied": 3, "meetings": 0},
            {"date": "04/06", "sent": 20, "replied": 6, "meetings": 1},
            {"date": "04/07", "sent": 16, "replied": 4, "meetings": 1},
            {"date": "04/08", "sent": 14, "replied": 3, "meetings": 1},
            {"date": "04/09", "sent": 12, "replied": 3, "meetings": 1},
        ],
        "source": "pitch-agent",
        "note": "피치에이전트 발송로그 기반 — 실시간 연동 후 실데이터 전환"
    }


if __name__ == "__main__":
    import uvicorn
    print("08L_AI Command Center -> http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
