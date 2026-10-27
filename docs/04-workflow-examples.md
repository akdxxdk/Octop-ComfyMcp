# 04 · 工作流实战：MiniMax H3 图生视频

> 完整复现一次「10 秒逃跑穿越」视频的生成过程。
> 硬件：RTX 5060 Ti 16GB ｜ 总耗时约 15.7 分钟 ｜ 云端花费 ¥0

---

## 一、先搞清楚 `video_minimax_h3_i2v` 是什么

这个名字**不是** MCP 工具，也**不是**云端 partner model。它是 **ComfyUI 官方工作流模板**的 ID：

- 标题：`MiniMax H3: Image to Video`
- 量化：Int8 版本（适配 16GB 显存）
- 性质：纯本地运行，`validate_workflow` 会返回 `spends_credits: false`

### 怎么确认一件事是不是云端付费模型

```bash
python scripts\mcp_call.py list_partner_models '{}'
```

返回的 52 个模型里，minimax 相关**只有** `minimax/video_generation`（海螺云端 API，且是文生视频）。

**判断标准**：跑 `validate_workflow`，看 `spends_credits` 字段。

---

## 二、模型清单

| 文件 | 位置 | 大小 |
|---|---|---|
| H3 主模型（int8） | `diffusion_models/` | ~21 GB |
| 文本编码器（NVFP4 AWQ） | `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 14.6 GiB |
| 视频 VAE（fp16） | `vae/minimax_h3_video_vae_fp16.safetensors` | — |
| pdmd LoRA 2step / 4step | `loras/` | 381 MB / 559 MB |
| turbo 8step LoRA | `loras/` | — |

模型统一放在 `<COMFY_SHARED_MODELS>`，通过 `extra_model_paths.yaml` 挂载。

从 ModelScope 下载 pdmd LoRA：

```bash
pip install modelscope
python -c "
from modelscope import snapshot_download
snapshot_download('Kijai/MiniMax-H3-experimental',
                  allow_patterns=['loras/*'],
                  local_dir='<COMFY_SHARED_MODELS>')
"
```

---

## 三、模板结构（这步很关键）

官方模板用了**子图（subgraph）**封装 —— 顶层只有 9 个节点，真正的采样逻辑藏在 `definitions.subgraphs[0]` 的 21 个节点里。

```
顶层 nodes（9 个）
├── 114  LoadImage            ← 起始图
├── 115  ResolutionSelector   ← 分辨率/宽高比
└── 105  Subgraph 实例         ← ★ 参数在这里的 widgets_values
         │
         └── definitions.subgraphs[0].nodes（21 个）
             ├── 11   VAELoader（视频 VAE）
             ├── 104  MiniMaxH3ImageToVideo（提示词）
             ├── 111  时长 float
             └── 126  enable lightning lora（turbo 开关）
