#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a customised MiniMax H3 image-to-video workflow from the official
template `video_minimax_h3_i2v`.

What it patches:
    main node 114  LoadImage              -> start image filename
    main node 115  ResolutionSelector     -> aspect ratio / megapixels
    main node 105  Subgraph instance      -> prompt / duration / video VAE / turbo
    sub  node  11  VAELoader              -> video VAE
    sub  node 104  MiniMaxH3ImageToVideo  -> prompt
    sub  node 111  PrimitiveFloat         -> duration (seconds)
    sub  node 126  PrimitiveBoolean       -> turbo / lightning LoRA

WHY PATCH BOTH main + subgraph?
    The official template wraps sampling logic in a subgraph. The subgraph
    *instance* (node 105) exposes widgets, but the subgraph *definition*
    (definitions.subgraphs[0]) holds the real nodes. Patching only one side
    silently does nothing -- the values you set are simply ignored.

FRAME COUNT IS AUTO-COMPUTED by node 107 (ComfyMathExpression):
    max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17
    e.g. a=10 -> 243 frames  (243 / 24fps = 10.12s)
    Don't hardcode it; just set duration and let the formula run.

Usage:
    python scripts\\make_workflow.py
    python scripts\\make_workflow.py --template workflows/template_raw.json \\
        --image my_start.png --duration 5 --out workflows/my_video.json
    python scripts\\make_workflow.py --no-turbo     # higher quality, much slower
"""

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

TEMPLATE = os.path.join(ROOT, "workflows", "template_raw.json")
OUT = os.path.join(ROOT, "workflows", "h3_escape_10s.json")

DEFAULT_IMAGE = "h3_escape_start.png"
DEFAULT_VAE = "minimax_h3_video_vae_fp16.safetensors"
DEFAULT_ASPECT = "16:9 (Widescreen)"

DEFAULT_PROMPT = (
    "Cinematic escape sequence continuing from the starting frame. She sprints "
    "forward as the glowing dimensional rift collapses and shatters behind her, "
    "bursts of cyan and magenta energy shards scattering in the air. Rain droplets "
    "streak through the light. The camera tracks alongside her desperate run through "
    "the neon-lit rainy night street, neon reflections sliding across the wet asphalt, "
    "her black leather jacket and long hair whipping in the wind. She glances back "
    "over her shoulder in fear as the portal detonates into sparks. Urgent forward "
    "motion, cinematic handheld camera feel, volumetric light, high energy."
)


def frames_for(duration):
    """Replicate node 107 (ComfyMathExpression) exactly.

    expression: max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17
    """
    base = max(5, round(duration * 24))
    return base + (5 - (base % 17)) % 17


def _set(node, idx, named_key, value, label, changed):
    """Patch both widgets_values[idx] and widgets_values_named[key]."""
    wv = node.get("widgets_values")
    if isinstance(wv, list) and idx is not None and idx < len(wv):
        wv[idx] = value
    nvn = node.get("widgets_values_named")
    if isinstance(nvn, dict) and named_key in nvn:
        nvn[named_key] = value
    changed.append(label)


def patch(workflow, image, aspect, prompt, duration, vae, turbo, megapixels=None):
    changed = []

    # ---------- main graph ----------
    for n in workflow.get("nodes", []):
        nid = n.get("id")
        if nid == 114:
            _set(n, 0, "image", image, "main:114 LoadImage -> %s" % image, changed)
        elif nid == 115:
            _set(n, 0, "aspect_ratio", aspect,
                 "main:115 ResolutionSelector -> %s" % aspect, changed)
            if megapixels is not None:
                _set(n, 1, "megapixels", megapixels,
                     "main:115 megapixels -> %s" % megapixels, changed)
        elif nid == 105:
            # index map verified against the official template
            _set(n, 0, "prompt", prompt,
                 "main:105 prompt -> (%d chars)" % len(prompt), changed)
            _set(n, 3, "duration", duration,
                 "main:105 duration -> %ss" % duration, changed)
            _set(n, 7, "video_vae", vae,
                 "main:105 video VAE -> %s" % vae, changed)
            _set(n, 9, "turbo", turbo,
                 "main:105 turbo -> %s" % turbo, changed)

    # ---------- subgraph definition ----------
    for sg in (workflow.get("definitions", {}).get("subgraphs") or []):
        for n in sg.get("nodes", []):
            nid = n.get("id")
            if nid == 11:
                _set(n, 0, "vae_name", vae, "sub:11 VAELoader -> %s" % vae, changed)
            elif nid == 104:
                _set(n, 0, "prompt", prompt, "sub:104 prompt -> synced", changed)
            elif nid == 111:
                _set(n, 0, "value", float(duration),
                     "sub:111 duration -> %.1f" % float(duration), changed)
            elif nid == 126:
                _set(n, 0, "value", turbo,
                     "sub:126 turbo -> %s" % turbo, changed)

    return changed


def main():
    ap = argparse.ArgumentParser(description="Build a custom H3 i2v workflow")
    ap.add_argument("--template", default=TEMPLATE)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--aspect", default=DEFAULT_ASPECT)
    ap.add_argument("--megapixels", type=float, default=None,
                    help="0.3=480p  0.6=720p  1.0=1080p (higher = slower + more VRAM)")
    ap.add_argument("--prompt", default=DEFAULT_PROMPT)
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--vae", default=DEFAULT_VAE)
    ap.add_argument("--no-turbo", action="store_true",
                    help="disable lightning LoRA (slower, marginally better)")
    args = ap.parse_args()

    if not os.path.exists(args.template):
        print(f"[ERROR] template not found: {args.template}")
        print("        Fetch it first:")
        print('        python scripts\\mcp_call.py fetch_template '
              '\'{"name":"video_minimax_h3_i2v",'
              '"out_path":"workflows/template_raw.json"}\'')
        return 1

    # sanity check: start image must exist in ComfyUI's input dir
    comfy_input = os.environ.get("COMFY_INPUT_DIR")
    if comfy_input:
        p = os.path.join(comfy_input, args.image)
        if not os.path.exists(p):
            print(f"[WARN] start image not found: {p}")
            print("        Copy it into ComfyUI's input/ directory first.")

    wf = json.load(open(args.template, encoding="utf-8"))
    changed = patch(wf, args.image, args.aspect, args.prompt,
                    args.duration, args.vae, not args.no_turbo, args.megapixels)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(wf, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print("Patched:")
    for c in changed:
        print("  -", c)
    print(f"\nSaved -> {args.out}")

    n = frames_for(args.duration)
    print(f"\nFrame count (auto, node 107): {n} frames "
          f"= {n / 24:.2f}s @ 24fps")
    print("\nNext:")
    print(f"  python scripts\\mcp_call.py validate_workflow "
          f"'{{\"workflow_path\":\"{args.out}\"}}'")
    print(f"  python scripts\\mcp_call.py run_workflow "
          f"'{{\"workflow_path\":\"{args.out}\",\"wait\":false}}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
