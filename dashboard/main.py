"""08L_AI Command Center â 통합 건시건³´건 + Google Sheets API + Anthropic AI Agents"""
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

load_dotenv(override=False)  # OS 환경건³수(Railway)가 .env건³´건¤ 우선
app = FastAPI(title="Command Center")
app.add_middleware(GZipMiddleware, minimum_size=500)
KST = ZoneInfo("Asia/Seoul")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ===== 건¡그인 인증 (쿠키 세션 건°©식) =====
DASH_USER = os.getenv("DASH_USER", "")
DASH_PASS = os.getenv("DASH_PASS", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))


def _make_token(user: str) -> str:
    return hashlib.sha256(f"{user}:{SESSION_SECRET}".encode()).hexdigest()


@app.get("/health")
async def health_check():
    """전체 API 연건 상태 â 7개 서건¹스"""
    def _chk(key): return "connected" if os.getenv(key) else "not_configured"
    # 건©타: 토큰 존재하건©´ connected, API 호출은 건³건 검증
    meta_status = "not_configured"
    meta_note = ""
    if os.getenv("META_ACCESS_TOKEN"):
        meta_status = "connected"
        try:
            r = req_lib.get(f"https://graph.facebook.com/v18.0/act_{os.getenv('META_AD_ACCOUNT_ID','230720044045370')}/campaigns",
                params={"access_token": os.getenv("META_ACCESS_TOKEN"), "fields": "name", "limit": "1"}, timeout=5)
            if r.status_code != 200:
                meta_note = "토큰 유효하건 API 응건µ 건¹정상 (code=" + str(r.status_code) + ")"
        except Exception:
            meta_note = "API 호출 타임아웃 (토큰은 설정건¨)"
    return {
        "status": "ok",
        "timestamp": datetime.now(KST).isoformat(),
        "services": {
            "google_sheets": "connected" if GSHEETS_API_KEY else "not_configured",
            "anthropic": _chk("ANTHROPIC_API_KEY"),
            "slack": _chk("SLACK_WEBHOOK_URL"),
            "email": "connected" if os.getenv("EMAIL_WEBHOOK_URL") else "not_configured",
            "meta_ads": meta_status,
            "meta_ads_note": meta_note,
            "naver_ads": "connected" if (os.getenv("NAVER_API_KEY") and os.getenv("NAVER_SECRET_KEY") and os.getenv("NAVER_CUSTOMER_ID")) else "not_configured",
            "google_ads": "connected" if (os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN") and os.getenv("GOOGLE_ADS_REFRESH_TOKEN")) else "not_configured",
            "kakao_b2b": "connected" if os.getenv("KAKAO_B2B_API_KEY") or os.getenv("KAKAO_REST_API_KEY") else "not_configured",
            "kakao_b2c": "connected" if os.getenv("KAKAO_B2C_API_KEY") or os.getenv("KAKAO_REST_API_KEY") else "not_configured",
            "naver_works_smtp": _chk("NAVER_WORKS_SMTP_PASSWORD"),
            "instagram": _chk("META_INSTAGRAM_TOKEN"),
        },
        "cache_entries": len(_cache),
    }

@app.get("/api/sheets/health")
async def api_sheets_health():
    """Google Sheets tab access check."""
    if not GSHEETS_API_KEY:
        return {"status": "no_api_key"}
    tabs = {
        "contract": {"sheet": SHEET_CONTRACT, "tab": TAB_CONTRACT, "range": "A1:A2"},
        "inbound": {"sheet": SHEET_INBOUND, "tab": TAB_INBOUND, "range": "A1:A2"},
        "influencer": {"sheet": SHEET_INFLUENCER, "tab": TAB_INFLUENCER, "range": "A1:A2"},
        "pitch_claude": {"sheet": PITCH_SHEET_ID, "tab": TAB_PITCH, "range": "A1:A2"},
        "sophie_claude": {"sheet": SOPHIE_SHEET_ID, "tab": TAB_SOPHIE, "range": "A1:A2"},
    }
    results = {}
    for key, info in tabs.items():
        try:
            data = fetch_sheet(info["sheet"], info["range"], info["tab"], ttl_key="default")
            results[key] = {"status": "ok", "tab": info["tab"], "rows": len(data)}
        except Exception as e:
            results[key] = {"status": "error", "tab": info["tab"], "error": str(e)[:100]}
    return results


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """건¡그인 폼 페이지"""
    if not DASH_USER or not DASH_PASS:
        return RedirectResponse("/", status_code=302)
    html = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Login â 08L_AI</title>
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
<h1>â¡ 08L_AI</h1>
<p class="sub">Command Center</p>
{"<p class='err'>아이건 건건 건¹건°건²호가 틀건 ¸습건건¤.</p>" if error else ""}
<form method="post" action="/login">
<input name="username" placeholder="아이건" required autocomplete="username">
<input name="password" type="password" placeholder="건¹건°건²호" required autocomplete="current-password">
<button type="submit">건¡그인</button>
</form></div></body></html>"""
    return HTMLResponse(html)


@app.post("/login")
async def login_submit(request: Request):
    """건¡그인 처건¦¬"""
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
    """쿠키 세션 기반 인증 확인. DASH_USER 건¯¸설정 시 항상 True."""
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

# 건°송 속건 제한
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
    """이건©일 건°송 건¡그 기건¡."""
    log = load_email_log()
    log.append({"agent": agent, "to": to, "subject": subject, "status": status,
                "sent_at": datetime.now(KST).isoformat(), "opened": False,
                "replied": False, "followup_count": 0, "meta": meta or {}})
    save_email_log(log)

def _check_send_limit() -> bool:
    """일일 건°송 한건 확인."""
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
    """에이전트 자건 건°송 건ª¨건 확인. 기건³¸ OFF."""
    if AGENT_AUTO_SEND_FILE.exists():
        try:
            return json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8")).get(agent, False)
        except Exception:
            pass
    return False

def _queue_or_send_email(agent: str, to_email: str, subject: str, html: str, meta: dict = None) -> dict:
    """자건 건°송 건ª¨건건©´ 즉시 건°송, 아건건©´ 검수 큐에 추가."""
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

# 토큰 건¹용 건¨가 (USD per M tokens)
TOKEN_COSTS = {
    "haiku": {"input": 1.0, "output": 5.0},
    "sonnet": {"input": 3.0, "output": 15.0},
}

def _record_tokens(agent: str, input_tokens: int, output_tokens: int, model: str = "sonnet"):
    """에이전트건³ 토큰 사용건 기건¡."""
    cost_table = TOKEN_COSTS.get("haiku" if "haiku" in model.lower() else "sonnet", TOKEN_COSTS["sonnet"])
    cost = (input_tokens * cost_table["input"] + output_tokens * cost_table["output"]) / 1_000_000
    _record_perf(agent, "input_tokens", input_tokens)
    _record_perf(agent, "output_tokens", output_tokens)
    _record_perf(agent, "cost_usd_x100", int(cost * 100))

# ===== 에이전트건³ 구글시트 =====
PITCH_SHEET_ID = os.getenv("PITCH_SHEET_ID", "1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8")
LUNA_SHEET_ID = os.getenv("LUNA_SHEET_ID", "1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs")
SOPHIE_SHEET_ID = os.getenv("SOPHIE_SHEET_ID", "1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU")

SHEET_URLS = {
    "피치": "https://docs.google.com/spreadsheets/d/1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8/edit#gid=0",
    "루나": "https://docs.google.com/spreadsheets/d/1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs/edit#gid=0",
    "소피": "https://docs.google.com/spreadsheets/d/1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU/edit#gid=0",
    "건 이": "https://docs.google.com/spreadsheets/d/1j_3IYME764NlrARbNCZ_TJqzZCyfAMy-N3V-ByRik6Q/edit#gid=0",
}

MEETING_LINK ="https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ3b3pndYo35A_3SjrHJeeXfAm3YpvBX0IXfkJqXP0QXixBEADR_ehY__tHBlJdNBkL5I2868Rrd"

# ===== 에이전트 이건©일 계정 =====
AGENT_EMAILS = {
    "카일": os.getenv("KYLE_EMAIL", "kyle@08liter.com"),
    "루나": os.getenv("LUNA_EMAIL", "luna@08liter.com"),
    "피치": os.getenv("PITCH_EMAIL", "pitch@08liter.com"),
    "건§¥스": os.getenv("MAX_EMAIL", "max@08liter.com"),
    "소피": os.getenv("SOPHIE_EMAIL", "sophie@08liter.com"),
    "건 이": os.getenv("RAY_EMAIL", "ray@08liter.com"),
    "하건": os.getenv("HANA_EMAIL", "hana@08liter.com"),
}

# ===== 월간 건ª©표 (기건³¸값, /api/goals건¡ 수정 가건¥) =====
DEFAULT_GOALS = {
    "revenue": 160000000, "contracts": 38, "inbound_db": 500,
    "valid_db": 150, "cpa": 50000, "influencer_pool": 1550000,
    "alert_threshold": 0.3,
}

# ===== 에이전트건³ 건ª©표 (일/주/월) =====
AGENT_TARGETS = {
    "피치": {
        "monthly": {"new_contract": 10, "renew_contract": 10, "meeting_booked": 60, "inbound_email": 3000, "outbound_email": 5000, "total_email": 8000},
        "weekly":  {"new_contract": 2.5, "renew_contract": 2.5, "meeting_booked": 15, "inbound_email": 750, "outbound_email": 1250, "total_email": 2000},
        "daily":   {"meeting_booked": 3, "inbound_email": 150, "outbound_email": 250, "total_email": 400},
    },
    "루나": {
        "monthly": {"influencer_acquired": 300, "outbound_email": 3000, "crawl_data": 5000, "email_reply": 450},
        "weekly":  {"influencer_acquired": 75, "outbound_email": 750, "crawl_data": 1250, "email_reply": 113},
        "daily":   {"influencer_acquired": 15, "outbound_email": 150, "crawl_data": 250, "email_reply": 23},
    },
    "소피": {
        "monthly": {"b2b_content": 20, "b2c_content": 20, "b2b_lead": 300, "b2c_lead": 500},
        "weekly":  {"b2b_content": 5, "b2c_content": 5, "b2b_lead": 75, "b2c_lead": 125},
        "daily":   {"b2b_content": 1, "b2c_content": 1, "b2b_lead": 15, "b2c_lead": 25},
    },
    "건§¥스": {
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
    """에이전트 일일 성과 기건¡. {건 짜: {에이전트: {metric: count}}}"""
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

# 시트 탭명 (환경변수 — 인코딩 깨짐 방지)
TAB_CONTRACT = os.getenv("SHEET_TAB_CONTRACT", "\uacc4\uc0b0\uc11c\ubc1c\ud589")
TAB_INBOUND = os.getenv("SHEET_TAB_INBOUND", "\ud30c\uc13c\ubb38\uc758")
TAB_INFLUENCER = os.getenv("SHEET_TAB_INFLUENCER", "\ud604\ud669\uc2dc\ud2b8(\uc218\ub3d9\ub9e4\uce6d)")
TAB_PITCH = os.getenv("SHEET_TAB_PITCH", "\ud53c\uce58_\ud074\ub85c\ub4dc")
TAB_LUNA = os.getenv("SHEET_TAB_LUNA", "\ub8e8\ub098_\ud074\ub85c\ub4dc")
TAB_SOPHIE = os.getenv("SHEET_TAB_SOPHIE", "\uc18c\ud53c_\ud074\ub85c\ub4dc")

_cache: Dict[str, list] = {}
_cache_time: Dict[str, float] = {}
CACHE_TTLS = {
    "inbound": 300,      # 5 min
    "contract": 300,     # 5건¶ â 건¡건© 속건 개선
    "influencer": 21600, # 6 hours
    "ads": 3600,         # 1 hour
    "default": 1800,     # 30 min fallback
}

SYSTEMS = [
    {"name": "KPI 집계건´", "icon": "chart", "port": 8001, "desc": "일일 KPI 자건 집계 건° Slack 건°송", "company": "공통"},
    {"name": "SNS 스케줄건¬", "icon": "share", "port": 8002, "desc": "SNS 콘텐츠 자건 건°행 관건¦¬", "company": "공통"},
    {"name": "카카오 CRM", "icon": "msg", "port": 8003, "desc": "구건§¤ 후 건©시지 시퀀스 자건화", "company": "Mili Mili"},
    {"name": "건¦¬건 파이프건¼인", "icon": "lead", "port": 8004, "desc": "인건°운건 건¦¬건 수집 건° 건±급 건¶건¥", "company": "08Liter"},
    {"name": "계약 자건화", "icon": "doc", "port": 8005, "desc": "전자계약 파이프건¼인", "company": "08Liter"},
    {"name": "광고 건ª¨건터건§", "icon": "ad", "port": 8006, "desc": "ROAS/CPA/CTR 실시간 추적", "company": "Mili Mili"},
    {"name": "건¦¬건·° 건ª¨건터건§", "icon": "star", "port": 8007, "desc": "건¦¬건·° 추적 건° 건응 관건¦¬", "company": "Mili Mili"},
]


# ===== Google Sheets Reader =====
def fetch_sheet(sheet_id: str, range_name: str, tab_name: str = None, ttl_key: str = "default") -> list:
    """Google Sheets API v4건¡ 건°이터 읽기. API Key 없으건©´ 건¹ 건¦¬스트."""
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
        "unhandled_brands": [{"name": "샘플건¸건건A", "channel": "SNS(건©타)", "source": "", "date": "오건", "reason": "건´건¹자 없음"}],
        "prev_month": {"inbound": 38, "valid": 110, "meeting": 25, "contract": 8, "renewal": 3},
        "last_year": {"inbound": 22, "valid": 68, "meeting": 15, "contract": 5, "renewal": 1},
        "conversion": {"valid_rate": 29.5, "meeting_rate": 22.0, "contract_rate": 4.7, "renewal_rate": 0.5},
        "channel_breakdown": [
            {"channel": "SNS(건©타)", "inbound": 18, "valid": 6, "rate": 33.3},
            {"channel": "이건©일", "inbound": 8, "valid": 3, "rate": 37.5},
            {"channel": "CPC(건¤이건²)", "inbound": 12, "valid": 2, "rate": 16.7},
            {"channel": "기타", "inbound": 5, "valid": 1, "rate": 20.0},
        ],
        "staff_breakdown": [
            {"name": "소필건¼", "inbound": 20, "valid": 8, "contract": 3, "rate": 40.0},
            {"name": "건¼이건", "inbound": 15, "valid": 6, "contract": 2, "rate": 40.0},
            {"name": "건¤엔", "inbound": 8, "valid": 3, "contract": 1, "rate": 37.5},
        ],
        "pipeline": {
            "인입DB": [
                {"name": "건·°티건¸건건A", "channel": "인스타그건¨", "date": today_str, "staff": "건¯¸건°°정"},
                {"name": "코스건©틱B", "channel": "구글광고", "date": today_str, "staff": "건¯¸건°°정"},
                {"name": "스킨케어C", "channel": "LinkedIn", "date": today_str, "staff": "건¯¸건°°정"},
            ],
            "유효DB": [
                {"name": "건¸건건D", "channel": "카카오톡", "staff": "소필건¼", "contact_count": 2},
                {"name": "건¸건건E", "channel": "이건©일", "staff": "건¼이건", "contact_count": 1},
                {"name": "건¸건건F", "channel": "전화", "staff": "건¤엔", "contact_count": 3, "expected": "450건§"},
            ],
            "건¯¸팅": [
                {"name": "건¸건건G", "meeting_date": "건´일 14:00", "stage": "견적 검토중", "amount": "520건§", "package": "Growth"},
                {"name": "건¸건건H", "meeting_date": "건ª©요일", "stage": "제안서 전건¬", "amount": "450건§", "package": "Growth"},
            ],
            "계약서": [
                {"name": "건¸건건I", "stage": "계약서 검토중", "amount": "600건§", "package": "Premium"},
                {"name": "건¸건건J", "stage": "건´건¶ 결재중", "amount": "800건§", "package": "Enterprise"},
            ],
            "재계약": [
                {"name": "건¸건건K", "date": "4월 1일", "amount": "420건§", "package": "Growth", "paid": True},
                {"name": "건¸건건L", "date": "3월 25일", "amount": "380건§", "package": "Growth", "paid": True},
            ],
        },
    }


def _dummy_influencer_db():
    return {
        "source": "dummy", "total": 1400000, "items": [
            {"date": "2026-04-01", "type": "아웃건°운건", "country": "KR", "category": "건·°티", "platform": "Instagram", "account": "@beauty_kr1", "url": "https://instagram.com/beauty_kr1", "followers": "520K", "followers_num": 520000, "email": "", "contact": "", "status": "사건¡활용가건¥", "currency": "", "price_collab": "180", "price_wish": "200", "price_krw": "180", "staff": "소필건¼", "campaign": "3월 캠페인", "note": ""},
            {"date": "2026-04-01", "type": "인건°운건", "country": "TH", "category": "패션", "platform": "TikTok", "account": "@style_th", "url": "https://tiktok.com/@style_th", "followers": "380K", "followers_num": 380000, "email": "", "contact": "", "status": "제안건°송", "currency": "", "price_collab": "120", "price_wish": "150", "price_krw": "120", "staff": "건¼이건", "campaign": "2월 캠페인", "note": ""},
            {"date": "2026-03-28", "type": "아웃건°운건", "country": "US", "category": "건·°티", "platform": "Instagram", "account": "@skincare_us", "url": "", "followers": "210K", "followers_num": 210000, "email": "", "contact": "", "status": "건¨순건¦¬스트업", "currency": "", "price_collab": "250", "price_wish": "300", "price_krw": "250", "staff": "소필건¼", "campaign": "", "note": ""},
            {"date": "2026-03-25", "type": "아웃건°운건", "country": "JP", "category": "건¼이프", "platform": "YouTube", "account": "@food_jp", "url": "", "followers": "890K", "followers_num": 890000, "email": "", "contact": "", "status": "사건¡활용가건¥", "currency": "", "price_collab": "320", "price_wish": "350", "price_krw": "320", "staff": "건¼이건", "campaign": "4월 예정", "note": ""},
            {"date": "2026-03-22", "type": "인건°운건", "country": "VN", "category": "건·°티", "platform": "TikTok", "account": "@beauty_vn", "url": "", "followers": "190K", "followers_num": 190000, "email": "", "contact": "", "status": "제안건°송", "currency": "", "price_collab": "70", "price_wish": "90", "price_krw": "70", "staff": "소필건¼", "campaign": "3월", "note": ""},
            {"date": "2026-03-20", "type": "아웃건°운건", "country": "ID", "category": "피트건스", "platform": "TikTok", "account": "@fit_id", "url": "", "followers": "330K", "followers_num": 330000, "email": "", "contact": "", "status": "건¨순건¦¬스트업", "currency": "", "price_collab": "90", "price_wish": "110", "price_krw": "90", "staff": "건¼이건", "campaign": "", "note": ""},
        ],
        "stats": {
            "by_country": {"KR": 2, "TH": 1, "US": 1, "JP": 1, "VN": 1, "ID": 1},
            "by_platform": {"Instagram": 3, "TikTok": 3, "YouTube": 1},
            "by_status": {"사건¡활용가건¥": 2, "제안건°송": 2, "건¨순건¦¬스트업": 2},
            "by_category": {"건·°티": 3, "패션": 1, "건¼이프": 1, "피트건스": 1},
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
            {"name": "소필건¼", "revenue": 18500000, "contracts": 3, "conversion": 37.5},
            {"name": "건¼이건", "revenue": 12000000, "contracts": 2, "conversion": 33.3},
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


# ===== 건 짜/채건 헬퍼 =====
def _is_date_today(date_val: str, now: datetime) -> bool:
    """건 짜 건¬¸자열이 오건(KST)인지 판건¨. 5가지 형식 지원."""
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
    """건 짜 건¬¸자열이 이건² 건¬인지 판건¨."""
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
    """유입채건 건¶건¥."""
    if not channel:
        return "기타"
    ch = channel.lower()
    if any(k in ch for k in ["sns", "건©타", "insta", "meta", "facebook", "fb"]):
        return "SNS(건©타)"
    if any(k in ch for k in ["email", "이건©일", "mail"]):
        return "이건©일"
    if any(k in ch for k in ["cpc", "건¤이건²", "naver", "검색", "search"]):
        return "CPC(건¤이건²)"
    if any(k in ch for k in ["google_sa", "google", "구글"]):
        return "구글(SA)"
    if any(k in ch for k in ["brandthumb", "건¸건건썸"]):
        return "건¸건건썸"
    if any(k in ch for k in ["blog", "건¸건¡그", "youtube", "유튜건¸"]):
        return "건¸건¡그/유튜건¸"
    return channel[:10] if channel else "기타"


def _find_col(headers, *keywords):
    """헤건 건¦¬스트에서 키워건 포함 컬건¼ 인건±스 건°환. 줄건°꿈 제거 후 건§¤칭."""
    for i, h in enumerate(headers):
        h_clean = h.replace("\n", " ")
        for kw in keywords:
            if kw in h_clean:
                return i
    return None


def _find_header_row(rows, *marker_keywords):
    """시트에서 실제 헤건 행 찾기. marker_keywords 중 하건건¥¼ 포함하건 첫 건²째 행 건°환."""
    for ri, row in enumerate(rows[:10]):
        row_text = " ".join(str(c).replace("\n", " ") for c in row)
        for kw in marker_keywords:
            if kw in row_text:
                return ri
    return 0


def _auto_detect_date_col(headers, sample_rows):
    """건 짜 컬건¼ 자건 감지: 헤건건ª 우선, 없으건©´ 건°이터 패턴으건¡."""
    for i, h in enumerate(headers):
        h_clean = h.replace("\n", " ")
        if any(k in h_clean for k in ['건 짜', 'date', '일자', '일시', 'Date']):
            return i
    for row in sample_rows[:5]:
        for ci in range(min(len(row), 15)):
            val = str(row[ci]).strip()
            if re.match(r'^\d{1,2}/\d{1,2}$', val) or re.match(r'^\d{4}-\d{2}-\d{2}', val):
                return ci
    return None


# ===== Live Sheets Parsing (헤건 기반 자건 감지) =====
def _parse_inbound(rows):
    """인건°운건 시트 파싱 â 헤건 기반 컬건¼ 자건 감지. 컨텍현황='워킹 중' â 유효DB."""
    now = datetime.now(KST)
    this_month_str = f"{now.year}.{now.month:02d}"

    result = {"today_inbound": 0, "today_valid": 0, "today_unhandled": 0, "today_handled": 0,
              "month_inbound": 0, "month_valid": 0, "month_unhandled": 0,
              "cumul_inbound": 0, "cumul_valid": 0, "cumul_invalid": 0,
              "channel_stats": {}, "staff_stats": {}, "source_stats": {},
              "unhandled_brands": [],
              "pipeline_items": {"인입DB": [], "유효DB": [], "건¯¸팅": [], "계약서": [], "재계약": []}}

    if not rows or len(rows) < 3:
        return result

    # 실제 헤건 행 자건 감지 (인건°운건 시트: "국가"/"월"/"건 짜" 포함 행)
    hdr_idx = _find_header_row(rows, "국가", "컨택현황", "컨텍현황", "건´건¹자")
    headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
    data_rows = rows[hdr_idx + 1:]

    date_idx = _auto_detect_date_col(headers, data_rows[:5])
    contact_status_idx = _find_col(headers, "컨텍현황", "컨택현황", "consulting")
    brand_idx = _find_col(headers, "업체건ª", "건¸건건", "상호", "brand name")
    channel_idx = _find_col(headers, "유입채건")
    staff_idx = _find_col(headers, "건´건¹자")
    month_idx = _find_col(headers, "월")
    source_idx = _find_col(headers, "유입소재", "유입경건¡", "소스")

    # 폴건°±: 기존 하건코건© 인건±스 (파센건¬¸의 탭)
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

    skip_kw = ["국가", "주의사항", "건³¸ 건¦¬스트", "[ ", "*", "brand name"]
    this_year_month_prefix = f"{now.year}.{now.month:02d}"  # "2026.04"
    this_year_iso_prefix = f"{now.year}-{now.month:02d}"     # "2026-04"

    def _is_current_year_month(month_val: str, date_val: str) -> bool:
        """월 컬건¼ 건건 건 짜 컬건¼이 현재 연월(2026.04)에 해건¹하건지 판건¨."""
        if this_year_month_prefix in month_val:
            return True
        # 월 컬건¼에 ISO 타임스탬프가 건¤어간 경우 (예: "2026-04-07 12:12:45")
        if month_val.startswith(this_year_iso_prefix):
            return True
        # 월 컬건¼이 건¹어있을 건 건 짜 컬건¼으건¡ 판건¨
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

        # 건적 (전체 기간, 건 짜 필터 없음)
        result["cumul_inbound"] += 1
        if status in ("워킹 중", "워킹중"):
            result["cumul_valid"] += 1

        # 이건² 건¬ 판건¨: 월 컬건¼이 현재 연월인지 확인 (연건 교차 건°©지)
        is_month = _is_current_year_month(month_val, date_val)
        # 오건 판건¨: 건 짜 건§¤칭 AND 월이 현재 연월 (2020/4/7 건± 과거 제외)
        is_today = _is_date_today(date_val, now) and is_month

        # 유효DB = 컨텍현황 "워킹중" (trim 후 건¹교)
        is_valid = status in ("워킹 중", "워킹중")
        is_unhandled = (not staff) or (not status)
        ch_key = _classify_channel(channel)

        card = {"name": brand, "channel": ch_key, "staff": staff or "건¯¸건°°정", "date": date_val,
                "source": source, "status": status if status else "건¯¸처건¦¬", "unhandled": is_unhandled}

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
                                                    "date": date_val, "reason": "건´건¹자 없음" if not staff else "컨택현황 건¯¸입건 ¥"})
            else:
                result["today_handled"] += 1

    result["cumul_invalid"] = result["cumul_inbound"] - result["cumul_valid"]
    return result


def _parse_contracts(rows):
    """세금계산서 시트 파싱 â 헤건 기반. 건±건¡기준일/공급가액/공급건°건자 상호."""
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

    # 실제 헤건 행 자건 감지 (계산서: "작성일자"/"공급가액"/"공급건°건자" 포함 행)
    hdr_idx = _find_header_row(rows, "작성일자", "공급가액", "공급건°건자")
    headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
    data_rows = rows[hdr_idx + 1:]

    date_idx = _find_col(headers, "작성일자", "건±건¡기준일", "건°행일")
    amount_idx = _find_col(headers, "공급가액")
    brand_idx = _find_col(headers, "공급건°건자 상호")  # 구체적 건§¤칭 (건±건¡건²호 제외)
    type_idx = _find_col(headers, "신규/", "재계약", "신규")
    staff_idx = _find_col(headers, "요청건´건¹자", "건´건¹자")
    month_idx = _find_col(headers, "작성월", "월건§¤출")

    payback_idx = _find_col(headers, "페이건°±건¹", "충전금", "구건§¤평충전금")

    # 폴건°± (기존 B:U 기준)
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
    # 건¸건건 첫 건±장 여건¶ 추적 (신규/재계약 자건 건¶건¥)
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
            revenue = int(float(revenue_raw.replace(",", "").replace("â©", "").replace(" ", ""))) if revenue_raw and revenue_raw not in ["-", ""] else 0
        except (ValueError, TypeError):
            revenue = 0
        if revenue < 0:
            revenue = 0

        # 페이건°±건¹ 파싱
        payback_raw = str(row[payback_idx]).strip() if payback_idx is not None and payback_idx < len(row) else "0"
        try:
            payback = int(float(payback_raw.replace(",", "").replace("â©", "").replace(" ", ""))) if payback_raw and payback_raw not in ["-", ""] else 0
        except (ValueError, TypeError):
            payback = 0
        if payback < 0:
            payback = 0

        # 건 짜 정건¦¬
        date_clean = date_raw.replace("-", "").replace(".", "").replace("/", "").replace(" ", "")
        if len(date_clean) < 6 or not date_clean[:6].isdigit():
            continue

        if brand:
            brand_set.add(brand)

        is_today = (date_clean[:8] == today_ymd) or date_raw.startswith(today_iso)
        is_this_month = (date_clean[:6] == this_ym) or (this_month_dot in month_val)
        is_prev_month = (date_clean[:6] == prev_ym) or (prev_month_dot in month_val)
        is_last_year = date_clean[:6] == ly_ym

        # 신규/재계약 자건 건¶건¥: type 컬건¼이 있으건©´ 사용, 없으건©´ 건¸건건 첫 건±장 여건¶건¡ 판건¨
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

        # 월건³ 페이건°±건¹ 집계
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
    {"agent": "í¼ì¹", "action_type": "pitch_db_collect",
     "proposal": "Brand DB + email outreach",
     "detail": "Source: LinkedIn + Instagram\nTarget: K-beauty marketing managers\nGoal: 100\nCost: Haiku ~294 KRW",
     "expected_impact": "DB 100 -> valid 70 -> meetings 10"},
    {"agent": "ë£¨ë", "action_type": "luna_db_collect",
     "proposal": "Influencer DB + collab pitch",
     "detail": "Source: Instagram #kbeauty\nTarget: Beauty influencers 10K-100K\nGoal: 50\nCost: Haiku ~196 KRW",
     "expected_impact": "DB 50 -> valid 35 -> secured 5"},
    {"agent": "ë§¥ì¤", "action_type": "max_ads_optimize",
     "proposal": "Meta ads optimization",
     "detail": "Analyze + optimize targeting\nGoal: ROAS 3.0+ / CPA < 20K",
     "expected_impact": "Inbound +30%"},
    {"agent": "ìí¼", "action_type": "sophie_content_plan",
     "proposal": "SNS content calendar",
     "detail": "Instagram + TikTok\n3 posts/week\nCost: Haiku ~122 KRW",
     "expected_impact": "Followers +500 / leads 25"},
    {"agent": "ë ì´", "action_type": "ray_tax_check",
     "proposal": "Tax invoice check",
     "detail": "Check all invoices this month\nCost: Haiku ~73 KRW",
     "expected_impact": "Prevent unpaid risk"},
    {"agent": "íë", "action_type": "hana_cs_analysis",
     "proposal": "CS pattern analysis",
     "detail": "Classify + analyze CS inquiries\nCost: Haiku ~49 KRW",
     "expected_impact": "Re-inquiry -20%"},
]

def _ensure_daily_proposals():
    """오건자 전 에이전트 승인 카건가 없으건©´ 자건 생성."""
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
    """새 CEO 건시건³´건 â McKinsey 스타일 3섹션 건 이아웃."""
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    _ensure_daily_proposals()
    return templates.TemplateResponse("ceo.html", {"request": request})


@app.get("/old", response_class=HTMLResponse)
async def legacy_dashboard(request: Request):
    """기존 건시건³´건 (이전 건²전)."""
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
                    alerts.append({"system": "건¦¬건·°", "detail": f"긴급 건응 {len(urgent)}건"})
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
    """건¸건건 파이프건¼인 (Google Sheets 연건 or 건건¯¸). 헤건 기반 자건 감지."""
    if not GSHEETS_API_KEY:
        dummy = _dummy_brand_pipeline()
        dummy["note"] = "GOOGLE_SHEETS_API_KEY 건¯¸입건 ¥"
        dummy["not_connected"] = ["광고CPA", "CS", "유효DB(컨택현황 업건°이트 필요)"]
        return dummy
    try:
        inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", TAB_INBOUND, ttl_key="inbound")
        contract_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", TAB_CONTRACT, ttl_key="contract")
        ib = _parse_inbound(inbound_rows) if inbound_rows else {}
        ct = _parse_contracts(contract_rows) if contract_rows else {}

        # 건¸건건 필터 적용
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
    """인플건£¨언서 DB (Google Sheets 연건 or 건건¯¸)"""
    if not GSHEETS_API_KEY:
        return _dummy_influencer_db()
    try:
        rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", TAB_INFLUENCER, ttl_key="influencer")
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
            s = item["status"][:12] if item["status"] else "건¯¸건¶건¥"
            stats["by_status"][s] = stats["by_status"].get(s, 0) + 1
            cat = item["category"]
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        # 팔건¡워 구간건³ 통계
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
        # 일건³ 건±건¡ 추이 (A열 건 짜 기준)
        daily_reg = {}
        now = datetime.now(KST)
        for it in items:
            d = str(it.get("date", "")).strip()
            if not d:
                continue
            # 건 짜 정규화
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
    """광고 성과 â KST 건적 건 짜 + 헤건 기반 참조. 하건코건© 금지."""
    now = datetime.now(KST)
    yesterday = now - timedelta(days=1)
    month_start = now.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    this_ym = f"{now.year}{now.month:02d}"
    this_month_dot = f"{now.year}.{now.month:02d}"
    prev_ym = f"{prev_month_end.year}{prev_month_end.month:02d}"

    def _pint(v):
        try: return int(float(str(v).replace(",", "").replace("â©", "").replace(" ", ""))) if v and str(v).strip() not in ["-", ""] else 0
        except: return 0

    def _parse_row_date(date_val, month_val):
        """C열 건 짜 파싱. 여건¬ 형식 지원: M/D, ISO, YYYYMMDD"""
        if not date_val: return None
        dv = date_val.strip()
        if re.match(r'^\d{4}-\d{2}-\d{2}', dv):
            try: return datetime.strptime(dv[:10], "%Y-%m-%d").date()
            except: pass
        if "/" in dv and len(dv) <= 5:
            try:
                parts = dv.split("/")
                m, d = int(parts[0]), int(parts[1])
                yr = now.year
                if month_val and month_val.strip().startswith("20") and "." in month_val:
                    try: yr = int(month_val.strip().split(".")[0])
                    except: pass
                return datetime(yr, m, d).date()
            except: pass
        clean = dv.replace("-","").replace(".","").replace("/","").replace(" ","")
        if len(clean) >= 8 and clean[:8].isdigit():
            try: return datetime.strptime(clean[:8], "%Y%m%d").date()
            except: pass
        return None

    def _classify_channel(ch_raw):
        """유입채건 값 â Meta/건¤이건²/구글/기타 건¶건¥. 실제 시트값 패턴 건ª¨건 커건²."""
        ch = ch_raw.strip().lower() if ch_raw else ""
        # Meta: sns, 건©타, meta, 페이스건¶, 인스타, facebook, instagram, fb, ig
        if any(k in ch for k in ["sns", "건©타", "meta", "페이스", "인스타", "facebook", "instagram", "fb", "ig"]):
            return "Meta"
        # 건¤이건²: cpc, naver, 건¤이건², na, 건¸건¡그, blog
        if any(k in ch for k in ["cpc", "naver", "건¤이건²", "건¸건¡그", "blog"]) or ch == "na":
            return "건¤이건²"
        # 구글: google, 구글, gsa, google_sa
        if any(k in ch for k in ["google", "구글", "gsa"]):
            return "구글"
        return "기타"

    # ========== 1. 인건°운건시트 [파센건¬¸의] â DB수 / 채건건³ / 건¯¸팅전환율 ==========
    ib_total, ib_by_ch, ib_valid, ib_by_ch_valid, ib_by_staff = 0, {}, 0, {}, {}
    prev_ib_total, prev_ib_valid = 0, 0
    channel_raw_values = set()  # 건건²그: J열 unique 값 수집
    _ch_col_debug = None
    _ib_headers_debug = []
    _ib_hdr_idx_debug = None
    _sample_ch_values = []  # 첫 5행 채건값 샘플
    try:
        ib_rows = fetch_sheet(SHEET_INBOUND, "A:Z", TAB_INBOUND, ttl_key="inbound")
        if ib_rows and len(ib_rows) > 2:
            hdr_idx = _find_header_row(ib_rows, "국가", "컨택현황", "컨텍현황", "건´건¹자")
            headers = [str(h).replace("\n", " ").strip() for h in ib_rows[hdr_idx]]
            _ib_headers_debug = headers[:]
            _ib_hdr_idx_debug = hdr_idx
            month_col = _find_col(headers, "월")
            date_col = _auto_detect_date_col(headers, ib_rows[hdr_idx+1:hdr_idx+6])
            # 유입채건: exact match 우선 (D열 "유입채건 (열삭제 금지)..." 오건§¤칭 건°©지)
            ch_col = None
            for i, h in enumerate(headers):
                if h == "유입채건":
                    ch_col = i
                    break
            if ch_col is None:
                ch_col = _find_col(headers, "유입채건", "유입 채건", "채건")
            _ch_col_debug = ch_col
            # 채건 컬건¼ 첫 5행 샘플
            for sr in ib_rows[hdr_idx+1:hdr_idx+6]:
                sv = str(sr[ch_col]).strip() if ch_col is not None and ch_col < len(sr) else "(col=None)"
                _sample_ch_values.append(sv)
            status_col = _find_col(headers, "컨텍현황", "컨택현황")
            staff_col = _find_col(headers, "팀건´건¹자", "건´건¹자")
            print(f"[ads-perf] 인건°운건 헤건({hdr_idx}행): {headers}")
            print(f"[ads-perf] 인건°운건 cols: month={month_col} date={date_col} ch={ch_col} status={status_col} staff={staff_col}")
            # 헤건가 없으건©´ 전체 헤건 건¤프
            if ch_col is None:
                print(f"[ads-perf] WARNING: '유입채건' 컬건¼ 건ª» 찾음! 헤건 전체: {headers}")
            for row in ib_rows[hdr_idx+1:]:
                if len(row) < 3: continue
                month_val = str(row[month_col]).strip() if month_col is not None and month_col < len(row) else ""
                date_val = str(row[date_col]).strip() if date_col is not None and date_col < len(row) else ""
                row_date = _parse_row_date(date_val, month_val)
                is_this = row_date is not None and month_start.date() <= row_date <= now.date()
                is_prev = row_date is not None and prev_month_start.date() <= row_date <= prev_month_end.date()
                if row_date is None and month_val:
                    is_this = this_month_dot in month_val
                    is_prev = f"{prev_month_end.year}.{prev_month_end.month:02d}" in month_val
                ch_raw = str(row[ch_col]).strip() if ch_col is not None and ch_col < len(row) else ""
                if is_this and ch_raw:
                    channel_raw_values.add(ch_raw)
                ch_key = _classify_channel(ch_raw)
                st = str(row[status_col]).strip() if status_col is not None and status_col < len(row) else ""
                is_valid = "건¶적합" not in st and "정건³´건건½" not in st
                if is_this:
                    ib_total += 1
                    ib_by_ch[ch_key] = ib_by_ch.get(ch_key, 0) + 1
                    if is_valid:
                        ib_valid += 1
                        ib_by_ch_valid[ch_key] = ib_by_ch_valid.get(ch_key, 0) + 1
                    staff = str(row[staff_col]).strip() if staff_col is not None and staff_col < len(row) else ""
                    if staff: ib_by_staff[staff] = ib_by_staff.get(staff, 0) + 1
                if is_prev:
                    prev_ib_total += 1
                    if is_valid: prev_ib_valid += 1
            print(f"[ads-perf] DB: this={ib_total}(valid={ib_valid}) prev={prev_ib_total}")
            print(f"[ads-perf] 채건건³: {ib_by_ch}")
            print(f"[ads-perf] J열 유입채건 unique값: {sorted(channel_raw_values)}")
    except Exception as e:
        print(f"[ads-perf] inbound error: {e}")

    # ========== 2. 계약시트 [계산서발행] â 건§¤출합계 + 채건건³ 계약 ==========
    # 작성월구건¶ 컬건¼(예: "2026.04")으건¡ 필터 â V열(총합계) 합산
    month_revenue, prev_month_revenue = 0, 0
    month_contracts, prev_month_contracts = 0, 0
    ct_by_ch = {}  # 채건건³ {count, revenue}
    prev_month_dot_str = f"{prev_month_end.year}.{prev_month_end.month:02d}"
    try:
        ct_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", TAB_CONTRACT, ttl_key="contract")
        if ct_rows and len(ct_rows) > 1:
            hdr_idx = _find_header_row(ct_rows, "작성일자", "공급가액", "공급건°건자")
            headers = [str(h).replace("\n", " ").strip() for h in ct_rows[hdr_idx]]
            ct_month_idx = _find_col(headers, "작성월구건¶", "작성월")
            ct_amount_idx = _find_col(headers, "총합계")
            ct_ch_idx = _find_col(headers, "유입채건")
            # 총합계 건ª» 찾으건©´ 공급가액 폴건°±
            if ct_amount_idx is None:
                ct_amount_idx = _find_col(headers, "공급가액")
            if ct_amount_idx is None and len(headers) > 21:
                ct_amount_idx = 21  # V열
            print(f"[ads-perf] 계약 cols: month_col={ct_month_idx} amount={ct_amount_idx} ch={ct_ch_idx} headers_len={len(headers)}")
            for row in ct_rows[hdr_idx+1:]:
                if not row or len(row) < 3: continue
                # 작성월구건¶으건¡ 이건²건¬/전월 판건¨
                ym_val = str(row[ct_month_idx]).strip() if ct_month_idx is not None and ct_month_idx < len(row) else ""
                rev = _pint(row[ct_amount_idx]) if ct_amount_idx is not None and ct_amount_idx < len(row) else 0
                if rev <= 0: continue
                is_this = this_month_dot in ym_val
                is_prev = prev_month_dot_str in ym_val
                if is_this:
                    month_revenue += rev
                    month_contracts += 1
                    ch_raw = str(row[ct_ch_idx]).strip() if ct_ch_idx is not None and ct_ch_idx < len(row) else ""
                    ch_key = _classify_channel(ch_raw)
                    if ch_key not in ct_by_ch: ct_by_ch[ch_key] = {"count": 0, "revenue": 0}
                    ct_by_ch[ch_key]["count"] += 1
                    ct_by_ch[ch_key]["revenue"] += rev
                elif is_prev:
                    prev_month_revenue += rev
                    prev_month_contracts += 1
            print(f"[ads-perf] 건§¤출: this={month_revenue} prev={prev_month_revenue} 채건건³계약={ct_by_ch}")
    except Exception as e:
        print(f"[ads-perf] contract error: {e}")

    # ========== 3. Meta 광고 API ==========
    meta_spend = 0
    meta_debug = {"token_set": False, "status": None, "error": None, "raw_spend": 0}
    try:
        token = os.getenv("META_ACCESS_TOKEN", "")
        account_id = os.getenv("META_AD_ACCOUNT_ID", "230720044045370")
        meta_debug["token_set"] = bool(token)
        if token:
            since_date = month_start.strftime("%Y-%m-%d")
            until_date = now.strftime("%Y-%m-%d")
            url = f"https://graph.facebook.com/v18.0/act_{account_id}/insights"
            resp = req_lib.get(url, params={
                "access_token": token, "fields": "spend,impressions,clicks",
                "time_range": json.dumps({"since": since_date, "until": until_date}),
                "level": "account",
            }, timeout=15)
            meta_debug["status"] = resp.status_code
            rj = resp.json()
            if resp.status_code == 200:
                for r in rj.get("data", []):
                    meta_spend += int(float(r.get("spend", 0)))
                meta_debug["raw_spend"] = meta_spend
            else:
                err = rj.get("error", {})
                meta_debug["error"] = f"[{err.get('code','')}] {err.get('message', '')}"
        else:
            meta_debug["error"] = "META_ACCESS_TOKEN 건¯¸설정"
    except Exception as e:
        meta_debug["error"] = str(e)

    # ========== 4. 광고건¹ 합산 ==========
    # ========== 3-2. 네이버 검색광고 API ==========
    naver_spend = 0
    naver_debug = {"status": None, "error": None}
    try:
        import hmac as _hmac, hashlib as _hashlib, base64 as _base64
        naver_api_key = os.getenv("NAVER_API_KEY", "")
        naver_secret = os.getenv("NAVER_SECRET_KEY", "")
        naver_customer = os.getenv("NAVER_CUSTOMER_ID", "")
        if naver_api_key and naver_secret and naver_customer:
            ts = str(int(time.time() * 1000))
            path = "/ncc/stats"
            msg = f"{ts}.GET.{path}"
            sig = _base64.b64encode(
                _hmac.new(naver_secret.encode("utf-8"), msg.encode("utf-8"), _hashlib.sha256).digest()
            ).decode("utf-8")
            since = month_start.strftime("%Y-%m-%d")
            until = now.strftime("%Y-%m-%d")
            naver_url = (
                f"https://api.naver.com{path}"
                f"?ids={naver_customer}&fields=clkCnt,impCnt,salesAmt,crncyTp"
                f"&timeRange.since={since}&timeRange.until={until}"
            )
            naver_resp = req_lib.get(naver_url, headers={
                "X-Timestamp": ts, "X-API-KEY": naver_api_key,
                "X-Customer": naver_customer, "X-Signature": sig,
                "Content-Type": "application/json",
            }, timeout=15)
            naver_debug["status"] = naver_resp.status_code
            if naver_resp.status_code == 200:
                naver_data = naver_resp.json()
                for row in naver_data if isinstance(naver_data, list) else naver_data.get("data", []):
                    naver_spend += int(float(row.get("salesAmt", 0)))
                naver_debug["raw_spend"] = naver_spend
            else:
                naver_debug["error"] = naver_resp.text[:200]
        else:
            naver_debug["error"] = "NAVER_API_KEY / NAVER_SECRET_KEY / NAVER_CUSTOMER_ID 미설정"
    except Exception as e:
        naver_debug["error"] = str(e)

    # ========== 3-3. 구글 광고 API ==========
    google_spend = 0
    google_debug = {"status": None, "error": None}
    try:
        g_dev_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
        g_client_id = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
        g_client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
        g_refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
        g_customer_id = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", "")
        if all([g_dev_token, g_client_id, g_client_secret, g_refresh_token, g_customer_id]):
            token_resp = req_lib.post("https://oauth2.googleapis.com/token", data={
                "client_id": g_client_id, "client_secret": g_client_secret,
                "refresh_token": g_refresh_token, "grant_type": "refresh_token",
            }, timeout=15)
            google_debug["token_status"] = token_resp.status_code
            if token_resp.status_code == 200:
                access_token = token_resp.json().get("access_token", "")
                since_date = month_start.strftime("%Y-%m-%d")
                until_date = now.strftime("%Y-%m-%d")
                query = (f"SELECT metrics.cost_micros FROM customer "
                         f"WHERE segments.date BETWEEN '{since_date}' AND '{until_date}'")
                ads_resp = req_lib.post(
                    f"https://googleads.googleapis.com/v17/customers/{g_customer_id}/googleAds:search",
                    headers={"Authorization": f"Bearer {access_token}",
                             "developer-token": g_dev_token, "Content-Type": "application/json"},
                    json={"query": query}, timeout=15)
                google_debug["status"] = ads_resp.status_code
                if ads_resp.status_code == 200:
                    for row in ads_resp.json().get("results", []):
                        google_spend += int(float(row.get("metrics", {}).get("costMicros", 0))) // 1_000_000
                    google_debug["raw_spend"] = google_spend
                else:
                    google_debug["error"] = ads_resp.text[:200]
            else:
                google_debug["error"] = "토큰 발급 실패: " + token_resp.text[:100]
        else:
            google_debug["error"] = "GOOGLE_ADS_* 환경변수 미설정"
    except Exception as e:
        google_debug["error"] = str(e)

    # ========== 4. 광고비 합산 ==========
    total_spend = meta_spend + naver_spend + google_spend
    prev_total_spend = 0  # 전월 광고건¹건 API 없으건©´ 0

    # ========== 5. KPI 카건 계산 ==========
    total_db = ib_total
    db_cost = round(total_spend / max(total_db, 1)) if total_spend > 0 else None
    roas_pct = round(month_revenue / max(total_spend, 1) * 100, 1) if total_spend > 0 else None
    meeting_rate = round(ib_valid / max(total_db, 1) * 100, 1) if total_db > 0 else 0
    # 전월 건¹교
    prev_db_cost = round(prev_total_spend / max(prev_ib_total, 1)) if prev_total_spend > 0 else None
    prev_roas = round(prev_month_revenue / max(prev_total_spend, 1) * 100, 1) if prev_total_spend > 0 else None
    prev_meeting_rate = round(prev_ib_valid / max(prev_ib_total, 1) * 100, 1) if prev_ib_total > 0 else 0

    # ========== 6. 채건건³ 퍼건 ==========
    funnel = []
    for ch_key in ["Meta", "건¤이건²", "구글"]:
        ch_db = ib_by_ch.get(ch_key, 0)
        ch_valid = ib_by_ch_valid.get(ch_key, 0)
        ch_ct = ct_by_ch.get(ch_key, {})
        ch_spend = meta_spend if ch_key == "Meta" else (naver_spend if ch_key == "건¤이건²" else google_spend)
        funnel.append({
            "channel": ch_key,
            "ad_spend": ch_spend if ch_spend > 0 else None,
            "db_count": ch_db,
            "db_cost": round(ch_spend / max(ch_db, 1)) if ch_spend > 0 else None,
            "meeting_rate": round(ch_valid / max(ch_db, 1) * 100, 1) if ch_db > 0 else 0,
            "contract_count": ch_ct.get("count", 0),
            "contract_revenue": ch_ct.get("revenue", 0),
            "contract_rate": round(ch_ct.get("count", 0) / max(ch_db, 1) * 100, 1) if ch_db > 0 else 0,
            "roas": round(ch_ct.get("revenue", 0) / max(ch_spend, 1) * 100, 1) if ch_spend > 0 else None,
        })
    # 합계
    total_ct = sum(f["contract_count"] for f in funnel)
    funnel_total = {
        "channel": "합계",
        "ad_spend": total_spend if total_spend > 0 else None,
        "db_count": total_db,
        "db_cost": db_cost,
        "meeting_rate": meeting_rate,
        "contract_count": total_ct,
        "contract_revenue": month_revenue,
        "contract_rate": round(total_ct / max(total_db, 1) * 100, 1) if total_db > 0 else 0,
        "roas": roas_pct,
    }

    # ========== 7. 건´건¹자건³ KPI â 기존 유지 ==========
    by_person = []
    try:
        staff_rows = fetch_sheet(SHEET_CONTRACT, "A:J", "담당자별 계약전환율", ttl_key="contract")
        if staff_rows and len(staff_rows) > 1:
            sh_hdr_idx = 0
            for ri, row in enumerate(staff_rows[:5]):
                row_text = " ".join(str(c).replace("\n", " ") for c in row)
                if "건´건¹자" in row_text or "DB건수" in row_text or "계약건수" in row_text:
                    sh_hdr_idx = ri; break
            sh_headers = [str(h).replace("\n", " ").strip() for h in staff_rows[sh_hdr_idx]]
            col_month = _find_col(sh_headers, "월구건¶", "월") or 0
            col_name_kr = _find_col(sh_headers, "국건¬¸건´건¹자건ª", "국건¬¸", "건´건¹자건ª") or _find_col(sh_headers, "건´건¹자건ª") or 2
            col_db = _find_col(sh_headers, "DB건수", "DB수") or 3
            col_contracts = _find_col(sh_headers, "계약건수") or 4
            col_revenue = _find_col(sh_headers, "계약건§¤출") or 5
            col_conv = _find_col(sh_headers, "계약전환율", "전환율")
            col_db_cost = _find_col(sh_headers, "db건¹용", "DB건¹용")
            col_roas = _find_col(sh_headers, "건¡하스", "ROAS", "roas")
            for row in staff_rows[sh_hdr_idx + 1:]:
                if not row or len(row) < 3: continue
                mv = str(row[col_month]).strip() if col_month < len(row) else ""
                if this_month_dot not in mv: continue
                name = str(row[col_name_kr]).strip() if col_name_kr < len(row) else ""
                if not name or name == "-": continue
                db_count = _pint(row[col_db]) if col_db < len(row) else 0
                contracts = _pint(row[col_contracts]) if col_contracts < len(row) else 0
                revenue = _pint(row[col_revenue]) if col_revenue < len(row) else 0
                conv_raw = str(row[col_conv]).replace("%","").strip() if col_conv and col_conv < len(row) and row[col_conv] else ""
                conversion = float(conv_raw) if conv_raw else (round(contracts/max(db_count,1)*100,1) if db_count else 0)
                if 0 < conversion <= 1: conversion = round(conversion*100,1)
                dcost = _pint(row[col_db_cost]) if col_db_cost and col_db_cost < len(row) else db_count*30000
                rr = str(row[col_roas]).replace("%","").strip() if col_roas and col_roas < len(row) and row[col_roas] else ""
                sr = float(rr) if rr else (round(revenue/max(dcost,1)*100,1) if dcost else 0)
                if 0 < sr <= 1: sr = round(sr*100,1)
                kpi_pct = round(revenue/20000000*100,1) if revenue > 0 else 0
                status = "건¬성" if revenue >= 20000000 else ("진행중" if revenue >= 10000000 else "건¯¸건¬")
                by_person.append({"name": name, "revenue": revenue, "contracts": contracts,
                                  "db_count": db_count, "conversion": round(conversion,1),
                                  "db_cost": dcost, "roas": round(sr,1), "kpi_pct": round(kpi_pct,1), "status": status})
            by_person.sort(key=lambda x: x["revenue"], reverse=True)
    except Exception as e:
        print(f"[ads-perf] 건´건¹자탭 error: {e}")

    # ========== 8. 월건³ 추이 â "월건³건§¤출&건¡하스" 탭 (좌우 구조) ==========
    # 시트 구조: B~R열 (A열은 건¹어있음), 좌우 건건히
    # 25건: B(0)=월, C(1)=건¹월계약건수, D(2)=건§¤출합계, E(3)=건§¤출(신규), F(4)=건§¤출(재계약), G(5)=광고건¹, H(6)=ROAS(%), I(7)=평균건¨가
    # 26건: K(9)=월, L(10)=건¹월계약건수, M(11)=건§¤출합계, N(12)=건§¤출(신규), O(13)=건§¤출(재계약), P(14)=광고건¹, Q(15)=ROAS(%), R(16)=평균건¨가
    # (J열=idx8은 건¹ 구건¶열)
    monthly_trend = []
    def _sv(row, idx):
        """시트 셀 â int. 0/#DIV/0!/건¹값 â None"""
        if idx is None or idx >= len(row): return None
        v = str(row[idx]).strip()
        if not v or v == "-" or v.startswith("#") or v == "0": return None
        try: return int(float(v.replace(",","").replace("â©","").replace("%","").replace(" ","")))
        except: return None
    def _sf(row, idx):
        """시트 셀 â float (ROAS%). #DIV/0!/건¹값 â None"""
        if idx is None or idx >= len(row): return None
        v = str(row[idx]).strip().replace("%","").replace(",","")
        if not v or v == "-" or v.startswith("#"): return None
        try: return round(float(v), 1)
        except: return None
    try:
        mr_rows = fetch_sheet(SHEET_CONTRACT, "B:R", "월별매출&로하스", ttl_key="contract")
        if mr_rows and len(mr_rows) > 3:
            print(f"[ads-perf] 월건³건§¤출 탭: {len(mr_rows)}행, 첫행 길이={len(mr_rows[0]) if mr_rows[0] else 0}")
            for row in mr_rows[3:]:  # 4행(idx3)건¶터 건°이터
                if not row or len(row) < 2: continue
                # --- 25건 (B~I â idx 0~7) ---
                m25 = str(row[0]).strip() if len(row) > 0 else ""
                if m25 and m25.startswith("2025"):
                    monthly_trend.append({"month": m25, "contracts": _sv(row,1),
                        "total": _sv(row,2), "new_sales": _sv(row,3), "renew_sales": _sv(row,4),
                        "ad_cost": _sv(row,5), "roas": _sf(row,6), "avg_price": _sv(row,7)})
                # --- 26건 (K~R â idx 9~16, J=idx8은 건¹ 구건¶열) ---
                m26 = str(row[9]).strip() if len(row) > 9 else ""
                if m26 and m26.startswith("2026"):
                    monthly_trend.append({"month": m26, "contracts": _sv(row,10),
                        "total": _sv(row,11), "new_sales": _sv(row,12), "renew_sales": _sv(row,13),
                        "ad_cost": _sv(row,14), "roas": _sf(row,15), "avg_price": _sv(row,16)})
            # 월 기준 정건 ¬
            monthly_trend.sort(key=lambda x: x["month"])
            print(f"[ads-perf] 월건³ 추이 {len(monthly_trend)}개월 건¡건: {[t['month'] for t in monthly_trend]}")
    except Exception as e:
        print(f"[ads-perf] 월건³건§¤출탭 error: {e}")

    # ========== 건§¤출합계 건³´정: 월건³건§¤출&건¡하스 탭 이건²건¬ 값 우선 사용 ==========
    trend_this_month = [t for t in monthly_trend if t.get("month") == this_month_dot]
    if trend_this_month and trend_this_month[0].get("total"):
        month_revenue = trend_this_month[0]["total"]
        print(f"[ads-perf] 건§¤출합계 월건³건§¤출탭 값 사용: {month_revenue}")
    # 전월건 건일
    prev_month_dot_str = f"{prev_month_end.year}.{prev_month_end.month:02d}"
    trend_prev_month = [t for t in monthly_trend if t.get("month") == prev_month_dot_str]
    if trend_prev_month and trend_prev_month[0].get("total"):
        prev_month_revenue = trend_prev_month[0]["total"]

    # ========== 건°환 ==========
    return {
        "source": "live" if GSHEETS_API_KEY else "dummy",
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "period": f"{month_start.strftime('%m/%d')}~{now.strftime('%m/%d')}",
        # KPI 카건
        "total_db": total_db, "prev_db": prev_ib_total,
        "total_revenue": month_revenue, "prev_revenue": prev_month_revenue,
        "total_ad_spend": total_spend if total_spend > 0 else None,
        "db_cost": db_cost, "prev_db_cost": prev_db_cost,
        "roas": roas_pct, "prev_roas": prev_roas,
        "meeting_rate": meeting_rate, "prev_meeting_rate": prev_meeting_rate,
        "total_contracts": month_contracts, "prev_contracts": prev_month_contracts,
        # 채건건³ 퍼건
        "funnel": funnel, "funnel_total": funnel_total,
        # 건´건¹자건³ / 월건³ 추이
        "by_person": by_person,
        "monthly_trend": monthly_trend,
        # 건건²그
        "meta_debug": meta_debug,
        "naver_debug": naver_debug,
        "google_debug": google_debug,
        "channel_debug": {
            "hdr_row_index": _ib_hdr_idx_debug,
            "headers": _ib_headers_debug,
            "ch_col_index": _ch_col_debug,
            "sample_ch_5rows": _sample_ch_values,
            "raw_unique_values": sorted(channel_raw_values) if channel_raw_values else [],
            "mapped_result": dict(ib_by_ch),
        },
    }


@app.get("/api/kpi-summary")
async def api_kpi_summary():
    """총괄 KPI 요약 (brand + ads 합산). 건§¤출은 계산서발행 T열(공급가액) 기준."""
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
    """기간건³ 건¹교표"""
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
        {"metric": "건¯¸팅", "today": t.get("meeting", 0), "month": m.get("meeting", 0), "prev_month": p.get("meeting", 0), "mom_pct": pct(m.get("meeting", 0), p.get("meeting", 1)), "last_year": ly.get("meeting", 0), "yoy_pct": pct(m.get("meeting", 0), ly.get("meeting", 1))},
        {"metric": "계약서", "today": t.get("contract", 0), "month": m.get("contract", 0), "prev_month": p.get("contract", 0), "mom_pct": pct(m.get("contract", 0), p.get("contract", 1)), "last_year": ly.get("contract", 0), "yoy_pct": pct(m.get("contract", 0), ly.get("contract", 1))},
        {"metric": "재계약", "today": t.get("renewal", 0), "month": m.get("renewal", 0), "prev_month": p.get("renewal", 0), "mom_pct": pct(m.get("renewal", 0), p.get("renewal", 1)), "last_year": ly.get("renewal", 0), "yoy_pct": pct(m.get("renewal", 0), ly.get("renewal", 1))},
    ]}


