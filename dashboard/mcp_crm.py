# -*- coding: utf-8 -*-
"""MCP CRM Client - dashboard/mcp_crm.py
Server: Next.js at mcp-crm.08liter.com
Known: /api/tools exists (403 = key expired), auth = Bearer
"""
import os
import json
import requests
from datetime import datetime, timedelta

MCP_URL = os.environ.get("MCP_CRM_URL", "https://mcp-crm.08liter.com")
MCP_KEY = os.environ.get("MCP_CRM_API_KEY", "")
DORMANT_DAYS = int(os.environ.get("DORMANT_DAYS", "90"))

_working_config = None


def _headers():
    return {"Authorization": f"Bearer {MCP_KEY}", "Content-Type": "application/json"}


def _get(path, timeout=10):
    try:
        r = requests.get(f"{MCP_URL}{path}", headers=_headers(), timeout=timeout)
        body = r.text[:500]
        is_html = body.strip().startswith("<\!DOCTYPE") or body.strip().startswith("<html")
        if is_html:
            return {"error": f"html_page_status_{r.status_code}"}
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return {"raw": body}
        return {"error": f"status_{r.status_code}", "body": body}
    except Exception as e:
        return {"error": str(e)}


def _post(path, payload, timeout=10):
    try:
        r = requests.post(f"{MCP_URL}{path}", json=payload, headers=_headers(), timeout=timeout)
        body = r.text[:500]
        is_html = body.strip().startswith("<\!DOCTYPE") or body.strip().startswith("<html")
        if is_html:
            return {"error": f"html_page_status_{r.status_code}"}
        if r.status_code == 200:
            try:
                return r.json()
            except Exception:
                return {"raw": body}
        return {"error": f"status_{r.status_code}", "body": body}
    except Exception as e:
        return {"error": str(e)}


def deep_probe():
    """Targeted probe based on findings: /api/tools is real, key rejected."""
    results = {"mcp_url": MCP_URL, "api_key_prefix": MCP_KEY[:16] + "..." if MCP_KEY else "NOT_SET"}
    findings = []

    # 1) /api/tools - the known real endpoint
    for method_fn, method_name, path in [
        (lambda p: requests.get(f"{MCP_URL}{p}", headers=_headers(), timeout=8), "GET", "/api/tools"),
        (lambda p: requests.get(f"{MCP_URL}{p}", headers=_headers(), timeout=8), "GET", "/api/tools/search_brands"),
        (lambda p: requests.post(f"{MCP_URL}{p}", json={"tool": "search_brands", "params": {"limit": 1}}, headers=_headers(), timeout=8), "POST", "/api/tools"),
        (lambda p: requests.post(f"{MCP_URL}{p}", json={"name": "search_brands", "arguments": {"limit": 1}}, headers=_headers(), timeout=8), "POST", "/api/tools"),
        (lambda p: requests.post(f"{MCP_URL}{p}", json={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "search_brands", "arguments": {"limit": 1}}, "id": 1}, headers=_headers(), timeout=8), "POST", "/api/tools"),
    ]:
        try:
            r = method_fn(path)
            body = r.text[:400]
            is_html = body.strip().startswith("<\!DOCTYPE")
            findings.append({"method": method_name, "path": path, "status": r.status_code, "body": "(html)" if is_html else body})
        except Exception as e:
            findings.append({"method": method_name, "path": path, "error": str(e)[:100]})

    # 2) MCP Protocol standard endpoints (SSE transport)
    for path in ["/sse", "/mcp/sse", "/mcp", "/message", "/mcp/message", "/messages"]:
        try:
            r = requests.get(f"{MCP_URL}{path}", headers=_headers(), timeout=5, stream=True)
            ct = r.headers.get("content-type", "")
            body = ""
            if "text/event-stream" in ct:
                # Read first few lines of SSE
                lines = []
                for i, line in enumerate(r.iter_lines(decode_unicode=True)):
                    lines.append(line)
                    if i > 5:
                        break
                body = "\n".join(lines)
                findings.append({"method": "GET(SSE)", "path": path, "status": r.status_code, "content_type": ct, "body": body[:300], "IS_MCP_SSE": True})
            elif "text/html" not in ct:
                body = r.text[:300] if hasattr(r, 'text') else ""
                findings.append({"method": "GET", "path": path, "status": r.status_code, "content_type": ct, "body": body})
            r.close()
        except Exception as e:
            findings.append({"method": "GET", "path": path, "error": str(e)[:100]})

    # 3) Try POST to /message (MCP standard)
    mcp_tool_call = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "search_brands", "arguments": {"limit": 1}},
        "id": 1,
    }
    for path in ["/message", "/mcp/message", "/messages", "/mcp/messages", "/api/message"]:
        try:
            r = requests.post(f"{MCP_URL}{path}", json=mcp_tool_call, headers=_headers(), timeout=8)
            body = r.text[:400]
            is_html = body.strip().startswith("<\!DOCTYPE")
            if not is_html:
                findings.append({"method": "POST", "path": path, "status": r.status_code, "body": body, "NOTE": "MCP protocol"})
        except Exception as e:
            findings.append({"method": "POST", "path": path, "error": str(e)[:100]})

    # 4) Try tools/list (MCP standard method)
    for path in ["/api/tools", "/message", "/mcp/message"]:
        try:
            payload = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2}
            r = requests.post(f"{MCP_URL}{path}", json=payload, headers=_headers(), timeout=8)
            body = r.text[:400]
            is_html = body.strip().startswith("<\!DOCTYPE")
            if not is_html:
                findings.append({"method": "POST(tools/list)", "path": path, "status": r.status_code, "body": body})
        except Exception:
            pass

    results["findings"] = findings
    results["diagnosis"] = "API key rejected at /api/tools (403). Key may be expired or wrong. Check mcp-crm.08liter.com admin panel."
    return results


