# 02 · aki 整合包路径 / 端口切换指南

> 适用场景：aki 整合包不在默认位置（换盘、重装、换目录），或端口也要改。
> 配套：`scripts\start-comfyui.bat`（已参数化）。

---

## 一、搬家前：先看清谁在引用这个路径

| # | 位置 | 搬家后要改吗 | 怎么改 |
|---|---|---|---|
| 1 | `scripts\start-comfyui.bat` 的 `DEFAULT_ROOT` | **要改**（改一行，或计划任务传参，文件都不用动） | 见场景 A |
| 2 | 计划任务 `ComfyUIAssistant` 的 WorkingDirectory | **建议同步改**（不改也能跑，bat 内部自己 `cd`） | 一条 PowerShell |
| 3 | Octop 连接器（存在 `~/.octop` 数据库） | **不用改**（只认端口，不认 aki 路径） | 仅端口变时才改，见场景 C |
| 4 | aki 内的 spacy 模型 `xx_sent_ud_sm` | 整体搬迁→不用；**换全新 aki→要重装** | 见场景 B |
| 5 | aki 内 `ComfyUI\extra_model_paths.yaml` | 整体搬迁→不用；**换全新 aki→要补** | 见场景 B |

**完全无关、不用碰的**：Octop 本体及 conda 环境、comfy-mcp / comfy-cli、共享模型目录 `<COMFY_SHARED_MODELS>`、连接器配置。

---

## 二、场景 A：整体搬迁（同一目录复制/剪切到新位置）

以搬到 `<COMFYUI_AKI_ROOT>` 为例。

**第 0 步 · 停掉当前 ComfyUI**

```bash
netstat -ano | grep ":8188"        # 记下 PID
taskkill //PID <PID> //F
```

**第 1 步 · 整目录复制**

```bash
robocopy <COMFYUI_AKI_ROOT> <COMFYUI_AKI_ROOT> /E
```

> robocopy 退出码 ≥1 都表示**成功**（复制了文件），不是错误。

确认无误后再删旧目录（建议先留一周）。

**第 2 步 · 改启动脚本（二选一）**

方式一（推荐）—— 只改一行：

```bat
REM 编辑 scripts\start-comfyui.bat
set "DEFAULT_ROOT=<COMFYUI_AKI_ROOT>"
```

方式二 —— 文件不动，计划任务传参（见第 3 步方式二）。

**第 3 步 · 更新计划任务（二选一）**

方式一 —— 只同步 WorkingDirectory：

```powershell
$newRoot = "<COMFYUI_AKI_ROOT>"
$t = Get-ScheduledTask -TaskName "ComfyUIAssistant"
$t.Actions[0].WorkingDirectory = "$newRoot\ComfyUI"
Set-ScheduledTask -TaskName "ComfyUIAssistant" -Action $t.Actions | Out-Null
(Get-ScheduledTask -TaskName "ComfyUIAssistant").Actions[0].WorkingDirectory   # 回显确认
```

方式二 —— 连参数一起传（脚本 `DEFAULT_ROOT` 可保留旧值不动）：

```powershell
$action = New-ScheduledTaskAction `
  -Execute "<项目路径>\scripts\start-comfyui.bat" `
  -Argument "<COMFYUI_AKI_ROOT>" `
  -WorkingDirectory "<COMFYUI_AKI_ROOT>\ComfyUI"
Set-ScheduledTask -TaskName "ComfyUIAssistant" -Action $action | Out-Null
```

**第 4 步 · 按第四节清单验证。**

---

## 三、场景 B：换成另一套全新 aki 安装

场景 A 的全部步骤之外，**多三项**（都在 aki 目录内部，不会随新包自动就位）：

**第 1 步 · 装 spacy 模型**

```bash
"新路径\python\python.exe" -m pip install --no-index --find-links "<wheel 目录>" xx-sent-ud-sm==3.8.0
```

wheel 若被清，重新下（走加速代理，约 250KB/s，**别直连**）：

```bash
curl -sL -o xx_sent_ud_sm-3.8.0-py3-none-any.whl \
  "https://gh-proxy.com/https://github.com/explosion/spacy-models/releases/download/xx_sent_ud_sm-3.8.0/xx_sent_ud_sm-3.8.0-py3-none-any.whl"
