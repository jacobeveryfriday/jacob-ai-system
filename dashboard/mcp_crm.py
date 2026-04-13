# -*- coding: utf-8 -*-
"""MCP CRM Client - dashboard/mcp_crm.py
Next.js API server at mcp-crm.08liter.com
Auth: Authorization: Bearer {API_KEY}
"""
import os
import json
import requests
from datetime import datetime, timedelta

MCP_URL = os.environ.get("MCP_CRM_URL", "https://mcp-crm.08liter.com")
MCP_KEY = os.environ.get("MCP_CRM_API_KEY", "")
DORMANT_DAYS = int(os.environ.get("DORMANT_DAYS", "90"))

# Cache discovered working config
_working_config = None


def _auth_headers():
    return {
        "Authorization": f"Bearer {MCP_KEY}",
        "Content-Type": "application/json",
    }


def _get(path):
    """GET request to MCP CRM API."""
    try:
        r = requests.get(f"{MCP_URL}{path}", headers=_auth_headers(), timeout=15)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text[:500]}
        return {"error": f"status_{r.status_code}", "body": r.text[:300]}
    except Exception as e:
        return {"error": str(e)}


def _post(path, payload):
    """POST request to MCP CRM API."""
    try:
        r = requests.post(f"{MCP_URL}{path}", json=payload, headers=_auth_headers(), timeout=15)
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return {"raw": r.text[:500]}
        return {"error": f"status_{r.status_code}", "body": r.text[:300]}
    except Exception as e:
        return {"error": str(e)}


def call_tool(tool_name: str, params: dict):
    """Call MCP CRM tool via discovered endpoint."""
    global _working_config
    if not MCP_KEY:
        return {"error": "MCP_CRM_API_KEY not set"}

    # If cached config exists, use it
    if _working_config:
        path = _working_config["path"]
        fmt = _working_config["format"]
        if fmt == "tool_params":
            result = _post(path, {"tool": tool_name, "params": params})
        elif fmt == "jsonrpc":
            result = _post(path, {"jsonrpc": "2.0", "method": tool_name, "params": params, "id": 1})
        elif fmt == "name_args":
            result = _post(path, {"name": tool_name, "arguments": params})
        elif fmt == "direct":
            result = _post(path, params)
        else:
            result = _post(path, {"tool": tool_name, "params": params})

        if "error" not in result or "status_" not in str(result.get("error", "")):
            return result
        _working_config = None  # Reset and retry

    # Try all API path + format combinations
    api_paths = [
        "/api/mcp",
        "/api/tools/call",
        "/api/v1/mcp",
        "/api/rpc",
        "/api/execute",
        "/api/mcp/call",
        "/api/call",
    ]
    formats = [
        ("tool_params", lambda t, p: {"tool": t, "params": p}),
        ("jsonrpc", lambda t, p: {"jsonrpc": "2.0", "method": t, "params": p, "id": 1}),
        ("name_args", lambda t, p: {"name": t, "arguments": p}),
    ]

    for path in api_paths:
        for fmt_name, fmt_fn in formats:
            payload = fmt_fn(tool_name, params)
            result = _post(path, payload)
            err = str(result.get("error", ""))
            # Skip clear failures
            if "status_404" in err or "status_405" in err:
                continue
            if "status_401" in err or "status_403" in err:
                continue
            if "error" not in result:
                _working_config = {"path": path, "format": fmt_name}
                return result

    return {"error": "all_api_paths_failed", "mcp_url": MCP_URL, "api_key_set": bool(MCP_KEY)}


def probe_server():
    """Deep probe: discover actual API structure."""
    results = []

    # 1) Check /api/docs with auth (should return API documentation)
    for path in ["/api/docs", "/api/schema", "/api/openapi", "/api/health",
                 "/api/status", "/api/brands", "/api/partners",
                 "/api/mcp", "/api/v1/brands", "/api/crm/brands",
                 "/api/tools", "/api/tools/list"]:
        try:
            r = requests.get(f"{MCP_URL}{path}", headers=_auth_headers(), timeout=8)
            body = r.text[:400]
            # Skip HTML responses (Next.js pages, not API)
            is_html = body.strip().startswith("<\!DOCTYPE") or body.strip().startswith("<html")
            results.append({
                "method": "GET", "path": path, "status": r.status_code,
                "is_api": not is_html,
                "body": body if not is_html else "(HTML page)",
            })
        except Exception as e:
            results.append({"method": "GET", "path": path, "status": -1, "body": str(e)[:100]})

    # 2) POST probes on likely API paths
    test_payloads = [
        {"tool": "search_brands", "params": {"limit": 1}},
        {"name": "search_brands", "arguments": {"limit": 1}},
    ]
    for path in ["/api/mcp", "/api/tools/call", "/api/rpc", "/api/execute",
                 "/api/mcp/call", "/api/v1/mcp", "/api/call"]:
        for payload in test_payloads:
            try:
                r = requests.post(f"{MCP_URL}{path}", json=payload,
                                  headers=_auth_headers(), timeout=8)
                body = r.text[:400]
                is_html = body.strip().startswith("<\!DOCTYPE") or body.strip().startswith("<html")
                if not is_html:  # Only log actual API responses
                    results.append({
                        "method": "POST", "path": path, "status": r.status_code,
                        "payload_keys": list(payload.keys()),
                        "body": body,
                    })
            except Exception:
                pass

    return {
        "mcp_url": MCP_URL,
        "api_key_prefix": MCP_KEY[:12] + "..." if MCP_KEY else "NOT_SET",
        "api_responses_only": True,
        "probe_results": results,
    }


def get_dormant_brands(limit=200):
    # Try direct REST endpoint first (Next.js API route pattern)
    result = _get(f"/api/brands?lastCampaignBefore={(datetime.now() - timedelta(days=DORMANT_DAYS)).strftime('%Y-%m-%d')}&hasVerifiedContact=true&limit={limit}")
    if "error" not in result:
        return result
    # Fallback to tool call
    cutoff = (datetime.now() - timedelta(days=DORMANT_DAYS)).strftime("%Y-%m-%d")
    return call_tool("search_brands", {
        "lastCampaignBefore": cutoff,
        "hasVerifiedContact": True,
        "limit": limit,
    })


def get_all_brands(limit=200):
    result = _get(f"/api/brands?hasVerifiedContact=true&limit={limit}")
    if "error" not in result:
        return result
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
    # Try direct REST first
    result = _get("/api/partners/schema")
    if "error" not in result:
        return {"schema": result, "admin_schema": {}}
    result = _get("/api/partners/stats")
    if "error" not in result:
        return {"schema": result, "admin_schema": {}}
    # Fallback to tool calls
    schema = call_tool("describe_schema", {"table": "partner"})
    admin = call_tool("describe_schema", {"table": "partner_admin"})
    return {"schema": schema, "admin_schema": admin}


def check_connection():
    if not MCP_KEY:
        return False
    try:
        r = requests.get(f"{MCP_URL}/api/health", headers=_auth_headers(), timeout=5)
        return r.status_code == 200
    except Exception:
        return False
