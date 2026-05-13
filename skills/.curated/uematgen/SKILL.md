---
name: uematgen
description: Generate Unreal Engine material assets through per-material Unreal Python scripts and Custom HLSL material nodes. Use when the user asks to "help to generate a material", "generate a material of ...", "uematgen", "UEMatGen", provides HLSL, paper/website references, image references, or describes a shader/material effect that should become a usable `.uasset` material in an Unreal project.
metadata:
  version: "0.1.1"
---

# UEMatGen

## Overview

Use this skill to turn a material effect request into a real Unreal Engine material asset. The preferred implementation is a generated `M_Name.py` Unreal Python script that assembles a Material asset with a Custom HLSL node, exposed parameter nodes, and connections to the final material outputs. The generated script should be usable either from `UnrealEditor-Cmd.exe -run=pythonscript` or from the open editor's Python execution path.

## Fresh Environment Install

Publish this skill as a normal GitHub directory that contains `SKILL.md` at the skill root. This repository publishes it at `https://github.com/crazybach/ue_skills_for_ai/tree/main/skills/.curated/uematgen`.

In a fresh Codex environment, install it through the preinstalled skill installer by giving the GitHub directory URL:

```text
$skill-installer install https://github.com/crazybach/ue_skills_for_ai/tree/main/skills/.curated/uematgen
```