def call_tool(tool_name: str, params: dict):
    """Call MCP CRM tool."""
    global _working_config
    if not MCP_KEY:
        return {"error": "MCP_CRM_API_KEY not set"}

    if _working_config:
        path = _working_config["path"]
        fmt = _working_config["format"]
        payload = _make_payload(fmt, tool_name, params)
        result = _post(path, payload)
        if "error" not in result:
            return result
        _working_config = None

    # Try known patterns
    attempts = [
        ("/api/tools", "jsonrpc_tools_call"),
        ("/api/tools", "tool_params"),
        ("/api/tools", "name_args"),
        ("/message", "jsonrpc_tools_call"),
        ("/mcp/message", "jsonrpc_tools_call"),
    ]
    for path, fmt in attempts:
        payload = _make_payload(fmt, tool_name, params)
        result = _post(path, payload)
        if "error" not in result:
            _working_config = {"path": path, "format": fmt}
            return result

    return {"error": "api_key_rejected_or_endpoint_not_found", "mcp_url": MCP_URL}


def _make_payload(fmt, tool_name, params):
    if fmt == "jsonrpc_tools_call":
        return {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": params}, "id": 1}
    elif fmt == "tool_params":
        return {"tool": tool_name, "params": params}
    elif fmt == "name_args":
        return {"name": tool_name, "arguments": params}
    return {"tool": tool_name, "params": params}


def get_dormant_brands(limit=200):
    cutoff = (datetime.now() - timedelta(days=DORMANT_DAYS)).strftime("%Y-%m-%d")
    return call_tool("search_brands", {
        "lastCampaignBefore": cutoff, "hasVerifiedContact": True, "limit": limit,
    })


def get_all_brands(limit=200):
    return call_tool("search_brands", {"hasVerifiedContact": True, "limit": limit})


def create_segment(name, targets):
    return call_tool("create_segment", {
        "name": name, "kind": "brand",
        "description": f"\ud734\uba74{DORMANT_DAYS}\uc77c \uae30\uc900 \uc790\ub3d9\uc138\uadf8\uba3c\ud2b8",
        "createdBy": "dashboard-auto",
        "targets": [{"externalId": t.get("brand_id", ""), "snapshot": t} for t in targets],
    })


def save_draft(segment_id, name, subject_tpl, body_tpl, targets):
    return call_tool("save_message_draft", {
        "segmentId": segment_id, "name": name,
        "subjectTemplate": subject_tpl, "bodyTemplate": body_tpl,
        "senderName": "\ud53c\uce58", "senderEmail": "pitch@08liter.com",
        "createdBy": "dashboard-auto", "targets": targets,
    })


def queue_review(draft_id, target_count):
    return call_tool("queue_for_review", {
        "draftId": draft_id, "actor": "dashboard-auto",
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
        r = requests.get(f"{MCP_URL}/api/tools", headers=_headers(), timeout=5)
        return r.status_code != 404
    except Exception:
        return False


# Keep old probe for backwards compat
def probe_server():
    return deep_probe()
