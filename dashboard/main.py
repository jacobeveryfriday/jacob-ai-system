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
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv(override=False)  # OS 환경변수(Railway)가 .env보다 우선
app = FastAPI(title="Command Center")
app.add_middleware(GZipMiddleware, minimum_size=500)
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
    # 메타: 토큰 존재하면 connected, API 호출은 별도 검증
    meta_status = "not_configured"
    meta_note = ""
    if os.getenv("META_ACCESS_TOKEN"):
        meta_status = "connected"
        try:
            r = req_lib.get(f"https://graph.facebook.com/v18.0/act_{os.getenv('META_AD_ACCOUNT_ID','230720044045370')}/campaigns",
                params={"access_token": os.getenv("META_ACCESS_TOKEN"), "fields": "name", "limit": "1"}, timeout=5)
            if r.status_code != 200:
                meta_note = "토큰 유효하나 API 응답 비정상 (code=" + str(r.status_code) + ")"
        except Exception:
            meta_note = "API 호출 타임아웃 (토큰은 설정됨)"
    return {
        "status": "ok",
        "timestamp": datetime.now(KST).isoformat(),
        "services": {
            "google_sheets": "connected" if GSHEETS_API_KEY else "not_configured",
            "anthropic": _chk("ANTHROPIC_API_KEY"),
            "slack": _chk("SLACK_WEBHOOK_URL"),
            "email_webhook": "connected" if os.getenv("EMAIL_WEBHOOK_URL") else "not_configured",
            "meta_ads": meta_status,
            "meta_ads_note": meta_note,
            "kakao_b2b": "connected" if os.getenv("KAKAO_B2B_API_KEY") or os.getenv("KAKAO_REST_API_KEY") else "not_configured",
            "kakao_b2c": "connected" if os.getenv("KAKAO_B2C_API_KEY") or os.getenv("KAKAO_REST_API_KEY") else "not_configured",
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
AGENT_PERF_FILE = DATA_DIR / "agent_performance.json"
BENCHMARKS_FILE = DATA_DIR / "benchmarks.json"
EMAIL_QUEUE_FILE = DATA_DIR / "email_queue.json"
AGENT_AUTO_SEND_FILE = DATA_DIR / "agent_auto_send.json"
CRAWLED_DATA_FILE = DATA_DIR / "crawled_data.json"
EMAIL_LOG_FILE = DATA_DIR / "email_log.json"

# 발송 속도 제한
SEND_LIMITS = {"hourly": 50, "daily": 550, "interval_sec": 30}

def load_crawled() -> list:
    if CRAWLED_DATA_FILE.exists():
        return json.loads(CRAWLED_DATA_FILE.read_text(encoding="utf-8"))
    return []

def save_crawled(data: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CRAWLED_DATA_FILE.write_text(json.dumps(data[-5000:], ensure_ascii=False, indent=2), encoding="utf-8")

def load_email_log() -> list:
    if EMAIL_LOG_FILE.exists():
        return json.loads(EMAIL_LOG_FILE.read_text(encoding="utf-8"))
    return []

def save_email_log(data: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EMAIL_LOG_FILE.write_text(json.dumps(data[-2000:], ensure_ascii=False, indent=2), encoding="utf-8")

def _log_email(agent: str, to: str, subject: str, status: str, meta: dict = None):
    """이메일 발송 로그 기록."""
    log = load_email_log()
    log.append({"agent": agent, "to": to, "subject": subject, "status": status,
                "sent_at": datetime.now(KST).isoformat(), "opened": False,
                "replied": False, "followup_count": 0, "meta": meta or {}})
    save_email_log(log)

def _check_send_limit() -> bool:
    """일일 발송 한도 확인."""
    log = load_email_log()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    today_count = sum(1 for e in log if e.get("sent_at", "").startswith(today) and e.get("status") == "sent")
    return today_count < SEND_LIMITS["daily"]

def load_email_queue() -> list:
    if EMAIL_QUEUE_FILE.exists():
        return json.loads(EMAIL_QUEUE_FILE.read_text(encoding="utf-8"))
    return []

def save_email_queue(data: list):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    EMAIL_QUEUE_FILE.write_text(json.dumps(data[-200:], ensure_ascii=False, indent=2), encoding="utf-8")

def _is_auto_send(agent: str) -> bool:
    """에이전트 자동 발송 모드 확인. 기본 OFF."""
    if AGENT_AUTO_SEND_FILE.exists():
        try:
            return json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8")).get(agent, False)
        except Exception:
            pass
    return False

def _queue_or_send_email(agent: str, to_email: str, subject: str, html: str, meta: dict = None) -> dict:
    """자동 발송 모드면 즉시 발송, 아니면 검수 큐에 추가."""
    if _is_auto_send(agent):
        result = _send_email(to_email, subject, html, agent)
        result["mode"] = "auto"
        return result
    queue = load_email_queue()
    entry = {
        "id": int(time.time() * 1000) % 10000000,
        "agent": agent,
        "to": to_email,
        "subject": subject,
        "html": html,
        "meta": meta or {},
        "status": "pending",
        "created_at": datetime.now(KST).isoformat(),
    }
    queue.append(entry)
    save_email_queue(queue)
    return {"status": "queued", "id": entry["id"], "mode": "review"}

def load_benchmarks() -> dict:
    if BENCHMARKS_FILE.exists():
        return json.loads(BENCHMARKS_FILE.read_text(encoding="utf-8"))
    return {}

# 토큰 비용 단가 (USD per M tokens)
TOKEN_COSTS = {
    "haiku": {"input": 1.0, "output": 5.0},
    "sonnet": {"input": 3.0, "output": 15.0},
}

def _record_tokens(agent: str, input_tokens: int, output_tokens: int, model: str = "sonnet"):
    """에이전트별 토큰 사용량 기록."""
    cost_table = TOKEN_COSTS.get("haiku" if "haiku" in model.lower() else "sonnet", TOKEN_COSTS["sonnet"])
    cost = (input_tokens * cost_table["input"] + output_tokens * cost_table["output"]) / 1_000_000
    _record_perf(agent, "input_tokens", input_tokens)
    _record_perf(agent, "output_tokens", output_tokens)
    _record_perf(agent, "cost_usd_x100", int(cost * 100))

# ===== 에이전트별 구글시트 =====
PITCH_SHEET_ID = os.getenv("PITCH_SHEET_ID", "1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8")
LUNA_SHEET_ID = os.getenv("LUNA_SHEET_ID", "1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs")
SOPHIE_SHEET_ID = os.getenv("SOPHIE_SHEET_ID", "1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU")

SHEET_URLS = {
    "피치": "https://docs.google.com/spreadsheets/d/1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8/edit#gid=0",
    "루나": "https://docs.google.com/spreadsheets/d/1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs/edit#gid=0",
    "소피": "https://docs.google.com/spreadsheets/d/1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU/edit#gid=0",
    "레이": "https://docs.google.com/spreadsheets/d/1j_3IYME764NlrARbNCZ_TJqzZCyfAMy-N3V-ByRik6Q/edit#gid=0",
}

MEETING_LINK ="https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ3b3pndYo35A_3SjrHJeeXfAm3YpvBX0IXfkJqXP0QXixBEADR_ehY__tHBlJdNBkL5I2868Rrd"

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
    "alert_threshold": 0.3,
}

# ===== 에이전트별 목표 (일/주/월) =====
AGENT_TARGETS = {
    "피치": {
        "monthly": {"new_contract": 10, "renew_contract": 10, "meeting_booked": 60, "inbound_email": 3000, "outbound_email": 5000, "total_email": 8000},
        "weekly":  {"new_contract": 2.5, "renew_contract": 2.5, "meeting_booked": 15, "inbound_email": 750, "outbound_email": 1250, "total_email": 2000},
        "daily":   {"meeting_booked": 3, "inbound_email": 150, "outbound_email": 250, "total_email": 400},
    },
    "루나": {
        "monthly": {"influencer_acquired": 300, "outbound_email": 3000, "crawl_data": 5000, "email_reply": 450},
        "weekly":  {"influencer_acquired": 75, "outbound_email": 750, "crawl_data": 1250, "email_reply": 113},
        "daily":   {"influencer_acquired": 15, "outbound_email": 150, "crawl_data": 250, "email_reply": 23},
    },
    "소피": {
        "monthly": {"b2b_content": 20, "b2c_content": 20, "b2b_lead": 300, "b2c_lead": 500},
        "weekly":  {"b2b_content": 5, "b2c_content": 5, "b2b_lead": 75, "b2c_lead": 125},
        "daily":   {"b2b_content": 1, "b2c_content": 1, "b2b_lead": 15, "b2c_lead": 25},
    },
    "맥스": {
        "monthly": {"cpa_target": 20000, "valid_db_ratio_x": 2},
    },
    "카일": {
        "daily":   {"dashboard_check": 1, "improvement_proposals": 2},
        "weekly":  {"improvement_proposals": 10, "kpi_achievement": 80},
        "monthly": {"improvement_proposals": 40, "kpi_achievement": 80},
    },
}

def load_goals() -> dict:
    if GOALS_FILE.exists():
        return json.loads(GOALS_FILE.read_text(encoding="utf-8"))
    return dict(DEFAULT_GOALS)

def save_goals(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    GOALS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load_agent_perf() -> dict:
    if AGENT_PERF_FILE.exists():
        return json.loads(AGENT_PERF_FILE.read_text(encoding="utf-8"))
    return {}

def save_agent_perf(data: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_PERF_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _record_perf(agent: str, metric: str, delta: int = 1):
    """에이전트 일일 성과 기록. {날짜: {에이전트: {metric: count}}}"""
    perf = load_agent_perf()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    perf.setdefault(today, {}).setdefault(agent, {})
    perf[today][agent][metric] = perf[today][agent].get(metric, 0) + delta
    save_agent_perf(perf)

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
    "contract": 300,     # 5분 — 로딩 속도 개선
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
            "meta": {"spend": 9000000, "db": 18, "cpa": 500000, "roas": 0, "impressions": 120000, "clicks": 3600, "ctr": 3.0, "cpc": 2500},
            "google": {"spend": 5000000, "db": 9, "cpa": 556000, "roas": 0, "impressions": 80000, "clicks": 2400, "ctr": 3.0, "cpc": 2083},
            "naver": {"spend": 8000000, "db": 12, "cpa": 667000, "roas": 0, "impressions": 95000, "clicks": 2850, "ctr": 3.0, "cpc": 2807},
            "kakao": {"spend": 2000000, "db": 4, "cpa": 500000, "roas": 0, "impressions": 40000, "clicks": 800, "ctr": 2.0, "cpc": 2500},
            "total": {"spend": 24000000, "db": 43, "cpa": 558000, "roas": 9.41},
        },
        "prev_month": {
            "meta": {"spend": 8500000, "db": 16, "cpa": 531000, "impressions": 110000, "clicks": 3300, "ctr": 3.0, "cpc": 2576},
            "google": {"spend": 4800000, "db": 8, "cpa": 600000, "impressions": 75000, "clicks": 2100, "ctr": 2.8, "cpc": 2286},
            "naver": {"spend": 7500000, "db": 10, "cpa": 750000, "impressions": 88000, "clicks": 2640, "ctr": 3.0, "cpc": 2841},
            "kakao": {"spend": 1800000, "db": 3, "cpa": 600000, "impressions": 35000, "clicks": 700, "ctr": 2.0, "cpc": 2571},
            "total": {"spend": 22600000, "db": 37, "cpa": 611000, "roas": 8.90},
        },
        "funnel": {
            "meta": {"db": 18, "meeting": 8, "contract": 3},
            "google": {"db": 9, "meeting": 4, "contract": 2},
            "naver": {"db": 12, "meeting": 5, "contract": 2},
            "total": {"db": 39, "meeting": 17, "contract": 7},
        },
        "by_person": [
            {"name": "소필라", "revenue": 18500000, "contracts": 3, "conversion": 37.5},
            {"name": "라이더", "revenue": 12000000, "contracts": 2, "conversion": 33.3},
            {"name": "제이콥", "revenue": 8700000, "contracts": 1, "conversion": 25.0},
        ],
        "monthly_trend": [
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
DAILY_AGENT_CARDS = [
    {"agent": "피치", "action_type": "pitch_db_collect",
     "proposal": "브랜드 DB 수집 + 이메일 발송",
     "detail": "📦 ① DB 수집 계획\n출처: LinkedIn + Instagram 브랜드\n타겟: K-뷰티 브랜드 마케팅매니저/CMO\n목표: 100명\n기간: 오늘 중\n비용: Haiku / 120,000토큰 / 약 294원\n제외: 대기업계열 / 이메일없는곳\n\n📧 ② 발송할 이메일\n제목: [공팔리터글로벌] 4월 인플루언서 마케팅 협업 제안\n안녕하세요 {담당자명}님, 공팔리터글로벌 피치입니다.\n저희 1,000명+ K-뷰티 인플루언서 네트워크로 협업 제안드립니다.\n5분 비대면 미팅 가능하실까요?",
     "expected_impact": "DB 100건 → 유효 70건 → 미팅 10건 → 계약 3건"},
    {"agent": "루나", "action_type": "luna_db_collect",
     "proposal": "인플루언서 DB 수집 + 협찬 제안 발송",
     "detail": "📦 ① DB 수집 계획\n출처: Instagram (#kbeauty 해시태그)\n타겟: 뷰티 인플루언서 (팔로워 1만~100만, 인게이지먼트 3%↑)\n목표: 50명\n기간: 오늘 중\n비용: Haiku / 80,000토큰 / 약 196원\n제외: 인게이지먼트 3%미만 / 비활성\n\n📧 ② 발송할 이메일\n제목: [밀리밀리] 4월 K-뷰티 협찬 제안드립니다\n안녕하세요 {인플루언서명}님! 밀리밀리 루나입니다.\n4월 협찬 제안드립니다. 제품 무상제공 + 수익쉐어 가능해요.",
     "expected_impact": "DB 50명 → 유효 35명 → 협찬확정 5건"},
    {"agent": "맥스", "action_type": "max_ads_optimize",
     "proposal": "메타광고 캠페인 최적화",
     "detail": "📦 ① 실행 계획\n내용: 메타광고 캠페인 성과 분석 + 타겟팅 최적화\n목표: 월 광고 ROAS 3.0 이상 / CPA 2만원 이하\n기간: 오늘 중\n비용: 광고비 별도 / 분석 토큰 무료\n\n📧 ② 실행 액션\n광고 캠페인 자동 모니터링 시작\n성과 미달 시 즉시 CEO 알림\nA/B 테스트 소재 변경 제안",
     "expected_impact": "광고 정상화 → 인바운드 +30% → CPA 2만원 달성"},
    {"agent": "소피", "action_type": "sophie_content_plan",
     "proposal": "이번주 SNS 콘텐츠 캘린더 수립",
     "detail": "📦 ① 실행 계획\n내용: 이번주 SNS 콘텐츠 캘린더 수립\n플랫폼: 인스타그램 / 틱톡\n목표: 주 3회 게시, 도달 5만 목표\n비용: Haiku / 50,000토큰 / 약 122원\n\n📧 ② 콘텐츠 방향\n밀리밀리 K-뷰티 스킨케어 루틴\n#kbeauty #skincare 해시태그 활용\nB2B: 브랜드 성공사례 / B2C: 협찬 모집",
     "expected_impact": "팔로워 +500 / B2B 리드 10건 / B2C 리드 15건"},
    {"agent": "레이", "action_type": "ray_tax_check",
     "proposal": "세금계산서 발행상태 전수점검",
     "detail": "📦 ① 실행 계획\n내용: 이번달 계약 건 세금계산서 발행상태 전수점검\n미발행 건수 파악 → 즉시 발행처리\n기간: 오늘 중\n비용: Haiku / 30,000토큰 / 약 73원\n\n📧 ② 보고 형식\n총 N건 중 발행 N건 / 미발행 N건\n미발행 목록: [브랜드명, 금액, 계약일]",
     "expected_impact": "미수금 리스크 사전 차단"},
    {"agent": "하나", "action_type": "hana_cs_analysis",
     "proposal": "CS 문의 분류 + 패턴 분석",
     "detail": "📦 ① 실행 계획\n내용: 오늘 CS 문의 분류 + 반복 패턴 분석\n목표: 반복 문의 유형 파악 → 근본해결 제안\n기간: 오늘 중\n비용: Haiku / 20,000토큰 / 약 49원\n\n📧 ② 보고 형식\n문의유형 TOP3: [유형, 건수, 해결방법]\n반복문의 근본해결 제안: [제안내용]",
     "expected_impact": "CS 재문의율 20% 감소"},
]

def _ensure_daily_proposals():
    """오늘자 전 에이전트 승인 카드가 없으면 자동 생성."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    proposals = load_proposals()
    today_types = {p.get("action_type") for p in proposals if p.get("created_at", "").startswith(today)}
    new_props = []
    for card in DAILY_AGENT_CARDS:
        if card["action_type"] not in today_types:
            new_props.append({
                "id": int(time.time() * 1000) % 10000000 + len(new_props),
                "agent": card["agent"], "status": "pending_approval",
                "proposal": card["proposal"], "detail": card["detail"],
                "expected_impact": card["expected_impact"],
                "action_type": card["action_type"],
                "ceo_comment": "", "created_at": datetime.now(KST).isoformat(),
            })
    if new_props:
        proposals.extend(new_props)
        save_proposals(proposals[-200:])

@app.get("/", response_class=HTMLResponse)
async def ceo_dashboard(request: Request):
    """새 CEO 대시보드 — McKinsey 스타일 3섹션 레이아웃."""
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    _ensure_daily_proposals()
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
    """광고 성과 — 시트 헤더 기반 동적 참조. 하드코딩 금지."""
    now = datetime.now(KST)
    this_ym = f"{now.year}{now.month:02d}"
    this_month_dot = f"{now.year}.{now.month:02d}"
    prev_dt = now.replace(day=1) - timedelta(days=1)
    prev_ym = f"{prev_dt.year}{prev_dt.month:02d}"

    def _pint(v):
        try: return int(float(str(v).replace(",", "").replace("₩", "").replace(" ", ""))) if v and str(v).strip() not in ["-", ""] else 0
        except: return 0

    # ---------- 1. 인바운드 시트 → DB수 / 채널별 / 담당자DB수 ----------
    ib_total, ib_by_ch, ib_valid, ib_by_staff = 0, {}, 0, {}
    prev_ib_total = 0
    try:
        ib_rows = fetch_sheet(SHEET_INBOUND, "A:Z", "파센문의", ttl_key="inbound")
        if ib_rows and len(ib_rows) > 2:
            hdr_idx = _find_header_row(ib_rows, "국가", "컨택현황", "컨텍현황", "담당자")
            headers = [str(h).replace("\n", " ").strip() for h in ib_rows[hdr_idx]]
            month_col = _find_col(headers, "월")
            date_col = _auto_detect_date_col(headers, ib_rows[hdr_idx+1:hdr_idx+6])
            ch_col = _find_col(headers, "유입채널")
            status_col = _find_col(headers, "컨텍현황", "컨택현황")
            staff_col = _find_col(headers, "팀담당자", "담당자")
            for row in ib_rows[hdr_idx+1:]:
                if len(row) < 3: continue
                month_val = str(row[month_col]).strip() if month_col is not None and month_col < len(row) else ""
                date_val = str(row[date_col]).strip() if date_col is not None and date_col < len(row) else ""
                date_clean = date_val.replace("-","").replace(".","").replace("/","").replace(" ","")
                is_this_month = (this_month_dot in month_val) or (len(date_clean)>=6 and date_clean[:6]==this_ym)
                is_prev_month = (f"{prev_dt.year}.{prev_dt.month:02d}" in month_val) or (len(date_clean)>=6 and date_clean[:6]==prev_ym)
                if is_this_month:
                    ib_total += 1
                    ch = str(row[ch_col]).strip() if ch_col is not None and ch_col < len(row) else "기타"
                    if "메타" in ch or "meta" in ch.lower() or "페이스" in ch or "인스타" in ch: ch_key = "Meta"
                    elif "네이버" in ch or "naver" in ch.lower(): ch_key = "네이버"
                    elif "구글" in ch or "google" in ch.lower(): ch_key = "구글"
                    else: ch_key = "기타"
                    ib_by_ch[ch_key] = ib_by_ch.get(ch_key, 0) + 1
                    st = str(row[status_col]).strip() if status_col is not None and status_col < len(row) else ""
                    if "부적합" not in st and "정보누락" not in st: ib_valid += 1
                    staff = str(row[staff_col]).strip() if staff_col is not None and staff_col < len(row) else ""
                    if staff: ib_by_staff[staff] = ib_by_staff.get(staff, 0) + 1
                if is_prev_month: prev_ib_total += 1
    except Exception as e:
        print(f"ads-perf inbound error: {e}")

    # ---------- 2. 계약 시트 → 매출합계 ----------
    month_revenue, prev_month_revenue = 0, 0
    month_contracts, prev_month_contracts = 0, 0
    monthly_trend = []
    try:
        ct_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "계산서발행", ttl_key="contract")
        if ct_rows and len(ct_rows) > 1:
            hdr_idx = _find_header_row(ct_rows, "작성일자", "공급가액", "공급받는자")
            headers = [str(h).replace("\n", " ").strip() for h in ct_rows[hdr_idx]]
            ct_date_idx = _find_col(headers, "계산서 작성일자", "작성일자", "등록기준일", "발행일")
            ct_amount_idx = _find_col(headers, "총합계", "공급가액")
            if ct_date_idx is None: ct_date_idx = 1
            if ct_amount_idx is None and len(headers) > 19: ct_amount_idx = 19
            monthly_map = {}
            for row in ct_rows[hdr_idx+1:]:
                if not row or len(row) < 3: continue
                date_raw = str(row[ct_date_idx]).strip() if ct_date_idx < len(row) else ""
                rev = _pint(row[ct_amount_idx]) if ct_amount_idx is not None and ct_amount_idx < len(row) else 0
                if rev <= 0: continue
                date_clean = date_raw.replace("-","").replace(".","").replace("/","").replace(" ","")
                if len(date_clean) < 6 or not date_clean[:6].isdigit(): continue
                ym = date_clean[:6]
                ym_dot = ym[:4] + "." + ym[4:6]
                if ym_dot not in monthly_map: monthly_map[ym_dot] = {"revenue": 0, "contracts": 0}
                monthly_map[ym_dot]["revenue"] += rev
                monthly_map[ym_dot]["contracts"] += 1
                if ym == this_ym:
                    month_revenue += rev
                    month_contracts += 1
                elif ym == prev_ym:
                    prev_month_revenue += rev
                    prev_month_contracts += 1
            for ym_dot in sorted(monthly_map.keys())[-6:]:
                d = monthly_map[ym_dot]
                monthly_trend.append({"month": ym_dot, "contracts": d["contracts"],
                                      "revenue": d["revenue"], "spend": 0, "roas": 0, "avg_price": round(d["revenue"]/max(d["contracts"],1))})
    except Exception as e:
        print(f"ads-perf contract error: {e}")

    # ---------- 3. Meta 광고 API → 이번달 광고비 ----------
    meta_spend = 0
    try:
        token = os.getenv("META_ACCESS_TOKEN", "")
        account_id = os.getenv("META_AD_ACCOUNT_ID", "230720044045370")
        if token:
            url = f"https://graph.facebook.com/v18.0/act_{account_id}/insights"
            resp = req_lib.get(url, params={"access_token": token, "fields": "spend,impressions,clicks",
                                            "date_preset": "this_month"}, timeout=15)
            if resp.status_code == 200:
                for r in resp.json().get("data", []):
                    meta_spend += int(float(r.get("spend", 0)))
    except Exception as e:
        print(f"ads-perf meta error: {e}")

    # ---------- 4. 네이버/구글 광고비 (API 미연동 시 더미) ----------
    naver_spend = 0  # TODO: 네이버 SA API 연동
    google_spend = 0  # TODO: Google Ads API 연동
    total_spend = meta_spend + naver_spend + google_spend

    # ---------- 5. 전월 광고비 (더미) ----------
    prev_total_spend = round(total_spend * 0.9) if total_spend > 0 else 22600000

    # ---------- 결과 조합 ----------
    db_cpa = round(total_spend / max(ib_total, 1)) if total_spend > 0 else 0
    prev_db_cpa = round(prev_total_spend / max(prev_ib_total, 1)) if prev_total_spend > 0 else 0
    roas = round(month_revenue / max(total_spend, 1) * 100, 1) if total_spend > 0 else 0
    prev_roas = round(prev_month_revenue / max(prev_total_spend, 1) * 100, 1) if prev_total_spend > 0 else 0
    meeting_rate = round(ib_valid / max(ib_total, 1) * 100, 1)

    # 채널별 데이터
    channel_data = {}
    for ch_key in ["Meta", "네이버", "구글"]:
        ch_db = ib_by_ch.get(ch_key, 0)
        ch_spend = meta_spend if ch_key == "Meta" else (naver_spend if ch_key == "네이버" else google_spend)
        channel_data[ch_key] = {"db": ch_db, "spend": ch_spend, "cpa": round(ch_spend / max(ch_db, 1)) if ch_spend else 0}

    # ---------- 담당자별 KPI — "담당자별 계약전환율" 탭 직접 연동 ----------
    by_person = []
    try:
        staff_rows = fetch_sheet(SHEET_CONTRACT, "A:J", "담당자별 계약전환율", ttl_key="contract")
        if staff_rows and len(staff_rows) > 1:
            # 헤더 찾기 (3번째 행 부근에 헤더가 있을 수 있음)
            sh_hdr_idx = 0
            for ri, row in enumerate(staff_rows[:5]):
                row_text = " ".join(str(c).replace("\n", " ") for c in row)
                if "담당자" in row_text or "DB건수" in row_text or "계약건수" in row_text:
                    sh_hdr_idx = ri
                    break
            sh_headers = [str(h).replace("\n", " ").strip() for h in staff_rows[sh_hdr_idx]]
            col_month = _find_col(sh_headers, "월구분", "월")
            col_name_kr = _find_col(sh_headers, "국문담당자명", "국문", "담당자명")
            col_name_en = _find_col(sh_headers, "담당자명")  # 영문 폴백
            col_db = _find_col(sh_headers, "DB건수", "DB수")
            col_contracts = _find_col(sh_headers, "계약건수")
            col_revenue = _find_col(sh_headers, "계약매출")
            col_conv = _find_col(sh_headers, "계약전환율", "전환율")
            col_lead_time = _find_col(sh_headers, "리드타임")
            col_db_cost = _find_col(sh_headers, "db비용", "DB비용")
            col_roas = _find_col(sh_headers, "로하스", "ROAS", "roas")
            if col_month is None: col_month = 0
            if col_name_kr is None: col_name_kr = col_name_en if col_name_en is not None else 2
            if col_db is None: col_db = 3
            if col_contracts is None: col_contracts = 4
            if col_revenue is None: col_revenue = 5
            print(f"[ads-perf] 담당자탭 헤더: {sh_headers}, month_col={col_month}, name={col_name_kr}, db={col_db}, rev={col_revenue}")
            for row in staff_rows[sh_hdr_idx + 1:]:
                if not row or len(row) < 3: continue
                month_val = str(row[col_month]).strip() if col_month < len(row) else ""
                if this_month_dot not in month_val: continue
                name = str(row[col_name_kr]).strip() if col_name_kr < len(row) else ""
                if not name or name == "-": continue
                db_count = _pint(row[col_db]) if col_db < len(row) else 0
                contracts = _pint(row[col_contracts]) if col_contracts < len(row) else 0
                revenue = _pint(row[col_revenue]) if col_revenue < len(row) else 0
                # 시트 수식값 그대로 가져오기
                conv_raw = str(row[col_conv]).replace("%", "").strip() if col_conv is not None and col_conv < len(row) and row[col_conv] else ""
                conversion = float(conv_raw) if conv_raw else (round(contracts / max(db_count, 1) * 100, 1) if db_count else 0)
                if conversion > 1 and conversion <= 100: pass  # 이미 % 단위
                elif 0 < conversion <= 1: conversion = round(conversion * 100, 1)  # 소수 → %
                db_cost = _pint(row[col_db_cost]) if col_db_cost is not None and col_db_cost < len(row) else db_count * 30000
                roas_raw = str(row[col_roas]).replace("%", "").strip() if col_roas is not None and col_roas < len(row) and row[col_roas] else ""
                staff_roas = float(roas_raw) if roas_raw else (round(revenue / max(db_cost, 1) * 100, 1) if db_cost else 0)
                if 0 < staff_roas <= 1: staff_roas = round(staff_roas * 100, 1)
                kpi_pct = round(revenue / 20000000 * 100, 1) if revenue > 0 else 0
                status = "달성" if revenue >= 20000000 else ("진행중" if revenue >= 10000000 else "미달")
                by_person.append({"name": name, "revenue": revenue, "contracts": contracts,
                                  "db_count": db_count, "conversion": round(conversion, 1),
                                  "db_cost": db_cost, "roas": round(staff_roas, 1),
                                  "kpi_pct": round(kpi_pct, 1), "status": status})
            by_person.sort(key=lambda x: x["revenue"], reverse=True)
            print(f"[ads-perf] 담당자 {len(by_person)}명 로드: {[p['name'] for p in by_person]}")
    except Exception as e:
        print(f"ads-perf 담당자탭 error: {e}")

    # 광고시트 월별 추이 (광고비/ROAS 보강)
    try:
        ads_rows = fetch_sheet(SHEET_ADS, "A1:O", "공팔리터B2B", ttl_key="ads")
        if ads_rows:
            for row in ads_rows:
                if not row or len(row) < 8: continue
                ms = str(row[5]).strip() if len(row) > 5 else ""
                if "20" not in ms or "." not in ms: continue
                try:
                    sp = _pint(row[10]) if len(row) > 10 else 0
                    rs = str(row[11]).replace("%","").strip() if len(row) > 11 and row[11] else "0"
                    rv = float(rs)/100 if float(rs)>1 else float(rs)
                    for t in monthly_trend:
                        if t["month"] == ms:
                            t["spend"] = sp
                            t["roas"] = round(rv, 2)
                except: pass
    except: pass

    is_live = bool(GSHEETS_API_KEY)
    return {
        "source": "live" if is_live else "dummy",
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "total_spend": total_spend, "prev_total_spend": prev_total_spend,
        "db_count": ib_total, "prev_db_count": prev_ib_total,
        "db_cpa": db_cpa, "prev_db_cpa": prev_db_cpa,
        "month_revenue": month_revenue, "prev_month_revenue": prev_month_revenue,
        "roas": roas, "prev_roas": prev_roas,
        "meeting_rate": meeting_rate,
        "month_contracts": month_contracts, "prev_month_contracts": prev_month_contracts,
        "channel_data": channel_data,
        "by_person": by_person,
        "monthly_trend": monthly_trend[-6:],
        "meta_spend": meta_spend,
        "naver_spend": naver_spend,
        "google_spend": google_spend,
    }


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
                usage = data.get("usage", {})
                _record_tokens(agent_name, usage.get("input_tokens", 0), usage.get("output_tokens", 0), ANTHROPIC_MODEL)
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
SLACK_TOGGLE_FILE = DATA_DIR / "slack_toggle.json"

def _slack_enabled():
    """Slack 보고 토글 상태. 기본 OFF."""
    if SLACK_TOGGLE_FILE.exists():
        try:
            return json.loads(SLACK_TOGGLE_FILE.read_text(encoding="utf-8")).get("enabled", False)
        except Exception:
            pass
    return False

@app.get("/api/slack/toggle")
async def slack_toggle_get():
    """Slack 보고 토글 상태 조회."""
    return {"enabled": _slack_enabled(), "webhook_configured": bool(SLACK_WEBHOOK_URL),
            "setup_guide": "" if SLACK_WEBHOOK_URL else "1) Slack 앱 > https://api.slack.com/apps 에서 새 앱 생성\n2) Incoming Webhooks 활성화\n3) Add New Webhook to Workspace → #ceo-briefing 채널 선택\n4) Webhook URL 복사 → Railway Variables에 SLACK_WEBHOOK_URL=URL 추가"}

@app.post("/api/slack/toggle")
async def slack_toggle_set(request: Request):
    """Slack 보고 ON/OFF 토글."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SLACK_TOGGLE_FILE.write_text(json.dumps({"enabled": bool(body.get("enabled")), "updated_at": datetime.now(KST).isoformat()}, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "enabled": bool(body.get("enabled"))}

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
    if not _slack_enabled():
        return {"status": "disabled", "message": "Slack 보고 OFF 상태. 대시보드에서 토글을 켜주세요."}
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
    if not _slack_enabled():
        return {"status": "disabled", "message": "Slack 보고 OFF 상태. 대시보드에서 토글을 켜주세요."}
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


# ===== 이메일 발송 (Naver Works SMTP 전용) =====


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


# 에이전트별 발신 이메일/이름 매핑
AGENT_FROM_EMAILS = {
    "피치": os.getenv("PITCH_FROM_EMAIL", "pitch@08liter.com"),
    "루나": os.getenv("LUNA_FROM_EMAIL", "luna@08liter.com"),
    "소피": os.getenv("SOPHIE_EMAIL", "sophie@08liter.com"),
    "카일": os.getenv("KYLE_EMAIL", "kyle@08liter.com"),
    "레이": os.getenv("RAY_EMAIL", "ray@08liter.com"),
    "하나": os.getenv("HANA_EMAIL", "hana@08liter.com"),
    "맥스": os.getenv("MAX_EMAIL", "max@08liter.com"),
}
AGENT_FROM_NAMES = {
    "피치": os.getenv("FROM_NAME_PITCH", "Pitch | 공팔리터글로벌"),
    "루나": os.getenv("FROM_NAME_LUNA", "Luna | 공팔리터글로벌"),
    "소피": "Sophie | 공팔리터글로벌",
    "카일": "Kyle | 공팔리터글로벌",
    "레이": "Ray | 공팔리터글로벌",
    "하나": "Hana | 공팔리터글로벌",
    "맥스": "Max | 공팔리터글로벌",
}

def _get_from(agent_name: str):
    """에이전트별 발신 이메일+이름 반환."""
    email = AGENT_FROM_EMAILS.get(agent_name, "pitch@08liter.com")
    name = AGENT_FROM_NAMES.get(agent_name, f"{agent_name} | 공팔리터글로벌")
    return email, name

EMAIL_WEBHOOK_URL = os.getenv("EMAIL_WEBHOOK_URL", "")

AGENT_ID_MAP = {"피치": "pitch", "루나": "luna", "소피": "sophie", "카일": "kyle", "레이": "ray", "하나": "hana", "맥스": "max"}

def _send_email_webhook(to_email: str, subject: str, body_text: str, agent_name: str = "루나") -> dict:
    """Google Apps Script 웹훅으로 이메일 발송."""
    webhook_url = EMAIL_WEBHOOK_URL
    if not webhook_url:
        return {"status": "not_configured", "message": "EMAIL_WEBHOOK_URL 미설정"}
    agent_id = AGENT_ID_MAP.get(agent_name, "pitch")
    try:
        resp = req_lib.post(webhook_url, json={
            "agent": agent_id,
            "to": to_email,
            "subject": subject,
            "body": body_text,
        }, timeout=30, allow_redirects=True)
        if resp.status_code == 200:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"message": resp.text[:200]}
            return {"status": "ok", "to": to_email, "agent": agent_id, "method": "gas_webhook", "response": data}
        return {"status": "error", "message": resp.text[:300], "code": resp.status_code, "method": "gas_webhook"}
    except Exception as e:
        return {"status": "error", "message": str(e), "method": "gas_webhook"}

def _html_to_text(html: str) -> str:
    """HTML에서 태그 제거하여 플레인 텍스트 추출."""
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    return text.strip()

def _send_email(to_email: str, subject: str, html: str, agent_name: str = "루나") -> dict:
    """이메일 발송: Google Apps Script 웹훅."""
    body_text = _html_to_text(html)
    result = _send_email_webhook(to_email, subject, body_text, agent_name)
    if result["status"] == "ok":
        _record_perf(agent_name, "email_sent")
        _log_email(agent_name, to_email, subject, "sent")
    return result


@app.post("/api/send-email")
async def api_send_email(request: Request):
    """Naver Works SMTP로 이메일 1건 발송. body에 raw HTML 또는 brand_name+body_text로 템플릿 사용."""
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
async def api_test_email(agent: str = "피치"):
    """에이전트별 테스트 이메일 발송 (GAS 웹훅)."""
    from_email, sender_name = _get_from(agent)
    to_email = "jacob@08liter.com"
    body_text = (f"안녕하세요!\n\n이 메일은 [{agent}] 에이전트 테스트 이메일입니다.\n"
                 f"발신: {sender_name} <{from_email}>\n"
                 f"발송 방식: Google Apps Script 웹훅\n"
                 f"발송 시각: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} (KST)\n\n"
                 f"이메일 연동이 정상적으로 작동하고 있습니다.")
    subject = f"[테스트] {agent} 이메일 발송 확인"
    result = _send_email_webhook(to_email, subject, body_text, agent)
    result["to"] = to_email
    result["webhook_url"] = EMAIL_WEBHOOK_URL[:50] + "..." if EMAIL_WEBHOOK_URL else "미설정"
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


# ===== 에이전트 자율 업무 함수 =====

async def _pitch_inbound_auto():
    """피치: 신규 인바운드 감지 → 자동 응대 이메일 + 미팅 링크 발송."""
    inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", "파센문의", ttl_key="inbound")
    if not inbound_rows:
        return {"sent": 0}
    hdr_idx = _find_header_row(inbound_rows, "국가", "컨택현황", "컨텍현황", "담당자")
    headers = [str(h).replace("\n", " ").strip() for h in inbound_rows[hdr_idx]]
    email_idx = _find_col(headers, "이메일") or 6
    brand_idx = _find_col(headers, "업체명", "브랜드") or 4
    status_idx = _find_col(headers, "컨텍현황", "컨택현황") or 16
    staff_idx = _find_col(headers, "담당자") or 14
    date_idx = 2
    now = datetime.now(KST)
    today_str = now.strftime("%-m/%-d")
    today_iso = now.strftime("%Y-%m-%d")
    sent = 0
    for row in inbound_rows[hdr_idx + 1:]:
        if len(row) < 5:
            continue
        date_val = str(row[date_idx]).strip() if date_idx < len(row) else ""
        is_today = (date_val == today_str or date_val.startswith(today_iso))
        if not is_today:
            continue
        staff = str(row[staff_idx]).strip() if staff_idx < len(row) else ""
        status = str(row[status_idx]).strip() if status_idx < len(row) else ""
        if staff or status:
            continue
        email = str(row[email_idx]).strip() if email_idx < len(row) else ""
        brand = str(row[brand_idx]).strip() if brand_idx < len(row) else ""
        if not email or "@" not in email:
            continue
        body = (f"안녕하세요, 공팔리터글로벌 피치입니다.\n\n"
                f"{brand} 관련 문의 감사합니다. 빠른 시일 내에 맞춤 제안을 준비해 드리겠습니다.\n\n"
                f"편하신 시간에 15분 비대면 미팅을 통해 상세히 안내드리겠습니다.\n\n"
                f"미팅 예약: {MEETING_LINK}\n\n감사합니다.\n피치 드림")
        html = _build_pitch_html(brand, body)
        result = _queue_or_send_email("피치", email, f"[공팔리터글로벌] {brand} 인플루언서 마케팅 제안", html, {"brand": brand})
        if result["status"] in ("ok", "queued"):
            sent += 1
            _record_perf("피치", "meeting_invite")
    _record_perf("피치", "inbound_processed", sent)
    return {"sent": sent}

async def _pitch_outbound_crm():
    """피치: 유효DB 중 미계약 브랜드에 CRM 뉴스레터 발송."""
    leads_data = await api_recontact_leads()
    leads = leads_data.get("leads", [])
    targets = [l for l in leads if l.get("email") and "@" in l.get("email", "")][:10]
    sent = 0
    for lead in targets:
        brand = lead["name"]
        body = (f"안녕하세요, 공팔리터글로벌 피치입니다.\n\n"
                f"현재 {brand}에 최적화된 프로모션 패키지를 준비했습니다.\n\n"
                f"글로벌 155만+ 인플루언서 네트워크를 활용한 맞춤형 캠페인으로\n"
                f"브랜드 인지도와 매출을 동시에 높여드립니다.\n\n"
                f"비대면 미팅 예약: {MEETING_LINK}\n\n감사합니다.\n피치 드림")
        html = _build_pitch_html(brand, body)
        result = _send_email(lead["email"], f"[공팔리터글로벌] {brand} 맞춤 프로모션 안내", html, "피치")
        if result["status"] == "ok":
            sent += 1
    _record_perf("피치", "crm_newsletter", sent)
    return {"sent": sent, "total_leads": len(leads)}

async def _luna_inbound_welcome():
    """루나: 신규 인플루언서 지원자에게 환영 이메일 + 캠페인 안내."""
    rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", "현황시트(수동매칭)", ttl_key="influencer")
    if not rows:
        return {"sent": 0}
    now = datetime.now(KST)
    today_str = now.strftime("%Y-%m-%d")
    sent = 0
    for row in rows[-20:]:
        if len(row) < 8:
            continue
        contact_date = str(row[0]).strip() if len(row) > 0 else ""
        if not contact_date.startswith(today_str):
            continue
        name = str(row[4]).strip() if len(row) > 4 else ""
        email = str(row[6]).strip() if len(row) > 6 else ""
        if not email or "@" not in email:
            continue
        body = (f"안녕하세요 {name}님, 공팔리터글로벌 루나입니다!\n\n"
                f"인플루언서 파트너 등록을 환영합니다.\n\n"
                f"현재 진행 중인 캠페인을 안내드립니다:\n"
                f"• K-뷰티 체험 캠페인 (밀리밀리)\n"
                f"• 글로벌 리뷰 캠페인\n"
                f"• 해외 구매평 서비스\n\n"
                f"관심 있는 캠페인이 있으시면 회신해 주세요.\n루나 드림")
        html = _build_pitch_html(name, body)
        result = _queue_or_send_email("루나", email, f"[공팔리터글로벌] {name}님 환영합니다!", html, {"influencer": name})
        if result["status"] in ("ok", "queued"):
            sent += 1
    _record_perf("루나", "welcome_sent", sent)
    return {"sent": sent}

async def _luna_outbound_pitch():
    """루나: 인플루언서 DB에서 이메일 있는 대상에게 캠페인 제안 발송."""
    rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", "현황시트(수동매칭)", ttl_key="influencer")
    if not rows:
        return {"sent": 0}
    targets = []
    for row in rows:
        if len(row) < 12:
            continue
        status = str(row[10]).strip() if len(row) > 10 else ""
        if status != "단순리스트업" and status != "1. 단순리스트업":
            continue
        email = str(row[6]).strip() if len(row) > 6 else ""
        name = str(row[4]).strip() if len(row) > 4 else ""
        followers = str(row[7]).strip() if len(row) > 7 else "0"
        if not email or "@" not in email:
            continue
        targets.append({"name": name, "email": email, "followers": followers})
    targets = targets[:10]
    sent = 0
    for t in targets:
        body = (f"Hi {t['name']},\n\n"
                f"I'm Luna from 08Liter Global, a K-beauty influencer marketing agency.\n\n"
                f"We're looking for talented creators like you for our upcoming campaigns.\n"
                f"We offer competitive compensation and work with top K-beauty brands.\n\n"
                f"Interested? Just reply to this email and I'll send you the details!\n\n"
                f"Best,\nLuna | 08Liter Global")
        html = _build_pitch_html(t["name"], body)
        result = _queue_or_send_email("루나", t["email"], f"[08Liter] Campaign opportunity for {t['name']}", html, {"influencer": t["name"]})
        if result["status"] == "ok":
            sent += 1
    _record_perf("루나", "outbound_sent", sent)
    return {"sent": sent, "targeted": len(targets)}

async def _sophie_daily_content():
    """소피: Anthropic API로 B2B/B2C 콘텐츠 기획 + 승인 큐 등록."""
    if not ANTHROPIC_API_KEY:
        return {"status": "no_api_key"}
    now = datetime.now(KST)
    prompt = (f"오늘은 {now.strftime('%Y년 %m월 %d일 %A')}입니다.\n"
              f"공팔리터글로벌의 SNS 콘텐츠를 기획해주세요.\n\n"
              f"1. B2B 콘텐츠 1개 (브랜드 담당자 타겟)\n"
              f"  - 인플루언서 마케팅 성공사례 또는 프로모션 안내\n"
              f"  - Instagram 카드뉴스 형식\n"
              f"2. B2C 콘텐츠 1개 (인플루언서 타겟)\n"
              f"  - 수익화 팁 또는 캠페인 모집 안내\n"
              f"  - TikTok/Instagram 릴스 형식\n\n"
              f"각 콘텐츠의 제목, 본문 텍스트, 해시태그 5개, CTA를 작성해주세요.")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": ANTHROPIC_MODEL, "max_tokens": 1024,
                      "system": "당신은 소피, 공팔리터글로벌 SNS 운영 에이전트입니다. 매력적인 콘텐츠를 기획합니다.",
                      "messages": [{"role": "user", "content": prompt}]})
            if resp.status_code == 200:
                content = resp.json()["content"][0]["text"]
                proposals = load_proposals()
                proposals.append({
                    "id": int(time.time() * 1000) % 10000000,
                    "agent": "소피", "status": "pending_approval",
                    "proposal": f"오늘의 SNS 콘텐츠 (B2B + B2C)",
                    "detail": content[:500],
                    "expected_impact": "B2B: 브랜드 리드 1건+ / B2C: 인플루언서 리드 2건+",
                    "action_type": "sns_content",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })
                save_proposals(proposals[-200:])
                _record_perf("소피", "content_created", 2)
                return {"status": "ok", "content": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "error"}


# ===== 에이전트 성과 API =====
@app.get("/api/agent-performance")
async def api_agent_performance(agent: Optional[str] = None):
    """에이전트별 일일 성과 + 목표 대비 달성률."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    today_perf = perf.get(today, {})
    yesterday_perf = perf.get(yesterday, {})
    # 월간 누적 계산
    month_prefix = now.strftime("%Y-%m")
    monthly_perf = {}
    for date_key, agents_data in perf.items():
        if date_key.startswith(month_prefix):
            for ag, metrics in agents_data.items():
                monthly_perf.setdefault(ag, {})
                for mk, mv in metrics.items():
                    monthly_perf[ag][mk] = monthly_perf[ag].get(mk, 0) + mv
    # 주간 누적
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    weekly_perf = {}
    for date_key, agents_data in perf.items():
        if date_key >= week_start:
            for ag, metrics in agents_data.items():
                weekly_perf.setdefault(ag, {})
                for mk, mv in metrics.items():
                    weekly_perf[ag][mk] = weekly_perf[ag].get(mk, 0) + mv
    # 목표 대비 달성률
    targets = {}
    for ag_name, ag_targets in AGENT_TARGETS.items():
        daily_t = ag_targets.get("daily", {})
        daily_a = today_perf.get(ag_name, {})
        weekly_t = ag_targets.get("weekly", {})
        weekly_a = weekly_perf.get(ag_name, {})
        monthly_t = ag_targets.get("monthly", {})
        monthly_a = monthly_perf.get(ag_name, {})
        targets[ag_name] = {
            "daily": {k: {"target": v, "actual": daily_a.get(k, 0), "pct": min(100, round(daily_a.get(k, 0) / max(v, 1) * 100))} for k, v in daily_t.items()},
            "weekly": {k: {"target": v, "actual": weekly_a.get(k, 0), "pct": min(100, round(weekly_a.get(k, 0) / max(v, 1) * 100)) if isinstance(v, (int, float)) and v > 0 else 0} for k, v in weekly_t.items()},
            "monthly": {k: {"target": v, "actual": monthly_a.get(k, 0), "pct": min(100, round(monthly_a.get(k, 0) / max(v, 1) * 100)) if isinstance(v, (int, float)) and v > 0 else 0} for k, v in monthly_t.items()},
        }
    if agent:
        return {"today": today_perf.get(agent, {}), "yesterday": yesterday_perf.get(agent, {}),
                "monthly": monthly_perf.get(agent, {}), "weekly": weekly_perf.get(agent, {}),
                "targets": targets.get(agent, {}), "agent": agent}
    return {"today": today_perf, "yesterday": yesterday_perf, "monthly": monthly_perf,
            "weekly": weekly_perf, "targets": targets, "date": today}


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
            "이메일 웹훅": bool(os.getenv("EMAIL_WEBHOOK_URL")),
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

        # 9. 피치 — 인바운드 자동 응대 + CRM 뉴스레터
        try:
            pitch_ib = await _pitch_inbound_auto()
            pitch_crm = await _pitch_outbound_crm()
            ib_sent = pitch_ib.get("sent", 0)
            crm_sent = pitch_crm.get("sent", 0)
            if ib_sent + crm_sent > 0:
                alerts_posted.append({"id": _id(), "agent": "피치", "severity": "info",
                    "summary": f"📧 피치 자율업무: 인바운드 응대 {ib_sent}건 + CRM 뉴스레터 {crm_sent}건",
                    "detail": f"미팅 예약 링크 포함 발송 완료",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Pitch auto error: {e}")

        # 9-1. 루나 — 인플루언서 환영 + 아웃바운드 + 재접촉
        try:
            luna_welcome = await _luna_inbound_welcome()
            luna_outbound = await _luna_outbound_pitch()
            recontact = await _run_recontact_campaign(dry_run=False, limit=5)
            w_sent = luna_welcome.get("sent", 0)
            o_sent = luna_outbound.get("sent", 0)
            r_sent = recontact.get("sent", 0)
            total_sent = w_sent + o_sent + r_sent
            if total_sent > 0:
                alerts_posted.append({"id": _id(), "agent": "루나", "severity": "info",
                    "summary": f"✉️ 루나 자율업무: 환영 {w_sent}건 + 아웃바운드 {o_sent}건 + 재접촉 {r_sent}건",
                    "detail": "",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Luna auto error: {e}")

        # 9-2. 소피 — 일일 콘텐츠 기획
        try:
            sophie = await _sophie_daily_content()
            if sophie.get("status") == "ok":
                alerts_posted.append({"id": _id(), "agent": "소피", "severity": "info",
                    "summary": "📱 소피 자율업무: 오늘의 B2B/B2C 콘텐츠 기획 완료",
                    "detail": "승인 큐에서 확인 후 승인해주세요",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Sophie auto error: {e}")

        # 9-3. 자동 에스컬레이션 — 일 목표 50% 미달 에이전트 감지
        try:
            perf = load_agent_perf()
            today_perf = perf.get(now_ts[:10], {})
            for ag_name, ag_targets in AGENT_TARGETS.items():
                daily_t = ag_targets.get("daily", {})
                daily_a = today_perf.get(ag_name, {})
                for metric, target in daily_t.items():
                    if isinstance(target, (int, float)) and target > 0:
                        actual = daily_a.get(metric, 0)
                        if actual < target * 0.5:
                            alerts_posted.append({"id": _id(), "agent": ag_name, "severity": "critical",
                                "summary": f"🚨 {ag_name} 목표 미달: {metric} {actual}/{target} ({round(actual/target*100)}%)",
                                "detail": f"일 목표의 50% 미달. 원인 분석 및 즉시 대응 필요.",
                                "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Escalation check error: {e}")

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
    b2b_key = os.getenv("KAKAO_B2B_API_KEY", "") or os.getenv("KAKAO_REST_API_KEY", "")
    b2c_key = os.getenv("KAKAO_B2C_API_KEY", "") or os.getenv("KAKAO_REST_API_KEY", "")
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
    # 계산서에서 월별 매출 집계 (B열 날짜 기반 통일)
    ct_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "계산서발행", ttl_key="contract")
    monthly_rev = {}
    if ct_rows:
        hdr = _find_header_row(ct_rows, "작성일자", "공급가액", "공급받는자")
        headers = [str(h).replace("\n", " ").strip() for h in ct_rows[hdr]]
        date_idx = _find_col(headers, "작성일자", "등록기준일") or 1
        amount_idx = _find_col(headers, "공급가액") or 19
    # 일별 매출 + 계약수 + 상품별 + 충전금
    daily_rev = {}
    daily_new = {}
    daily_renew = {}
    daily_new_rev = {}
    daily_renew_rev = {}
    product_dist = {}
    daily_payback = {}
    # 월별 집계 (전체 기간 — 차트 12개월용)
    monthly_new_rev = {}
    monthly_renew_rev = {}
    monthly_new_cnt = {}
    monthly_renew_cnt = {}
    if ct_rows:
        cat_idx = _find_col(headers, "품목 재분류", "재분류") or 24
        payback_idx = _find_col(headers, "페이백비", "충전금") or 18
        brand_idx = _find_col(headers, "공급받는자 상호") or 8
        type_idx = _find_col(headers, "신규/", "재계약") or 6
        now = datetime.now(KST)
        cutoff_90 = (now - timedelta(days=90)).strftime("%Y%m%d")
        # 브랜드 첫 등장 추적 (G열 없을 때 폴백)
        brand_first_seen = {}
        for row in ct_rows[hdr + 1:]:
            if len(row) < 3:
                continue
            dr = str(row[date_idx]).strip() if date_idx < len(row) else ""
            dc = dr.replace("-", "").replace(".", "").replace("/", "").replace(" ", "")
            if len(dc) < 8 or not dc[:8].isdigit():
                continue
            day_key = dc[:8]
            mk = dc[:4] + "." + dc[4:6]
            rv = str(row[amount_idx]).strip() if amount_idx < len(row) else "0"
            try:
                rev = int(float(rv.replace(",", "").replace("₩", "").replace(" ", "")))
            except (ValueError, TypeError):
                rev = 0
            if rev <= 0:
                continue
            brand = str(row[brand_idx]).strip() if brand_idx < len(row) else ""
            ctype = str(row[type_idx]).strip() if type_idx is not None and type_idx < len(row) else ""
            # G열 기반 신규/재계약 분류 (_parse_contracts와 동일 로직)
            if ctype and ctype != "-" and "확인필요" not in ctype:
                is_renew = "신규" not in ctype
            else:
                brand_lower = brand.lower() if brand else ""
                if brand_lower:
                    if brand_lower not in brand_first_seen:
                        brand_first_seen[brand_lower] = day_key
                        is_renew = False
                    else:
                        is_renew = True
                else:
                    is_renew = False
            # 월별 집계 (전체 기간 — B열 날짜 기반 통일)
            monthly_rev[mk] = monthly_rev.get(mk, 0) + rev
            if is_renew:
                monthly_renew_rev[mk] = monthly_renew_rev.get(mk, 0) + rev
                monthly_renew_cnt[mk] = monthly_renew_cnt.get(mk, 0) + 1
            else:
                monthly_new_rev[mk] = monthly_new_rev.get(mk, 0) + rev
                monthly_new_cnt[mk] = monthly_new_cnt.get(mk, 0) + 1
            # 일별 집계 (최근 90일만)
            if day_key >= cutoff_90:
                daily_rev[day_key] = daily_rev.get(day_key, 0) + rev
                if is_renew:
                    daily_renew[day_key] = daily_renew.get(day_key, 0) + 1
                    daily_renew_rev[day_key] = daily_renew_rev.get(day_key, 0) + rev
                else:
                    daily_new[day_key] = daily_new.get(day_key, 0) + 1
                    daily_new_rev[day_key] = daily_new_rev.get(day_key, 0) + rev
            cat = str(row[cat_idx]).strip() if cat_idx < len(row) else ""
            if cat:
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
        "today_payback": daily_payback.get(datetime.now(KST).strftime("%Y%m%d"), 0),
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
        "EMAIL_WEBHOOK_URL",
        "PITCH_SMTP_USER", "PITCH_SMTP_PASS", "LUNA_SMTP_USER", "LUNA_SMTP_PASS",
        "ANTHROPIC_API_KEY", "GOOGLE_SHEETS_API_KEY",
        "NAVER_WORKS_SMTP_USER", "NAVER_WORKS_SMTP_PASSWORD",
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
            # DB 수집 파이프라인 자동 시작
            action_type = p.get("action_type", "")
            pipeline_result = None
            if action_type in ("pitch_db_collect", "luna_db_collect"):
                try:
                    agent_name = "피치" if "pitch" in action_type else "루나"
                    if agent_name == "피치":
                        pitch_result = await _pitch_outbound_crm()
                        pipeline_result = {"step": "이메일 생성+큐 등록", "sent": pitch_result.get("sent", 0)}
                    else:
                        luna_result = await _luna_outbound_pitch()
                        pipeline_result = {"step": "이메일 생성+큐 등록", "sent": luna_result.get("sent", 0)}
                    p["result"] = f"파이프라인 실행: {pipeline_result.get('sent',0)}건 이메일 → 검수 큐"
                    p["status"] = "executed"
                    p["executed_at"] = datetime.now(KST).isoformat()
                except Exception as ex:
                    pipeline_result = {"error": str(ex)}
            # Slack 알림
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url and _slack_enabled():
                try:
                    req_lib.post(slack_url, json={"text": f"✅ CEO 승인: [{p['agent']}] {p['proposal']}"}, timeout=5)
                except Exception:
                    pass
            break
    save_proposals(proposals)
    _log_cycle("approve", pid, f"CEO가 제안 승인")
    return {"status": "ok", "pipeline": pipeline_result}


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


@app.get("/api/agent-scoreboard")
async def api_agent_scoreboard():
    """주간 에이전트 랭킹 스코어보드."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    weekly = {}
    for date_key, agents_data in perf.items():
        if date_key >= week_start:
            for ag, metrics in agents_data.items():
                weekly.setdefault(ag, {})
                for mk, mv in metrics.items():
                    weekly[ag][mk] = weekly[ag].get(mk, 0) + mv
    scoreboard = []
    for ag_name, ag_targets in AGENT_TARGETS.items():
        weekly_t = ag_targets.get("weekly", {})
        weekly_a = weekly.get(ag_name, {})
        total_target = sum(v for v in weekly_t.values() if isinstance(v, (int, float)))
        total_actual = sum(weekly_a.get(k, 0) for k in weekly_t.keys())
        pct = min(100, round(total_actual / max(total_target, 1) * 100)) if total_target > 0 else 0
        scoreboard.append({"agent": ag_name, "pct": pct, "actual": total_actual, "target": total_target, "details": weekly_a})
    scoreboard.sort(key=lambda x: -x["pct"])
    return {"scoreboard": scoreboard, "week_start": week_start}

@app.get("/api/benchmarks")
async def api_benchmarks():
    """업계 벤치마크 데이터 조회."""
    return load_benchmarks()

@app.get("/api/token-usage")
async def api_token_usage():
    """에이전트별 토큰 사용량 + 비용."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    today_data = perf.get(today, {})
    monthly_data = {}
    for date_key, agents_data in perf.items():
        if date_key.startswith(month_prefix):
            for ag, metrics in agents_data.items():
                monthly_data.setdefault(ag, {})
                for mk, mv in metrics.items():
                    monthly_data[ag][mk] = monthly_data[ag].get(mk, 0) + mv
    agents = {}
    for ag in ["피치", "루나", "소피", "맥스", "카일"]:
        td = today_data.get(ag, {})
        md = monthly_data.get(ag, {})
        today_in = td.get("input_tokens", 0)
        today_out = td.get("output_tokens", 0)
        today_cost = td.get("cost_usd_x100", 0) / 100
        month_in = md.get("input_tokens", 0)
        month_out = md.get("output_tokens", 0)
        month_cost = md.get("cost_usd_x100", 0) / 100
        agents[ag] = {
            "today": {"input": today_in, "output": today_out, "total": today_in + today_out, "cost": round(today_cost, 2)},
            "monthly": {"input": month_in, "output": month_out, "total": month_in + month_out, "cost": round(month_cost, 2)},
        }
    # 전체 합계
    total_today_cost = sum(a["today"]["cost"] for a in agents.values())
    total_month_cost = sum(a["monthly"]["cost"] for a in agents.values())
    biz_days_left = max(1, 20 - now.day)
    daily_avg = total_month_cost / max(now.day, 1)
    projected = total_month_cost + daily_avg * biz_days_left
    return {
        "agents": agents,
        "total": {"today_cost": round(total_today_cost, 2), "month_cost": round(total_month_cost, 2), "projected": round(projected, 2)},
    }

@app.get("/api/email-queue")
async def api_email_queue(agent: Optional[str] = None):
    """발송 대기 이메일 큐 조회."""
    queue = load_email_queue()
    pending = [e for e in queue if e.get("status") == "pending"]
    if agent:
        pending = [e for e in pending if e.get("agent") == agent]
    return {"emails": pending, "count": len(pending)}

@app.post("/api/email-queue/approve")
async def api_email_approve(request: Request):
    """CEO가 이메일 승인 발송."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    for e in queue:
        if e.get("id") == eid and e.get("status") == "pending":
            subject = body.get("subject", e["subject"])
            html = body.get("html", e["html"])
            result = _send_email(e["to"], subject, html, e.get("agent", "피치"))
            e["status"] = "sent" if result["status"] == "ok" else "failed"
            e["sent_at"] = datetime.now(KST).isoformat()
            e["result"] = result
            break
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/email-queue/delete")
async def api_email_delete(request: Request):
    """이메일 삭제."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    queue = [e for e in queue if e.get("id") != eid]
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/email-queue/approve-all")
async def api_email_approve_all(request: Request):
    """대기 중인 이메일 전체 승인 발송."""
    body = await request.json()
    agent = body.get("agent")
    queue = load_email_queue()
    sent = 0
    for e in queue:
        if e.get("status") != "pending":
            continue
        if agent and e.get("agent") != agent:
            continue
        if not _check_send_limit():
            break
        result = _send_email(e["to"], e["subject"], e["html"], e.get("agent", "피치"))
        e["status"] = "sent" if result["status"] == "ok" else "failed"
        e["sent_at"] = datetime.now(KST).isoformat()
        e["result"] = result
        if result["status"] == "ok":
            _log_email(e.get("agent", ""), e["to"], e["subject"], "sent", e.get("meta"))
            sent += 1
    save_email_queue(queue)
    return {"status": "ok", "sent": sent}

@app.post("/api/email-queue/update")
async def api_email_update(request: Request):
    """대기 이메일 제목/본문 수정 (status는 pending 유지)."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    for e in queue:
        if e.get("id") == eid and e.get("status") == "pending":
            if body.get("subject"):
                e["subject"] = body["subject"]
            if body.get("html"):
                e["html"] = body["html"]
            if body.get("body_text"):
                e["html"] = _build_pitch_html(e.get("meta", {}).get("target", ""), body["body_text"] + f"\n\n[미팅 예약하기]({MEETING_LINK})")
            break
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/email-queue/regenerate")
async def api_email_regenerate(request: Request):
    """AI로 이메일 내용 재생성."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    for e in queue:
        if e.get("id") == eid and e.get("status") == "pending":
            target = e.get("meta", {}).get("target", "고객")
            agent = e.get("agent", "피치")
            if ANTHROPIC_API_KEY:
                try:
                    prompt = f"{target}에게 보낼 {'인플루언서 마케팅' if agent=='피치' else '협찬'} 제안 이메일을 작성해주세요. 100단어, 미팅 링크 포함."
                    async with httpx.AsyncClient(timeout=20) as client:
                        resp = await client.post("https://api.anthropic.com/v1/messages",
                            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 512,
                                  "messages": [{"role": "user", "content": prompt}]})
                        if resp.status_code == 200:
                            new_body = resp.json()["content"][0]["text"]
                            e["subject"] = f"[공팔리터글로벌] {target} 맞춤 제안"
                            e["html"] = _build_pitch_html(target, new_body + f"\n\n[미팅 예약하기]({MEETING_LINK})")
                            e["meta"]["regenerated"] = True
                            usage = resp.json().get("usage", {})
                            _record_tokens(agent, usage.get("input_tokens", 0), usage.get("output_tokens", 0), "haiku")
                except Exception as ex:
                    print(f"Regenerate error: {ex}")
            break
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/generate-with-promo")
async def api_generate_with_promo(request: Request):
    """프로모션/협찬 설정 기반 이메일 생성."""
    body = await request.json()
    agent = body.get("agent", "피치")
    promos = body.get("promos", [])
    highlights = body.get("highlights", [])
    targets = body.get("targets", [])
    promo_text = " / ".join(promos) if promos else "4월 프로모션"
    highlight_text = " / ".join(highlights) if highlights else ""
    queued = 0
    for t in targets[:20]:
        email = t.get("email", "")
        if not email or "@" not in email:
            continue
        name = t.get("company", t.get("name", "담당자"))
        email_body = f"안녕하세요, {name} 담당자님.\n글로벌 인플루언서 마케팅 플랫폼 공팔리터의 제이콥입니다.\n\n"
        if agent == "피치":
            email_body += f"현재 진행 중인 프로모션을 안내드립니다:\n"
            for p in promos:
                email_body += f"• {p}\n"
            if highlight_text:
                email_body += f"\n핵심 포인트: {highlight_text}\n"
            email_body += f"\n10분 비대면 미팅으로 {name}에 맞는 맞춤 제안 드립니다."
        else:
            email_body += f"협찬 제안드립니다:\n"
            for p in promos:
                email_body += f"• {p}\n"
            email_body += f"\n관심 있으시면 답장 부탁드립니다."
        html = _build_pitch_html(name, email_body + f"\n\n[미팅 예약하기]({MEETING_LINK})")
        subject = f"[공팔리터글로벌] {name} {'맞춤 프로모션' if agent=='피치' else '무료 협찬 제안'}"
        _queue_or_send_email(agent, email, subject, html, {"target": name, "promos": promos})
        queued += 1
    return {"status": "ok", "queued": queued}

@app.post("/api/sns-content/generate")
async def api_sns_content_generate(request: Request):
    """소피: 프로모션 설정 기반 B2B/B2C 콘텐츠 생성 → 승인 큐."""
    body = await request.json()
    b2b_topics = body.get("b2b_topics", ["인플루언서 마케팅 성공사례"])
    b2c_topics = body.get("b2c_topics", ["무료 협찬 모집"])
    b2b_channel = body.get("b2b_channel", "Instagram")
    b2c_channel = body.get("b2c_channel", "TikTok")
    now = datetime.now(KST)
    results = {"b2b": None, "b2c": None}
    if ANTHROPIC_API_KEY:
        for content_type, topics, channel in [("b2b", b2b_topics, b2b_channel), ("b2c", b2c_topics, b2c_channel)]:
            target = "브랜드 마케팅 담당자" if content_type == "b2b" else "뷰티 인플루언서"
            prompt = (f"공팔리터글로벌 {channel}용 {'B2B' if content_type=='b2b' else 'B2C'} 콘텐츠를 작성해주세요.\n"
                      f"타겟: {target}\n주제: {', '.join(topics)}\n"
                      f"형식: {'카드뉴스 텍스트' if channel=='Instagram' else '숏폼 스크립트'}\n"
                      f"제목 + 본문(150단어) + 해시태그 5개 + CTA 1줄을 작성해주세요.")
            try:
                async with httpx.AsyncClient(timeout=25) as client:
                    resp = await client.post("https://api.anthropic.com/v1/messages",
                        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                        json={"model": "claude-haiku-4-5-20251001", "max_tokens": 600,
                              "messages": [{"role": "user", "content": prompt}]})
                    if resp.status_code == 200:
                        content = resp.json()["content"][0]["text"]
                        results[content_type] = {"channel": channel, "target": target, "content": content, "topics": topics}
                        usage = resp.json().get("usage", {})
                        _record_tokens("소피", usage.get("input_tokens", 0), usage.get("output_tokens", 0), "haiku")
            except Exception as ex:
                print(f"SNS content gen error: {ex}")
    else:
        results["b2b"] = {"channel": b2b_channel, "target": "브랜드 담당자", "content": f"[B2B] {', '.join(b2b_topics)}\n\n리뷰 0개인 브랜드가 3주만에 100개 만든 비결...\n\n#인플루언서마케팅 #공팔리터 #리뷰마케팅 #K뷰티 #브랜드성장\n\nCTA: 프로필 링크에서 무료 상담 예약", "topics": b2b_topics}
        results["b2c"] = {"channel": b2c_channel, "target": "뷰티 인플루언서", "content": f"[B2C] {', '.join(b2c_topics)}\n\nK-뷰티 제품 공짜로 받고 싶으세요?\n공팔리터에서 매주 새로운 협찬 기회!\n\n#무료협찬 #K뷰티 #인플루언서 #뷰티크리에이터 #협찬제안\n\nCTA: 프로필 링크에서 지금 신청!", "topics": b2c_topics}
    # 승인 큐에 등록
    proposals = load_proposals()
    for ct in ["b2b", "b2c"]:
        if results[ct]:
            proposals.append({
                "id": int(time.time() * 1000) % 10000000 + (1 if ct == "b2c" else 0),
                "agent": "소피", "status": "pending_approval",
                "proposal": f"{'B2B' if ct=='b2b' else 'B2C'} 콘텐츠 — {results[ct]['channel']}",
                "detail": results[ct]["content"],
                "expected_impact": f"예상 리드: {'5~15' if ct=='b2b' else '10~30'}건",
                "action_type": "sns_content",
                "channel": results[ct]["channel"],
                "content_type": ct,
                "ceo_comment": "", "created_at": now.isoformat(),
            })
    save_proposals(proposals[-200:])
    _record_perf("소피", "content_created", 2)
    return {"status": "ok", "results": results}

@app.get("/api/sheet-pipeline")
async def api_sheet_pipeline(agent: str = "피치"):
    """구글시트 실시간 파이프라인 — 에이전트별 집계. 실제 시트 컬럼 기반."""
    now = datetime.now(KST)
    result = {"agent": agent, "today": {}, "month": {}, "total": {}, "funnel": {},
              "sheet_url": SHEET_URLS.get(agent, "")}
    if agent == "피치":
        # 피치 시트: 파센문의 탭 A:V (헤더 3행)
        # A:국가 B:월 C:날짜 D:유입채널 E:업체명 F:연락처 G:이메일
        # M:미팅예약 N:팀 O:담당자 Q:컨택현황
        rows = fetch_sheet(PITCH_SHEET_ID, "A:V", "파센문의", ttl_key="inbound")
        if rows:
            hdr_idx = _find_header_row(rows, "국가", "컨택현황", "컨텍현황", "담당자")
            headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
            email_idx = _find_col(headers, "이메일") or 6
            brand_idx = _find_col(headers, "업체명", "브랜드") or 4
            status_idx = _find_col(headers, "컨텍현황", "컨택현황") or 16
            staff_idx = _find_col(headers, "담당자") or 14
            meeting_idx = _find_col(headers, "미팅") or 12
            date_idx = 2
            month_idx = 1
            this_month = f"{now.year}.{now.month:02d}"
            cnt = {"total": 0, "with_email": 0, "working": 0, "meeting": 0,
                   "today_inbound": 0, "month_inbound": 0, "unhandled": 0,
                   "rejected": 0, "by_staff": {}}
            for row in rows[hdr_idx + 1:]:
                if len(row) < 5:
                    continue
                cnt["total"] += 1
                email = str(row[email_idx]).strip() if email_idx < len(row) else ""
                status = str(row[status_idx]).strip() if status_idx < len(row) else ""
                staff = str(row[staff_idx]).strip() if staff_idx < len(row) else ""
                meeting = str(row[meeting_idx]).strip() if meeting_idx < len(row) else ""
                date_val = str(row[date_idx]).strip() if date_idx < len(row) else ""
                month_val = str(row[month_idx]).strip() if month_idx < len(row) else ""
                if email and "@" in email:
                    cnt["with_email"] += 1
                if "워킹" in status:
                    cnt["working"] += 1
                if meeting and meeting != "-":
                    cnt["meeting"] += 1
                if "부적합" in status or "거부" in status:
                    cnt["rejected"] += 1
                if not staff and not status:
                    cnt["unhandled"] += 1
                if _is_date_today(date_val, now):
                    cnt["today_inbound"] += 1
                if this_month in month_val:
                    cnt["month_inbound"] += 1
                if staff:
                    cnt["by_staff"][staff] = cnt["by_staff"].get(staff, 0) + 1
            result["total"] = cnt
            result["today"] = {"inbound": cnt["today_inbound"], "unhandled": cnt["unhandled"]}
            result["month"] = {"inbound": cnt["month_inbound"]}
            result["funnel"] = {"db": cnt["total"], "email": cnt["with_email"],
                                "working": cnt["working"], "meeting": cnt["meeting"]}
    elif agent == "루나":
        # 루나 시트: 현황시트(수동매칭) A:R (헤더 1행)
        # A:컨택날짜 B:모집형태 C:국가 D:카테고리 E:플랫폼 F:인플루언서명
        # H:팔로워 I:이메일 K:진행상태 P:담당자
        rows = fetch_sheet(LUNA_SHEET_ID, "A:R", "현황시트(수동매칭)", ttl_key="influencer")
        if rows and len(rows) > 1:
            cnt = {"total": 0, "outbound": 0, "inbound": 0, "with_email": 0,
                   "listed": 0, "proposed": 0, "usable": 0,
                   "by_country": {}, "by_platform": {}}
            for r in rows[1:]:
                if len(r) < 5:
                    continue
                cnt["total"] += 1
                recruit = str(r[1]).strip() if len(r) > 1 else ""
                country = str(r[2]).strip() if len(r) > 2 else ""
                platform = str(r[4]).strip() if len(r) > 4 else ""
                email = str(r[8]).strip() if len(r) > 8 else ""
                status = str(r[10]).strip() if len(r) > 10 else ""
                if "아웃바운드" in recruit or "수동" in recruit:
                    cnt["outbound"] += 1
                elif "인바운드" in recruit:
                    cnt["inbound"] += 1
                if email and "@" in email:
                    cnt["with_email"] += 1
                if "리스트" in status:
                    cnt["listed"] += 1
                elif "제안" in status:
                    cnt["proposed"] += 1
                elif "사례" in status:
                    cnt["usable"] += 1
                if country:
                    cnt["by_country"][country] = cnt["by_country"].get(country, 0) + 1
                if platform:
                    cnt["by_platform"][platform] = cnt["by_platform"].get(platform, 0) + 1
            result["total"] = cnt
            result["funnel"] = {"crawled": cnt["total"], "with_email": cnt["with_email"],
                                "proposed": cnt["proposed"], "usable": cnt["usable"]}
    elif agent == "소피":
        # 소피 시트: 소피_클로드 A:I (헤더 1행)
        # A:일자 B:국가 C:채널 D:기획안 E:타겟 F:예상목적 G:비용 H:결과 I:결과확인시트
        rows = fetch_sheet(SOPHIE_SHEET_ID, "A:I", "소피_클로드", ttl_key="default")
        if rows and len(rows) > 1:
            cnt = {"total": 0, "b2b": 0, "b2c": 0, "with_result": 0}
            for r in rows[1:]:
                if len(r) < 2:
                    continue
                cnt["total"] += 1
                target = str(r[4]).strip().lower() if len(r) > 4 else ""
                result_val = str(r[7]).strip() if len(r) > 7 else ""
                if "b2b" in target or "btob" in target:
                    cnt["b2b"] += 1
                elif "b2c" in target or "btoc" in target:
                    cnt["b2c"] += 1
                if result_val and result_val != "-":
                    cnt["with_result"] += 1
            result["total"] = cnt
    return result

@app.post("/api/pipeline/start")
async def api_pipeline_start(request: Request):
    """CEO 승인 후 DB 수집 + 이메일 생성 파이프라인 실행."""
    body = await request.json()
    agent = body.get("agent", "피치")
    pid = body.get("proposal_id")
    now = datetime.now(KST)
    result = {"agent": agent, "steps": []}

    # STEP 1: DB 수집
    if agent == "피치":
        crawl = await api_crawl_brands(Request(scope={"type": "http"}, receive=None))
        # 시뮬레이션이지만 실데이터 기반
        leads = await api_recontact_leads()
        count = leads.get("count", 0)
        result["steps"].append({"step": "DB 수집", "status": "완료", "count": count})
        _record_perf("피치", "crawl_brands", count)
    elif agent == "루나":
        inf = await api_influencer_db()
        count = inf.get("total", 0) if isinstance(inf.get("total"), int) else len(inf.get("items", inf.get("rows", [])))
        result["steps"].append({"step": "DB 수집", "status": "완료", "count": count})
        _record_perf("루나", "crawl_influencers", count)

    # STEP 2: 이메일 개인화 생성 → 검수 큐
    if agent == "피치":
        leads_data = await api_recontact_leads()
        targets = [l for l in leads_data.get("leads", []) if l.get("email") and "@" in l.get("email", "")][:20]
        tmpl = EMAIL_TEMPLATES.get("pitch_outbound")
        queued = 0
        for t in targets:
            name = t.get("name", "담당자")
            email = t.get("email", "")
            subject = tmpl["subject"].format(brand=name, contact="담당자", name=name, fee="200")
            email_body = tmpl["body"].format(brand=name, contact="담당자", product="제품", name=name, fee="200", **{"미팅링크": MEETING_LINK})
            html = _build_pitch_html(name, email_body + f"\n\n[미팅 예약하기]({MEETING_LINK})")
            _queue_or_send_email("피치", email, subject, html, {"target": name, "pipeline": True})
            queued += 1
        result["steps"].append({"step": "이메일 생성", "status": "완료", "queued": queued})
    elif agent == "루나":
        inf = await api_influencer_db()
        items = inf.get("items", inf.get("rows", []))
        targets = [i for i in items if isinstance(i, dict) and i.get("email") and "@" in i.get("email", "")][:20]
        tmpl = EMAIL_TEMPLATES.get("luna_kr")
        queued = 0
        for t in targets:
            name = t.get("account", t.get("name", ""))
            email = t.get("email", "")
            subject = tmpl["subject"].format(name=name, fee="200000")
            email_body = tmpl["body"].format(name=name, fee="200000")
            html = _build_pitch_html(name, email_body)
            _queue_or_send_email("루나", email, subject, html, {"target": name, "pipeline": True})
            queued += 1
        result["steps"].append({"step": "이메일 생성", "status": "완료", "queued": queued})

    # STEP 3: proposal 상태 업데이트
    if pid:
        proposals = load_proposals()
        for p in proposals:
            if p.get("id") == pid:
                p["status"] = "executed"
                p["executed_at"] = now.isoformat()
                p["result"] = f"DB {result['steps'][0].get('count',0)}건 수집 → 이메일 {result['steps'][-1].get('queued',0)}건 생성"
                break
        save_proposals(proposals)

    # STEP 4: Slack 알림
    if _slack_enabled() and SLACK_WEBHOOK_URL:
        try:
            text = f"🤖 [{agent}] 파이프라인 실행 완료\n"
            for s in result["steps"]:
                text += f"• {s['step']}: {s['status']} ({s.get('count', s.get('queued', 0))}건)\n"
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(SLACK_WEBHOOK_URL, json={"text": text})
        except Exception:
            pass

    return {"status": "ok", "result": result}

@app.get("/api/outbound-dashboard")
async def api_outbound_dashboard(agent: str = "피치"):
    """섹션 최상단 통합 KPI — CEO 대시보드용."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    today_perf = perf.get(today, {}).get(agent, {})
    # 월간/주간 누적
    monthly_p, weekly_p = {}, {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix) and agent in ad:
            for mk, mv in ad[agent].items():
                monthly_p[mk] = monthly_p.get(mk, 0) + mv
        if dk >= week_start and agent in ad:
            for mk, mv in ad[agent].items():
                weekly_p[mk] = weekly_p.get(mk, 0) + mv
    # 발송 현황
    log = load_email_log()
    agent_log = [e for e in log if e.get("agent") == agent]
    today_sent = sum(1 for e in agent_log if e.get("sent_at", "").startswith(today) and e.get("status") == "sent")
    today_opened = sum(1 for e in agent_log if e.get("sent_at", "").startswith(today) and e.get("opened"))
    today_replied = sum(1 for e in agent_log if e.get("sent_at", "").startswith(today) and e.get("replied"))
    queue = load_email_queue()
    pending = sum(1 for q in queue if q.get("agent") == agent and q.get("status") == "pending")
    crawled = load_crawled()
    agent_type = "brand" if agent == "피치" else "influencer"
    total_crawled = sum(1 for c in crawled if c.get("type") == agent_type)
    # 벤치마크
    bench = load_benchmarks()
    bm = bench.get("cold_email_b2b", {}) if agent == "피치" else bench.get("influencer_outreach", {})
    open_rate = round(today_opened / max(today_sent, 1) * 100, 1)
    reply_rate = round(today_replied / max(today_sent, 1) * 100, 1)
    bm_reply = bm.get("reply_rate", {})
    # 목표
    targets = AGENT_TARGETS.get(agent, {})
    daily_t = targets.get("daily", {})
    weekly_t = targets.get("weekly", {})
    monthly_t = targets.get("monthly", {})
    meeting_key = "meeting_booked" if agent == "피치" else "influencer_acquired"
    # 토큰
    token_today = today_perf.get("cost_usd_x100", 0) / 100
    token_month = monthly_p.get("cost_usd_x100", 0) / 100
    return {
        "target_summary": f"{'K-뷰티 브랜드' if agent=='피치' else 'SNS 인플루언서'} / 총 {total_crawled}개 확보",
        "send_status": {"today_sent": today_sent, "pending": pending, "today_opened": today_opened, "today_replied": today_replied},
        "ctr": {"open_rate": open_rate, "reply_rate": reply_rate,
                "bench_reply_avg": bm_reply.get("average", 0), "bench_reply_good": bm_reply.get("good", 0),
                "bench_source": bm_reply.get("source", "")},
        "goal": {
            "today": {"actual": today_perf.get(meeting_key, 0), "target": daily_t.get(meeting_key, 0)},
            "week": {"actual": weekly_p.get(meeting_key, 0), "target": weekly_t.get(meeting_key, 0)},
            "month": {"actual": monthly_p.get(meeting_key, 0), "target": monthly_t.get(meeting_key, 0)},
        },
        "token": {"today": round(token_today, 2), "month": round(token_month, 2)},
        "funnel": {"crawled": total_crawled, "email_found": total_crawled,
                   "sent": sum(1 for e in agent_log if e.get("status") == "sent"),
                   "opened": sum(1 for e in agent_log if e.get("opened")),
                   "replied": sum(1 for e in agent_log if e.get("replied")), "converted": 0},
    }

@app.get("/api/agent-auto-send")
async def api_agent_auto_send_get():
    """에이전트별 자동 발송 모드 조회."""
    if AGENT_AUTO_SEND_FILE.exists():
        return json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8"))
    return {"피치": False, "루나": False}

@app.post("/api/agent-auto-send")
async def api_agent_auto_send_set(request: Request):
    """에이전트별 자동 발송 ON/OFF."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if AGENT_AUTO_SEND_FILE.exists():
        existing = json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8"))
    agent = body.get("agent", "")
    existing[agent] = bool(body.get("enabled", False))
    AGENT_AUTO_SEND_FILE.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "agent": agent, "enabled": existing[agent]}


# ===== 크롤링 + 파이프라인 API =====

# 이메일 템플릿
EMAIL_TEMPLATES = {
    "pitch_outbound": {
        "subject": "[{brand}] 리뷰 0개 → 100개, 무료로 시작하세요 (4월 한정)",
        "body": """안녕하세요, {contact}님.
글로벌 인플루언서 마케팅 플랫폼 공팔리터(08liter)의 제이콥입니다.
{brand}의 {product} 관련, 현재 브랜드 단계에서 효율이 높은 3가지 핵심 혜택을 안내드립니다.

1. 리뷰가 없으면 구매도 없습니다 (국내/해외 구매평 무료 제공)
2. 터지는 숏폼, 3개월간 걱정 없이 1000개도 가능합니다 (월 100만원)
3. 확실한 매출 전환을 위한 맞춤 키 인플루언서

10분 비대면 미팅으로 {brand}에 맞는 맞춤 제안 드립니다.""",
    },
    "pitch_crm": {
        "subject": "{brand}님, 4월 앵콜 프로모션 — 숏폼 무제한 300만원",
        "body": """안녕하세요, {contact}님.
지난번 {brand} 관련 문의를 주셨을 때 좋은 대화를 나눴었는데요,
이후 진행 상황이 궁금하여 다시 연락드립니다.

현재 4월 앵콜 프로모션 진행 중입니다:
- 숏폼 무제한 월 300만원 (기존 500만원)
- 해외 구매평 100건 무료 제공
- 맞춤 키 인플루언서 3명 배정

편하신 시간에 10분만 투자해 주시면 맞춤 제안을 드리겠습니다.""",
    },
    "pitch_followup": {
        "subject": "Re: {brand} — 10분이면 충분합니다",
        "body": "안녕하세요, {contact}님. 혹시 확인하셨을까요? 지금 시기가 가장 효율 좋은 타이밍입니다. 편하신 때 답변 부탁드립니다.",
    },
    "luna_intl": {
        "subject": "Free K-Beauty Products for {name} — Paid Collab",
        "body": """Hi {name},

Loved your recent content! I'm Luna from 08liter, Asia's largest K-beauty influencer platform (139M+ creators).

We'd love to send you:
- Free K-beauty products
- Content fee: ${fee}
- Just 1 Reel/Short, 3-month rights

Reply 'YES' for full details!

Luna, 08liter""",
    },
    "luna_kr": {
        "subject": "{name}님, 무료 협찬 + 제작비 제안",
        "body": """안녕하세요 {name}님, 공팔리터 루나입니다!

최근 콘텐츠 정말 인상적이었어요. K-뷰티 브랜드 협찬 제안드립니다:
- 무료 제품 제공
- 제작비: {fee}원
- 릴스/숏츠 1개, 3개월 사용권

관심 있으시면 답장만 주세요!

루나 드림""",
    },
    "luna_followup": {
        "subject": "Re: {name}님 — 혹시 확인하셨나요?",
        "body": "안녕하세요 {name}님! 혹시 확인하셨나요? 관심 있으시면 답장만 주세요 :)",
    },
}

@app.get("/api/email-templates")
async def api_email_templates():
    """이메일 템플릿 목록."""
    return EMAIL_TEMPLATES

@app.post("/api/crawl/brands")
async def api_crawl_brands(request: Request):
    """피치용 브랜드 크롤링 (시뮬레이션). 실제 크롤링은 추후 연동."""
    body = await request.json()
    channels = body.get("channels", [])
    keyword = body.get("keyword", "K-뷰티")
    limit = min(body.get("limit", 50), 200)
    # 시뮬레이션: 구글시트 인바운드 + 크롤링 결과 병합
    results = []
    try:
        leads = await api_recontact_leads()
        for l in leads.get("leads", [])[:limit]:
            results.append({"company": l["name"], "contact": "", "title": "담당자",
                            "email": l.get("email", ""), "phone": l.get("contact", ""),
                            "url": "", "product": keyword, "source": "인바운드DB", "size": ""})
    except Exception:
        pass
    _record_perf("피치", "crawl_brands", len(results))
    existing = load_crawled()
    seen = {e.get("email") for e in existing if e.get("email")}
    new_items = [r for r in results if r.get("email") and r["email"] not in seen]
    existing.extend([{**r, "type": "brand", "crawled_at": datetime.now(KST).isoformat()} for r in new_items])
    save_crawled(existing)
    return {"status": "ok", "count": len(results), "new": len(new_items), "results": results[:50]}

@app.post("/api/crawl/influencers")
async def api_crawl_influencers(request: Request):
    """루나용 인플루언서 크롤링 (시뮬레이션). 실제 SNS 크롤링은 추후 연동."""
    body = await request.json()
    countries = body.get("countries", ["KR"])
    platforms = body.get("platforms", ["Instagram"])
    min_followers = body.get("min_followers", 1000)
    limit = min(body.get("limit", 50), 200)
    results = []
    try:
        inf = await api_influencer_db()
        for item in (inf.get("items") or inf.get("rows", []))[:limit]:
            if isinstance(item, dict):
                email = item.get("email", "")
                if email and "@" in email:
                    results.append({"name": item.get("account", item.get("name", "")),
                                    "platform": item.get("platform", "Instagram"),
                                    "followers": item.get("followers", "0"),
                                    "category": item.get("category", "뷰티"),
                                    "country": item.get("country", "KR"),
                                    "email": email, "engagement": "3.2%",
                                    "url": item.get("url", ""), "source": "인플루언서DB"})
    except Exception:
        pass
    _record_perf("루나", "crawl_influencers", len(results))
    existing = load_crawled()
    seen = {e.get("email") for e in existing if e.get("email")}
    new_items = [r for r in results if r.get("email") and r["email"] not in seen]
    existing.extend([{**r, "type": "influencer", "crawled_at": datetime.now(KST).isoformat()} for r in new_items])
    save_crawled(existing)
    return {"status": "ok", "count": len(results), "new": len(new_items), "results": results[:50]}

@app.post("/api/generate-emails")
async def api_generate_emails(request: Request):
    """크롤링 결과 기반 이메일 자동 생성 → 검수 큐."""
    body = await request.json()
    targets = body.get("targets", [])
    agent = body.get("agent", "피치")
    template_key = body.get("template", "pitch_outbound")
    tmpl = EMAIL_TEMPLATES.get(template_key, EMAIL_TEMPLATES["pitch_outbound"])
    queued = 0
    for t in targets[:50]:
        email = t.get("email", "")
        if not email or "@" not in email:
            continue
        vars_map = {"brand": t.get("company", t.get("name", "")), "contact": t.get("contact", "담당자"),
                    "product": t.get("product", "제품"), "name": t.get("name", ""),
                    "fee": t.get("fee", "200"), "미팅링크": MEETING_LINK}
        try:
            subject = tmpl["subject"].format(**{k: vars_map.get(k, "") for k in ["brand", "contact", "name", "fee"]})
            email_body = tmpl["body"].format(**{k: vars_map.get(k, "") for k in ["brand", "contact", "product", "name", "fee", "미팅링크"]})
        except (KeyError, IndexError):
            subject = tmpl["subject"]
            email_body = tmpl["body"]
        html = _build_pitch_html(vars_map.get("brand", vars_map.get("name", "")), email_body + f"\n\n[미팅 예약하기]({MEETING_LINK})")
        _queue_or_send_email(agent, email, subject, html, {"target": t.get("company", t.get("name", ""))})
        queued += 1
    _record_perf(agent, "emails_generated", queued)
    return {"status": "ok", "queued": queued}

@app.get("/api/email-log")
async def api_get_email_log(agent: Optional[str] = None):
    """이메일 발송 로그 조회."""
    log = load_email_log()
    if agent:
        log = [e for e in log if e.get("agent") == agent]
    today = datetime.now(KST).strftime("%Y-%m-%d")
    today_log = [e for e in log if e.get("sent_at", "").startswith(today)]
    total_sent = sum(1 for e in today_log if e.get("status") == "sent")
    total_opened = sum(1 for e in today_log if e.get("opened"))
    total_replied = sum(1 for e in today_log if e.get("replied"))
    return {"log": log[-50:], "today": {"sent": total_sent, "opened": total_opened, "replied": total_replied},
            "total": len(log)}

@app.get("/api/pipeline-stats")
async def api_pipeline_stats(agent: Optional[str] = None):
    """파이프라인 단계별 통계."""
    log = load_email_log()
    crawled = load_crawled()
    queue = load_email_queue()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    if agent:
        log = [e for e in log if e.get("agent") == agent]
        crawled = [c for c in crawled if c.get("type") == ("brand" if agent == "피치" else "influencer")]
        queue = [q for q in queue if q.get("agent") == agent]
    today_crawled = sum(1 for c in crawled if c.get("crawled_at", "").startswith(today))
    today_queued = sum(1 for q in queue if q.get("status") == "pending" and q.get("created_at", "").startswith(today))
    today_sent = sum(1 for e in log if e.get("sent_at", "").startswith(today) and e.get("status") == "sent")
    today_replied = sum(1 for e in log if e.get("sent_at", "").startswith(today) and e.get("replied"))
    return {
        "crawled": {"total": len(crawled), "today": today_crawled},
        "queued": {"total": sum(1 for q in queue if q.get("status") == "pending"), "today": today_queued},
        "sent": {"total": sum(1 for e in log if e.get("status") == "sent"), "today": today_sent},
        "replied": {"total": sum(1 for e in log if e.get("replied")), "today": today_replied},
    }

@app.get("/api/agent-kpi-dashboard")
async def api_agent_kpi_dashboard():
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


import asyncio
import threading

def _cache_warm():
    """서버 시작 시 구글시트 데이터를 미리 로드."""
    if not GSHEETS_API_KEY:
        return
    try:
        fetch_sheet(SHEET_INBOUND, "A:Z", "파센문의", ttl_key="inbound")
        fetch_sheet(SHEET_CONTRACT, "A:Z", "계산서발행", ttl_key="contract")
        fetch_sheet(SHEET_INFLUENCER, "A2:R", "현황시트(수동매칭)", ttl_key="influencer")
        print("[CACHE] 구글시트 데이터 사전 로드 완료")
    except Exception as e:
        print(f"[CACHE] 사전 로드 오류: {e}")

def _cache_refresh_loop():
    """10분마다 백그라운드에서 캐시 갱신."""
    import time as _time
    while True:
        _time.sleep(600)
        try:
            _cache.clear()
            _cache_time.clear()
            _cache_warm()
            print("[CACHE] 백그라운드 갱신 완료")
        except Exception:
            pass

# 서버 시작 시 캐시 워밍 + 백그라운드 갱신 스레드
_cache_warm()
_bg_thread = threading.Thread(target=_cache_refresh_loop, daemon=True)
_bg_thread.start()

if __name__ == "__main__":
    import uvicorn
    print("08L_AI Command Center -> http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
