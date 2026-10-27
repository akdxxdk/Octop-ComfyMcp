#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Full end-to-end verification of the Octop <-> ComfyUI MCP setup.

Checks:
    [1] auth/login      - obtain JWT (field name: access_token)
    [2] health          - db up, agents running
    [3] agents          - which agents have comfyui bound
    [4] mcp connector   - enabled + command path
    [5] mcp probe       - ok=True, tool count
    [6] comfyui 8188    - HTTP reachable, GPU visible

SECURITY: credentials via --password / OCTOP_PASS / interactive prompt only.

Usage:
    python scripts\\verify.py
    python scripts\\verify.py --url http://127.0.0.1:8088/api --comfy http://127.0.0.1:8188
"""

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8088/api"
DEFAULT_COMFY = "http://127.0.0.1:8188"
EXPECTED_TOOLS = 39

# Loopback must bypass any ambient proxy, otherwise you get a fake 502.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def req(method, path, body=None, token=None, base=DEFAULT_URL, timeout=150):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with OPENER.open(r, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except Exception:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def main():
    ap = argparse.ArgumentParser(description="Verify Octop <-> ComfyUI MCP")
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--comfy", default=DEFAULT_COMFY)
    ap.add_argument("--username")
    ap.add_argument("--password")
    args = ap.parse_args()

    user = args.username or os.environ.get("OCTOP_USER") or "admin"
    pwd = args.password or os.environ.get("OCTOP_PASS")
    if not pwd:
        pwd = getpass.getpass(f"Octop password for {user}: ")

    fails = []

    # [1] login
    st, out = req("POST", "/auth/login", {"username": user, "password": pwd}, base=args.url)
    if st != 200 or not isinstance(out, dict) or not out.get("access_token"):
        print(f"[1] auth/login            : FAIL (HTTP {st}) {str(out)[:200]}")
        return 1
    tok = out["access_token"]
    print("[1] auth/login            : 200 OK")

    # [2] health
    st, o = req("GET", "/health", token=tok, base=args.url)
    if st == 200 and isinstance(o, dict):
        print(f"[2] health                : ok={o.get('ok')} db={o.get('db')} agents_running={o.get('agents_running')}")
        if not o.get("ok") or not o.get("db"):
            fails.append("health/db")
    else:
        print(f"[2] health                : FAIL (HTTP {st})")
        fails.append("health")

    # [3] agents
    st, o = req("GET", "/agents", token=tok, base=args.url)
    lst = o if isinstance(o, list) else ((o or {}).get("data") or [])
    bound = [a.get("name") for a in lst if a.get("mcp_servers")]
    print(f"[3] agents                : {len(lst)} 个  |  绑定 MCP: {bound}")
    if not bound:
        fails.append("no agent has comfyui bound")

    # [4] connector
    st, o = req("GET", "/connectors/custom-mcp", token=tok, base=args.url)
    if st == 200 and isinstance(o, dict):
        c = o.get("servers", {}).get("comfyui", {})
        print(f"[4] mcp connector         : enabled={c.get('enabled')} cmd={c.get('command')}")
        if not c.get("enabled"):
            fails.append("connector disabled")
        cmd = (c.get("command") or "").replace("\\", "/")
        if "comfymcp" not in cmd:
            fails.append("command not pointing at isolated venv")
    else:
        print(f"[4] mcp connector         : FAIL (HTTP {st})")
        fails.append("connector read")

    # [5] probe
    st, o = req("POST", "/connectors/custom-mcp/test", {"name": "comfyui"}, token=tok, base=args.url)
    if isinstance(o, dict):
        ok = o.get("ok")
        n = len(o.get("tools") or [])
        err = o.get("error") or "-"
        print(f"[5] mcp probe             : ok={ok} tools={n} err={err}")
        if not ok or n == 0:
            fails.append("probe failed (see docs/03-mcp-isolation.md)")
        elif EXPECTED_TOOLS and n != EXPECTED_TOOLS:
            print(f"    [note] expected {EXPECTED_TOOLS} tools, got {n}")
    else:
        print(f"[5] mcp probe             : FAIL (HTTP {st})")
        fails.append("probe")

    # [6] comfyui
    try:
        r = urllib.request.Request(args.comfy + "/system_stats")
        with OPENER.open(r, timeout=10) as x:
            s = json.loads(x.read().decode())
        devs = [d.get("name") for d in (s.get("devices") or [])][:2]
        print(f"[6] comfyui {args.comfy.split('//')[-1]:<16}: 200  devices={devs}")
    except Exception as e:
        print(f"[6] comfyui               : FAIL {e}")
        fails.append("comfyui unreachable")

    print()
    if fails:
        print("RESULT: FAILED -> " + "; ".join(fails))
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
