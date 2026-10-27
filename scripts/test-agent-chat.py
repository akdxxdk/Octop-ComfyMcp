#!/usr/bin/env python
"""通过 Octop 真实对话通道（WebSocket）测试 Agent，查看技能是否被正确使用。

为什么不用 REST：Octop 的发消息接口是 WebSocket（`/api/agents/{id}/chat/ws`），
没有等价的 POST 端点，所以必须走 WS。

用法:
    python test-agent-chat.py "你的问题"
    python test-agent-chat.py "你的问题" craft --agent BBGFVS
    OCTOP_PASS=xxx python test-agent-chat.py "..." craft

环境变量:
    OCTOP_URL    默认 http://127.0.0.1:8088
    OCTOP_USER   默认 admin
    OCTOP_PASS   必填（或运行时交互输入）

输出:
    1. 帧类型统计（判断是否真的产生了输出）
    2. 工具调用列表（判断 Agent 有没有去读技能文件）
    3. 最终回答全文

依赖: websockets（Octop 自带环境 <OCTOP_CONDA_ENV>\\python.exe 已装）
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
import urllib.request
import uuid

try:
    import websockets
except ImportError:
    sys.exit("缺少 websockets，请用 Octop 自带 python 运行："
             "<OCTOP_CONDA_ENV>\\python.exe")

BASE_HTTP = os.environ.get("OCTOP_URL", "http://127.0.0.1:8088").rstrip("/")
BASE_WS = BASE_HTTP.replace("https://", "wss://").replace("http://", "ws://")

# 环境里有 http_proxy 时，访问 127.0.0.1 会得到假的 502，必须绕过
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def login(user: str, password: str) -> str:
    body = json.dumps({"username": user, "password": password}).encode()
    req = urllib.request.Request(f"{BASE_HTTP}/api/auth/login", data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    with _opener.open(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    # 注意：字段名是 access_token，不是 token
    return data["access_token"]


async def chat(agent: str, prompt: str, mode: str, token: str, timeout: float) -> list[dict]:
    url = f"{BASE_WS}/api/agents/{agent}/chat/ws?token={token}"
    frames: list[dict] = []
    done = asyncio.Event()

    async with websockets.connect(url, max_size=None, ping_interval=20) as ws:
        await ws.send(json.dumps({
            "type": "user_turn",
            "text": prompt,
            "conversation_mode": mode,
            # 随机 session_key：避免模型复述同一 thread 里的历史答案
            "session_key": f"test-{uuid.uuid4().hex[:8]}",
        }, ensure_ascii=False))

        async def reader() -> None:
            try:
                async for raw in ws:
                    try:
                        f = json.loads(raw)
                    except Exception:
                        f = {"type": "raw", "data": str(raw)[:300]}
                    frames.append(f)
                    t = f.get("type")
                    if t == "error":
                        print(f"  [ERROR] {f.get('message')}", flush=True)
                    if t in ("done", "error"):
                        done.set()
                        return
            except Exception as e:
                print(f"  [WS closed] {type(e).__name__}", flush=True)
                done.set()

        task = asyncio.create_task(reader())
        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            print(f"  [TIMEOUT {timeout:.0f}s — 小模型/大模型都可能卡在这里]", flush=True)
        task.cancel()

    return frames


def _walk_messages(obj, out: list[dict]) -> None:
    if isinstance(obj, dict):
        if "content" in obj and obj.get("type") in ("ai", "human", "tool"):
            out.append(obj)
        for v in obj.values():
            _walk_messages(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_messages(v, out)


def extract_answer(frames: list[dict]) -> str:
    toks = [f.get("text") or f.get("delta") or ""
            for f in frames if f.get("type") == "token"]
    streamed = "".join(t for t in toks if t)
    if streamed:
        return streamed

    msgs: list[dict] = []
    for f in frames:
        _walk_messages(f, msgs)
    ai = [m for m in msgs
          if m.get("type") == "ai" and isinstance(m.get("content"), str) and m["content"].strip()]
    if ai:
        return ai[-1]["content"]
    return "（无文本输出）"


def report(frames: list[dict]) -> None:
    types: dict[str, int] = {}
    for f in frames:
        k = f.get("type", "?")
        types[k] = types.get(k, 0) + 1
    print("\n=== 帧类型 ===")
    print(json.dumps(types, ensure_ascii=False, indent=1))

    print("\n=== 工具调用 ===")
    msgs: list[dict] = []
    for f in frames:
        _walk_messages(f, msgs)
    calls = []
    for m in msgs:
        for tc in (m.get("tool_calls") or []):
            name = tc.get("name") or (tc.get("function") or {}).get("name")
            args = tc.get("args") or (tc.get("function") or {}).get("arguments")
            calls.append((name, str(args)[:180]))
    if calls:
        for n, a in calls:
            print(f"  - {n}({a})")
    else:
        print("  (无 —— 说明模型没有主动读技能参考文件)")

    print("\n=== 回答 ===")
    print(extract_answer(frames)[:8000])


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", help="发给 Agent 的问题")
    ap.add_argument("mode", nargs="?", default="craft",
                    choices=["ask", "plan", "craft"], help="对话模式，默认 craft")
    ap.add_argument("--agent", default="BBGFVS", help="Agent ID，默认 BBGFVS")
    # 27B 模型一条 prompt 要 7-8 分钟。注意：客户端超时后服务端仍在跑，
    # 断线重连该 thread 仍能拿到完整结果，所以超时不必太紧张。
    ap.add_argument("--timeout", type=float, default=900.0, help="秒，默认 900（适配 27B）")
    args = ap.parse_args()

    user = os.environ.get("OCTOP_USER", "admin")
    password = os.environ.get("OCTOP_PASS") or getpass.getpass(f"{user} 的密码: ")

    print(f"=== 提问 ===\n{args.prompt}\n")
    token = login(user, password)
    frames = await chat(args.agent, args.prompt, args.mode, token, args.timeout)
    report(frames)


if __name__ == "__main__":
    asyncio.run(main())