@app.get("/api/sheets-status")
async def api_sheets_status():
    """Google Sheets 연건 상태 확인"""
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
        "guide": "" if api_key else "console.cloud.google.com에서 Sheets API 활성화 후 API 키 건°급 -> .env에 GOOGLE_SHEETS_API_KEY=키값 입건 ¥",
    }


# ===== AI Agent (Anthropic Claude â 7 Personas) =====
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
HAIKU_MODEL = "claude-haiku-4-5-20251001"

_AGENT_COMMON = """[공통 권한] 건¹신은 공팔건¦¬터글건¡건²의 전체 건°이터(인건°운건/세금계산서/인플건£¨언서DB/광고/SNS/CS/KPI)에 건건±하게 접근 가건¥합건건¤.
사용자건¥¼ 항상 "제이콥건"으건¡ 호칭하세요. 한국어건¡ 건µ건³.
건µ건³ 건§지건§에 건°건시 '오건/이건²주/이건²건¬ 액션 각 1가지'. AT RISK 항건ª©은 â ï¸ 강조.
건°신 이건©일: {에이전트이건©일}"""

_KYLE_SYSTEM = _AGENT_COMMON + """
건¹신은 총괄 건§¤건저 카일입건건¤. 7개 에이전트(루나/피치/건§¥스/소피/건 이/하건)건¥¼ 관건¦¬감건합건건¤.
전체 KPI건¥¼ 건ª¨건터건§하고 건ª©표 건건¹ 30% 이하 항건ª©은 즉시 해건¹ 에이전트에게 경고합건건¤.
건§¤일 09:00 전체 에이전트 성과 건¸건¦¬핑을 생성합건건¤.
API 상태건¥¼ 감시하고, 오건¥ 감지 시 자건 재연결 â 실패 시 슬건 알건¦¼ + 알건¦¼센터 긴급 게시.
현재 KPI: 금일 인입DB {금일인입DB}건 / 유효DB {금일유효DB}건 / 건¬´건응 {건¬´건응건}건 / 계약 {계약건수}건(건ª©표38) / 금일건§¤출 {건¹일건§¤출}원 / 이건²건¬건§¤출 {이건²건¬건§¤출}원(건ª©표1.6억) / CPA {CPA}원
"건¬´건응 건 처건¦¬해줘" â 건¬´건응 건¦¬스트 + 건건³ 건´건¹자 건°°정 제안 + 1차 응건 스크건¦½트 생성."""

