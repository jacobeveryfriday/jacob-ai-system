# -*- coding: utf-8 -*-
"""MCP CRM Client - dashboard/mcp_crm.py
Auto-detects API endpoint and auth method for mcp-crm.08liter.com
"""
import os
import json
import requests
from datetime import datetime, timedelta

MCP_URL = os.environ.get("MCP_CRM_URL", "https://mcp-crm.08liter.com")
MCP_KEY = os.environ.get("MCP_CRM_API_KEY", "")
DORMANT_DAYS = int(os.environ.get("DORMANT_DAYS", "90"))

# Cache discovered working config
_working_endpoint = None
_working_auth = None

# All possible endpoint paths to try
_ENDPOINTS = [
    "/api/mcp",
    "/mcp",
    "/api/v1/mcp",
    "/api/tools/call",
    "/tools/call",
    "/api/rpc",
    "/rpc",
    "/api/execute",
]

# All possible auth header combos to try
_AUTH_HEADERS = [
    lambda k: {"Authorization": f"Bearer {k}"},
    lambda k: {"X-API-Key": k},
    lambda k: {"Authorization": k},
    lambda k: {"api-key": k},
    lambda k: {"x-api-key": k},
]

# All possible payload formats
_PAYLOADS = [
    lambda t, p: {"tool": t, "params": p},
    lambda t, p: {"method": t, "params": p},
    lambda t, p: {"jsonrpc": "2.0", "method": t, "params": p, "id": 1},
    lambda t, p: {"action": t, "data": p},
    lambda t, p: {"name": t, "arguments": p},
]


def _try_request(endpoint, auth_hdr, payload):
    """Single attempt with specific endpoint + auth + payload."""
    url = f"{MCP_URL}{endpoint}"
    headers = {**auth_hdr, "Content-Type": "application/json"}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        return r.status_code, r.text[:500]
    except Exception as e:
        return -1, str(e)[:200]


def probe_server():
    """Try all combinations to find working config. Returns debug info."""
    results = []

    # Step 1: Try health/root endpoints
    for path in ["/health", "/", "/api", "/docs", "/api/docs", "/openapi.json"]:
        try:
            r = requests.get(f"{MCP_URL}{path}", timeout=5)
            results.append({"type": "GET", "path": path, "status": r.status_code, "body": r.text[:300]})
        except Exception as e:
            results.append({"type": "GET", "path": path, "status": -1, "body": str(e)[:200]})

    # Step 2: Try POST with first 3 endpoint + auth + payload combos
    for ep in _ENDPOINTS[:4]:
        for auth_fn in _AUTH_HEADERS[:3]:
            for payload_fn in _PAYLOADS[:3]:
                auth_hdr = auth_fn(MCP_KEY)
                payload = payload_fn("search_brands", {"limit": 1})
                code, body = _try_request(ep, auth_hdr, payload)
                if code not in (-1, 401, 403, 404, 405):
                    results.append({
                        "type": "POST",
                        "path": ep,
                        "auth": list(auth_hdr.keys())[0],
                        "payload_keys": list(payload.keys()),
                        "status": code,
                        "body": body[:300],
                        "WORKING": code == 200,
                    })
                # Only log non-404s to keep output clean
                elif code not in (404, 405, -1):
                    results.append({
                        "type": "POST", "path": ep,
                        "auth": list(auth_hdr.keys())[0],
                        "status": code, "body": body[:200],
                    })

    return {
        "mcp_url": MCP_URL,
        "api_key_prefix": MCP_KEY[:12] + "..." if MCP_KEY else "NOT_SET",
        "probe_results": results,
    }


def call_tool(tool_name: str, params: dict):
    """Call MCP CRM tool. Uses cached config or tries all combos."""
    global _working_endpoint, _working_auth

    if not MCP_KEY:
        return {"error": "MCP_CRM_API_KEY not set"}

    # If we have a cached working config, use it
    if _working_endpoint and _working_auth:
        try:
            auth_hdr = {**_working_auth, "Content-Type": "application/json"}
            payload = _working_endpoint["payload_fn"](tool_name, params)
            r = requests.post(
                f"{MCP_URL}{_working_endpoint['path']}",
                json=payload, headers=auth_hdr, timeout=15,
            )
            if r.status_code == 200:
                return r.json()
        except Exception:
            _working_endpoint = None
            _working_auth = None

    # Try all combinations
    for ep in _ENDPOINTS:
        for auth_fn in _AUTH_HEADERS:
            for payload_fn in _PAYLOADS:
                auth_hdr = auth_fn(MCP_KEY)
                payload = payload_fn(tool_name, params)
                try:
                    r = requests.post(
                        f"{MCP_URL}{ep}",
                        json=payload,
                        headers={**auth_hdr, "Content-Type": "application/json"},
                        timeout=10,
                    )
                    if r.status_code == 200:
                        # Cache this working config
                        _working_endpoint = {"path": ep, "payload_fn": payload_fn}
                        _working_auth = auth_hdr
                        try:
                            return r.json()
                        except Exception:
                            return {"data": r.text[:1000]}
                except Exception:
                    continue

    return {"error": "all_auth_combinations_failed", "mcp_url": MCP_URL,
            "api_key_set": bool(MCP_KEY), "endpoints_tried": len(_ENDPOINTS)}


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
        "senderName": "\ud53c\uce58",
        "senderEmail": "pitch@08liter.com",
        "createdBy": "dashboard-auto",
        "targets": targets,
    })


def queue_review(draft_id, target_count):
    return call_tool("queue_for_review", {
        "draftId": draft_id,
        "actor": "dashboard-auto",
        "note": f"\ud734\uba74{DORMANT_DAYS}\uc77c \ube0c\ub79c\ub4dc {target_count}\uac74 \uc790\ub3d9\uc2e4\ud589 \ub300\uae30\uc911",
    })


def get_influencer_schema():
    schema = call_tool("describe_schema", {"table": "partner"})
    admin = call_tool("describe_schema", {"table": "partner_admin"})
    return {"schema": schema, "admin_schema": admin}


def check_connection():
    if not MCP_KEY:
        return False
    try:
        r = requests.get(f"{MCP_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False
