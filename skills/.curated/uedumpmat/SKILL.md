---
name: uedumpmat
description: Dump Unreal Engine material asset information and generated shader source to clean Markdown reports. Use when the user says "uedumpmat", "dump the material of ...", "dump material", "get material info", "get material details", "material layout", asks for UE material properties, parameters, graph/node details, HLSL/shader code, or provides a single Material object path, material asset name, or `/Game/...` folder containing materials.
metadata:
  version: "0.1.0"
---

# UEDumpMat

Use this skill to inspect existing Unreal Engine material assets from command-line Unreal Python and produce AI-readable Markdown reports. Prefer commandlet execution; the user does not need to open the editor.

## Core Workflow

1. Locate the project `.uproject` and Unreal command binary. Prefer `UnrealEditor-Cmd.exe` with `-run=pythonscript`.
2. Copy `scripts/uedumpmat_dump.py` into the project, usually:

```text
Content/Python/MaterialDump/uedumpmat_dump.py
```

3. Set `UEDUMPMAT_TARGET` to either a single material object path, a `/Game/...` folder, or a semicolon-separated list.
4. Run the copied script with Unreal commandlet Python.
5. Verify the report folder contains `summary.md`, one `<MaterialName>.layout.md` per material, and copied shader files when HLSL debug output is available.

## Command Pattern

Use this PowerShell pattern for a single material:

```powershell
$env:UEDUMPMAT_TARGET="/Script/Engine.Material'/Game/Materials/MasterMaterials/M_Opaque/M_Tank_02.M_Tank_02'"
$env:UEDUMPMAT_OUTPUT_ROOT="Content/Python/MaterialDump"
$env:UEDUMPMAT_SHADER_KEYWORDS="BasePassPixelShader,BasePass"
& "D:\Path\To\UnrealEditor-Cmd.exe" "D:\Path\To\Project.uproject" -run=pythonscript -script="D:\Path\To\Project\Content\Python\MaterialDump\uedumpmat_dump.py" -unattended -nop4 -nosplash
```

Use this for a folder:

```powershell
$env:UEDUMPMAT_TARGET="/Game/Materials/MasterMaterials/M_Opaque"
$env:UEDUMPMAT_RECURSIVE="1"
& "D:\Path\To\UnrealEditor-Cmd.exe" "D:\Path\To\Project.uproject" -run=pythonscript -script="D:\Path\To\Project\Content\Python\MaterialDump\uedumpmat_dump.py" -unattended -nop4 -nosplash
```

## Output Layout

The script writes all intermediate and final output under:

```text
Content/Python/MaterialDump/<InputName>/
```

For each material, expect:

- `<MaterialName>.layout.md`: material properties, parameters, root inputs, accessible expression nodes, connections when available, used textures, serialized fallback symbols, and selected HLSL preview.
- `Shaders/<MaterialName>/`: copied shader debug source files selected from `Saved/ShaderDebugInfo`.
- `summary.md`: run settings, target list, success/failure status, and report paths.

Keep reports clean and factual. They are meant to be read by humans and reused as AI reference input, so organize by material properties, parameters, graph, textures, shader selection, and notes.

## Material Graph Limits

Unreal Python may not expose full material graph expression arrays or pin connections in commandlet mode. It can return zero or partial nodes even when the material is valid. Do not treat missing graph nodes as a failed dump.

When nodes are missing:

- Keep parameter and texture sections from `MaterialEditingLibrary`.
- Include serialized `.uasset` symbols as fallback evidence.
- Add a short note that exact graph/pin reconstruction may require a small reflected C++ editor helper.

## HLSL Selection

The Material Editor menu `Window > Shader Code > HLSL` uses private editor C++ paths that are not directly exposed to Python. The Python-only route is:

1. Enable shader debug dump console variables.
2. Recompile the material.
3. Search `Saved/ShaderDebugInfo` for the newest folder matching the material name.
4. Select and copy shader source files by keyword.

Default keywords should prefer BasePass pixel shader output:

```text
BasePassPixelShader,BasePass
```

If the user asks for another shader, set `UEDUMPMAT_SHADER_KEYWORDS` to comma-separated keywords such as:

```text
DebugViewModePixelShader
GPUSkinVFDefault,BasePassPixelShader
VertexShader
```

Report the selected source path and include a preview of the best matching shader. Copy supporting `.usf`, `.ush`, `.hlsl`, and `.txt` files into the report folder.

## Script Settings

The bundled script reads these environment variables:

- `UEDUMPMAT_TARGET`: required; material object path, package path, `/Game/...` folder, or semicolon-separated list.
- `UEDUMPMAT_OUTPUT_ROOT`: optional; default `Content/Python/MaterialDump`.
- `UEDUMPMAT_SHADER_KEYWORDS`: optional; default `BasePassPixelShader,BasePass`.
- `UEDUMPMAT_RECURSIVE`: optional; default `1` for folder targets.
- `UEDUMPMAT_MAX_SHADER_COPIES`: optional; default `24`.
- `UEDUMPMAT_WAIT_SECONDS`: optional; default `45`.
- `UEDUMPMAT_DEBUG`: optional; set `1` to add reflection diagnostics.

## Verification

After running Unreal, inspect:

- The command output for `[UEDumpMat] Wrote report`.
- `Content/Python/MaterialDump/<InputName>/summary.md`.
- At least one generated `.layout.md`.

If no shader files are copied, check whether shader compilation was skipped due to cached shaders or platform configuration. The material information dump can still be valid without HLSL capture.

## Bundled Resources

- `scripts/uedumpmat_dump.py`: commandlet-compatible Unreal Python script for single material and folder material dumps.
