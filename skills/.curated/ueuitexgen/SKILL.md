---
name: ueuitexgen
description: Generate Unreal Engine UI texture assets from reference UI screenshots by disassembling UI into reusable transparent PNG widget parts, an opaque background, layout mapping files, and optional UE import scripts. Use when the user asks for "ueuitexgen", UI texture extraction, sliced UI images, production-style UI widget PNGs, imagegen-assisted UI asset generation, reusable UI parts, or fake/disassembled hierarchy files for downstream `uewbpgen` Widget Blueprint generation.
metadata:
  version: "0.1.0"
---

# ueuitexgen

Generate game-ready Unreal Engine UI texture assets (`.uasset`) from reference UI screenshots by disassembling UI into reusable PNG parts, producing a layout mapping file for downstream Widget Blueprint generation.

## Core Output Contract

For each UI set, create a subfolder named `<UI_NAME>/` containing:
- `<UI_NAME>.layout.txt` for widget-to-texture mapping.
- `*.png` files for all disassembled textures.
- Generated `*.uasset` textures after the UE import/build step.
- Optional `<UI_NAME>.py` or import scripts for UE texture automation.
- `intermediate/` for imagegen source boards, chroma-key sources, masks, contact sheets, crops, and trace files.

Required output rules:
1. Create one opaque full-screen background PNG.
2. Create separate transparent RGBA widget PNGs for buttons, icons, cards, panels, bars, badges, etc.
3. Never ship an atlas/sprite sheet as the final widget asset. Source boards are allowed only in `intermediate/` and must be sliced into individual PNGs.
4. Keep widget filenames semantic and stable, preferably lowercase snake_case with size suffix.
5. Write a layout file mapping every widget to its size, parent/group, and texture path for `uewbpgen`.

## Quality Bar

Default to production-style assets, not solid-color placeholders, unless the user explicitly asks for rough blockout/prototype art.

Production-style means:
- Use the `imagegen` skill for polished raster UI art when the visual quality matters.
- Preserve the reference UI's hierarchy, proportions, color language, and functional roles.
- Add material detail appropriate to the style: bevels, glow, glass, brushed metal, carbon fiber, halftone, scratches, scanlines, shadows, and icon detail.
- Keep final UI readable in Unreal: avoid tiny baked text unless it is intentionally decorative; prefer Unreal `TextBlock` for live labels.

Use deterministic drawing only for masks, layout diagnostics, temporary guides, or simple fallback widgets. Do not leave obvious flat rectangles as final production assets when imagegen can be used.

## Imagegen-Assisted Workflow

Use this workflow for high-quality results:

1. Analyze the reference screenshot(s) and identify the UI asset manifest before generating art.
2. Decide each final slice size first, e.g. `button_upgrade_248x58`, `tank_card_red_160x126`, `module_socket_empty_64x64`.
3. For each asset or widget family, write meaningful imagegen prompts that describe:
   - widget purpose and final use in Unreal UI,
   - visual style/materials from the reference,
   - target shape and approximate aspect ratio,
   - whether the output should contain text or leave blank space for UMG text,
   - constraints: no watermark, no copied logos, crisp edges, no real brand marks.
4. Prefer direct per-widget imagegen when asset count is small or details are unique.
5. For many related assets, generate high-quality source boards by family, then slice them:
   - controls board: buttons, chips, badges, small toggles,
   - module/icon board: sockets, stat chips, ability/perk icons,
   - carousel/card board: vehicle cards, selected frame, assigned banner,
   - tank/character cutout board: hero render on chroma-key if needed,
   - full-screen reference board: background mood and global style.
6. Save all imagegen outputs into `intermediate/` and keep original generated images untouched in Codex's generated image folder.
7. Extract each source-board element into its own final PNG. The source board is not the deliverable.
8. Resize each extracted element to the pre-decided slice size with high-quality resampling.
9. Re-add live text in UMG where practical; only bake short labels when matching a specific reference is important.

