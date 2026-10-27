#!/usr/bin/env python
"""诊断 Octop Agent 为什么"有 comfyui 连接件却不调用工具"。

按四个闸门依次检查：
  1. 会话模式（ask/plan 会整体摘掉 MCP）
  2. Agent 是否绑定 comfyui
  3. 连接件是否 active
  4. 上下文预算够不够（39 工具 schema ≈ 18.7k tokens）

用法:
    python scripts\\diagnose-agent-mcp.py BBGFVS
    OCTOP_PASS=xxx python scripts\\diagnose-agent-mcp.py BBGFVS

环境变量:
    OCTOP_URL    默认 http://127.0.0.1:8088
    OCTOP_USER   默认 admin
    OCTOP_PASS   必填（或交互输入）
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("OCTOP_URL", "http://127.0.0.1:8088").rstrip("/")

# 本地有 http_proxy 时访问 127.0.0.1 会拿到假的 502
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api(method: str, path: str, token: str | None = None, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with _opener.open(req, timeout=30) as r:
        body = r.read().decode()
        return json.loads(body) if body else None


def login(user: str, password: str) -> str:
    data = api("POST", "/api/auth/login", payload={"username": user, "password": password})
    return data["access_token"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", help="Agent ID，如 BBGFVS")
    ap.add_argument("--mcp-token-estimate", type=int, default=18700,
                    help="comfyui 39 工具的 token 估算值，默认 18700")
    args = ap.parse_args()

    user = os.environ.get("OCTOP_USER", "admin")
    password = os.environ.get("OCTOP_PASS") or getpass.getpass(f"{user} 的密码: ")
    token = login(user, password)

    problems: list[str] = []

    # ---- 1. Agent 绑定 ----
    agent = api("GET", f"/api/agents/{args.agent}", token)
    servers = agent.get("mcp_servers") or []
    print(f"[1] Agent {args.agent} ({agent.get('name')})")
    print(f"    model        : {agent.get('default_model')}")
    print(f"    mcp_servers  : {servers}")
    print(f"    conversation : {(agent.get('config') or {}).get('conversation_mode') or '(未设置 → craft)'}")
    if "comfyui" not in servers:
        problems.append("Agent 没有绑定 comfyui，控制台 → MCP 服务器里勾选")

    # ---- 2. 连接件状态 ----
    print("\n[2] 连接件")
    try:
        data = api("GET", "/api/connectors/custom-mcp", token)
        servers = data.get("servers") if isinstance(data, dict) else None
        # servers 以别名为 key：{"comfyui": {"transport": "stdio", "enabled": true, ...}}
        items = list(servers.items()) if isinstance(servers, dict) else []
        if not items:
            problems.append("没有自定义 MCP 连接件")
        for alias, cfg in items:
            cfg = cfg or {}
            enabled = cfg.get("enabled")
            print(f"    {alias}: {cfg.get('display_name')} enabled={enabled} transport={cfg.get('transport')}")
            print(f"        command={cfg.get('command')}")
            if not enabled:
                problems.append(f"连接件 {alias} 未启用")
            if not cfg.get("command"):
                problems.append(f"连接件 {alias} 缺 command")
    except urllib.error.HTTPError as e:
        print(f"    (接口不可用 {e.code}，跳过)")

    # ---- 3. 会话模式 ----
    print("\n[3] 会话模式")
    threads = api("GET", f"/api/agents/{args.agent}/threads", token)
    rows = threads if isinstance(threads, list) else threads.get("threads", [])
    rows = sorted(rows, key=lambda t: t.get("last_active") or 0, reverse=True)
    for t in rows[:5]:
        mode = t.get("conversation_mode") or "craft"
        flag = "  ← MCP 被摘掉" if mode in ("ask", "plan") else ""
        print(f"    {t.get('thread_id')}  mode={mode:<5} {str(t.get('title'))[:28]}{flag}")
        if mode in ("ask", "plan"):
            problems.append(f"会话 {t.get('thread_id')} 处于 {mode} 模式，MCP 不会注入；切 craft 或新开会话")

    # ---- 4. 上下文预算 ----
    print("\n[4] 上下文预算")
    providers = api("GET", "/api/admin/providers", token)
    rows = providers if isinstance(providers, list) else providers.get("providers", [])
    model_ref = agent.get("default_model") or ""
    pname, _, mid = model_ref.partition("/")
    hit = next((p for p in rows if p.get("name") == pname), None)
    if hit:
        m = next((x for x in hit.get("models", []) if x.get("id") == mid), None)
        if m:
            limit = m.get("max_input_tokens") or m.get("context_window")
            print(f"    {model_ref}: max_input_tokens={limit}")
            if isinstance(limit, int):
                budget = int(limit * 0.95)
                print(f"    可用输入预算 ≈ {budget} tokens（未扣 max_output）")
                print(f"    工具 schema 占 ≈ {args.mcp_token_estimate}")
                if budget - args.mcp_token_estimate < 8000:
                    problems.append(
                        f"{model_ref} 预算 {budget} 减去工具 {args.mcp_token_estimate} 后不足 8k，"
                        "多聊几轮就会 Context overflow；调大 max_input_tokens 或换大上下文模型"
                    )

    # ---- 结论 ----
    print("\n" + "=" * 56)
    if problems:
        print(f"发现 {len(problems)} 个问题：")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        sys.exit(1)
    print("四项全过。若模型仍不调用工具，看它是否在 Ask/Plan 提示下自行收手，")
    print("或新开会话排除历史污染。")


if __name__ == "__main__":
    main()
