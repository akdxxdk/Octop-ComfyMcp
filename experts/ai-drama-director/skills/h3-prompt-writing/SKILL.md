---
name: H3 Prompt Writing（H3 提示词写作）
description: Write MiniMax H3 video generation prompts for T2VA, I2VA, FL2VA, L2VA, and Ref2VA. Use when rewriting multimodal requests into H3 prompt structures, composing integrated_multimodal_description, overall_soundscape, and non_diegetic_music, aligning keyframes, or defining reference labels for images, videos, and audio. 【中文】为 MiniMax H3 撰写/重写视频生成提示词：文生视频、首帧/首尾帧/末帧生视频、全参考生视频（多图+视频+音频）。当需要把创意或分镜改写成 H3 结构化 prompt、编排 integrated_multimodal_description / overall_soundscape / non_diegetic_music、对齐关键帧、或定义 <Picture 1> 等引用标签时使用。本机为 ComfyUI 本地部署 H3-Base，落地细节见 references/local-comfyui-notes.md。
compatibility: Portable to any agent that can read local files — no external API calls, MiniMax Hub tools, or proprietary runtime required. The agents/openai.yaml file only adds optional ChatGPT/Codex UI metadata; it does not restrict the skill to OpenAI agents.
---

# H3 Prompt Writing

> 本机补充：`references/local-comfyui-notes.md` 记录了本机 ComfyUI 实测的
> 模式→节点/模板映射、时长帧数公式、模型文件与已知坑。
> **写完后要落地生成时，必须读它。**

## Workflow

1. Identify the input mode: T2VA, I2VA, FL2VA, L2VA, or full-reference Ref2VA.
2. For base text/keyframe modes, read `references/base-en.txt` and follow its final prompt structure.
3. For full-reference mode, read `references/ref-en.txt` and follow its six-section rewrite format.
4. Preserve the exact field names, section order, labels, and timing notation from the selected guide.
5. **Before handing off for generation, read `references/local-comfyui-notes.md`** and map the mode to the local ComfyUI node/template. Confirm duration, resolution and model choices are actually available on this machine.

## Base Modes

- T2VA: build the full audiovisual timeline from text.
- I2VA: start from the first frame and develop forward from it.
- FL2VA: describe the continuous path between the first and last frames.
- L2VA: infer a plausible opening and converge to the supplied last frame.

Use `integrated_multimodal_description`, `overall_soundscape`, and `non_diegetic_music` in the order shown in `references/base-en.txt`.

## Full-Reference Mode

Ref2VA rewrites use `subject_definitions`, `summary`, `retention_analysis`, `detailed_description`, `overall_soundscape`, and `non_diegetic_music` in that order. Reference labels stay consistent across all sections.

Read `references/ref-en.txt` for label rules, retention analysis, and complete examples.

## Output Rules

- Write rewrite sections in English; preserve dialogue, lyrics, and visible scene text in their original language.
- Describe each shot by composition, subjects, environment, actions, camera, sound, and the exact point where referenced content appears.
- Avoid plot summaries, unresolved reference labels, and timing that does not match the requested duration.
## Tips for Better Results
- Always match the total duration of the description to the requested video length (4–15 seconds).
- Keep reference labels consistent (e.g. `<Picture 1>`, `<Video 1>`, `<Audio 1>`) across every section.
- Prefer concrete visual and audio details over abstract words like "cinematic" or "beautiful".
- When using keyframes (I2VA / FL2VA / L2VA), clearly state how the first and/or last frame connects to the timeline.

## Local Deployment Notes (本机环境)

本机跑的是 **H3-Base 本地部署**（ComfyUI），**不含** H3-Context-IR 云端预处理，
也**不含** H3-Regenerate-2K 升分辨率模块。因此：

- **Context-IR 的活儿由你承担。** 官方明确指出 Context-IR 对成片质量至关重要，
  本机没有它，所以按本技能写出结构化 prompt 是**唯一的质量保障手段**，不是可选项。
- 输出为 **768p 原生**（本机模板实测 480p：864×480），无 2K 再生成。
- 本机本地模板：`video_minimax_h3_t2v` / `video_minimax_h3_i2v` / `video_minimax_h3_r2v`。
  `ComfyCloud*` 节点走云端、消耗额度，本机场景优先本地节点。
- I2VA / T2VA 最终只吃**一个 prompt 字符串**：
  把 `integrated_multimodal_description` + `overall_soundscape` + `non_diegetic_music` 合并输出，
  **不要**留下悬空的 `<Picture 1>` 引用（本机无对应图片槽位，解析不了）。
  引用标签只在 Ref2VA 模式（`MiniMaxH3ReferenceToVideo` 接多图）下使用。

完整映射表与实测参数见 `references/local-comfyui-notes.md`。
