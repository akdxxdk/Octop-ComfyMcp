#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Write the ComfyUI MCP connector config into Octop's database.

SECURITY: credentials are NEVER hardcoded. Resolution order:
    1. --username / --password  (CLI args)
    2. OCTOP_USER / OCTOP_PASS  (env vars)
    3. interactive prompt       (getpass)

Usage:
    python scripts\\setup-connector.py
    python scripts\\setup-connector.py --config config\\comfyui-mcp-connector.json
    python scripts\\setup-connector.py --dry-run        # print, do not write

Connector config may use ${VAR} placeholders (e.g. ${COMFYMCP_VENV}); they are
expanded from environment / a local .env (copy from .env.example) before PUT.
"""

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

# ${VAR} expansion for portable, path-free connector configs.
import re

DEFAULT_URL = "http://127.0.0.1:8088/api"
DEFAULT_CONFIG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "comfyui-mcp-connector.json",
)

# Never trust the ambient proxy for loopback traffic: an http_proxy in the
# environment returns a bogus 502 for 127.0.0.1 and sends you chasing ghosts.
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


# ---------------------------------------------------------------------------
# Portable config: load .env and expand ${VAR} placeholders
# ---------------------------------------------------------------------------
DOTENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".env",
)


def load_dotenv(path=DOTENV_PATH):
    """Minimal .env loader (KEY=VALUE; '#' comments and blanks ignored).

    Existing environment variables win (setdefault) so shell exports and
    CLI args take precedence over a local .env file.
    """
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


_VAR_RE = re.compile(r"\$\{(\w+)\}")


def expand_obj(obj):
    """Recursively expand ${VAR} in every string; return (obj, missing_vars)."""
    if isinstance(obj, str):
        miss = []

        def _sub(m):
            name = m.group(1)
            if name not in os.environ:
                miss.append(name)
                return m.group(0)
            return os.environ[name]

        return _VAR_RE.sub(_sub, obj), miss
    if isinstance(obj, dict):
        out, miss = {}, []
        for k, v in obj.items():
            if k == "_comment":
                out[k] = v  # keep illustrative ${VAR} text verbatim
                continue
            e, m = expand_obj(v)
            out[k], miss = e, miss + m
        return out, miss
    if isinstance(obj, list):
        out, miss = [], []
        for v in obj:
            e, m = expand_obj(v)
            out.append(e)
            miss.extend(m)
        return out, miss
    return obj, []


def req(method, path, body=None, token=None, base=DEFAULT_URL, timeout=120):
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


def resolve_credentials(args):
    user = args.username or os.environ.get("OCTOP_USER")
    pwd = args.password or os.environ.get("OCTOP_PASS")
    if not user:
        user = input("Octop username [admin]: ").strip() or "admin"
    if not pwd:
        pwd = getpass.getpass("Octop password: ")
    return user, pwd


def main():
    ap = argparse.ArgumentParser(description="Write ComfyUI MCP connector into Octop")
    ap.add_argument("--url", default=DEFAULT_URL, help="Octop API base (default: %(default)s)")
    ap.add_argument("--config", default=DEFAULT_CONFIG, help="connector JSON path")
    ap.add_argument("--username")
    ap.add_argument("--password")
    ap.add_argument("--dry-run", action="store_true", help="print payload, do not write")
    args = ap.parse_args()

    if not os.path.exists(args.config):
        print(f"[ERROR] config not found: {args.config}")
        print("        Copy config/comfyui-mcp-connector.example.json and edit it.")
        return 1

    cfg = json.load(open(args.config, encoding="utf-8"))
    load_dotenv()
    cfg, missing = expand_obj(cfg)
    if missing:
        uniq = sorted(set(missing))
        print(f"[ERROR] connector config references undefined variables: {uniq}")
        print("        Define them in a local .env (copy .env.example) or export them,")
        print("        or replace ${VAR} in the config with real absolute paths.")
        return 1
    servers = cfg.get("servers", {})
    if "comfyui" not in servers:
        print("[ERROR] config must contain servers.comfyui")
        return 1

    entry = servers["comfyui"]
    print("Connector payload:")
    print(json.dumps(entry, ensure_ascii=False, indent=2))

    # sanity: command must point at the ISOLATED env, not Octop's main env
    cmd = (entry.get("command") or "").replace("\\", "/")
    comfy_bin = ((entry.get("env") or {}).get("COMFY_BIN") or "").replace("\\", "/")
    if "comfy.exe" in cmd and "comfymcp" not in cmd:
        print()
        print("[WARN] command points into Octop's main env.")
        print("       comfy-mcp MUST run from its own venv (see docs/03-mcp-isolation.md).")
        if not args.dry_run:
            ans = input("       Continue anyway? [y/N] ").strip().lower()
            if ans != "y":
                return 1

    if args.dry_run:
        print("\n[dry-run] nothing written.")
        return 0

    user, pwd = resolve_credentials(args)
    st, out = req("POST", "/auth/login", {"username": user, "password": pwd}, base=args.url)
    if st != 200 or not isinstance(out, dict) or not out.get("access_token"):
        print(f"[ERROR] login failed (HTTP {st}): {str(out)[:300]}")
        print("        Check the URL and credentials (env: OCTOP_USER / OCTOP_PASS).")
        return 1
    token = out["access_token"]
    print("\n[OK] logged in")

    st, out = req("PUT", "/connectors/custom-mcp", cfg, token=token, base=args.url)
    print(f"PUT /connectors/custom-mcp -> HTTP {st}")
    if st >= 400:
        print(str(out)[:800])
        return 1

    st, after = req("GET", "/connectors/custom-mcp", token=token, base=args.url)
    if st == 200 and isinstance(after, dict):
        s = after.get("servers", {}).get("comfyui", {})
        print("\nCurrent effective config:")
        print(f"  enabled : {s.get('enabled')}")
        print(f"  command : {s.get('command')}")
        print(f"  env     : {s.get('env')}")
    else:
        print(f"[WARN] read-back failed (HTTP {st})")

    print("\nNext: python scripts\\verify.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
