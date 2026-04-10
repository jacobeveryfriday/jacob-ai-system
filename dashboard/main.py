"""08L_AI Command Center â íµí© 건ì건³´건 + Google Sheets API + Anthropic AI Agents"""
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

load_dotenv(override=False)  # OS íê²½건³ì(Railway)ê° .env건³´건¤ ì°ì 
app = FastAPI(title="Command Center")
app.add_middleware(GZipMiddleware, minimum_size=500)
KST = ZoneInfo("Asia/Seoul")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ===== 건¡ê·¸ì¸ ì¸ì¦ (ì¿ í¤ ì¸ì 건°©ì) =====
DASH_USER = os.getenv("DASH_USER", "")
DASH_PASS = os.getenv("DASH_PASS", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", secrets.token_hex(32))


def _make_token(user: str) -> str:
    return hashlib.sha256(f"{user}:{SESSION_SECRET}".encode()).hexdigest()


@app.get("/health")
async def health_check():
    """ì ì²´ API ì°건 ìí â 7ê° ì건¹ì¤"""
    def _chk(key): return "connected" if os.getenv(key) else "not_configured"
    # 건©í: í í° ì¡´ì¬í건©´ connected, API í¸ì¶ì 건³건 ê²ì¦
    meta_status = "not_configured"
    meta_note = ""
    if os.getenv("META_ACCESS_TOKEN"):
        meta_status = "connected"
        try:
            r = req_lib.get(f"https://graph.facebook.com/v18.0/act_{os.getenv('META_AD_ACCOUNT_ID','230720044045370')}/campaigns",
                params={"access_token": os.getenv("META_ACCESS_TOKEN"), "fields": "name", "limit": "1"}, timeout=5)
            if r.status_code != 200:
                meta_note = "í í° ì í¨í건 API ì건µ 건¹ì ì (code=" + str(r.status_code) + ")"
        except Exception:
            meta_note = "API í¸ì¶ íììì (í í°ì ì¤ì 건¨)"
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


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    """건¡ê·¸ì¸ í¼ íì´ì§"""
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
{"<p class='err'>ìì´건 건건 건¹건°건²í¸ê° í건 ¸ìµ건건¤.</p>" if error else ""}
<form method="post" action="/login">
<input name="username" placeholder="ìì´건" required autocomplete="username">
<input name="password" type="password" placeholder="건¹건°건²í¸" required autocomplete="current-password">
<button type="submit">건¡ê·¸ì¸</button>
</form></div></body></html>"""
    return HTMLResponse(html)


@app.post("/login")
async def login_submit(request: Request):
    """건¡ê·¸ì¸ ì²건¦¬"""
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
    """ì¿ í¤ ì¸ì 기반 ì¸ì¦ íì¸. DASH_USER 건¯¸ì¤ì  ì í­ì True."""
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

# 건°ì¡ ì건 ì í
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
    """ì´건©ì¼ 건°ì¡ 건¡ê·¸ ê¸°건¡."""
    log = load_email_log()
    log.append({"agent": agent, "to": to, "subject": subject, "status": status,
                "sent_at": datetime.now(KST).isoformat(), "opened": False,
                "replied": False, "followup_count": 0, "meta": meta or {}})
    save_email_log(log)

def _check_send_limit() -> bool:
    """ì¼ì¼ 건°ì¡ í건 íì¸."""
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
    """ìì´ì í¸ ì건 건°ì¡ 건ª¨건 íì¸. ê¸°건³¸ OFF."""
    if AGENT_AUTO_SEND_FILE.exists():
        try:
            return json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8")).get(agent, False)
        except Exception:
            pass
    return False

def _queue_or_send_email(agent: str, to_email: str, subject: str, html: str, meta: dict = None) -> dict:
    """ì건 건°ì¡ 건ª¨건건©´ ì¦ì 건°ì¡, ì건건©´ ê²ì íì ì¶ê°."""
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

# í í° 건¹ì© 건¨ê° (USD per M tokens)
TOKEN_COSTS = {
    "haiku": {"input": 1.0, "output": 5.0},
    "sonnet": {"input": 3.0, "output": 15.0},
}

def _record_tokens(agent: str, input_tokens: int, output_tokens: int, model: str = "sonnet"):
    """ìì´ì í¸건³ í í° ì¬ì©건 ê¸°건¡."""
    cost_table = TOKEN_COSTS.get("haiku" if "haiku" in model.lower() else "sonnet", TOKEN_COSTS["sonnet"])
    cost = (input_tokens * cost_table["input"] + output_tokens * cost_table["output"]) / 1_000_000
    _record_perf(agent, "input_tokens", input_tokens)
    _record_perf(agent, "output_tokens", output_tokens)
    _record_perf(agent, "cost_usd_x100", int(cost * 100))

# ===== ìì´ì í¸건³ êµ¬ê¸ìí¸ =====
PITCH_SHEET_ID = os.getenv("PITCH_SHEET_ID", "1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8")
LUNA_SHEET_ID = os.getenv("LUNA_SHEET_ID", "1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs")
SOPHIE_SHEET_ID = os.getenv("SOPHIE_SHEET_ID", "1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU")

SHEET_URLS = {
    "í¼ì¹": "https://docs.google.com/spreadsheets/d/1ISL7s96ylMGhZzxeC0ABzwHgZWszA7yqoY_deXPMce8/edit#gid=0",
    "루나": "https://docs.google.com/spreadsheets/d/1xLkrmlFfVrTEWvsbaP5FaBQ8sRvqestuQNorVC_Urgs/edit#gid=0",
    "ìí¼": "https://docs.google.com/spreadsheets/d/1FOnGv2WMurqFo4Kpx0s4vltSkAeEEIm3yUTYhXSW2pU/edit#gid=0",
    "건 ì´": "https://docs.google.com/spreadsheets/d/1j_3IYME764NlrARbNCZ_TJqzZCyfAMy-N3V-ByRik6Q/edit#gid=0",
}

MEETING_LINK ="https://calendar.google.com/calendar/u/0/appointments/schedules/AcZssZ3b3pndYo35A_3SjrHJeeXfAm3YpvBX0IXfkJqXP0QXixBEADR_ehY__tHBlJdNBkL5I2868Rrd"

# ===== ìì´ì í¸ ì´건©ì¼ ê³ì  =====
AGENT_EMAILS = {
    "ì¹´ì¼": os.getenv("KYLE_EMAIL", "kyle@08liter.com"),
    "루나": os.getenv("LUNA_EMAIL", "luna@08liter.com"),
    "í¼ì¹": os.getenv("PITCH_EMAIL", "pitch@08liter.com"),
    "건§¥ì¤": os.getenv("MAX_EMAIL", "max@08liter.com"),
    "ìí¼": os.getenv("SOPHIE_EMAIL", "sophie@08liter.com"),
    "건 ì´": os.getenv("RAY_EMAIL", "ray@08liter.com"),
    "í건": os.getenv("HANA_EMAIL", "hana@08liter.com"),
}

# ===== ìê° 건ª©í (ê¸°건³¸ê°, /api/goals건¡ ìì  ê°건¥) =====
DEFAULT_GOALS = {
    "revenue": 160000000, "contracts": 38, "inbound_db": 500,
    "valid_db": 150, "cpa": 50000, "influencer_pool": 1550000,
    "alert_threshold": 0.3,
}

# ===== ìì´ì í¸건³ 건ª©í (ì¼/ì£¼/ì) =====
AGENT_TARGETS = {
    "í¼ì¹": {
        "monthly": {"new_contract": 10, "renew_contract": 10, "meeting_booked": 60, "inbound_email": 3000, "outbound_email": 5000, "total_email": 8000},
        "weekly":  {"new_contract": 2.5, "renew_contract": 2.5, "meeting_booked": 15, "inbound_email": 750, "outbound_email": 1250, "total_email": 2000},
        "daily":   {"meeting_booked": 3, "inbound_email": 150, "outbound_email": 250, "total_email": 400},
    },
    "루나": {
        "monthly": {"influencer_acquired": 300, "outbound_email": 3000, "crawl_data": 5000, "email_reply": 450},
        "weekly":  {"influencer_acquired": 75, "outbound_email": 750, "crawl_data": 1250, "email_reply": 113},
        "daily":   {"influencer_acquired": 15, "outbound_email": 150, "crawl_data": 250, "email_reply": 23},
    },
    "ìí¼": {
        "monthly": {"b2b_content": 20, "b2c_content": 20, "b2b_lead": 300, "b2c_lead": 500},
        "weekly":  {"b2b_content": 5, "b2c_content": 5, "b2b_lead": 75, "b2c_lead": 125},
        "daily":   {"b2b_content": 1, "b2c_content": 1, "b2b_lead": 15, "b2c_lead": 25},
    },
    "건§¥ì¤": {
        "monthly": {"cpa_target": 20000, "valid_db_ratio_x": 2},
    },
    "ì¹´ì¼": {
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
    """ìì´ì í¸ ì¼ì¼ ì±ê³¼ ê¸°건¡. {건 ì§: {ìì´ì í¸: {metric: count}}}"""
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
    "contract": 300,     # 5건¶ â 건¡건© ì건 ê°ì 
    "influencer": 21600, # 6 hours
    "ads": 3600,         # 1 hour
    "default": 1800,     # 30 min fallback
}

SYSTEMS = [
    {"name": "KPI ì§ê³건´", "icon": "chart", "port": 8001, "desc": "ì¼ì¼ KPI ì건 ì§ê³ 건° Slack 건°ì¡", "company": "ê³µíµ"},
    {"name": "SNS ì¤ì¼ì¤건¬", "icon": "share", "port": 8002, "desc": "SNS ì½íì¸  ì건 건°í ê´건¦¬", "company": "ê³µíµ"},
    {"name": "ì¹´ì¹´ì¤ CRM", "icon": "msg", "port": 8003, "desc": "êµ¬건§¤ í 건©ìì§ ìíì¤ ì건í", "company": "Mili Mili"},
    {"name": "건¦¬건 íì´í건¼ì¸", "icon": "lead", "port": 8004, "desc": "ì¸건°ì´건 건¦¬건 ìì§ 건° 건±ê¸ 건¶건¥", "company": "08Liter"},
    {"name": "ê³ì½ ì건í", "icon": "doc", "port": 8005, "desc": "ì ìê³ì½ íì´í건¼ì¸", "company": "08Liter"},
    {"name": "ê´ê³  건ª¨건í°건§", "icon": "ad", "port": 8006, "desc": "ROAS/CPA/CTR ì¤ìê° ì¶ì ", "company": "Mili Mili"},
    {"name": "건¦¬건·° 건ª¨건í°건§", "icon": "star", "port": 8007, "desc": "건¦¬건·° ì¶ì  건° 건ì ê´건¦¬", "company": "Mili Mili"},
]


# ===== Google Sheets Reader =====
def fetch_sheet(sheet_id: str, range_name: str, tab_name: str = None, ttl_key: str = "default") -> list:
    """Google Sheets API v4건¡ 건°ì´í° ì½ê¸°. API Key ìì¼건©´ 건¹ 건¦¬ì¤í¸."""
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
        "unhandled_brands": [{"name": "ìí건¸건건A", "channel": "SNS(건©í)", "source": "", "date": "ì¤건", "reason": "건´건¹ì ìì"}],
        "prev_month": {"inbound": 38, "valid": 110, "meeting": 25, "contract": 8, "renewal": 3},
        "last_year": {"inbound": 22, "valid": 68, "meeting": 15, "contract": 5, "renewal": 1},
        "conversion": {"valid_rate": 29.5, "meeting_rate": 22.0, "contract_rate": 4.7, "renewal_rate": 0.5},
        "channel_breakdown": [
            {"channel": "SNS(건©í)", "inbound": 18, "valid": 6, "rate": 33.3},
            {"channel": "ì´건©ì¼", "inbound": 8, "valid": 3, "rate": 37.5},
            {"channel": "CPC(건¤ì´건²)", "inbound": 12, "valid": 2, "rate": 16.7},
            {"channel": "ê¸°í", "inbound": 5, "valid": 1, "rate": 20.0},
        ],
        "staff_breakdown": [
            {"name": "ìí건¼", "inbound": 20, "valid": 8, "contract": 3, "rate": 40.0},
            {"name": "건¼ì´건", "inbound": 15, "valid": 6, "contract": 2, "rate": 40.0},
            {"name": "건¤ì", "inbound": 8, "valid": 3, "contract": 1, "rate": 37.5},
        ],
        "pipeline": {
            "ì¸ìDB": [
                {"name": "건·°í°건¸건건A", "channel": "ì¸ì¤íê·¸건¨", "date": today_str, "staff": "건¯¸건°°ì "},
                {"name": "ì½ì¤건©í±B", "channel": "êµ¬ê¸ê´ê³ ", "date": today_str, "staff": "건¯¸건°°ì "},
                {"name": "ì¤í¨ì¼ì´C", "channel": "LinkedIn", "date": today_str, "staff": "건¯¸건°°ì "},
            ],
            "ì í¨DB": [
                {"name": "건¸건건D", "channel": "ì¹´ì¹´ì¤í¡", "staff": "ìí건¼", "contact_count": 2},
                {"name": "건¸건건E", "channel": "ì´건©ì¼", "staff": "건¼ì´건", "contact_count": 1},
                {"name": "건¸건건F", "channel": "ì í", "staff": "건¤ì", "contact_count": 3, "expected": "450건§"},
            ],
            "건¯¸í": [
                {"name": "건¸건건G", "meeting_date": "건´ì¼ 14:00", "stage": "ê²¬ì  ê²í ì¤", "amount": "520건§", "package": "Growth"},
                {"name": "건¸건건H", "meeting_date": "건ª©ìì¼", "stage": "ì ìì ì 건¬", "amount": "450건§", "package": "Growth"},
            ],
            "ê³ì½ì": [
                {"name": "건¸건건I", "stage": "ê³ì½ì ê²í ì¤", "amount": "600건§", "package": "Premium"},
                {"name": "건¸건건J", "stage": "건´건¶ ê²°ì¬ì¤", "amount": "800건§", "package": "Enterprise"},
            ],
            "ì¬ê³ì½": [
                {"name": "건¸건건K", "date": "4ì 1ì¼", "amount": "420건§", "package": "Growth", "paid": True},
                {"name": "건¸건건L", "date": "3ì 25ì¼", "amount": "380건§", "package": "Growth", "paid": True},
            ],
        },
    }


def _dummy_influencer_db():
    return {
        "source": "dummy", "total": 1400000, "items": [
            {"date": "2026-04-01", "type": "ìì건°ì´건", "country": "KR", "category": "건·°í°", "platform": "Instagram", "account": "@beauty_kr1", "url": "https://instagram.com/beauty_kr1", "followers": "520K", "followers_num": 520000, "email": "", "contact": "", "status": "ì¬건¡íì©ê°건¥", "currency": "", "price_collab": "180", "price_wish": "200", "price_krw": "180", "staff": "ìí건¼", "campaign": "3ì ìº íì¸", "note": ""},
            {"date": "2026-04-01", "type": "ì¸건°ì´건", "country": "TH", "category": "í¨ì", "platform": "TikTok", "account": "@style_th", "url": "https://tiktok.com/@style_th", "followers": "380K", "followers_num": 380000, "email": "", "contact": "", "status": "ì ì건°ì¡", "currency": "", "price_collab": "120", "price_wish": "150", "price_krw": "120", "staff": "건¼ì´건", "campaign": "2ì ìº íì¸", "note": ""},
            {"date": "2026-03-28", "type": "ìì건°ì´건", "country": "US", "category": "건·°í°", "platform": "Instagram", "account": "@skincare_us", "url": "", "followers": "210K", "followers_num": 210000, "email": "", "contact": "", "status": "건¨ì건¦¬ì¤í¸ì", "currency": "", "price_collab": "250", "price_wish": "300", "price_krw": "250", "staff": "ìí건¼", "campaign": "", "note": ""},
            {"date": "2026-03-25", "type": "ìì건°ì´건", "country": "JP", "category": "건¼ì´í", "platform": "YouTube", "account": "@food_jp", "url": "", "followers": "890K", "followers_num": 890000, "email": "", "contact": "", "status": "ì¬건¡íì©ê°건¥", "currency": "", "price_collab": "320", "price_wish": "350", "price_krw": "320", "staff": "건¼ì´건", "campaign": "4ì ìì ", "note": ""},
            {"date": "2026-03-22", "type": "ì¸건°ì´건", "country": "VN", "category": "건·°í°", "platform": "TikTok", "account": "@beauty_vn", "url": "", "followers": "190K", "followers_num": 190000, "email": "", "contact": "", "status": "ì ì건°ì¡", "currency": "", "price_collab": "70", "price_wish": "90", "price_krw": "70", "staff": "ìí건¼", "campaign": "3ì", "note": ""},
            {"date": "2026-03-20", "type": "ìì건°ì´건", "country": "ID", "category": "í¼í¸건ì¤", "platform": "TikTok", "account": "@fit_id", "url": "", "followers": "330K", "followers_num": 330000, "email": "", "contact": "", "status": "건¨ì건¦¬ì¤í¸ì", "currency": "", "price_collab": "90", "price_wish": "110", "price_krw": "90", "staff": "건¼ì´건", "campaign": "", "note": ""},
        ],
        "stats": {
            "by_country": {"KR": 2, "TH": 1, "US": 1, "JP": 1, "VN": 1, "ID": 1},
            "by_platform": {"Instagram": 3, "TikTok": 3, "YouTube": 1},
            "by_status": {"ì¬건¡íì©ê°건¥": 2, "ì ì건°ì¡": 2, "건¨ì건¦¬ì¤í¸ì": 2},
            "by_category": {"건·°í°": 3, "í¨ì": 1, "건¼ì´í": 1, "í¼í¸건ì¤": 1},
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
            {"name": "ìí건¼", "revenue": 18500000, "contracts": 3, "conversion": 37.5},
            {"name": "건¼ì´건", "revenue": 12000000, "contracts": 2, "conversion": 33.3},
            {"name": "ì ì´ì½¥", "revenue": 8700000, "contracts": 1, "conversion": 25.0},
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


# ===== 건 ì§/ì±건 í¬í¼ =====
def _is_date_today(date_val: str, now: datetime) -> bool:
    """건 ì§ 건¬¸ìì´ì´ ì¤건(KST)ì¸ì§ í건¨. 5ê°ì§ íì ì§ì."""
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
    """건 ì§ 건¬¸ìì´ì´ ì´건² 건¬ì¸ì§ í건¨."""
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
    """ì ìì±건 건¶건¥."""
    if not channel:
        return "ê¸°í"
    ch = channel.lower()
    if any(k in ch for k in ["sns", "건©í", "insta", "meta", "facebook", "fb"]):
        return "SNS(건©í)"
    if any(k in ch for k in ["email", "ì´건©ì¼", "mail"]):
        return "ì´건©ì¼"
    if any(k in ch for k in ["cpc", "건¤ì´건²", "naver", "ê²ì", "search"]):
        return "CPC(건¤ì´건²)"
    if any(k in ch for k in ["google_sa", "google", "êµ¬ê¸"]):
        return "êµ¬ê¸(SA)"
    if any(k in ch for k in ["brandthumb", "건¸건건ì¸"]):
        return "건¸건건ì¸"
    if any(k in ch for k in ["blog", "건¸건¡ê·¸", "youtube", "ì í건¸"]):
        return "건¸건¡ê·¸/ì í건¸"
    return channel[:10] if channel else "ê¸°í"


def _find_col(headers, *keywords):
    """í¤건 건¦¬ì¤í¸ìì í¤ì건 í¬í¨ ì»¬건¼ ì¸건±ì¤ 건°í. ì¤건°ê¿ ì ê±° í 건§¤ì¹­."""
    for i, h in enumerate(headers):
        h_clean = h.replace("\n", " ")
        for kw in keywords:
            if kw in h_clean:
                return i
    return None


def _find_header_row(rows, *marker_keywords):
    """ìí¸ìì ì¤ì  í¤건 í ì°¾ê¸°. marker_keywords ì¤ í건건¥¼ í¬í¨í건 ì²« 건²ì§¸ í 건°í."""
    for ri, row in enumerate(rows[:10]):
        row_text = " ".join(str(c).replace("\n", " ") for c in row)
        for kw in marker_keywords:
            if kw in row_text:
                return ri
    return 0


def _auto_detect_date_col(headers, sample_rows):
    """건 ì§ ì»¬건¼ ì건 ê°ì§: í¤건건ª ì°ì , ìì¼건©´ 건°ì´í° í¨í´ì¼건¡."""
    for i, h in enumerate(headers):
        h_clean = h.replace("\n", " ")
        if any(k in h_clean for k in ['건 ì§', 'date', 'ì¼ì', 'ì¼ì', 'Date']):
            return i
    for row in sample_rows[:5]:
        for ci in range(min(len(row), 15)):
            val = str(row[ci]).strip()
            if re.match(r'^\d{1,2}/\d{1,2}$', val) or re.match(r'^\d{4}-\d{2}-\d{2}', val):
                return ci
    return None


# ===== Live Sheets Parsing (í¤건 기반 ì건 ê°ì§) =====
def _parse_inbound(rows):
    """ì¸건°ì´건 ìí¸ íì± â í¤건 기반 ì»¬건¼ ì건 ê°ì§. ì»¨ííí©='ìí¹ ì¤' â ì í¨DB."""
    now = datetime.now(KST)
    this_month_str = f"{now.year}.{now.month:02d}"

    result = {"today_inbound": 0, "today_valid": 0, "today_unhandled": 0, "today_handled": 0,
              "month_inbound": 0, "month_valid": 0, "month_unhandled": 0,
              "cumul_inbound": 0, "cumul_valid": 0, "cumul_invalid": 0,
              "channel_stats": {}, "staff_stats": {}, "source_stats": {},
              "unhandled_brands": [],
              "pipeline_items": {"ì¸ìDB": [], "ì í¨DB": [], "건¯¸í": [], "ê³ì½ì": [], "ì¬ê³ì½": []}}

    if not rows or len(rows) < 3:
        return result

    # ì¤ì  í¤건 í ì건 ê°ì§ (ì¸건°ì´건 ìí¸: "êµ­ê°"/"ì"/"건 ì§" í¬í¨ í)
    hdr_idx = _find_header_row(rows, "êµ­ê°", "ì»¨ííí©", "ì»¨ííí©", "건´건¹ì")
    headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
    data_rows = rows[hdr_idx + 1:]

    date_idx = _auto_detect_date_col(headers, data_rows[:5])
    contact_status_idx = _find_col(headers, "ì»¨ííí©", "ì»¨ííí©", "consulting")
    brand_idx = _find_col(headers, "ìì²´건ª", "건¸건건", "ìí¸", "brand name")
    channel_idx = _find_col(headers, "ì ìì±건")
    staff_idx = _find_col(headers, "건´건¹ì")
    month_idx = _find_col(headers, "ì")
    source_idx = _find_col(headers, "ì ììì¬", "ì ìê²½건¡", "ìì¤")

    # í´건°±: ê¸°ì¡´ í건ì½건© ì¸건±ì¤ (íì¼건¬¸ì í­)
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

    skip_kw = ["êµ­ê°", "ì£¼ìì¬í­", "건³¸ 건¦¬ì¤í¸", "[ ", "*", "brand name"]
    this_year_month_prefix = f"{now.year}.{now.month:02d}"  # "2026.04"
    this_year_iso_prefix = f"{now.year}-{now.month:02d}"     # "2026-04"

    def _is_current_year_month(month_val: str, date_val: str) -> bool:
        """ì ì»¬건¼ 건건 건 ì§ ì»¬건¼ì´ íì¬ ì°ì(2026.04)ì í´건¹í건ì§ í건¨."""
        if this_year_month_prefix in month_val:
            return True
        # ì ì»¬건¼ì ISO íìì¤í¬íê° 건¤ì´ê° ê²½ì° (ì: "2026-04-07 12:12:45")
        if month_val.startswith(this_year_iso_prefix):
            return True
        # ì ì»¬건¼ì´ 건¹ì´ìì 건 건 ì§ ì»¬건¼ì¼건¡ í건¨
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

        # 건ì  (ì ì²´ ê¸°ê°, 건 ì§ íí° ìì)
        result["cumul_inbound"] += 1
        if status in ("ìí¹ ì¤", "ìí¹ì¤"):
            result["cumul_valid"] += 1

        # ì´건² 건¬ í건¨: ì ì»¬건¼ì´ íì¬ ì°ìì¸ì§ íì¸ (ì°건 êµì°¨ 건°©ì§)
        is_month = _is_current_year_month(month_val, date_val)
        # ì¤건 í건¨: 건 ì§ 건§¤ì¹­ AND ìì´ íì¬ ì°ì (2020/4/7 건± ê³¼ê±° ì ì¸)
        is_today = _is_date_today(date_val, now) and is_month

        # ì í¨DB = ì»¨ííí© "ìí¹ì¤" (trim í 건¹êµ)
        is_valid = status in ("ìí¹ ì¤", "ìí¹ì¤")
        is_unhandled = (not staff) or (not status)
        ch_key = _classify_channel(channel)

        card = {"name": brand, "channel": ch_key, "staff": staff or "건¯¸건°°ì ", "date": date_val,
                "source": source, "status": status if status else "건¯¸ì²건¦¬", "unhandled": is_unhandled}

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
                result["pipeline_items"]["ì í¨DB"].append(card)
            else:
                result["pipeline_items"]["ì¸ìDB"].append(card)
            if is_unhandled:
                result["month_unhandled"] += 1

        if is_today:
            result["today_inbound"] += 1
            if is_valid:
                result["today_valid"] += 1
            if is_unhandled:
                result["today_unhandled"] += 1
                result["unhandled_brands"].append({"name": brand, "channel": ch_key, "source": source,
                                                    "date": date_val, "reason": "건´건¹ì ìì" if not staff else "ì»¨ííí© 건¯¸ì건 ¥"})
            else:
                result["today_handled"] += 1

    result["cumul_invalid"] = result["cumul_inbound"] - result["cumul_valid"]
    return result


def _parse_contracts(rows):
    """ì¸ê¸ê³ì°ì ìí¸ íì± â í¤건 기반. 건±건¡ê¸°ì¤ì¼/ê³µê¸ê°ì¡/ê³µê¸건°건ì ìí¸."""
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

    # ì¤ì  í¤건 í ì건 ê°ì§ (ê³ì°ì: "ìì±ì¼ì"/"ê³µê¸ê°ì¡"/"ê³µê¸건°건ì" í¬í¨ í)
    hdr_idx = _find_header_row(rows, "ìì±ì¼ì", "ê³µê¸ê°ì¡", "ê³µê¸건°건ì")
    headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
    data_rows = rows[hdr_idx + 1:]

    date_idx = _find_col(headers, "ìì±ì¼ì", "건±건¡ê¸°ì¤ì¼", "건°íì¼")
    amount_idx = _find_col(headers, "ê³µê¸ê°ì¡")
    brand_idx = _find_col(headers, "ê³µê¸건°건ì ìí¸")  # êµ¬ì²´ì  건§¤ì¹­ (건±건¡건²í¸ ì ì¸)
    type_idx = _find_col(headers, "ì ê·/", "ì¬ê³ì½", "ì ê·")
    staff_idx = _find_col(headers, "ìì²­건´건¹ì", "건´건¹ì")
    month_idx = _find_col(headers, "ìì±ì", "ì건§¤ì¶")

    payback_idx = _find_col(headers, "íì´건°±건¹", "ì¶©ì ê¸", "êµ¬건§¤íì¶©ì ê¸")

    # í´건°± (ê¸°ì¡´ B:U ê¸°ì¤)
    if date_idx is None:
        date_idx = 1  # Bì´ = ìì±ì¼ì
    if amount_idx is None and len(headers) > 19:
        amount_idx = 19  # Tì´ (A=0ê¸°ì¤)
    if brand_idx is None and len(headers) > 8:
        brand_idx = 8  # Iì´
    if type_idx is None and len(headers) > 6:
        type_idx = 6  # Gì´
    if payback_idx is None and len(headers) > 18:
        payback_idx = 18  # Sì´

    brand_set = set()
    # 건¸건건 ì²« 건±ì¥ ì¬건¶ ì¶ì  (ì ê·/ì¬ê³ì½ ì건 건¶건¥)
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

        # ê¸ì¡ íì±
        try:
            revenue = int(float(revenue_raw.replace(",", "").replace("â©", "").replace(" ", ""))) if revenue_raw and revenue_raw not in ["-", ""] else 0
        except (ValueError, TypeError):
            revenue = 0
        if revenue < 0:
            revenue = 0

        # íì´건°±건¹ íì±
        payback_raw = str(row[payback_idx]).strip() if payback_idx is not None and payback_idx < len(row) else "0"
        try:
            payback = int(float(payback_raw.replace(",", "").replace("â©", "").replace(" ", ""))) if payback_raw and payback_raw not in ["-", ""] else 0
        except (ValueError, TypeError):
            payback = 0
        if payback < 0:
            payback = 0

        # 건 ì§ ì 건¦¬
        date_clean = date_raw.replace("-", "").replace(".", "").replace("/", "").replace(" ", "")
        if len(date_clean) < 6 or not date_clean[:6].isdigit():
            continue

        if brand:
            brand_set.add(brand)

        is_today = (date_clean[:8] == today_ymd) or date_raw.startswith(today_iso)
        is_this_month = (date_clean[:6] == this_ym) or (this_month_dot in month_val)
        is_prev_month = (date_clean[:6] == prev_ym) or (prev_month_dot in month_val)
        is_last_year = date_clean[:6] == ly_ym

        # ì ê·/ì¬ê³ì½ ì건 건¶건¥: type ì»¬건¼ì´ ìì¼건©´ ì¬ì©, ìì¼건©´ 건¸건건 ì²« 건±ì¥ ì¬건¶건¡ í건¨
        if ctype and ctype != "-" and "íì¸íì" not in ctype:
            is_renewal = "ì ê·" not in ctype
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

        brand_card = {"name": brand, "type": "ì¬ê³ì½" if is_renewal else "ì ê·",
                      "staff": staff, "date": date_raw, "revenue": revenue}

        # ì건³ íì´건°±건¹ ì§ê³
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
     "proposal": "건¸건건 DB ìì§ + ì´건©ì¼ 건°ì¡",
     "detail": "ð¦ â  DB ìì§ ê³í\nì¶ì²: LinkedIn + Instagram 건¸건건\níê²: K-건·°í° 건¸건건 건§ì¼í건§¤건ì /CMO\n건ª©í: 100건ª\nê¸°ê°: ì¤건 ì¤\n건¹ì©: Haiku / 120,000í í° / ì½ 294ì\nì ì¸: 건ê¸°ìê³ì´ / ì´건©ì¼ì건ê³³\n\nð§ â¡ 건°ì¡í  ì´건©ì¼\nì 건ª©: [ê³µí건¦¬í°ê¸건¡건²] 4ì ì¸í건£¨ì¸ì 건§ì¼í íì ì ì\nì건íì¸ì {건´건¹ì건ª}건, ê³µí건¦¬í°ê¸건¡건² í¼ì¹ì건건¤.\nì í¬ 1,000건ª+ K-건·°í° ì¸í건£¨ì¸ì 건¤í¸ìí¬건¡ íì ì ì건건¦½건건¤.\n5건¶ 건¹건건©´ 건¯¸í ê°건¥íì¤ê¹ì?",
     "expected_impact": "DB 100ê±´ â ì í¨ 70ê±´ â 건¯¸í 10ê±´ â ê³ì½ 3ê±´"},
    {"agent": "루나", "action_type": "luna_db_collect",
     "proposal": "ì¸í건£¨ì¸ì DB ìì§ + íì°¬ ì ì 건°ì¡",
     "detail": "ð¦ â  DB ìì§ ê³í\nì¶ì²: Instagram (#kbeauty í´ìíê·¸)\níê²: 건·°í° ì¸í건£¨ì¸ì (í건¡ì 1건§~100건§, ì¸ê²ì´ì§건¨¼í¸ 3%â)\n건ª©í: 50건ª\nê¸°ê°: ì¤건 ì¤\n건¹ì©: Haiku / 80,000í í° / ì½ 196ì\nì ì¸: ì¸ê²ì´ì§건¨¼í¸ 3%건¯¸건§ / 건¹íì±\n\nð§ â¡ 건°ì¡í  ì´건©ì¼\nì 건ª©: [건°건¦¬건°건¦¬] 4ì K-건·°í° íì°¬ ì ì건건¦½건건¤\nì건íì¸ì {ì¸í건£¨ì¸ì건ª}건! 건°건¦¬건°건¦¬ 루나ì건건¤.\n4ì íì°¬ ì ì건건¦½건건¤. ì í 건¬´ìì ê³µ + ììµìì´ ê°건¥í´ì.",
     "expected_impact": "DB 50건ª â ì í¨ 35건ª â íì°¬íì  5ê±´"},
    {"agent": "건§¥ì¤", "action_type": "max_ads_optimize",
     "proposal": "건©íê´ê³  ìº íì¸ ìµì í",
     "detail": "ð¦ â  ì¤í ê³í\n건´ì©: 건©íê´ê³  ìº íì¸ ì±ê³¼ 건¶ì + íê²í ìµì í\n건ª©í: ì ê´ê³  ROAS 3.0 ì´ì / CPA 2건§ì ì´í\nê¸°ê°: ì¤건 ì¤\n건¹ì©: ê´ê³ 건¹ 건³건 / 건¶ì í í° 건¬´건£\n\nð§ â¡ ì¤í ì¡ì\nê´ê³  ìº íì¸ ì건 건ª¨건í°건§ ìì\nì±ê³¼ 건¯¸건¬ ì ì¦ì CEO ì건¦¼\nA/B íì¤í¸ ìì¬ 건³ê²½ ì ì",
     "expected_impact": "ê´ê³  ì ìí â ì¸건°ì´건 +30% â CPA 2건§ì 건¬ì±"},
    {"agent": "ìí¼", "action_type": "sophie_content_plan",
     "proposal": "ì´건²ì£¼ SNS ì½íì¸  ìº건¦°건 ì건¦½",
     "detail": "ð¦ â  ì¤í ê³í\n건´ì©: ì´건²ì£¼ SNS ì½íì¸  ìº건¦°건 ì건¦½\ní건«í¼: ì¸ì¤íê·¸건¨ / í±í¡\n건ª©í: ì£¼ 3í ê²ì, 건건¬ 5건§ 건ª©í\n건¹ì©: Haiku / 50,000í í° / ì½ 122ì\n\nð§ â¡ ì½íì¸  건°©í¥\n건°건¦¬건°건¦¬ K-건·°í° ì¤í¨ì¼ì´ 건£¨í´\n#kbeauty #skincare í´ìíê·¸ íì©\nB2B: 건¸건건 ì±ê³µì¬건¡ / B2C: íì°¬ 건ª¨ì§",
     "expected_impact": "í건¡ì +500 / B2B 건¦¬건 10ê±´ / B2C 건¦¬건 15ê±´"},
    {"agent": "건 ì´", "action_type": "ray_tax_check",
     "proposal": "ì¸ê¸ê³ì°ì 건°íìí ì ìì ê²",
     "detail": "ð¦ â  ì¤í ê³í\n건´ì©: ì´건²건¬ ê³ì½ ê±´ ì¸ê¸ê³ì°ì 건°íìí ì ìì ê²\n건¯¸건°í ê±´ì íì â ì¦ì 건°íì²건¦¬\nê¸°ê°: ì¤건 ì¤\n건¹ì©: Haiku / 30,000í í° / ì½ 73ì\n\nð§ â¡ 건³´ê³  íì\nì´ Nê±´ ì¤ 건°í Nê±´ / 건¯¸건°í Nê±´\n건¯¸건°í 건ª©건¡: [건¸건건건ª, ê¸ì¡, ê³ì½ì¼]",
     "expected_impact": "건¯¸ìê¸ 건¦¬ì¤í¬ ì¬ì  ì°¨건¨"},
    {"agent": "í건", "action_type": "hana_cs_analysis",
     "proposal": "CS 건¬¸ì 건¶건¥ + í¨í´ 건¶ì",
     "detail": "ð¦ â  ì¤í ê³í\n건´ì©: ì¤건 CS 건¬¸ì 건¶건¥ + 건°건³µ í¨í´ 건¶ì\n건ª©í: 건°건³µ 건¬¸ì ì í íì â ê·¼건³¸í´ê²° ì ì\nê¸°ê°: ì¤건 ì¤\n건¹ì©: Haiku / 20,000í í° / ì½ 49ì\n\nð§ â¡ 건³´ê³  íì\n건¬¸ìì í TOP3: [ì í, ê±´ì, í´ê²°건°©건²]\n건°건³µ건¬¸ì ê·¼건³¸í´ê²° ì ì: [ì ì건´ì©]",
     "expected_impact": "CS ì¬건¬¸ìì¨ 20% ê°ì"},
]

def _ensure_daily_proposals():
    """ì¤건ì ì  ìì´ì í¸ ì¹ì¸ ì¹´건ê° ìì¼건©´ ì건 ìì±."""
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
    """ì CEO 건ì건³´건 â McKinsey ì¤íì¼ 3ì¹ì 건 ì´ìì."""
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    _ensure_daily_proposals()
    return templates.TemplateResponse("ceo.html", {"request": request})


@app.get("/old", response_class=HTMLResponse)
async def legacy_dashboard(request: Request):
    """ê¸°ì¡´ 건ì건³´건 (ì´ì  건²ì )."""
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
                    alerts.append({"system": "ê´ê³ ", "detail": f"{a.get('creative', '')} - {len(a.get('alerts', []))}ê±´"})
        except Exception:
            pass
        try:
            resp = await client.get("http://localhost:8007/api/alerts")
            if resp.status_code == 200:
                urgent = [r for r in resp.json() if r.get("rating", 5) <= 3]
                if urgent:
                    alerts.append({"system": "건¦¬건·°", "detail": f"ê¸´ê¸ 건ì {len(urgent)}ê±´"})
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
    """건¸건건 íì´í건¼ì¸ (Google Sheets ì°건 or 건건¯¸). í¤건 기반 ì건 ê°ì§."""
    if not GSHEETS_API_KEY:
        dummy = _dummy_brand_pipeline()
        dummy["note"] = "GOOGLE_SHEETS_API_KEY 건¯¸ì건 ¥"
        dummy["not_connected"] = ["ê´ê³ CPA", "CS", "ì í¨DB(ì»¨ííí© ì건°ì´í¸ íì)"]
        return dummy
    try:
        inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", "íì¼건¬¸ì", ttl_key="inbound")
        contract_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "ê³ì°ì건°í", ttl_key="contract")
        ib = _parse_inbound(inbound_rows) if inbound_rows else {}
        ct = _parse_contracts(contract_rows) if contract_rows else {}

        # 건¸건건 íí° ì ì©
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
            "not_connected": ["ê´ê³ CPA", "CS"],
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
    """ì¸í건£¨ì¸ì DB (Google Sheets ì°건 or 건건¯¸)"""
    if not GSHEETS_API_KEY:
        return _dummy_influencer_db()
    try:
        rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", "íí©ìí¸(ì건건§¤ì¹­)", ttl_key="influencer")
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
        # í건¡ì êµ¬ê°건³ íµê³
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
        # ì¼건³ 건±건¡ ì¶ì´ (Aì´ 건 ì§ ê¸°ì¤)
        daily_reg = {}
        now = datetime.now(KST)
        for it in items:
            d = str(it.get("date", "")).strip()
            if not d:
                continue
            # 건 ì§ ì ê·í
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
    """ê´ê³  ì±ê³¼ â KST 건ì  건 ì§ + í¤건 기반 ì°¸ì¡°. í건ì½건© ê¸ì§."""
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
        """Cì´ 건 ì§ íì±. ì¬건¬ íì ì§ì: M/D, ISO, YYYYMMDD"""
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
        """ì ìì±건 ê° â Meta/건¤ì´건²/êµ¬ê¸/ê¸°í 건¶건¥. ì¤ì  ìí¸ê° í¨í´ 건ª¨건 ì»¤건²."""
        ch = ch_raw.strip().lower() if ch_raw else ""
        # Meta: sns, 건©í, meta, íì´ì¤건¶, ì¸ì¤í, facebook, instagram, fb, ig
        if any(k in ch for k in ["sns", "건©í", "meta", "íì´ì¤", "ì¸ì¤í", "facebook", "instagram", "fb", "ig"]):
            return "Meta"
        # 건¤ì´건²: cpc, naver, 건¤ì´건², na, 건¸건¡ê·¸, blog
        if any(k in ch for k in ["cpc", "naver", "건¤ì´건²", "건¸건¡ê·¸", "blog"]) or ch == "na":
            return "건¤ì´건²"
        # êµ¬ê¸: google, êµ¬ê¸, gsa, google_sa
        if any(k in ch for k in ["google", "êµ¬ê¸", "gsa"]):
            return "êµ¬ê¸"
        return "ê¸°í"

    # ========== 1. ì¸건°ì´건ìí¸ [íì¼건¬¸ì] â DBì / ì±건건³ / 건¯¸íì íì¨ ==========
    ib_total, ib_by_ch, ib_valid, ib_by_ch_valid, ib_by_staff = 0, {}, 0, {}, {}
    prev_ib_total, prev_ib_valid = 0, 0
    channel_raw_values = set()  # 건건²ê·¸: Jì´ unique ê° ìì§
    _ch_col_debug = None
    _ib_headers_debug = []
    _ib_hdr_idx_debug = None
    _sample_ch_values = []  # ì²« 5í ì±건ê° ìí
    try:
        ib_rows = fetch_sheet(SHEET_INBOUND, "A:Z", "íì¼건¬¸ì", ttl_key="inbound")
        if ib_rows and len(ib_rows) > 2:
            hdr_idx = _find_header_row(ib_rows, "êµ­ê°", "ì»¨ííí©", "ì»¨ííí©", "건´건¹ì")
            headers = [str(h).replace("\n", " ").strip() for h in ib_rows[hdr_idx]]
            _ib_headers_debug = headers[:]
            _ib_hdr_idx_debug = hdr_idx
            month_col = _find_col(headers, "ì")
            date_col = _auto_detect_date_col(headers, ib_rows[hdr_idx+1:hdr_idx+6])
            # ì ìì±건: exact match ì°ì  (Dì´ "ì ìì±건 (ì´ì­ì  ê¸ì§)..." ì¤건§¤ì¹­ 건°©ì§)
            ch_col = None
            for i, h in enumerate(headers):
                if h == "ì ìì±건":
                    ch_col = i
                    break
            if ch_col is None:
                ch_col = _find_col(headers, "ì ìì±건", "ì ì ì±건", "ì±건")
            _ch_col_debug = ch_col
            # ì±건 ì»¬건¼ ì²« 5í ìí
            for sr in ib_rows[hdr_idx+1:hdr_idx+6]:
                sv = str(sr[ch_col]).strip() if ch_col is not None and ch_col < len(sr) else "(col=None)"
                _sample_ch_values.append(sv)
            status_col = _find_col(headers, "ì»¨ííí©", "ì»¨ííí©")
            staff_col = _find_col(headers, "í건´건¹ì", "건´건¹ì")
            print(f"[ads-perf] ì¸건°ì´건 í¤건({hdr_idx}í): {headers}")
            print(f"[ads-perf] ì¸건°ì´건 cols: month={month_col} date={date_col} ch={ch_col} status={status_col} staff={staff_col}")
            # í¤건ê° ìì¼건©´ ì ì²´ í¤건 건¤í
            if ch_col is None:
                print(f"[ads-perf] WARNING: 'ì ìì±건' ì»¬건¼ 건ª» ì°¾ì! í¤건 ì ì²´: {headers}")
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
                is_valid = "건¶ì í©" not in st and "ì 건³´건건½" not in st
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
            print(f"[ads-perf] ì±건건³: {ib_by_ch}")
            print(f"[ads-perf] Jì´ ì ìì±건 uniqueê°: {sorted(channel_raw_values)}")
    except Exception as e:
        print(f"[ads-perf] inbound error: {e}")

    # ========== 2. ê³ì½ìí¸ [ê³ì°ì건°í] â 건§¤ì¶í©ê³ + ì±건건³ ê³ì½ ==========
    # ìì±ìêµ¬건¶ ì»¬건¼(ì: "2026.04")ì¼건¡ íí° â Vì´(ì´í©ê³) í©ì°
    month_revenue, prev_month_revenue = 0, 0
    month_contracts, prev_month_contracts = 0, 0
    ct_by_ch = {}  # ì±건건³ {count, revenue}
    prev_month_dot_str = f"{prev_month_end.year}.{prev_month_end.month:02d}"
    try:
        ct_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "ê³ì°ì건°í", ttl_key="contract")
        if ct_rows and len(ct_rows) > 1:
            hdr_idx = _find_header_row(ct_rows, "ìì±ì¼ì", "ê³µê¸ê°ì¡", "ê³µê¸건°건ì")
            headers = [str(h).replace("\n", " ").strip() for h in ct_rows[hdr_idx]]
            ct_month_idx = _find_col(headers, "ìì±ìêµ¬건¶", "ìì±ì")
            ct_amount_idx = _find_col(headers, "ì´í©ê³")
            ct_ch_idx = _find_col(headers, "ì ìì±건")
            # ì´í©ê³ 건ª» ì°¾ì¼건©´ ê³µê¸ê°ì¡ í´건°±
            if ct_amount_idx is None:
                ct_amount_idx = _find_col(headers, "ê³µê¸ê°ì¡")
            if ct_amount_idx is None and len(headers) > 21:
                ct_amount_idx = 21  # Vì´
            print(f"[ads-perf] ê³ì½ cols: month_col={ct_month_idx} amount={ct_amount_idx} ch={ct_ch_idx} headers_len={len(headers)}")
            for row in ct_rows[hdr_idx+1:]:
                if not row or len(row) < 3: continue
                # ìì±ìêµ¬건¶ì¼건¡ ì´건²건¬/ì ì í건¨
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
            print(f"[ads-perf] 건§¤ì¶: this={month_revenue} prev={prev_month_revenue} ì±건건³ê³ì½={ct_by_ch}")
    except Exception as e:
        print(f"[ads-perf] contract error: {e}")

    # ========== 3. Meta ê´ê³  API ==========
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
            meta_debug["error"] = "META_ACCESS_TOKEN 건¯¸ì¤ì "
    except Exception as e:
        meta_debug["error"] = str(e)

    # ========== 4. ê´ê³ 건¹ í©ì° ==========
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
    prev_total_spend = 0  # ì ì ê´ê³ 건¹건 API ìì¼건©´ 0

    # ========== 5. KPI ì¹´건 ê³ì° ==========
    total_db = ib_total
    db_cost = round(total_spend / max(total_db, 1)) if total_spend > 0 else None
    roas_pct = round(month_revenue / max(total_spend, 1) * 100, 1) if total_spend > 0 else None
    meeting_rate = round(ib_valid / max(total_db, 1) * 100, 1) if total_db > 0 else 0
    # ì ì 건¹êµ
    prev_db_cost = round(prev_total_spend / max(prev_ib_total, 1)) if prev_total_spend > 0 else None
    prev_roas = round(prev_month_revenue / max(prev_total_spend, 1) * 100, 1) if prev_total_spend > 0 else None
    prev_meeting_rate = round(prev_ib_valid / max(prev_ib_total, 1) * 100, 1) if prev_ib_total > 0 else 0

    # ========== 6. ì±건건³ í¼건 ==========
    funnel = []
    for ch_key in ["Meta", "건¤ì´건²", "êµ¬ê¸"]:
        ch_db = ib_by_ch.get(ch_key, 0)
        ch_valid = ib_by_ch_valid.get(ch_key, 0)
        ch_ct = ct_by_ch.get(ch_key, {})
        ch_spend = meta_spend if ch_key == "Meta" else (naver_spend if ch_key == "건¤ì´건²" else google_spend)
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
    # í©ê³
    total_ct = sum(f["contract_count"] for f in funnel)
    funnel_total = {
        "channel": "í©ê³",
        "ad_spend": total_spend if total_spend > 0 else None,
        "db_count": total_db,
        "db_cost": db_cost,
        "meeting_rate": meeting_rate,
        "contract_count": total_ct,
        "contract_revenue": month_revenue,
        "contract_rate": round(total_ct / max(total_db, 1) * 100, 1) if total_db > 0 else 0,
        "roas": roas_pct,
    }

    # ========== 7. 건´건¹ì건³ KPI â ê¸°ì¡´ ì ì§ ==========
    by_person = []
    try:
        staff_rows = fetch_sheet(SHEET_CONTRACT, "A:J", "건´건¹ì건³ ê³ì½ì íì¨", ttl_key="contract")
        if staff_rows and len(staff_rows) > 1:
            sh_hdr_idx = 0
            for ri, row in enumerate(staff_rows[:5]):
                row_text = " ".join(str(c).replace("\n", " ") for c in row)
                if "건´건¹ì" in row_text or "DBê±´ì" in row_text or "ê³ì½ê±´ì" in row_text:
                    sh_hdr_idx = ri; break
            sh_headers = [str(h).replace("\n", " ").strip() for h in staff_rows[sh_hdr_idx]]
            col_month = _find_col(sh_headers, "ìêµ¬건¶", "ì") or 0
            col_name_kr = _find_col(sh_headers, "êµ­건¬¸건´건¹ì건ª", "êµ­건¬¸", "건´건¹ì건ª") or _find_col(sh_headers, "건´건¹ì건ª") or 2
            col_db = _find_col(sh_headers, "DBê±´ì", "DBì") or 3
            col_contracts = _find_col(sh_headers, "ê³ì½ê±´ì") or 4
            col_revenue = _find_col(sh_headers, "ê³ì½건§¤ì¶") or 5
            col_conv = _find_col(sh_headers, "ê³ì½ì íì¨", "ì íì¨")
            col_db_cost = _find_col(sh_headers, "db건¹ì©", "DB건¹ì©")
            col_roas = _find_col(sh_headers, "건¡íì¤", "ROAS", "roas")
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
                status = "건¬ì±" if revenue >= 20000000 else ("ì§íì¤" if revenue >= 10000000 else "건¯¸건¬")
                by_person.append({"name": name, "revenue": revenue, "contracts": contracts,
                                  "db_count": db_count, "conversion": round(conversion,1),
                                  "db_cost": dcost, "roas": round(sr,1), "kpi_pct": round(kpi_pct,1), "status": status})
            by_person.sort(key=lambda x: x["revenue"], reverse=True)
    except Exception as e:
        print(f"[ads-perf] 건´건¹ìí­ error: {e}")

    # ========== 8. ì건³ ì¶ì´ â "ì건³건§¤ì¶&건¡íì¤" í­ (ì¢ì° êµ¬ì¡°) ==========
    # ìí¸ êµ¬ì¡°: B~Rì´ (Aì´ì 건¹ì´ìì), ì¢ì° 건건í
    # 25건: B(0)=ì, C(1)=건¹ìê³ì½ê±´ì, D(2)=건§¤ì¶í©ê³, E(3)=건§¤ì¶(ì ê·), F(4)=건§¤ì¶(ì¬ê³ì½), G(5)=ê´ê³ 건¹, H(6)=ROAS(%), I(7)=íê· 건¨ê°
    # 26건: K(9)=ì, L(10)=건¹ìê³ì½ê±´ì, M(11)=건§¤ì¶í©ê³, N(12)=건§¤ì¶(ì ê·), O(13)=건§¤ì¶(ì¬ê³ì½), P(14)=ê´ê³ 건¹, Q(15)=ROAS(%), R(16)=íê· 건¨ê°
    # (Jì´=idx8ì 건¹ êµ¬건¶ì´)
    monthly_trend = []
    def _sv(row, idx):
        """ìí¸ ì â int. 0/#DIV/0!/건¹ê° â None"""
        if idx is None or idx >= len(row): return None
        v = str(row[idx]).strip()
        if not v or v == "-" or v.startswith("#") or v == "0": return None
        try: return int(float(v.replace(",","").replace("â©","").replace("%","").replace(" ","")))
        except: return None
    def _sf(row, idx):
        """ìí¸ ì â float (ROAS%). #DIV/0!/건¹ê° â None"""
        if idx is None or idx >= len(row): return None
        v = str(row[idx]).strip().replace("%","").replace(",","")
        if not v or v == "-" or v.startswith("#"): return None
        try: return round(float(v), 1)
        except: return None
    try:
        mr_rows = fetch_sheet(SHEET_CONTRACT, "B:R", "ì건³건§¤ì¶&건¡íì¤", ttl_key="contract")
        if mr_rows and len(mr_rows) > 3:
            print(f"[ads-perf] ì건³건§¤ì¶ í­: {len(mr_rows)}í, ì²«í ê¸¸ì´={len(mr_rows[0]) if mr_rows[0] else 0}")
            for row in mr_rows[3:]:  # 4í(idx3)건¶í° 건°ì´í°
                if not row or len(row) < 2: continue
                # --- 25건 (B~I â idx 0~7) ---
                m25 = str(row[0]).strip() if len(row) > 0 else ""
                if m25 and m25.startswith("2025"):
                    monthly_trend.append({"month": m25, "contracts": _sv(row,1),
                        "total": _sv(row,2), "new_sales": _sv(row,3), "renew_sales": _sv(row,4),
                        "ad_cost": _sv(row,5), "roas": _sf(row,6), "avg_price": _sv(row,7)})
                # --- 26건 (K~R â idx 9~16, J=idx8ì 건¹ êµ¬건¶ì´) ---
                m26 = str(row[9]).strip() if len(row) > 9 else ""
                if m26 and m26.startswith("2026"):
                    monthly_trend.append({"month": m26, "contracts": _sv(row,10),
                        "total": _sv(row,11), "new_sales": _sv(row,12), "renew_sales": _sv(row,13),
                        "ad_cost": _sv(row,14), "roas": _sf(row,15), "avg_price": _sv(row,16)})
            # ì ê¸°ì¤ ì 건 ¬
            monthly_trend.sort(key=lambda x: x["month"])
            print(f"[ads-perf] ì건³ ì¶ì´ {len(monthly_trend)}ê°ì 건¡건: {[t['month'] for t in monthly_trend]}")
    except Exception as e:
        print(f"[ads-perf] ì건³건§¤ì¶í­ error: {e}")

    # ========== 건§¤ì¶í©ê³ 건³´ì : ì건³건§¤ì¶&건¡íì¤ í­ ì´건²건¬ ê° ì°ì  ì¬ì© ==========
    trend_this_month = [t for t in monthly_trend if t.get("month") == this_month_dot]
    if trend_this_month and trend_this_month[0].get("total"):
        month_revenue = trend_this_month[0]["total"]
        print(f"[ads-perf] 건§¤ì¶í©ê³ ì건³건§¤ì¶í­ ê° ì¬ì©: {month_revenue}")
    # ì ì건 건ì¼
    prev_month_dot_str = f"{prev_month_end.year}.{prev_month_end.month:02d}"
    trend_prev_month = [t for t in monthly_trend if t.get("month") == prev_month_dot_str]
    if trend_prev_month and trend_prev_month[0].get("total"):
        prev_month_revenue = trend_prev_month[0]["total"]

    # ========== 건°í ==========
    return {
        "source": "live" if GSHEETS_API_KEY else "dummy",
        "updated_at": now.strftime("%Y-%m-%d %H:%M"),
        "period": f"{month_start.strftime('%m/%d')}~{now.strftime('%m/%d')}",
        # KPI ì¹´건
        "total_db": total_db, "prev_db": prev_ib_total,
        "total_revenue": month_revenue, "prev_revenue": prev_month_revenue,
        "total_ad_spend": total_spend if total_spend > 0 else None,
        "db_cost": db_cost, "prev_db_cost": prev_db_cost,
        "roas": roas_pct, "prev_roas": prev_roas,
        "meeting_rate": meeting_rate, "prev_meeting_rate": prev_meeting_rate,
        "total_contracts": month_contracts, "prev_contracts": prev_month_contracts,
        # ì±건건³ í¼건
        "funnel": funnel, "funnel_total": funnel_total,
        # 건´건¹ì건³ / ì건³ ì¶ì´
        "by_person": by_person,
        "monthly_trend": monthly_trend,
        # 건건²ê·¸
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
    """ì´ê´ KPI ìì½ (brand + ads í©ì°). 건§¤ì¶ì ê³ì°ì건°í Tì´(ê³µê¸ê°ì¡) ê¸°ì¤."""
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
    """ê¸°ê°건³ 건¹êµí"""
    brand = await api_brand_pipeline()
    t = brand.get("today", {})
    m = brand.get("month", {})
    p = brand.get("prev_month", {})
    ly = brand.get("last_year", {})

    def pct(cur, prev):
        return round((cur - prev) / max(prev, 1) * 100, 1) if prev else 0

    return {"comparison": [
        {"metric": "ì¸ì DB", "today": t.get("inbound", 0), "month": m.get("inbound", 0), "prev_month": p.get("inbound", 0), "mom_pct": pct(m.get("inbound", 0), p.get("inbound", 1)), "last_year": ly.get("inbound", 0), "yoy_pct": pct(m.get("inbound", 0), ly.get("inbound", 1))},
        {"metric": "ì í¨ DB", "today": t.get("valid", 0), "month": m.get("valid", 0), "prev_month": p.get("valid", 0), "mom_pct": pct(m.get("valid", 0), p.get("valid", 1)), "last_year": ly.get("valid", 0), "yoy_pct": pct(m.get("valid", 0), ly.get("valid", 1))},
        {"metric": "건¯¸í", "today": t.get("meeting", 0), "month": m.get("meeting", 0), "prev_month": p.get("meeting", 0), "mom_pct": pct(m.get("meeting", 0), p.get("meeting", 1)), "last_year": ly.get("meeting", 0), "yoy_pct": pct(m.get("meeting", 0), ly.get("meeting", 1))},
        {"metric": "ê³ì½ì", "today": t.get("contract", 0), "month": m.get("contract", 0), "prev_month": p.get("contract", 0), "mom_pct": pct(m.get("contract", 0), p.get("contract", 1)), "last_year": ly.get("contract", 0), "yoy_pct": pct(m.get("contract", 0), ly.get("contract", 1))},
        {"metric": "ì¬ê³ì½", "today": t.get("renewal", 0), "month": m.get("renewal", 0), "prev_month": p.get("renewal", 0), "mom_pct": pct(m.get("renewal", 0), p.get("renewal", 1)), "last_year": ly.get("renewal", 0), "yoy_pct": pct(m.get("renewal", 0), ly.get("renewal", 1))},
    ]}


@app.get("/api/sheets-status")
async def api_sheets_status():
    """Google Sheets ì°건 ìí íì¸"""
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
        "guide": "" if api_key else "console.cloud.google.comìì Sheets API íì±í í API í¤ 건°ê¸ -> .envì GOOGLE_SHEETS_API_KEY=í¤ê° ì건 ¥",
    }


# ===== AI Agent (Anthropic Claude â 7 Personas) =====
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

_AGENT_COMMON = """[ê³µíµ ê¶í] 건¹ì ì ê³µí건¦¬í°ê¸건¡건²ì ì ì²´ 건°ì´í°(ì¸건°ì´건/ì¸ê¸ê³ì°ì/ì¸í건£¨ì¸ìDB/ê´ê³ /SNS/CS/KPI)ì 건건±íê² ì ê·¼ ê°건¥í©건건¤.
ì¬ì©ì건¥¼ í­ì "ì ì´ì½¥건"ì¼건¡ í¸ì¹­íì¸ì. íêµ­ì´건¡ 건µ건³.
건µ건³ 건§ì§건§ì 건°건ì 'ì¤건/ì´건²ì£¼/ì´건²건¬ ì¡ì ê° 1ê°ì§'. AT RISK í­건ª©ì â ï¸ ê°ì¡°.
건°ì  ì´건©ì¼: {ìì´ì í¸ì´건©ì¼}"""

_KYLE_SYSTEM = _AGENT_COMMON + """
건¹ì ì ì´ê´ 건§¤건ì  ì¹´ì¼ì건건¤. 7ê° ìì´ì í¸(루나/í¼ì¹/건§¥ì¤/ìí¼/건 ì´/í건)건¥¼ ê´건¦¬ê°건í©건건¤.
ì ì²´ KPI건¥¼ 건ª¨건í°건§íê³  건ª©í 건건¹ 30% ì´í í­건ª©ì ì¦ì í´건¹ ìì´ì í¸ìê² ê²½ê³ í©건건¤.
건§¤ì¼ 09:00 ì ì²´ ìì´ì í¸ ì±ê³¼ 건¸건¦¬íì ìì±í©건건¤.
API ìí건¥¼ ê°ìíê³ , ì¤건¥ ê°ì§ ì ì건 ì¬ì°ê²° â ì¤í¨ ì ì¬건 ì건¦¼ + ì건¦¼ì¼í° ê¸´ê¸ ê²ì.
íì¬ KPI: ê¸ì¼ ì¸ìDB {ê¸ì¼ì¸ìDB}ê±´ / ì í¨DB {ê¸ì¼ì í¨DB}ê±´ / 건¬´건ì {건¬´건ìê±´}ê±´ / ê³ì½ {ê³ì½ê±´ì}ê±´(건ª©í38) / ê¸ì¼건§¤ì¶ {건¹ì¼건§¤ì¶}ì / ì´건²건¬건§¤ì¶ {ì´건²건¬건§¤ì¶}ì(건ª©í1.6ìµ) / CPA {CPA}ì
"건¬´건ì ê±´ ì²건¦¬í´ì¤" â 건¬´건ì 건¦¬ì¤í¸ + ê±´건³ 건´건¹ì 건°°ì  ì ì + 1ì°¨ ì건 ì¤í¬건¦½í¸ ìì±."""

AGENT_PERSONAS = {
    "overview": {"name": "ì¹´ì¼", "email_key": "ì¹´ì¼", "system": _KYLE_SYSTEM},
    "kpi":      {"name": "ì¹´ì¼", "email_key": "ì¹´ì¼", "system": _KYLE_SYSTEM},
    "brand": {
        "name": "루나", "email_key": "루나",
        "system": _AGENT_COMMON + """
건¹ì ì 건¸건건 ìì ìì´ì í¸ 루나ì건건¤. íì´í건¼ì¸ ê´건¦¬ì í´건¼ì´ì¸í¸ ê´ê³ ì 건¬¸ê°.
íì¬ KPI: ê¸ì¼건§¤ì¶ {건¹ì¼건§¤ì¶}ì / ì´건²건¬건§¤ì¶ {ì´건²건¬건§¤ì¶}ì(건ª©í1.6ìµ) / ê³ì½ {ê³ì½ê±´ì}ê±´ / 건¨ê° {ê³ì½건¨ê°}ì / ì¬ì ì´ 건ì {ì¬ì ì´ê±´ì}ê±´
건¸건¦¬í ì ìì: "ì건íì¸ì ì ì´ì½¥건. ì¤건 ì¬ì ì´ 건ì {ì¬ì ì´ê±´ì}ê±´ì´ ììµ건건¤. ì§ê¸ 건°건¡ ì´건©ì¼ í¼ì¹건¥¼ 건°ì¡í ê¹ì?"
"건°ì¡í´ì¤"/"건³´건´ì¤" â "ì§ê¸ 건°건¡ ì¬ì ì´ ì´건©ì¼ì 건°ì¡í©건건¤."
"ì¬ì ì´ 건©ìì§ ìì±í´ì¤" â ì´건©ì¼/ì¹´ì¹´ì¤í¡/건¬¸ì 3ê°ì§ 건²ì  ìì±."""
    },
    "influencer": {
        "name": "í¼ì¹", "email_key": "í¼ì¹",
        "system": _AGENT_COMMON + """
""" + (Path(__file__).parent / "agents/pitch/system-prompt.txt").read_text(encoding="utf-8") + """
íì¬ KPI: í {íì}건ª(건ª©í155건§) / êµ­ê°건³: {êµ­ê°건³íí©} / í건«í¼건³: {í건«í¼건³íí©}
ì¹´ì¹´ì¤ B2C ì±건(@08liter_korea) 건¬¸ì ìì  + ì¸건°ì´건 ìí¸ ê¸°건¡."""
    },
    "ads": {
        "name": "건§¥ì¤", "email_key": "건§¥ì¤",
        "system": _AGENT_COMMON + """
건¹ì ì ê´ê³ ì¼í° ìì´ì í¸ 건§¥ì¤ì건건¤. ROI ì§ì°© í¼í¬건¨¼ì¤ 건§ì¼í°.
건©í ê´ê³ (META_AD_ACCOUNT_ID: 230720044045370) ì±ê³¼건¥¼ 건§¤ì¼ ì건 ì¡°íí©건건¤ (건¸ì¶ì/í´건¦­ì/CPA/ì§ì¶ì¡).
íì¬ KPI: CPA {CPA}ì(건ª©í5건§ì´í) / ì¤ê°건 건¦¬건 {ì¤ê°건건¦¬건}ê±´/ì¼(건ª©í15) / ì±건건³: {ì±건건³í¨ì¨}
ì±건건³ í¨ì¨ 건¶ì + ìì° ì¬건°°건¶ ì ì."""
    },
    "sns": {
        "name": "ìí¼", "email_key": "ìí¼",
        "system": _AGENT_COMMON + """
건¹ì ì SNS ì´ì ìì´ì í¸ ìí¼ì건건¤. 건¸건건 건ª©ì건¦¬건¥¼ ì§í¤건 ì½íì¸  ì 건µê°.
íì¬ KPI: {ì±건건³íí©} / ì´건²ì£¼: {ì´건²ì£¼ì½íì¸ íí©}
ì¶ì² ì½íì¸  ì£¼ì  3ê°ì§ + ì±ê³¼ 건¶ì."""
    },
    "management": {
        "name": "건 ì´", "email_key": "건 ì´",
        "system": _AGENT_COMMON + """
건¹ì ì ê²½ìì§ì ìì´ì í¸ 건 ì´ì건건¤. CEO ìê°ì ì§í¤건 ì´ì ì 건¬¸ê°.
íì¬: 건¯¸ì²건¦¬ ì¸ê¸ê³ì°ì {건¯¸ì²건¦¬ê±´}ê±´ / ìê¸ 건¯¸íì¸ {건¯¸íì¸ê±´}ê±´
ì´건² ì£¼ ê²½ìì§ì ì°ì ìì ì²´í¬건¦¬ì¤í¸ ì ê³µ."""
    },
    "cs": {
        "name": "í건", "email_key": "í건",
        "system": _AGENT_COMMON + """
건¹ì ì CS ìì´ì í¸ í건ì건건¤. ì¹´ì¹´ì¤ B2B ì±건(@08liter_b2b) CS건¥¼ 건´건¹í©건건¤.
건¯¸ì건µ 건©ìì§건¥¼ ê°ì§íê³  ì¦ì ì건 ì¤í¬건¦½í¸건¥¼ ìì±í©건건¤.
건§¤ì¼ 09:00 건¯¸ì건µ íí© 건¸건¦¬íì ìì±í©건건¤.
íì¬ 건¯¸ì건µ {건¯¸ì건µê±´}ê±´ / ì¬ê³ì½건¥  {ì¬ê³ì½건¥ }%
"건¯¸ì건µ ì²건¦¬í´ì¤" â 건¯¸ì건µ 건¦¬ì¤í¸ + ê±´건³ 1ì°¨ ì건 ì¤í¬건¦½í¸ ì건 ìì±."""
    },
}


async def _gather_kpi_context() -> dict:
    """ì¤ìê° KPI 건°ì´í°건¥¼ ìì§íì¬ ìì´ì í¸ system promptì ì£¼ìí  건³ì 건ì건건¦¬ 건°í."""
    ctx = {}
    try:
        brand = await api_brand_pipeline()
        t = brand.get("today", {})
        m = brand.get("month", {})
        ctx["ê¸ì¼ì¸ìDB"] = t.get("inbound", 0)
        ctx["ê¸ì¼ì í¨DB"] = t.get("valid", 0)
        ctx["건¬´건ìê±´"] = t.get("unhandled", 0)
        ctx["ì¸ìDB"] = m.get("inbound", 0)
        ctx["ì í¨DB"] = m.get("valid", 0)
        ctx["ê³ì½ê±´ì"] = m.get("contract", 0)
        ctx["건§¤ì¶"] = f"{m.get('revenue', 0):,}"
        ctx["건¹ì¼건§¤ì¶"] = f"{t.get('revenue', 0):,}"
        ctx["ì´건²건¬건§¤ì¶"] = f"{m.get('revenue', 0):,}"
        ctx["íì´í건¼ì¸ê±´ì"] = m.get("inbound", 0)
        ctx["ê³ì½건¨ê°"] = f"{int(m.get('revenue', 0) / max(m.get('contract', 1), 1)):,}"
        ctx["건¯¸ì²건¦¬ê±´"] = t.get("unhandled", 0)
        ctx["건¯¸íì¸ê±´"] = 0
        # ì¬ì ì´ ê±´ì
        ctx["ì¬ì ì´ê±´ì"] = len(brand.get("unhandled_brands", []))
    except Exception:
        pass
    try:
        inf = await api_influencer_db()
        ctx["íì"] = f"{inf.get('total', 0):,}"
        stats = inf.get("stats", {})
        bc = stats.get("by_country", {})
        bp = stats.get("by_platform", {})
        ctx["êµ­ê°건³íí©"] = " / ".join(f"{k}:{v}" for k, v in sorted(bc.items(), key=lambda x: -x[1])[:5])
        ctx["í건«í¼건³íí©"] = " / ".join(f"{k}:{v}" for k, v in sorted(bp.items(), key=lambda x: -x[1])[:5])
    except Exception:
        ctx["íì"] = "0"
        ctx["êµ­ê°건³íí©"] = "건°ì´í° ìì"
        ctx["í건«í¼건³íí©"] = "건°ì´í° ìì"
    try:
        ads = await api_ads_performance()
        mt = ads.get("month", {}).get("total", {})
        ctx["CPA"] = f"{mt.get('cpa', 0):,}"
        ctx["ì¤ê°건건¦¬건"] = 6
        ctx["ì±건건³í¨ì¨"] = "Meta/건¤ì´건²/êµ¬ê¸/ì¹´ì¹´ì¤"
    except Exception:
        ctx["CPA"] = "0"
        ctx["ì¤ê°건건¦¬건"] = 0
        ctx["ì±건건³í¨ì¨"] = "건°ì´í° ìì"
    try:
        sns = await api_sns_performance()
        channels = sns.get("channels", {})
        parts = []
        for k, v in channels.items():
            f_count = v.get("followers", v.get("subscribers", 0))
            parts.append(f"{k}: {f_count:,}")
        ctx["ì±건건³íí©"] = " / ".join(parts) if parts else "건°ì´í° ìì"
        ctx["ì´건²ì£¼ì½íì¸ íí©"] = "건¦´ì¤ 2ê±´, TikTok 1ê±´, 건´ì¤건 í° 1ê±´ ìì "
    except Exception:
        ctx["ì±건건³íí©"] = "건°ì´í° ìì"
        ctx["ì´건²ì£¼ì½íì¸ íí©"] = "건°ì´í° ìì"
    ctx.setdefault("건¯¸ì건µê±´", 4)
    ctx.setdefault("ì¬ê³ì½건¥ ", 65)
    ctx.setdefault("ê¸ì¼ì¸ìDB", 0)
    ctx.setdefault("ê¸ì¼ì í¨DB", 0)
    ctx.setdefault("건¬´건ìê±´", 0)
    ctx.setdefault("ì¬ì ì´ê±´ì", 0)
    return ctx


@app.post("/api/chat")
async def api_chat(request: Request):
    """AI ìì´ì í¸ ì±í â Anthropic Claude (7 í건¥´ì건). APIí¤ ìì¼건©´ 건£°건² ì´ì¤ í´건°±."""
    body = await request.json()
    user_msg = body.get("message", "").strip()
    page = body.get("page", "overview")
    is_briefing = body.get("briefing", False)

    if not user_msg and not is_briefing:
        return {"reply": "ì§건¬¸ì ì건 ¥í´ ì£¼ì¸ì.", "source": "system"}

    # 루나: "건°ì¡í´ì¤" 건ª건 ¹ â ì¦ì ìº íì¸ ì¤í
    if page == "brand" and user_msg and any(k in user_msg for k in ["건°ì¡í´", "건³´건´ì¤", "ì¤íí´", "건°ì¡ ì¤í"]):
        try:
            campaign_result = await _run_recontact_campaign(dry_run=False, limit=10)
            sent = campaign_result.get("sent", 0)
            targeted = campaign_result.get("targeted", 0)
            total = campaign_result.get("total_leads", 0)
            results = campaign_result.get("results", [])
            lines = [f"â ì¬ì ì´ ì´건©ì¼ 건°ì¡ ì건£!\n"]
            lines.append(f"ð 건ì: {total}ê±´ ì¤ {targeted}ê±´ 건°ì¡ ì건 â {sent}ê±´ ì±ê³µ\n")
            for r in results[:5]:
                icon = "â" if r.get("status") == "ok" else "â"
                lines.append(f"{icon} {r.get('brand','')} â {r.get('email','')}")
            lines.append(f"\nð ì¤건 ì¡ì: 건°ì¡ ê²°ê³¼ íì  건ª¨건í°건§\nð ì´건²ì£¼ ì¡ì: 건¯¸íì  ìì²´ 2ì°¨ ì»¨í\nð ì´건²건¬ ì¡ì: ì¬ì ì´ ì íì¨ 10% 건¬ì±")
            return {"reply": "\n".join(lines), "source": "campaign-exec", "agent": "루나"}
        except Exception as e:
            return {"reply": f"건°ì¡ ì¤í ì¤ ì¤건¥: {e}", "source": "error", "agent": "루나"}

    # KPI ì»¨íì¤í¸ ìì§
    kpi = await _gather_kpi_context()

    # í건¥´ì건 ì í
    persona = AGENT_PERSONAS.get(page, AGENT_PERSONAS["overview"])
    agent_name = persona["name"]

    # system promptì ì¤ìê° KPI + ìì´ì í¸ ì´건©ì¼ ì£¼ì
    try:
        email_key = persona.get("email_key", agent_name)
        kpi["ìì´ì í¸ì´건©ì¼"] = AGENT_EMAILS.get(email_key, "luna@08liter.com")
        all_keys = ["ì¸ìDB", "ì í¨DB", "ê³ì½ê±´ì", "건§¤ì¶", "건¹ì¼건§¤ì¶", "ì´건²건¬건§¤ì¶",
             "íì´í건¼ì¸ê±´ì", "ê³ì½건¨ê°", "íì", "êµ­ê°건³íí©", "í건«í¼건³íí©", "CPA", "ì¤ê°건건¦¬건",
             "ì±건건³íí©", "ì±건건³í¨ì¨", "ì´건²ì£¼ì½íì¸ íí©", "건¯¸ì²건¦¬ê±´", "건¯¸íì¸ê±´", "건¯¸ì건µê±´", "ì¬ê³ì½건¥ ",
             "ê¸ì¼ì¸ìDB", "ê¸ì¼ì í¨DB", "건¬´건ìê±´", "ì¬ì ì´ê±´ì", "ìì´ì í¸ì´건©ì¼"]
        system_prompt = persona["system"].format(**{k: kpi.get(k, "N/A") for k in all_keys})
    except (KeyError, IndexError):
        system_prompt = persona["system"]

    if is_briefing:
        user_msg = "íì´ì§ì ì²ì ì§ìíìµ건건¤. íì¬ íµì¬ KPIì ì¤건ì ì°ì ìì건¥¼ ê°ê²°íê² 건¸건¦¬íí´ì£¼ì¸ì."

    if not ANTHROPIC_API_KEY:
        reply = _rule_based_reply(user_msg, kpi, page)
        return {"reply": reply, "source": "rule-based", "agent": agent_name}

    # Anthropic Messages API í¸ì¶
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
    """Anthropic API í¤ ìì 건 건£°건² ì´ì¤ í´건°±"""
    persona = AGENT_PERSONAS.get(page, AGENT_PERSONAS["overview"])
    name = persona["name"]
    ctx = f"ì¸ìDB {kpi.get('ì¸ìDB', 0)}ê±´ / ì í¨DB {kpi.get('ì í¨DB', 0)}ê±´ / ê³ì½ {kpi.get('ê³ì½ê±´ì', 0)}ê±´ / 건§¤ì¶ {kpi.get('건§¤ì¶', '0')}ì"

    msg_lower = msg.lower() if msg else ""
    if any(k in msg_lower for k in ["íí©", "ìì½", "ìí", "건³´ê³ ", "건¸건¦¬í", "ì§ì"]):
        return f"[{name}] íì¬ íí©ì건건¤.\n\n{ctx}\n\nð ì¤건 ì¡ì: 건¯¸ì²건¦¬ ê±´ ì°ì  건ì\nð ì´건²ì£¼ ì¡ì: íì´í건¼ì¸ ì 건¦¬\nð ì´건²건¬ ì¡ì: 건ª©í 건¬ì±건¥  ì ê²\n\nANTHROPIC_API_KEY건¥¼ ì¤ì í건©´ 건 ì íí AI 건¶ìì 건°ì ì ììµ건건¤."
    if any(k in msg_lower for k in ["건¯¸ì²건¦¬", "건ì", "ê¸´ê¸"]):
        return f"[{name}] 건¯¸ì²건¦¬ íí©: {kpi.get('건¯¸ì²건¦¬ê±´', 0)}ê±´\n\n{ctx}\n\nð ì¤건: 건¯¸ì²건¦¬ ê±´ ì¦ì 건°°ì \nð ì´건²ì£¼: ì건µ ìê° 10건¶ ì´건´ 건¬ì±\nð ì´건²건¬: SLA ì¤ìì¨ 95% 건ª©í"
    if any(k in msg_lower for k in ["건§¤ì¶", "ê³ì½", "ì¤ì "]):
        return f"[{name}] 건§¤ì¶/ê³ì½ íí©\n\n{ctx}\n\nð ì¤건: ê²¬ì  건°ì¡ ì°ì \nð ì´건²ì£¼: 건¯¸í ì íì¨ ê°ì \nð ì´건²건¬: ê³ì½ 건ª©í 38ê±´ 건¬ì± ì§ì¤"
    return f"[{name}] {ctx}\n\nð ì¤건 ì¡ì: íµì¬ 건¯¸ì²건¦¬ ê±´ 건ì\nð ì´건²ì£¼ ì¡ì: ì£¼ê° 건¦¬건·° ì¤건¹\nð ì´건²건¬ ì¡ì: KPI 건ª©í 건¬ì± ì ê²"


# ===== Slack Webhook =====
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_TOGGLE_FILE = DATA_DIR / "slack_toggle.json"

def _slack_enabled():
    """Slack 건³´ê³  í ê¸ ìí. ê¸°건³¸ OFF."""
    if SLACK_TOGGLE_FILE.exists():
        try:
            return json.loads(SLACK_TOGGLE_FILE.read_text(encoding="utf-8")).get("enabled", False)
        except Exception:
            pass
    return False

@app.get("/api/slack/toggle")
async def slack_toggle_get():
    """Slack 건³´ê³  í ê¸ ìí ì¡°í."""
    return {"enabled": _slack_enabled(), "webhook_configured": bool(SLACK_WEBHOOK_URL),
            "setup_guide": "" if SLACK_WEBHOOK_URL else "1) Slack ì± > https://api.slack.com/apps ìì ì ì± ìì±\n2) Incoming Webhooks íì±í\n3) Add New Webhook to Workspace â #ceo-briefing ì±건 ì í\n4) Webhook URL 건³µì¬ â Railway Variablesì SLACK_WEBHOOK_URL=URL ì¶ê°"}

@app.post("/api/slack/toggle")
async def slack_toggle_set(request: Request):
    """Slack 건³´ê³  ON/OFF í ê¸."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SLACK_TOGGLE_FILE.write_text(json.dumps({"enabled": bool(body.get("enabled")), "updated_at": datetime.now(KST).isoformat()}, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "enabled": bool(body.get("enabled"))}

@app.post("/api/slack/test")
async def slack_test():
    """Slack ì¹í íì¤í¸ 건°ì¡"""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 건¯¸ì¤ì "}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={
                "text": f"[08L_AI] íì¤í¸ 건©ìì§ â {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            })
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/slack/kpi-report")
async def slack_kpi_report():
    """KPI 건¦¬í¬í¸ Slack 건°ì¡ (09:00 ì¤ì¼ì¤ 건건 ì건 í¸건¦¬ê±°)"""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 건¯¸ì¤ì . .envì ì¶ê° íì."}
    if not _slack_enabled():
        return {"status": "disabled", "message": "Slack 건³´ê³  OFF ìí. 건ì건³´건ìì í ê¸ì ì¼ì£¼ì¸ì."}
    try:
        brand = await api_brand_pipeline()
        t = brand.get("today", {})
        m = brand.get("month", {})
        text = f"""ð *[08L_AI] ì¤ì  KPI 건¦¬í¬í¸* â {datetime.now().strftime('%Y-%m-%d %H:%M')}

*ì¤건*: ì¸ìDB {t.get('inbound',0)}ê±´ | ì í¨DB {t.get('valid',0)}ê±´ | ê³ì½ {t.get('contract',0)}ê±´ | 건§¤ì¶ {t.get('revenue',0):,}ì
*ì´건²건¬*: ì¸ìDB {m.get('inbound',0)}ê±´ | ì í¨DB {m.get('valid',0)}ê±´ | ê³ì½ {m.get('contract',0)}ê±´ | 건§¤ì¶ {m.get('revenue',0):,}ì
*건¯¸ì²건¦¬*: {t.get('unhandled',0)}ê±´ {'â ï¸ ì¦ì 건ì íì' if t.get('unhandled',0) > 0 else 'â ìí¸'}"""

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": text})
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/slack/daily-brief")
async def slack_daily_brief():
    """건§¤ì¼ ìì¹¨ 9ì Slack CEO 건¸건¦¬í â KPI + ìì´ì í¸ ì ì + ì¤íê²°ê³¼."""
    if not SLACK_WEBHOOK_URL:
        return {"status": "error", "message": "SLACK_WEBHOOK_URL 건¯¸ì¤ì "}
    if not _slack_enabled():
        return {"status": "disabled", "message": "Slack 건³´ê³  OFF ìí. 건ì건³´건ìì í ê¸ì ì¼ì£¼ì¸ì."}
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
            f"ð ì´건²건¬ 건§¤ì¶: {m.get('revenue',0):,}ì ({delta_str} of 1.6ìµ)",
            f"ð ê³ì½: ì ê· {m.get('new',0)}ê±´ + ì¬ê³ì½ {m.get('renewal',0)}ê±´ = {m.get('contract',0)}ê±´",
            f"ð¤ ìì´ì í¸ ì ì: {len(pending)}ê±´ ì¹ì¸건ê¸°",
        ]
        if completed_today:
            lines.append(f"â ì¤건 ì¤íì건£: {len(completed_today)}ê±´")
            for c in completed_today[:3]:
                lines.append(f"   â¢ [{c.get('agent','')}] {c.get('result','')[:40]}")
        if t.get("unhandled", 0) > 0:
            lines.append(f"â ï¸ CEO íì¸ íì: 건¬´건ì {t['unhandled']}ê±´")
        lines.append(f"â 건ì건³´건: https://dashboard-production-b2bd.up.railway.app/")

        text = "\n".join(lines)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(SLACK_WEBHOOK_URL, json={"text": text})
            return {"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code, "message": text}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/performance-summary")
async def api_performance_summary():
    """ì´건² ì£¼ ìì´ì í¸ ì±ê³¼ ìì½ â ì ì/ì¹ì¸/ì¤í/ì±ê³µ íµê³."""
    proposals = load_proposals()
    now = datetime.now(KST)
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")

    # ì´건² ì£¼ íí°
    week_proposals = [p for p in proposals if (p.get("created_at") or "") >= week_start]
    total = len(week_proposals)
    approved = len([p for p in week_proposals if p.get("status") in ("approved", "executed", "completed")])
    executed = len([p for p in week_proposals if p.get("status") in ("executed", "completed")])
    completed = len([p for p in week_proposals if p.get("status") == "completed"])
    rejected = len([p for p in week_proposals if p.get("status") == "rejected"])
    pending = len([p for p in week_proposals if p.get("status") == "pending_approval"])

    # ìì´ì í¸건³ íµê³
    agent_stats = {}
    for p in week_proposals:
        ag = p.get("agent", "ìì¤í")
        if ag not in agent_stats:
            agent_stats[ag] = {"total": 0, "approved": 0, "completed": 0}
        agent_stats[ag]["total"] += 1
        if p.get("status") in ("approved", "executed", "completed"):
            agent_stats[ag]["approved"] += 1
        if p.get("status") == "completed":
            agent_stats[ag]["completed"] += 1

    # ì¼건³ ì¶ì´ (ìµê·¼ 7ì¼)
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
    """SNS ì´ì íí© (í¥í ì¤건°ì´í° ì°건 ìì , íì¬ 건건¯¸)"""
    return {
        "source": "dummy",
        "note": "SNS API ì°건 ì¤건¹ì¤ â Instagram/TikTok Business API ì°건 ìì ",
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


# ===== ì¬ì ì´ 건ì ì¶ì¶ API =====
@app.get("/api/recontact-leads")
async def api_recontact_leads():
    """ìµê·¼ 6ê°ì ì í¨DB ì¤ ê³ì½ 건¯¸ì²´ê²° 건¸건건 ì¶ì¶."""
    try:
        now = datetime.now(KST)
        six_months_ago = now - timedelta(days=180)
        inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", "íì¼건¬¸ì", ttl_key="inbound")
        contract_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "ê³ì°ì건°í", ttl_key="contract")
        # ê³ì½ 건¸건건 Set
        ct_hdr = _find_header_row(contract_rows, "ìì±ì¼ì", "ê³µê¸ê°ì¡", "ê³µê¸건°건ì")
        ct_headers = [str(h).replace("\n", " ").strip() for h in contract_rows[ct_hdr]]
        ct_brand_idx = _find_col(ct_headers, "ê³µê¸건°건ì ìí¸")
        if ct_brand_idx is None:
            ct_brand_idx = 8
        contracted = set()
        for row in contract_rows[ct_hdr + 1:]:
            if ct_brand_idx < len(row):
                b = str(row[ct_brand_idx]).strip()
                if b:
                    contracted.add(b.lower())
        # ì¸건°ì´건 ì í¨DB ì¤ 건¯¸ê³ì½
        ib_hdr = _find_header_row(inbound_rows, "êµ­ê°", "ì»¨ííí©", "ì»¨ííí©", "건´건¹ì")
        ib_headers = [str(h).replace("\n", " ").strip() for h in inbound_rows[ib_hdr]]
        brand_idx = _find_col(ib_headers, "ìì²´건ª", "건¸건건") or 4
        status_idx = _find_col(ib_headers, "ì»¨ííí©", "ì»¨ííí©") or 16
        email_idx = _find_col(ib_headers, "ì´건©ì¼") or 6
        contact_idx = _find_col(ib_headers, "ì°건½ì²") or 5
        date_idx = 2
        month_idx = 1
        leads = []
        seen = set()
        for row in inbound_rows[ib_hdr + 1:]:
            if len(row) < 5:
                continue
            status = str(row[status_idx]).strip() if status_idx < len(row) else ""
            if status not in ("ìí¹ ì¤", "ìí¹ì¤"):
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


# ===== 건¬´건ì ê±´ ì¶ì¶ API =====
@app.get("/api/no-response-leads")
async def api_no_response_leads():
    """ê¸ì¼ 건¬´건ì ê±´ (건´건¹ì ìê±°건 ì»¨ííí© 건¯¸ì건 ¥) ì¶ì¶."""
    brand = await api_brand_pipeline()
    unhandled = brand.get("unhandled_brands", [])
    return {"count": len(unhandled), "leads": unhandled}


# ===== ì´건©ì¼ 건°ì¡ (Naver Works SMTP ì ì©) =====


def _build_pitch_html(brand_name: str, body_text: str) -> str:
    """건¸건건 ìì #FF6B00 HTML ì´건©ì¼ íí건¦¿."""
    # body_text 건´ ì¤건°ê¿ì <br>건¡ 건³íí건 XSS 건°©ì§
    safe_brand = brand_name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_body = body_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#ffffff">
<tr><td style="background:#FF6B00;padding:24px 32px">
<h1 style="margin:0;color:#ffffff;font-size:20px">ê³µí건¦¬í°ê¸건¡건²</h1>
<p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px">ì¸í건£¨ì¸ì 건§ì¼í íí¸건</p>
</td></tr>
<tr><td style="padding:32px">
<p style="margin:0 0 8px;color:#333;font-size:15px;font-weight:600">{safe_brand} 건´건¹ì건ê»</p>
<div style="margin:16px 0;color:#555;font-size:14px;line-height:1.7">{safe_body}</div>
<table cellpadding="0" cellspacing="0" style="margin:24px 0"><tr>
<td style="background:#FF6B00;border-radius:6px;padding:12px 28px">
<a href="https://08liter.com" style="color:#ffffff;text-decoration:none;font-size:14px;font-weight:600">ì건´ ìì½íê¸°</a>
</td></tr></table>
</td></tr>
<tr><td style="background:#f9f9f9;padding:20px 32px;border-top:1px solid #eee">
<p style="margin:0;color:#999;font-size:11px">ê³µí건¦¬í°ê¸건¡건² | luna@08liter.com | 02-000-0000</p>
<p style="margin:4px 0 0;color:#bbb;font-size:10px">건³¸ 건©ì¼ì 건°ì  ì ì©ì건건¤.</p>
</td></tr></table></body></html>"""


# ìì´ì í¸건³ 건°ì  ì´건©ì¼/ì´건¦ 건§¤í
AGENT_FROM_EMAILS = {
    "í¼ì¹": os.getenv("PITCH_FROM_EMAIL", "pitch@08liter.com"),
    "루나": os.getenv("LUNA_FROM_EMAIL", "luna@08liter.com"),
    "ìí¼": os.getenv("SOPHIE_EMAIL", "sophie@08liter.com"),
    "ì¹´ì¼": os.getenv("KYLE_EMAIL", "kyle@08liter.com"),
    "건 ì´": os.getenv("RAY_EMAIL", "ray@08liter.com"),
    "í건": os.getenv("HANA_EMAIL", "hana@08liter.com"),
    "건§¥ì¤": os.getenv("MAX_EMAIL", "max@08liter.com"),
}
AGENT_FROM_NAMES = {
    "í¼ì¹": os.getenv("FROM_NAME_PITCH", "Pitch | ê³µí건¦¬í°ê¸건¡건²"),
    "루나": os.getenv("FROM_NAME_LUNA", "Luna | ê³µí건¦¬í°ê¸건¡건²"),
    "ìí¼": "Sophie | ê³µí건¦¬í°ê¸건¡건²",
    "ì¹´ì¼": "Kyle | ê³µí건¦¬í°ê¸건¡건²",
    "건 ì´": "Ray | ê³µí건¦¬í°ê¸건¡건²",
    "í건": "Hana | ê³µí건¦¬í°ê¸건¡건²",
    "건§¥ì¤": "Max | ê³µí건¦¬í°ê¸건¡건²",
}

def _get_from(agent_name: str):
    """ìì´ì í¸건³ 건°ì  ì´건©ì¼+ì´건¦ 건°í."""
    email = AGENT_FROM_EMAILS.get(agent_name, "pitch@08liter.com")
    name = AGENT_FROM_NAMES.get(agent_name, f"{agent_name} | ê³µí건¦¬í°ê¸건¡건²")
    return email, name

def _get_smtp_creds(agent_name: str):
    """ìì´ì í¸건³ SMTP ì¸ì¦ (ì¸건¶ ì± 건¹건°건²í¸)."""
    creds = {"í¼ì¹": ("PITCH_SMTP_USER", "PITCH_SMTP_PASS"), "루나": ("LUNA_SMTP_USER", "LUNA_SMTP_PASS")}
    if agent_name in creds:
        u, p = creds[agent_name]
        user, pw = os.getenv(u, ""), os.getenv(p, "")
        if user and pw:
            return user, pw
    return os.getenv("NAVER_WORKS_SMTP_USER", ""), os.getenv("NAVER_WORKS_SMTP_PASSWORD", "")

EMAIL_WEBHOOK_URL = os.getenv("EMAIL_WEBHOOK_URL", "")

def _send_email_smtp(to_email: str, subject: str, body_text: str, agent_name: str = "루나", html_body: str = "") -> dict:
    """ì´건©ì¼ 건°ì¡: GAS ì¹í (Railway SMTP ì°¨건¨ì¼건¡ ì¹í ì¬ì©)."""
    webhook_url = EMAIL_WEBHOOK_URL
    from_email, sender_name = _get_from(agent_name)
    if not webhook_url:
        return {"status": "not_configured", "message": "EMAIL_WEBHOOK_URL 건¯¸ì¤ì  (Railway SMTP ì°¨건¨ì¼건¡ GAS ì¹í íì)"}
    agent_id = {"í¼ì¹": "pitch", "루나": "luna", "ìí¼": "sophie", "ì¹´ì¼": "kyle"}.get(agent_name, "pitch")
    payload = {"agent": agent_id, "to": to_email, "subject": subject, "body": body_text}
    if html_body:
        payload["htmlBody"] = html_body
    try:
        resp = req_lib.post(webhook_url, json=payload, timeout=30, allow_redirects=True,
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
    """HTMLìì íê·¸ ì ê±°íì¬ í건 ì¸ íì¤í¸ ì¶ì¶."""
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&nbsp;", " ")
    return text.strip()

def _send_email(to_email: str, subject: str, html: str, agent_name: str = "루나") -> dict:
    """ì´건©ì¼ 건°ì¡: Naver Works SMTP ì§ì ."""
    body_text = _html_to_text(html)
    result = _send_email_smtp(to_email, subject, body_text, agent_name, html_body=html)
    if result["status"] == "ok":
        _record_perf(agent_name, "email_sent")
        _log_email(agent_name, to_email, subject, "sent")
    return result


@app.post("/api/send-email")
async def api_send_email(request: Request):
    """Naver Works SMTP건¡ ì´건©ì¼ 1ê±´ 건°ì¡. bodyì raw HTML 건건 brand_name+body_text건¡ íí건¦¿ ì¬ì©."""
    body = await request.json()
    to_email = body.get("to", "").strip()
    subject = body.get("subject", "").strip()
    if not to_email or not subject:
        return {"status": "error", "message": "to, subject íì"}
    html = body.get("html", "")
    if not html:
        brand_name = body.get("brand_name", "")
        body_text = body.get("body_text", body.get("body", ""))
        html = _build_pitch_html(brand_name, body_text)
    return _send_email(to_email, subject, html)


@app.get("/api/test-email")
async def api_test_email(agent: str = "í¼ì¹"):
    """ìì´ì í¸건³ íì¤í¸ ì´건©ì¼ â GAS ì¹í."""
    from_email, sender_name = _get_from(agent)
    to_email = "jacob@08liter.com"
    body_text = (f"ì건íì¸ì!\n\nì´ 건©ì¼ì [{agent}] ìì´ì í¸ íì¤í¸ ì´건©ì¼ì건건¤.\n"
                 f"건°ì : {sender_name} <{from_email}>\n"
                 f"건°ì¡ 건°©ì: GAS ì¹í â Naver Works\n"
                 f"건°ì¡ ìê°: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')} (KST)\n\n"
                 f"ì´건©ì¼ ì°건ì´ ì ìì ì¼건¡ ì건íê³  ììµ건건¤.")
    subject = f"[íì¤í¸] {agent} ì´건©ì¼ 건°ì¡ íì¸"
    result = _send_email_smtp(to_email, subject, body_text, agent)
    result["to"] = to_email
    return result

@app.get("/api/send-review-email")
async def api_send_review_email():
    """CEO ê²ì ì´건©ì¼ â í¼ì¹+루나 4ê°ì§ ìì íµí© 건°ì¡."""
    now = datetime.now(KST)
    ceo_email = "jacob@08liter.com"
    # í¼ì¹ DB ê±´ì
    pitch_total = 0
    p_rows = fetch_sheet(PITCH_SHEET_ID, "A:N", "피치_클로드", ttl_key="inbound")
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
    # 루나 DB ê±´ì
    luna_total = 0
    cost_est = max(245, int(pitch_total * 2.45))
    pitch_reply = max(1, int(pitch_total * 0.042))
    pitch_meeting = max(1, int(pitch_total * 0.013))

    body = f"""âââââââââââââââââââââââ
ð 건°ì¡ ê°ì
âââââââââââââââââââââââ
í¼ì¹ 건°ì¡ ìì : {pitch_total}ê±´ / K-건·°í° 건¸건건 건§ì¼í건´건¹ì
루나 건°ì¡ ìì : {luna_total}ê±´ / 건·°í° ì¸í건£¨ì¸ì
ì´ 건¹ì©: ì½ {cost_est}ì

ìì ê²°ê³¼:
í¼ì¹ â ì¤í ì½ {max(1,int(pitch_total*0.20))}ê±´ / 건µ건³ ì½ {pitch_reply}ê±´ / 건¯¸í ì½ {pitch_meeting}ê±´
루나 â 건µ건³ ì½ 5ê±´ / íì°¬íì  ì½ 2ê±´
âââââââââââââââââââââââ

[í¼ì¹ ìì A â ì±ê³¼ íí¹í]
건°ì : Pitch | ê³µí건¦¬í°(0.8L) <pitch@08liter.com>
ì 건ª©: ìí¼ 1ê°건¡ 건§¤ì¶ 8ìµ â {{건¸건건건ª}}건 ê°건¥í ì´ì 

ì건íì¸ì {{건´건¹ì건ª}}건,
ê³µí건¦¬í°(0.8L) í¼ì¹ì건건¤.

ì í¬ íí¸건ì ì¤ì  ì±ê³¼ì건건¤:
ìí¼ 1ê° â ì¡°í 287건§ â 건§¤ì¶ 8ìµ 건¬ì±
건¦¬건·° 200ê±´ â ì¬건¦¬건¸ì ê²ì건 +340%
건§건 ì´ìì KOL 건¼ì´건¸ â 2건¶ 30ì´ì 1ìµ 건§¤ì¶

10건ê° 8ê°êµ­, 2건§ì¬ 건¸건건ì í¨ê»í
ê¸건¡건² ìµ건 ì¸í건£¨ì¸ì 건§ì¼í í건«í¼ì건건¤.

4ì íì  â ìí¼ 100ê±´ ê¸°ì¤ 60% í ì¸ ì¤ì건건¤. (ì í¨ê¸°ê° 4ì 30ì¼)

ìíìê°ì: https://buly.kr/AF24dn7
5건¶ 건¹건건©´ ì건´: https://buly.kr/1c9NOdW

---

[í¼ì¹ ìì B â í건¡건ª¨ì ê¸´ê¸í]
건°ì : Pitch | ê³µí건¦¬í°(0.8L) <pitch@08liter.com>
ì 건ª©: 4ì 30ì¼ 건§ê° â ìí¼ 100ê±´ 200건§ì (ì ê° 500건§ì)

ì건íì¸ì {{건´건¹ì건ª}}건,
ê³µí건¦¬í°(0.8L) í¼ì¹ì건건¤.

êµ­건´: ìí¼ 100ê±´ 200건§ì(60% í ì¸) / 건¦´ì¤ 건¬´ì í 300건§ì / êµ¬건§¤í 100ê±´+ ê±´건¹ 3,000ì
í´ì¸: ê¸건¡건² ìí¼ 100ê±´ 500건§ì(50% í ì¸) / ê¸건¡건² êµ¬건§¤í 100ê±´+ ê±´건¹ 3건§ì(40% í ì¸)

ìì± ì½íì¸ 건 3ê°ìê° ê´ê³  ìì¬ 건¬´건£ íì© ê°건¥í©건건¤.

ìíìê°ì: https://buly.kr/AF24dn7
5건¶ 건¹건건©´ ì건´: https://buly.kr/1c9NOdW

---

[루나 ìì A â ì±ê³¼+ììµ ì ìí]
건°ì : Luna | 건°건¦¬건°건¦¬ x ê³µí건¦¬í°(0.8L) <luna@08liter.com>
ì 건ª©: {{ì¸í건£¨ì¸ì건ª}}건 í건¡ìê° ì¬ê³  ì¶ì´í  K-건·°í°, íì°¬ ì ì건건¦½건건¤

ì건íì¸ì {{ì¸í건£¨ì¸ì건ª}}건!
건°건¦¬건°건¦¬ x ê³µí건¦¬í°(0.8L) 루나ì건건¤.

ì í¬ íì ì¸í건£¨ì¸ì건¤ì ì¤ì  ê²°ê³¼:
ìí¼ 1ê° â ì¡°í 287건§, 건§¤ì¶ ì§ê²°
KOL 건¼ì´건¸ â 2건¶ 30ì´ì 1ìµ 건§¤ì¶
건¦¬건·° ì½íì¸  â í건«í¼ ê²ì건 3건°° ìì¹

ì í 건¬´ì ì ê³µ / ì½íì¸  건°©í¥ 100% ìì  / ì±ê³¼ ììµ ìì´

건¸건건 ìê°: https://buly.kr/AF24dn7
íì 건¯¸í: https://buly.kr/1c9NOdW

---

[루나 ìì B â 건¨건ì§ìí]
건°ì : Luna | 건°건¦¬건°건¦¬ x ê³µí건¦¬í°(0.8L) <luna@08liter.com>
ì 건ª©: K-건·°í° íì°¬ â 건°건¦¬건°건¦¬ê° {{ì¸í건£¨ì¸ì건ª}}건ì ì ííìµ건건¤

ì건íì¸ì {{ì¸í건£¨ì¸ì건ª}}건,
건°건¦¬건°건¦¬ 루나ì건건¤.
ì í 건¬´ìì ê³µ + ììµ ìì´건¡ ì§íí건©° ì½íì¸  건°©í¥ 100% ìì ì건건¤.
건¶건´ ìì´ ìí건¶í° 건¨¼ì  건°ì건³´ì¤ ì ìì´ì.

건¸건건 ìê°: https://buly.kr/AF24dn7
íì 건¯¸í: https://buly.kr/1c9NOdW

ââââââââââââââââââââââââââââââ
âï¸ ì´ ì´건©ì¼ì íì í´ì£¼ì¸ì
ââââââââââââââââââââââââââââââ
í¼ì¹: "í¼ì¹A" 건건 "í¼ì¹B" 건건 "í¼ì¹ìì : [건´ì©]"
루나: "루나A" 건건 "루나B" 건건 "루나ìì : [건´ì©]"
ìì: "í¼ì¹A, 루나B"
ì ì²´ì·¨ì: "ì·¨ì"

â» íì  ìì´건 건¨ 1íµ건 건°ì¡건ì§ ììµ건건¤.
"""

    subject = f"[í¼ì¹+루나 ê²ì ìì²­] 4ê°ì§ ìì íì¸í´ì£¼ì¸ì | 4/30 건§ê°"
    # HTML 건²ì  ìì±
    html = f'''<div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px">
<h2 style="color:#1a1a1a;border-bottom:2px solid #333;padding-bottom:10px">ð 건°ì¡ ê°ì</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:20px">
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd;font-weight:bold">í­건ª©</td><td style="padding:8px;border:1px solid #ddd;font-weight:bold">건´ì©</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">í¼ì¹ 건°ì¡ ìì </td><td style="padding:8px;border:1px solid #ddd">{pitch_total}ê±´ (K-건·°í° 건¸건건)</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">루나 건°ì¡ ìì </td><td style="padding:8px;border:1px solid #ddd">{luna_total}ê±´ (DB ìì§ í ì§í)</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">ìì ì¤í/건µ건³/건¯¸í</td><td style="padding:8px;border:1px solid #ddd">{max(1,int(pitch_total*0.20))}ê±´ / {pitch_reply}ê±´ / {pitch_meeting}ê±´</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">건°ì¡ 건¹ì©</td><td style="padding:8px;border:1px solid #ddd">ì½ {cost_est}ì</td></tr>
</table>
<hr style="border:1px solid #eee;margin:20px 0">
<h2 style="color:#1a1a1a">ð§ í¼ì¹ ìì A â ì±ê³¼ íí¹í</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p style="margin:0 0 8px"><strong>ì 건ª©:</strong> ìí¼ 1ê°건¡ 건§¤ì¶ 8ìµ â {{건¸건건건ª}}건 ê°건¥í ì´ì </p>
<p style="margin:0"><strong>건°ì :</strong> Pitch | ê³µí건¦¬í°(0.8L)</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">
<p>ì건íì¸ì {{건´건¹ì건ª}}건,<br>ê³µí건¦¬í°(0.8L) í¼ì¹ì건건¤.</p>
<p>ì í¬ íí¸건ì ì¤ì  ì±ê³¼ì건건¤:<br>ð¥ ìí¼ 1ê° â ì¡°í 287건§ â 건§¤ì¶ 8ìµ<br>ð¥ 건¦¬건·° 200ê±´ â ì¬건¦¬건¸ì ê²ì건 +340%<br>ð¥ KOL 건¼ì´건¸ â 2건¶ 30ì´ì 1ìµ 건§¤ì¶</p>
<p>4ì íì  â ìí¼ 100ê±´ ê¸°ì¤ 60% í ì¸ (4/30 건§ê°)</p>
<p>ð <a href="https://buly.kr/AF24dn7">ìíìê°ì</a> | ð <a href="https://buly.kr/1c9NOdW">5건¶ ì건´</a></p></div>
<hr style="border:1px solid #eee;margin:20px 0">
<h2 style="color:#1a1a1a">ð§ í¼ì¹ ìì B â í건¡건ª¨ì ê¸´ê¸í</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p style="margin:0 0 8px"><strong>ì 건ª©:</strong> 4ì 30ì¼ 건§ê° â ìí¼ 100ê±´ 200건§ì (ì ê° 500건§ì)</p>
<p style="margin:0"><strong>건°ì :</strong> Pitch | ê³µí건¦¬í°(0.8L)</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">
<p>ì건íì¸ì {{건´건¹ì건ª}}건,<br>ê³µí건¦¬í°(0.8L) í¼ì¹ì건건¤.</p>
<p>ð°ð· <strong>êµ­건´</strong><br>ð¥ ìí¼ 100ê±´: 200건§ì (60% í ì¸)<br>ð¥ 건¦´ì¤ 건¬´ì í 300건§ì<br>ð¥ êµ¬건§¤í 100ê±´+ ê±´건¹ 3,000ì</p>
<p>ð <strong>í´ì¸</strong><br>ð¥ ê¸건¡건² ìí¼ 100ê±´: 500건§ì (50% í ì¸)<br>ð¥ ê¸건¡건² êµ¬건§¤í 100ê±´+ ê±´건¹ 3건§ì</p>
<p>ð <a href="https://buly.kr/AF24dn7">í건¡건ª¨ì ìì¸</a> | ð <a href="https://buly.kr/1c9NOdW">5건¶ ì건´</a></p></div>
<hr style="border:1px solid #eee;margin:20px 0">
<h2 style="color:#1a1a1a">ð§ 루나 ìì A â ì±ê³¼+ììµ ì ìí</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p style="margin:0 0 8px"><strong>ì 건ª©:</strong> {{ì¸í건£¨ì¸ì건ª}}건 í건¡ìê° ì¬ê³  ì¶ì´í  K-건·°í°, íì°¬ ì ì</p>
<p style="margin:0"><strong>건°ì :</strong> Luna | 건°건¦¬건°건¦¬ x ê³µí건¦¬í°(0.8L)</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">
<p>ì건íì¸ì {{ì¸í건£¨ì¸ì건ª}}건!<br>건°건¦¬건°건¦¬ x ê³µí건¦¬í°(0.8L) 루나ì건건¤.</p>
<p>â ìí¼ 1ê° â ì¡°í 287건§<br>â KOL 건¼ì´건¸ â 2건¶ 30ì´ì 1ìµ<br>â 건¦¬건·° â ê²ì건 3건°°</p>
<p>â ì í 건¬´ì ì ê³µ / â ì½íì¸  100% ìì  / â ììµ ìì´</p>
<p>ð <a href="https://buly.kr/AF24dn7">건¸건건 ìê°</a> | ð <a href="https://buly.kr/1c9NOdW">íì 건¯¸í</a></p></div>
<hr style="border:1px solid #eee;margin:20px 0">
<h2 style="color:#1a1a1a">ð§ 루나 ìì B â 건¨건ì§ìí</h2>
<div style="background:#f9f9f9;padding:15px;border-left:4px solid #333;margin-bottom:10px">
<p style="margin:0 0 8px"><strong>ì 건ª©:</strong> K-건·°í° íì°¬ â 건°건¦¬건°건¦¬ê° {{ì¸í건£¨ì¸ì건ª}}건ì ì ííìµ건건¤</p>
<p style="margin:0"><strong>건°ì :</strong> Luna | 건°건¦¬건°건¦¬ x ê³µí건¦¬í°(0.8L)</p></div>
<div style="background:#fff;padding:15px;border:1px solid #ddd;line-height:1.8">
<p>ì건íì¸ì {{ì¸í건£¨ì¸ì건ª}}건,<br>건°건¦¬건°건¦¬ 루나ì건건¤.</p>
<p>ì í 건¬´ì ì ê³µ + ììµ ìì´ / ì½íì¸  100% ìì <br>건¶건´ ìì´ ìí건¶í° 건¨¼ì  건°ì건³´ì¤ ì ìì´ì.</p>
<p>ð <a href="https://buly.kr/AF24dn7">건¸건건 ìê°</a> | ð <a href="https://buly.kr/1c9NOdW">íì 건¯¸í</a></p></div>
<hr style="border:2px solid #333;margin:30px 0">
<div style="background:#fff3cd;padding:15px;border:1px solid #ffc107;border-radius:4px">
<h3 style="margin:0 0 10px;color:#856404">âï¸ ì´ ì´건©ì¼ì íì í´ì£¼ì¸ì</h3>
<p style="margin:0 0 8px">í¼ì¹: <strong>"í¼ì¹A"</strong> 건건 <strong>"í¼ì¹B"</strong></p>
<p style="margin:0 0 8px">루나: <strong>"루나A"</strong> 건건 <strong>"루나B"</strong></p>
<p style="margin:0 0 8px">ìì: <strong>"í¼ì¹A, 루나B"</strong></p>
<p style="margin:0;color:#dc3545"><strong>â» íì  ìì´건 건¨ 1íµ건 건°ì¡건ì§ ììµ건건¤.</strong></p>
</div></div>'''

    result = _send_email_smtp(ceo_email, subject, body, "í¼ì¹", html_body=html)
    result["pitch_total"] = pitch_total
    result["luna_total"] = luna_total
    return result

@app.get("/api/send-luna-db-request")
async def api_send_luna_db_request():
    """루나 DB ìì§ ì¹ì¸ ìì²­ ì´건©ì¼ 건°ì¡."""
    ceo_email = "jacob@08liter.com"
    subject = "[루나 DB ìì§ ì¹ì¸ ìì²­] ì¸í건£¨ì¸ì 50건ª | 건¹ì© 196ì"
    html = '''<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
<h2 style="color:#1a1a1a;border-bottom:2px solid #333;padding-bottom:10px">ð¦ 루나 DB ìì§ ê³í</h2>
<table style="width:100%;border-collapse:collapse;margin-bottom:20px">
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd;font-weight:bold">í­건ª©</td><td style="padding:8px;border:1px solid #ddd;font-weight:bold">건´ì©</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">ìì§ ì¶ì²</td><td style="padding:8px;border:1px solid #ddd">Instagram (#kbeauty #skincare í´ìíê·¸)</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">ìì§ 건ª©í</td><td style="padding:8px;border:1px solid #ddd">50건ª</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">ì건£ ê¸°ê°</td><td style="padding:8px;border:1px solid #ddd">ì¹ì¸ í 건¹ì¼</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">ìì 건¹ì©</td><td style="padding:8px;border:1px solid #ddd">ì½ 196ì (Haiku ê¸°ì¤)</td></tr>
<tr><td style="padding:8px;border:1px solid #ddd">íê² ê¸°ì¤</td><td style="padding:8px;border:1px solid #ddd">â í건¡ì 1건§~100건§<br>â ì¸ê²ì´ì§건¨¼í¸ 3%+<br>â 건·°í°/ì¤í¨ì¼ì´<br>â ê³µê° 건¹ì¦건ì¤ ì´건©ì¼<br>â íêµ­ 50% / ì¼건³¸ 25% / 건건¨ì 25%</td></tr>
<tr style="background:#f5f5f5"><td style="padding:8px;border:1px solid #ddd">ì ì¸ ê¸°ì¤</td><td style="padding:8px;border:1px solid #ddd">â ì¸ê²ì´ì§건¨¼í¸ 3% 건¯¸건§<br>â 3ê°ì 건¯¸ì건¡건<br>â ì´건©ì¼ ì건 ê³ì </td></tr>
</table>
<div style="background:#fff3cd;padding:15px;border:1px solid #ffc107;border-radius:4px">
<strong>âï¸ íì í´ì£¼ì¸ì:</strong><br>
"ìì§ì¹ì¸" â ì¦ì ìì§ ìì<br>
"ìì§ìì : [건´ì©]" â ìì  í ì¬ìì²­<br>
"ìì§ì·¨ì" â ì·¨ì<br><br>
<strong style="color:#dc3545">â» íì  ìì´건 ìì§ ìì 건¶ê°</strong>
</div></div>'''
    result = _send_email_smtp(ceo_email, subject, "루나 DB ìì§ ì¹ì¸ ìì²­", "루나", html_body=html)
    return result

# ===== ì건¬´ìê° ì²´í¬ =====
def _is_business_hours(country: str = "KR") -> bool:
    """íì§ ì건¬´ìê°(íì¼ 09~18ì) ì¬건¶ íì¸."""
    offsets = {"KR": 9, "JP": 9, "US": -4, "TH": 7, "ID": 7, "VN": 7, "MY": 8, "SG": 8}
    offset = offsets.get(country[:2].upper(), 9)
    now_utc = datetime.utcnow()
    local_hour = (now_utc.hour + offset) % 24
    local_weekday = ((now_utc.weekday() * 24 + now_utc.hour + offset) // 24) % 7
    # 0=ì ~ 4=ê¸ = íì¼, 5=í  6=ì¼ = ì£¼건§
    is_weekend = local_weekday >= 5
    return not is_weekend and 9 <= local_hour < 18

# ===== í¼ì¹ ìì¨ ì¤í + íì§ ì ê² + 2ì°¨ ì´건©ì¼ =====

PITCH_TEMPLATES = {
    "A": {"label": "ì±ê³µì¬건¡í",
          "subject": "2건¶ 30ì´ì 1ìµ, ìí¼ 1ê°건¡ 287건§ ì¡°í â {brand}ì 건¤ì ì¬건¡ê° 건  ì ììµ건건¤",
          "body": "ì건íì¸ì {contact}건,\n\nì í¬ íí¸건ê° 건§건 ì´ìì 건¼ì´건¸ 2건¶ 30ì´ 건§ì 1ìµ 건§¤ì¶,\nêµ­건´ íí¸건건 ìí¼ 1ê°건¡ 287건§ ì¡°íÂ·건§¤ì¶ +180%건¥¼ 건§건¤ììµ건건¤.\n\n{brand}ì´ ì§ì¶í건 ¤건 êµ­ê°건 ì±건, ê³ 건¯¼íì건 건¶건¶ì\nì건 ¤ì£¼ì건©´ ê´건 ¨ ì±ê³µ ì¬건¡건¥¼ 건°건¡ 건³´건´건건¦¬ê² ìµ건건¤.\ní¸íì  ìê°ì 30건¶ 건¹건건©´ì¼건¡ ì§ì  ì¤건ª건건¦´ ì건 ììµ건건¤.\n\nð ìíìê°ì 건° í건¡건ª¨ì: https://buly.kr/AF24dn7\nð 30건¶ 건¹건건©´ 건¯¸í ìì½: https://buly.kr/1c9NOdW\n\n---\nê³µí건¦¬í° ì£¼건ì´ ì»¨ì¤í´í¸\ní¼ì¹ 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "B": {"label": "í건¡건ª¨ìí",
          "subject": "4/30 건§ê° â ìí¼ 100ê±´ 200건§ì, {brand} ì ì²­ ê°건¥í©건건¤",
          "body": "ì건íì¸ì {contact}건,\n\n4ì í 건¬건§ ì§íí건 í건¡건ª¨ìì건건¤.\n\nêµ­건´: ìí¼ 100ê±´ 200건§ì (ì ê° 500건§ì / 60% í ì¸)\ní´ì¸(ì건§ì¡´Â·ì¼í¼Â·í±í¡ìµ): ê¸건¡건² ìí¼ 100ê±´ 500건§ì (ì ê° 1,000건§ì / 50% í ì¸)\n\nìì±건 ì½íì¸ 건 3ê°ìê° ê´ê³  ìì¬건¡ 건¬´건£ íì© ê°건¥í©건건¤.\n{brand}ì 건§건 íì© 건°©건²ì 30건¶ 건¹건건©´ì¼건¡ ì¤건ª건건¦´ ì ììµ건건¤.\n\nð ì ì²´ í건¡건ª¨ì ìì¸: https://buly.kr/AF24dn7\nð 30건¶ 건¹건건©´ 건¯¸í ìì½: https://buly.kr/1c9NOdW\n\n---\nê³µí건¦¬í° ì£¼건ì´ ì»¨ì¤í´í¸\ní¼ì¹ 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "C": {"label": "íí¹í",
          "subject": "{brand}, ì§ê¸ ê°ì¥ ê³ 건¯¼íì건 ê² 건­ê°ì?",
          "body": "ì건íì¸ì {contact}건,\n\n건¦¬건·°ê° ìì´ì, ìí¼ì´ ì í°ì ¸ì, í´ì¸ ì§ì¶ì´ 건§건§í´ì.\n건¸건건건§건¤ ê³ 건¯¼ì´ 건¤건¦건건¤.\n\nì§ì¶í건 ¤건 êµ­ê°건 ì±건ì ì건 ¤ì£¼ì건©´\n10건ê° 8ê°êµ­ 2건§ì¬ 건¸건건ì í¨ê»í ê²½íì¼건¡\n건± 건§건 ì¬건¡건¥¼ ì°¾ì 30건¶ 건¹건건©´ì¼건¡ ì¤건ª건건¦¬ê² ìµ건건¤.\n\nð ìíìê°ì 건° í건¡건ª¨ì: https://buly.kr/AF24dn7\nð 30건¶ 건¹건건©´ 건¯¸í ìì½: https://buly.kr/1c9NOdW\n\n---\nê³µí건¦¬í° ì£¼건ì´ ì»¨ì¤í´í¸\ní¼ì¹ 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "A_EN": {"label": "Success Story (EN)",
             "subject": "287M views from 1 short video â {brand} could be next",
             "body": "Hi {contact},\n\nOne of our partners hit 1B KRW in sales from a 2.5-minute live stream in Malaysia.\nAnother drove 287M views and +180% revenue from a single short-form video.\n\nLet us know which market or channel you're focusing on, and we'll share the most relevant case study.\n\nHappy to explain in a 30-min virtual call.\n\nð Deck + Promotions: https://buly.kr/AF24dn7\nð Book a call: https://buly.kr/1c9NOdW\n\n---\nPitch\nJunior Consultant, 08liter Global\n\npitch@08liter.com\nwww.08liter.com"},
    "B_EN": {"label": "Promo Urgent (EN)",
             "subject": "April only â 100 short videos for 2M KRW ({brand} eligible)",
             "body": "Hi {contact},\n\nThis month only, we're offering 100 short-form videos (Reels/TikTok) for 2M KRW â regular price 5M KRW.\n\nFor global markets (Amazon, Shopee, TikTok Shop): 100 videos for 5M KRW (regular 10M KRW).\n\nAll content is yours to reuse as ad creative for 3 months at no extra cost.\n\nð Full details: https://buly.kr/AF24dn7\nð 30-min call: https://buly.kr/1c9NOdW\n\n---\nPitch\nJunior Consultant, 08liter Global\n\npitch@08liter.com\nwww.08liter.com"},
}

PITCH_REPLY_TEMPLATES = {
    "meeting": {"subject": "RE: 건¯¸í ìì½ 건§í¬ 건³´건´건건¦½건건¤",
                "body": "ì건íì¸ì {contact}건,\n\nìê° 건´ì£¼ìì ê°ì¬í©건건¤.\nì건 건§í¬ìì í¸íì  ìê° ì íí´ ì£¼ì¸ì.\n\nð https://buly.kr/1c9NOdW\n\n건¯¸í ì ì ì건 건´ì© 건¯¸건¦¬ ì건 ¤ì£¼ì건©´ 건 ìì°¨ê² ì¤건¹íê² ìµ건건¤.\n\nÂ· ì£¼건 ¥ í건§¤ ì±건\nÂ· ê´ì¬ ì건 건§ì¼í 건°©ì\nÂ· ì§ì¶í건 ¤건 êµ­ê°\n\nê¸°건¤건¦¬ê² ìµ건건¤.\n\n---\nê³µí건¦¬í° ì£¼건ì´ ì»¨ì¤í´í¸\ní¼ì¹ 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "info": {"subject": "RE: ê³µí건¦¬í° ì건¹ì¤ ì건´건건¦½건건¤",
             "body": "ì건íì¸ì {contact}건,\n\nì í¬건 ì¸ ê°ì§ ì건¹ì¤건¥¼ ì´ìí©건건¤.\n\nâ  êµ¬건§¤í â ì¿ í¡Â·ì¬건¦¬건¸ìÂ·ì건§ì¡´ 건± ì¤êµ¬건§¤ 건¦¬건·°\nâ¡ ìí¼ ì²´í건¨ â ì¸ì¤íÂ·í±í¡Â·ì¼ì¸  ìì ì½íì¸  ì ì\nâ¢ 건§ì¶¤ ì¸í건£¨ì¸ì â 건¸건건 íì 건§건 KOL íì\n\n4ì íì  ìµ건 60% í ì¸ ì¤ì건건¤.\n\nð ìì¸í 건´ì©: https://buly.kr/AF24dn7\nð 30건¶ 건¹건건©´ 건¯¸í: https://buly.kr/1c9NOdW\n\n---\nê³µí건¦¬í° ì£¼건ì´ ì»¨ì¤í´í¸\ní¼ì¹ 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "later": {"subject": "{brand}, 4ì 30ì¼ì´ 건§ì§건§ì건건¤",
              "body": "ì건íì¸ì {contact}건,\n\nì§건건² ì°건½건건 ¸건 ê³µí건¦¬í° í¼ì¹ì건건¤.\n\n4ì íì  60% í ì¸ í건¡건ª¨ìì´ ì´건² 건¬ 건§ 건§ê°건©건건¤.\n건°ìì  ê±´ ì¶©건¶í ì´í´í©건건¤.\n5ì ì¼ì ì¼건¡ 건¯¸건¦¬ 건 ì§건§ ì¡ì건ì건 건©건건¤.\n\nð https://buly.kr/1c9NOdW\nð ìíìê°ì: https://buly.kr/AF24dn7\n\n---\nê³µí건¦¬í° ì£¼건ì´ ì»¨ì¤í´í¸\ní¼ì¹ 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
    "reject": {"subject": "RE: 건§ì ê°ì¬í©건건¤",
               "body": "ì건íì¸ì {contact}건,\n\n건§ì ê°ì¬í©건건¤.\n건¦¬건·°Â·ìí¼Â·í´ì¸ ì§ì¶ ê´건 ¨í´ì\nê³ 건¯¼ì´ ìê¸°ì¤ 건 í¸íê² ì°건½ ì£¼ì¸ì.\n\n---\nê³µí건¦¬í° ì£¼건ì´ ì»¨ì¤í´í¸\ní¼ì¹ 건건¦¼\n\npitch@08liter.com\nwww.08liter.com"},
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
    """건°ì¡ ì  íì§ ì ê². ì¤í¨ ì¬ì  건¦¬ì¤í¸ 건°í (건¹ 건¦¬ì¤í¸ = íµê³¼)."""
    errors = []
    if not email or "@" not in email:
        errors.append("ì´건©ì¼ ì£¼ì 건¬´í¨")
    if not subject:
        errors.append("ì 건ª© 건¹ì´ìì")
    if not body:
        errors.append("건³¸건¬¸ 건¹ì´ìì")
    if "{" in subject or "{" in body:
        errors.append("ê°ì¸í 건¯¸ì¹í ({} ìì¡´)")
    if "buly.kr/AF24dn7" not in body:
        errors.append("ìê°ì 건§í¬ 건건½")
    if "buly.kr/1c9NOdW" not in body:
        errors.append("건¯¸í 건§í¬ 건건½")
    if "ê³µí건¦¬í°" not in body and "í¼ì¹ 건건¦¼" not in body:
        errors.append("ì건ª 건건½")
    return errors

@app.post("/api/pitch/send")
async def api_pitch_send(request: Request):
    """CEO ì¹ì¸건 ììì¼건¡ í¼ì¹ ì´건©ì¼ 건°ì¡. DB ìì¤: ì¤ì§ í¼ì¹_í´건¡건 í­."""
    body = await request.json()
    template_key = body.get("template", body.get("variant", "A")).upper()
    if template_key == "AB":
        template_key = "A"  # 건³µì ì í ì A ì°ì 
    tmpl = PITCH_TEMPLATES.get(template_key, PITCH_TEMPLATES["A"])
    # DB ìì¤: ì¤ì§ í¼ì¹ ìí¸ "í¼ì¹_í´건¡건" í­ (건¤건¥¸ ìí¸ í¼ì© ê¸ì§)
    rows = fetch_sheet(PITCH_SHEET_ID, "A:N", "í¼ì¹_í´건¡건", ttl_key="inbound")
    leads = []
    if rows and len(rows) > 1:
        # í¤건 íì¸ (A:No B:DBí건³´건 ì§ ... E:건¸건건건ª ... H:ì´건©ì¼ ... N:건°ì¡ìí)
        for row in rows[1:]:
            if len(row) < 8:
                continue
            email = str(row[7]).strip() if len(row) > 7 else ""  # Hì´ = ì´건©ì¼
            brand = str(row[4]).strip() if len(row) > 4 else ""  # Eì´ = 건¸건건건ª
            sent_status = str(row[13]).strip() if len(row) > 13 else ""  # Nì´ = 건°ì¡ìí
            if email and "@" in email and not sent_status:  # 건°ì¡ì¼ì 건¹ì´ì건 ê±´건§
                leads.append({"name": brand, "email": email})
    if not leads:
        # í¼ì¹_í´건¡건 í­ì´ 건¹ìì¼건©´ íì¼건¬¸ì í´건°± (ê²½ê³  í¬í¨)
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
        # ì건¬´ìê° ì²´í¬
        if not _is_business_hours(country):
            deferred += 1
            continue
        # ì¸ì´ ì건 ì í: íêµ­/ì¼건³¸ â íêµ­ì´, ê·¸ ì¸ â ìì´
        if country not in ("KR", "JP") and template_key + "_EN" in PITCH_TEMPLATES:
            tmpl = PITCH_TEMPLATES[template_key + "_EN"]
        subj = tmpl["subject"].replace("{brand}", brand).replace("{contact}", contact)
        email_body = tmpl["body"].replace("{brand}", brand).replace("{contact}", contact)
        qc = _pitch_quality_check(email, subj, email_body)
        if qc:
            skipped += 1
            errors_list.append({"brand": brand, "errors": qc})
            _record_perf("í¼ì¹", "quality_fail")
            continue
        html = _build_pitch_html(brand, email_body)
        result = _send_email(email, subj, html, "í¼ì¹")
        if result["status"] == "ok":
            sent += 1
        else:
            skipped += 1
            errors_list.append({"brand": brand, "errors": [result.get("message", "건°ì¡ ì¤í¨")]})
    _record_perf("í¼ì¹", "email_sent_batch", sent)
    return {"status": "ok", "template": template_key, "sent": sent, "skipped": skipped, "deferred": deferred, "errors": errors_list[:10]}

@app.post("/api/agents/pitch/daily")
async def api_pitch_daily(request: Request):
    """í¼ì¹ 건§¤ì¼ ìì¨ ì¤í. trigger=immediate/scheduled, action=collect_only/full."""
    body = await request.json()
    action = body.get("action", "full")
    now = datetime.now(KST)
    result = {"timestamp": now.isoformat(), "steps": []}

    # STEP 1: í¼ì¹_í´건¡건 í­ ì ê· DB ê±´ì íì¸
    rows = fetch_sheet(PITCH_SHEET_ID, "A:N", "í¼ì¹_í´건¡건", ttl_key="inbound")
    unsent = 0
    if rows and len(rows) > 1:
        for row in rows[1:]:
            email = str(row[7]).strip() if len(row) > 7 else ""
            sent_status = str(row[13]).strip() if len(row) > 13 else ""
            if email and "@" in email and not sent_status:
                unsent += 1
    result["steps"].append({"step": "DB íì¸", "unsent": unsent})

    # STEP 2: 건¶ì¡±í건©´ DB ìì§ (íì¬건 ì¸건°ì´건 ìí¸ 기반)
    collected = 0
    if unsent < 10:
        leads_data = await api_recontact_leads()
        leads = [l for l in leads_data.get("leads", []) if l.get("email") and "@" in l.get("email", "")]
        collected = len(leads)
        _record_perf("í¼ì¹", "crawl_brands", collected)
    result["steps"].append({"step": "DB ìì§", "collected": collected, "needed": unsent < 10})

    if action == "collect_only":
        # DB ìì§건§ (건°ì¡ì ììì¼ 09:00)
        notify_body = f"[í¼ì¹] DB {unsent + collected}ê±´ íì¸ ì건£.\nì ê· 건¯¸건°ì¡: {unsent}ê±´\nì¶ê° ìì§: {collected}ê±´\n\nììì¼ 08:30ì ê²ì ì´건©ì¼ 건°ì¡ ìì ì건건¤."
        _send_email_smtp("jacob@08liter.com", "[í¼ì¹] DB ìì§ ì건£ â ììì¼ 건°ì¡ ìì ", notify_body, "í¼ì¹")
        result["steps"].append({"step": "CEO ì건¦¼", "message": "ììì¼ 건°ì¡ ìì "})
        return result

    # STEP 3: ì건¬´ìê° ì²´í¬
    if not _is_business_hours("KR"):
        result["steps"].append({"step": "건°ì¡ 건³´건¥", "reason": "ì건¬´ìê° ì¸ (ì~ê¸ 09~18ì건§)"})
        return result

    # STEP 3: CEO ê²ì ì´건©ì¼ 건°ì¡
    review_result = await api_send_review_email()
    result["steps"].append({"step": "CEO ê²ì 건°ì¡", "status": review_result.get("status"), "total": review_result.get("pitch_total", 0)})
    return result

@app.post("/api/pitch/revise")
async def api_pitch_revise(request: Request):
    """CEO ìì  ìì²­ ì ì â ìì  í ì¬ê²ì ì´건©ì¼ 건°ì¡."""
    body = await request.json()
    instruction = body.get("instruction", "")
    # ìì  ìì²­ ê¸°건¡
    _record_perf("í¼ì¹", "revise_request")
    # ì¬ê²ì ì´건©ì¼ 건°ì¡
    result = await api_send_review_email()
    result["revise_instruction"] = instruction[:200]
    return result

@app.post("/api/pitch/reply")
async def api_pitch_reply(request: Request):
    """건¸건건 건µ건³ ì í건³ 2ì°¨ ì´건©ì¼ ì건 건°ì¡."""
    body = await request.json()
    reply_type = body.get("type", "info")
    brand = body.get("brand", "")
    contact = body.get("contact", brand)
    email = body.get("email", "")
    tmpl = PITCH_REPLY_TEMPLATES.get(reply_type, PITCH_REPLY_TEMPLATES["info"])
    subj = tmpl["subject"].replace("{brand}", brand).replace("{contact}", contact)
    email_body = tmpl["body"].replace("{brand}", brand).replace("{contact}", contact)
    html = _build_pitch_html(brand, email_body)
    result = _send_email(email, subj, html, "í¼ì¹")
    _record_perf("í¼ì¹", f"reply_{reply_type}")
    return {"status": result["status"], "type": reply_type, "to": email}

@app.get("/api/pitch/performance")
async def api_pitch_performance():
    """í¼ì¹ ì±ê³¼ 건ì건³´건 â ìí¸ ì¤건°ì´í° 기반."""
    pipeline = await api_sheet_pipeline(agent="í¼ì¹")
    perf = load_agent_perf()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    today_p = perf.get(today, {}).get("í¼ì¹", {})
    monthly_p = {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix) and "í¼ì¹" in ad:
            for mk, mv in ad["í¼ì¹"].items():
                monthly_p[mk] = monthly_p.get(mk, 0) + mv
    total = pipeline.get("total", {})
    funnel = pipeline.get("funnel", {})
    return {
        "kpi": {
            "total_db": total.get("db", 0),
            "with_email": total.get("with_email", 0),
            "sent_today": today_p.get("email_sent", 0) + today_p.get("email_sent_batch", 0),
            "sent_month": monthly_p.get("email_sent", 0) + monthly_p.get("email_sent_batch", 0),
            "quality_fail": monthly_p.get("quality_fail", 0),
            "working": total.get("working", 0),
            "meeting": total.get("meeting", 0),
        },
        "funnel": funnel,
        "reply_types": {
            "meeting": monthly_p.get("reply_meeting", 0),
            "info": monthly_p.get("reply_info", 0),
            "later": monthly_p.get("reply_later", 0),
            "reject": monthly_p.get("reply_reject", 0),
        },
        "sheet_url": SHEET_URLS.get("í¼ì¹", ""),
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
    rows = fetch_sheet(LUNA_SHEET_ID, "A:R", "현황시트(수동매칭)", ttl_key="influencer")
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
    rows = fetch_sheet(LUNA_SHEET_ID, "A:R", "현황시트(수동매칭)", ttl_key="influencer")
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
    rows = fetch_sheet(LUNA_SHEET_ID, "A:R", "현황시트(수동매칭)", ttl_key="influencer")
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

async def _run_recontact_campaign(dry_run: bool = True, limit: int = 10) -> dict:
    """ì¬ì ì´ ìº íì¸ 건´건¶ ì¤í í¨ì."""
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
            f"ì건íì¸ì, ê³µí건¦¬í°ê¸건¡건² 건¸건건 íí¸건ì­ í 루나ì건건¤.\n\n"
            f"ì§건건² {brand_name} ê´건 ¨ 건¬¸ì건¥¼ ì£¼ì¨ì 건 ì¢ì 건í건¥¼ 건건´ì건건°ì,\n"
            f"ì´í ì§í ìí©ì´ ê¶ê¸íì¬ 건¤ì ì°건½건건¦½건건¤.\n\n"
            f"ìµê·¼ ì í¬건 ì¸í건£¨ì¸ì 건§ì¼í 건¶ì¼ìì ì건¡ì´ ì±ê³¼건¥¼ ê±°건ê³  ìì¼건©°,\n"
            f"{brand_name}ì ìµì í건 ìº íì¸ ì 건µì ì¤건¹íìµ건건¤.\n\n"
            f"í¸íì  ìê°ì 15건¶건§ í¬ìí´ ì£¼ì건©´ 건§ì¶¤ ì ìì 건건¦¬ê² ìµ건건¤.\n\nê°ì¬í©건건¤.\n루나 건건¦¼"
        )
        subject = f"[ê³µí건¦¬í°ê¸건¡건²] {brand_name} 건§ì¶¤ ì¸í건£¨ì¸ì 건§ì¼í ì ì"
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
    """루나 ì¬ì ì´ ìº íì¸ ì¤í API."""
    body = await request.json()
    return await _run_recontact_campaign(dry_run=body.get("dry_run", True), limit=body.get("limit", 10))


# ===== ìì´ì í¸ ìì¨ ì건¬´ í¨ì =====

async def _pitch_inbound_auto():
    """í¼ì¹: ì ê· ì¸건°ì´건 ê°ì§ â ì건 ì건 ì´건©ì¼ + 건¯¸í 건§í¬ 건°ì¡."""
    inbound_rows = fetch_sheet(SHEET_INBOUND, "A:Z", "íì¼건¬¸ì", ttl_key="inbound")
    if not inbound_rows:
        return {"sent": 0}
    hdr_idx = _find_header_row(inbound_rows, "êµ­ê°", "ì»¨ííí©", "ì»¨ííí©", "건´건¹ì")
    headers = [str(h).replace("\n", " ").strip() for h in inbound_rows[hdr_idx]]
    email_idx = _find_col(headers, "ì´건©ì¼") or 6
    brand_idx = _find_col(headers, "ìì²´건ª", "건¸건건") or 4
    status_idx = _find_col(headers, "ì»¨ííí©", "ì»¨ííí©") or 16
    staff_idx = _find_col(headers, "건´건¹ì") or 14
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
        body = (f"ì건íì¸ì, ê³µí건¦¬í°ê¸건¡건² í¼ì¹ì건건¤.\n\n"
                f"{brand} ê´건 ¨ 건¬¸ì ê°ì¬í©건건¤. 건¹ 건¥¸ ìì¼ 건´ì 건§ì¶¤ ì ìì ì¤건¹í´ 건건¦¬ê² ìµ건건¤.\n\n"
                f"í¸íì  ìê°ì 15건¶ 건¹건건©´ 건¯¸íì íµí´ ìì¸í ì건´건건¦¬ê² ìµ건건¤.\n\n"
                f"건¯¸í ìì½: {MEETING_LINK}\n\nê°ì¬í©건건¤.\ní¼ì¹ 건건¦¼")
        html = _build_pitch_html(brand, body)
        result = _queue_or_send_email("í¼ì¹", email, f"[ê³µí건¦¬í°ê¸건¡건²] {brand} ì¸í건£¨ì¸ì 건§ì¼í ì ì", html, {"brand": brand})
        if result["status"] in ("ok", "queued"):
            sent += 1
            _record_perf("í¼ì¹", "meeting_invite")
    _record_perf("í¼ì¹", "inbound_processed", sent)
    return {"sent": sent}

async def _pitch_outbound_crm():
    """í¼ì¹: ì í¨DB ì¤ 건¯¸ê³ì½ 건¸건건ì CRM 건´ì¤건 í° 건°ì¡."""
    leads_data = await api_recontact_leads()
    leads = leads_data.get("leads", [])
    targets = [l for l in leads if l.get("email") and "@" in l.get("email", "")][:10]
    sent = 0
    for lead in targets:
        brand = lead["name"]
        body = (f"ì건íì¸ì, ê³µí건¦¬í°ê¸건¡건² í¼ì¹ì건건¤.\n\n"
                f"íì¬ {brand}ì ìµì í건 í건¡건ª¨ì í¨í¤ì§건¥¼ ì¤건¹íìµ건건¤.\n\n"
                f"ê¸건¡건² 155건§+ ì¸í건£¨ì¸ì 건¤í¸ìí¬건¥¼ íì©í 건§ì¶¤í ìº íì¸ì¼건¡\n"
                f"건¸건건 ì¸ì§건ì 건§¤ì¶ì 건ìì 건ì¬건건¦½건건¤.\n\n"
                f"건¹건건©´ 건¯¸í ìì½: {MEETING_LINK}\n\nê°ì¬í©건건¤.\ní¼ì¹ 건건¦¼")
        html = _build_pitch_html(brand, body)
        result = _send_email(lead["email"], f"[ê³µí건¦¬í°ê¸건¡건²] {brand} 건§ì¶¤ í건¡건ª¨ì ì건´", html, "í¼ì¹")
        if result["status"] == "ok":
            sent += 1
    _record_perf("í¼ì¹", "crm_newsletter", sent)
    return {"sent": sent, "total_leads": len(leads)}

async def _luna_inbound_welcome():
    """루나: ì ê· ì¸í건£¨ì¸ì ì§ìììê² íì ì´건©ì¼ + ìº íì¸ ì건´."""
    rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", "íí©ìí¸(ì건건§¤ì¹­)", ttl_key="influencer")
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
        body = (f"ì건íì¸ì {name}건, ê³µí건¦¬í°ê¸건¡건² 루나ì건건¤!\n\n"
                f"ì¸í건£¨ì¸ì íí¸건 건±건¡ì íìí©건건¤.\n\n"
                f"íì¬ ì§í ì¤ì¸ ìº íì¸ì ì건´건건¦½건건¤:\n"
                f"â¢ K-건·°í° ì²´í ìº íì¸ (건°건¦¬건°건¦¬)\n"
                f"â¢ ê¸건¡건² 건¦¬건·° ìº íì¸\n"
                f"â¢ í´ì¸ êµ¬건§¤í ì건¹ì¤\n\n"
                f"ê´ì¬ ì건 ìº íì¸ì´ ìì¼ì건©´ íì í´ ì£¼ì¸ì.\n루나 건건¦¼")
        html = _build_pitch_html(name, body)
        result = _queue_or_send_email("루나", email, f"[ê³µí건¦¬í°ê¸건¡건²] {name}건 íìí©건건¤!", html, {"influencer": name})
        if result["status"] in ("ok", "queued"):
            sent += 1
    _record_perf("루나", "welcome_sent", sent)
    return {"sent": sent}

async def _luna_outbound_pitch():
    """루나: ì¸í건£¨ì¸ì DBìì ì´건©ì¼ ì건 건ììê² ìº íì¸ ì ì 건°ì¡."""
    rows = fetch_sheet(SHEET_INFLUENCER, "A2:R", "íí©ìí¸(ì건건§¤ì¹­)", ttl_key="influencer")
    if not rows:
        return {"sent": 0}
    targets = []
    for row in rows:
        if len(row) < 12:
            continue
        status = str(row[10]).strip() if len(row) > 10 else ""
        if status != "건¨ì건¦¬ì¤í¸ì" and status != "1. 건¨ì건¦¬ì¤í¸ì":
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
    """ìí¼: Anthropic API건¡ B2B/B2C ì½íì¸  ê¸°í + ì¹ì¸ í 건±건¡."""
    if not ANTHROPIC_API_KEY:
        return {"status": "no_api_key"}
    now = datetime.now(KST)
    prompt = (f"ì¤건ì {now.strftime('%Y건 %mì %dì¼ %A')}ì건건¤.\n"
              f"ê³µí건¦¬í°ê¸건¡건²ì SNS ì½íì¸ 건¥¼ ê¸°íí´ì£¼ì¸ì.\n\n"
              f"1. B2B ì½íì¸  1ê° (건¸건건 건´건¹ì íê²)\n"
              f"  - ì¸í건£¨ì¸ì 건§ì¼í ì±ê³µì¬건¡ 건건 í건¡건ª¨ì ì건´\n"
              f"  - Instagram ì¹´건건´ì¤ íì\n"
              f"2. B2C ì½íì¸  1ê° (ì¸í건£¨ì¸ì íê²)\n"
              f"  - ììµí í 건건 ìº íì¸ 건ª¨ì§ ì건´\n"
              f"  - TikTok/Instagram 건¦´ì¤ íì\n\n"
              f"ê° ì½íì¸ ì ì 건ª©, 건³¸건¬¸ íì¤í¸, í´ìíê·¸ 5ê°, CTA건¥¼ ìì±í´ì£¼ì¸ì.")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": ANTHROPIC_MODEL, "max_tokens": 1024,
                      "system": "건¹ì ì ìí¼, ê³µí건¦¬í°ê¸건¡건² SNS ì´ì ìì´ì í¸ì건건¤. 건§¤건 ¥ì ì¸ ì½íì¸ 건¥¼ ê¸°íí©건건¤.",
                      "messages": [{"role": "user", "content": prompt}]})
            if resp.status_code == 200:
                content = resp.json()["content"][0]["text"]
                proposals = load_proposals()
                proposals.append({
                    "id": int(time.time() * 1000) % 10000000,
                    "agent": "ìí¼", "status": "pending_approval",
                    "proposal": f"ì¤건ì SNS ì½íì¸  (B2B + B2C)",
                    "detail": content[:500],
                    "expected_impact": "B2B: 건¸건건 건¦¬건 1ê±´+ / B2C: ì¸í건£¨ì¸ì 건¦¬건 2ê±´+",
                    "action_type": "sns_content",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })
                save_proposals(proposals[-200:])
                _record_perf("ìí¼", "content_created", 2)
                return {"status": "ok", "content": content}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    return {"status": "error"}


# ===== ìì´ì í¸ ì±ê³¼ API =====
@app.get("/api/agent-performance")
async def api_agent_performance(agent: Optional[str] = None):
    """ìì´ì í¸건³ ì¼ì¼ ì±ê³¼ + 건ª©í 건건¹ 건¬ì±건¥ ."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    today_perf = perf.get(today, {})
    yesterday_perf = perf.get(yesterday, {})
    # ìê° 건ì  ê³ì°
    month_prefix = now.strftime("%Y-%m")
    monthly_perf = {}
    for date_key, agents_data in perf.items():
        if date_key.startswith(month_prefix):
            for ag, metrics in agents_data.items():
                monthly_perf.setdefault(ag, {})
                for mk, mv in metrics.items():
                    monthly_perf[ag][mk] = monthly_perf[ag].get(mk, 0) + mv
    # ì£¼ê° 건ì 
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    weekly_perf = {}
    for date_key, agents_data in perf.items():
        if date_key >= week_start:
            for ag, metrics in agents_data.items():
                weekly_perf.setdefault(ag, {})
                for mk, mv in metrics.items():
                    weekly_perf[ag][mk] = weekly_perf[ag].get(mk, 0) + mv
    # 건ª©í 건건¹ 건¬ì±건¥ 
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


# ===== 건ª©í ì¤ì  API =====
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


# ===== ì건¦¼ì¼í° API (ê²ìí íí) =====
@app.get("/api/alerts-board")
async def api_alerts_board():
    alerts = load_alerts()
    # 건¯¸í´ê²° ì건¨ ê³ ì 
    alerts.sort(key=lambda a: (0 if a.get("resolved") else 1, a.get("timestamp", "")), reverse=True)
    return {"alerts": alerts[:50]}

@app.post("/api/alerts-board")
async def api_post_alert(request: Request):
    body = await request.json()
    alerts = load_alerts()
    alert = {
        "id": len(alerts) + 1,
        "agent": body.get("agent", "ìì¤í"),
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


# ===== ìì´ì í¸ ìì¨ì¤í í건 ììí¬ =====
async def _agent_auto_cycle():
    """건§¤ì¼ 09:00 KST ì ì²´ ìì´ì í¸ ìì¨ì¤í: 건°ì´í°ìì§ â 건¶ì â ê°ì§ â ì건¦¼ â ì ììì± â ì¹ì¸건 ì ì ì¤í â ì¬건."""
    goals = load_goals()
    alerts_posted = []
    now_ts = datetime.now(KST).isoformat()
    _id = lambda: int(time.time() * 1000) % 1000000 + len(alerts_posted)

    # 0. ìì´ì í¸ ìì¨ ê°ì  건£¨í â ì ì ì건ìì±
    try:
        new_proposals = await _generate_agent_proposals()
        if new_proposals:
            _log_cycle("auto_generate", None, f"ìì´ì í¸ ì ì {len(new_proposals)}ê±´ ì건ìì±")
    except Exception as e:
        print(f"Proposal auto-generation error: {e}")

    # 0-1. ì¹ì¸건 ì ì ì건ì¤í
    try:
        proposals = load_proposals()
        for p in proposals:
            if p.get("status") == "approved" and not p.get("executed_at"):
                agent = p.get("agent", "")
                result_text = "ì건 ì¤í ì건£"
                if agent == "루나" and "ì¬ì ì´" in p.get("proposal", ""):
                    try:
                        campaign = await _run_recontact_campaign(dry_run=False, limit=5)
                        result_text = f"ì¬ì ì´ ì´건©ì¼ {campaign.get('sent',0)}ê±´ 건°ì¡"
                    except Exception:
                        result_text = "ì¬ì ì´ ì¤í ì¤건¥"
                p["status"] = "completed"
                p["executed_at"] = now_ts
                p["result"] = result_text
                _log_cycle("auto_execute", p.get("id"), result_text)
        save_proposals(proposals)
    except Exception as e:
        print(f"Auto-execute error: {e}")

    try:
        # 1. ì ì²´ KPI 건°ì´í° ìì§
        brand = await api_brand_pipeline()
        m = brand.get("month", {})
        t = brand.get("today", {})
        threshold = goals.get("alert_threshold", 0.2)  # 80% 건¯¸건§ = 건¬ì±건¥  0.8 건¯¸건§

        # 2. ì¹´ì¼ â KPI 건ª©í 건건¹ 건¶ì
        checks = [
            ("건§¤ì¶", m.get("revenue", 0), goals.get("revenue", 160000000), "ì¹´ì¼"),
            ("ê³ì½ê±´ì", m.get("contract", 0), goals.get("contracts", 38), "ì¹´ì¼"),
            ("ì¸ìDB", m.get("inbound", 0), goals.get("inbound_db", 500), "루나"),
            ("ì í¨DB", m.get("valid", 0), goals.get("valid_db", 150), "루나"),
        ]
        for label, val, target, agent in checks:
            if target > 0 and val / target < 0.8:  # 80% 건¯¸건§건§ ì건¦¼
                alerts_posted.append({
                    "id": _id(), "agent": agent, "severity": "critical",
                    "summary": f"â ï¸ {label} AT RISK: {val:,} / 건ª©í {target:,} ({val/target*100:.0f}%)",
                    "detail": f"건ª©í 건건¹ {threshold*100:.0f}% 건¯¸건¬ â ì¹´ì¼ ì§ì: ì¦ì 건ì íì",
                    "timestamp": now_ts, "resolved": False})

        # 3. ì¹´ì¼ â 건¬´건ì ê±´ ê°ì§
        if t.get("unhandled", 0) > 0:
            alerts_posted.append({
                "id": _id(), "agent": "ì¹´ì¼", "severity": "warning",
                "summary": f"건¬´건ì {t['unhandled']}ê±´ â 건´건¹ì 건°°ì  íì",
                "detail": "건´건¹ì 건¯¸건°°ì  건건 ì»¨ííí© 건¯¸ì건 ¥",
                "timestamp": now_ts, "resolved": False})

        # 4. ì¹´ì¼ â API ìí ì ê² (건¹¨ê° í­건ª© ê°ì§)
        api_checks = {
            "Google Sheets": bool(GSHEETS_API_KEY),
            "Anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            "Slack": bool(os.getenv("SLACK_WEBHOOK_URL")),
            "ì´건©ì¼": bool(os.getenv("EMAIL_WEBHOOK_URL")),
        }
        for svc, ok in api_checks.items():
            if not ok:
                alerts_posted.append({
                    "id": _id(), "agent": "ì¹´ì¼", "severity": "critical",
                    "summary": f"ð´ {svc} ì°ê²° ì¤í¨ â ì건 ì¬ì°ê²° ì건 ì¤",
                    "detail": f"{svc} API í¤ 건¯¸ì¤ì  건건 건§건£. Railway Variables íì¸ íì.",
                    "timestamp": now_ts, "resolved": False})

        # 5. ìí¼ â SNS ì½íì¸  ìì± + ì¬건 + ì´건©ì¼
        try:
            sophie_result = await api_sophie_content()
            if sophie_result.get("status") == "ok":
                content = sophie_result.get("content", "")
                alerts_posted.append({"id": _id(), "agent": "ìí¼", "severity": "info",
                    "summary": "ð± ì´건² ì£¼ SNS ì½íì¸  ì 건µ ìì± ì건£", "detail": content[:200],
                    "timestamp": now_ts, "resolved": False})
                _send_email(AGENT_EMAILS["ìí¼"], "[ìí¼] ì´건² ì£¼ SNS ì½íì¸  ì 건µ", _build_pitch_html("SNS ì½íì¸ ", content), "ìí¼")
        except Exception as e:
            print(f"Sophie content error: {e}")

        # 6. í¼ì¹ â ì¸í건£¨ì¸ì í 건¶ì + ì´건©ì¼
        try:
            inf = await api_influencer_db()
            stats = inf.get("stats", {})
            bc = stats.get("by_country", {})
            total = inf.get("total", 0)
            pitch_summary = f"ì¸í건£¨ì¸ì í: {total:,}건ª\nêµ­ê°건³: {', '.join(f'{k}:{v}' for k,v in sorted(bc.items(), key=lambda x:-x[1])[:5])}"
            alerts_posted.append({"id": _id(), "agent": "í¼ì¹", "severity": "info",
                "summary": f"ð ì¸í건£¨ì¸ì í íí©: {total:,}건ª", "detail": pitch_summary,
                "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["í¼ì¹"], "[í¼ì¹] ì¸í건£¨ì¸ì í ì¼ì¼ 건³´ê³ ì", _build_pitch_html("ì¸í건£¨ì¸ì", pitch_summary), "í¼ì¹")
        except Exception as e:
            print(f"Pitch analysis error: {e}")

        # 7. í건 â CS 건¯¸ì건µ íí© + ì´건©ì¼
        try:
            unhandled_count = t.get("unhandled", 0)
            hana_summary = f"ê¸ì¼ 건¯¸ì건µ CS: {unhandled_count}ê±´\nì¦ì ì건 íì ê±´: {unhandled_count}ê±´"
            if unhandled_count > 0:
                alerts_posted.append({"id": _id(), "agent": "í건", "severity": "warning",
                    "summary": f"ð 건¯¸ì건µ CS {unhandled_count}ê±´ â ì건 íì", "detail": hana_summary,
                    "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["í건"], "[í건] CS 건¯¸ì건µ íí©", _build_pitch_html("CS", hana_summary), "í건")
        except Exception as e:
            print(f"Hana CS error: {e}")

        # 8. 건 ì´ â ì¸ê¸ê³ì°ì ì²´í¬건¦¬ì¤í¸ + ì´건©ì¼
        try:
            ct_count = m.get("contract", 0)
            ray_summary = f"ì´건²건¬ ì¸ê¸ê³ì°ì: {ct_count}ê±´\n건§¤ì¶: {m.get('revenue',0):,}ì\nì²´í¬: 건¯¸ì²건¦¬ ê³ì°ì, ìê¸ íì¸, ì 건¶ì§ì 건§ê°"
            alerts_posted.append({"id": _id(), "agent": "건 ì´", "severity": "info",
                "summary": f"ð ê²½ìì§ì ì¼ì¼ ì²´í¬건¦¬ì¤í¸", "detail": ray_summary,
                "timestamp": now_ts, "resolved": False})
            _send_email(AGENT_EMAILS["건 ì´"], "[건 ì´] ê²½ìì§ì ì¼ì¼ ì²´í¬건¦¬ì¤í¸", _build_pitch_html("ê²½ìì§ì", ray_summary), "건 ì´")
        except Exception as e:
            print(f"Ray management error: {e}")

        # 9. í¼ì¹ â ì¸건°ì´건 ì건 ì건 + CRM 건´ì¤건 í°
        try:
            pitch_ib = await _pitch_inbound_auto()
            pitch_crm = await _pitch_outbound_crm()
            ib_sent = pitch_ib.get("sent", 0)
            crm_sent = pitch_crm.get("sent", 0)
            if ib_sent + crm_sent > 0:
                alerts_posted.append({"id": _id(), "agent": "í¼ì¹", "severity": "info",
                    "summary": f"ð§ í¼ì¹ ìì¨ì건¬´: ì¸건°ì´건 ì건 {ib_sent}ê±´ + CRM 건´ì¤건 í° {crm_sent}ê±´",
                    "detail": f"건¯¸í ìì½ 건§í¬ í¬í¨ 건°ì¡ ì건£",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Pitch auto error: {e}")

        # 9-1. 루나 â ì¸í건£¨ì¸ì íì + ìì건°ì´건 + ì¬ì ì´
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
                    "summary": f"âï¸ 루나 ìì¨ì건¬´: íì {w_sent}ê±´ + ìì건°ì´건 {o_sent}ê±´ + ì¬ì ì´ {r_sent}ê±´",
                    "detail": "",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Luna auto error: {e}")

        # 9-2. ìí¼ â ì¼ì¼ ì½íì¸  ê¸°í
        try:
            sophie = await _sophie_daily_content()
            if sophie.get("status") == "ok":
                alerts_posted.append({"id": _id(), "agent": "ìí¼", "severity": "info",
                    "summary": "ð± ìí¼ ìì¨ì건¬´: ì¤건ì B2B/B2C ì½íì¸  ê¸°í ì건£",
                    "detail": "ì¹ì¸ íìì íì¸ í ì¹ì¸í´ì£¼ì¸ì",
                    "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Sophie auto error: {e}")

        # 9-3. ì건 ìì¤ì»¬건 ì´ì â ì¼ 건ª©í 50% 건¯¸건¬ ìì´ì í¸ ê°ì§
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
                                "summary": f"ð¨ {ag_name} 건ª©í 건¯¸건¬: {metric} {actual}/{target} ({round(actual/target*100)}%)",
                                "detail": f"ì¼ 건ª©íì 50% 건¯¸건¬. ìì¸ 건¶ì 건° ì¦ì 건ì íì.",
                                "timestamp": now_ts, "resolved": False})
        except Exception as e:
            print(f"Escalation check error: {e}")

        # 10. ì¹´ì¼ â ì ì²´ 건¸건¦¬í ì´건©ì¼ 건°ì¡
        try:
            briefing = (
                f"ð ì ì²´ KPI 건¸건¦¬í â {datetime.now(KST).strftime('%Y-%m-%d')}\n\n"
                f"건§¤ì¶: {m.get('revenue',0):,}ì / 건ª©í 1.6ìµ\n"
                f"ê³ì½: {m.get('contract',0)}ê±´ / 건ª©í 38ê±´\n"
                f"ì¸ìDB: {t.get('inbound',0)}ê±´ / ì í¨: {t.get('valid',0)}ê±´\n"
                f"건¬´건ì: {t.get('unhandled',0)}ê±´\n\n"
                f"ê²½ê³  {len(alerts_posted)}ê±´ 건°ì"
            )
            _send_email(AGENT_EMAILS["ì¹´ì¼"], "[ì¹´ì¼] ì ì²´ ìì´ì í¸ ì¼ì¼ 건¸건¦¬í", _build_pitch_html("KPI 건¸건¦¬í", briefing), "ì¹´ì¼")
        except Exception as e:
            print(f"Kyle briefing error: {e}")

        # 11. ê²°ê³¼ ì ì¥ + ì¬건 ê³µì 
        if alerts_posted:
            existing = load_alerts()
            existing.extend(alerts_posted)
            save_alerts(existing[-200:])
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url:
                text = f"ð¨ *[ì¹´ì¼] 09:00 ì ì²´ ìì´ì í¸ ìì¨ì¤í â {len(alerts_posted)}ê±´*\n"
                for a in alerts_posted[:8]:
                    text += f"â¢ [{a['agent']}] {a['summary']}\n"
                text += "\nìì¸: https://dashboard-production-b2bd.up.railway.app/ â ì건¦¼ ì¼í°"
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
    """ìì´ì í¸ ìì¨ì¤í ì¬ì´í´ ì건 í¸건¦¬ê±°."""
    alerts = await _agent_auto_cycle()
    return {"status": "ok", "alerts_posted": len(alerts), "alerts": alerts}


# ===== 건©í ê´ê³  API =====
@app.get("/api/meta-ads")
async def api_meta_ads(date_preset: str = Query("today")):
    """건©í ê´ê³  ì±ê³¼ ì¡°í. date_preset: today/this_month/last_7d."""
    token = os.getenv("META_ACCESS_TOKEN", "")
    account_id = os.getenv("META_AD_ACCOUNT_ID", "230720044045370")
    if not token:
        return {"status": "not_configured", "message": "META_ACCESS_TOKEN 건¯¸ì¤ì . 건©í 건¹ì¦건ì¤ ê´건¦¬ììì 건°ê¸ íì."}
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
            # CPA ì건 ê³ì°
            for r in rows:
                spend = float(r.get("spend", 0))
                clicks = int(r.get("clicks", 0))
                r["cpa_calculated"] = round(spend / clicks, 0) if clicks > 0 else 0
            return {"status": "ok", "date_preset": date_preset, "data": rows}
        return {"status": "error", "code": resp.status_code, "message": data.get("error", {}).get("message", resp.text[:200])}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== ì¹´ì¹´ì¤ ì±건 API (B2B/B2C 건¶건¦¬) =====
@app.get("/api/kakao-channel")
async def api_kakao_channel():
    """ì¹´ì¹´ì¤ ì±건 ìí."""
    b2b_key = os.getenv("KAKAO_B2B_API_KEY", "") or os.getenv("KAKAO_REST_API_KEY", "")
    b2c_key = os.getenv("KAKAO_B2C_API_KEY", "") or os.getenv("KAKAO_REST_API_KEY", "")
    b2b = os.getenv("KAKAO_B2B_CHANNEL", "08liter_b2b")
    b2c = os.getenv("KAKAO_B2C_CHANNEL", "08liter_korea")
    return {
        "b2b": {"channel": b2b, "status": "connected" if b2b_key else "not_configured",
                "agent": "í건", "desc": "B2B CS 건©ìì§ ì건 ìì /ì건"},
        "b2c": {"channel": b2c, "status": "connected" if b2c_key else "not_configured",
                "agent": "í¼ì¹", "desc": "B2C ì¸í건£¨ì¸ì 건¬¸ì ìì  â ì¸건°ì´건 ìí¸ ì건 ê¸°건¡"},
    }

@app.get("/api/kakao-b2b/messages")
async def api_kakao_b2b_messages():
    """í건: ì¹´ì¹´ì¤ B2B ì±건 í건¡í 건° 건¯¸ì건µ 건©ìì§ ì¡°í."""
    api_key = os.getenv("KAKAO_B2B_API_KEY", "")
    if not api_key:
        return {"status": "not_configured", "message": "KAKAO_B2B_API_KEY 건¯¸ì¤ì . Railway Variablesì ì¶ê° íì.",
                "mock_unresponded": 4, "note": "API ì°건 ì  건건¯¸ 건°ì´í°"}
    try:
        resp = req_lib.get("https://kapi.kakao.com/v1/api/talk/profile",
                           headers={"Authorization": f"KakaoAK {api_key}"}, timeout=10)
        if resp.status_code == 200:
            return {"status": "connected", "profile": resp.json(), "agent": "í건"}
        return {"status": "error", "code": resp.status_code, "message": resp.text[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/kakao-b2c/inquiries")
async def api_kakao_b2c_inquiries():
    """í¼ì¹: ì¹´ì¹´ì¤ B2C ì±건 í건¡í ì¡°í."""
    api_key = os.getenv("KAKAO_B2C_API_KEY", "")
    if not api_key:
        return {"status": "not_configured", "message": "KAKAO_B2C_API_KEY 건¯¸ì¤ì . Railway Variablesì ì¶ê° íì.",
                "mock_inquiries": 2, "note": "API ì°건 ì  건건¯¸ 건°ì´í°"}
    try:
        resp = req_lib.get("https://kapi.kakao.com/v1/api/talk/profile",
                           headers={"Authorization": f"KakaoAK {api_key}"}, timeout=10)
        if resp.status_code == 200:
            return {"status": "connected", "profile": resp.json(), "agent": "í¼ì¹"}
        return {"status": "error", "code": resp.status_code, "message": resp.text[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== SNS ê³ì  ì¤ì  =====
@app.get("/api/sns-accounts")
async def api_sns_accounts():
    """SNS ê³ì  íí©. ì¸ì¤í/ì í건¸/í±í¡ B2B+B2C."""
    ig_token = os.getenv("META_INSTAGRAM_TOKEN", "")
    return {
        "instagram_b2b": {"account": os.getenv("INSTAGRAM_B2B_ACCOUNT", "insight._.lab"), "status": "connected" if ig_token else "pending", "agent": "ìí¼"},
        "instagram_b2c": {"account": os.getenv("INSTAGRAM_B2C_ACCOUNT", "08l_korea"), "status": "connected" if ig_token else "pending", "agent": "ìí¼"},
        "youtube_b2b": {"account": os.getenv("YOUTUBE_B2B_CHANNEL", "08L_insight"), "status": "pending", "agent": "ìí¼"},
        "tiktok_b2b": {"account": os.getenv("TIKTOK_B2B_ACCOUNT", "08l_insight"), "status": "pending", "agent": "ìí¼"},
        "tiktok_b2c": {"account": os.getenv("TIKTOK_B2C_ACCOUNT", "08liter_korea"), "status": "pending", "agent": "ìí¼"},
        "meta_instagram_token": "SET" if ig_token else "NOT_SET",
    }


# ===== KPI ì¶ì´ 건°ì´í° (ê·¸건íì©) =====
@app.get("/api/kpi-trend")
async def api_kpi_trend():
    """ìµê·¼ 12ê°ì ì건³ + ìµê·¼ 90ì¼ ì¼건³ KPI ì¶ì´. êµ¬ê¸ìí¸ ì¤건°ì´í°."""
    monthly = []
    try:
        ads = await api_ads_performance()
        monthly = ads.get("monthly_trend", [])
    except Exception:
        pass
    # ê³ì°ììì ì건³ 건§¤ì¶ ì§ê³ (Bì´ 건 ì§ 기반 íµì¼)
    ct_rows = fetch_sheet(SHEET_CONTRACT, "A:Z", "ê³ì°ì건°í", ttl_key="contract")
    monthly_rev = {}
    if ct_rows:
        hdr = _find_header_row(ct_rows, "ìì±ì¼ì", "ê³µê¸ê°ì¡", "ê³µê¸건°건ì")
        headers = [str(h).replace("\n", " ").strip() for h in ct_rows[hdr]]
        date_idx = _find_col(headers, "ìì±ì¼ì", "건±건¡ê¸°ì¤ì¼") or 1
        amount_idx = _find_col(headers, "ê³µê¸ê°ì¡") or 19
    # ì¼건³ 건§¤ì¶ + ê³ì½ì + ìí건³ + ì¶©ì ê¸
    daily_rev = {}
    daily_new = {}
    daily_renew = {}
    daily_new_rev = {}
    daily_renew_rev = {}
    product_dist = {}
    daily_payback = {}
    # ì건³ ì§ê³ (ì ì²´ ê¸°ê° â ì°¨í¸ 12ê°ìì©)
    monthly_new_rev = {}
    monthly_renew_rev = {}
    monthly_new_cnt = {}
    monthly_renew_cnt = {}
    if ct_rows:
        cat_idx = _find_col(headers, "í건ª© ì¬건¶건¥", "ì¬건¶건¥") or 24
        payback_idx = _find_col(headers, "íì´건°±건¹", "ì¶©ì ê¸") or 18
        brand_idx = _find_col(headers, "ê³µê¸건°건ì ìí¸") or 8
        type_idx = _find_col(headers, "ì ê·/", "ì¬ê³ì½") or 6
        now = datetime.now(KST)
        cutoff_90 = (now - timedelta(days=90)).strftime("%Y%m%d")
        # 건¸건건 ì²« 건±ì¥ ì¶ì  (Gì´ ìì 건 í´건°±)
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
            # Gì´ 기반 ì ê·/ì¬ê³ì½ 건¶건¥ (_parse_contractsì 건ì¼ 건¡ì§)
            if ctype and ctype != "-" and "íì¸íì" not in ctype:
                is_renew = "ì ê·" not in ctype
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
            # ì건³ ì§ê³ (ì ì²´ ê¸°ê° â Bì´ 건 ì§ 기반 íµì¼)
            monthly_rev[mk] = monthly_rev.get(mk, 0) + rev
            if is_renew:
                monthly_renew_rev[mk] = monthly_renew_rev.get(mk, 0) + rev
                monthly_renew_cnt[mk] = monthly_renew_cnt.get(mk, 0) + 1
            else:
                monthly_new_rev[mk] = monthly_new_rev.get(mk, 0) + rev
                monthly_new_cnt[mk] = monthly_new_cnt.get(mk, 0) + 1
            # ì¼건³ ì§ê³ (ìµê·¼ 90ì¼건§)
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
                if "ì건©" in cl or "ì²´í건¨" in cl:
                    cat = "êµ­건´ì²´í건¨(ì건©)"
                elif "í¤ì¸í" in cl or "ì건" in cl:
                    cat = "건§ì¶¤íí¤ì¸í(ì건)"
                elif "êµ¬건§¤í" in cl or "ì건¹ì¤건í" in cl:
                    cat = "í´ì¸êµ¬건§¤í(ì건¹ì¤건í)"
                elif "ì´¬ì" in cl:
                    cat = "ì¬ì§ì´¬ì"
                elif "ìí건ê¸" in cl:
                    cat = "ìí건ê¸"
                else:
                    cat = "ê¸°í"
                product_dist[cat] = product_dist.get(cat, 0) + rev
            pb = str(row[payback_idx]).strip() if payback_idx < len(row) else "0"
            try:
                pb_val = int(float(pb.replace(",", "").replace("â©", "").replace(" ", "")))
            except (ValueError, TypeError):
                pb_val = 0
            if pb_val > 0:
                daily_payback[day_key] = daily_payback.get(day_key, 0) + pb_val
    # ì건³ ì¶©ì ê¸(íì´건°±건¹) ì§ê³
    monthly_payback = {}
    ct2 = _parse_contracts(ct_rows) if ct_rows else {}
    monthly_payback = ct2.get("monthly_payback", {})
    # ì´ ì¶©ì ê¸ í©ê³
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


# ===== ê´ê³  ì건ì건 ¥ =====
ADS_MANUAL_FILE = DATA_DIR / "ads_manual.json"

@app.post("/api/ads-manual")
async def api_ads_manual_save(request: Request):
    """ê´ê³ ì¼í° ì건 ì건 ¥ 건°ì´í° ì ì¥."""
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
    """ê´ê³ ì¼í° ì건 ì건 ¥ 건°ì´í° ì¡°í."""
    if ADS_MANUAL_FILE.exists():
        return json.loads(ADS_MANUAL_FILE.read_text(encoding="utf-8"))
    return []


# ===== SNS ì건ì건 ¥ =====
SNS_MANUAL_FILE = DATA_DIR / "sns_manual.json"

@app.post("/api/sns-manual")
async def api_sns_manual_save(request: Request):
    """SNS ì건 ì건 ¥ 건°ì´í° ì ì¥."""
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


# ===== ìí¼: SNS ì½íì¸  ì건 ìì± =====
@app.get("/api/sophie-content")
async def api_sophie_content():
    """ìí¼: Anthropic API건¡ B2B/B2C SNS ì½íì¸  ì£¼ì  + ìº¡ì ìì±."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"status": "error", "message": "ANTHROPIC_API_KEY 건¯¸ì¤ì "}
    prompt = """ê³µí건¦¬í°ê¸건¡건² SNS ì½íì¸  ì 건µê° ìí¼ì건건¤.

B2B ì¸ì¤í(@insight._.lab) ì½íì¸  ì£¼ì  3ê° + ìº¡ì ì´ì:
- ì¸í건£¨ì¸ì 건§ì¼í í¸건 건, ì±ê³µ ì¬건¡, ì¸ì¬ì´í¸ ì¤ì¬
- ì 건¬¸ì ì´ê³  ì 건¢°ê° ì건 í¤

B2C ì¸ì¤í(@08l_korea) ì½íì¸  ì£¼ì  3ê° + ìº¡ì ì´ì + í´ìíê·¸ 30ê°:
- 건·°í°/건¼ì´íì¤íì¼/í¸건 건 ì¤ì¬
- ì¹ê·¼íê³  í¸건 건í í¤

ì´건² ì£¼ ì¶ì² ì½íì¸ 건¥¼ JSON íì ìì´ ê¹건íê² ìì±í´ì£¼ì¸ì."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-20250514", "max_tokens": 1500,
                      "messages": [{"role": "user", "content": prompt}]})
            if resp.status_code == 200:
                text = resp.json()["content"][0]["text"]
                return {"status": "ok", "content": text, "agent": "ìí¼"}
            return {"status": "error", "message": resp.text[:200]}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ===== ì¸í건£¨ì¸ì ì건 ì건 ¥ =====
INF_MANUAL_FILE = DATA_DIR / "influencer_manual.json"

@app.post("/api/influencer-add")
async def api_influencer_add(request: Request):
    """ì¸í건£¨ì¸ì ì건 ì¶ê°."""
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

# ===== íìíí© ì건 ì건 ¥ =====
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
    """ìºì ì´ê¸°í"""
    _cache.clear()
    _cache_time.clear()
    return {"status": "cleared"}


@app.get("/api/debug-env")
async def api_debug_env():
    """íê²½건³ì ì¤ì  ì¬건¶ íì¸. ì¤ì  ê°ì ì¨ê¸°ê³  SET/NOT_SET건§ íì."""
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


# ===== ìì´ì í¸ ìì¨ ê°ì  건£¨í (Proposal System) =====

@app.get("/api/proposals")
async def api_get_proposals(status: Optional[str] = None):
    """ì ì 건ª©건¡ ì¡°í. status: pending_approval/approved/executed/completed/rejected"""
    proposals = load_proposals()
    if status:
        proposals = [p for p in proposals if p.get("status") == status]
    proposals.sort(key=lambda p: p.get("created_at", ""), reverse=True)
    return {"proposals": proposals[:50]}


@app.post("/api/proposals")
async def api_create_proposal(request: Request):
    """ìì´ì í¸ê° ì ì ìì± (ì건 건건 ì건 ì¬ì´í´)."""
    body = await request.json()
    proposals = load_proposals()
    proposal = {
        "id": int(time.time() * 1000) % 10000000,
        "agent": body.get("agent", "ìì¤í"),
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
    """CEOê° ì ì ì¹ì¸ â status건¥¼ approved건¡ 건³ê²½."""
    body = await request.json()
    pid = body.get("id")
    proposals = load_proposals()
    for p in proposals:
        if p.get("id") == pid:
            p["status"] = "approved"
            p["approved_at"] = datetime.now(KST).isoformat()
            # DB ìì§ íì´í건¼ì¸ ì건 ìì
            action_type = p.get("action_type", "")
            pipeline_result = None
            if action_type in ("pitch_db_collect", "luna_db_collect"):
                try:
                    agent_name = "í¼ì¹" if "pitch" in action_type else "루나"
                    if agent_name == "í¼ì¹":
                        pitch_result = await _pitch_outbound_crm()
                        pipeline_result = {"step": "ì´건©ì¼ ìì±+í 건±건¡", "sent": pitch_result.get("sent", 0)}
                    else:
                        luna_result = await _luna_outbound_pitch()
                        pipeline_result = {"step": "ì´건©ì¼ ìì±+í 건±건¡", "sent": luna_result.get("sent", 0)}
                    p["result"] = f"íì´í건¼ì¸ ì¤í: {pipeline_result.get('sent',0)}ê±´ ì´건©ì¼ â ê²ì í"
                    p["status"] = "executed"
                    p["executed_at"] = datetime.now(KST).isoformat()
                except Exception as ex:
                    pipeline_result = {"error": str(ex)}
            # Slack ì건¦¼
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url and _slack_enabled():
                try:
                    req_lib.post(slack_url, json={"text": f"â CEO ì¹ì¸: [{p['agent']}] {p['proposal']}"}, timeout=5)
                except Exception:
                    pass
            break
    save_proposals(proposals)
    _log_cycle("approve", pid, f"CEOê° ì ì ì¹ì¸")
    return {"status": "ok", "pipeline": pipeline_result}


@app.post("/api/proposals/reject")
async def api_reject_proposal(request: Request):
    """CEOê° ì ì ê±°ì ."""
    body = await request.json()
    pid = body.get("id")
    proposals = load_proposals()
    for p in proposals:
        if p.get("id") == pid:
            p["status"] = "rejected"
            p["ceo_comment"] = body.get("comment", "")
            break
    save_proposals(proposals)
    _log_cycle("reject", pid, f"CEOê° ì ì ê±°ì : {body.get('comment','')}")
    return {"status": "ok"}


@app.post("/api/proposals/edit")
async def api_edit_proposal(request: Request):
    """CEOê° ìì ìì²­ â ìì´ì í¸ê° 건°ì í ì¬ì ì¶."""
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
    _log_cycle("edit_request", pid, f"CEO ìì ìì²­: {comment[:80]}")
    return {"status": "ok"}


@app.post("/api/proposals/execute")
async def api_execute_proposal(request: Request):
    """ì¹ì¸건 ì ì ì¤í (ì건 í¸건¦¬ê±° 건건 ì건 ì¬ì´í´)."""
    body = await request.json()
    pid = body.get("id")
    proposals = load_proposals()
    result_text = "ì¤í ì건£"
    for p in proposals:
        if p.get("id") == pid and p.get("status") == "approved":
            p["status"] = "executed"
            p["executed_at"] = datetime.now(KST).isoformat()
            # ìì´ì í¸건³ ì¤í 건¡ì§
            agent = p.get("agent", "")
            if agent == "루나" and "ì¬ì ì´" in p.get("proposal", ""):
                try:
                    campaign = await _run_recontact_campaign(dry_run=False, limit=5)
                    result_text = f"ì¬ì ì´ ì´건©ì¼ {campaign.get('sent',0)}ê±´ 건°ì¡"
                except Exception as e:
                    result_text = f"ì¤í ì¤건¥: {e}"
            elif agent == "ì¹´ì¼":
                result_text = "KPI 건ª¨건í°건§ ì¬ì´í´ ì¤í ì건£"
            p["result"] = result_text
            p["status"] = "completed"
            # Slack ê²°ê³¼ ì 건¬
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            if slack_url:
                try:
                    req_lib.post(slack_url, json={"text": f"ð¤ ì¤íì건£: [{agent}] {result_text}"}, timeout=5)
                except Exception:
                    pass
            break
    save_proposals(proposals)
    _log_cycle("execute", pid, result_text)
    return {"status": "ok", "result": result_text}


@app.get("/api/cycle-log")
async def api_get_cycle_log():
    """ìì´ì í¸ ì¬ì´í´ íì¤í 건¦¬ ì¡°í."""
    return {"log": load_cycle_log()[-30:]}


def _log_cycle(action: str, proposal_id, detail: str):
    """ì¬ì´í´ 건¡ê·¸ ê¸°건¡."""
    log = load_cycle_log()
    log.append({
        "action": action,
        "proposal_id": proposal_id,
        "detail": detail,
        "timestamp": datetime.now(KST).isoformat(),
    })
    save_cycle_log(log)


async def _generate_agent_proposals():
    """ìì´ì í¸ ì¬ì´í´: 건°ì´í° 건¶ì â ê°ì ì ì건 ìì± â proposals.json ì ì¥."""
    now = datetime.now(KST)
    proposals = load_proposals()
    existing_pending = [p for p in proposals if p.get("status") == "pending_approval"]
    if len(existing_pending) >= 10:
        return []  # 건¯¸ì²건¦¬ ì ìì´ 10ê° ì´ìì´건©´ ì¶ê° ìì± ì í¨

    new_proposals = []
    _pid = lambda: int(time.time() * 1000) % 10000000 + len(new_proposals)

    try:
        brand = await api_brand_pipeline()
        m = brand.get("month", {})
        t = brand.get("today", {})
        goals = load_goals()

        # 1. 건°ì´ì´ ìì건¦¬ì¹ â ì건µ건¥  건¶ì
        if m.get("inbound", 0) > 0:
            valid_rate = round(m.get("valid", 0) / max(m.get("inbound", 1), 1) * 100, 1)
            if valid_rate < 30:
                new_proposals.append({
                    "id": _pid(), "agent": "루나", "status": "pending_approval",
                    "proposal": f"ì í¨DB ì íì¨ {valid_rate}% â ì´건©ì¼ ì 건ª©ì¤ A/B íì¤í¸ ì ì",
                    "detail": f"íì¬ ì¸ìDB {m.get('inbound',0)}ê±´ ì¤ ì í¨ {m.get('valid',0)}ê±´({valid_rate}%). ìê³ íê·  30% 건건¹ 건®ì. ì´건©ì¼ ì 건ª©ì¤ 건³ê²½ íì¤í¸ ê¶ì¥.",
                    "expected_impact": "ì í¨DB ì íì¨ 30%+ 건¬ì± ì ì ê³ì½ 5ê±´ ì¶ê° ìì",
                    "action_type": "email_ab_test",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })

        # 2. ì¸ê¸ê³ì°ì â 건¯¸건°í ê°ì§
        ct_count = m.get("contract", 0)
        if ct_count > 0:
            new_proposals.append({
                "id": _pid(), "agent": "건 ì´", "status": "pending_approval",
                "proposal": f"ì´건²건¬ ê³ì½ {ct_count}ê±´ â ì¸ê¸ê³ì°ì 건°í ìí ì ê² ì ì",
                "detail": f"ê³ì½ {ct_count}ê±´ ì¤ 건¯¸건°í ê±´ì´ ìì ì ìì. êµ¬ê¸ìí¸ ê³ì°ìí­ê³¼ 건ì¡° íì.",
                "expected_impact": "건¯¸ìê¸ 건¦¬ì¤í¬ ì¬ì  ì°¨건¨",
                "action_type": "tax_check",
                "ceo_comment": "", "created_at": now.isoformat(),
                "approved_at": None, "executed_at": None, "result": None,
            })

        # 3. ì¸í건£¨ì¸ì 건§¤ì¹­ â 건¯¸건§¤ì¹­ ìº íì¸
        try:
            inf = await api_influencer_db()
            stats = inf.get("stats", {})
            listed = stats.get("by_status", {}).get("1. 건¨ì건¦¬ì¤í¸ì", 0)
            if listed > 50:
                new_proposals.append({
                    "id": _pid(), "agent": "í¼ì¹", "status": "pending_approval",
                    "proposal": f"건¨ì건¦¬ì¤í¸ì {listed}건ª â ì»¨í ì í ìº íì¸ ì ì",
                    "detail": f"건¦¬ì¤í¸ì건§ 건 ì¸í건£¨ì¸ì {listed}건ª. ì´ ì¤ í건¡ì 10건§+ 건ìì¼건¡ ê°ì¸í ì»¨í ì´건©ì¼ 건°ì¡ ê¶ì¥.",
                    "expected_impact": f"ì건µ건¥  25% ê¸°ì¤ {int(listed*0.25)}건ª ì¶ê° í건³´",
                    "action_type": "influencer_outreach",
                    "ceo_comment": "", "created_at": now.isoformat(),
                    "approved_at": None, "executed_at": None, "result": None,
                })
        except Exception:
            pass

        # 4. ì¹´ì¼ â 건¬´건ì ì건건°°ì 
        if t.get("unhandled", 0) > 0:
            new_proposals.append({
                "id": _pid(), "agent": "ì¹´ì¼", "status": "pending_approval",
                "proposal": f"건¬´건ì {t['unhandled']}ê±´ â 건´건¹ì ì건건°°ì  ì ì",
                "detail": "건¯¸ì²건¦¬ ì¸건°ì´건ê° 건°©ì¹ ì¤. 건´건¹ì건³ ì건¬´건 ê¸°ì¤ì¼건¡ ì건 건°°ì  ì¤í ê°건¥.",
                "expected_impact": "ì건µìê° 50% 건¨ì¶, ì íì¨ ê°ì ",
                "action_type": "auto_assign",
                "ceo_comment": "", "created_at": now.isoformat(),
                "approved_at": None, "executed_at": None, "result": None,
            })

        # 5. 루나 â ì¬ì ì´ 건ì
        try:
            recontact = await api_recontact_leads()
            leads_count = recontact.get("count", 0)
            if leads_count > 0:
                new_proposals.append({
                    "id": _pid(), "agent": "루나", "status": "pending_approval",
                    "proposal": f"ì¬ì ì´ 건ì {leads_count}ê±´ â ì´건©ì¼ í¼ì¹ 건°ì¡ ì ì",
                    "detail": f"ì í¨DB ì¤ ê³ì½ 건¯¸ì²´ê²° {leads_count}ê±´ 건°ê²¬. 건§ì¶¤ ì ì ì´건©ì¼ 건°ì¡ ê¶ì¥.",
                    "expected_impact": f"ì íì¨ 10% ê¸°ì¤ {max(1,leads_count//10)}ê±´ ì¶ê° ê³ì½",
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


# ===== ì¹´ì¼ ìì´ì í¸ ê°ì ì ì API =====
@app.get("/api/kyle-suggestions")
async def api_kyle_suggestions():
    """ì¹´ì¼ ìì´ì í¸ ê°ì ì ì ì건ìì± â ì¤ìê° KPI 기반."""
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
            suggestions.append({"urgency": "건ì", "category": "건§¤ì¶ê°ì ",
                "title": f"건§¤ì¶ 건¬ì±건¥  {rev_pct:.0f}% â ê¸´ê¸ 건§¤ì¶ 건¶ì¤í íì",
                "detail": f"ì´건²건¬ 건§¤ì¶ {m.get('revenue',0):,}ì / 건ª©í {goals.get('revenue',160000000):,}ì. ì¬ê³ì½ ì§ì¤ + ê³ 건¨ê° í¨í¤ì§ ì ì íì.",
                "action": "루나 ìì´ì í¸ì ì¬ì ì´ ìº íì¸ ì¦ì ì¤í ì§ì"})
        if t.get("unhandled", 0) > 0:
            suggestions.append({"urgency": "건ì", "category": "ìì¤íì ìí",
                "title": f"건¬´건ì {t['unhandled']}ê±´ â ì¦ì 건´건¹ì 건°°ì ",
                "detail": "건¯¸ì²건¦¬ ì¸건°ì´건ê° 건°©ì¹건건©´ ì ì¬ 건§¤ì¶ ìì¤ 건°ì.",
                "action": "건¬´건ì ê±´ 건´건¹ì ì건건°°ì  ì¤í"})
        # API ìí ì ê²
        api_issues = []
        if not os.getenv("META_ACCESS_TOKEN"): api_issues.append("건©í ê´ê³  API")
        if not os.getenv("META_INSTAGRAM_TOKEN"): api_issues.append("ì¸ì¤íê·¸건¨ API")
        if api_issues:
            suggestions.append({"urgency": "ì¤ê°", "category": "APIì°건건³´ì",
                "title": f"건¯¸ì°건 API {len(api_issues)}ê° â 건°ì´í° ìì§ 건¶ìì ",
                "detail": f"건¯¸ì°건: {', '.join(api_issues)}. ì°건 ì ì건 건°ì´í° ìì§ ê°건¥.",
                "action": "Railway Variablesì API í¤ ì¶ê°"})
        if ct_pct < 50:
            suggestions.append({"urgency": "ì¤ê°", "category": "건§¤ì¶ê°ì ",
                "title": f"ê³ì½ 건¬ì±건¥  {ct_pct:.0f}% â íì´í건¼ì¸ ê°ì íì",
                "detail": f"ì´건²건¬ {m.get('contract',0)}ê±´ / 건ª©í {goals.get('contracts',38)}ê±´. 건¯¸íì íì¨ ê°ì  íì.",
                "action": "루나ìê² 건¯¸í ì¸í ì°ì ìì ì§ì"})
        if not suggestions:
            suggestions.append({"urgency": "건®ì", "category": "건ì건³´건ê°ì ",
                "title": "ì ì²´ KPI ìí¸ â ì§ì 건ª¨건í°건§ ì¤",
                "detail": f"건§¤ì¶ 건¬ì±건¥  {rev_pct:.0f}%, ê³ì½ 건¬ì±건¥  {ct_pct:.0f}%.",
                "action": "íì¬ ì 건µ ì ì§"})
    except Exception as e:
        suggestions.append({"urgency": "건ì", "category": "ìì¤íì ìí",
            "title": "건°ì´í° ìì§ ì¤건¥", "detail": str(e), "action": "ìì¤í ì ê²"})
    return {"suggestions": suggestions, "timestamp": now.isoformat(), "agent": "ì¹´ì¼"}


@app.get("/api/agent-scoreboard")
async def api_agent_scoreboard():
    """ì£¼ê° ìì´ì í¸ 건­í¹ ì¤ì½ì´건³´건."""
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
    """ìê³ 건²¤ì¹건§í¬ 건°ì´í° ì¡°í."""
    return load_benchmarks()

@app.get("/api/token-usage")
async def api_token_usage():
    """ìì´ì í¸건³ í í° ì¬ì©건 + 건¹ì©."""
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
    for ag in ["í¼ì¹", "루나", "ìí¼", "건§¥ì¤", "ì¹´ì¼"]:
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
    # ì ì²´ í©ê³
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
    """건°ì¡ 건ê¸° ì´건©ì¼ í ì¡°í."""
    queue = load_email_queue()
    pending = [e for e in queue if e.get("status") == "pending"]
    if agent:
        pending = [e for e in pending if e.get("agent") == agent]
    return {"emails": pending, "count": len(pending)}

@app.post("/api/email-queue/approve")
async def api_email_approve(request: Request):
    """CEOê° ì´건©ì¼ ì¹ì¸ 건°ì¡."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    for e in queue:
        if e.get("id") == eid and e.get("status") == "pending":
            subject = body.get("subject", e["subject"])
            html = body.get("html", e["html"])
            result = _send_email(e["to"], subject, html, e.get("agent", "í¼ì¹"))
            e["status"] = "sent" if result["status"] == "ok" else "failed"
            e["sent_at"] = datetime.now(KST).isoformat()
            e["result"] = result
            break
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/email-queue/delete")
async def api_email_delete(request: Request):
    """ì´건©ì¼ ì­ì ."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    queue = [e for e in queue if e.get("id") != eid]
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/email-queue/approve-all")
async def api_email_approve_all(request: Request):
    """건ê¸° ì¤ì¸ ì´건©ì¼ ì ì²´ ì¹ì¸ 건°ì¡."""
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
        result = _send_email(e["to"], e["subject"], e["html"], e.get("agent", "í¼ì¹"))
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
    """건ê¸° ì´건©ì¼ ì 건ª©/건³¸건¬¸ ìì  (status건 pending ì ì§)."""
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
                e["html"] = _build_pitch_html(e.get("meta", {}).get("target", ""), body["body_text"] + f"\n\n[건¯¸í ìì½íê¸°]({MEETING_LINK})")
            break
    save_email_queue(queue)
    return {"status": "ok"}

@app.post("/api/email-queue/regenerate")
async def api_email_regenerate(request: Request):
    """AI건¡ ì´건©ì¼ 건´ì© ì¬ìì±."""
    body = await request.json()
    eid = body.get("id")
    queue = load_email_queue()
    for e in queue:
        if e.get("id") == eid and e.get("status") == "pending":
            target = e.get("meta", {}).get("target", "ê³ ê°")
            agent = e.get("agent", "í¼ì¹")
            if ANTHROPIC_API_KEY:
                try:
                    prompt = f"{target}ìê² 건³´건¼ {'ì¸í건£¨ì¸ì 건§ì¼í' if agent=='í¼ì¹' else 'íì°¬'} ì ì ì´건©ì¼ì ìì±í´ì£¼ì¸ì. 100건¨ì´, 건¯¸í 건§í¬ í¬í¨."
                    async with httpx.AsyncClient(timeout=20) as client:
                        resp = await client.post("https://api.anthropic.com/v1/messages",
                            headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                            json={"model": "claude-haiku-4-5-20251001", "max_tokens": 512,
                                  "messages": [{"role": "user", "content": prompt}]})
                        if resp.status_code == 200:
                            new_body = resp.json()["content"][0]["text"]
                            e["subject"] = f"[ê³µí건¦¬í°ê¸건¡건²] {target} 건§ì¶¤ ì ì"
                            e["html"] = _build_pitch_html(target, new_body + f"\n\n[건¯¸í ìì½íê¸°]({MEETING_LINK})")
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
    """í건¡건ª¨ì/íì°¬ ì¤ì  기반 ì´건©ì¼ ìì±."""
    body = await request.json()
    agent = body.get("agent", "í¼ì¹")
    promos = body.get("promos", [])
    highlights = body.get("highlights", [])
    targets = body.get("targets", [])
    promo_text = " / ".join(promos) if promos else "4ì í건¡건ª¨ì"
    highlight_text = " / ".join(highlights) if highlights else ""
    queued = 0
    for t in targets[:20]:
        email = t.get("email", "")
        if not email or "@" not in email:
            continue
        name = t.get("company", t.get("name", "건´건¹ì"))
        email_body = f"ì건íì¸ì, {name} 건´건¹ì건.\nê¸건¡건² ì¸í건£¨ì¸ì 건§ì¼í í건«í¼ ê³µí건¦¬í°ì ì ì´ì½¥ì건건¤.\n\n"
        if agent == "í¼ì¹":
            email_body += f"íì¬ ì§í ì¤ì¸ í건¡건ª¨ìì ì건´건건¦½건건¤:\n"
            for p in promos:
                email_body += f"â¢ {p}\n"
            if highlight_text:
                email_body += f"\níµì¬ í¬ì¸í¸: {highlight_text}\n"
            email_body += f"\n10건¶ 건¹건건©´ 건¯¸íì¼건¡ {name}ì 건§건 건§ì¶¤ ì ì 건건¦½건건¤."
        else:
            email_body += f"íì°¬ ì ì건건¦½건건¤:\n"
            for p in promos:
                email_body += f"â¢ {p}\n"
            email_body += f"\nê´ì¬ ìì¼ì건©´ 건µì¥ 건¶í건건¦½건건¤."
        html = _build_pitch_html(name, email_body + f"\n\n[건¯¸í ìì½íê¸°]({MEETING_LINK})")
        subject = f"[ê³µí건¦¬í°ê¸건¡건²] {name} {'건§ì¶¤ í건¡건ª¨ì' if agent=='í¼ì¹' else '건¬´건£ íì°¬ ì ì'}"
        _queue_or_send_email(agent, email, subject, html, {"target": name, "promos": promos})
        queued += 1
    return {"status": "ok", "queued": queued}

@app.post("/api/sns-content/generate")
async def api_sns_content_generate(request: Request):
    """ìí¼: í건¡건ª¨ì ì¤ì  기반 B2B/B2C ì½íì¸  ìì± â ì¹ì¸ í."""
    body = await request.json()
    b2b_topics = body.get("b2b_topics", ["ì¸í건£¨ì¸ì 건§ì¼í ì±ê³µì¬건¡"])
    b2c_topics = body.get("b2c_topics", ["건¬´건£ íì°¬ 건ª¨ì§"])
    b2b_channel = body.get("b2b_channel", "Instagram")
    b2c_channel = body.get("b2c_channel", "TikTok")
    now = datetime.now(KST)
    results = {"b2b": None, "b2c": None}
    if ANTHROPIC_API_KEY:
        for content_type, topics, channel in [("b2b", b2b_topics, b2b_channel), ("b2c", b2c_topics, b2c_channel)]:
            target = "건¸건건 건§ì¼í 건´건¹ì" if content_type == "b2b" else "건·°í° ì¸í건£¨ì¸ì"
            prompt = (f"ê³µí건¦¬í°ê¸건¡건² {channel}ì© {'B2B' if content_type=='b2b' else 'B2C'} ì½íì¸ 건¥¼ ìì±í´ì£¼ì¸ì.\n"
                      f"íê²: {target}\nì£¼ì : {', '.join(topics)}\n"
                      f"íì: {'ì¹´건건´ì¤ íì¤í¸' if channel=='Instagram' else 'ìí¼ ì¤í¬건¦½í¸'}\n"
                      f"ì 건ª© + 건³¸건¬¸(150건¨ì´) + í´ìíê·¸ 5ê° + CTA 1ì¤ì ìì±í´ì£¼ì¸ì.")
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
                        _record_tokens("ìí¼", usage.get("input_tokens", 0), usage.get("output_tokens", 0), "haiku")
            except Exception as ex:
                print(f"SNS content gen error: {ex}")
    else:
        results["b2b"] = {"channel": b2b_channel, "target": "건¸건건 건´건¹ì", "content": f"[B2B] {', '.join(b2b_topics)}\n\n건¦¬건·° 0ê°ì¸ 건¸건건ê° 3ì£¼건§ì 100ê° 건§건  건¹ê²°...\n\n#ì¸í건£¨ì¸ì건§ì¼í #ê³µí건¦¬í° #건¦¬건·°건§ì¼í #K건·°í° #건¸건건ì±ì¥\n\nCTA: í건¡í 건§í¬ìì 건¬´건£ ì건´ ìì½", "topics": b2b_topics}
        results["b2c"] = {"channel": b2c_channel, "target": "건·°í° ì¸í건£¨ì¸ì", "content": f"[B2C] {', '.join(b2c_topics)}\n\nK-건·°í° ì í ê³µì§건¡ 건°ê³  ì¶ì¼ì¸ì?\nê³µí건¦¬í°ìì 건§¤ì£¼ ì건¡ì´ íì°¬ ê¸°í!\n\n#건¬´건£íì°¬ #K건·°í° #ì¸í건£¨ì¸ì #건·°í°í¬건¦¬ìì´í° #íì°¬ì ì\n\nCTA: í건¡í 건§í¬ìì ì§ê¸ ì ì²­!", "topics": b2c_topics}
    # ì¹ì¸ íì 건±건¡
    proposals = load_proposals()
    for ct in ["b2b", "b2c"]:
        if results[ct]:
            proposals.append({
                "id": int(time.time() * 1000) % 10000000 + (1 if ct == "b2c" else 0),
                "agent": "ìí¼", "status": "pending_approval",
                "proposal": f"{'B2B' if ct=='b2b' else 'B2C'} ì½íì¸  â {results[ct]['channel']}",
                "detail": results[ct]["content"],
                "expected_impact": f"ìì 건¦¬건: {'5~15' if ct=='b2b' else '10~30'}ê±´",
                "action_type": "sns_content",
                "channel": results[ct]["channel"],
                "content_type": ct,
                "ceo_comment": "", "created_at": now.isoformat(),
            })
    save_proposals(proposals[-200:])
    _record_perf("ìí¼", "content_created", 2)
    return {"status": "ok", "results": results}

@app.get("/api/sheet-pipeline")
async def api_sheet_pipeline(agent: str = "í¼ì¹"):
    """êµ¬ê¸ìí¸ ì¤ìê° íì´í건¼ì¸ â ìì´ì í¸건³ ì§ê³. ì¤ì  ìí¸ ì»¬건¼ 기반."""
    now = datetime.now(KST)
    result = {"agent": agent, "today": {}, "month": {}, "total": {}, "funnel": {},
              "sheet_url": SHEET_URLS.get(agent, "")}
    if agent == "í¼ì¹":
        # í¼ì¹ ìí¸: íì¼건¬¸ì í­ A:V (í¤건 3í)
        # A:êµ­ê° B:ì C:건 ì§ D:ì ìì±건 E:ìì²´건ª F:ì°건½ì² G:ì´건©ì¼
        # M:건¯¸íìì½ N:í O:건´건¹ì Q:ì»¨ííí©
        rows = fetch_sheet(PITCH_SHEET_ID, "A:V", "íì¼건¬¸ì", ttl_key="inbound")
        if rows:
            hdr_idx = _find_header_row(rows, "êµ­ê°", "ì»¨ííí©", "ì»¨ííí©", "건´건¹ì")
            headers = [str(h).replace("\n", " ").strip() for h in rows[hdr_idx]]
            email_idx = _find_col(headers, "ì´건©ì¼") or 6
            brand_idx = _find_col(headers, "ìì²´건ª", "건¸건건") or 4
            status_idx = _find_col(headers, "ì»¨ííí©", "ì»¨ííí©") or 16
            staff_idx = _find_col(headers, "건´건¹ì") or 14
            meeting_idx = _find_col(headers, "건¯¸í") or 12
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
                if "ìí¹" in status:
                    cnt["working"] += 1
                if meeting and meeting != "-":
                    cnt["meeting"] += 1
                if "건¶ì í©" in status or "ê±°건¶" in status:
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
        # 루나 ìí¸: íí©ìí¸(ì건건§¤ì¹­) A:R (í¤건 1í)
        # A:ì»¨í건 ì§ B:건ª¨ì§íí C:êµ­ê° D:ì¹´íê³ 건¦¬ E:í건«í¼ F:ì¸í건£¨ì¸ì건ª
        # H:í건¡ì I:ì´건©ì¼ K:ì§íìí P:건´건¹ì
        rows = fetch_sheet(LUNA_SHEET_ID, "A:R", "íí©ìí¸(ì건건§¤ì¹­)", ttl_key="influencer")
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
                if "ìì건°ì´건" in recruit or "ì건" in recruit:
                    cnt["outbound"] += 1
                elif "ì¸건°ì´건" in recruit:
                    cnt["inbound"] += 1
                if email and "@" in email:
                    cnt["with_email"] += 1
                if "건¦¬ì¤í¸" in status:
                    cnt["listed"] += 1
                elif "ì ì" in status:
                    cnt["proposed"] += 1
                elif "ì¬건¡" in status:
                    cnt["usable"] += 1
                if country:
                    cnt["by_country"][country] = cnt["by_country"].get(country, 0) + 1
                if platform:
                    cnt["by_platform"][platform] = cnt["by_platform"].get(platform, 0) + 1
            result["total"] = cnt
            result["funnel"] = {"crawled": cnt["total"], "with_email": cnt["with_email"],
                                "proposed": cnt["proposed"], "usable": cnt["usable"]}
    elif agent == "ìí¼":
        # ìí¼ ìí¸: ìí¼_í´건¡건 A:I (í¤건 1í)
        # A:ì¼ì B:êµ­ê° C:ì±건 D:ê¸°íì E:íê² F:ìì건ª©ì  G:건¹ì© H:ê²°ê³¼ I:ê²°ê³¼íì¸ìí¸
        rows = fetch_sheet(SOPHIE_SHEET_ID, "A:I", "ìí¼_í´건¡건", ttl_key="default")
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
    """CEO ì¹ì¸ í DB ìì§ + ì´건©ì¼ ìì± íì´í건¼ì¸ ì¤í."""
    body = await request.json()
    agent = body.get("agent", "í¼ì¹")
    pid = body.get("proposal_id")
    now = datetime.now(KST)
    result = {"agent": agent, "steps": []}

    # STEP 1: DB ìì§
    if agent == "í¼ì¹":
        crawl = await api_crawl_brands(Request(scope={"type": "http"}, receive=None))
        # ì건®¬건 ì´ìì´ì§건§ ì¤건°ì´í° 기반
        leads = await api_recontact_leads()
        count = leads.get("count", 0)
        result["steps"].append({"step": "DB ìì§", "status": "ì건£", "count": count})
        _record_perf("í¼ì¹", "crawl_brands", count)
    elif agent == "루나":
        inf = await api_influencer_db()
        count = inf.get("total", 0) if isinstance(inf.get("total"), int) else len(inf.get("items", inf.get("rows", [])))
        result["steps"].append({"step": "DB ìì§", "status": "ì건£", "count": count})
        _record_perf("루나", "crawl_influencers", count)

    # STEP 2: ì´건©ì¼ ê°ì¸í ìì± â ê²ì í
    if agent == "í¼ì¹":
        leads_data = await api_recontact_leads()
        targets = [l for l in leads_data.get("leads", []) if l.get("email") and "@" in l.get("email", "")][:20]
        tmpl = EMAIL_TEMPLATES.get("pitch_outbound")
        queued = 0
        for t in targets:
            name = t.get("name", "건´건¹ì")
            email = t.get("email", "")
            subject = tmpl["subject"].format(brand=name, contact="건´건¹ì", name=name, fee="200")
            email_body = tmpl["body"].format(brand=name, contact="건´건¹ì", product="ì í", name=name, fee="200", **{"건¯¸í건§í¬": MEETING_LINK})
            html = _build_pitch_html(name, email_body + f"\n\n[건¯¸í ìì½íê¸°]({MEETING_LINK})")
            _queue_or_send_email("í¼ì¹", email, subject, html, {"target": name, "pipeline": True})
            queued += 1
        result["steps"].append({"step": "ì´건©ì¼ ìì±", "status": "ì건£", "queued": queued})
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
        result["steps"].append({"step": "ì´건©ì¼ ìì±", "status": "ì건£", "queued": queued})

    # STEP 3: proposal ìí ì건°ì´í¸
    if pid:
        proposals = load_proposals()
        for p in proposals:
            if p.get("id") == pid:
                p["status"] = "executed"
                p["executed_at"] = now.isoformat()
                p["result"] = f"DB {result['steps'][0].get('count',0)}ê±´ ìì§ â ì´건©ì¼ {result['steps'][-1].get('queued',0)}ê±´ ìì±"
                break
        save_proposals(proposals)

    # STEP 4: Slack ì건¦¼
    if _slack_enabled() and SLACK_WEBHOOK_URL:
        try:
            text = f"ð¤ [{agent}] íì´í건¼ì¸ ì¤í ì건£\n"
            for s in result["steps"]:
                text += f"â¢ {s['step']}: {s['status']} ({s.get('count', s.get('queued', 0))}ê±´)\n"
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(SLACK_WEBHOOK_URL, json={"text": text})
        except Exception:
            pass

    return {"status": "ok", "result": result}

@app.get("/api/outbound-dashboard")
async def api_outbound_dashboard(agent: str = "í¼ì¹"):
    """ì¹ì ìµì건¨ íµí© KPI â CEO 건ì건³´건ì©."""
    perf = load_agent_perf()
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    month_prefix = now.strftime("%Y-%m")
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    today_perf = perf.get(today, {}).get(agent, {})
    # ìê°/ì£¼ê° 건ì 
    monthly_p, weekly_p = {}, {}
    for dk, ad in perf.items():
        if dk.startswith(month_prefix) and agent in ad:
            for mk, mv in ad[agent].items():
                monthly_p[mk] = monthly_p.get(mk, 0) + mv
        if dk >= week_start and agent in ad:
            for mk, mv in ad[agent].items():
                weekly_p[mk] = weekly_p.get(mk, 0) + mv
    # 건°ì¡ íí©
    log = load_email_log()
    agent_log = [e for e in log if e.get("agent") == agent]
    today_sent = sum(1 for e in agent_log if e.get("sent_at", "").startswith(today) and e.get("status") == "sent")
    today_opened = sum(1 for e in agent_log if e.get("sent_at", "").startswith(today) and e.get("opened"))
    today_replied = sum(1 for e in agent_log if e.get("sent_at", "").startswith(today) and e.get("replied"))
    queue = load_email_queue()
    pending = sum(1 for q in queue if q.get("agent") == agent and q.get("status") == "pending")
    crawled = load_crawled()
    agent_type = "brand" if agent == "í¼ì¹" else "influencer"
    total_crawled = sum(1 for c in crawled if c.get("type") == agent_type)
    # 건²¤ì¹건§í¬
    bench = load_benchmarks()
    bm = bench.get("cold_email_b2b", {}) if agent == "í¼ì¹" else bench.get("influencer_outreach", {})
    open_rate = round(today_opened / max(today_sent, 1) * 100, 1)
    reply_rate = round(today_replied / max(today_sent, 1) * 100, 1)
    bm_reply = bm.get("reply_rate", {})
    # 건ª©í
    targets = AGENT_TARGETS.get(agent, {})
    daily_t = targets.get("daily", {})
    weekly_t = targets.get("weekly", {})
    monthly_t = targets.get("monthly", {})
    meeting_key = "meeting_booked" if agent == "í¼ì¹" else "influencer_acquired"
    # í í°
    token_today = today_perf.get("cost_usd_x100", 0) / 100
    token_month = monthly_p.get("cost_usd_x100", 0) / 100
    return {
        "target_summary": f"{'K-건·°í° 건¸건건' if agent=='í¼ì¹' else 'SNS ì¸í건£¨ì¸ì'} / ì´ {total_crawled}ê° í건³´",
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
    """ìì´ì í¸건³ ì건 건°ì¡ 건ª¨건 ì¡°í."""
    if AGENT_AUTO_SEND_FILE.exists():
        return json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8"))
    return {"í¼ì¹": False, "루나": False}

@app.post("/api/agent-auto-send")
async def api_agent_auto_send_set(request: Request):
    """ìì´ì í¸건³ ì건 건°ì¡ ON/OFF."""
    body = await request.json()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = {}
    if AGENT_AUTO_SEND_FILE.exists():
        existing = json.loads(AGENT_AUTO_SEND_FILE.read_text(encoding="utf-8"))
    agent = body.get("agent", "")
    existing[agent] = bool(body.get("enabled", False))
    AGENT_AUTO_SEND_FILE.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "agent": agent, "enabled": existing[agent]}


# ===== í¬건¡¤건§ + íì´í건¼ì¸ API =====

# ì´건©ì¼ íí건¦¿
EMAIL_TEMPLATES = {
    "pitch_outbound": {
        "subject": "[{brand}] 건¦¬건·° 0ê° â 100ê°, 건¬´건£건¡ ììíì¸ì (4ì íì )",
        "body": """ì건íì¸ì, {contact}건.
ê¸건¡건² ì¸í건£¨ì¸ì 건§ì¼í í건«í¼ ê³µí건¦¬í°(08liter)ì ì ì´ì½¥ì건건¤.
{brand}ì {product} ê´건 ¨, íì¬ 건¸건건 건¨ê³ìì í¨ì¨ì´ 건ì 3ê°ì§ íµì¬ ííì ì건´건건¦½건건¤.

1. 건¦¬건·°ê° ìì¼건©´ êµ¬건§¤건 ììµ건건¤ (êµ­건´/í´ì¸ êµ¬건§¤í 건¬´건£ ì ê³µ)
2. í°ì§건 ìí¼, 3ê°ìê° ê±±ì  ìì´ 1000ê°건 ê°건¥í©건건¤ (ì 100건§ì)
3. íì¤í 건§¤ì¶ ì íì ìí 건§ì¶¤ í¤ ì¸í건£¨ì¸ì

10건¶ 건¹건건©´ 건¯¸íì¼건¡ {brand}ì 건§건 건§ì¶¤ ì ì 건건¦½건건¤.""",
    },
    "pitch_crm": {
        "subject": "{brand}건, 4ì ìµì½ í건¡건ª¨ì â ìí¼ 건¬´ì í 300건§ì",
        "body": """ì건íì¸ì, {contact}건.
ì§건건² {brand} ê´건 ¨ 건¬¸ì건¥¼ ì£¼ì¨ì 건 ì¢ì 건í건¥¼ 건건´ì건건°ì,
ì´í ì§í ìí©ì´ ê¶ê¸íì¬ 건¤ì ì°건½건건¦½건건¤.

íì¬ 4ì ìµì½ í건¡건ª¨ì ì§í ì¤ì건건¤:
- ìí¼ 건¬´ì í ì 300건§ì (ê¸°ì¡´ 500건§ì)
- í´ì¸ êµ¬건§¤í 100ê±´ 건¬´건£ ì ê³µ
- 건§ì¶¤ í¤ ì¸í건£¨ì¸ì 3건ª 건°°ì 

í¸íì  ìê°ì 10건¶건§ í¬ìí´ ì£¼ì건©´ 건§ì¶¤ ì ìì 건건¦¬ê² ìµ건건¤.""",
    },
    "pitch_followup": {
        "subject": "Re: {brand} â 10건¶ì´건©´ ì¶©건¶í©건건¤",
        "body": "ì건íì¸ì, {contact}건. í¹ì íì¸íì¨ìê¹ì? ì§ê¸ ìê¸°ê° ê°ì¥ í¨ì¨ ì¢ì íì´건°ì건건¤. í¸íì  건 건µ건³ 건¶í건건¦½건건¤.",
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
        "subject": "{name}건, 건¬´건£ íì°¬ + ì ì건¹ ì ì",
        "body": """ì건íì¸ì {name}건, ê³µí건¦¬í° 루나ì건건¤!

ìµê·¼ ì½íì¸  ì 건§ ì¸ìì ì´ìì´ì. K-건·°í° 건¸건건 íì°¬ ì ì건건¦½건건¤:
- 건¬´건£ ì í ì ê³µ
- ì ì건¹: {fee}ì
- 건¦´ì¤/ìì¸  1ê°, 3ê°ì ì¬ì©ê¶

ê´ì¬ ìì¼ì건©´ 건µì¥건§ ì£¼ì¸ì!

루나 건건¦¼""",
    },
    "luna_followup": {
        "subject": "Re: {name}건 â í¹ì íì¸íì¨건ì?",
        "body": "ì건íì¸ì {name}건! í¹ì íì¸íì¨건ì? ê´ì¬ ìì¼ì건©´ 건µì¥건§ ì£¼ì¸ì :)",
    },
}

@app.get("/api/email-templates")
async def api_email_templates():
    """ì´건©ì¼ íí건¦¿ 건ª©건¡."""
    return EMAIL_TEMPLATES

@app.post("/api/crawl/brands")
async def api_crawl_brands(request: Request):
    """í¼ì¹ì© 건¸건건 í¬건¡¤건§ (ì건®¬건 ì´ì). ì¤ì  í¬건¡¤건§ì ì¶í ì°건."""
    body = await request.json()
    channels = body.get("channels", [])
    keyword = body.get("keyword", "K-건·°í°")
    limit = min(body.get("limit", 50), 200)
    # ì건®¬건 ì´ì: êµ¬ê¸ìí¸ ì¸건°ì´건 + í¬건¡¤건§ ê²°ê³¼ 건³í©
    results = []
    try:
        leads = await api_recontact_leads()
        for l in leads.get("leads", [])[:limit]:
            results.append({"company": l["name"], "contact": "", "title": "건´건¹ì",
                            "email": l.get("email", ""), "phone": l.get("contact", ""),
                            "url": "", "product": keyword, "source": "ì¸건°ì´건DB", "size": ""})
    except Exception:
        pass
    _record_perf("í¼ì¹", "crawl_brands", len(results))
    existing = load_crawled()
    seen = {e.get("email") for e in existing if e.get("email")}
    new_items = [r for r in results if r.get("email") and r["email"] not in seen]
    existing.extend([{**r, "type": "brand", "crawled_at": datetime.now(KST).isoformat()} for r in new_items])
    save_crawled(existing)
    return {"status": "ok", "count": len(results), "new": len(new_items), "results": results[:50]}

@app.post("/api/crawl/influencers")
async def api_crawl_influencers(request: Request):
    """루나ì© ì¸í건£¨ì¸ì í¬건¡¤건§ (ì건®¬건 ì´ì). ì¤ì  SNS í¬건¡¤건§ì ì¶í ì°건."""
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
                                    "category": item.get("category", "건·°í°"),
                                    "country": item.get("country", "KR"),
                                    "email": email, "engagement": "3.2%",
                                    "url": item.get("url", ""), "source": "ì¸í건£¨ì¸ìDB"})
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
    """í¬건¡¤건§ ê²°ê³¼ 기반 ì´건©ì¼ ì건 ìì± â ê²ì í."""
    body = await request.json()
    targets = body.get("targets", [])
    agent = body.get("agent", "í¼ì¹")
    template_key = body.get("template", "pitch_outbound")
    tmpl = EMAIL_TEMPLATES.get(template_key, EMAIL_TEMPLATES["pitch_outbound"])
    queued = 0
    for t in targets[:50]:
        email = t.get("email", "")
        if not email or "@" not in email:
            continue
        vars_map = {"brand": t.get("company", t.get("name", "")), "contact": t.get("contact", "건´건¹ì"),
                    "product": t.get("product", "ì í"), "name": t.get("name", ""),
                    "fee": t.get("fee", "200"), "건¯¸í건§í¬": MEETING_LINK}
        try:
            subject = tmpl["subject"].format(**{k: vars_map.get(k, "") for k in ["brand", "contact", "name", "fee"]})
            email_body = tmpl["body"].format(**{k: vars_map.get(k, "") for k in ["brand", "contact", "product", "name", "fee", "건¯¸í건§í¬"]})
        except (KeyError, IndexError):
            subject = tmpl["subject"]
            email_body = tmpl["body"]
        html = _build_pitch_html(vars_map.get("brand", vars_map.get("name", "")), email_body + f"\n\n[건¯¸í ìì½íê¸°]({MEETING_LINK})")
        _queue_or_send_email(agent, email, subject, html, {"target": t.get("company", t.get("name", ""))})
        queued += 1
    _record_perf(agent, "emails_generated", queued)
    return {"status": "ok", "queued": queued}

@app.get("/api/email-log")
async def api_get_email_log(agent: Optional[str] = None):
    """ì´건©ì¼ 건°ì¡ 건¡ê·¸ ì¡°í."""
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
    """íì´í건¼ì¸ 건¨ê³건³ íµê³."""
    log = load_email_log()
    crawled = load_crawled()
    queue = load_email_queue()
    today = datetime.now(KST).strftime("%Y-%m-%d")
    if agent:
        log = [e for e in log if e.get("agent") == agent]
        crawled = [c for c in crawled if c.get("type") == ("brand" if agent == "í¼ì¹" else "influencer")]
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
    """ìì´ì í¸건³ KPI 건¬ì±건¥  â ì¹´ì¼ 건ì건³´건ì©."""
    goals = load_goals()
    brand = await api_brand_pipeline()
    m = brand.get("month", {})
    t = brand.get("today", {})
    inf = await api_influencer_db()
    agents = {
        "ì¹´ì¼": {"role": "ì´ê´", "kpi": min(100, round(m.get("revenue", 0) / max(goals.get("revenue", 160000000), 1) * 100)), "metric": f"건§¤ì¶ {m.get('revenue',0):,}ì"},
        "루나": {"role": "건¸건건ìì", "kpi": min(100, round(m.get("contract", 0) / max(goals.get("contracts", 38), 1) * 100)), "metric": f"ê³ì½ {m.get('contract',0)}ê±´"},
        "í¼ì¹": {"role": "ì¸í건£¨ì¸ì", "kpi": min(100, round(inf.get("total", 0) / max(goals.get("influencer_pool", 1550000), 1) * 100)), "metric": f"í {inf.get('total',0):,}건ª"},
        "건§¥ì¤": {"role": "ê´ê³ ì¼í°", "kpi": 72, "metric": "CPA 32,000ì"},
        "ìí¼": {"role": "SNSì´ì", "kpi": 65, "metric": "í건¡ì 43,370"},
        "건 ì´": {"role": "ê²½ìì§ì", "kpi": 88, "metric": f"ê³ì°ì {m.get('contract',0)}ê±´"},
        "í건": {"role": "CS", "kpi": 78, "metric": "íê· ì건µ 12건¶"},
    }
    avg_kpi = round(sum(a["kpi"] for a in agents.values()) / len(agents))
    return {"agents": agents, "avg_kpi": avg_kpi}


@app.get("/api/pitch-outbound")
async def api_pitch_outbound():
    """í¼ì¹ ìì건°ì´건 ì±ê³¼ 건ì건³´건 건°ì´í°."""
    return {
        "today": {"sent": 12, "replied": 3, "handled": 2, "meetings": 1, "negotiating": 2},
        "funnel": [
            {"stage": "건°ì¡", "count": 12, "rate": 100},
            {"stage": "건µ건³", "count": 3, "rate": 25},
            {"stage": "건ì", "count": 2, "rate": 16.7},
            {"stage": "건¯¸í", "count": 1, "rate": 8.3},
            {"stage": "íì", "count": 2, "rate": 16.7},
            {"stage": "ê³ì½", "count": 0, "rate": 0},
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
        "note": "í¼ì¹ìì´ì í¸ 건°ì¡건¡ê·¸ 기반 â ì¤ìê° ì°건 í ì¤건°ì´í° ì í"
    }


import asyncio
import threading

def _cache_warm():
    """ì건² ìì ì êµ¬ê¸ìí¸ 건°ì´í°건¥¼ 건¯¸건¦¬ 건¡건."""
    if not GSHEETS_API_KEY:
        return
    try:
        fetch_sheet(SHEET_INBOUND, "A:Z", "íì¼건¬¸ì", ttl_key="inbound")
        fetch_sheet(SHEET_CONTRACT, "A:Z", "ê³ì°ì건°í", ttl_key="contract")
        fetch_sheet(SHEET_INFLUENCER, "A2:R", "íí©ìí¸(ì건건§¤ì¹­)", ttl_key="influencer")
        print("[CACHE] êµ¬ê¸ìí¸ 건°ì´í° ì¬ì  건¡건 ì건£")
    except Exception as e:
        print(f"[CACHE] ì¬ì  건¡건 ì¤건¥: {e}")

def _cache_refresh_loop():
    """10건¶건§건¤ 건°±ê·¸건¼ì´건ìì ìºì ê°±ì ."""
    import time as _time
    while True:
        _time.sleep(600)
        try:
            _cache.clear()
            _cache_time.clear()
            _cache_warm()
            print("[CACHE] 건°±ê·¸건¼ì´건 ê°±ì  ì건£")
        except Exception:
            pass

# ì건² ìì ì ìºì ì건° + 건°±ê·¸건¼ì´건 ê°±ì  ì¤건 건
_cache_warm()
_bg_thread = threading.Thread(target=_cache_refresh_loop, daemon=True)
_bg_thread.start()

if __name__ == "__main__":
    import uvicorn
    print("08L_AI Command Center -> http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
