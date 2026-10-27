#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Call a ComfyUI MCP tool directly over stdio -- handy for debugging and for
inspecting a template's structure before you run it.

NOTE (MCP SDK 2.x): the Tool object attribute is `input_schema`,
NOT `inputSchema` (that was 1.x).

Usage:
    python scripts\\mcp_call.py <tool_name> '<json args>'
    python scripts\\mcp_call.py list_tools
    python scripts\\mcp_call.py describe <tool_name>

    python scripts\\mcp_call.py search_templates '{"query":"minimax"}'
    python scripts\\mcp_call.py fetch_template \\
        '{"name":"video_minimax_h3_i2v","out_path":"workflows/raw.json"}'
    python scripts\\mcp_call.py run_workflow \\
        '{"workflow_path":"workflows/h3_escape_10s.json","wait":false}'

Env vars:
    COMFY_MCP_BIN   path to comfy-mcp.exe   (isolated venv!)
    COMFY_BIN       path to comfy.exe       (octop conda env)
    COMFYMCP_VENV   isolated venv dir (alternative to COMFY_MCP_BIN)
    OCTOP_CONDA_ENV octop conda env dir (alternative to COMFY_BIN)
    COMFYUI_URL     e.g. http://127.0.0.1:8288 (only if not 8188)
"""

import asyncio
import json
import os
import sys

# Resolved from environment (set COMFYMCP_VENV / OCTOP_CONDA_ENV in a local .env).
# Falls back to a <placeholder> so a missing config fails with a clear error
# instead of silently pointing at someone else's machine path.
DEFAULT_MCP_BIN = (
    os.environ.get("COMFY_MCP_BIN")
    or os.environ.get("COMFYMCP_VENV", "<COMFYMCP_VENV>") + "/Scripts/comfy-mcp.exe"
)
DEFAULT_COMFY_BIN = (
    os.environ.get("COMFY_BIN")
    or os.environ.get("OCTOP_CONDA_ENV", "<OCTOP_CONDA_ENV>") + "/Scripts/comfy.exe"
)


def build_env():
    env = dict(os.environ)
    env["COMFY_BIN"] = os.environ.get("COMFY_BIN") or DEFAULT_COMFY_BIN
    if os.environ.get("COMFYUI_URL"):
        env["COMFYUI_URL"] = os.environ["COMFYUI_URL"]
        env["COMFY_LOCAL_URL"] = os.environ["COMFYUI_URL"]
    return env


async def run(mcp_bin, env):
    # import here so --help works without the SDK installed
    sys.path.insert(0, os.path.join(os.path.dirname(mcp_bin), "..", "Lib", "site-packages"))
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=mcp_bin, args=[], env=env)
    return stdio_client(params), ClientSession


def dump(obj, limit=4000):
    try:
        txt = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        txt = str(obj)
    print(txt[:limit])


async def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0

    cmd = sys.argv[1]
    mcp_bin = os.environ.get("COMFY_MCP_BIN") or DEFAULT_MCP_BIN
    env = build_env()

    if not os.path.exists(mcp_bin):
        print(f"[ERROR] comfy-mcp not found: {mcp_bin}")
        print("        Set COMFY_MCP_BIN or run scripts\\setup-comfymcp-venv.bat")
        return 1

    (ctx_factory, SessionCls) = await run(mcp_bin, env)
    async with ctx_factory as (r, w):
        async with SessionCls(r, w) as s:
            await s.initialize()

            if cmd == "list_tools":
                res = await s.list_tools()
                print("TOTAL TOOLS:", len(res.tools))
                for t in res.tools:
                    print("  -", t.name)
                return 0

            if cmd == "describe":
                res = await s.list_tools()
                for t in res.tools:
                    if t.name == sys.argv[2]:
                        print("=" * 30, t.name)
                        dump(t.input_schema, 3000)
                        return 0
                print(f"[ERROR] no such tool: {sys.argv[2]}")
                return 1

            args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
            res = await s.call_tool(cmd, args)
            for c in res.content:
                txt = getattr(c, "text", None)
                if txt:
                    try:
                        dump(json.loads(txt))
                    except Exception:
                        print(txt[:4000])
                else:
                    print(str(c)[:1500])
            if getattr(res, "isError", False):
                print("!! TOOL ERROR")
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
