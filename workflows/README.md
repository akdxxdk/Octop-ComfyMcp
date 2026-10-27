# 工作流文件说明

| 文件 | 说明 |
|---|---|
| `template_raw.json` | 官方模板 `video_minimax_h3_i2v` 原文（MiniMax H3: Image to Video，Int8 量化版），**未经修改**，作为 baseline 与改造母版 |
| `h3_escape_10s.json` | 定制版：10 秒「逃跑穿越」图生视频，已验证可跑通 |

---

## `h3_escape_10s.json` 改造点

| 节点 | 参数 | 原值 | 改后 | 原因 |
|---|---|---|---|---|
| main 114 | LoadImage | `transparent_rgb_gaming_mouse.png` | `h3_escape_start.png` | 换成我们的起始图 |
| main 115 | ResolutionSelector | `1:1 (Square)` / 0.4 MP | `16:9 (Widescreen)` | 视频需要横向 |
| main 105 | prompt | 蒸汽波鼠标广告 | 逃跑穿越延续动作 | 需求 |
| main 105 | duration | 2 秒 | **10 秒** | 需求 |
| main 105 | video VAE | `..._int8_convrot` ❌ | `..._fp16` | 本地只有 fp16 版 |
| main 105 | turbo | False | **True** | 8 步采样加速 |
| sub 11 | VAELoader | 同上 | `..._fp16` | 同步 |
| sub 104 | prompt | 同上 | 逃跑穿越 | 同步 |
| sub 111 | duration | 2.0 | 10.0 | 同步 |
| sub 126 | lightning LoRA | false | true | 同步 |

---

## ⚠️ 子图（subgraph）陷阱

官方模板把采样逻辑包在子图里：

- 顶层 `nodes` 只有 9 个，其中 **node 105 是子图实例**
- 真正的 21 个节点在 `definitions.subgraphs[0].nodes`

**只改一侧不生效。** 必须同时改：

1. 子图实例 node 105 的 `widgets_values`（UI 显示值）
2. 子图定义内部对应节点（11 / 104 / 111 / 126）的 `widgets_values` 和 `widgets_values_named`

推荐直接用 `scripts\make_workflow.py`，它已经处理了两处同步。

---

## 复用到自己的视频

1. 把起始图放进 ComfyUI 的 `input/` 目录
2. 生成工作流：

```bash
python scripts\make_workflow.py \
  --image my_start.png \
  --prompt "your prompt here" \
  --duration 5 \
  --out workflows/my_video.json
```

3. 校验（期望 `errors: 0`、`spends_credits: false`）：

```bash
python scripts\mcp_call.py validate_workflow '{"workflow_path":"workflows/my_video.json"}'
```

4. 提交（非阻塞）：

```bash
python scripts\mcp_call.py run_workflow '{"workflow_path":"workflows/my_video.json","wait":false}'
```

5. 用返回的 `prompt_id` 轮询 `/history/<prompt_id>` 取成品

---

## 分辨率 / 时长对照

| 目标 | `--megapixels` | 相对耗时 | 显存压力 |
|---|---|---|---|
| 480p | `0.3` | 1×（10s ≈ 14 分钟） | 轻松 |
| 720p | `0.6` | 显著上升 | 中等 |
| 1080p | `1.0` | 很高 | 紧张，需 offload |

时长用 `--duration` 指定秒数，帧数由模板节点 107 的公式自动算：

```
max(5, round(duration * 24)) + (5 - (max(5, round(duration * 24)) % 17)) % 17
```

例：`10s → 243 帧`（243 / 24 = 10.12s），已实测验证。
