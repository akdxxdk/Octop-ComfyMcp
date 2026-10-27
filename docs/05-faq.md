# 05 · 常见问题与性能答疑

---

## 性能篇

### Q：用 MCP 驱动会比在浏览器里手动跑慢吗？

**不会。生成速度和以前完全一样。**

绘世启动器本质就是个 GUI 封装 —— 它干的活就是拼一串命令行然后跑 `main.py`：

```
main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch
```

被 MCP 驱动的进程跑的也是这个。而 MCP 只是把工作流 JSON 提交到 8188 的 `/prompt` —— **和你在浏览器点"运行"走的是同一个 API**。采样计算全在 ComfyUI 进程里、在你的 GPU 上，谁提交的根本不影响。

### Q：那 MCP 这一层有额外开销吗？

有，但可忽略。实测数据：

| 环节 | 耗时 |
|---|---|
| 启动 comfy-mcp 进程 | 108 ms |
| MCP 握手（一次性） | 2.8 s |
| 每次工具调用往返 | **约 2.1 s** |

2.1 秒主要花在 spawn `comfy --json` 子进程上。但这只发生在**提交和查询**环节，**不参与采样计算**。

对照 14 分钟的视频生成任务：占比约 **0.2%**，完全在噪声里。用 `wait:false` 提交后后台轮询，连这点等待都不阻塞。

### Q：真正影响速度的是什么？

三样，都和 MCP 无关：

1. **启动参数** —— 若在绘世启动器勾了低显存模式（`--lowvram`），会明显变慢
2. **模型量化** —— int8 / fp8 比 fp16 快且省显存
3. **显存被占** —— 跑大任务前先调一次 `free_memory`

### Q：GPU 显示占用 14.2/16.3GB，是被别人抢了吗？

大概率不是。里面主要是 **PyTorch 的缓存池 + 桌面 UI 进程**（dwm、explorer、Edge WebView2、NVIDIA Overlay）。ComfyUI 自己视角还剩 1.9GB，跑大任务会自动 offload。

---

## 版本兼容篇

### Q：秋叶 aki 整合包哪个版本支持 MCP？

**都支持，和版本无关。**

MCP 是挂在整合包外面的独立一层，不依赖 aki 是 V3 还是 V3.7。实测 ComfyUI 0.36.0 的 `/mcp`、`/api/mcp`、`/sse` **全部 404** —— ComfyUI 本体根本不实现 MCP，能力全部来自外部的 `comfy-mcp`。

整合包只负责把 ComfyUI 内核跑起来。判断能不能用 MCP，只看：

| 条件 | 要求 |
|---|---|
| ComfyUI 监听 8188 | 必须 |
| comfy-cli | ≥ 1.14.0 |
| comfy-mcp + `COMFY_BIN` 指对 | 必须 |

### Q：升级到 aki-V3.7 后 MCP 侧要改什么？

**什么都不用改。** 唯一需要动的情况是换目录或换端口 —— 见 [02-comfyui-path.md](02-comfyui-path.md)。

---

## 排障篇

### Q：MCP 探针报 `Connection closed`，工具数 0

这是 **MCP SDK 版本冲突**，不是网络问题。大概率发生在 Octop 升级之后。

根因与解法见 [03-mcp-isolation.md](03-mcp-isolation.md)。快速自查：

```bash
pip list | grep -i "^mcp"
# 若 mcp=1.30.0 而 mcp-types=2.3.0 → 就是这个问题
```

修复：给 comfy-mcp 建独立 venv，连接器 `command` 指向隔离环境的 exe。

### Q：curl 访问 8088 返回 502，但服务明明在跑

环境里有代理（`http_proxy=http://127.0.0.1:61656`），**假 502**。

```bash
curl -s --noproxy "*" http://127.0.0.1:8088/api/health
```

### Q：改了 `comfyui-mcp-connector.json` 没生效

正常的。那是存档副本，生效配置在 Octop 数据库里，必须走 API：

```
PUT /api/connectors/custom-mcp
```

### Q：用 `comfy launch` 启动后报缺模型

**别用 `comfy launch` 启动。** comfy-cli 的 workspace 默认指向 `<USERPROFILE>/Documents/comfy/ComfyUI`，和你的整合包不是同一个目录，模型路径全丢。

继续用绘世启动器或 `scripts\start-comfyui.bat`。