The equivalent helper command is:

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE ".codex" }
python (Join-Path $codexHome "skills\.system\skill-installer\scripts\install-skill-from-github.py") --url "https://github.com/crazybach/ue_skills_for_ai/tree/main/skills/.curated/uematgen"
```

After install, restart Codex so the new skill is discovered. For private repos, make sure GitHub credentials are available through existing git auth or `GITHUB_TOKEN`/`GH_TOKEN`.

## Workflow

1. Summarize the requested material function first. Describe what the generated material should do, for example: "pass color and texture parameters through a standard PBR lighting setup", "create a 2D SDF animation", or "create a rotating UV effect with a speed parameter". Use any user-provided HLSL, website/paper notes, or image references to define the intended effect.
2. Determine the material asset name. If the user gave a clear name, normalize it to Unreal style: `M_DescriptiveName`. If no clear name exists, propose a representative `M_...` name from the function summary and ask the user only when the choice would be risky or ambiguous.
3. Determine the save folder. Prefer a user-provided `/Game/...` path. If missing, search the project for existing material folders such as `/Game/Materials`, `/Game/Art/Materials`, or domain-specific folders, then choose a reasonable subfolder or ask the user when multiple choices are equally plausible.
4. Locate the `.uproject` file and the Unreal Editor command binary. Search the repo and common engine paths first. Ask the user for paths only if they cannot be found reliably.
5. Write a corresponding per-material script named after the asset, for example `M_StandardPBR.py`. The script must create or update the `.uasset`, construct parameter/input nodes, create a Custom HLSL node, inject the HLSL code, connect outputs, save the material, and log the generated asset path.
6. Run Unreal Editor command-line generation when possible. Prefer `-run=pythonscript -script="M_Name.py"` because it worked in UE 5.3-style commandlets. If the editor is already open or command execution is not available, tell the user how to run the generated script from the editor Python console/menu.
7. Verify success by checking that the `.uasset` exists under `Content/...` and by searching `Saved/Logs/*.log` for `[UEMatGen] Generated material asset:`. If command output omits the custom log line, inspect the saved logs before assuming failure.
8. Report the generated asset path, script path, command or batch file used, and any assumptions about references, HLSL limitations, or parameters that the user may want to tune.

## Implementation Rules

- Prefer a Custom HLSL node for non-trivial material behavior. UE material graphs are human-friendly but verbose for AI generation; keep graph complexity low and put core logic in HLSL.
- For multi-result effects, prefer one Custom HLSL node with Additional Outputs instead of several separate Custom nodes. Name pins by meaning and material role, for example `BaseColorOut`, `EmissiveColorOut`, `OpacityOut`, `NormalOut`, or `WPOOffsetOut`, so users can understand and manually wire the graph when needed.
- Expose useful controls as Unreal material parameter nodes: `ScalarParameter`, `VectorParameter`, `TextureSampleParameter2D`, and `TextureObjectParameter` where appropriate.
- Start with the fewest meaningful parameters that control the requested effect. Avoid speculative tuning knobs, duplicate controls, and random default directions; add more parameters only when the user asks for the extra control.
- Use `TextureObjectParameter` when the Custom HLSL needs to sample a texture itself. In HLSL, a texture object input named `StyleTexture` is sampled with `Texture2DSample(StyleTexture, StyleTextureSampler, UV)`.
- Include `TextureCoordinate` and `Time` nodes by default for procedural, animated, UV-space, SDF, distortion, dissolve, or image-processing materials. Let the user tune input names only when needed.
- Prefer UE material editor built-in nodes as Custom HLSL inputs when they make the effect clearer or more robust, especially position/context nodes such as `WorldPosition`, `ActorPositionWS`, `ObjectPositionWS`, `CameraPositionWS`, `LocalPosition`, `ParticlePositionWS`, `ScreenPosition`, and `DepthFromWorldPosition`. Use these nodes rather than reconstructing context in HLSL when available.
- Keep generated HLSL self-contained and deterministic. Name inputs clearly, for example `UV`, `Time`, `Speed`, `Tint`, `StyleTexture`, or `SdfScale`. Add concise comments inside non-trivial Custom HLSL blocks that explain the meaning of masks, cell ids, animation phases, output pins, and any vertex-vs-pixel assumptions so humans can inspect and rewire the node confidently.
- Connect the Custom HLSL output to the correct material property, usually Base Color, Emissive Color, Opacity, World Position Offset, or Normal. For PBR-style materials, use simple parameter nodes for Metallic, Roughness, Specular unless the HLSL specifically computes them.
- If Unreal Python cannot connect a Custom HLSL output pin to the final material property reliably, try at most 2-3 reasonable compatibility approaches, such as alternate enum names, alternate output names, or a direct material-input fallback. If those fail, leave the output pin unconnected, keep the generated value available on a clear pin such as `WPOOffsetOut`, and tell the user exactly which pin to wire manually. Do not keep adding debug scripts or fallback nodes that obscure or duplicate the intended output.
- For WPO effects, remember World Position Offset is evaluated per vertex. Do not depend on pixel-only masks, tiny UV border masks, or per-pixel cell interiors to produce displacement; low-density meshes may have vertices only on UV borders. Make the WPO output valid at mesh vertices, and keep fine grid lines/color masks in Base Color or Emissive.
- For grid or cell WPO effects, drive displacement from cell index or vertex-valid position context so each tile/cell can move as a unit. Keep the WPO output as a vector offset such as `WPOOffsetOut`; expose a single direction vector only when needed, with direct defaults such as `(0, 0, 1)` for upward Z motion.
- Use compatibility wrappers for Unreal Python enum names, `CustomInput` construction, `connect_material_expressions`, and `connect_material_property`; Unreal Python APIs vary across engine versions.
- End generated material scripts with an unconditional `main()` call so commandlet execution and in-editor script execution both perform the asset generation.
- Do not write `.uasset` files directly. Always generate them through Unreal Editor Python.
- Save per-material generator scripts outside `Content/` unless the user asks to store tooling in the project. A project `Saved/UEMatGen/` or external scripts folder is appropriate. If the user asks for a related Python script folder, saving next to project Python tools is acceptable.

## Revision Policy

When modifying an existing generated material, choose one of these strategies before writing files:

1. **Version-increment**: create `M_Name_V02.py`, `M_Name_V02_Run.bat`, and `/Game/.../M_Name_V02`. Prefer this when user feedback is exploratory or when preserving the previous result helps comparison.
2. **Clean-regenerate**: delete or move the previous `.uasset` and regenerate the same asset name. Use only when the user clearly wants replacement and deletion is acceptable.
3. **Update-in-place**: load the existing material, delete all previous material expressions, rebuild all nodes and connections, then save. Use when the user wants the same asset path preserved.

For iterative revisions, decide the next version number yourself from the user's latest requested iteration and the existing files/assets. Default to auto-incrementing the version, for example V05 to V06, unless the user explicitly asks to update in place or use a specific version. Tell the user which new version will be created before editing. Advance the version every time and build the new version from a clean setup. Do not blindly copy the previous script and keep editing accumulated graph logic; either generate a fresh script from the current intended design or copy only stable helper functions, then rewrite the effect-specific HLSL, parameters, output pins, and wiring. If the versioned asset already exists, delete that versioned asset or delete all material expressions before rebuilding so broken/stale Custom nodes never remain.

Do not silently stack new nodes into an existing generated material without first deleting the old generated graph or creating a new versioned asset.

## Script Generation

Use `scripts/write_material_script.py` to generate a first-pass per-material Unreal Python script from a JSON spec. The generated script is intended to be reviewed and customized by Codex when the effect needs special HLSL or graph wiring.

Minimum spec shape:

```json
{
  "asset_path": "/Game/Materials/M_RotatingSDF",
  "description": "Animated 2D SDF ring with a speed parameter.",
  "blend_mode": "translucent",
  "shading_model": "unlit",
  "two_sided": false,
  "custom_output": "emissive",
  "custom_output_type": "float3",
  "include_uv": true,
  "include_time": true,
  "hlsl_code": "return float3(1, 1, 1);",
  "scalar_parameters": {"Speed": 1.0, "Scale": 8.0},
  "vector_parameters": {"Tint": [0.2, 0.8, 1.0, 1.0]},
  "texture_object_parameters": {"StyleTexture": "/Engine/EngineResources/DefaultTexture"},
  "texture_parameters": {"SampledColor": "/Game/Textures/T_DefaultWhite"},
  "material_parameters": {"opacity": 1.0, "roughness": 0.5, "metallic": 0.0}
}
```

Then run:

```powershell
python "<skill>/scripts/write_material_script.py" "<spec.json>" --out-dir "D:\Project\Saved\UEMatGen" --write-bat --editor "<UnrealEditor-Cmd.exe>" --uproject "<Project.uproject>"
```

Read `references/unreal_command.md` when constructing commands, locating Unreal binaries, or deciding between command-line and in-editor execution.

After the helper writes the first-pass script, inspect the generated `M_Name.py` before running Unreal for non-trivial effects. Customize HLSL, parameter defaults, material settings, or graph wiring directly in that script when the prompt requires behavior beyond the JSON schema.

## Bundled Resources

- `scripts/write_material_script.py`: creates `M_Name.py` per-material Unreal Python scripts and optional `.bat` launchers from a material spec.
- `references/unreal_command.md`: command-line patterns, path discovery, and troubleshooting notes for running Unreal Python.