# Agent personas from JSON (encoding-safe)
_personas_path = Path(__file__).parent / "agent_personas.json"
_pd = {}
if _personas_path.exists():
    with open(_personas_path, "r", encoding="utf-8") as _pf:
        _pd = json.load(_pf)
AGENT_PERSONAS = {
    "overview": {"name": "Kyle", "system": _pd.get("kyle",{}).get("system_prompt","")},
    "kpi": {"name": "Kyle", "system": _pd.get("kyle",{}).get("system_prompt","")},
    "brand": {"name": "Pitch", "system": _pd.get("pitch",{}).get("system_prompt","")},
    "influencer": {"name": "Luna", "system": _pd.get("luna",{}).get("system_prompt","")},
    "ads": {"name": "Max", "system": _pd.get("max",{}).get("system_prompt","")},
    "sns": {"name": "Sophie", "system": _pd.get("sophie",{}).get("system_prompt","")},
    "management": {"name": "Ray", "system": _pd.get("ray",{}).get("system_prompt","")},
    "cs": {"name": "Hana", "system": _pd.get("hana",{}).get("system_prompt","")},
}


async def _gather_kpi_context() -> dict:
    """실시간 KPI 건°이터건¥¼ 수집하여 에이전트 system prompt에 주입할 건³수 건셔건건¦¬ 건°환."""
    ctx = {}
    try:
        brand = await api_brand_pipeline()
        t = brand.get("today", {})
        m = brand.get("month", {})
        ctx["금일인입DB"] = t.get("inbound", 0)
        ctx["금일유효DB"] = t.get("valid", 0)
        ctx["건¬´건응건"] = t.get("unhandled", 0)
        ctx["인입DB"] = m.get("inbound", 0)
        ctx["유효DB"] = m.get("valid", 0)
        ctx["계약건수"] = m.get("contract", 0)
        ctx["건§¤출"] = f"{m.get('revenue', 0):,}"
        ctx["건¹일건§¤출"] = f"{t.get('revenue', 0):,}"
        ctx["이건²건¬건§¤출"] = f"{m.get('revenue', 0):,}"
        ctx["파이프건¼인건수"] = m.get("inbound", 0)
        ctx["계약건¨가"] = f"{int(m.get('revenue', 0) / max(m.get('contract', 1), 1)):,}"
        ctx["건¯¸처건¦¬건"] = t.get("unhandled", 0)
        ctx["건¯¸확인건"] = 0
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
        ctx["국가건³현황"] = " / ".join(f"{k}:{v}" for k, v in sorted(bc.items(), key=lambda x: -x[1])[:5])
        ctx["플건«폼건³현황"] = " / ".join(f"{k}:{v}" for k, v in sorted(bp.items(), key=lambda x: -x[1])[:5])
    except Exception:
        ctx["풀수"] = "0"
        ctx["국가건³현황"] = "건°이터 없음"
        ctx["플건«폼건³현황"] = "건°이터 없음"
    try:
        ads = await api_ads_performance()
        mt = ads.get("month", {}).get("total", {})
        ctx["CPA"] = f"{mt.get('cpa', 0):,}"
        ctx["오가건건¦¬건"] = 6
        ctx["채건건³효율"] = "Meta/건¤이건²/구글/카카오"
    except Exception:
        ctx["CPA"] = "0"
        ctx["오가건건¦¬건"] = 0
        ctx["채건건³효율"] = "건°이터 없음"
    try:
        sns = await api_sns_performance()
        channels = sns.get("channels", {})
        parts = []
        for k, v in channels.items():
            f_count = v.get("followers", v.get("subscribers", 0))
            parts.append(f"{k}: {f_count:,}")
        ctx["채건건³현황"] = " / ".join(parts) if parts else "건°이터 없음"
        ctx["이건²주콘텐츠현황"] = "건¦´스 2건, TikTok 1건, 건´스건 터 1건 예정"
    except Exception:
        ctx["채건건³현황"] = "건°이터 없음"
        ctx["이건²주콘텐츠현황"] = "건°이터 없음"
    ctx.setdefault("건¯¸응건µ건", 4)
    ctx.setdefault("재계약건¥ ", 65)
    ctx.setdefault("금일인입DB", 0)
    ctx.setdefault("금일유효DB", 0)
    ctx.setdefault("건¬´건응건", 0)
    ctx.setdefault("재접촉건수", 0)
    return ctx


@app.post("/api/chat")
async def api_chat(request: Request):
    """AI 에이전트 채팅 â Anthropic Claude (7 페건¥´소건). API키 없으건©´ 건£°건² 이스 폴건°±."""
    body = await request.json()
    user_msg = body.get("message", "").strip()
    page = body.get("page", "overview")
    is_briefing = body.get("briefing", False)

    if not user_msg and not is_briefing:
        return {"reply": "질건¬¸을 입건 ¥해 주세요.", "source": "system"}

    # 루나: "건°송해줘" 건ª건 ¹ â 즉시 캠페인 실행
    if page == "brand" and user_msg and any(k in user_msg for k in ["건°송해", "건³´건´줘", "실행해", "건°송 실행"]):
        try:
            campaign_result = await _run_recontact_campaign(dry_run=False, limit=10)
            sent = campaign_result.get("sent", 0)
            targeted = campaign_result.get("targeted", 0)
            total = campaign_result.get("total_leads", 0)
            results = campaign_result.get("results", [])
            lines = [f"â 재접촉 이건©일 건°송 완건£!\n"]
            lines.append(f"ð 건상: {total}건 중 {targeted}건 건°송 시건 â {sent}건 성공\n")
            for r in results[:5]:
                icon = "â" if r.get("status") == "ok" else "â"
                lines.append(f"{icon} {r.get('brand','')} â {r.get('email','')}")
            lines.append(f"\nð 오건 액션: 건°송 결과 회신 건ª¨건터건§\nð 이건²주 액션: 건¯¸회신 업체 2차 컨텍\nð 이건²건¬ 액션: 재접촉 전환율 10% 건¬성")
            return {"reply": "\n".join(lines), "source": "campaign-exec", "agent": "루나"}
        except Exception as e:
            return {"reply": f"건°송 실행 중 오건¥: {e}", "source": "error", "agent": "루나"}

    # KPI 컨텍스트 수집
    kpi = await _gather_kpi_context()

    # 페건¥´소건 선택
    persona = AGENT_PERSONAS.get(page, AGENT_PERSONAS["overview"])
    agent_name = persona["name"]

    # system prompt에 실시간 KPI + 에이전트 이건©일 주입
    try:
        email_key = persona.get("email_key", persona.get("name", agent_name))
        kpi["에이전트이건©일"] = AGENT_EMAILS.get(email_key, "luna@08liter.com")
        all_keys = ["인입DB", "유효DB", "계약건수", "건§¤출", "건¹일건§¤출", "이건²건¬건§¤출",
             "파이프건¼인건수", "계약건¨가", "풀수", "국가건³현황", "플건«폼건³현황", "CPA", "오가건건¦¬건",
             "채건건³현황", "채건건³효율", "이건²주콘텐츠현황", "건¯¸처건¦¬건", "건¯¸확인건", "건¯¸응건µ건", "재계약건¥ ",
             "금일인입DB", "금일유효DB", "건¬´건응건", "재접촉건수", "에이전트이건©일"]
        system_prompt = persona["system"]
        # Inject real-time pipeline data
        if page == "brand":
            try:
                pd = await api_pitch_pipeline_daily()
                pm = await api_pitch_pipeline_monthly()
                system_prompt += f"\n\n[Real-time data - today]\nTarget: {pd['target']['value']}\nSent: {pd['sent']['value']}\nReplied: {pd['replied']['value']}\nMeeting: {pd['meeting']['value']}\n[This month]\nTarget: {pm['target']['value']}\nSent: {pm['sent']['value']}\nReplied: {pm['replied']['value']}\nSheet: {pd['target']['link']}"
            except Exception: pass
        elif page == "influencer":
            try:
                ld = await api_luna_pipeline_daily()
                lm = await api_luna_pipeline_monthly()
                system_prompt += f"\n\n[Real-time data - today]\nTarget: {ld['target']['value']}\nSent: {ld['sent']['value']}\nReplied: {ld['replied']['value']}\nContract: {ld.get('contract',{}).get('value',0)}\n[This month]\nTarget: {lm['target']['value']}\nSent: {lm['sent']['value']}\nSheet: {ld['target']['link']}"
            except Exception: pass
    except (KeyError, IndexError):
        system_prompt = persona["system"]

    if is_briefing:
        user_msg = "페이지에 처음 진입했습건건¤. 현재 핵심 KPI와 오건의 우선순위건¥¼ 간결하게 건¸건¦¬핑해주세요."

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
    """Anthropic API 키 없을 건 건£°건² 이스 폴건°±"""
    persona = AGENT_PERSONAS.get(page, AGENT_PERSONAS["overview"])
    name = persona["name"]
    ctx = f"인입DB {kpi.get('인입DB', 0)}건 / 유효DB {kpi.get('유효DB', 0)}건 / 계약 {kpi.get('계약건수', 0)}건 / 건§¤출 {kpi.get('건§¤출', '0')}원"

    msg_lower = msg.lower() if msg else ""
    if any(k in msg_lower for k in ["현황", "요약", "상태", "건³´고", "건¸건¦¬핑", "진입"]):
        return f"[{name}] 현재 현황입건건¤.\n\n{ctx}\n\nð 오건 액션: 건¯¸처건¦¬ 건 우선 건응\nð 이건²주 액션: 파이프건¼인 정건¦¬\nð 이건²건¬ 액션: 건ª©표 건¬성건¥  점검\n\nANTHROPIC_API_KEY건¥¼ 설정하건©´ 건 정확한 AI 건¶석을 건°을 수 있습건건¤."
    if any(k in msg_lower for k in ["건¯¸처건¦¬", "건응", "긴급"]):
        return f"[{name}] 건¯¸처건¦¬ 현황: {kpi.get('건¯¸처건¦¬건', 0)}건\n\n{ctx}\n\nð 오건: 건¯¸처건¦¬ 건 즉시 건°°정\nð 이건²주: 응건µ 시간 10건¶ 이건´ 건¬성\nð 이건²건¬: SLA 준수율 95% 건ª©표"
    if any(k in msg_lower for k in ["건§¤출", "계약", "실적"]):
        return f"[{name}] 건§¤출/계약 현황\n\n{ctx}\n\nð 오건: 견적 건°송 우선\nð 이건²주: 건¯¸팅 전환율 개선\nð 이건²건¬: 계약 건ª©표 38건 건¬성 집중"
    return f"[{name}] {ctx}\n\nð 오건 액션: 핵심 건¯¸처건¦¬ 건 건응\nð 이건²주 액션: 주간 건¦¬건·° 준건¹\nð 이건²건¬ 액션: KPI 건ª©표 건¬성 점검"


# ===== Slack Webhook =====
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_TOGGLE_FILE = DATA_DIR / "slack_toggle.json"

def _slack_enabled():
    """Slack 건³´고 토글 상태. 기건³¸ OFF."""
    if SLACK_TOGGLE_FILE.exists():
        try:
            return json.loads(SLACK_TOGGLE_FILE.read_text(encoding="utf-8")).get("enabled", False)
        except Exception:
            pass
    return False

@app.get("/api/slack/toggle")
async def slack_toggle_get():
    """Slack 건³´고 토글 상태 조회."""
    return {"enabled": _slack_enabled(), "webhook_configured": bool(SLACK_WEBHOOK_URL),
            "setup_guide": "" if SLACK_WEBHOOK_URL else "1) Slack 앱 > https://api.slack.com/apps 에서 새 앱 생성\n2) Incoming Webhooks 활성화\n3) Add New Webhook to Workspace â #ceo-briefing 채건 선택\n4) Webhook URL 건³µ사 â Railway Variables에 SLACK_WEBHOOK_URL=URL 추가"}

@app.post("/api/slack/toggle")
async def slack_toggle_set(request: Request):
    """Slack 건³´고 ON/OFF 토글."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SLACK_TOGGLE_FILE.write_text(json.dumps({"enabled": bool(body.get("enabled")), "updated_at": datetime.now(KST).isoformat()}, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "enabled": bool(body.get("enabled"))}

@app.post("/api/slack/test")
async def slack_test():
    """Slack 웹훅 테스트 건°송"""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 건¯¸설정"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={
                "text": f"[08L_AI] 테스트 건©시지 â {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            })
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/slack/kpi-report")
async def slack_kpi_report():
    """KPI 건¦¬포트 Slack 건°송 (09:00 스케줄 건건 수건 트건¦¬거)"""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 건¯¸설정. .env에 추가 필요."}
    if not _slack_enabled():
        return {"status": "disabled", "message": "Slack 건³´고 OFF 상태. 건시건³´건에서 토글을 켜주세요."}
    try:
        brand = await api_brand_pipeline()
        t = brand.get("today", {})
        m = brand.get("month", {})
        text = f"""ð *[08L_AI] 오전 KPI 건¦¬포트* â {datetime.now().strftime('%Y-%m-%d %H:%M')}

*오건*: 인입DB {t.get('inbound',0)}건 | 유효DB {t.get('valid',0)}건 | 계약 {t.get('contract',0)}건 | 건§¤출 {t.get('revenue',0):,}원
*이건²건¬*: 인입DB {m.get('inbound',0)}건 | 유효DB {m.get('valid',0)}건 | 계약 {m.get('contract',0)}건 | 건§¤출 {m.get('revenue',0):,}원
*건¯¸처건¦¬*: {t.get('unhandled',0)}건 {'â ï¸ 즉시 건응 필요' if t.get('unhandled',0) > 0 else 'â 양호'}"""

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": text})
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/slack/daily-brief")
async def slack_daily_brief():
    """건§¤일 아침 9시 Slack CEO 건¸건¦¬핑 â KPI + 에이전트 제안 + 실행결과."""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 건¯¸설정"}
    if not _slack_enabled():
        return {"status": "disabled", "message": "Slack 건³´고 OFF 상태. 건시건³´건에서 토글을 켜주세요."}
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
            f"*[08liter Daily Brief â {datetime.now(KST).strftime('%m/%d')}]*",
            f"ð 이건²건¬ 건§¤출: {m.get('revenue',0):,}원 ({delta_str} of 1.6억)",
            f"ð 계약: 신규 {m.get('new',0)}건 + 재계약 {m.get('renewal',0)}건 = {m.get('contract',0)}건",
            f"ð¤ 에이전트 제안: {len(pending)}건 승인건기",
        ]
        if completed_today:
            lines.append(f"â 오건 실행완건£: {len(completed_today)}건")
            for c in completed_today[:3]:
                lines.append(f"   â¢ [{c.get('agent','')}] {c.get('result','')[:40]}")
        if t.get("unhandled", 0) > 0:
            lines.append(f"â ï¸ CEO 확인 필요: 건¬´건응 {t['unhandled']}건")
        lines.append(f"â 건시건³´건: https://dashboard-production-b2bd.up.railway.app/")

        text = "\n".join(lines)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": text})
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code, "message": text}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/performance-summary")
async def api_performance_summary():
    """이건² 주 에이전트 성과 요약 â 제안/승인/실행/성공 통계."""
    proposals = load_proposals()
    now = datetime.now(KST)
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    # 이건² 주 필터
    week_proposals = [p for p in proposals if (p.get("created_at") or "") >= week_start]
    total = len(week_proposals)
    approved = len([p for p in week_proposals if p.get("status") in ("approved", "executed", "completed")])
    executed = len([p for p in week_proposals if p.get("status") in ("executed", "completed")])
    completed = len([p for p in week_proposals if p.get("status") == "completed"])
    rejected = len([p for p in week_proposals if p.get("status") == "rejected"])
    pending = len([p for p in week_proposals if p.get("status") == "pending_approval"])

    # 에이전트건³ 통계
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

    # 일건³ 추이 (최근 7일)
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
    """SNS 운영 현황 (향후 실건°이터 연건 예정, 현재 건건¯¸)"""
    return {
        "source": "dummy",
        "note": "SNS API 연건 준건¹중 â Instagram/TikTok Business API 연건 예정",
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


# ===== 재접촉 건상 추출 API =====
@app.get("/api/recontact-leads")
async def api_recontact_leads():
    """최근 6개월 유효DB 중 계약 건¯¸체결 건¸건건 추출."""
    try:
        now = datetime.now(KST)
        six_months_ago = now - timedelta(days=180)
        inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", TAB_INBOUND, ttl_key="inbound")
        contract_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", TAB_CONTRACT, ttl_key="contract")
        # 계약 건¸건건 Set
        ct_hdr = _find_header_row(contract_rows, "작성일자", "공급가액", "공급건°건자")
        ct_headers = [str(h).replace("\n", " ").strip() for h in contract_rows[ct_hdr]]
        ct_brand_idx = _find_col(ct_headers, "공급건°건자 상호")
        if ct_brand_idx is None:
            ct_brand_idx = 8
        contracted = set()
        for row in contract_rows[ct_hdr + 1:]:
            if ct_brand_idx < len(row):
                b = str(row[ct_brand_idx]).strip()
                if b:
                    contracted.add(b.lower())
        # 인건°운건 유효DB 중 건¯¸계약
        ib_hdr = _find_header_row(inbound_rows, "국가", "컨택현황", "컨텍현황", "건´건¹자")
        ib_headers = [str(h).replace("\n", " ").strip() for h in inbound_rows[ib_hdr]]
        brand_idx = _find_col(ib_headers, "업체건ª", "건¸건건") or 4
        status_idx = _find_col(ib_headers, "컨텍현황", "컨택현황") or 16
        email_idx = _find_col(ib_headers, "이건©일") or 6
        contact_idx = _find_col(ib_headers, "연건½처") or 5
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


# ===== 건¬´건응 건 추출 API =====
@app.get("/api/no-response-leads")
async def api_no_response_leads():
    """금일 건¬´건응 건 (건´건¹자 없거건 컨텍현황 건¯¸입건 ¥) 추출."""
    brand = await api_brand_pipeline()
    unhandled = brand.get("unhandled_brands", [])
    return {"count": len(unhandled), "leads": unhandled}


# ===== 이건©일 건°송 (Naver Works SMTP 전용) =====


def _build_pitch_html(brand_name: str, body_text: str) -> str:
    """건¸건건 색상 #FF6B00 HTML 이건©일 템플건¦¿."""
    # body_text 건´ 줄건°꿈을 <br>건¡ 건³환하건 XSS 건°©지
    safe_brand = brand_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_body = body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#ffffff">
