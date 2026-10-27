# 01 · 完整安装部署流程

> 本文所有命令均在 Windows 11 + RTX 5060 Ti 16GB 本机实测通过（2026-10-19）。
> 路径请按你的实际环境替换。

---

## 0. 组件关系速览

| 组件 | 安装位置 | 作用 |
|---|---|---|
| **Octop** | conda 环境 `octop` | AI 平台本体（8088） |
| **ComfyUI** | aki 整合包 | 生成本体（8188） |
| **comfy-cli** | conda 环境 `octop` | 命令行客户端，comfy-mcp 靠它调 ComfyUI |
| **comfy-mcp** | **独立 venv** `<COMFYMCP_VENV>` | MCP 服务器，暴露 39 个工具 |

⚠️ 最后一行是硬要求，不是建议。原因见 [03-mcp-isolation.md](03-mcp-isolation.md)。

---

## 1. 准备 ComfyUI（秋叶 aki 整合包）

### 1.1 确认真实根目录

aki 整合包有个容易踩的坑：**ComfyUI 本体在根目录的下一层**。

```
<COMFYUI_AKI_ROOT>\          ← 整合包根目录（启动器、python）
    ├── ComfyUI\            ← ★ 真正的 ComfyUI 根目录
    │   ├── main.py
    │   ├── custom_nodes\   ← 自定义节点在这层
    │   ├── input\          ← 起始图放这里
    │   ├── output\         ← 成品输出到这里
    │   └── extra_model_paths.yaml
    └── python\python.exe   ← 整合包自带解释器
```

在错误的层级找 `custom_nodes` 会得到"节点缺失"的误判 —— 这个坑我们踩过一次。

### 1.2 配置共享模型目录（可选但推荐）

编辑 `ComfyUI\extra_model_paths.yaml`，把模型统一指向共享目录：

```yaml
shared_models:
  base_path: <COMFY_SHARED_MODELS>
  is_default: true      # Manager 下载直接进共享文件夹

  checkpoints: checkpoints/
  loras: loras/
  vae: vae/
  controlnet: controlnet/
  clip: clip/
  clip_vision: clip_vision/
  diffusion_models: diffusion_models/
  upscale_models: upscale_models/
  embeddings: embeddings/
  text_encoders: text_encoders/
```

好处：多套 ComfyUI 共用一份模型，换整合包不用重新下几十 GB。

### 1.3 预装 spacy 模型（必做，否则每次启动卡 5–8 分钟）

aki 首次启动时 `controlnet_aux` 会从 GitHub 拉 `xx_sent_ud_sm`，直连只有 ~20KB/s。

用加速镜像提前装好：

```bash
curl -sL -o xx_sent_ud_sm-3.8.0-py3-none-any.whl \
  "https://gh-proxy.com/https://github.com/explosion/spacy-models/releases/download/xx_sent_ud_sm-3.8.0/xx_sent_ud_sm-3.8.0-py3-none-any.whl"

"<COMFYUI_AKI_ROOT>\python\python.exe" -m pip install --no-index --find-links . xx_sent_ud_sm-3.8.0-py3-none-any.whl
```

### 1.4 启动

```bat
scripts\start-comfyui.bat <COMFYUI_AKI_ROOT>
```

验证：`curl --noproxy "*" -o /dev/null -w "%{http_code}" http://127.0.0.1:8188` → 期望 `200`。

---

## 2. 安装 Octop

```bash
conda create -n octop python=3.12 -y
conda activate octop
pip install octop==1.0.2
```

数据目录默认在 `%USERPROFILE%\.octop`（含 `octop.db`、`config.json`、`secrets`）。

启动：

```bat
scripts\start-octop.bat
```

首次启动会打印管理员账号和随机密码，**记下来**。

---

## 3. 安装 comfy-cli + comfy-mcp

### 3.1 comfy-cli → Octop 主环境

```bash
conda activate octop
pip install comfy-cli==1.22.0
```

验证：`comfy --version`

### 3.2 comfy-mcp → **独立 venv**

```bat
scripts\setup-comfymcp-venv.bat
```

> 该脚本读取仓库根 `comfy-mcp-requirements.txt`（锁定 `mcp==2.3.0` + `comfy-mcp==0.10.0`）创建隔离 venv。
> 运行前请把 `.env.example` 复制为 `.env` 并填好 `COMFYMCP_VENV` / `OCTOP_CONDA_ENV`（见仓库根 `.env.example`）。

