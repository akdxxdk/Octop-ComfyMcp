# 03 · MCP 依赖隔离（最重要的一篇）

> 如果你遇到 MCP 探针报 `Connection closed`、工具数从 39 掉到 0，**先看这里**。
> 这是本方案唯一一个"必须这么干、没有替代方案"的约束。

---

## 一、故障现象

升级 Octop 到 1.0.2 正式版后：

```
mcp probe : ok=False  error=Connection closed  tools=0
```

之前明明是 `ok=True tools=39`。

---

## 二、根因：MCP SDK 1.x / 2.x 在同一环境互斥

| 组件 | 需要的 MCP SDK | 导入路径 |
|---|---|---|
| `comfy-mcp` 0.10.0 | **2.x** | `mcp.server.mcpserver` |
| `langchain-mcp-adapters`（Octop 的 MCP 客户端） | **1.x** | `mcp.server.fastmcp.*`（**顶层导入**） |

### 诊断线索

`uv pip install octop==1.0.2` 的依赖解析把 `mcp` 主包降到了 **1.30.0**，但 `mcp-types` 仍是 **2.3.0** —— **这个版本错位本身就是最明显的线索**：

```bash
pip list | grep -i mcp
# mcp        1.30.0     ← 被降级
# mcp-types  2.3.0      ← 没动
```

而 `langchain_mcp_adapters/tools.py:27-28` 是**顶层导入** `mcp.server.fastmcp.*`：

```python
from mcp.server.fastmcp.client.logging import MessageHandler
from mcp.server.fastmcp.utilities.logging import get_logger
```

所以：

- **把主环境升到 mcp 2.x** → Octop 的 MCP 客户端**整体 ImportError**，所有 MCP 连接器全挂
- **降回 1.x** → comfy-mcp 起不来

**结论：不能靠升降级解决，只能隔离。**

---

## 三、解法：comfy-mcp 独立 venv

```bat
<CONDA_BASE>/python.exe -m venv <COMFYMCP_VENV>
<COMFYMCP_VENV>\Scripts\python.exe -m pip install ^
  -i https://mirrors.aliyun.com/pypi/simple "mcp==2.3.0" "comfy-mcp==0.10.0"
```

最终布局：

| 环境 | 内容 | 约束 |
|---|---|---|
| `<COMFYMCP_VENV>` | mcp 2.3.0 + mcp-types 2.3.0 + comfy-mcp 0.10.0 | 只给 comfy-mcp 用 |
| `<OCTOP_CONDA_ENV>` | Octop + comfy-cli 1.22.0 + mcp **1.30.0** | **mcp 版本不要动** |

连接器配置相应调整：

- `command` → `<COMFYMCP_VENV>/Scripts/comfy-mcp.exe`
- `env.COMFY_BIN` → **保持不变**，仍指向 octop 环境的 `comfy.exe`

验证：`ok=True`，39 个工具恢复。

---

## 四、四条关键坑（都踩过）

### 1. `--noproxy` 必须加

环境里有 `http_proxy=http://127.0.0.1:61656`。不加 `--noproxy "*"` 会拿到**假的 `502 Bad Gateway`**，让你误判成 Octop 服务挂了、白白排查半天。

```bash
# ✅ 正确
curl -s --noproxy "*" http://127.0.0.1:8088/api/health

# ❌ 会拿到假 502
curl -s http://127.0.0.1:8088/api/health
```

Python 里同理：

```python
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
```

### 2. 改配置必须走 API

`comfyui-mcp-connector.json` 是**存档副本，改它不生效**。真正生效的配置在 Octop 数据库里：

```
PUT /api/connectors/custom-mcp      # 写入（PUT 后自动重载 agent）
GET /api/connectors/custom-mcp      # 读取
POST /api/connectors/custom-mcp/test  # 探针
```

### 3. Git Bash 里 `export PATH="a;b;$PATH"` 不生效

分号分隔会被吃掉。启动时**直接用可执行文件的绝对路径**：

```bash
# ❌ PATH 不会生效
export PATH="<OCTOP_CONDA_ENV>/Scripts;$PATH" && octop.exe run

# ✅
"<OCTOP_CONDA_ENV>/Scripts/octop.exe" run
```

### 4. 登录接口返回的是 `access_token`，不是 `token`

```python
tok = response["access_token"]   # ✅
tok = response["token"]          # ❌ KeyError
```

---

## 五、API 速查

| 用途 | 方法 | 路径 |
|---|---|---|
| 登录（取 token） | POST | `/api/auth/login` |
| 健康检查 | GET | `/api/health` |
| Agent 列表 | GET | `/api/agents` |
| 挂载 MCP | PATCH | `/api/agents/<id>` |
| 读连接器 | GET | `/api/connectors/custom-mcp` |
| 写连接器 | PUT | `/api/connectors/custom-mcp` |
| 探针测试 | POST | `/api/connectors/custom-mcp/test` |

> 注意：路径都要带 `/api` 前缀；鉴权用 `Authorization: Bearer <access_token>`。

---

## 六、一键验证

```bash
python scripts\verify.py
```

全绿输出：

```
[1] auth/login            : 200 OK
[2] health                : ok=True db=True agents_running=10
[3] agents                : 10 个 | 绑定 MCP: ['案例包装官']
[4] mcp connector         : enabled=True cmd=<COMFYMCP_VENV>/Scripts/comfy-mcp.exe
[5] mcp probe             : ok=True tools=39
[6] comfyui 8188          : 200  devices=['cuda:0 NVIDIA GeForce RTX 5060 Ti']
```