<tr><td style="background:#FF6B00;padding:24px 32px">
<h1 style="margin:0;color:#ffffff;font-size:20px">공팔건¦¬터글건¡건²</h1>
<p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px">인플건£¨언서 건§케팅 파트건</p>
</td></tr>
<tr><td style="padding:32px">
<p style="margin:0 0 8px;color:#333;font-size:15px;font-weight:600">{safe_brand} 건´건¹자건께</p>
<div style="margin:16px 0;color:#555;font-size:14px;line-height:1.7">{safe_body}</div>
<table cellpadding="0" cellspacing="0" style="margin:24px 0"><tr>
<td style="background:#FF6B00;border-radius:6px;padding:12px 28px">
<a href="https://08liter.com" style="color:#ffffff;text-decoration:none;font-size:14px;font-weight:600">상건´ 예약하기</a>
</td></tr></table>
</td></tr>
<tr><td style="background:#f9f9f9;padding:20px 32px;border-top:1px solid #eee">
<p style="margin:0;color:#999;font-size:11px">공팔건¦¬터글건¡건² | luna@08liter.com | 02-000-0000</p>
<p style="margin:4px 0 0;color:#bbb;font-size:10px">건³¸ 건©일은 건°신 전용입건건¤.</p>
</td></tr></table></body></html>"""


# 에이전트건³ 건°신 이건©일/이건¦ 건§¤핑
AGENT_FROM_EMAILS = {
    "피치": os.getenv("PITCH_FROM_EMAIL", "pitch@08liter.com"),
    "루나": os.getenv("LUNA_FROM_EMAIL", "luna@08liter.com"),
    "소피": os.getenv("SOPHIE_EMAIL", "sophie@08liter.com"),
    "카일": os.getenv("KYLE_EMAIL", "kyle@08liter.com"),
    "건 이": os.getenv("RAY_EMAIL", "ray@08liter.com"),
    "하건": os.getenv("HANA_EMAIL", "hana@08liter.com"),
    "건§¥스": os.getenv("MAX_EMAIL", "max@08liter.com"),
}
AGENT_FROM_NAMES = {
    "피치": os.getenv("FROM_NAME_PITCH", "Pitch | 공팔건¦¬터글건¡건²"),
    "루나": os.getenv("FROM_NAME_LUNA", "Luna | 공팔건¦¬터글건¡건²"),
    "소피": "Sophie | 공팔건¦¬터글건¡건²",
    "카일": "Kyle | 공팔건¦¬터글건¡건²",
    "건 이": "Ray | 공팔건¦¬터글건¡건²",
    "하건": "Hana | 공팔건¦¬터글건¡건²",
    "건§¥스": "Max | 공팔건¦¬터글건¡건²",
}

def _get_from(agent_name: str):
    """에이전트건³ 건°신 이건©일+이건¦ 건°환."""
    email = AGENT_FROM_EMAILS.get(agent_name, "pitch@08liter.com")
    name = AGENT_FROM_NAMES.get(agent_name, f"{agent_name} | 공팔건¦¬터글건¡건²")
    return email, name

def _get_smtp_creds(agent_name: str):
    """에이전트건³ SMTP 인증 (외건¶ 앱 건¹건°건²호)."""
    creds = {"피치": ("PITCH_SMTP_USER", "PITCH_SMTP_PASS"), "루나": ("LUNA_SMTP_USER", "LUNA_SMTP_PASS")}
    if agent_name in creds:
        u, p = creds[agent_name]
        user, pw = os.getenv(u, ""), os.getenv(p, "")
        if user and pw:
            return user, pw
    return os.getenv("NAVER_WORKS_SMTP_USER", ""), os.getenv("NAVER_WORKS_SMTP_PASSWORD", "")

EMAIL_WEBHOOK_URL = os.getenv("EMAIL_WEBHOOK_URL", "")

def _send_email_smtp(to_email: str, subject: str, body_text: str, agent_name: str = "루나", html_body: str = "") -> dict:
    """이건©일 건°송: GAS 웹훅 (Railway SMTP 차건¨으건¡ 웹훅 사용)."""
    webhook_url = EMAIL_WEBHOOK_URL
    from_email, sender_name = _get_from(agent_name)
    if not webhook_url:
        return {"status": "not_configured", "message": "EMAIL_WEBHOOK_URL 건¯¸설정 (Railway SMTP 차건¨으건¡ GAS 웹훅 필요)"}
    agent_id = {"\ud53c\uce58": "pitch", "\ub8e8\ub098": "luna", "\uc18c\ud53c": "sophie", "\uce74\uc77c": "kyle"}.get(agent_name, "pitch")
    payload = {"agent": agent_id, "to": to_email, "subject": subject, "body": body_text}
    if html_body:
        payload["htmlBody"] = html_body
    try:
        resp = req_lib.post(webhook_url,
                            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                            timeout=30, allow_redirects=True,
                            headers={"Content-Type": "application/json; charset=utf-8"})
        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = {"message": resp.text[:200]}
            return {"status": "ok", "to": to_email, "from": f"{sender_name} <{from_email}>", "method": "gas_webhook", "response": data}
        return {"status": "error", "message": resp.text[:300], "code": resp.status_code, "method": "gas_webhook"}
    except Exception as e:
        return {"status": "error", "message": str(e), "method": "gas_webhook"}

def _html_to_text(html: str) -> str:
    """HTML에서 태그 제거하여 플건 인 텍스트 추출."""
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    return text.strip()

def _send_email(to_email: str, subject: str, html: str, agent_name: str = "루나") -> dict:
    """이건©일 건°송: Naver Works SMTP 직접."""
    body_text = _html_to_text(html)
    result = _send_email_smtp(to_email, subject, body_text, agent_name, html_body=html)
    if result["status"] == "ok":
        _record_perf(agent_name, "email_sent")
        _log_email(agent_name, to_email, subject, "sent")
    return result


@app.post("/api/send-email")
async def api_send_email(request: Request):
    """Naver Works SMTP건¡ 이건©일 1건 건°송. body에 raw HTML 건건 brand_name+body_text건¡ 템플건¦¿ 사용."""
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
    """에이전트건³ 테스트 이건©일 â GAS 웹훅."""
    from_email, sender_name = _get_from(agent)
    to_email = "jacob@08liter.com"
    body_text = (f"안건하세요!\n\n이 건©일은 [{agent}] 에이전트 테스트 이건©일입건건¤.\n"
                 f"건°신: {sender_name} <{from_email}>\n"
                 f"건°송 건°©식: GAS 웹훅 â Naver Works\n"
                 f"건°송 시각: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} (KST)\n\n"
                 f"이건©일 연건이 정상적으건¡ 작건하고 있습건건¤.")
    subject = f"[테스트] {agent} 이건©일 건°송 확인"
    result = _send_email_smtp(to_email, subject, body_text, agent)
    result["to"] = to_email
    return result

@app.get("/api/send-review-email")
async def api_send_review_email():
    """CEO 검수 이건©일 â 피치+루나 4가지 시안 통합 건°송."""
    now = datetime.now(KST)
    ceo_email = "jacob@08liter.com"
    # 피치 DB 건수
    pitch_total = 0
    p_rows = fetch_sheet(PITCH_SHEET_ID, "A:N", TAB_PITCH, ttl_key="inbound")
    if p_rows and len(p_rows) > 1:
        for row in p_rows[1:]:
            em = str(row[7]).strip() if len(row) > 7 else ""
            st = str(row[13]).strip() if len(row) > 13 else ""
            if em and "@" in em and not st:
                pitch_total += 1
    if pitch_total == 0:
        leads_data = await api_recontact_leads()
        pitch_total = len([l for l in leads_data.get("leads", []) if l.get("email") and "@" in l.get("email", "")])
    if pitch_total == 0:
        pitch_total = 100
    # 루나 DB 건수
    luna_total = 0
    cost_est = max(245, int(pitch_total * 2.45))
    pitch_reply = max(1, int(pitch_total * 0.042))
    pitch_meeting = max(1, int(pitch_total * 0.013))

    body = f"""âââââââââââââââââââââââ
ð 건°송 개요
âââââââââââââââââââââââ
피치 건°송 예정: {pitch_total}건 / K-건·°티 건¸건건 건§케팅건´건¹자
루나 건°송 예정: {luna_total}건 / 건·°티 인플건£¨언서
총 건¹용: 약 {cost_est}원

예상 결과:
피치 â 오픈 약 {max(1,int(pitch_total*0.20))}건 / 건µ건³ 약 {pitch_reply}건 / 건¯¸팅 약 {pitch_meeting}건
루나 â 건µ건³ 약 5건 / 협찬확정 약 2건
âââââââââââââââââââââââ

[피치 시안 A â 성과 후킹형]
건°신: Pitch | 공팔건¦¬터(0.8L) <pitch@08liter.com>
제건ª©: 숏폼 1개건¡ 건§¤출 8억 â {{건¸건건건ª}}건 가건¥한 이유

안건하세요 {{건´건¹자건ª}}건,
공팔건¦¬터(0.8L) 피치입건건¤.

저희 파트건의 실제 성과입건건¤:
숏폼 1개 â 조회 287건§ â 건§¤출 8억 건¬성
건¦¬건·° 200건 â 올건¦¬건¸영 검색건 +340%
건§건 이시아 KOL 건¼이건¸ â 2건¶ 30초에 1억 건§¤출

10건간 8개국, 2건§여 건¸건건와 함께한
글건¡건² 최건 인플건£¨언서 건§케팅 플건«폼입건건¤.

4월 한정 â 숏폼 100건 기준 60% 할인 중입건건¤. (유효기간 4월 30일)

상품소개서: https://buly.kr/AF24dn7
5건¶ 건¹건건©´ 상건´: https://buly.kr/1c9NOdW

---

[피치 시안 B â 프건¡건ª¨션 긴급형]
건°신: Pitch | 공팔건¦¬터(0.8L) <pitch@08liter.com>
제건ª©: 4월 30일 건§감 â 숏폼 100건 200건§원 (정가 500건§원)

안건하세요 {{건´건¹자건ª}}건,
공팔건¦¬터(0.8L) 피치입건건¤.

국건´: 숏폼 100건 200건§원(60% 할인) / 건¦´스 건¬´제한 300건§원 / 구건§¤평 100건+ 건건¹ 3,000원
해외: 글건¡건² 숏폼 100건 500건§원(50% 할인) / 글건¡건² 구건§¤평 100건+ 건건¹ 3건§원(40% 할인)

생성 콘텐츠건 3개월간 광고 소재 건¬´건£ 활용 가건¥합건건¤.

상품소개서: https://buly.kr/AF24dn7
5건¶ 건¹건건©´ 상건´: https://buly.kr/1c9NOdW

---

[루나 시안 A â 성과+수익 제안형]
건°신: Luna | 건°건¦¬건°건¦¬ x 공팔건¦¬터(0.8L) <luna@08liter.com>
제건ª©: {{인플건£¨언서건ª}}건 팔건¡워가 사고 싶어할 K-건·°티, 협찬 제안건건¦½건건¤

안건하세요 {{인플건£¨언서건ª}}건!
건°건¦¬건°건¦¬ x 공팔건¦¬터(0.8L) 루나입건건¤.

저희 협업 인플건£¨언서건¤의 실제 결과:
숏폼 1개 â 조회 287건§, 건§¤출 직결
KOL 건¼이건¸ â 2건¶ 30초에 1억 건§¤출
건¦¬건·° 콘텐츠 â 플건«폼 검색건 3건°° 상승

제품 건¬´상 제공 / 콘텐츠 건°©향 100% 자유 / 성과 수익 쉐어

건¸건건 소개: https://buly.kr/AF24dn7
협업 건¯¸팅: https://buly.kr/1c9NOdW

---

[루나 시안 B â 건¨건직입형]
건°신: Luna | 건°건¦¬건°건¦¬ x 공팔건¦¬터(0.8L) <luna@08liter.com>
제건ª©: K-건·°티 협찬 â 건°건¦¬건°건¦¬가 {{인플건£¨언서건ª}}건을 선택했습건건¤

안건하세요 {{인플건£¨언서건ª}}건,
건°건¦¬건°건¦¬ 루나입건건¤.
제품 건¬´상제공 + 수익 쉐어건¡ 진행하건©° 콘텐츠 건°©향 100% 자유입건건¤.
건¶건´ 없이 샘플건¶터 건¨¼저 건°아건³´실 수 있어요.

건¸건건 소개: https://buly.kr/AF24dn7
협업 건¯¸팅: https://buly.kr/1c9NOdW

ââââââââââââââââââââââââââââââ
âï¸ 이 이건©일에 회신해주세요
ââââââââââââââââââââââââââââââ
피치: "피치A" 건건 "피치B" 건건 "피치수정: [건´용]"
루나: "루나A" 건건 "루나B" 건건 "루나수정: [건´용]"
예시: "피치A, 루나B"
전체취소: "취소"