等价于：

```bat
<CONDA_BASE>/python.exe -m venv <COMFYMCP_VENV>
<COMFYMCP_VENV>\Scripts\python.exe -m pip install ^
  -i https://mirrors.aliyun.com/pypi/simple "mcp==2.3.0" "comfy-mcp==0.10.0"
```

验证：

```bash
"<COMFYMCP_VENV>\Scripts\python.exe" -c "from mcp.server.mcpserver import MCPServer; import comfy_mcp.server; print('OK')"
```

---

## 4. 写入 MCP 连接器配置

> ⚠️ **改文件不生效**。生效配置存在 Octop 数据库里，必须走 API。

两种填法（二选一）：

**A. 手动填路径**：复制示例并编辑
```bash
cp config/comfyui-mcp-connector.example.json config/comfyui-mcp-connector.json
```
把其中的 `${COMFYMCP_VENV}` / `${OCTOP_CONDA_ENV}` 换成你的真实绝对路径。

**B. 环境变量驱动（推荐，不落盘真实路径）**：在 `.env` 里设好
`COMFYMCP_VENV` 与 `OCTOP_CONDA_ENV`，直接运行 `setup-connector.py`，
脚本会先把 `${VAR}` 占位符展开成环境变量值，再 `PUT` 进 Octop。

`setup-connector.py` 读取的字段：

| 字段 | 填什么 |
|---|---|
| `command` | 隔离环境的 `comfy-mcp.exe` 绝对路径 |
| `env.COMFY_BIN` | octop 环境的 `comfy.exe` 绝对路径 |
| `env.COMFYUI_URL` | 可选，仅当端口不是 8188 |

然后写入：

```bash
python scripts\setup-connector.py
```

脚本会先登录取 token、再 `PUT /api/connectors/custom-mcp`，PUT 后 Octop 自动重载 agent。

---

## 5. 给 Agent 挂载

控制台：编辑 Agent → MCP 服务器 → 勾选 `comfyui`。

或 API：

```bash
curl -X PATCH http://127.0.0.1:8088/api/agents/<AGENT_ID> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mcp_servers":["comfyui"]}'
```

---

## 6. 验证

```bash
python scripts\verify.py
```

六项全绿：

```
[1] auth/login            : 200 OK
[2] health                : ok=True db=True agents_running=10
[3] agents                : 10 个 | 绑定 MCP: ['案例包装官']
[4] mcp connector         : enabled=True cmd=<COMFYMCP_VENV>/Scripts/comfy-mcp.exe
[5] mcp probe             : ok=True tools=39
[6] comfyui 8188          : 200  devices=['cuda:0 NVIDIA GeForce RTX 5060 Ti']
```

---

## 7. 开机自启（可选）

两个计划任务，都是"用户登录时触发"：

```powershell
$action = New-ScheduledTaskAction `
  -Execute "<项目路径>\scripts\start-comfyui.bat" `
  -Argument "<COMFYUI_AKI_ROOT>" `
  -WorkingDirectory "<COMFYUI_AKI_ROOT>\ComfyUI"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "ComfyUIAssistant" -Action $action -Trigger $trigger
```

Octop 同理，脚本为 `start-octop.bat`。

---

## 8. 升级 Octop 的正确姿势

`octop update` 在 Windows 下会因 `octop.exe` 自锁失败（文件占用无法改名）。

**改用直装**：

1. 停止 `octop.exe` 进程（任务管理器或 `taskkill`）
2. 备份数据目录：`xcopy %USERPROFILE%\.octop <备份路径> /E /H`
3. 直装：

```bash
<CONDA_BASE>/Scripts/uv pip install ^
  --python <OCTOP_CONDA_ENV>\python.exe ^
  --index-url https://mirrors.aliyun.com/pypi/simple "octop==1.0.2"
```

4. 重启后**必跑一次** `scripts\verify.py` —— 升级会重新解析依赖，很可能把 `mcp` 版本改掉，见 [03](03-mcp-isolation.md)。

### 回滚

```bash
# 1. 停进程
# 2. 备份当前 octop.db
# 3. 用备份目录整目录覆盖 %USERPROFILE%\.octop
# 4. 降级安装
uv pip install --python <OCTOP_CONDA_ENV>\python.exe "octop==1.0.2b9"
```