```

**子图实例的 `widgets_values` 索引**（改错就无效）：

| 索引 | 含义 | 示例值 |
|---|---|---|
| `[0]` | 提示词 | `"Cinematic escape sequence..."` |
| `[3]` | **时长（秒）** | `10` |
| `[7]` | **视频 VAE** | `"minimax_h3_video_vae_fp16.safetensors"` |
| `[9]` | **turbo 开关** | `True` |

⚠️ **改了子图实例，也要同步改子图内部的对应节点**（11 / 104 / 111 / 126），否则不生效。

### 帧数不用手算

节点 107 有帧数公式，自动按 `时长 × 24fps + 1` 算：

```
10 秒 → 243 帧
```

---

## 四、本次改造点

| 节点 | 参数 | 模板原值 | 改成 | 原因 |
|---|---|---|---|---|
| 11 | 视频 VAE | `..._int8_convrot` ❌ | `..._fp16` | 本地只有 fp16 |
| 111 | **时长** | 2 秒 | **10 秒** | 需求 |
| 104 | 提示词 | 蒸汽波鼠标广告 | 逃跑穿越延续动作 | 需求 |
| 126 | turbo 开关 | False | **True** | 8 步采样加速 |

---

## 五、执行步骤

### Step 1 · 生成起始图

用本地 RealVisXL V4.0（SDXL 写实）跑文生图：

```json
{
  "1": {"class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "RealVisXL_V4.0.safetensors"}},
  "2": {"class_type": "CLIPTextEncode",
        "inputs": {"text": "<正面提示词>", "clip": ["1", 1]}},
  "3": {"class_type": "CLIPTextEncode",
        "inputs": {"text": "<负面提示词>", "clip": ["1", 1]}},
  "4": {"class_type": "EmptyLatentImage",
        "inputs": {"width": 1216, "height": 704, "batch_size": 1}},
  "5": {"class_type": "KSampler",
        "inputs": {"seed": 774213, "steps": 30, "cfg": 6.0,
                   "sampler_name": "dpmpp_2m", "scheduler": "karras",
                   "denoise": 1.0, "model": ["1", 0],
                   "positive": ["2", 0], "negative": ["3", 0],
                   "latent_image": ["4", 0]}},
  "6": {"class_type": "VAEDecode",
        "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
  "7": {"class_type": "SaveImage",
        "inputs": {"images": ["6", 0], "filename_prefix": "h3_start"}}
}
```

**提示词写法要点**：明确主体 + 动作 + 环境 + 光效 + 镜头语言。负面提示词固定加 `blurry, low quality, watermark, text, logo, deformed hands, extra limbs`。

**耗时**：约 101 秒。

### Step 2 · 拷贝到 input 目录

```bash
cp "<ComfyUI 根目录>/output/h3_start_00001_.png" \
   "<ComfyUI 根目录>/input/h3_escape_start.png"
```

> ⚠️ 记住：aki 的真实根目录是 `<COMFYUI_AKI_ROOT>\ComfyUI\`（多一层），`input/` 和 `output/` 都在这层里。

### Step 3 · 改造工作流

见 `workflows/h3_escape_10s.json`，或用 `scripts\make_workflow.py` 从模板生成。

### Step 4 · 校验

```bash
python scripts\mcp_call.py validate_workflow '{"workflow_path":"workflows/h3_escape_10s.json"}'
```

期望 `errors: 0`，`spends_credits: false`。

### Step 5 · 提交（非阻塞）

```bash
python scripts\mcp_call.py run_workflow \
  '{"workflow_path":"workflows/h3_escape_10s.json","wait":false}'
```

拿到 `prompt_id` 后后台轮询 `/history/<prompt_id>`。

**耗时**：约 840 秒（14 分钟）。

---

## 六、显存观察

生成过程中的典型显存曲线：

| 阶段 | 显存 |
|---|---|
| 空闲 | ~9.6 GB free |
| VAE 加载完成 | ~7 GB free |
| 文本编码器（NVFP4，分级加载） | ~1.9 GB free |

21GB 的 int8 主模型在 16GB 卡上靠自动分级 offload 跑，**没有 OOM**。

> 如果担心显存碎片，跑大任务前先调一次 `free_memory` 工具。

---

## 七、调分辨率 / 时长

改模板里 `ResolutionSelector` 的 `megapixels`：

| 目标 | megapixels | 预计耗时 | 显存压力 |
|---|---|---|---|
| 480p | 0.3（默认） | 14 分钟 | 轻松 |
| 720p | 0.6 | 显著上升 | 中等 |
| 1080p | 1.0 | 很高 | 紧张，需 offload |

时长直接改节点 111 的 `widgets_values[0]`，帧数会自动算。

---

## 八、可复用脚本

`workflows/h3_escape_10s.json` 是通用模板：

1. 换 `input/` 里的起始图
2. 改节点 114 的 `widgets_values[0]` 为新文件名
3. 改节点 105 的 `[0]`（提示词）、`[3]`（时长）
4. 同步子图 104 / 111
5. 校验 → 提交

批量出片无障碍。