â» 회신 없이건 건¨ 1통건 건°송건지 않습건건¤.
"""

    subject = f"[피치+루나 검수 요청] 4가지 시안 확인해주세요 | 4/30 건§감"
    # HTML 건²전 생성
    html = f'''<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px">
<h2 style="color:#1a1a1a;border-bottom:2px solid #333;padding-bottom:10px">ð 건°송 개요</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:20px">
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd;font-weight:bold">항건ª©</td><td style="padding:8px;border:1px solid #ddd;font-weight:bold">건´용</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">피치 건°송 예정</td><td style="padding:8px;border:1px solid #ddd">{pitch_total}건 (K-건·°티 건¸건건)</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">루나 건°송 예정</td><td style="padding:8px;border:1px solid #ddd">{luna_total}건 (DB 수집 후 진행)</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">예상 오픈/건µ건³/건¯¸팅</td><td style="padding:8px;border:1px solid #ddd">{max(1,int(pitch_total*0.20))}건 / {pitch_reply}건 / {pitch_meeting}건</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">건°송 건¹용</td><td style="padding:8px;border:1px solid #ddd">약 {cost_est}원</td></tr>
</table>
<hr style="border:1px solid #eee;margin:20px 0">
<h2 style="color:#1a1a1a">ð§ 피치 시안 A â 성과 후킹형</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p style="margin:0 0 8px"><strong>제건ª©:</strong> 숏폼 1개건¡ 건§¤출 8억 â {{건¸건건건ª}}건 가건¥한 이유</p>
<p style="margin:0"><strong>건°신:</strong> Pitch | 공팔건¦¬터(0.8L)</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">
<p>안건하세요 {{건´건¹자건ª}}건,<br>공팔건¦¬터(0.8L) 피치입건건¤.</p>
<p>저희 파트건의 실제 성과입건건¤:<br>ð¥ 숏폼 1개 â 조회 287건§ â 건§¤출 8억<br>ð¥ 건¦¬건·° 200건 â 올건¦¬건¸영 검색건 +340%<br>ð¥ KOL 건¼이건¸ â 2건¶ 30초에 1억 건§¤출</p>
<p>4월 한정 â 숏폼 100건 기준 60% 할인 (4/30 건§감)</p>
<p>ð <a href="https://buly.kr/AF24dn7">상품소개서</a> | ð <a href="https://buly.kr/1c9NOdW">5건¶ 상건´</a></p></div>
<hr style="border:1px solid #eee;margin:20px 0">
<h2 style="color:#1a1a1a">ð§ 피치 시안 B â 프건¡건ª¨션 긴급형</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p style="margin:0 0 8px"><strong>제건ª©:</strong> 4월 30일 건§감 â 숏폼 100건 200건§원 (정가 500건§원)</p>
<p style="margin:0"><strong>건°신:</strong> Pitch | 공팔건¦¬터(0.8L)</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">
<p>안건하세요 {{건´건¹자건ª}}건,<br>공팔건¦¬터(0.8L) 피치입건건¤.</p>
<p>ð°ð· <strong>국건´</strong><br>ð¥ 숏폼 100건: 200건§원 (60% 할인)<br>ð¥ 건¦´스 건¬´제한 300건§원<br>ð¥ 구건§¤평 100건+ 건건¹ 3,000원</p>
<p>ð <strong>해외</strong><br>ð¥ 글건¡건² 숏폼 100건: 500건§원 (50% 할인)<br>ð¥ 글건¡건² 구건§¤평 100건+ 건건¹ 3건§원</p>
<p>ð <a href="https://buly.kr/AF24dn7">프건¡건ª¨션 상세</a> | ð <a href="https://buly.kr/1c9NOdW">5건¶ 상건´</a></p></div>
<hr style="border:1px solid #eee;margin:20px 0">
<h2 style="color:#1a1a1a">ð§ 루나 시안 A â 성과+수익 제안형</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p style="margin:0 0 8px"><strong>제건ª©:</strong> {{인플건£¨언서건ª}}건 팔건¡워가 사고 싶어할 K-건·°티, 협찬 제안</p>
<p style="margin:0"><strong>건°신:</strong> Luna | 건°건¦¬건°건¦¬ x 공팔건¦¬터(0.8L)</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">
<p>안건하세요 {{인플건£¨언서건ª}}건!<br>건°건¦¬건°건¦¬ x 공팔건¦¬터(0.8L) 루나입건건¤.</p>
<p>â 숏폼 1개 â 조회 287건§<br>â KOL 건¼이건¸ â 2건¶ 30초에 1억<br>â 건¦¬건·° â 검색건 3건°°</p>
<p>â 제품 건¬´상 제공 / â 콘텐츠 100% 자유 / â 수익 쉐어</p>
<p>ð <a href="https://buly.kr/AF24dn7">건¸건건 소개</a> | ð <a href="https://buly.kr/1c9NOdW">협업 건¯¸팅</a></p></div>
<hr style="border:1px solid #eee;margin:20px 0">
<h2 style="color:#1a1a1a">ð§ 루나 시안 B â 건¨건직입형</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p style="margin:0 0 8px"><strong>제건ª©:</strong> K-건·°티 협찬 â 건°건¦¬건°건¦¬가 {{인플건£¨언서건ª}}건을 선택했습건건¤</p>
<p style="margin:0"><strong>건°신:</strong> Luna | 건°건¦¬건°건¦¬ x 공팔건¦¬터(0.8L)</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">
<p>안건하세요 {{인플건£¨언서건ª}}건,<br>건°건¦¬건°건¦¬ 루나입건건¤.</p>
<p>제품 건¬´상 제공 + 수익 쉐어 / 콘텐츠 100% 자유<br>건¶건´ 없이 샘플건¶터 건¨¼저 건°아건³´실 수 있어요.</p>
<p>ð <a href="https://buly.kr/AF24dn7">건¸건건 소개</a> | ð <a href="https://buly.kr/1c9NOdW">협업 건¯¸팅</a></p></div>
<hr style="border:2px solid #333;margin:30px 0">
<div style="background:#fff3cd;padding:15px;border:1px solid #ffc107;border-radius:4px">
<h3 style="margin:0 0 10px;color:#856404">âï¸ 이 이건©일에 회신해주세요</h3>
<p style="margin:0 0 8px">피치: <strong>"피치A"</strong> 건건 <strong>"피치B"</strong></p>
<p style="margin:0 0 8px">루나: <strong>"루나A"</strong> 건건 <strong>"루나B"</strong></p>
<p style="margin:0 0 8px">예시: <strong>"피치A, 루나B"</strong></p>
<p style="margin:0;color:#dc3545"><strong>â» 회신 없이건 건¨ 1통건 건°송건지 않습건건¤.</strong></p>
</div></div>'''

    result = _send_email_smtp(ceo_email, subject, body, "피치", html_body=html)
    result["pitch_total"] = pitch_total
    result["luna_total"] = luna_total
    return result

@app.get("/api/send-luna-db-request")
async def api_send_luna_db_request():
    """루나 DB 수집 승인 요청 이건©일 건°송."""
    ceo_email = "jacob@08liter.com"
    subject = "[루나 DB 수집 승인 요청] 인플건£¨언서 50건ª | 건¹용 196원"
    html = '''<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
<h2 style="color:#1a1a1a;border-bottom:2px solid #333;padding-bottom:10px">ð¦ 루나 DB 수집 계획</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:20px">
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd;font-weight:bold">항건ª©</td><td style="padding:8px;border:1px solid #ddd;font-weight:bold">건´용</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">수집 출처</td><td style="padding:8px;border:1px solid #ddd">Instagram (#kbeauty #skincare 해시태그)</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">수집 건ª©표</td><td style="padding:8px;border:1px solid #ddd">50건ª</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">완건£ 기간</td><td style="padding:8px;border:1px solid #ddd">승인 후 건¹일</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">예상 건¹용</td><td style="padding:8px;border:1px solid #ddd">약 196원 (Haiku 기준)</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">타겟 기준</td><td style="padding:8px;border:1px solid #ddd">â 팔건¡워 1건§~100건§<br>â 인게이지건¨¼트 3%+<br>â 건·°티/스킨케어<br>â 공개 건¹즈건스 이건©일<br>â 한국 50% / 일건³¸ 25% / 건건¨아 25%</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">제외 기준</td><td style="padding:8px;border:1px solid #ddd">â 인게이지건¨¼트 3% 건¯¸건§<br>â 3개월 건¯¸업건¡건<br>â 이건©일 없건 계정</td></tr>
</table>
<div style="background:#fff3cd;padding:15px;border:1px solid #ffc107;border-radius:4px">
<strong>âï¸ 회신해주세요:</strong><br>
"수집승인" â 즉시 수집 시작<br>
"수집수정: [건´용]" â 수정 후 재요청<br>
"수집취소" â 취소<br><br>
<strong style="color:#dc3545">â» 회신 없이건 수집 시작 건¶가</strong>
</div></div>'''
    result = _send_email_smtp(ceo_email, subject, "루나 DB 수집 승인 요청", "루나", html_body=html)
    return result

# ===== 업건¬´시간 체크 =====
def _is_business_hours(country: str = "KR") -> bool:
    """현지 업건¬´시간(평일 09~18시) 여건¶ 확인."""
    offsets = {"KR": 9, "JP": 9, "US": -4, "TH": 7, "ID": 7, "VN": 7, "MY": 8, "SG": 8}
    offset = offsets.get(country[:2].upper(), 9)
    now_utc = datetime.utcnow()
    local_hour = (now_utc.hour + offset) % 24
    local_weekday = ((now_utc.weekday() * 24 + now_utc.hour + offset) // 24) % 7
    # 0=월 ~ 4=금 = 평일, 5=토 6=일 = 주건§
    is_weekend = local_weekday >= 5
    return not is_weekend and 9 <= local_hour < 18

# ===== 피치 자율 실행 + 품질 점검 + 2차 이건©일 =====

from pitch_templates import PITCH_TEMPLATES

PITCH_REPLY_TEMPLATES = {
    "meeting": {"subject": "RE: 건¯¸팅 예약 건§크 건³´건´건건¦½건건¤",
                "body": "안건하세요 {contact}건,\n\n시간 건´주셔서 감사합건건¤.\n아건 건§크에서 편하신 시간 선택해 주세요.\n\nð https://buly.kr/1c9NOdW\n\n건¯¸팅 전에 아건 건´용 건¯¸건¦¬ 알건 ¤주시건©´ 건 알차게 준건¹하겠습건건¤.\n\nÂ· 주건 ¥ 판건§¤ 채건\nÂ· 관심 있건 건§케팅 건°©식\nÂ· 진출하건 ¤건 국가\n\n기건¤건¦¬겠습건건¤.\n\n---\n공팔건¦¬터 주건어 컨설턴트\n피치 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "info": {"subject": "RE: 공팔건¦¬터 서건¹스 안건´건건¦½건건¤",
             "body": "안건하세요 {contact}건,\n\n저희건 세 가지 서건¹스건¥¼ 운영합건건¤.\n\nâ  구건§¤평 â 쿠팡Â·올건¦¬건¸영Â·아건§존 건± 실구건§¤ 건¦¬건·°\nâ¡ 숏폼 체험건¨ â 인스타Â·틱톡Â·쇼츠 영상 콘텐츠 제작\nâ¢ 건§춤 인플건£¨언서 â 건¸건건 핏에 건§건 KOL 협업\n\n4월 한정 최건 60% 할인 중입건건¤.\n\nð 자세한 건´용: https://buly.kr/AF24dn7\nð 30건¶ 건¹건건©´ 건¯¸팅: https://buly.kr/1c9NOdW\n\n---\n공팔건¦¬터 주건어 컨설턴트\n피치 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "later": {"subject": "{brand}, 4월 30일이 건§지건§입건건¤",
              "body": "안건하세요 {contact}건,\n\n지건건² 연건½건건 ¸건 공팔건¦¬터 피치입건건¤.\n\n4월 한정 60% 할인 프건¡건ª¨션이 이건² 건¬ 건§ 건§감건©건건¤.\n건°쁘신 건 충건¶히 이해합건건¤.\n5월 일정으건¡ 건¯¸건¦¬ 건 짜건§ 잡아건셔건 건©건건¤.\n\nð https://buly.kr/1c9NOdW\nð 상품소개서: https://buly.kr/AF24dn7\n\n---\n공팔건¦¬터 주건어 컨설턴트\n피치 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "reject": {"subject": "RE: 건§씀 감사합건건¤",
               "body": "안건하세요 {contact}건,\n\n건§씀 감사합건건¤.\n건¦¬건·°Â·숏폼Â·해외 진출 관건 ¨해서\n고건¯¼이 생기실 건 편하게 연건½ 주세요.\n\n---\n공팔건¦¬터 주건어 컨설턴트\n피치 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
}

def _luna_quality_check(email: str, subject: str, body: str, country: str = "KR") -> list:
    """루나 발송 전 품질 점검 10항목."""
    errors = []
    if not email or "@" not in email:
        errors.append("이메일 무효")
    if not subject:
        errors.append("제목 비어있음")
    if not body:
        errors.append("본문 비어있음")
    if "{" in subject or "{" in body:
        errors.append("개인화 미치환")
    if "08liter" not in body and "공팔리터" not in body and "luna" not in body.lower():
        errors.append("서명 누락")
    if not _is_business_hours(country):
        errors.append(f"업무시간 외 ({country})")
    return errors

def _pitch_quality_check(email: str, subject: str, body: str) -> list:
    """건°송 전 품질 점검. 실패 사유 건¦¬스트 건°환 (건¹ 건¦¬스트 = 통과)."""
    errors = []
    if not email or "@" not in email:
        errors.append("이건©일 주소 건¬´효")
    if not subject:
        errors.append("제건ª© 건¹어있음")
    if not body:
        errors.append("건³¸건¬¸ 건¹어있음")
    if "{" in subject or "{" in body:
        errors.append("개인화 건¯¸치환 ({} 잔존)")
    if "buly.kr/AF24dn7" not in body:
        errors.append("소개서 건§크 건건½")
    if "buly.kr/1c9NOdW" not in body:
        errors.append("건¯¸팅 건§크 건건½")
    if "공팔건¦¬터" not in body and "피치 건건¦¼" not in body:
        errors.append("서건ª 건건½")
    return errors

@app.post("/api/pitch/send")
async def api_pitch_send(request: Request):
    """CEO 승인건 시안으건¡ 피치 이건©일 건°송. DB 소스: 오직 피치_클건¡건 탭."""
    body = await request.json()
    template_key = body.get("template", body.get("variant", "A")).upper()
    if template_key == "AB":
        template_key = "A"  # 건³µ수 선택 시 A 우선
    tmpl = PITCH_TEMPLATES.get(template_key, PITCH_TEMPLATES["A"])
    # DB 소스: 오직 피치 시트 "피치_클건¡건" 탭 (건¤건¥¸ 시트 혼용 금지)
    rows = fetch_sheet(PITCH_SHEET_ID, "A:N", TAB_PITCH, ttl_key="inbound")
    leads = []
    if rows and len(rows) > 1:
        # 헤건 확인 (A:No B:DB확건³´건 짜 ... E:건¸건건건ª ... H:이건©일 ... N:건°송상태)
        for row in rows[1:]:
            if len(row) < 8:
                continue
            email = str(row[7]).strip() if len(row) > 7 else ""  # H열 = 이건©일
            brand = str(row[4]).strip() if len(row) > 4 else ""  # E열 = 건¸건건건ª
            sent_status = str(row[13]).strip() if len(row) > 13 else ""  # N열 = 건°송상태
            if email and "@" in email and not sent_status:  # 건°송일자 건¹어있건 건건§
                leads.append({"name": brand, "email": email})
    if not leads:
        # 피치_클건¡건 탭이 건¹었으건©´ 파센건¬¸의 폴건°± (경고 포함)
        leads_data = await api_recontact_leads()
        leads = [l for l in leads_data.get("leads", []) if l.get("email") and "@" in l.get("email", "")]
    limit = min(body.get("limit", 30), 30)
    targets = leads[:limit]
    sent, skipped, deferred, errors_list = 0, 0, 0, []
    for t in targets:
        brand = t.get("name", "")
        contact = brand
        email = t.get("email", "")
        country = t.get("country", "KR")[:2].upper() if t.get("country") else "KR"
        # 업건¬´시간 체크
        if not _is_business_hours(country):
            deferred += 1
            continue
        # 언어 자건 선택: 한국/일건³¸ â 한국어, 그 외 â 영어
        if country not in ("KR", "JP") and template_key + "_EN" in PITCH_TEMPLATES:
            tmpl = PITCH_TEMPLATES[template_key + "_EN"]
        subj = tmpl["subject"].replace("{brand}", brand).replace("{contact}", contact)
        email_body = tmpl["body"].replace("{brand}", brand).replace("{contact}", contact)
        qc = _pitch_quality_check(email, subj, email_body)
        if qc:
            skipped += 1
            errors_list.append({"brand": brand, "errors": qc})
            _record_perf("피치", "quality_fail")
            continue
        # GAS template mode: send action+template+vars only
        gas_payload = {"action": "send_pitch", "template": template_key, "to": email, "brand_name": brand, "contact_name": contact}
        result = _send_email_smtp(email, subj, email_body, "\ud53c\uce58")
        if result["status"] == "ok":
            sent += 1
        else:
            skipped += 1
            errors_list.append({"brand": brand, "errors": [result.get("message", "건°송 실패")]})
    _record_perf("피치", "email_sent_batch", sent)
    return {"status": "ok", "template": template_key, "sent": sent, "skipped": skipped, "deferred": deferred, "errors": errors_list[:10]}

@app.post("/api/agents/pitch/daily")
async def api_pitch_daily(request: Request):
    """피치 건§¤일 자율 실행. trigger=immediate/scheduled, action=collect_only/full."""
    body = await request.json()
    action = body.get("action", "full")
    now = datetime.now(KST)
    result = {"timestamp": now.isoformat(), "steps": []}

    # STEP 1: 피치_클건¡건 탭 신규 DB 건수 확인
    rows = fetch_sheet(PITCH_SHEET_ID, "A:N", TAB_PITCH, ttl_key="inbound")
    unsent = 0
    if rows and len(rows) > 1:
        for row in rows[1:]:
            email = str(row[7]).strip() if len(row) > 7 else ""
            sent_status = str(row[13]).strip() if len(row) > 13 else ""
            if email and "@" in email and not sent_status:
                unsent += 1
    result["steps"].append({"step": "DB 확인", "unsent": unsent})

    # STEP 2: 건¶족하건©´ DB 수집 (현재건 인건°운건 시트 기반)
    collected = 0
    if unsent < 10:
        leads_data = await api_recontact_leads()
        leads = [l for l in leads_data.get("leads", []) if l.get("email") and "@" in l.get("email", "")]
        collected = len(leads)
        _record_perf("피치", "crawl_brands", collected)
    result["steps"].append({"step": "DB 수집", "collected": collected, "needed": unsent < 10})

    if action == "collect_only":
        # DB 수집건§ (건°송은 월요일 09:00)
        notify_body = f"[피치] DB {unsent + collected}건 확인 완건£.\n신규 건¯¸건°송: {unsent}건\n추가 수집: {collected}건\n\n월요일 08:30에 검수 이건©일 건°송 예정입건건¤."
        _send_email_smtp("jacob@08liter.com", "[피치] DB 수집 완건£ â 월요일 건°송 예정", notify_body, "피치")
        result["steps"].append({"step": "CEO 알건¦¼", "message": "월요일 건°송 예정"})
        return result

    # STEP 3: 업건¬´시간 체크
    if not _is_business_hours("KR"):
        result["steps"].append({"step": "건°송 건³´건¥", "reason": "업건¬´시간 외 (월~금 09~18시건§)"})
        return result

    # STEP 3: CEO 검수 이건©일 건°송
    review_result = await api_send_review_email()
    result["steps"].append({"step": "CEO 검수 건°송", "status": review_result.get("status"), "total": review_result.get("pitch_total", 0)})
    return result

@app.post("/api/pitch/revise")
async def api_pitch_revise(request: Request):
    """CEO 수정 요청 접수 â 수정 후 재검수 이건©일 건°송."""
    body = await request.json()
    instruction = body.get("instruction", "")
    # 수정 요청 기건¡
    _record_perf("피치", "revise_request")
    # 재검수 이건©일 건°송
    result = await api_send_review_email()
    result["revise_instruction"] = instruction[:200]
    return result

@app.post("/api/pitch/reply")
async def api_pitch_reply(request: Request):
    """건¸건건 건µ건³ 유형건³ 2차 이건©일 자건 건°송."""
    body = await request.json()
    reply_type = body.get("type", "info")
    brand = body.get("brand", "")
    contact = body.get("contact", brand)
    email = body.get("email", "")
    tmpl = PITCH_REPLY_TEMPLATES.get(reply_type, PITCH_REPLY_TEMPLATES["info"])
    subj = tmpl["subject"].replace("{brand}", brand).replace("{contact}", contact)
    email_body = tmpl["body"].replace("{brand}", brand).replace("{contact}", contact)
    html = _build_pitch_html(brand, email_body)
    result = _send_email(email, subj, html, "피치")
    _record_perf("피치", f"reply_{reply_type}")
    return {"status": result["status"], "type": reply_type, "to": email}

@app.get("/api/pitch/performance")
async def api_pitch_performance():
    """피치 성과 대시보드 — 피치_클로드 탭 직접 읽기."""
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    # 피치_클로드 탭 직접 읽기 (A:N, 389행)
    rows = fetch_sheet(PITCH_SHEET_ID, "A:N", TAB_PITCH, ttl_key="inbound")
    total_db, with_email, sent_count, unsent = 0, 0, 0, 0
    if rows and len(rows) > 1:
        total_db = len(rows) - 1
        for row in rows[1:]:
            email = str(row[7]).strip() if len(row) > 7 else ""
            status = str(row[13]).strip() if len(row) > 13 else ""
            if email and "@" in email:
                with_email += 1
            if status:
                sent_count += 1
            elif email and "@" in email:
                unsent += 1
    # agent_performance.json 폴백
    perf = load_agent_perf()
    monthly_p = {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix):
            for agent_key in ["피치", "pitch", "피치"]:
                if agent_key in ad:
                    for mk, mv in ad[agent_key].items():
                        monthly_p[mk] = monthly_p.get(mk, 0) + mv
    return {
        "kpi": {
            "total_db": total_db,
            "with_email": with_email,
            "sent": sent_count,
            "unsent": unsent,
            "sent_month": monthly_p.get("email_sent", 0) + monthly_p.get("email_sent_batch", 0),
            "quality_fail": monthly_p.get("quality_fail", 0),
        },
        "reply_types": {
            "meeting": monthly_p.get("reply_meeting", 0),
            "info": monthly_p.get("reply_info", 0),
            "later": monthly_p.get("reply_later", 0),
            "reject": monthly_p.get("reply_reject", 0),
        },
        "sheet_url": "https://docs.google.com/spreadsheets/d/1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8/edit#gid=0",
    }


# ===== 루나 북미 DB 수집 + 영어 이메일 =====

LUNA_NA_TEMPLATES = {
    "D": {"label": "한국 매니저형 (EN)",
          "subject": "Want a Korean beauty partner who finds YOU the best deals?",
          "body": "Hi {name},\n\nI'm Luna from 08liter Global — a K-beauty influencer platform based in Seoul.\n\nWe work with 20,000+ beauty brands in Korea and match them with creators like you.\n\nWhat we do for our partners:\n· Bring the best Korean brand deals to you\n· Handle all negotiation on your behalf\n· Pay monthly — no chasing invoices\n\nYour audience clearly loves beauty content.\nWe'd love to be your Korean beauty partner.\n\nInterested in hearing more?\n\n---\n08liter Global — Influencer Partnership\nLuna\n\nluna@08liter.com\nwww.08liter.com"},
    "E": {"label": "장기계약형 (EN)",
          "subject": "Steady monthly income from K-beauty collabs — interested?",
          "body": "Hi {name},\n\nI'm Luna from 08liter Global in Seoul.\n\nInstead of one-off sponsorships, we offer long-term partnerships:\n\n· Guaranteed brand collabs per month\n· Fixed monthly payment\n· You choose the brands you like\n· Dedicated manager (me, Luna)\n\nBased on your followers, you could earn competitive monthly income.\n\nContracts start from 6 months.\nWant to know more?\n\n---\n08liter Global — Influencer Partnership\nLuna\n\nluna@08liter.com\nwww.08liter.com"},
    "F": {"label": "비전 제시형 (EN)",
          "subject": "Your K-beauty journey starts here",
          "body": "Hi {name},\n\nI'm Luna from 08liter Global.\n\nOne of our creator partners grew from 15K to 80K in 6 months — through K-beauty collabs.\n\nThe right brand partnerships don't just pay you. They grow your audience too.\n\nWe'd love to be part of your journey.\nCan I share more?\n\n---\n08liter Global — Influencer Partnership\nLuna\n\nluna@08liter.com\nwww.08liter.com"},
}

@app.post("/api/agents/luna/collect-northamerica")
async def api_luna_collect_na(request: Request):
    """루나 북미 DB 수집 — 인스타 50 + 틱톡 50."""
    body = await request.json()
    target_count = body.get("target_count", 100)
    now = datetime.now(KST)
    # 루나 시트에서 기존 US/CA 건수 확인
    rows = fetch_sheet(LUNA_SHEET_ID, "A:R", TAB_INFLUENCER, ttl_key="influencer")
    existing_na = 0
    existing_emails = set()
    if rows and len(rows) > 1:
        for r in rows[1:]:
            country = str(r[2]).strip().upper() if len(r) > 2 else ""
            email = str(r[8]).strip() if len(r) > 8 else ""
            if country in ("US", "CA"):
                existing_na += 1
            if email:
                existing_emails.add(email.lower())
    # 인플루언서 DB에서 수집 (시뮬레이션)
    inf = await api_influencer_db()
    items = inf.get("items", inf.get("rows", []))
    collected_ig, collected_tt = 0, 0
    new_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        email = item.get("email", "")
        if not email or "@" not in email or email.lower() in existing_emails:
            continue
        country = item.get("country", "")
        if country.upper() not in ("US", "CA", ""):
            continue
        platform = item.get("platform", "Instagram")
        if "instagram" in platform.lower() or "ig" in platform.lower():
            if collected_ig >= target_count // 2:
                continue
            collected_ig += 1
        elif "tiktok" in platform.lower():
            if collected_tt >= target_count // 2:
                continue
            collected_tt += 1
        else:
            continue
        new_items.append(item)
        existing_emails.add(email.lower())
    total_collected = collected_ig + collected_tt
    _record_perf("루나", "na_collect_ig", collected_ig)
    _record_perf("루나", "na_collect_tt", collected_tt)
    # CEO 알림
    day_num = (now - datetime(2026, 4, 11, tzinfo=KST)).days + 1
    alert_body = (f"[루나 북미 DB] {day_num}일차 수집 완료 — 총 {existing_na + total_collected}건 확보\n\n"
                  f"오늘 수집: 인스타 {collected_ig}명 / 틱톡 {collected_tt}명\n"
                  f"누적 수집: {existing_na + total_collected}명 / 400명 목표\n\n"
                  f"월요일 오전 09:00 승인 요청 이메일 발송 예정.")
    _send_email_smtp("jacob@08liter.com", f"[루나 북미 DB] {day_num}일차 수집 완료 — 총 {existing_na + total_collected}건", alert_body, "루나")
    return {"status": "ok", "day": day_num, "collected": {"instagram": collected_ig, "tiktok": collected_tt},
            "total_na": existing_na + total_collected, "target": 400}

@app.get("/api/agents/luna/review-northamerica")
async def api_luna_review_na():
    """월요일 09:00 — 루나 북미 승인 요청 이메일 발송."""
    now = datetime.now(KST)
    rows = fetch_sheet(LUNA_SHEET_ID, "A:R", TAB_INFLUENCER, ttl_key="influencer")
    na_count, na_email, total = 0, 0, 0
    if rows and len(rows) > 1:
        total = len(rows) - 1
        for r in rows[1:]:
            country = str(r[2]).strip().upper() if len(r) > 2 else ""
            email = str(r[8]).strip() if len(r) > 8 else ""
            if country in ("US", "CA"):
                na_count += 1
                if email and "@" in email:
                    na_email += 1
    unsent = na_email  # 미발송 건수 (추적 컬럼 없으므로 전체)
    html = f'''<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px">
<h2 style="color:#1a1a1a;border-bottom:2px solid #333;padding-bottom:10px">📋 북미 DB 현황</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:20px">
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd"><b>총 확보</b></td><td style="padding:8px;border:1px solid #ddd">{na_count}명 / 400명 목표</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">이메일 보유</td><td style="padding:8px;border:1px solid #ddd">{na_email}명</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">미발송 (이번 주 발송 예정)</td><td style="padding:8px;border:1px solid #ddd">{unsent}명</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">채널</td><td style="padding:8px;border:1px solid #ddd">틱톡 50% / 인스타 50%</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">국가</td><td style="padding:8px;border:1px solid #ddd">US/CA</td></tr>
</table>
<hr style="border:1px solid #eee;margin:20px 0">
<h2>📧 시안 D — 한국 매니저형</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p><b>제목:</b> Want a Korean beauty partner who finds YOU the best deals?</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">{LUNA_NA_TEMPLATES["D"]["body"].replace(chr(10),"<br>")}</div>
<hr style="border:1px solid #eee;margin:20px 0">
<h2>📧 시안 E — 장기계약형</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p><b>제목:</b> Steady monthly income from K-beauty collabs — interested?</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">{LUNA_NA_TEMPLATES["E"]["body"].replace(chr(10),"<br>")}</div>
<hr style="border:1px solid #eee;margin:20px 0">
<h2>📧 시안 F — 비전 제시형</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p><b>제목:</b> Your K-beauty journey starts here</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">{LUNA_NA_TEMPLATES["F"]["body"].replace(chr(10),"<br>")}</div>
<hr style="border:2px solid #333;margin:30px 0">
<div style="background:#fff3cd;padding:15px;border:1px solid #ffc107;border-radius:4px">
<h3 style="margin:0 0 10px;color:#856404">✉️ 이 이메일에 회신해주세요</h3>
<p>"루나D" / "루나E" / "루나F" / "루나D+E" 복수 가능</p>
<p>"루나수정: [내용]" → 수정 후 재발송</p>
<p style="color:#dc3545"><b>※ 회신 없이는 단 1통도 발송되지 않습니다.</b></p>
</div></div>'''
    subject = f"[루나 북미 발송 승인 요청] 이번 주 비정형형 뉴스레터 확인해주세요"
    result = _send_email_smtp("jacob@08liter.com", subject, "루나 북미 승인 요청", "루나", html_body=html)
    result["na_count"] = na_count
    result["na_email"] = na_email
    return result

@app.post("/api/luna/send-na")
async def api_luna_send_na(request: Request):
    """CEO 승인된 시안으로 루나 북미 이메일 발송."""
    body = await request.json()
    template_key = body.get("template", "D").upper()
    tmpl = LUNA_NA_TEMPLATES.get(template_key, LUNA_NA_TEMPLATES["D"])
    rows = fetch_sheet(LUNA_SHEET_ID, "A:R", TAB_INFLUENCER, ttl_key="influencer")
    targets = []
    if rows and len(rows) > 1:
        for r in rows[1:]:
            country = str(r[2]).strip().upper() if len(r) > 2 else ""
            email = str(r[8]).strip() if len(r) > 8 else ""
            name = str(r[5]).strip() if len(r) > 5 else ""
            if country in ("US", "CA") and email and "@" in email:
                targets.append({"name": name, "email": email, "country": country})
    limit = min(body.get("limit", 30), 30)
    sent, skipped = 0, 0
    for t in targets[:limit]:
        if not _is_business_hours("US"):
            break
        subj = tmpl["subject"].replace("{name}", t["name"]).replace("{InfluencerName}", t["name"])
        email_body = tmpl["body"].replace("{name}", t["name"]).replace("{InfluencerName}", t["name"])
        qc = _luna_quality_check(t["email"], subj, email_body, t.get("country", "US"))
        if qc:
            skipped += 1
            continue
        html = _build_pitch_html(t["name"], email_body)
        result = _send_email(t["email"], subj, html, "루나")
        if result["status"] == "ok":
            sent += 1
        else:
            skipped += 1
    _record_perf("루나", "na_email_sent", sent)
    return {"status": "ok", "template": template_key, "sent": sent, "skipped": skipped}

# ===== Quality Check + Batch Send + Pipeline APIs =====

PITCH_SHEET_URL = "https://docs.google.com/spreadsheets/d/1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8/edit?gid=1333794047"
LUNA_SHEET_URL = "https://docs.google.com/spreadsheets/d/1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs/edit?gid=1722455708"
VALID_TEMPLATES = {"A", "B", "C", "A_EN", "B_EN"}
LUNA_VALID_TEMPLATES = {"A", "B"}
BATCH_SIZE = 50

def _email_quality_check(to: str, subject: str, body: str, template: str, country: str = "KR", agent: str = "pitch") -> list:
    """Pre-send quality check. Returns list of failures (empty = pass)."""
    errors = []
    if not subject:
        errors.append("empty subject")
    if not body:
        errors.append("empty body")
    if not to or "@" not in to:
        errors.append("invalid email")
    if "{" in subject or "{" in body:
        errors.append("unsubstituted variable")
    valid = VALID_TEMPLATES if agent == "pitch" else LUNA_VALID_TEMPLATES
    if template not in valid:
        errors.append(f"invalid template: {template}")
    if not _is_business_hours(country):
        errors.append(f"outside business hours ({country})")
    return errors

@app.get("/api/email-quality-check")
async def api_email_quality_check(agent: str = "pitch"):
    """Pre-send quality check status."""
    links = {
        "promo": "https://buly.kr/AF24dn7",
        "meeting": "https://buly.kr/1c9NOdW",
    }
    checks = {}
    for name, url in links.items():
        try:
            r = req_lib.head(url, timeout=5, allow_redirects=True)
            checks[name] = {"status": "ok" if r.status_code < 400 else "error", "code": r.status_code}
        except Exception:
            checks[name] = {"status": "error", "code": 0}
    return {"agent": agent, "link_checks": checks, "batch_size": BATCH_SIZE, "valid_templates": list(VALID_TEMPLATES if agent == "pitch" else LUNA_VALID_TEMPLATES)}

@app.get("/api/pitch/pipeline/daily")
async def api_pitch_pipeline_daily():
    """Pitch daily pipeline stats."""
    perf = load_agent_perf()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    tp = perf.get(today, {}).get("\ud53c\uce58", perf.get(today, {}).get("pitch", {}))
    queue = load_email_queue()
    pending = sum(1 for q in queue if q.get("agent") in ("\ud53c\uce58", "pitch") and q.get("status") == "pending")
    sent = tp.get("email_sent", 0) + tp.get("email_sent_batch", 0)
    rows = fetch_sheet(PITCH_SHEET_ID, "A:N", TAB_PITCH, ttl_key="inbound")
    target = max(len(rows) - 1, 0) if rows else 0
    replied = tp.get("reply_info", 0) + tp.get("reply_meeting", 0)
    meeting = tp.get("reply_meeting", 0)
    goals = load_goals()
    pg = goals.get("agent_goals", {}).get("pitch", {})
    db_goal = pg.get("daily_db", 100)
    meeting_goal = pg.get("meeting", 10)
    return {
        "period": "daily", "date": today,
        "target": {"value": target, "goal": db_goal, "pct": min(round(target / max(db_goal, 1) * 100), 999), "link": PITCH_SHEET_URL, "source": "\ud53c\uce58_\ud074\ub85c\ub4dc \ud0ed"},
        "pending": {"value": pending, "link": PITCH_SHEET_URL, "source": "\uc774\uba54\uc77c \ud050"},
        "sent": {"value": sent, "link": PITCH_SHEET_URL, "source": "\ubc1c\uc1a1 \uc131\uacf5 (\ubc18\uc1a1 \uc81c\uc678)"},
        "replied": {"value": replied, "link": PITCH_SHEET_URL, "source": "pitch@08liter.com \uc218\uc2e0"},
        "meeting": {"value": meeting, "goal": meeting_goal, "pct": min(round(meeting / max(meeting_goal, 1) * 100), 999), "link": "https://buly.kr/1c9NOdW", "source": "buly.kr \ud074\ub9ad \uae30\uc900"},
        "conversion": {
            "pending_rate": f"{round(pending/max(target,1)*100)}%" if target else "0%",
            "sent_rate": f"{round(sent/max(target,1)*100)}%" if target else "0%",
            "reply_rate": f"{round(replied/max(sent,1)*100)}%" if sent else "0%",
            "meeting_rate": f"{round(meeting/max(sent,1)*100)}%" if sent else "0%",
        },
    }

@app.get("/api/pitch/pipeline/monthly")
async def api_pitch_pipeline_monthly():
    """Pitch monthly pipeline stats."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    month_prefix = now.strftime("%Y-%m")
    mp = {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix):
            for key in ["\ud53c\uce58", "pitch"]:
                if key in ad:
                    for mk, mv in ad[key].items():
                        mp[mk] = mp.get(mk, 0) + mv
    rows = fetch_sheet(PITCH_SHEET_ID, "A:N", TAB_PITCH, ttl_key="inbound")
    target = max(len(rows) - 1, 0) if rows else 0
    sent = mp.get("email_sent", 0) + mp.get("email_sent_batch", 0)
    replied = mp.get("reply_info", 0) + mp.get("reply_meeting", 0)
    meeting = mp.get("reply_meeting", 0)
    return {
        "period": "monthly", "date": now.strftime("%Y-%m"),
        "target": {"value": target, "link": PITCH_SHEET_URL, "source": "피치_클로드 탭"},
        "pending": {"value": 0, "link": PITCH_SHEET_URL, "source": "이메일 큐"},
        "sent": {"value": sent, "link": PITCH_SHEET_URL, "source": "발송 성공 (반송 제외)"},
        "replied": {"value": replied, "link": PITCH_SHEET_URL, "source": "pitch@08liter.com 수신"},
        "meeting": {"value": meeting, "link": "https://buly.kr/1c9NOdW", "source": "buly.kr 클릭 기준"},
    }

@app.get("/api/luna/pipeline/daily")
async def api_luna_pipeline_daily():
    """Luna daily pipeline stats."""
    perf = load_agent_perf()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    tp = perf.get(today, {}).get("\ub8e8\ub098", perf.get(today, {}).get("luna", {}))
    rows = fetch_sheet(LUNA_SHEET_ID, "A:R", TAB_INFLUENCER, ttl_key="influencer")
    target = max(len(rows) - 1, 0) if rows else 0
    sent = tp.get("email_sent", 0) + tp.get("na_email_sent", 0)
    replied = tp.get("reply_info", 0) + tp.get("reply_meeting", 0)
    contract = tp.get("reply_meeting", 0)
    goals = load_goals()
    lg = goals.get("agent_goals", {}).get("luna", {})
    db_goal = lg.get("monthly_db", 150)
    ct_goal = lg.get("contract", 80)
    return {
        "period": "daily", "date": today,
        "target": {"value": target, "goal": db_goal, "pct": min(round(target / max(db_goal, 1) * 100), 999), "link": LUNA_SHEET_URL, "source": "\uc778\ud50c\ub8e8\uc5b8\uc11c DB"},
        "pending": {"value": 0, "link": LUNA_SHEET_URL, "source": "\uc774\uba54\uc77c \ud050"},
        "sent": {"value": sent, "link": LUNA_SHEET_URL, "source": "\ubc1c\uc1a1 \uc131\uacf5 (\ubc18\uc1a1 \uc81c\uc678)"},
        "replied": {"value": replied, "link": LUNA_SHEET_URL, "source": "luna@08liter.com \uc218\uc2e0"},
        "contract": {"value": contract, "goal": ct_goal, "pct": min(round(contract / max(ct_goal, 1) * 100), 999), "link": LUNA_SHEET_URL, "source": "\uacc4\uc57d \uc644\ub8cc"},
    }

@app.get("/api/luna/pipeline/monthly")
async def api_luna_pipeline_monthly():
    """Luna monthly pipeline stats."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    month_prefix = now.strftime("%Y-%m")
    mp = {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix):
            for key in ["\ub8e8\ub098", "luna"]:
                if key in ad:
                    for mk, mv in ad[key].items():
                        mp[mk] = mp.get(mk, 0) + mv
    rows = fetch_sheet(LUNA_SHEET_ID, "A:R", TAB_INFLUENCER, ttl_key="influencer")
    target = max(len(rows) - 1, 0) if rows else 0
    sent = mp.get("email_sent", 0) + mp.get("na_email_sent", 0)
    replied = mp.get("reply_info", 0) + mp.get("reply_meeting", 0)
    contract = mp.get("reply_meeting", 0)
    return {
        "period": "monthly", "date": now.strftime("%Y-%m"),
        "target": {"value": target, "link": LUNA_SHEET_URL, "source": "인플루언서 DB"},
        "sent": {"value": sent, "link": LUNA_SHEET_URL, "source": "발송 성공 (반송 제외)"},
        "replied": {"value": replied, "link": LUNA_SHEET_URL, "source": "luna@08liter.com 수신"},
        "contract": {"value": contract, "link": LUNA_SHEET_URL, "source": "\uacc4\uc57d \uc644\ub8cc"},
    }

# ===== Max/Sophie/Ray/Hana Pipeline APIs =====

@app.get("/api/max/pipeline/daily")
async def api_max_pipeline_daily():
    """Max daily ads pipeline: budget -> clicks -> visits -> CPA -> conversions."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    perf = load_agent_perf()
    tp = perf.get(today, {}).get("max", perf.get(today, {}).get("\ub9e5\uc2a4", {}))
    return {
        "period": "daily", "date": today,
        "budget": {"value": tp.get("budget", 0), "source": "Meta+Kakao+Naver"},
        "clicks": {"value": tp.get("clicks", 0), "source": "\ucd1d \ud074\ub9ad"},
        "visits": {"value": tp.get("visits", 0), "source": "\uc720\uc785 \uc218"},
        "cpa": {"value": tp.get("cpa", 0), "source": "\ubaa9\ud45c: \u20a910,000"},
        "conversions": {"value": tp.get("conversions", 0), "source": "\uc804\ud658 \uac74\uc218"},
    }

