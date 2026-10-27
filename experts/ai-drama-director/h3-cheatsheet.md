# MiniMax H3 技术速查

> 本机实测环境：Windows 11 + RTX 5060 Ti 16GB + ComfyUI 0.36.0（秋叶 aki 整合包）

---

## 一、工作流模板

| 模板 ID | 用途 | 备注 |
|---|---|---|
| `video_minimax_h3_i2v` | **图生视频** | 短剧主力，靠起始图锚定一致性 |
| 官方 t2v 模板 | 文生视频 | 无起始图时使用 |

模板是 UI 格式 JSON（含 `nodes` + `definitions.subgraphs`），不是 API 格式。

## 二、关键参数与节点位置

### 主图（顶层 nodes）

| 节点 | 类型 | 参数 |
|---|---|---|
| 114 | LoadImage | 起始图文件名（需先放进 `input/`） |
| 115 | ResolutionSelector | 宽高比 + megapixels |
| 105 | 子图实例 | 见下方索引表 |

### 子图实例 node 105 的 `widgets_values` 索引

| 索引 | 含义 | 示例 |
|---|---|---|
| `[0]` | 提示词 | `"Cinematic escape sequence..."` |
| `[3]` | **时长（秒）** | `10` |
| `[7]` | **视频 VAE** | `"minimax_h3_video_vae_fp16.safetensors"` |
| `[9]` | **turbo 开关** | `True` |

### 子图内部（`definitions.subgraphs[0].nodes`）

| 节点 | 类型 | 参数 |
|---|---|---|
| 11 | VAELoader | 视频 VAE 文件名 |
| 104 | MiniMaxH3ImageToVideo | 提示词（含 `last_frame` 输入） |
| 111 | PrimitiveFloat | 时长（秒） |
| 126 | PrimitiveBoolean | Lightning LoRA 开关 |
| 107 | ComfyMathExpression | 帧数公式 |

### ⚠️ 子图必须双写

**子图实例（105）和子图内部节点（11 / 104 / 111 / 126）要同时改。只改一侧不生效。**

## 三、帧数公式

模板 node 107：

```
max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17
```

`a` = 时长（秒）。输出固定 24fps。

| 时长 | 帧数 | 实际秒数 |
|---|---|---|
| 2s | 56 | 2.33s |
| 5s | 124 | 5.17s |
| 10s | 243 | 10.12s ✅ 实测验证 |

**不要手写帧数，改时长即可。**

## 四、模型文件

| 文件 | 目录 | 大小 |
|---|---|---|
| H3 主模型（int8） | `diffusion_models/` | ~21 GB |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | `text_encoders/` | 14.6 GiB |
| `minimax_h3_video_vae_fp16.safetensors` | `vae/` | 5.2 GB |
| `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | `loras/` | 1.96 GB |
| `minimax_h3_pdmd_2step_lora_avg_rank_38_bf16.safetensors` | `loras/` | 381 MB |
| `minimax_h3_pdmd_4step_lora_avg_rank_57_bf16.safetensors` | `loras/` | 559 MB |

统一放在 `<COMFY_SHARED_MODELS>`，由 `extra_model_paths.yaml` 挂载。

⚠️ 官方模板默认要 `minimax_h3_video_vae_int8_convrot.safetensors`，本机没有，需换成 fp16 版。

## 五、分辨率与成本

| 档位 | megapixels | 16:9 输出 | 10 秒耗时 |
|---|---|---|---|
| 480p | `0.3` | 864×480 | ~14 分钟 |
| 720p | `0.6` | — | 显著上升 |
| 1080p | `1.0` | — | 很高，需 offload |

## 六、显存

21GB int8 主模型 + 15GB NVFP4 文本编码器在 16G 卡上靠自动分级 offload 跑，**不 OOM**。

典型显存曲线：

| 阶段 | 可用显存 |
|---|---|
| 空闲 | ~9.6 GB |
| VAE 加载完 | ~7 GB |
| 文本编码器加载中 | ~1.9 GB |

跑大任务前可先调一次 `free_memory` 工具清理碎片。

## 七、提交执行

```bash
# 校验（期望 errors: 0, spends_credits: false）
python scripts/mcp_call.py validate_workflow '{"workflow_path":"workflows/x.json"}'

# 提交（非阻塞！wait 默认 true 且 timeout 110s，长任务必超时）
python scripts/mcp_call.py run_workflow '{"workflow_path":"workflows/x.json","wait":false}'
```

拿到 `prompt_id` 后轮询 `/history/<prompt_id>`。

## 八、路径要点

- **aki 真实根目录多一层**：`<COMFYUI_AKI_ROOT>\ComfyUI\`（`custom_nodes` / `input` / `output` 都在这层）
- 起始图放 `ComfyUI\input\`，成品出 `ComfyUI\output\video\`
- **不要用 `comfy launch` 启动** —— comfy-cli 的 workspace 在 C 盘，模型路径会全丢
