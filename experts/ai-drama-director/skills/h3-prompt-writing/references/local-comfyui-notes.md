# Local ComfyUI Deployment Notes (本机落地适配)

> 本文件由本机环境实测补充，非 MiniMax 官方内容。
> 官方 `SKILL.md` 讲「怎么写 H3 prompt」，本文件讲「写完之后在本机怎么跑」。
> 机器：Windows 11 + RTX 5060 Ti 16GB，ComfyUI 0.36.0（秋叶 aki 整合包），端口 8188。

---

## 1. 本机跑的是 H3-Base，不是完整 H3 系统

官方 H3 系统由三个模块组成：

| 模块 | 作用 | 本机是否有 |
|---|---|---|
| **H3-Context-IR** | 云端预处理：把自由形式的多模态输入理解、补全、序列化成结构化表示 | ❌ 无（托管服务，未开源） |
| **H3-Base** | 根据 Context-IR 输出生成音视频，**768p** | ✅ 有（ComfyUI 本地部署） |
| **H3-Regenerate-2K** | 把 768p 结果 + 原上下文回灌，重生成 2K | ❌ 无 |

### 由此推出的最重要一条结论

官方明确说：**H3-Context-IR 对最终质量至关重要**，官方强烈建议「要么接入 Context-IR，要么按 Prompting Guidance 自建上下文处理系统」。

本机没有 Context-IR，所以 **Context-IR 的活儿必须由你（Agent）来干**——
也就是说 `base-en.txt` / `ref-en.txt` 里那套结构化 prompt 不是「可选的优化」，
而是**本机唯一的上下文处理手段**。不写就等于把裸 prompt 直接喂给 H3-Base，质量会明显下降。

这不是风格建议，是本机环境下的硬性要求。

---

## 2. 输入模式 → 本机节点 / 模板映射

本机 ComfyUI 的本地节点（非 ComfyCloud）实测清单：

| 官方模式 | 本机节点 | 官方模板 | 本机可用性 |
|---|---|---|---|
| **T2VA** 文生视频 | `MiniMaxH3ImageToVideo`（不接 first_frame） | `video_minimax_h3_t2v` | ✅ |
| **I2VA** 首帧图生视频 | `MiniMaxH3ImageToVideo` + `first_frame` | `video_minimax_h3_i2v` | ✅ 已实测跑通 |
| **FL2VA** 首尾帧 | `MiniMaxH3ImageToVideo` + `first_frame` + `last_frame` | 用 i2v 模板加 last_frame | ✅ 可选输入已支持 |
| **L2VA** 末帧反推 | 同上，只给 `last_frame` | 无独立模板 | ⚠️ 需手工接线 |
| **Ref2VA** 全参考（多图/视频/音频） | `MiniMaxH3ReferenceToVideo` | `video_minimax_h3_r2v` | ✅ |

`MiniMaxH3ReferenceToVideo` 可选输入：`ref_images`(≤9) / `ref_videos`(≤3) / `ref_video_audios` / `ref_audios`(≤3)，
与官方 Ref2VA 规格一致（视频/音频单条 2–15s、总长 ≤15s、混合输入文件总数 ≤12）。

另有 `ComfyCloud*` 系列节点（`ComfyCloudMiniMaxH3TextToVideoNode` 等）——
那些是**走 Comfy 云端、要花钱/额度**的，本机场景优先用本地节点。

---

## 3. 本机实测参数（可直接引用，别再拍脑袋）

### i2v 模板 `video_minimax_h3_i2v`

| 项 | 值 |
|---|---|
| 主节点 | 子图内 `MiniMaxH3ImageToVideo` |
| 输出分辨率 | 480p，16:9 下为 **864×480** |
| 帧率 | 24 fps |
| 时长→帧数公式 | `max(5, round(a*24)) + (5 - (max(5, round(a*24)) % 17)) % 17` |
| 10 秒 → | **243 帧**，实测成片 **10.12s** |
| 耗时（10s@480p，含 turbo） | **约 14 分钟** |
| 音频 | H3 原生生成，自带音轨 |

时长官方允许 4–15 秒；本机模板滑块一致。

### 子图双写陷阱（必看）

`video_minimax_h3_i2v` 的主图节点 105 只是**子图实例**。
改 prompt / duration / VAE / turbo_switch 时，
**必须同时改「主图 node 105 的 widgets_values」和「子图内对应节点」**，只改一侧不生效。
（子图内对应节点：104=prompt，111=duration，11=video VAE，126=turbo 开关）

### 本机模型文件

- 主模型：`<COMFY_SHARED_MODELS>\diffusion_models\minimax_h3_video_int8.safetensors`（约 21GB）
- 文本编码器：`qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`（约 15GB，分级加载）
- 视频 VAE：本机**没有** `int8_convrot` 版，必须用 `minimax_h3_video_vae_fp16.safetensors`
- Turbo LoRA：`minimax_h3_turbo_8step_lora.safetensors`（建议开启，8 步采样）

跑 21GB 模型 + 15GB 编码器在 16G 显存上靠自动 offload 完成，**不会 OOM**，但别再开别的吃显存的程序。

---

## 4. 与官方技能的衔接方式

1. 按 `SKILL.md` 的 Workflow 判断模式（T2VA/I2VA/FL2VA/L2VA/Ref2VA）
2. 读 `base-en.txt` 或 `ref-en.txt`，按官方字段结构写出完整 prompt
3. 用本文件的映射表选模板 / 节点
4. 用 `make_workflow.py` 生成工作流 JSON，或直接给参数让 MCP 提交
5. 提交前 `validate_workflow` 校验（`spends_credits: false` 表示纯本地、不花钱）

### 一个本机特有的注意点

官方指南面向的是「H3 全系统 + 云端 API」，
其示例 prompt 里会出现 `<Picture 1>`、`[Shot 1]` 这类**引用标签**——
这些在 Ref2VA 模式下由 `ref-en.txt` 明确定义，本机 `MiniMaxH3ReferenceToVideo` 能接多图，可以直接用。

但在 **I2VA/T2VA** 模式下，本机只吃一个 `prompt` 字符串，
所以应输出 `integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music` 的**合并文本**，
不要留下悬空的 `<Picture 1>` 引用（本机没有对应的图片槽位会解析不了）。
