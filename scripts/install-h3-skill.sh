#!/usr/bin/env bash
# 安装 MiniMax 官方 h3-prompt-writing 技能到指定 Octop Agent
#
# 用法:
#   ./install-h3-skill.sh --agent BBGFVS
#   ./install-h3-skill.sh --agent BBGFVS --octop-home /c/Users/me/.octop
#   ./install-h3-skill.sh --agent BBGFVS --no-local-notes   # 不装本机适配文档
#
# 说明:
#   1. 从 jsDelivr 镜像拉取 MiniMax-AI/MiniMax-H3 的 skills/h3-prompt-writing
#      （raw.githubusercontent.com 在部分网络环境直连不通，故走镜像）
#   2. 复制到 <octop-home>/agents/<AGENT_ID>/.octop/skills/h3-prompt-writing/
#   3. 可选：并入本仓库的本机落地适配文档 local-comfyui-notes.md
#   4. 调用 Octop API 重载该 Agent 使其生效
#
# 无 npx / gh CLI 依赖，仅需 curl 与 bash。

set -euo pipefail

REPO="MiniMax-AI/MiniMax-H3"
REF="${REF:-main}"
SLUG="h3-prompt-writing"
MIRROR="${MIRROR:-https://cdn.jsdelivr.net/gh}"

AGENT_ID=""
OCTOP_HOME="${OCTOP_HOME:-$HOME/.octop}"
WITH_LOCAL_NOTES=1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)           AGENT_ID="$2"; shift 2;;
    --octop-home)      OCTOP_HOME="$2"; shift 2;;
    --ref)             REF="$2"; shift 2;;
    --no-local-notes)  WITH_LOCAL_NOTES=0; shift;;
    -h|--help)         usage;;
    *) echo "未知参数: $1"; usage;;
  esac
done

if [[ -z "$AGENT_ID" ]]; then
  echo "错误: 必须用 --agent 指定 Agent ID（如 BBGFVS）"
  echo "可用 Agent 列表："
  ls -1 "$OCTOP_HOME/agents" 2>/dev/null | sed 's/^/  /' || true
  exit 1
fi

BASE_URL="$MIRROR/$REPO@$REF/skills/$SLUG"
DEST="$OCTOP_HOME/agents/$AGENT_ID/.octop/skills/$SLUG"

if [[ ! -d "$OCTOP_HOME/agents/$AGENT_ID" ]]; then
  echo "错误: Agent 目录不存在 -> $OCTOP_HOME/agents/$AGENT_ID"
  exit 1
fi

echo "目标 Agent : $AGENT_ID"
echo "安装位置   : $DEST"
echo "源         : $BASE_URL"
echo

mkdir -p "$DEST/references"

fetch() {
  local rel="$1" out="$2"
  printf '  下载 %-28s' "$rel"
  if curl -fsSL --max-time 60 -o "$out" "$BASE_URL/$rel"; then
    printf ' ✓ (%s bytes)\n' "$(wc -c < "$out" | tr -d ' ')"
  else
    printf ' ✗ 失败\n'
    echo "     提示：可换镜像重试  MIRROR=https://gh-proxy.com/https://raw.githubusercontent.com $0 --agent $AGENT_ID"
    exit 1
  fi
}

fetch "SKILL.md"                  "$DEST/SKILL.md"
fetch "references/base-en.txt"    "$DEST/references/base-en.txt"
fetch "references/ref-en.txt"     "$DEST/references/ref-en.txt"
# 可选文件，缺失不影响
curl -fsSL --max-time 30 -o "$DEST/agents/openai.yaml" "$BASE_URL/agents/openai.yaml" 2>/dev/null \
  && echo "  下载 agents/openai.yaml          ✓" || true

# 应用本仓库的增强版（中文 name/description + 本机落地章节 + 适配文档）
# 用 --no-local-notes 可保留 MiniMax 官方原版 SKILL.md
if [[ "$WITH_LOCAL_NOTES" -eq 1 ]]; then
  LOCAL_DIR="$SCRIPT_DIR/../experts/ai-drama-director/skills/$SLUG"
  if [[ -f "$LOCAL_DIR/SKILL.md" ]]; then
    cp "$LOCAL_DIR/SKILL.md" "$DEST/SKILL.md"
    echo "  应用增强版 SKILL.md              ✓（中文化 + 本机落地章节）"
  fi
  if [[ -f "$LOCAL_DIR/references/local-comfyui-notes.md" ]]; then
    cp "$LOCAL_DIR/references/local-comfyui-notes.md" "$DEST/references/local-comfyui-notes.md"
    echo "  并入本机落地适配文档             ✓ (local-comfyui-notes.md)"
  fi
  if [[ ! -d "$LOCAL_DIR" ]]; then
    echo "  未找到本仓库增强目录，保留官方原版"
  fi
fi

echo
echo "已安装文件："
find "$DEST" -type f | sed "s|$DEST/|  - |"

# ---- 重载 Agent ----
echo
if command -v curl >/dev/null 2>&1 && curl -fsS --noproxy '*' -m 5 "http://127.0.0.1:8088/api/health" >/dev/null 2>&1; then
  read -r -p "Octop 服务在线，是否现在重载 Agent 使技能生效? [Y/n] " ans
  ans="${ans:-Y}"
  if [[ "$ans" =~ ^[Yy]$ ]]; then
    read -r -p "Octop 管理员用户名 [admin]: " OU; OU="${OU:-admin}"
    read -r -s -p "密码: " OP; echo
    TOKEN=$(curl -sS --noproxy '*' -m 20 -X POST "http://127.0.0.1:8088/api/auth/login" \
              -H "Content-Type: application/json" \
              -d "{\"username\":\"$OU\",\"password\":\"$OP\"}" \
            | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    if [[ -n "$TOKEN" ]]; then
      code=$(curl -sS --noproxy '*' -m 30 -o /dev/null -w '%{http_code}' \
               -X POST "http://127.0.0.1:8088/api/agents/$AGENT_ID/reload" \
               -H "Authorization: Bearer $TOKEN")
      echo "重载 Agent -> HTTP $code"
      curl -sS --noproxy '*' -m 30 "http://127.0.0.1:8088/api/agents/$AGENT_ID/skills" \
        -H "Authorization: Bearer $TOKEN" \
        | grep -o "\"slug\": *\"$SLUG\"" >/dev/null \
        && echo "✓ 技能已在技能列表中生效" \
        || echo "⚠ 未在技能列表中找到，请检查 Octop 控制台"
    else
      echo "登录失败，跳过重载（手动执行：控制台重启该 Agent）"
    fi
  fi
else
  echo "Octop 服务未运行或不可达，跳过重载。"
  echo "启动后手动重载：POST /api/agents/$AGENT_ID/reload"
fi

echo
echo "完成。该 Agent 现在可按官方结构撰写 H3 prompt。"