Transparent asset guidance:
- Use `imagegen` on a flat chroma-key background for isolated widgets when true alpha is needed.
- Remove chroma key locally and validate transparent corners, plausible coverage, and no green fringe.
- If chroma-key removal would damage green UI elements, use magenta or another unlikely key color.
- Never treat source-board green backgrounds as final transparent pixels without validating alpha.

## Step-by-Step Workflow

1. Read all input reference images and infer screen purpose, interaction groups, hierarchy, and reusable widgets.
2. Create or choose `<UI_NAME>/`; for risky regeneration or locked `.uasset`s, create a versioned folder such as `<UI_NAME>_V02` rather than forcing overwrite.
3. Build an asset manifest with widget id, semantic name, final size, opacity rule, and generation method.
4. Generate or extract the opaque background.
5. Generate production art with `imagegen` per widget or per widget-family source board.
6. Disassemble/slice source boards into standalone transparent PNGs with exact target sizes.
7. Create `intermediate/` contact sheets for visual QA of extracted assets.
8. Write/update `<UI_NAME>.layout.txt` with hierarchy and texture bindings.
9. Generate/update UE texture import scripts using UI texture settings: sRGB on, UI texture group, no mips, non-streaming.
10. Run UE import when requested, then verify `.uasset` count and names match the PNG set.
11. If chaining to `uewbpgen`, pass the layout file and texture package path forward.

## PNG Standard

For every final widget PNG:
1. Use RGBA8 (`R8G8B8A8`).
2. Keep unused pixels alpha `0x00`.
3. Keep the intended widget shape and glow visible without opaque rectangular backing unless the backing is part of the design.
4. Avoid baked layout guides, crop marks, source-board backgrounds, and debug labels.
5. Save exactly one widget per PNG.

Background PNG rule:
- Background must be opaque-only (`alpha=255` everywhere), suitable as a root UMG image.

## Layout File Specification

The layout file must be human-readable and machine-friendly.

Include:
- `ui_name`, `source_refs`, `output_root`, `asset_root`, `screen_size`, `timestamp`.
- One block per widget.
- Widget class/type, parent/group, slot position/size/z, texture path, opacity notes, and optional `action` names.
- No combined texture references.

Example:

```text
ui_name: Tank_Select_Mod_Prototype_V02
asset_root: /Game/UI_Generated/Tank_Select_Mod_Prototype_V02
screen_size: 1536x864

widget: UpgradeButtonImage
class: Image
parent: RightPanel
slot: 50,382,248,58,4
texture: button_upgrade_248x58.png

widget: UpgradeButton
class: Button
parent: RightPanel
slot: 50,382,248,58,5
action: upgrade_selected_tank
```

## Iteration Policy

When improving visual quality:
- Do not merely overlay noise/glow onto flat placeholder art if imagegen source assets are available.
- Regenerate or re-extract the actual per-slice PNGs from imagegen sources.
- Keep prior iterations unless the user explicitly asks to replace them.
- If UE import fails due to locked files (`Error Code 32` on Windows), create a new versioned package and import there instead of killing the editor or forcing deletes.
- Keep intermediate source boards and contact sheets for traceability.

## Validation Checklist

Before finishing, verify:
- No final atlas sheets were produced.
- Background alpha is fully opaque.
- Each widget PNG is separate and has transparent unused pixels where expected.
- Chroma-key extraction has transparent corners and no obvious fringe.
- Layout references only existing PNGs.
- Import script points to the correct `/Game/...` package.
- Generated `.uasset` count matches the expected PNG count.
- A contact sheet or spot-check confirms the assets do not look like flat solid-color placeholders.

## Lessons From Previous Tank Selection Run

The successful high-quality iteration used:
- Multiple imagegen source boards split by widget family.
- Exact target sizes decided before generation/extraction.
- Chroma-key tank render converted to a transparent cutout.
- Source boards stored only in `intermediate/`.
- Final PNGs extracted one widget per file and imported into a clean versioned UE package.

Avoid the failed pattern:
- Drawing all widgets as simple colored polygons first and trying to make them production quality afterward with generic noise/glow.
