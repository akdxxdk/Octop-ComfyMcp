# Octop-ComfyMcp

> 让 Octop 的 AI Agent 通过 MCP 协议直接驱动本地 ComfyUI 出图 / 出视频

一套在 Windows 上实测跑通的集成方案：把 [ComfyUI](https://github.com/comfyanonymous/ComfyUI)（秋叶 aki 整合包）接入 [Octop](https://pypi.org/project/octop/) 自托管 AI 平台，让 Octop 的 Agent 具备调用本地 GPU 生成图片和视频的能力。

全程本地推理，**不消耗任何云端额度**。

---

## ✨ 这套方案能做什么

- 🤖 **Agent 自主生成** —— Octop 的 Agent 通过 MCP 自主提交 ComfyUI 工作流、查询结果、取回成品
- 🎬 **视频生成** —— 已实测跑通 MiniMax H3 i2v（图生视频），10 秒 243 帧 @24fps
- 🎨 **图片生成** —— 支持任意本地 checkpoint / LoRA（本仓库示例用 RealVisXL V4.0）
- 🔧 **39 个 MCP 工具** —— 模板搜索、工作流校验、槽位填充、任务调度、历史查询全覆盖
- 🔒 **纯本地** —— 数据不出本机，服务仅监听 127.0.0.1

## 📊 实测成果

| 项目 | 结果 |
|---|---|
| 生成任务 | MiniMax H3 i2v「逃跑穿越」10 秒视频 |
| 成品规格 | 243 帧 @24fps / 10.12s / 864×480 / 2.4MB |
| 硬件 | RTX 5060 Ti 16GB |
| 总耗时 | ~15.7 分钟（起始图 101s + 视频采样 840s） |
| 云端花费 | ¥0 |

画面演进：起始帧与输入图无缝衔接 → 中段时空环坍缩成蓝白粒子漩涡 → 末帧奔跑回头张望。人物一致性良好，无崩坏帧。

<table>
<tr>
<td align="center"><b>起始图（视频首帧）</b><br><img src="assets/start_frame.jpg" width="240"></td>
<td align="center"><b>中段 · 时空环坍缩</b><br><img src="assets/frame_2_121.jpg" width="240"></td>
<td align="center"><b>末帧 · 奔跑回头</b><br><img src="assets/frame_4_242.jpg" width="240"></td>
</tr>
</table>

---

## 🏗️ 架构

MCP **不是** ComfyUI 内置能力（实测 0.36.0 的 `/mcp`、`/api/mcp`、`/sse` 全部 404），而是挂在外部的一层：

```
┌──────────────────────────────────────────────────────┐
│  Octop Console (127.0.0.1:8088)                     │
│    └─ Agent「案例包装官」mcp_servers=["comfyui"]      │
└────────────────────┬─────────────────────────────────┘
                     │ stdio
┌────────────────────▼─────────────────────────────────┐
│  comfy-mcp  (<COMFYMCP_VENV>)  ← 独立 venv!    │
│    MCP SDK 2.3.0  ·  39 tools                       │
└────────────────────┬─────────────────────────────────┘
                     │ subprocess: comfy --json
┌────────────────────▼─────────────────────────────────┐
│  comfy-cli 1.22.0  (octop conda env)                │
└────────────────────┬─────────────────────────────────┘
                     │ HTTP /prompt  /history  /queue
┌────────────────────▼─────────────────────────────────┐
│  ComfyUI 0.36.0  (127.0.0.1:8188)  ← aki 整合包     │
│    └─ RTX 5060 Ti 16GB  ·  本地模型                   │
└──────────────────────────────────────────────────────┘
```

**关键点**：MCP 只是遥控器，把工作流 JSON 提交到 8188 的 `/prompt`——**和你在浏览器点"运行"走的是同一个 API**。采样计算全在 ComfyUI 进程里，谁提交的**不影响生成速度**。

### 为什么 comfy-mcp 必须独立 venv

这是本方案最重要的一个坑，也是官方硬性要求：

| 组件 | 需要的 MCP SDK | 导入路径 |
|---|---|---|
| `comfy-mcp` 0.10.0 | **2.x** | `mcp.server.mcpserver` |
| `langchain-mcp-adapters`（Octop 的 MCP 客户端） | **1.x** | `mcp.server.fastmcp.*`（**顶层导入**） |

两者在同一环境**互斥**。升级 Octop 时依赖解析会把 `mcp` 降到 1.30.0，导致 comfy-mcp 起不来（`ModuleNotFoundError`）；反过来把主环境升到 2.x，Octop 自己的 MCP 客户端会整体崩溃。

**解法：隔离。** 详见 [docs/04-mcp-isolation.md](docs/04-mcp-isolation.md)。

---

## 🚀 快速开始

### 前置条件

| 组件 | 版本要求 | 说明 |
|---|---|---|
| Windows | 10 / 11 | 本方案在本机 Win11 实测 |
| Octop | 1.0.2+ | `pip install octop` |
| ComfyUI | 任意 | 本方案用秋叶 aki 整合包 V3 |
| comfy-cli | ≥ 1.14.0 | 本仓库用 1.22.0 |
| comfy-mcp | 0.10.0 | **必须装在独立 venv** |
| GPU | 建议 ≥ 12GB | 本方案在 5060 Ti 16GB 实测 |

### 三步接入

**1️⃣ 启动 ComfyUI**

双击 `scripts\start-comfyui.bat`，或命令行传入你的 aki 根目录：

```bat
start-comfyui.bat <COMFYUI_AKI_ROOT>
```

确认日志出现 `To see the GUI go to http://127.0.0.1:8188`。

> ⚠️ 不要用 `comfy launch` 启动 —— comfy-cli 的 workspace 默认指向 `<USERPROFILE>/Documents/comfy/ComfyUI`，和整合包不是同一套，模型路径会全丢。

**2️⃣ 建隔离环境并启动 Octop**

```bat
scripts\setup-comfymcp-venv.bat
scripts\start-octop.bat
```

**3️⃣ 写入连接器配置并验证**

```bash
python scripts\setup-connector.py
python scripts\verify.py
```

看到 `mcp probe : ok=True tools=39` 即告成功。

### 给 Agent 挂载 MCP

在 Octop 控制台编辑目标 Agent，把 MCP 服务器设为 `comfyui`；或走 API：

```bash
curl -X PATCH http://127.0.0.1:8088/api/agents/<AGENT_ID> \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mcp_servers":["comfyui"]}'
```

---

## 📁 目录结构

```
Octop-ComfyMcp/
├── README.md                  ← 你在这里
├── LICENSE                    MIT
├── CHANGELOG.md               版本演进记录
├── .gitignore                 已排除凭据/备份/大文件
├── .env.example               ← 复制为 .env 填本机路径（.env 已被 gitignore）
├── comfy-mcp-requirements.txt ← comfy-mcp 隔离 venv 依赖清单（锁定版本）
│
├── docs/
│   ├── 01-install.md          完整安装部署流程
│   ├── 02-comfyui-path.md     aki 路径/端口切换指南
│   ├── 03-mcp-isolation.md    MCP 依赖隔离排障
│   ├── 04-workflow-examples.md  H3 视频生成实战
│   └── 05-faq.md              常见问题与性能答疑
│
├── scripts/
│   ├── start-comfyui.bat      参数化 ComfyUI 启动器
│   ├── start-octop.bat        Octop 启动器
│   ├── setup-comfymcp-venv.bat  一键建隔离环境
│   ├── setup-connector.py     通过 API 写入 MCP 连接器
│   ├── verify.py              六项全量验证
│   ├── mcp_call.py            MCP 工具直调（调试用）
│   ├── install-h3-skill.sh    一键安装 h3-prompt-writing 技能到任意 Agent
│   ├── test-agent-chat.py     走 WebSocket 真实对话测试 Agent（技能是否被用）
│   └── diagnose-agent-mcp.py  诊断「有连接件却不调用工具」四道闸门
│
├── config/
│   └── comfyui-mcp-connector.example.json   ← 复制为本地配置后填写
│
├── experts/
│   └── ai-drama-director/     ★ 内置专家：AI 短剧制作专家
│       ├── SOUL.md            人设：全链路导演方法论
│       ├── h3-cheatsheet.md   H3 参数速查（实测数据）
│       ├── storyboard-template.md  分镜表模板
│       ├── suggested-user-profile.md  建议填进「用户档案」的内容
│       └── skills/h3-prompt-writing/  ★ MiniMax 官方提示词技能（已本机适配）
│           ├── SKILL.md                    技能主文件（含本机落地章节）
│           ├── references/base-en.txt      官方 T2VA/I2VA/FL2VA/L2VA 指南
│           ├── references/ref-en.txt       官方 Ref2VA 指南
│           ├── references/local-comfyui-notes.md  ★ 本机实测落地适配
│           └── agents/openai.yaml          官方 UI 元数据（可选）
│
└── workflows/
    └── h3_escape_10s.json     10 秒逃跑穿越示例工作流
```

---

## 🎬 内置专家：AI 短剧制作专家

`experts/ai-drama-director/` 是一个可直接导入 Octop 的专家配置，定位 **AI 短剧导演兼技术负责人**：

- **创作侧**：黄金 3 秒钩子、15–20 秒爽点密度、反转与悬念结构
- **分镜侧**：景别/运镜体系、180 度轴线、镜头时长与信息量匹配、转场动机
- **技术侧**：MiniMax H3 图生视频参数、一致性控制方案、显存与耗时预估

导入方式：把 `SOUL.md` 内容填进 Octop 控制台新建 Agent 的 System Prompt，或用 API：

```bash
curl -X POST http://127.0.0.1:8088/api/agents \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"AI短剧制作专家","description":"...","system_prompt":"<SOUL.md 内容>"}'

# 挂载 ComfyUI MCP
curl -X PATCH http://127.0.0.1:8088/api/agents/<AGENT_ID> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"mcp_servers":["comfyui"]}'
```

> ⚠️ **SOUL.md 不会自动生效**：Octop 的人设取自数据库 `agents.system_prompt`，
> 改完 `SOUL.md` 必须再写回 `system_prompt` 并 reload，否则 Agent 仍用旧人设。

---

## 🧩 技能：h3-prompt-writing（MiniMax 官方）

来自 [`MiniMax-AI/MiniMax-H3`](https://github.com/MiniMax-AI/MiniMax-H3)，官方用这条命令分发：

```bash
npx skills add https://github.com/MiniMax-AI/MiniMax-H3 --skill h3-prompt-writing
```

Octop 环境下不需要 npx，直接：

```bash
./scripts/install-h3-skill.sh --agent <你的 Agent ID>
```

### 它解决什么问题

H3 不是「写句话就能出片」的模型。官方的 H3 系统原本有个云端预处理模块
**H3-Context-IR**，负责把自由形式的输入理解、补全、序列化成结构化表示。
官方明确说它**对成片质量至关重要**。

本机（ComfyUI 本地部署）只有 **H3-Base**，没有 Context-IR。
所以这套结构化 prompt 写法在本机不是「优化技巧」，而是**唯一的质量保障手段**。

### 两种结构

| 模式 | 段落顺序（固定） |
|---|---|
| **Base**（T2VA / I2VA / FL2VA / L2VA） | `integrated_multimodal_description` → `overall_soundscape` → `non_diegetic_music` |
| **Ref2VA**（全参考：≤9 图 + ≤3 视频 + ≤3 音频） | `subject_definitions` → `summary` → `retention_analysis` → `detailed_description` → `overall_soundscape` → `non_diegetic_music` |

要点：章节正文用英文；对白/歌词/画面内文字保留原语言；描述时长必须匹配请求时长（4–15 秒）；
避免 `cinematic`、`beautiful` 这类空词。

### 本机落地适配（`local-comfyui-notes.md`）

官方技能只讲「怎么写」，本机适配文档讲「写完怎么跑」：

- 模式 → 节点/模板映射（`video_minimax_h3_t2v` / `_i2v` / `_r2v`）
- 帧数公式、480p 实测 864×480、10 秒约 14 分钟
- 模型文件清单与坑（本机无 int8 convrot VAE，必须用 fp16）
- **I2VA/T2VA 只吃一个 prompt 字符串**，三段要合并，不留悬空 `<Picture 1>` 引用

---

## 📚 文档索引

| 文档 | 适合谁 |
|---|---|
| [01-install.md](docs/01-install.md) | 从零开始部署 |
| [02-comfyui-path.md](docs/02-comfyui-path.md) | aki 换盘 / 重装 / 换端口 |
| [03-mcp-isolation.md](docs/03-mcp-isolation.md) | MCP 探针报 `Connection closed` |
| [04-workflow-examples.md](docs/04-workflow-examples.md) | 想跑 H3 图生视频 |
| [05-faq.md](docs/05-faq.md) | 性能、冲突、疑难杂症 |
| [06-octop-tips.md](docs/06-octop-tips.md) | Octop 运维技巧（人设同步、自启） |

---

## 🙏 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) —— 节点式生成工作流引擎
- [Octop](https://pypi.org/project/octop/) —— 自托管多 Agent AI 平台
- [comfy-mcp](https://github.com/Comfy-Org/comfy-mcp) —— ComfyUI 官方 MCP 服务器
- 秋叶 aki 整合包 —— Windows 上一键式 ComfyUI 环境

## 📄 许可

MIT License —— 详见 [LICENSE](LICENSE)。