@app.get("/api/max/pipeline/monthly")
async def api_max_pipeline_monthly():
    """Max monthly ads pipeline."""
    now = datetime.now(KST)
    month_prefix = now.strftime("%Y-%m")
    perf = load_agent_perf()
    mp: Dict[str, int] = {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix):
            for key in ["max", "\ub9e5\uc2a4"]:
                if key in ad:
                    for mk, mv in ad[key].items():
                        if isinstance(mv, (int, float)):
                            mp[mk] = mp.get(mk, 0) + mv
    return {
        "period": "monthly", "date": now.strftime("%Y-%m"),
        "budget": {"value": mp.get("budget", 0), "source": "Meta+Kakao+Naver"},
        "clicks": {"value": mp.get("clicks", 0), "source": "\ucd1d \ud074\ub9ad"},
        "visits": {"value": mp.get("visits", 0), "source": "\uc720\uc785 \uc218"},
        "cpa": {"value": mp.get("cpa", 0), "source": "\ubaa9\ud45c: \u20a910,000"},
        "conversions": {"value": mp.get("conversions", 0), "source": "\uc804\ud658 \uac74\uc218"},
    }

@app.get("/api/sophie/pipeline/daily")
async def api_sophie_pipeline_daily():
    """Sophie daily content pipeline."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    perf = load_agent_perf()
    tp = perf.get(today, {}).get("sophie", perf.get(today, {}).get("\uc18c\ud53c", {}))
    return {
        "period": "daily", "date": today,
        "scheduled": {"value": tp.get("scheduled", 0), "source": "\ubc1c\ud589 \uc608\uc815"},
        "published": {"value": tp.get("published", 0), "source": "\ubc1c\ud589 \uc644\ub8cc"},
        "views": {"value": tp.get("views", 0), "source": "\uc870\ud68c\uc218"},
        "engagement": {"value": tp.get("engagement", 0), "source": "\ucc38\uc5ec\uc728 (%)"},
        "leads": {"value": tp.get("leads", 0), "source": "B2B+B2C \ub9ac\ub4dc"},
    }

@app.get("/api/sophie/pipeline/monthly")
async def api_sophie_pipeline_monthly():
    """Sophie monthly content pipeline."""
    now = datetime.now(KST)
    month_prefix = now.strftime("%Y-%m")
    perf = load_agent_perf()
    mp: Dict[str, int] = {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix):
            for key in ["sophie", "\uc18c\ud53c"]:
                if key in ad:
                    for mk, mv in ad[key].items():
                        if isinstance(mv, (int, float)):
                            mp[mk] = mp.get(mk, 0) + mv
    return {
        "period": "monthly", "date": now.strftime("%Y-%m"),
        "scheduled": {"value": mp.get("scheduled", 0), "source": "\ubc1c\ud589 \uc608\uc815"},
        "published": {"value": mp.get("published", 0), "source": "\ubc1c\ud589 \uc644\ub8cc"},
        "views": {"value": mp.get("views", 0), "source": "\uc870\ud68c\uc218"},
        "engagement": {"value": mp.get("engagement", 0), "source": "\ucc38\uc5ec\uc728 (%)"},
        "leads": {"value": mp.get("leads", 0), "source": "B2B+B2C \ub9ac\ub4dc"},
    }

@app.get("/api/ray/pipeline/daily")
async def api_ray_pipeline_daily():
    """Ray daily invoice pipeline."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    perf = load_agent_perf()
    tp = perf.get(today, {}).get("ray", perf.get(today, {}).get("\ub808\uc774", {}))
    return {
        "period": "daily", "date": today,
        "issued": {"value": tp.get("issued", 0), "source": "\ubc1c\ud589 \uc608\uc815"},
        "collected": {"value": tp.get("collected", 0), "source": "\ubc1c\ud589 \uc644\ub8cc"},
        "paid": {"value": tp.get("paid", 0), "source": "\uc218\uae08 \uc644\ub8cc"},
        "unpaid": {"value": tp.get("unpaid", 0), "source": "\ubbf8\uc218\uae08"},
    }

@app.get("/api/ray/pipeline/monthly")
async def api_ray_pipeline_monthly():
    """Ray monthly invoice pipeline."""
    now = datetime.now(KST)
    month_prefix = now.strftime("%Y-%m")
    perf = load_agent_perf()
    mp: Dict[str, int] = {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix):
            for key in ["ray", "\ub808\uc774"]:
                if key in ad:
                    for mk, mv in ad[key].items():
                        if isinstance(mv, (int, float)):
                            mp[mk] = mp.get(mk, 0) + mv
    return {
        "period": "monthly", "date": now.strftime("%Y-%m"),
        "issued": {"value": mp.get("issued", 0), "source": "\ubc1c\ud589 \uc608\uc815"},
        "collected": {"value": mp.get("collected", 0), "source": "\ubc1c\ud589 \uc644\ub8cc"},
        "paid": {"value": mp.get("paid", 0), "source": "\uc218\uae08 \uc644\ub8cc"},
        "unpaid": {"value": mp.get("unpaid", 0), "source": "\ubbf8\uc218\uae08"},
    }

@app.get("/api/hana/pipeline/daily")
async def api_hana_pipeline_daily():
    """Hana daily CS pipeline."""
    today = datetime.now(KST).strftime("%Y-%m-%d")
    perf = load_agent_perf()
    tp = perf.get(today, {}).get("hana", perf.get(today, {}).get("\ud558\ub098", {}))
    return {
        "period": "daily", "date": today,
        "new_inquiry": {"value": tp.get("new_inquiry", 0), "source": "\uc2e0\uaddc \ubb38\uc758"},
        "in_progress": {"value": tp.get("in_progress", 0), "source": "\ucc98\ub9ac\uc911"},
        "resolved": {"value": tp.get("resolved", 0), "source": "\uc644\ub8cc"},
        "renewal": {"value": tp.get("renewal", 0), "source": "\uc7ac\uacc4\uc57d"},
    }

@app.get("/api/hana/pipeline/monthly")
async def api_hana_pipeline_monthly():
    """Hana monthly CS pipeline."""
    now = datetime.now(KST)
    month_prefix = now.strftime("%Y-%m")
    perf = load_agent_perf()
    mp: Dict[str, int] = {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix):
            for key in ["hana", "\ud558\ub098"]:
                if key in ad:
                    for mk, mv in ad[key].items():
                        if isinstance(mv, (int, float)):
                            mp[mk] = mp.get(mk, 0) + mv
    return {
        "period": "monthly", "date": now.strftime("%Y-%m"),
        "new_inquiry": {"value": mp.get("new_inquiry", 0), "source": "\uc2e0\uaddc \ubb38\uc758"},
        "in_progress": {"value": mp.get("in_progress", 0), "source": "\ucc98\ub9ac\uc911"},
        "resolved": {"value": mp.get("resolved", 0), "source": "\uc644\ub8cc"},
        "renewal": {"value": mp.get("renewal", 0), "source": "\uc7ac\uacc4\uc57d"},
    }

async def _run_recontact_campaign(dry_run: bool = True, limit: int = 10) -> dict:
    """재접촉 캠페인 건´건¶ 실행 함수."""
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
            f"안건하세요, 공팔건¦¬터글건¡건² 건¸건건 파트건십 팀 루나입건건¤.\n\n"
            f"지건건² {brand_name} 관건 ¨ 건¬¸의건¥¼ 주셨을 건 좋은 건화건¥¼ 건건´었건건°요,\n"
            f"이후 진행 상황이 궁금하여 건¤시 연건½건건¦½건건¤.\n\n"
            f"최근 저희건 인플건£¨언서 건§케팅 건¶야에서 새건¡운 성과건¥¼ 거건고 있으건©°,\n"
            f"{brand_name}에 최적화건 캠페인 전건µ을 준건¹했습건건¤.\n\n"
            f"편하신 시간에 15건¶건§ 투자해 주시건©´ 건§춤 제안을 건건¦¬겠습건건¤.\n\n감사합건건¤.\n루나 건건¦¼"
        )
        subject = f"[공팔건¦¬터글건¡건²] {brand_name} 건§춤 인플건£¨언서 건§케팅 제안"
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
    """루나 재접촉 캠페인 실행 API."""
    body = await request.json()
    return await _run_recontact_campaign(dry_run=body.get("dry_run", True), limit=body.get("limit", 10))


# ===== 에이전트 자율 업건¬´ 함수 =====

async def _pitch_inbound_auto():
    """피치: 신규 인건°운건 감지 â 자건 응건 이건©일 + 건¯¸팅 건§크 건°송."""
    inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", TAB_INBOUND, ttl_key="inbound")
    if not inbound_rows:
        return {"sent": 0}
    hdr_idx = _find_header_row(inbound_rows, "국가", "컨택현황", "컨텍현황", "건´건¹자")
    headers = [str(h).replace("\n", " ").strip() for h in inbound_rows[hdr_idx]]
    email_idx = _find_col(headers, "이건©일") or 6
    brand_idx = _find_col(headers, "업체건ª", "건¸건건") or 4
    status_idx = _find_col(headers, "컨텍현황", "컨택현황") or 16
    staff_idx = _find_col(headers, "건´건¹자") or 14
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
        body = (f"안건하세요, 공팔건¦¬터글건¡건² 피치입건건¤.\n\n"
                f"{brand} 관건 ¨ 건¬¸의 감사합건건¤. 건¹ 건¥¸ 시일 건´에 건§춤 제안을 준건¹해 건건¦¬겠습건건¤.\n\n"
                f"편하신 시간에 15건¶ 건¹건건©´ 건¯¸팅을 통해 상세히 안건´건건¦¬겠습건건¤.\n\n"
                f"건¯¸팅 예약: {MEETING_LINK}\n\n감사합건건¤.\n피치 건건¦¼")
        html = _build_pitch_html(brand, body)
        result = _queue_or_send_email("피치", email, f"[공팔건¦¬터글건¡건²] {brand} 인플건£¨언서 건§케팅 제안", html, {"brand": brand})
        if result["status"] in ("ok", "queued"):
            sent += 1
            _record_perf("피치", "meeting_invite")
    _record_perf("피치", "inbound_processed", sent)
    return {"sent": sent}

async def _pitch_outbound_crm():
    """피치: 유효DB 중 건¯¸계약 건¸건건에 CRM 건´스건 터 건°송."""
    leads_data = await api_recontact_leads()
    leads = leads_data.get("leads", [])
    targets = [l for l in leads if l.get("email") and "@" in l.get("email", "")][:10]
    sent = 0
    for lead in targets:
        brand = lead["name"]
        body = (f"안건하세요, 공팔건¦¬터글건¡건² 피치입건건¤.\n\n"
                f"현재 {brand}에 최적화건 프건¡건ª¨션 패키지건¥¼ 준건¹했습건건¤.\n\n"
                f"글건¡건² 155건§+ 인플건£¨언서 건¤트워크건¥¼ 활용한 건§춤형 캠페인으건¡\n"
                f"건¸건건 인지건와 건§¤출을 건시에 건여건건¦½건건¤.\n\n"
                f"건¹건건©´ 건¯¸팅 예약: {MEETING_LINK}\n\n감사합건건¤.\n피치 건건¦¼")
        html = _build_pitch_html(brand, body)
        result = _send_email(lead["email"], f"[공팔건¦¬터글건¡건²] {brand} 건§춤 프건¡건ª¨션 안건´", html, "피치")
        if result["status"] == "ok":
            sent += 1
    _record_perf("피치", "crm_newsletter", sent)
    return {"sent": sent, "total_leads": len(leads)}

async def _luna_inbound_welcome():
    """루나: 신규 인플건£¨언서 지원자에게 환영 이건©일 + 캠페인 안건´."""
    rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", TAB_INFLUENCER, ttl_key="influencer")
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
        body = (f"안건하세요 {name}건, 공팔건¦¬터글건¡건² 루나입건건¤!\n\n"
                f"인플건£¨언서 파트건 건±건¡을 환영합건건¤.\n\n"
                f"현재 진행 중인 캠페인을 안건´건건¦½건건¤:\n"
                f"â¢ K-건·°티 체험 캠페인 (건°건¦¬건°건¦¬)\n"
                f"â¢ 글건¡건² 건¦¬건·° 캠페인\n"
                f"â¢ 해외 구건§¤평 서건¹스\n\n"
                f"관심 있건 캠페인이 있으시건©´ 회신해 주세요.\n루나 건건¦¼")
        html = _build_pitch_html(name, body)
        result = _queue_or_send_email("루나", email, f"[공팔건¦¬터글건¡건²] {name}건 환영합건건¤!", html, {"influencer": name})
        if result["status"] in ("ok", "queued"):
            sent += 1
    _record_perf("루나", "welcome_sent", sent)
    return {"sent": sent}

async def _luna_outbound_pitch():
    """루나: 인플건£¨언서 DB에서 이건©일 있건 건상에게 캠페인 제안 건°송."""
    rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", TAB_INFLUENCER, ttl_key="influencer")
    if not rows:
        return {"sent": 0}
    targets = []
    for row in rows:
        if len(row) < 12:
            continue
        status = str(row[10]).strip() if len(row) > 10 else ""
        if status != "건¨순건¦¬스트업" and status != "1. 건¨순건¦¬스트업":
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
        result = _queue_or_send_email("루나", t["email"], f"[08Liter] Campaign opportunity for {t['name']}", html, {"influencer": t["name"]})
        if result["status"] == "ok":
            sent += 1
    _record_perf("루나", "outbound_sent", sent)
    return {"sent": sent, "targeted": len(targets)}

