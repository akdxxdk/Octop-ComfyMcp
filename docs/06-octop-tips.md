# 06 · Octop 使用技巧（非 MCP 部分）

部署过程中积累的 Octop 侧经验，与 ComfyUI 无关但对运维有用。

---

## 一、改了 SOUL.md 人设却不生效

### 现象

在工作目录里改了 `SOUL.md`，reload 之后 Agent 行为没变化。

### 原因

在 Octop 1.0.2 里，工作目录下的 `SOUL.md` **不会**自动成为 Agent 人设。

`manifest.json` 里的 `prompt_files` 只是**仪表盘元数据**，不参与运行时。真正生效的人设存在 `agents` 表的 `system_prompt` 字段里，由 manager reload 时应用。

### 解法：同步脚本

```bash
# 查看哪些 agent 的人设与文件不一致
python scripts\sync-persona.py --list

# 同步全部有 SOUL.md 的 agent
python scripts\sync-persona.py

# 只同步指定 agent
python scripts\sync-persona.py 90ZHGP
```

脚本会自动扫描 `~/.octop/agents/` 下所有含 `SOUL.md` 的目录，把文件内容写进数据库。

写完再 reload：

```bash
octop agent reload <AGENT_ID>
```

> ⚠️ 写库前先停 Octop 服务，并备份 `octop.db`。

---

## 二、开机自启

Octop 服务和 ComfyUI 都用计划任务在**用户登录时**拉起：

```powershell
# ComfyUI
$action = New-ScheduledTaskAction `
  -Execute "<项目路径>\scripts\start-comfyui.bat" `
  -Argument "<COMFYUI_AKI_ROOT>" `
  -WorkingDirectory "<COMFYUI_AKI_ROOT>\ComfyUI"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "ComfyUIAssistant" -Action $action -Trigger $trigger

# Octop（同理，脚本为 start-octop.bat）
Register-ScheduledTask -TaskName "OctopAssistant" -Action $octopAction -Trigger $trigger
```

> 注意：某些沙箱/会话环境会在工具调用结束后回收进程，靠计划任务维持是可靠的做法。

---

## 三、常用命令

```bash
octop provider list         # 查看模型供应商
octop provider test 1       # 测试本地模型连通性
octop models list           # 查看可用模型
octop models active         # 查看当前默认模型
octop agent reload <ID>     # 重载指定 agent
octop env                   # 查看环境信息（comfy-cli 侧用 comfy env）
```

---

## 四、凭据管理建议

Octop 首次启动会生成随机管理员密码，**请立即修改**：

> 控制台 → 右上角头像 → 账户设置 → 修改密码

本仓库的脚本**不硬编码任何凭据**，统一通过以下方式获取（优先级从高到低）：

1. `--username` / `--password` 命令行参数
2. `OCTOP_USER` / `OCTOP_PASS` 环境变量
3. 交互式提示（`getpass`，不回显）

推荐用法：

```bash
export OCTOP_USER=admin
export OCTOP_PASS='your-password'
python scripts/verify.py
```

`.gitignore` 已排除 `config/comfyui-mcp-connector.json`（含本机路径的真实配置）—— 只提交 `.example.json` 占位版本。

---

## 五、API 要点

- 所有路径带 **`/api`** 前缀
- 鉴权：`Authorization: Bearer <access_token>`
- 登录响应字段名是 **`access_token`**，不是 `token`
- 循环流量必须绕过代理，否则拿到**假的 502**（环境里有 `http_proxy` 时）

```python
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
# 或 curl --noproxy "*"
```