### Q：ComfyUI 启动卡在下载 spacy

`controlnet_aux` 在从 GitHub 拉 `xx_sent_ud_sm`，直连只有 ~20KB/s。走加速代理预装，见 [01-install.md §1.3](01-install.md#13-预装-spacy-模型必做否则每次启动卡-58-分钟)。

### Q：提示缺 H3 节点

先确认你找对目录了 —— aki 的真实根目录是 `<COMFYUI_AKI_ROOT>\ComfyUI\`（多一层），`custom_nodes` 在这层里。我们踩过这个坑，一度误判成"节点缺失"。

### Q：H3 模型加载就报错

检查 `comfy_kitchen` 是否安装 —— NVFP4 / INT8 反量化核依赖它，缺失则加载即报错。在 ComfyUI Manager 里补装。

### Q：跑了一两天后突然 `MemoryError: VBAR allocation failed`

典型日志：

```
[ERROR] aimdo: src/model-vbar.c:242: Could not reserve Virtual Address space for VBAR
[ERROR] !!! Exception during processing !!! VBAR allocation failed
  comfy/model_patcher.py:1809 → ModelVBAR(self.model_size() * 10, ...)
```

**这不是配置问题，也不用改参数 —— 重启进程就好。**

`comfy-aimdo` 每次加载模型都要预留 `model_size × 10` 的**连续虚拟地址空间**。H3 这套很大（qwen3vl_32b 文本编码器 ~14.9 GB、video VAE ~5 GB、diffusion ~20 GB），在同一个进程里连续几十小时、反复换模型加载之后，Windows 的 VA 空间碎片化到留不出这么大的连续块，就抛这个错。

实测：一个跑了 **43 小时 30 分**、期间成功出过 3 次片（SDXL 出图 100s / H3 8 步 14 分钟 / H3 20 步 24 分钟）的进程，第 4 次加载文本编码器时命中此错，之后进程退出。

**判断要点**：报错发生在 `Requested to load MiniMaxH3TEModel_` 之后、`0 models unloaded` 附近，且此前长时间稳定运行 → 就是 VA 碎片，不是显存不足（`nvidia-smi` 会显示显存其实很空）。

**处理**：

1. 停掉 ComfyUI 进程，重新启动（VA 空间随进程回收）
2. 长时间批量出片时，每跑十几条就重启一次，比等它崩更省事
3. 不要指望 `--lowvram` 之类参数能绕开，VBAR 是地址空间预留，跟显存策略无关

---

## 其他

### Q：自定义 Agent 怎么拿到 ComfyUI 能力？

控制台编辑 Agent → MCP 服务器 → 勾选 `comfyui`。

### Q：39 个工具都包含什么？

模板搜索（`search_templates` / `get_template` / `fetch_template`）、模型查询（`search_models` / `list_partner_models`）、工作流操作（`validate_workflow` / `run_workflow` / `set_workflow_slot`）、任务管理（`queue` / `history` / `get_job`）、环境信息（`server_info` / `which` / `env` / `free_memory`）等。

列全部：

```bash
python scripts\mcp_call.py list_partner_models '{}'
```

---

## Agent 接上工具却"说它没有 ComfyUI 能力"

这不是连接件坏了，是三个独立闸门。按顺序查。

### ① 会话模式是 Ask / Plan（最常见）

Octop 的 Ask / Plan 模式会**把 MCP 连接整个摘掉**，不是隐藏按钮，是根本没注入：

```python
# octop/infra/gateway/process/processor.py
if mode in ("ask", "plan"):
    request.pop("mcp_servers", None)   # ← 连接件在这里被移除
```

此时 Agent 的工具表里只剩 `ls` / `read_file` / `web_search` 等只读工具，它当然说"我没有图像/视频生成能力"——它没说谎，它确实看不到。

**判定**：`GET /api/agents/{id}/threads` 看 `conversation_mode`；`ask` 就是它。

**修**：把会话切回 craft，并且给 Agent 的 config 设默认模式（否则新会话还是 craft，但老会话粘在 ask）：

```bash
curl -X PATCH http://127.0.0.1:8088/api/agents/BBGFVS/threads/<thread_id> \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"conversation_mode":"craft"}'

# Agent 默认模式（新会话生效）
curl -X PATCH http://127.0.0.1:8088/api/agents/BBGFVS \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"config":{"workspace_dir":"<原值>","system_files_path":".octop","conversation_mode":"craft"}}'
```

注意 `PATCH config` 是**整体替换** `config_json`，必须把原字段一起带上。

### ② 上下文预算被 39 个工具吃穿

39 个工具的 schema 实测 **59,786 字符 ≈ 18.7k tokens**。加上内置工具 + 人设提示词 + 历史对话，
很容易顶到模型的 `max_input_tokens` 上限，报：

```
Context remains above the input budget after compaction; reduce input, tools, or configured output tokens.
```

`octop` 里模型声明的 `max_input_tokens` 若小于真实上下文（例如 qwen3 写 32768，而 Ollama 实际能给 40960），
预算公式 `limit × 0.95 − max_output` 会把可用输入压到 ~23k，第一次对话就可能溢出。

**修**：`PATCH /api/admin/providers/{id}` 把 `models[].max_input_tokens` 对齐真实值
（`ollama show <model>` 的 `context_length`，本机 qwen3 系列是 40960）。
长对话场景直接换大上下文模型（DeepSeek 1M）更省事。

### ③ 老会话已被"污染"

模型在前几轮里说过"我做不到 / 没有生成工具"，这些结论会留在 thread 里，后续即使切到 craft 也会自我引用。
**切模式后请新开会话**，别在旧会话里继续追问：

```bash
curl -X POST http://127.0.0.1:8088/api/agents/BBGFVS/threads \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"title":"新会话"}'

curl -X PATCH http://127.0.0.1:8088/api/agents/BBGFVS/session \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"thread_id":"<新 thread_id>"}'
```

### 附：另外两个本机坑（与连接件无关）

- **`fetch_template` 必然失败**（`getaddrinfo failed`，模板 CDN 解析不到）。模板 JSON 就在
  `<ComfyUI>\python\Lib\site-packages\comfyui_workflow_templates_json\templates\`，
  复制到工作区后直接 `validate_workflow` 即可，实测 `valid: true`。
- **`list_workflow_slots` 必报错**：comfy-cli 1.22.0 输出的 JSON 中，模板默认提示词带换行未转义，
  把信封行截断，MCP 按行解析失败。绕法是用 `comfy --json --where local workflow slots <path>` 直读，
  或直接按已知地址改槽位（`105.prompt` / `105.value_1` / `115.aspect_ratio` / `115.megapixels` / `114.image`）。
- **`set_workflow_slot` 同样不可信（2026-10-20 实测）**：调用返回 `"changed": false`，
  文件根本没有被修改（写后读回 widgets 仍是旧值）。也就是说 comfy-cli 1.22.0 的
  `workflow slots` / `workflow set-slot` 两个子命令在这类带多行提示词的工作流上都失效，
  不能依赖 MCP 的槽位工具改参数。**可靠做法：直接用脚本改工作流 JSON**
  （顶层节点 `105` 的 `widgets_values[0]`=提示词、`[3]`=时长秒数、`[4]`=种子；
  子图内节点 `111` 的 `[0]`=时长原语、`104` 的 `[0]`=提示词），改完 `validate_workflow` 确认 `valid: true` 再提交。
  需要看槽位名时，可用 comfy-cli 的内部接口绕开 JSON 序列化 bug：

  ```python
  # 在装有 comfy-cli 的环境里运行
  import json
  from comfy_cli.command.workflow import _get_graph
  wf = json.load(open(path, encoding="utf-8"))
  schema = _get_graph(None, None, None, on_stale=lambda *a: None).get_template_schema("probe", wf)
  for s in schema.get("slots") or []:
      print(s.get("address"), s.get("type"))
  ```

### 出片链路实测基准（2026-10-20，RTX 5060 Ti 16G）

- Agent：Octop 专家（craft 模式 + DeepSeek v4-flash + comfyui 连接件），无人值守
- 任务：4 秒 H3 i2v（turbo 8 步 LoRA、fp16 video VAE、864×480）
- 全程 **15 次工具调用**（run_workflow 提交 1 次 + `comfyui_job` 轮询若干次），从提交到出片 **384 秒**
- 成片 107 帧 @ 24fps = 4.46s，h264 + 音轨，帧数与公式 `max(5, round(a×24)) + (5-(…%17))%17` 完全吻合