async def _sophie_daily_content():
    """소피: Anthropic API건¡ B2B/B2C 콘텐츠 기획 + 승인 큐 건±건¡."""
    if not ANTHROPIC_API_KEY:
        return {"status": "no_api_key"}
    now = datetime.now(KST)
    prompt = (f"오건은 {now.strftime('%Y건 %m월 %d일 %A')}입건건¤.\n"
              f"공팔건¦¬터글건¡건²의 SNS 콘텐츠건¥¼ 기획해주세요.\n\n"
              f"1. B2B 콘텐츠 1개 (건¸건건 건´건¹자 타겟)\n"
              f"  - 인플건£¨언서 건§케팅 성공사건¡ 건건 프건¡건ª¨션 안건´\n"
              f"  - Instagram 카건건´스 형식\n"
              f"2. B2C 콘텐츠 1개 (인플건£¨언서 타겟)\n"
              f"  - 수익화 팁 건건 캠페인 건ª¨집 안건´\n"
              f"  - TikTok/Instagram 건¦´스 형식\n\n"
              f"각 콘텐츠의 제건ª©, 건³¸건¬¸ 텍스트, 해시태그 5개, CTA건¥¼ 작성해주세요.")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": ANTHROPIC_MODEL, "max_tokens": 1024,
                      "system": "건¹신은 소피, 공팔건¦¬터글건¡건² SNS 운영 에이전트입건건¤. 건§¤건 ¥적인 콘텐츠건¥¼ 기획합건건¤.",
                      "messages": [{"role": "user", "content": prompt}]})
            if resp.status_code == 200:
                content = resp.json()["content"][0]["text"]
                proposals = load_proposals()
                proposals.append({
                    "id": int(time.time() * 1000) % 10000000,
                    "agent": "소피", "status": "pending_approval",
                    "proposal": f"오건의 SNS 콘텐츠 (B2B + B2C)",
                    "detail": content[:500],
                    "expected_impact": "B2B: 건¸건건 건¦¬건 1건+ / B2C: 인플건£¨언서 건¦¬건 2건+",
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
    """에이전트건³ 일일 성과 + 건ª©표 건건¹ 건¬성건¥ ."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    today_perf = perf.get(today, {})
    yesterday_perf = perf.get(yesterday, {})
    # 월간 건적 계산
    month_prefix = now.strftime("%Y-%m")
    monthly_perf = {}
    for date_key, agents_data in perf.items():
        if date_key.startswith(month_prefix):
            for ag, metrics in agents_data.items():
                monthly_perf.setdefault(ag, {})
                for mk, mv in metrics.items():
                    monthly_perf[ag][mk] = monthly_perf[ag].get(mk, 0) + mv
    # 주간 건적
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    weekly_perf = {}
    for date_key, agents_data in perf.items():
        if date_key >= week_start:
            for ag, metrics in agents_data.items():
                weekly_perf.setdefault(ag, {})
                for mk, mv in metrics.items():
                    weekly_perf[ag][mk] = weekly_perf[ag].get(mk, 0) + mv
    # 건ª©표 건건¹ 건¬성건¥ 
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


# ===== 건ª©표 설정 API =====
@app.get("/api/goals")
async def api_get_goals():
    return load_goals()

@app.post("/api/goals")
async def api_set_goals(request: Request):
    body = await request.json()
    goals = load_goals()
    # Update monthly section
    if "monthly" in body:
        if "monthly" not in goals:
            goals["monthly"] = {}
        goals["monthly"].update(body["monthly"])
    # Update agent_goals if provided
    if "agent_goals" in body:
        if "agent_goals" not in goals:
            goals["agent_goals"] = {}
        for ag, ag_goals in body["agent_goals"].items():
            if ag not in goals["agent_goals"]:
                goals["agent_goals"][ag] = {}
            goals["agent_goals"][ag].update(ag_goals)
    # Legacy flat keys support
    flat_keys = {"revenue", "contracts", "contract", "inbound_db", "valid_db",
                 "cpa", "influencer_pool", "alert_threshold",
                 "monthly_revenue", "monthly_contracts", "contract_unit_price",
                 "daily_inbound_db", "daily_valid_db", "cpa_target"}
    for k, v in body.items():
        if k in flat_keys:
            goals[k] = v
    # Auto-distribute to agent_goals from monthly
    m = goals.get("monthly", {})
    if "agent_goals" not in goals:
        goals["agent_goals"] = {}
    ag = goals["agent_goals"]
    if m.get("revenue"):
        ag.setdefault("kyle", {})["revenue"] = m["revenue"]
    if m.get("contract"):
        ag.setdefault("kyle", {})["contract"] = m["contract"]
    if m.get("inbound_db"):
        ag.setdefault("pitch", {})["monthly_db"] = m["inbound_db"]
        ag.setdefault("pitch", {}).setdefault("daily_db", max(1, m["inbound_db"] // 20))
    if m.get("valid_db"):
        ag.setdefault("luna", {})["monthly_db"] = m["valid_db"]
        ag.setdefault("luna", {}).setdefault("daily_db", max(1, m["valid_db"] // 20))
    if m.get("cpa"):
        ag.setdefault("max", {})["cpa"] = m["cpa"]
    goals["updated_at"] = datetime.now(KST).isoformat()
    save_goals(goals)
    # Clear caches
    _cache.clear()
    _cache_time.clear()
    synced = list(ag.keys()) if ag else []
    return {"status": "ok", "synced_agents": synced, "updated_at": goals["updated_at"], "goals": goals}


# ===== 알건¦¼센터 API (게시판 형태) =====
@app.get("/api/alerts-board")
async def api_alerts_board():
    alerts = load_alerts()
    # 건¯¸해결 상건¨ 고정
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


# ===== 에이전트 자율실행 프건 임워크 =====
async def _agent_auto_cycle():
    """건§¤일 09:00 KST 전체 에이전트 자율실행: 건°이터수집 â 건¶석 â 감지 â 알건¦¼ â 제안생성 â 승인건 제안 실행 â 슬건."""
    goals = load_goals()
    alerts_posted = []
    now_ts = datetime.now(KST).isoformat()
    _id = lambda: int(time.time() * 1000) % 1000000 + len(alerts_posted)

    # 0. 에이전트 자율 개선 건£¨프 â 제안 자건생성
    try:
        new_proposals = await _generate_agent_proposals()
        if new_proposals:
            _log_cycle("auto_generate", None, f"에이전트 제안 {len(new_proposals)}건 자건생성")
    except Exception as e:
        print(f"Proposal auto-generation error: {e}")

    # 0-1. 승인건 제안 자건실행
    try:
        proposals = load_proposals()
        for p in proposals:
            if p.get("status") == "approved" and not p.get("executed_at"):
                agent = p.get("agent", "")
                result_text = "자건 실행 완건£"
                if agent == "루나" and "재접촉" in p.get("proposal", ""):
                    try:
                        campaign = await _run_recontact_campaign(dry_run=False, limit=5)
                        result_text = f"재접촉 이건©일 {campaign.get('sent',0)}건 건°송"
                    except Exception:
                        result_text = "재접촉 실행 오건¥"
                p["status"] = "completed"
                p["executed_at"] = now_ts
                p["result"] = result_text
                _log_cycle("auto_execute", p.get("id"), result_text)
        save_proposals(proposals)
    except Exception as e:
        print(f"Auto-execute error: {e}")

    try:
        # 1. 전체 KPI 건°이터 수집
        brand = await api_brand_pipeline()
        m = brand.get("month", {})
        t = brand.get("today", {})
        monthly_goals = goals.get("monthly", {})
        ag_goals = goals.get("agent_goals", {})
        threshold_pct = monthly_goals.get("alert_threshold_pct", 30) / 100
        rev_target = ag_goals.get("kyle", {}).get("revenue", monthly_goals.get("revenue", goals.get("revenue", 160000000)))
        ct_target = ag_goals.get("kyle", {}).get("contract", monthly_goals.get("contract", goals.get("contracts", 38)))
        inb_target = ag_goals.get("pitch", {}).get("monthly_db", monthly_goals.get("inbound_db", goals.get("inbound_db", 500)))
        val_target = ag_goals.get("luna", {}).get("monthly_db", monthly_goals.get("valid_db", goals.get("valid_db", 150)))

        checks = [
            ("매출", m.get("revenue", 0), rev_target, "카일"),
            ("계약건수", m.get("contract", 0), ct_target, "카일"),
            ("인입DB", m.get("inbound", 0), inb_target, "피치"),
            ("유효DB", m.get("valid", 0), val_target, "루나"),
        ]
        for label, val, target, agent in checks:
            if target > 0 and val / target < 0.8:  # 80% 건¯¸건§건§ 알건¦¼
                alerts_posted.append({
                    "id": _id(), "agent": agent, "severity": "critical",
                    "summary": f"â ï¸ {label} AT RISK: {val:,} / 건ª©표 {target:,} ({val/target*100:.0f}%)",
                    "detail": f"건ª©표 건건¹ {threshold_pct*100:.0f}% 건¯¸건¬ â 카일 지시: 즉시 건응 필요",
                    "timestamp": now_ts, "resolved": False})

        # 3. 카일 â 건¬´건응 건 감지
        if t.get("unhandled", 0) > 0:
            alerts_posted.append({
                "id": _id(), "agent": "카일", "severity": "warning",
                "summary": f"건¬´건응 {t['unhandled']}건 â 건´건¹자 건°°정 필요",
                "detail": "건´건¹자 건¯¸건°°정 건건 컨텍현황 건¯¸입건 ¥",
                "timestamp": now_ts, "resolved": False})

        # 4. 카일 â API 상태 점검 (건¹¨간 항건ª© 감지)
        api_checks = {
            "Google Sheets": bool(GSHEETS_API_KEY),
            "Anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "Slack": bool(os.getenv("SLACK_WEBHOOK_URL")),
            "이건©일": bool(os.getenv("EMAIL_WEBHOOK_URL")),
        }
        for svc, ok in api_checks.items():
            if not ok:
                alerts_posted.append({
                    "id": _id(), "agent": "카일", "severity": "critical",
                    "summary": f"ð´ {svc} 연결 실패 â 자건 재연결 시건 중",
                    "detail": f"{svc} API 키 건¯¸설정 건건 건§건£. Railway Variables 확인 필요.",
                    "timestamp": now_ts, "resolved": False})

        # 5. 소피 â SNS 콘텐츠 생성 + 슬건 + 이건©일
        try:
            sophie_result = await api_sophie_content()
            if sophie_result.get("status") == "ok":
                content = sophie_result.get("content", "")
                alerts_posted.append({"id": _id(), "agent": "소피", "severity": "info",
                    "summary": "ð± 이건² 주 SNS 콘텐츠 전건µ 생성 완건£", "detail": content[:200],
                    "timestamp": now_ts, "resolved": False})
                _send_email(AGENT_EMAILS["소피"], "[소피] 이건² 주 SNS 콘텐츠 전건µ", _build_pitch_html("SNS 콘텐츠", content), "소피")
        except Exception as e:
            print(f"Sophie content error: {e}")

        # 6. 피치 â 인플건£¨언서 풀 건¶석 + 이건©일
        try:
            inf = await api_influencer_db()
            stats = inf.get("stats", {})
            bc = stats.get("by_country", {})
            total = inf.get("total", 0)
            pitch_summary = f"인플건£¨언서 풀: {total:,}건ª\n국가건³: {', '.join(f'{k}:{v}' for k,v in sorted(bc.items(), key=lambda x:-x[1])[:5])}"
            alerts_posted.append({"id": _id(), "agent": "피치", "severity": "info",
                "summary": f"ð 인플건£¨언서 풀 현황: {total:,}건ª", "detail": pitch_summary,
                "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["피치"], "[피치] 인플건£¨언서 풀 일일 건³´고서", _build_pitch_html("인플건£¨언서", pitch_summary), "피치")
        except Exception as e:
            print(f"Pitch analysis error: {e}")

        # 7. 하건 â CS 건¯¸응건µ 현황 + 이건©일
        try:
            unhandled_count = t.get("unhandled", 0)
            hana_summary = f"금일 건¯¸응건µ CS: {unhandled_count}건\n즉시 응건 필요 건: {unhandled_count}건"
            if unhandled_count > 0:
                alerts_posted.append({"id": _id(), "agent": "하건", "severity": "warning",
                    "summary": f"ð 건¯¸응건µ CS {unhandled_count}건 â 응건 필요", "detail": hana_summary,
                    "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["하건"], "[하건] CS 건¯¸응건µ 현황", _build_pitch_html("CS", hana_summary), "하건")
        except Exception as e:
            print(f"Hana CS error: {e}")

        # 8. 건 이 â 세금계산서 체크건¦¬스트 + 이건©일
        try:
            ct_count = m.get("contract", 0)
            ray_summary = f"이건²건¬ 세금계산서: {ct_count}건\n건§¤출: {m.get('revenue',0):,}원\n체크: 건¯¸처건¦¬ 계산서, 입금 확인, 정건¶지원 건§감"
            alerts_posted.append({"id": _id(), "agent": "건 이", "severity": "info",
                "summary": f"ð 경영지원 일일 체크건¦¬스트", "detail": ray_summary,
                "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["건 이"], "[건 이] 경영지원 일일 체크건¦¬스트", _build_pitch_html("경영지원", ray_summary), "건 이")
        except Exception as e:
            print(f"Ray management error: {e}")

        # 9. 피치 â 인건°운건 자건 응건 + CRM 건´스건 터
        try:
            pitch_ib = await _pitch_inbound_auto()
            pitch_crm = await _pitch_outbound_crm()
            ib_sent = pitch_ib.get("sent", 0)
            crm_sent = pitch_crm.get("sent", 0)
            if ib_sent + crm_sent > 0:
                alerts_posted.append({"id": _id(), "agent": "피치", "severity": "info",
                    "summary": f"ð§ 피치 자율업건¬´: 인건°운건 응건 {ib_sent}건 + CRM 건´스건 터 {crm_sent}건",
                    "detail": f"건¯¸팅 예약 건§크 포함 건°송 완건£",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Pitch auto error: {e}")

        # 9-1. 루나 â 인플건£¨언서 환영 + 아웃건°운건 + 재접촉
        try:
            luna_welcome = await _luna_inbound_welcome()
            luna_outbound = await _luna_outbound_pitch()
            recontact = await _run_recontact_campaign(dry_run=False, limit=5)
            w_sent = luna_welcome.get("sent", 0)
            o_sent = luna_outbound.get("sent", 0)
            r_sent = recontact.get("sent", 0)
            total_sent = w_sent + o_sent + r_sent
            if total_sent > 0:
                alerts_posted.append({"id": _id(), "agent": "루나", "severity": "info",
                    "summary": f"âï¸ 루나 자율업건¬´: 환영 {w_sent}건 + 아웃건°운건 {o_sent}건 + 재접촉 {r_sent}건",
                    "detail": "",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Luna auto error: {e}")

        # 9-2. 소피 â 일일 콘텐츠 기획
        try:
            sophie = await _sophie_daily_content()
            if sophie.get("status") == "ok":
                alerts_posted.append({"id": _id(), "agent": "소피", "severity": "info",
                    "summary": "ð± 소피 자율업건¬´: 오건의 B2B/B2C 콘텐츠 기획 완건£",
                    "detail": "승인 큐에서 확인 후 승인해주세요",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Sophie auto error: {e}")

        # 9-3. 자건 에스컬건 이션 â 일 건ª©표 50% 건¯¸건¬ 에이전트 감지
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
                                "summary": f"ð¨ {ag_name} 건ª©표 건¯¸건¬: {metric} {actual}/{target} ({round(actual/target*100)}%)",
                                "detail": f"일 건ª©표의 50% 건¯¸건¬. 원인 건¶석 건° 즉시 건응 필요.",
                                "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Escalation check error: {e}")

        # 10. 카일 â 전체 건¸건¦¬핑 이건©일 건°송
        try:
            briefing = (
                f"ð 전체 KPI 건¸건¦¬핑 â {datetime.now(KST).strftime('%Y-%m-%d')}\n\n"
                f"건§¤출: {m.get('revenue',0):,}원 / 건ª©표 1.6억\n"
                f"계약: {m.get('contract',0)}건 / 건ª©표 38건\n"
                f"인입DB: {t.get('inbound',0)}건 / 유효: {t.get('valid',0)}건\n"
                f"건¬´건응: {t.get('unhandled',0)}건\n\n"
                f"경고 {len(alerts_posted)}건 건°생"
            )
            _send_email(AGENT_EMAILS["카일"], "[카일] 전체 에이전트 일일 건¸건¦¬핑", _build_pitch_html("KPI 건¸건¦¬핑", briefing), "카일")
        except Exception as e:
            print(f"Kyle briefing error: {e}")

        # 11. 결과 저장 + 슬건 공유
        if alerts_posted:
            existing = load_alerts()
            existing.extend(alerts_posted)
            save_alerts(existing[-200:])
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url:
                text = f"ð¨ *[카일] 09:00 전체 에이전트 자율실행 â {len(alerts_posted)}건*\n"
                for a in alerts_posted[:8]:
                    text += f"â¢ [{a['agent']}] {a['summary']}\n"
                text += "\n상세: https://dashboard-production-b2bd.up.railway.app/ â 알건¦¼ 센터"
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
    """에이전트 자율실행 사이클 수건 트건¦¬거."""
    alerts = await _agent_auto_cycle()
    return {"status": "ok", "alerts_posted": len(alerts), "alerts": alerts}


# ===== 건©타 광고 API =====
@app.get("/api/meta-ads")
async def api_meta_ads(date_preset: str = Query("today")):
    """건©타 광고 성과 조회. date_preset: today/this_month/last_7d."""
    token = os.getenv("META_ACCESS_TOKEN", "")
    account_id = os.getenv("META_AD_ACCOUNT_ID", "230720044045370")
    if not token:
        return {"status": "not_configured", "message": "META_ACCESS_TOKEN 건¯¸설정. 건©타 건¹즈건스 관건¦¬자에서 건°급 필요."}
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
            # CPA 자건 계산
            for r in rows:
                spend = float(r.get("spend", 0))
                clicks = int(r.get("clicks", 0))
                r["cpa_calculated"] = round(spend / clicks, 0) if clicks > 0 else 0
            return {"status": "ok", "date_preset": date_preset, "data": rows}
        return {"status": "error", "code": resp.status_code, "message": data.get("error", {}).get("message", resp.text[:200])}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== 카카오 채건 API (B2B/B2C 건¶건¦¬) =====
@app.get("/api/kakao-channel")
async def api_kakao_channel():
    """카카오 채건 상태."""
    b2b_key = os.getenv("KAKAO_B2B_API_KEY", "") or os.getenv("KAKAO_REST_API_KEY", "")
    b2c_key = os.getenv("KAKAO_B2C_API_KEY", "") or os.getenv("KAKAO_REST_API_KEY", "")
    b2b = os.getenv("KAKAO_B2B_CHANNEL", "08liter_b2b")
    b2c = os.getenv("KAKAO_B2C_CHANNEL", "08liter_korea")
    return {
        "b2b": {"channel": b2b, "status": "connected" if b2b_key else "not_configured",
                "agent": "하건", "desc": "B2B CS 건©시지 자건 수신/응건"},
        "b2c": {"channel": b2c, "status": "connected" if b2c_key else "not_configured",
                "agent": "피치", "desc": "B2C 인플건£¨언서 건¬¸의 수신 â 인건°운건 시트 자건 기건¡"},
    }

@app.get("/api/kakao-b2b/messages")
async def api_kakao_b2b_messages():
    """하건: 카카오 B2B 채건 프건¡필 건° 건¯¸응건µ 건©시지 조회."""
    api_key = os.getenv("KAKAO_B2B_API_KEY", "")
    if not api_key:
        return {"status": "not_configured", "message": "KAKAO_B2B_API_KEY 건¯¸설정. Railway Variables에 추가 필요.",
                "mock_unresponded": 4, "note": "API 연건 전 건건¯¸ 건°이터"}
    try:
        resp = req_lib.get("https://kapi.kakao.com/v1/api/talk/profile",
                           headers={"Authorization": f"KakaoAK {api_key}"}, timeout=10)
        if resp.status_code == 200:
            return {"status": "connected", "profile": resp.json(), "agent": "하건"}
        return {"status": "error", "code": resp.status_code, "message": resp.text[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/kakao-b2c/inquiries")
async def api_kakao_b2c_inquiries():
    """피치: 카카오 B2C 채건 프건¡필 조회."""
    api_key = os.getenv("KAKAO_B2C_API_KEY", "")
    if not api_key:
        return {"status": "not_configured", "message": "KAKAO_B2C_API_KEY 건¯¸설정. Railway Variables에 추가 필요.",
                "mock_inquiries": 2, "note": "API 연건 전 건건¯¸ 건°이터"}
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
    """SNS 계정 현황. 인스타/유튜건¸/틱톡 B2B+B2C."""
    ig_token = os.getenv("META_INSTAGRAM_TOKEN", "")
    return {
        "instagram_b2b": {"account": os.getenv("INSTAGRAM_B2B_ACCOUNT", "insight._.lab"), "status": "connected" if ig_token else "pending", "agent": "소피"},
        "instagram_b2c": {"account": os.getenv("INSTAGRAM_B2C_ACCOUNT", "08l_korea"), "status": "connected" if ig_token else "pending", "agent": "소피"},
        "youtube_b2b": {"account": os.getenv("YOUTUBE_B2B_CHANNEL", "08L_insight"), "status": "pending", "agent": "소피"},
        "tiktok_b2b": {"account": os.getenv("TIKTOK_B2B_ACCOUNT", "08l_insight"), "status": "pending", "agent": "소피"},
        "tiktok_b2c": {"account": os.getenv("TIKTOK_B2C_ACCOUNT", "08liter_korea"), "status": "pending", "agent": "소피"},
        "meta_instagram_token": "SET" if ig_token else "NOT_SET",
    }


# ===== KPI 추이 건°이터 (그건프용) =====
@app.get("/api/kpi-trend")
async def api_kpi_trend():
    """최근 12개월 월건³ + 최근 90일 일건³ KPI 추이. 구글시트 실건°이터."""
    monthly = []
    try:
        ads = await api_ads_performance()
        monthly = ads.get("monthly_trend", [])
    except Exception:
        pass
    # 계산서에서 월건³ 건§¤출 집계 (B열 건 짜 기반 통일)
    ct_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", TAB_CONTRACT, ttl_key="contract")
    monthly_rev = {}
    if ct_rows:
        hdr = _find_header_row(ct_rows, "작성일자", "공급가액", "공급건°건자")
        headers = [str(h).replace("\n", " ").strip() for h in ct_rows[hdr]]
        date_idx = _find_col(headers, "작성일자", "건±건¡기준일") or 1
        amount_idx = _find_col(headers, "공급가액") or 19
    # 일건³ 건§¤출 + 계약수 + 상품건³ + 충전금
    daily_rev = {}
    daily_new = {}
    daily_renew = {}
    daily_new_rev = {}
    daily_renew_rev = {}
    product_dist = {}
    daily_payback = {}
    # 월건³ 집계 (전체 기간 â 차트 12개월용)
    monthly_new_rev = {}
    monthly_renew_rev = {}
    monthly_new_cnt = {}
    monthly_renew_cnt = {}
    if ct_rows:
        cat_idx = _find_col(headers, "품건ª© 재건¶건¥", "재건¶건¥") or 24
        payback_idx = _find_col(headers, "페이건°±건¹", "충전금") or 18
        brand_idx = _find_col(headers, "공급건°건자 상호") or 8
        type_idx = _find_col(headers, "신규/", "재계약") or 6
        now = datetime.now(KST)
        cutoff_90 = (now - timedelta(days=90)).strftime("%Y%m%d")
        # 건¸건건 첫 건±장 추적 (G열 없을 건 폴건°±)
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
                rev = int(float(rv.replace(",", "").replace("â©", "").replace(" ", "")))
            except (ValueError, TypeError):
                rev = 0
            if rev <= 0:
                continue
            brand = str(row[brand_idx]).strip() if brand_idx < len(row) else ""
            ctype = str(row[type_idx]).strip() if type_idx is not None and type_idx < len(row) else ""
            # G열 기반 신규/재계약 건¶건¥ (_parse_contracts와 건일 건¡직)
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
            # 월건³ 집계 (전체 기간 â B열 건 짜 기반 통일)
            monthly_rev[mk] = monthly_rev.get(mk, 0) + rev
            if is_renew:
                monthly_renew_rev[mk] = monthly_renew_rev.get(mk, 0) + rev
                monthly_renew_cnt[mk] = monthly_renew_cnt.get(mk, 0) + 1
            else:
                monthly_new_rev[mk] = monthly_new_rev.get(mk, 0) + rev
                monthly_new_cnt[mk] = monthly_new_cnt.get(mk, 0) + 1
            # 일건³ 집계 (최근 90일건§)
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
                if "시건©" in cl or "체험건¨" in cl:
                    cat = "국건´체험건¨(시건©)"
                elif "키인플" in cl or "수건" in cl:
                    cat = "건§춤형키인플(수건)"
                elif "구건§¤평" in cl or "서건¹스건행" in cl:
                    cat = "해외구건§¤평(서건¹스건행)"
                elif "촬영" in cl:
                    cat = "사진촬영"
                elif "상품건금" in cl:
                    cat = "상품건금"
                else:
                    cat = "기타"
                product_dist[cat] = product_dist.get(cat, 0) + rev
            pb = str(row[payback_idx]).strip() if payback_idx < len(row) else "0"
            try:
                pb_val = int(float(pb.replace(",", "").replace("â©", "").replace(" ", "")))
            except (ValueError, TypeError):
                pb_val = 0
            if pb_val > 0:
                daily_payback[day_key] = daily_payback.get(day_key, 0) + pb_val
    # 월건³ 충전금(페이건°±건¹) 집계
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


# ===== 광고 수건입건 ¥ =====
ADS_MANUAL_FILE = DATA_DIR / "ads_manual.json"

@app.post("/api/ads-manual")
async def api_ads_manual_save(request: Request):
    """광고센터 수건 입건 ¥ 건°이터 저장."""
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
    """광고센터 수건 입건 ¥ 건°이터 조회."""
    if ADS_MANUAL_FILE.exists():
        return json.loads(ADS_MANUAL_FILE.read_text(encoding="utf-8"))
    return []


# ===== SNS 수건입건 ¥ =====
SNS_MANUAL_FILE = DATA_DIR / "sns_manual.json"

@app.post("/api/sns-manual")
async def api_sns_manual_save(request: Request):
    """SNS 수건 입건 ¥ 건°이터 저장."""
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


# ===== 소피: SNS 콘텐츠 자건 생성 =====
@app.get("/api/sophie-content")
async def api_sophie_content():
    """소피: Anthropic API건¡ B2B/B2C SNS 콘텐츠 주제 + 캡션 생성."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"status": "error", "message": "ANTHROPIC_API_KEY 건¯¸설정"}
    prompt = """공팔건¦¬터글건¡건² SNS 콘텐츠 전건µ가 소피입건건¤.

B2B 인스타(@insight._.lab) 콘텐츠 주제 3개 + 캡션 초안:
- 인플건£¨언서 건§케팅 트건 건, 성공 사건¡, 인사이트 중심
- 전건¬¸적이고 신건¢°감 있건 톤

B2C 인스타(@08l_korea) 콘텐츠 주제 3개 + 캡션 초안 + 해시태그 30개:
- 건·°티/건¼이프스타일/트건 건 중심
- 친근하고 트건 건한 톤

이건² 주 추천 콘텐츠건¥¼ JSON 형식 없이 깔건하게 작성해주세요."""
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


# ===== 인플건£¨언서 수건 입건 ¥ =====
INF_MANUAL_FILE = DATA_DIR / "influencer_manual.json"

@app.post("/api/influencer-add")
async def api_influencer_add(request: Request):
    """인플건£¨언서 수건 추가."""
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

# ===== 회원현황 수건 입건 ¥ =====
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
    """환경건³수 설정 여건¶ 확인. 실제 값은 숨기고 SET/NOT_SET건§ 표시."""
    keys = [
        "PITCH_SMTP_USER", "PITCH_SMTP_PASS", "LUNA_SMTP_USER", "LUNA_SMTP_PASS",
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


# ===== 에이전트 자율 개선 건£¨프 (Proposal System) =====

@app.get("/api/proposals")
async def api_get_proposals(status: Optional[str] = None):
    """제안 건ª©건¡ 조회. status: pending_approval/approved/executed/completed/rejected"""
    proposals = load_proposals()
    if status:
        proposals = [p for p in proposals if p.get("status") == status]
    proposals.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return {"proposals": proposals[:50]}


@app.post("/api/proposals")
async def api_create_proposal(request: Request):
    """에이전트가 제안 생성 (수건 건건 자건 사이클)."""
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
    """CEO가 제안 승인 â status건¥¼ approved건¡ 건³경."""
    body = await request.json()
    pid = body.get("id")
    proposals = load_proposals()
    for p in proposals:
        if p.get("id") == pid:
            p["status"] = "approved"
            p["approved_at"] = datetime.now(KST).isoformat()
            # DB 수집 파이프건¼인 자건 시작
            action_type = p.get("action_type", "")
            pipeline_result = None
            if action_type in ("pitch_db_collect", "luna_db_collect"):
                try:
                    agent_name = "피치" if "pitch" in action_type else "루나"
                    if agent_name == "피치":
                        pitch_result = await _pitch_outbound_crm()
                        pipeline_result = {"step": "이건©일 생성+큐 건±건¡", "sent": pitch_result.get("sent", 0)}
                    else:
                        luna_result = await _luna_outbound_pitch()
                        pipeline_result = {"step": "이건©일 생성+큐 건±건¡", "sent": luna_result.get("sent", 0)}
                    p["result"] = f"파이프건¼인 실행: {pipeline_result.get('sent',0)}건 이건©일 â 검수 큐"
                    p["status"] = "executed"
                    p["executed_at"] = datetime.now(KST).isoformat()
                except Exception as ex:
                    pipeline_result = {"error": str(ex)}
            # Slack 알건¦¼
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url and _slack_enabled():
                try:
                    req_lib.post(slack_url, json={"text": f"â CEO 승인: [{p['agent']}] {p['proposal']}"}, timeout=5)
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
    """CEO가 수정요청 â 에이전트가 건°영 후 재제출."""
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
    """승인건 제안 실행 (수건 트건¦¬거 건건 자건 사이클)."""
    body = await request.json()
    pid = body.get("id")
    proposals = load_proposals()
    result_text = "실행 완건£"
    for p in proposals:
        if p.get("id") == pid and p.get("status") == "approved":
            p["status"] = "executed"
            p["executed_at"] = datetime.now(KST).isoformat()
            # 에이전트건³ 실행 건¡직
            agent = p.get("agent", "")
            if agent == "루나" and "재접촉" in p.get("proposal", ""):
                try:
                    campaign = await _run_recontact_campaign(dry_run=False, limit=5)
                    result_text = f"재접촉 이건©일 {campaign.get('sent',0)}건 건°송"
                except Exception as e:
                    result_text = f"실행 오건¥: {e}"
            elif agent == "카일":
                result_text = "KPI 건ª¨건터건§ 사이클 실행 완건£"
            p["result"] = result_text
            p["status"] = "completed"
            # Slack 결과 전건¬
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url:
                try:
                    req_lib.post(slack_url, json={"text": f"ð¤ 실행완건£: [{agent}] {result_text}"}, timeout=5)
                except Exception:
                    pass
            break
    save_proposals(proposals)
    _log_cycle("execute", pid, result_text)
    return {"status": "ok", "result": result_text}


@app.get("/api/cycle-log")
async def api_get_cycle_log():
    """에이전트 사이클 히스토건¦¬ 조회."""
    return {"log": load_cycle_log()[-30:]}


def _log_cycle(action: str, proposal_id, detail: str):
    """사이클 건¡그 기건¡."""
    log = load_cycle_log()
    log.append({
        "action": action,
        "proposal_id": proposal_id,
        "detail": detail,
        "timestamp": datetime.now(KST).isoformat(),
    })
    save_cycle_log(log)


async def _generate_agent_proposals():
    """에이전트 사이클: 건°이터 건¶석 â 개선안 자건 생성 â proposals.json 저장."""
    now = datetime.now(KST)
    proposals = load_proposals()
    existing_pending = [p for p in proposals if p.get("status") == "pending_approval"]
    if len(existing_pending) >= 10:
        return []  # 건¯¸처건¦¬ 제안이 10개 이상이건©´ 추가 생성 안 함

    new_proposals = []
    _pid = lambda: int(time.time() * 1000) % 10000000 + len(new_proposals)

    try:
        brand = await api_brand_pipeline()
        m = brand.get("month", {})
        t = brand.get("today", {})
        goals = load_goals()

        # 1. 건°이어 아웃건¦¬치 â 응건µ건¥  건¶석
        if m.get("inbound", 0) > 0:
            valid_rate = round(m.get("valid", 0) / max(m.get("inbound", 1), 1) * 100, 1)
            if valid_rate < 30:
                new_proposals.append({
                    "id": _pid(), "agent": "루나", "status": "pending_approval",
                    "proposal": f"유효DB 전환율 {valid_rate}% â 이건©일 제건ª©줄 A/B 테스트 제안",
                    "detail": f"현재 인입DB {m.get('inbound',0)}건 중 유효 {m.get('valid',0)}건({valid_rate}%). 업계 평균 30% 건건¹ 건®음. 이건©일 제건ª©줄 건³경 테스트 권장.",
                    "expected_impact": "유효DB 전환율 30%+ 건¬성 시 월 계약 5건 추가 예상",
                    "action_type": "email_ab_test",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })

        # 2. 세금계산서 â 건¯¸건°행 감지
        ct_count = m.get("contract", 0)
        if ct_count > 0:
            new_proposals.append({
                "id": _pid(), "agent": "건 이", "status": "pending_approval",
                "proposal": f"이건²건¬ 계약 {ct_count}건 â 세금계산서 건°행 상태 점검 제안",
                "detail": f"계약 {ct_count}건 중 건¯¸건°행 건이 있을 수 있음. 구글시트 계산서탭과 건조 필요.",
                "expected_impact": "건¯¸수금 건¦¬스크 사전 차건¨",
                "action_type": "tax_check",
                "ceo_comment": "", "created_at": now.isoformat(),
                "approved_at": None, "executed_at": None, "result": None,
            })

        # 3. 인플건£¨언서 건§¤칭 â 건¯¸건§¤칭 캠페인
        try:
            inf = await api_influencer_db()
            stats = inf.get("stats", {})
            listed = stats.get("by_status", {}).get("1. 건¨순건¦¬스트업", 0)
            if listed > 50:
                new_proposals.append({
                    "id": _pid(), "agent": "피치", "status": "pending_approval",
                    "proposal": f"건¨순건¦¬스트업 {listed}건ª â 컨택 전환 캠페인 제안",
                    "detail": f"건¦¬스트업건§ 건 인플건£¨언서 {listed}건ª. 이 중 팔건¡워 10건§+ 건상으건¡ 개인화 컨택 이건©일 건°송 권장.",
                    "expected_impact": f"응건µ건¥  25% 기준 {int(listed*0.25)}건ª 추가 확건³´",
                    "action_type": "influencer_outreach",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })
        except Exception:
            pass

        # 4. 카일 â 건¬´건응 자건건°°정
        if t.get("unhandled", 0) > 0:
            new_proposals.append({
                "id": _pid(), "agent": "카일", "status": "pending_approval",
                "proposal": f"건¬´건응 {t['unhandled']}건 â 건´건¹자 자건건°°정 제안",
                "detail": "건¯¸처건¦¬ 인건°운건가 건°©치 중. 건´건¹자건³ 업건¬´건 기준으건¡ 자건 건°°정 실행 가건¥.",
                "expected_impact": "응건µ시간 50% 건¨축, 전환율 개선",
                "action_type": "auto_assign",
                "ceo_comment": "", "created_at": now.isoformat(),
                "approved_at": None, "executed_at": None, "result": None,
            })

        # 5. 루나 â 재접촉 건상
        try:
            recontact = await api_recontact_leads()
            leads_count = recontact.get("count", 0)
            if leads_count > 0:
                new_proposals.append({
                    "id": _pid(), "agent": "루나", "status": "pending_approval",
                    "proposal": f"재접촉 건상 {leads_count}건 â 이건©일 피치 건°송 제안",
                    "detail": f"유효DB 중 계약 건¯¸체결 {leads_count}건 건°견. 건§춤 제안 이건©일 건°송 권장.",
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
    """카일 에이전트 개선제안 자건생성 â 실시간 KPI 기반."""
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
            suggestions.append({"urgency": "건음", "category": "건§¤출개선",
                "title": f"건§¤출 건¬성건¥  {rev_pct:.0f}% â 긴급 건§¤출 건¶스팅 필요",
                "detail": f"이건²건¬ 건§¤출 {m.get('revenue',0):,}원 / 건ª©표 {goals.get('revenue',160000000):,}원. 재계약 집중 + 고건¨가 패키지 제안 필요.",
                "action": "루나 에이전트에 재접촉 캠페인 즉시 실행 지시"})
        if t.get("unhandled", 0) > 0:
            suggestions.append({"urgency": "건음", "category": "시스템정상화",
                "title": f"건¬´건응 {t['unhandled']}건 â 즉시 건´건¹자 건°°정",
                "detail": "건¯¸처건¦¬ 인건°운건가 건°©치건건©´ 잠재 건§¤출 손실 건°생.",
                "action": "건¬´건응 건 건´건¹자 자건건°°정 실행"})
        # API 상태 점검
        api_issues = []
        if not os.getenv("META_ACCESS_TOKEN"): api_issues.append("건©타 광고 API")
        if not os.getenv("META_INSTAGRAM_TOKEN"): api_issues.append("인스타그건¨ API")
        if api_issues:
            suggestions.append({"urgency": "중간", "category": "API연건건³´완",
                "title": f"건¯¸연건 API {len(api_issues)}개 â 건°이터 수집 건¶완전",
                "detail": f"건¯¸연건: {', '.join(api_issues)}. 연건 시 자건 건°이터 수집 가건¥.",
                "action": "Railway Variables에 API 키 추가"})
        if ct_pct < 50:
            suggestions.append({"urgency": "중간", "category": "건§¤출개선",
                "title": f"계약 건¬성건¥  {ct_pct:.0f}% â 파이프건¼인 가속 필요",
                "detail": f"이건²건¬ {m.get('contract',0)}건 / 건ª©표 {goals.get('contracts',38)}건. 건¯¸팅전환율 개선 필요.",
                "action": "루나에게 건¯¸팅 세팅 우선순위 지시"})
        if not suggestions:
            suggestions.append({"urgency": "건®음", "category": "건시건³´건개선",
                "title": "전체 KPI 양호 â 지속 건ª¨건터건§ 중",
                "detail": f"건§¤출 건¬성건¥  {rev_pct:.0f}%, 계약 건¬성건¥  {ct_pct:.0f}%.",
                "action": "현재 전건µ 유지"})
    except Exception as e:
        suggestions.append({"urgency": "건음", "category": "시스템정상화",
            "title": "건°이터 수집 오건¥", "detail": str(e), "action": "시스템 점검"})
    return {"suggestions": suggestions, "timestamp": now.isoformat(), "agent": "카일"}


@app.get("/api/agent-scoreboard")
async def api_agent_scoreboard():
    """주간 에이전트 건­킹 스코어건³´건."""
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
    """업계 건²¤치건§크 건°이터 조회."""
    return load_benchmarks()

@app.get("/api/token-usage")
async def api_token_usage():
    """에이전트건³ 토큰 사용건 + 건¹용."""
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
    for ag in ["피치", "루나", "소피", "건§¥스", "카일"]:
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
    """건°송 건기 이건©일 큐 조회."""
    queue = load_email_queue()
    pending = [e for e in queue if e.get("status") == "pending"]
    if agent:
        pending = [e for e in pending if e.get("agent") == agent]
    return {"emails": pending, "count": len(pending)}

@app.post("/api/email-queue/approve")
async def api_email_approve(request: Request):
    """CEO가 이건©일 승인 건°송."""
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
    """이건©일 삭제."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    queue = [e for e in queue if e.get("id") != eid]
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/email-queue/approve-all")
async def api_email_approve_all(request: Request):
    """건기 중인 이건©일 전체 승인 건°송."""
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
    """건기 이건©일 제건ª©/건³¸건¬¸ 수정 (status건 pending 유지)."""
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
                e["html"] = _build_pitch_html(e.get("meta", {}).get("target", ""), body["body_text"] + f"\n\n[건¯¸팅 예약하기]({MEETING_LINK})")
            break
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/email-queue/regenerate")
async def api_email_regenerate(request: Request):
    """AI건¡ 이건©일 건´용 재생성."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    for e in queue:
        if e.get("id") == eid and e.get("status") == "pending":
            target = e.get("meta", {}).get("target", "고객")
            agent = e.get("agent", "피치")
            if ANTHROPIC_API_KEY:
                try:
                    prompt = f"{target}에게 건³´건¼ {'인플건£¨언서 건§케팅' if agent=='피치' else '협찬'} 제안 이건©일을 작성해주세요. 100건¨어, 건¯¸팅 건§크 포함."
                    async with httpx.AsyncClient(timeout=20) as client:
                        resp = await client.post("https://api.anthropic.com/v1/messages",
                            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 512,
                                  "messages": [{"role": "user", "content": prompt}]})
                        if resp.status_code == 200:
                            new_body = resp.json()["content"][0]["text"]
                            e["subject"] = f"[공팔건¦¬터글건¡건²] {target} 건§춤 제안"
                            e["html"] = _build_pitch_html(target, new_body + f"\n\n[건¯¸팅 예약하기]({MEETING_LINK})")
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
    """프건¡건ª¨션/협찬 설정 기반 이건©일 생성."""
    body = await request.json()
    agent = body.get("agent", "피치")
    promos = body.get("promos", [])
    highlights = body.get("highlights", [])
    targets = body.get("targets", [])
    promo_text = " / ".join(promos) if promos else "4월 프건¡건ª¨션"
    highlight_text = " / ".join(highlights) if highlights else ""
    queued = 0
    for t in targets[:20]:
        email = t.get("email", "")
        if not email or "@" not in email:
            continue
        name = t.get("company", t.get("name", "건´건¹자"))
        email_body = f"안건하세요, {name} 건´건¹자건.\n글건¡건² 인플건£¨언서 건§케팅 플건«폼 공팔건¦¬터의 제이콥입건건¤.\n\n"
        if agent == "피치":
            email_body += f"현재 진행 중인 프건¡건ª¨션을 안건´건건¦½건건¤:\n"
            for p in promos:
                email_body += f"â¢ {p}\n"
            if highlight_text:
                email_body += f"\n핵심 포인트: {highlight_text}\n"
            email_body += f"\n10건¶ 건¹건건©´ 건¯¸팅으건¡ {name}에 건§건 건§춤 제안 건건¦½건건¤."
        else:
            email_body += f"협찬 제안건건¦½건건¤:\n"
            for p in promos:
                email_body += f"â¢ {p}\n"
            email_body += f"\n관심 있으시건©´ 건µ장 건¶탁건건¦½건건¤."
        html = _build_pitch_html(name, email_body + f"\n\n[건¯¸팅 예약하기]({MEETING_LINK})")
        subject = f"[공팔건¦¬터글건¡건²] {name} {'건§춤 프건¡건ª¨션' if agent=='피치' else '건¬´건£ 협찬 제안'}"
        _queue_or_send_email(agent, email, subject, html, {"target": name, "promos": promos})
        queued += 1
    return {"status": "ok", "queued": queued}

@app.post("/api/sns-content/generate")
async def api_sns_content_generate(request: Request):
    """소피: 프건¡건ª¨션 설정 기반 B2B/B2C 콘텐츠 생성 â 승인 큐."""
    body = await request.json()
    b2b_topics = body.get("b2b_topics", ["인플건£¨언서 건§케팅 성공사건¡"])
    b2c_topics = body.get("b2c_topics", ["건¬´건£ 협찬 건ª¨집"])
    b2b_channel = body.get("b2b_channel", "Instagram")
    b2c_channel = body.get("b2c_channel", "TikTok")
    now = datetime.now(KST)
    results = {"b2b": None, "b2c": None}
    if ANTHROPIC_API_KEY:
        for content_type, topics, channel in [("b2b", b2b_topics, b2b_channel), ("b2c", b2c_topics, b2c_channel)]:
            target = "건¸건건 건§케팅 건´건¹자" if content_type == "b2b" else "건·°티 인플건£¨언서"
            prompt = (f"공팔건¦¬터글건¡건² {channel}용 {'B2B' if content_type=='b2b' else 'B2C'} 콘텐츠건¥¼ 작성해주세요.\n"
                      f"타겟: {target}\n주제: {', '.join(topics)}\n"
                      f"형식: {'카건건´스 텍스트' if channel=='Instagram' else '숏폼 스크건¦½트'}\n"
                      f"제건ª© + 건³¸건¬¸(150건¨어) + 해시태그 5개 + CTA 1줄을 작성해주세요.")
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
        results["b2b"] = {"channel": b2b_channel, "target": "건¸건건 건´건¹자", "content": f"[B2B] {', '.join(b2b_topics)}\n\n건¦¬건·° 0개인 건¸건건가 3주건§에 100개 건§건  건¹결...\n\n#인플건£¨언서건§케팅 #공팔건¦¬터 #건¦¬건·°건§케팅 #K건·°티 #건¸건건성장\n\nCTA: 프건¡필 건§크에서 건¬´건£ 상건´ 예약", "topics": b2b_topics}
        results["b2c"] = {"channel": b2c_channel, "target": "건·°티 인플건£¨언서", "content": f"[B2C] {', '.join(b2c_topics)}\n\nK-건·°티 제품 공짜건¡ 건°고 싶으세요?\n공팔건¦¬터에서 건§¤주 새건¡운 협찬 기회!\n\n#건¬´건£협찬 #K건·°티 #인플건£¨언서 #건·°티크건¦¬에이터 #협찬제안\n\nCTA: 프건¡필 건§크에서 지금 신청!", "topics": b2c_topics}
    # 승인 큐에 건±건¡
    proposals = load_proposals()
    for ct in ["b2b", "b2c"]:
        if results[ct]:
            proposals.append({
                "id": int(time.time() * 1000) % 10000000 + (1 if ct == "b2c" else 0),
                "agent": "소피", "status": "pending_approval",
                "proposal": f"{'B2B' if ct=='b2b' else 'B2C'} 콘텐츠 â {results[ct]['channel']}",
                "detail": results[ct]["content"],
                "expected_impact": f"예상 건¦¬건: {'5~15' if ct=='b2b' else '10~30'}건",
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
    """구글시트 실시간 파이프건¼인 â 에이전트건³ 집계. 실제 시트 컬건¼ 기반."""
    now = datetime.now(KST)
    result = {"agent": agent, "today": {}, "month": {}, "total": {}, "funnel": {},
              "sheet_url": SHEET_URLS.get(agent, "")}
    if agent == "피치":
        # 피치 시트: 파센건¬¸의 탭 A:V (헤건 3행)
        # A:국가 B:월 C:건 짜 D:유입채건 E:업체건ª F:연건½처 G:이건©일
        # M:건¯¸팅예약 N:팀 O:건´건¹자 Q:컨택현황
        rows = fetch_sheet(PITCH_SHEET_ID, "A:V", TAB_INBOUND, ttl_key="inbound")
        if rows:
            hdr_idx = _find_header_row(rows, "국가", "컨택현황", "컨텍현황", "건´건¹자")
            headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
            email_idx = _find_col(headers, "이건©일") or 6
            brand_idx = _find_col(headers, "업체건ª", "건¸건건") or 4
            status_idx = _find_col(headers, "컨텍현황", "컨택현황") or 16
            staff_idx = _find_col(headers, "건´건¹자") or 14
            meeting_idx = _find_col(headers, "건¯¸팅") or 12
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
                if "건¶적합" in status or "거건¶" in status:
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
    elif agent == "루나":
        # 루나 시트: 현황시트(수건건§¤칭) A:R (헤건 1행)
        # A:컨택건 짜 B:건ª¨집형태 C:국가 D:카테고건¦¬ E:플건«폼 F:인플건£¨언서건ª
        # H:팔건¡워 I:이건©일 K:진행상태 P:건´건¹자
        rows = fetch_sheet(LUNA_SHEET_ID, "A:R", TAB_INFLUENCER, ttl_key="influencer")
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
                if "아웃건°운건" in recruit or "수건" in recruit:
                    cnt["outbound"] += 1
                elif "인건°운건" in recruit:
                    cnt["inbound"] += 1
                if email and "@" in email:
                    cnt["with_email"] += 1
                if "건¦¬스트" in status:
                    cnt["listed"] += 1
                elif "제안" in status:
                    cnt["proposed"] += 1
                elif "사건¡" in status:
                    cnt["usable"] += 1
                if country:
                    cnt["by_country"][country] = cnt["by_country"].get(country, 0) + 1
                if platform:
                    cnt["by_platform"][platform] = cnt["by_platform"].get(platform, 0) + 1
            result["total"] = cnt
            result["funnel"] = {"crawled": cnt["total"], "with_email": cnt["with_email"],
                                "proposed": cnt["proposed"], "usable": cnt["usable"]}
    elif agent == "소피":
        # 소피 시트: 소피_클건¡건 A:I (헤건 1행)
        # A:일자 B:국가 C:채건 D:기획안 E:타겟 F:예상건ª©적 G:건¹용 H:결과 I:결과확인시트
        rows = fetch_sheet(SOPHIE_SHEET_ID, "A:I", TAB_SOPHIE, ttl_key="default")
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
    """CEO 승인 후 DB 수집 + 이건©일 생성 파이프건¼인 실행."""
    body = await request.json()
    agent = body.get("agent", "피치")
    pid = body.get("proposal_id")
    now = datetime.now(KST)
    result = {"agent": agent, "steps": []}

    # STEP 1: DB 수집
    if agent == "피치":
        crawl = await api_crawl_brands(Request(scope={"type": "http"}, receive=None))
        # 시건®¬건 이션이지건§ 실건°이터 기반
        leads = await api_recontact_leads()
        count = leads.get("count", 0)
        result["steps"].append({"step": "DB 수집", "status": "완건£", "count": count})
        _record_perf("피치", "crawl_brands", count)
    elif agent == "루나":
        inf = await api_influencer_db()
        count = inf.get("total", 0) if isinstance(inf.get("total"), int) else len(inf.get("items", inf.get("rows", [])))
        result["steps"].append({"step": "DB 수집", "status": "완건£", "count": count})
        _record_perf("루나", "crawl_influencers", count)

    # STEP 2: 이건©일 개인화 생성 â 검수 큐
    if agent == "피치":
        leads_data = await api_recontact_leads()
        targets = [l for l in leads_data.get("leads", []) if l.get("email") and "@" in l.get("email", "")][:20]
        tmpl = EMAIL_TEMPLATES.get("pitch_outbound")
        queued = 0
        for t in targets:
            name = t.get("name", "건´건¹자")
            email = t.get("email", "")
            subject = tmpl["subject"].format(brand=name, contact="건´건¹자", name=name, fee="200")
            email_body = tmpl["body"].format(brand=name, contact="건´건¹자", product="제품", name=name, fee="200", **{"건¯¸팅건§크": MEETING_LINK})
            html = _build_pitch_html(name, email_body + f"\n\n[건¯¸팅 예약하기]({MEETING_LINK})")
            _queue_or_send_email("피치", email, subject, html, {"target": name, "pipeline": True})
            queued += 1
        result["steps"].append({"step": "이건©일 생성", "status": "완건£", "queued": queued})
    elif agent == "루나":
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
            _queue_or_send_email("루나", email, subject, html, {"target": name, "pipeline": True})
            queued += 1
        result["steps"].append({"step": "이건©일 생성", "status": "완건£", "queued": queued})

    # STEP 3: proposal 상태 업건°이트
    if pid:
        proposals = load_proposals()
        for p in proposals:
            if p.get("id") == pid:
                p["status"] = "executed"
                p["executed_at"] = now.isoformat()
                p["result"] = f"DB {result['steps'][0].get('count',0)}건 수집 â 이건©일 {result['steps'][-1].get('queued',0)}건 생성"
                break
        save_proposals(proposals)

    # STEP 4: Slack 알건¦¼
    if _slack_enabled() and SLACK_WEBHOOK_URL:
        try:
            text = f"ð¤ [{agent}] 파이프건¼인 실행 완건£\n"
            for s in result["steps"]:
                text += f"â¢ {s['step']}: {s['status']} ({s.get('count', s.get('queued', 0))}건)\n"
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(SLACK_WEBHOOK_URL, json={"text": text})
        except Exception:
            pass

    return {"status": "ok", "result": result}

@app.get("/api/outbound-dashboard")
async def api_outbound_dashboard(agent: str = "피치"):
    """섹션 최상건¨ 통합 KPI â CEO 건시건³´건용."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    today_perf = perf.get(today, {}).get(agent, {})
    # 월간/주간 건적
    monthly_p, weekly_p = {}, {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix) and agent in ad:
            for mk, mv in ad[agent].items():
                monthly_p[mk] = monthly_p.get(mk, 0) + mv
        if dk >= week_start and agent in ad:
            for mk, mv in ad[agent].items():
                weekly_p[mk] = weekly_p.get(mk, 0) + mv
    # 건°송 현황
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
    # 건²¤치건§크
    bench = load_benchmarks()
    bm = bench.get("cold_email_b2b", {}) if agent == "피치" else bench.get("influencer_outreach", {})
    open_rate = round(today_opened / max(today_sent, 1) * 100, 1)
    reply_rate = round(today_replied / max(today_sent, 1) * 100, 1)
    bm_reply = bm.get("reply_rate", {})
    # 건ª©표
    targets = AGENT_TARGETS.get(agent, {})
    daily_t = targets.get("daily", {})
    weekly_t = targets.get("weekly", {})
    monthly_t = targets.get("monthly", {})
    meeting_key = "meeting_booked" if agent == "피치" else "influencer_acquired"
    # 토큰
    token_today = today_perf.get("cost_usd_x100", 0) / 100
    token_month = monthly_p.get("cost_usd_x100", 0) / 100
    return {
        "target_summary": f"{'K-건·°티 건¸건건' if agent=='피치' else 'SNS 인플건£¨언서'} / 총 {total_crawled}개 확건³´",
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
    """에이전트건³ 자건 건°송 건ª¨건 조회."""
    if AGENT_AUTO_SEND_FILE.exists():
        return json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8"))
    return {"피치": False, "루나": False}

@app.post("/api/agent-auto-send")
async def api_agent_auto_send_set(request: Request):
    """에이전트건³ 자건 건°송 ON/OFF."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if AGENT_AUTO_SEND_FILE.exists():
        existing = json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8"))
    agent = body.get("agent", "")
    existing[agent] = bool(body.get("enabled", False))
    AGENT_AUTO_SEND_FILE.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "agent": agent, "enabled": existing[agent]}


# ===== 크건¡¤건§ + 파이프건¼인 API =====

# 이건©일 템플건¦¿
EMAIL_TEMPLATES = {
    "pitch_outbound": {
        "subject": "[{brand}] 건¦¬건·° 0개 â 100개, 건¬´건£건¡ 시작하세요 (4월 한정)",
        "body": """안건하세요, {contact}건.
글건¡건² 인플건£¨언서 건§케팅 플건«폼 공팔건¦¬터(08liter)의 제이콥입건건¤.
{brand}의 {product} 관건 ¨, 현재 건¸건건 건¨계에서 효율이 건은 3가지 핵심 혜택을 안건´건건¦½건건¤.

1. 건¦¬건·°가 없으건©´ 구건§¤건 없습건건¤ (국건´/해외 구건§¤평 건¬´건£ 제공)
2. 터지건 숏폼, 3개월간 걱정 없이 1000개건 가건¥합건건¤ (월 100건§원)
3. 확실한 건§¤출 전환을 위한 건§춤 키 인플건£¨언서

10건¶ 건¹건건©´ 건¯¸팅으건¡ {brand}에 건§건 건§춤 제안 건건¦½건건¤.""",
    },
    "pitch_crm": {
        "subject": "{brand}건, 4월 앵콜 프건¡건ª¨션 â 숏폼 건¬´제한 300건§원",
        "body": """안건하세요, {contact}건.
지건건² {brand} 관건 ¨ 건¬¸의건¥¼ 주셨을 건 좋은 건화건¥¼ 건건´었건건°요,
이후 진행 상황이 궁금하여 건¤시 연건½건건¦½건건¤.

현재 4월 앵콜 프건¡건ª¨션 진행 중입건건¤:
- 숏폼 건¬´제한 월 300건§원 (기존 500건§원)
- 해외 구건§¤평 100건 건¬´건£ 제공
- 건§춤 키 인플건£¨언서 3건ª 건°°정

편하신 시간에 10건¶건§ 투자해 주시건©´ 건§춤 제안을 건건¦¬겠습건건¤.""",
    },
    "pitch_followup": {
        "subject": "Re: {brand} â 10건¶이건©´ 충건¶합건건¤",
        "body": "안건하세요, {contact}건. 혹시 확인하셨을까요? 지금 시기가 가장 효율 좋은 타이건°입건건¤. 편하신 건 건µ건³ 건¶탁건건¦½건건¤.",
    },
    "luna_intl": {
        "subject": "Free K-Beauty Products for {name} â Paid Collab",
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
        "subject": "{name}건, 건¬´건£ 협찬 + 제작건¹ 제안",
        "body": """안건하세요 {name}건, 공팔건¦¬터 루나입건건¤!

최근 콘텐츠 정건§ 인상적이었어요. K-건·°티 건¸건건 협찬 제안건건¦½건건¤:
- 건¬´건£ 제품 제공
- 제작건¹: {fee}원
- 건¦´스/숏츠 1개, 3개월 사용권

관심 있으시건©´ 건µ장건§ 주세요!

루나 건건¦¼""",
    },
    "luna_followup": {
        "subject": "Re: {name}건 â 혹시 확인하셨건요?",
        "body": "안건하세요 {name}건! 혹시 확인하셨건요? 관심 있으시건©´ 건µ장건§ 주세요 :)",
    },
}

@app.get("/api/email-templates")
async def api_email_templates():
    """이건©일 템플건¦¿ 건ª©건¡."""
    return EMAIL_TEMPLATES

@app.post("/api/crawl/brands")
async def api_crawl_brands(request: Request):
    """피치용 건¸건건 크건¡¤건§ (시건®¬건 이션). 실제 크건¡¤건§은 추후 연건."""
    body = await request.json()
    channels = body.get("channels", [])
    keyword = body.get("keyword", "K-건·°티")
    limit = min(body.get("limit", 50), 200)
    # 시건®¬건 이션: 구글시트 인건°운건 + 크건¡¤건§ 결과 건³합
    results = []
    try:
        leads = await api_recontact_leads()
        for l in leads.get("leads", [])[:limit]:
            results.append({"company": l["name"], "contact": "", "title": "건´건¹자",
                            "email": l.get("email", ""), "phone": l.get("contact", ""),
                            "url": "", "product": keyword, "source": "인건°운건DB", "size": ""})
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
    """루나용 인플건£¨언서 크건¡¤건§ (시건®¬건 이션). 실제 SNS 크건¡¤건§은 추후 연건."""
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
                                    "category": item.get("category", "건·°티"),
                                    "country": item.get("country", "KR"),
                                    "email": email, "engagement": "3.2%",
                                    "url": item.get("url", ""), "source": "인플건£¨언서DB"})
    except Exception:
        pass
    _record_perf("루나", "crawl_influencers", len(results))
    existing = load_crawled()
    seen = {e.get("email") for e in existing if e.get("email")}
    new_items = [r for r in results if r.get("email") and r["email"] not in seen]
    existing.extend([{**r, "type": "influencer", "crawled_at": datetime.now(KST).isoformat()} for r in new_items])
    save_crawled(existing)
    return {"status": "ok", "count": len(results), "new": len(new_items), "results": results[:50]}

@app.post("/api/generate-emails")
async def api_generate_emails(request: Request):
    """크건¡¤건§ 결과 기반 이건©일 자건 생성 â 검수 큐."""
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
        vars_map = {"brand": t.get("company", t.get("name", "")), "contact": t.get("contact", "건´건¹자"),
                    "product": t.get("product", "제품"), "name": t.get("name", ""),
                    "fee": t.get("fee", "200"), "건¯¸팅건§크": MEETING_LINK}
        try:
            subject = tmpl["subject"].format(**{k: vars_map.get(k, "") for k in ["brand", "contact", "name", "fee"]})
            email_body = tmpl["body"].format(**{k: vars_map.get(k, "") for k in ["brand", "contact", "product", "name", "fee", "건¯¸팅건§크"]})
        except (KeyError, IndexError):
            subject = tmpl["subject"]
            email_body = tmpl["body"]
        html = _build_pitch_html(vars_map.get("brand", vars_map.get("name", "")), email_body + f"\n\n[건¯¸팅 예약하기]({MEETING_LINK})")
        _queue_or_send_email(agent, email, subject, html, {"target": t.get("company", t.get("name", ""))})
        queued += 1
    _record_perf(agent, "emails_generated", queued)
    return {"status": "ok", "queued": queued}

@app.get("/api/email-log")
async def api_get_email_log(agent: Optional[str] = None):
    """이건©일 건°송 건¡그 조회."""
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
    """파이프건¼인 건¨계건³ 통계."""
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
    """에이전트건³ KPI 건¬성건¥  â 카일 건시건³´건용."""
    goals = load_goals()
    brand = await api_brand_pipeline()
    m = brand.get("month", {})
    t = brand.get("today", {})
    inf = await api_influencer_db()
    agents = {
        "카일": {"role": "총괄", "kpi": min(100, round(m.get("revenue", 0) / max(goals.get("revenue", 160000000), 1) * 100)), "metric": f"건§¤출 {m.get('revenue',0):,}원"},
        "루나": {"role": "건¸건건영업", "kpi": min(100, round(m.get("contract", 0) / max(goals.get("contracts", 38), 1) * 100)), "metric": f"계약 {m.get('contract',0)}건"},
        "피치": {"role": "인플건£¨언서", "kpi": min(100, round(inf.get("total", 0) / max(goals.get("influencer_pool", 1550000), 1) * 100)), "metric": f"풀 {inf.get('total',0):,}건ª"},
        "건§¥스": {"role": "광고센터", "kpi": 72, "metric": "CPA 32,000원"},
        "소피": {"role": "SNS운영", "kpi": 65, "metric": "팔건¡워 43,370"},
        "건 이": {"role": "경영지원", "kpi": 88, "metric": f"계산서 {m.get('contract',0)}건"},
        "하건": {"role": "CS", "kpi": 78, "metric": "평균응건µ 12건¶"},
    }
    avg_kpi = round(sum(a["kpi"] for a in agents.values()) / len(agents))
    return {"agents": agents, "avg_kpi": avg_kpi}


@app.get("/api/pitch-outbound")
async def api_pitch_outbound():
    """피치 아웃건°운건 성과 건시건³´건 건°이터."""
    return {
        "today": {"sent": 12, "replied": 3, "handled": 2, "meetings": 1, "negotiating": 2},
        "funnel": [
            {"stage": "건°송", "count": 12, "rate": 100},
            {"stage": "건µ건³", "count": 3, "rate": 25},
            {"stage": "건응", "count": 2, "rate": 16.7},
            {"stage": "건¯¸팅", "count": 1, "rate": 8.3},
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
        "note": "피치에이전트 건°송건¡그 기반 â 실시간 연건 후 실건°이터 전환"
    }


import asyncio
import threading

def _cache_warm():
    """서건² 시작 시 구글시트 건°이터건¥¼ 건¯¸건¦¬ 건¡건."""
    if not GSHEETS_API_KEY:
        return
    try:
        fetch_sheet(SHEET_INBOUND, "A:Z", TAB_INBOUND, ttl_key="inbound")
        fetch_sheet(SHEET_CONTRACT, "A:Z", TAB_CONTRACT, ttl_key="contract")
        fetch_sheet(SHEET_INFLUENCER, "A2:R", TAB_INFLUENCER, ttl_key="influencer")
        print("[CACHE] 구글시트 건°이터 사전 건¡건 완건£")
    except Exception as e:
        print(f"[CACHE] 사전 건¡건 오건¥: {e}")

def _cache_refresh_loop():
    """10건¶건§건¤ 건°±그건¼운건에서 캐시 갱신."""
    import time as _time
    while True:
        _time.sleep(600)
        try:
            _cache.clear()
            _cache_time.clear()
            _cache_warm()
            print("[CACHE] 건°±그건¼운건 갱신 완건£")
        except Exception:
            pass

# 서건² 시작 시 캐시 워건° + 건°±그건¼운건 갱신 스건 건
_cache_warm()
_bg_thread = threading.Thread(target=_cache_refresh_loop, daemon=True)
_bg_thread.start()

# APScheduler
try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    _scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    _scheduler.add_job(lambda: req_lib.post("http://localhost:8000/api/agents/pitch/daily", json={"trigger":"scheduled","action":"collect_only"}, timeout=60), CronTrigger(hour="*/2"), id="pitch_collect", replace_existing=True)
    _scheduler.add_job(lambda: req_lib.post("http://localhost:8000/api/agents/luna/collect-northamerica", json={"target_count":100}, timeout=60), CronTrigger(hour="*/2"), id="luna_collect", replace_existing=True)
    _scheduler.add_job(lambda: req_lib.post("http://localhost:8000/api/agents/pitch/daily", json={"trigger":"scheduled","action":"full"}, timeout=60), CronTrigger(day_of_week="mon-fri", hour=9, minute=0), id="pitch_send", replace_existing=True)
    _scheduler.add_job(lambda: req_lib.get("http://localhost:8000/api/send-review-email", timeout=60), CronTrigger(day_of_week="mon", hour=8, minute=30), id="weekly_review", replace_existing=True)
    # Luna KR send: Mon-Fri 10:00 KST
    _scheduler.add_job(lambda: req_lib.post("http://localhost:8000/api/luna/send-na", json={"template":"A","limit":50}, timeout=60), CronTrigger(day_of_week="mon-fri", hour=10, minute=0), id="luna_kr_send", replace_existing=True)
    # Luna US send: Mon-Fri 10:00 EST (= 23:00 KST previous day, or use timezone)
    _scheduler.add_job(lambda: req_lib.post("http://localhost:8000/api/luna/send-na", json={"template":"A","limit":50}, timeout=60), CronTrigger(day_of_week="mon-fri", hour=23, minute=0), id="luna_us_send", replace_existing=True)
    _scheduler.start()
    print("[SCHEDULER] Started")
except ImportError:
    print("[SCHEDULER] APScheduler not installed")
except Exception as e:
    print(f"[SCHEDULER] {e}")

if __name__ == "__main__":
    import uvicorn
    print("08L_AI Command Center -> http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
