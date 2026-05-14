---
name: uewbpgen
description: Generate Unreal Engine Widget Blueprint assets through per-WBP Unreal Python scripts that duplicate a required template Widget Blueprint with a CanvasPanel root. Use when the user says "uewbpgen", asks to "Create a WBP", "create an UI", "create UI widgets", "generate a Widget Blueprint", provides UI screenshots/references, or describes a screen/layout that should become a UE `.uasset` Widget Blueprint.
metadata:
  version: "0.1.0"
---

# UEWBPGen

## Overview

Use this skill to turn a UI description, screenshot, website reference, or rough layout into a real Unreal Engine Widget Blueprint asset. The preferred implementation is a generated per-asset Unreal Python script named after the Widget Blueprint, for example `WBP_Login.py`, which duplicates a simple template Widget Blueprint and builds the requested widget hierarchy on the duplicate.

## Required Template

Unreal Python in some UE 5.x projects cannot reliably create a Widget Blueprint designer tree or assign `WidgetTree.RootWidget` from scratch. Always use a template-based workflow unless the local project proves it exposes a stronger API.

The template must be created once by the user in Unreal Editor:

1. Create a Widget Blueprint asset.
2. Add one `Canvas Panel` as the root widget.
3. Rename the root canvas to `RootCanvas`.
4. Save the asset.
5. Prefer the default path `/Game/Python/ActorTools/WBP_Python_Template_RootCanvas`, or use the path supplied by the user.

If the template path or output folder is missing, ask only when it is risky. Otherwise default to `/Game/Python/ActorTools/WBP_Python_Template_RootCanvas` for the template and `/Game/Python/ActorTools` for generated assets.

## Workflow

1. Interpret the request. Identify the target screen purpose, functional UI elements, rough resolution, anchors, and interaction groups. If the user provides an image, analyze hierarchy, alignment, position, relative scale, colors, and control types.
2. Ignore non-functional artwork details in prototypes. Put background art, screenshots, 3D scenes, VFX, tanks, characters, scenery, and texture-heavy decoration into a single background layer such as `BGLayer_PredefinedBackground` or `BGLayer_Engine3DScene`. Represent it with one `Image` placeholder unless the user asks for detailed art reconstruction.
3. Build only functional hierarchy. Prefer clean groups such as `FunctionLayer`, `TopBar`, `LeftRail`, `BottomRight_ActionCluster`, `LoginPanel`, and `FooterLayer`. Use `CanvasPanel` for anchored screen-level groups, then use `Button`, `TextBlock`, `EditableTextBox`, `ComboBoxString`, `CheckBox`, `Image`, `Border`, `ProgressBar`, `Slider`, `ScrollBox`, and panel widgets only where they serve real layout or interaction.
4. Choose the asset name. Use the user's name when supplied, normalized to `WBP_DescriptiveName`. If missing, infer a concise name from the UI purpose, for example `WBP_LoginScreen` or `WBP_LobbyMockup`.
5. Choose the output path. Prefer a user-provided `/Game/...` folder. If missing, use `/Game/Python/ActorTools` for prototypes.
6. Generate a corresponding Unreal Python script named exactly after the asset, for example `WBP_LoginScreen.py`. The script must duplicate the template, find `RootCanvas`, create the widget hierarchy on the duplicate, save the asset, and log the generated path.
7. Place the generated `.py` in a project Python/tooling folder when available, usually `Content/Python/ActorTools` or `Content/Python`. Do not write `.uasset` files directly.
8. Tell the user how to run the generated script from Unreal Editor's Output Log Python input:

```python
exec(open(r"D:\path\to\project\Content\Python\ActorTools\WBP_Name.py", encoding="utf-8").read())
```

9. When command-line Unreal execution is appropriate, mirror the `uematgen` pattern: use Unreal Editor Python to generate the `.uasset`, then verify the generated asset exists under `Content/...`.

## Script Generation

Use `scripts/write_wbp_script.py` to generate a first-pass per-WBP Unreal Python script from a JSON spec. The generated script is intended to be reviewed and customized by Codex for non-trivial layouts.

Minimum spec shape:

```json
{
  "asset_path": "/Game/Python/ActorTools/WBP_LoginMockup",
  "template_asset_path": "/Game/Python/ActorTools/WBP_Python_Template_RootCanvas",
  "root_canvas_name": "RootCanvas",
  "screen_size": [1397, 869],
  "widgets": [
    {"type": "CanvasPanel", "name": "BGLayer_PredefinedBackground", "parent": "RootCanvas", "slot": {"x": 0, "y": 0, "w": 0, "h": 0, "z": 0, "anchors": [0, 0, 1, 1]}},
    {"type": "Image", "name": "Predefined_BG_Image", "parent": "BGLayer_PredefinedBackground", "slot": {"x": 0, "y": 0, "w": 1397, "h": 869}},
    {"type": "CanvasPanel", "name": "FunctionLayer", "parent": "RootCanvas", "slot": {"x": 0, "y": 0, "w": 0, "h": 0, "z": 10, "anchors": [0, 0, 1, 1]}},
    {"type": "Button", "name": "StartGame_Button", "parent": "FunctionLayer", "text": "START GAME", "slot": {"x": 570, "y": 575, "w": 263, "h": 55, "z": 20}}
  ]
}
```

Then run:

```powershell
python "<skill>/scripts/write_wbp_script.py" "<spec.json>" --out-dir "D:\Project\Content\Python\ActorTools"
```

Read `references/unreal_widget_python.md` when designing specs, handling anchors, choosing widget types, or troubleshooting UE Python limitations.

## Design Rules

- Keep prototype hierarchy simple and performance-oriented. Prefer a few screen-level canvases and grouped functional panels over many decorative widgets.
- Use `CanvasPanel` only where absolute position or screen-edge anchoring is needed. Use `HorizontalBox`, `VerticalBox`, `Overlay`, `SizeBox`, and `ScrollBox` inside groups when they reduce manual slot work.
- Use anchors for screen-edge UI: top-left player info, top-center currency, top-right navigation, left/right rails, bottom-left offers, bottom-center profile, and bottom-right CTAs.
- Keep background/image-heavy content in `BGLayer`; keep interactive controls in `FunctionLayer`.
- Use placeholder `Image` or `Border` widgets for missing textures. Do not attempt to recreate texture details unless the user explicitly asks.
- Name widgets by purpose, not appearance, for example `Battle_Button`, `Server_ComboBox`, `PrivacyAccept_CheckBox`, `TopRight_Navigation`.
- Set position, size, z-order, anchors, alignment, text, font size, tint/color, checkbox state, combo options, and simple values where the generated script supports them.
- For screenshots with 3D content, represent the 3D viewport as a single background image/engine layer and focus on the 2D widget overlay.

## References And Inputs

If the user provides image references, inspect the image directly and infer hierarchy, anchors, and rough dimensions. If the user references a website, design system, document, or remote asset, use available tools/plugins to inspect it before generating the spec when current or precise visual information matters.

## Revision Policy

For iterative changes, prefer creating a new timestamped or versioned WBP script/asset unless the user clearly asks to replace the previous one. Do not silently stack new generated widgets into an existing generated asset; duplicate the template or a clean known base and rebuild the requested hierarchy.

## Bundled Resources

- `scripts/write_wbp_script.py`: writes a per-WBP Unreal Python generator script from a JSON widget spec.
- `references/unreal_widget_python.md`: UE Python template workflow, slot/anchor notes, widget type guidance, and troubleshooting.
