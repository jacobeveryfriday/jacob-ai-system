# -*- coding: utf-8 -*-
"""MCP CRM Client \u2014 dashboard/mcp_crm.py
Connects to https://mcp-crm.08liter.com for brand/influencer CRM operations.
All Korean strings use \\uXXXX escapes (no raw Korean in source).
"""
import os
import requests
from datetime import datetime, timedelta

MCP_URL = os.environ.get("MCP_CRM_URL", "https://mcp-crm.08liter.com")
MCP_KEY = os.environ.get("MCP_CRM_API_KEY", "")
DORMANT_DAYS = int(os.environ.get("DORMANT_DAYS", "90"))


def _headers():
    return {
        "Authorization": f"Bearer {MCP_KEY}",
        "Content-Type": "application/json",
    }


def _headers_alt():
    """Fallback: X-API-Key header."""
    return {
        "X-API-Key": MCP_KEY,
        "Content-Type": "application/json",
    }


def call_tool(tool_name: str, params: dict):
    """Call MCP CRM tool endpoint. Try Bearer first, fallback to X-API-Key."""
    payload = {"tool": tool_name, "params": params}
    for hdr_fn in (_headers, _headers_alt):
        try:
            r = requests.post(
                f"{MCP_URL}/api/mcp",
                json=payload,
                headers=hdr_fn(),
                timeout=15,
            )
            if r.status_code == 401 or r.status_code == 403:
                continue  # try next auth method
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError:
            continue
        except Exception as e:
            return {"error": str(e)}
    return {"error": "auth_failed: both Bearer and X-API-Key rejected"}


def get_dormant_brands(limit=200):
    cutoff = (datetime.now() - timedelta(days=DORMANT_DAYS)).strftime("%Y-%m-%d")
    return call_tool("search_brands", {
        "lastCampaignBefore": cutoff,
        "hasVerifiedContact": True,
        "limit": limit,
    })


def get_all_brands(limit=200):
    return call_tool("search_brands", {
        "hasVerifiedContact": True,
        "limit": limit,
    })


def create_segment(name, targets):
    return call_tool("create_segment", {
        "name": name,
        "kind": "brand",
        # \ud734\uba74 = 휴면, \uc77c = 일, \uae30\uc900 = 기준, \uc790\ub3d9\uc138\uadf8\uba3c\ud2b8 = 자동세그먼트
        "description": f"\ud734\uba74{DORMANT_DAYS}\uc77c \uae30\uc900 \uc790\ub3d9\uc138\uadf8\uba3c\ud2b8",
        "createdBy": "dashboard-auto",
        "targets": [{"externalId": t.get("brand_id", ""), "snapshot": t} for t in targets],
    })


def save_draft(segment_id, name, subject_tpl, body_tpl, targets):
    return call_tool("save_message_draft", {
        "segmentId": segment_id,
        "name": name,
        "subjectTemplate": subject_tpl,
        "bodyTemplate": body_tpl,
        # \ud53c\uce58 = 피치
        "senderName": "\ud53c\uce58",
        "senderEmail": "pitch@08liter.com",
        "createdBy": "dashboard-auto",
        "targets": targets,
    })


def queue_review(draft_id, target_count):
    return call_tool("queue_for_review", {
        "draftId": draft_id,
        "actor": "dashboard-auto",
        # \ud734\uba74 = 휴면, \ube0c\ub79c\ub4dc = 브랜드, \uac74 = 건, \uc790\ub3d9\uc2e4\ud589 = 자동실행, \ub300\uae30\uc911 = 대기중
        "note": f"\ud734\uba74{DORMANT_DAYS}\uc77c \ube0c\ub79c\ub4dc {target_count}\uac74 \uc790\ub3d9\uc2e4\ud589 \ub300\uae30\uc911",
    })


def get_influencer_schema():
    """Fetch partner table schema + admin stats for Luna section."""
    schema = call_tool("describe_schema", {"table": "partner"})
    admin = call_tool("describe_schema", {"table": "partner_admin"})
    return {"schema": schema, "admin_schema": admin}


def check_connection():
    """Health-check: returns True if MCP CRM is reachable."""
    if not MCP_KEY:
        return False
    try:
        r = requests.get(f"{MCP_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False