```

不装的后果：每次启动卡在 GitHub 慢速下载 5–8 分钟。

**第 2 步 · 建 `extra_model_paths.yaml`**

在 `新路径\ComfyUI\` 下建/覆盖该文件，内容见 [01-install.md §1.2](01-install.md#12-配置共享模型目录可选但推荐)。

**第 3 步 · 确认 `comfy_kitchen` 在位**

这是 H3 量化模型（NVFP4 / INT8 反量化核）的依赖。启动日志里应出现 comfy_kitchen 的 CUDA 后端可用字样；**若缺失，H3 模型一加载就报错**，需在 ComfyUI Manager 里补装。

---

## 四、场景 C：连端口也换（如 8188 被占，改用 8288）

**第 1 步** · `scripts\start-comfyui.bat` 里 `--port 8188` 改为新端口（只有一处）。

**第 2 步** · 连接器加 URL 并重新写入 Octop。

⚠️ 两个易错点：

- `comfyui-mcp-connector.json` 只是**存档副本，改它不生效**；真正生效的是 Octop 数据库里的连接器，**必须走 API 重新 PUT**（PUT 后自动重载 agent）。
- comfy-mcp 读地址优先级：`COMFYUI_URL`（完整 URL，只能写到 host:port，**不能带路径**）> `COMFYUI_HOST` + `COMFYUI_PORT` > 默认 `127.0.0.1:8188`。

```json
{
  "servers": {
    "comfyui": {
      "transport": "stdio",
      "command": "<COMFYMCP_VENV>/Scripts/comfy-mcp.exe",
      "env": {
        "COMFY_BIN": "<OCTOP_CONDA_ENV>/Scripts/comfy.exe",
        "COMFYUI_URL": "http://127.0.0.1:8288",
        "COMFY_LOCAL_URL": "http://127.0.0.1:8288"
      },
      "enabled": true,
      "shared": true,
      "default_open": true,
      "display_name": "ComfyUI 本地生成"
    }
  }
}
```

**第 3 步** · 探针验证（见第五节第 4 项）。

---

## 五、验证清单（5 项全过才算完成）

```bash
# 1) 手动启动（不依赖计划任务，先确认脚本本身对）
"<项目路径>\scripts\start-comfyui.bat"
#    期望：日志出现 To see the GUI go to http://127.0.0.1:8188
#    （窗口别关，它就是这个服务的本体）

# 2) HTTP 探活 —— 期望 200
curl -s --noproxy "*" --max-time 10 -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8188

# 3) comfy-cli 链路 —— 期望 server.running: true，url 指到新位置/新端口
"<OCTOP_CONDA_ENV>/Scripts/comfy.exe" env

# 4) Octop MCP 探针 —— 期望 ok: true，工具数 39
python scripts\verify.py

# 5) 手动触发一次计划任务，确认开机自启链也指向新路径
Start-ScheduledTask -TaskName "ComfyUIAssistant"
```

---

## 六、最短路径回忆卡

| 你想干嘛 | 操作 |
|---|---|
| 整体搬到 `<COMFYUI_AKI_ROOT>` | 改 bat 的 `DEFAULT_ROOT` 一行 + PowerShell 同步 WorkingDirectory |
| 不想改 bat | 计划任务 Arguments 传新根目录 |
| 换成全新 aki | 场景 A + 装 spacy wheel + 补 `extra_model_paths.yaml` + 查 `comfy_kitchen` |
| 端口也换 | bat 改 `--port` + 连接器 env 加 `COMFYUI_URL` + 重新 PUT + 探针 |
| 验证 | 手动跑 bat → curl 200 → `comfy env` → MCP 探针 39 工具 → 触发计划任务 |
