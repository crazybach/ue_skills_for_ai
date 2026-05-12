# Unreal Command Reference

## Path Discovery

Find `.uproject` files from the current repo first:

```powershell
Get-ChildItem -Recurse -Filter *.uproject
```

Find installed Windows editor binaries from common Epic locations:

```powershell
Get-ChildItem 'C:\Program Files\Epic Games' -Recurse -Filter UnrealEditor-Cmd.exe -ErrorAction SilentlyContinue
```

Prefer the engine version that matches the project. If the project uses a source-built engine, inspect project docs or sibling `Engine/Binaries/Win64/UnrealEditor-Cmd.exe`.

For source-built workspaces, also check paths like:

```powershell
Get-ChildItem '<workspace>\UnrealEngine\Engine\Binaries\Win64' -Filter 'UnrealEditor*.exe'
```

## Command-Line Generation

For UE 5.3 style command execution, prefer:

```bat
"C:\Program Files\Epic Games\UE_5.3\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" ^
  "D:\Projects\MyProject\MyProject.uproject" ^
  -run=pythonscript ^
  -script="D:\Projects\MyProject\Saved\UEMatGen\M_StandardPBR.py" ^
  -unattended -nop4 -nosplash
```

Some versions also support:

```powershell
& "<UnrealEditor-Cmd.exe>" "<Project.uproject>" -unattended -nop4 -nosplash -ExecutePythonScript="<M_Name.py>"
```

Use the `-run=pythonscript -script="..."` form when matching user examples or UE 5.3 commandlets.

Generated material scripts should call `main()` at file scope. This makes the same script work from commandlets and from the open editor script runner.

## In-Editor Execution

If Unreal Editor is already open, the user can run the generated `M_Name.py` through the Python console or an editor utility entry point. The script is self-contained and includes the asset path, material settings, Custom HLSL code, parameter nodes, output connections, and save call.

If the new asset does not appear immediately in an already-open Content Browser, refresh the folder or sync/browse to the asset path after generation.

## Generated Batch File

`scripts/write_material_script.py --write-bat` emits `M_Name_Run.bat` beside the generated `M_Name.py`. Use it when the user wants repeatable local generation or when the command is too long to paste comfortably.

## Verification

After command-line generation:

```powershell
Test-Path '<Project>\Content\<Folder>\M_Name.uasset'
rg -n "\[UEMatGen\]|Generated material asset|graph warnings|Failed to generate" '<Project>\Saved\Logs' -g "*.log"
```

Treat a saved `.uasset` plus `[UEMatGen] Generated material asset:` as a successful first pass. Engine/plugin warnings unrelated to the generated material are common in large projects.

## Troubleshooting

- Ensure the Python Editor Script Plugin is enabled.
- Ensure the asset path starts with `/Game/` and the asset name starts with `M_`.
- Ensure texture parameter paths point to imported `Texture2D` assets.
- For HLSL texture sampling inside Custom nodes, use a texture object input and sample it as `Texture2DSample(InputName, InputNameSampler, UV)`.
- If the Custom node input API differs in the local Unreal version, adjust the generated `set_custom_inputs` function in `M_Name.py` rather than changing the material design.
- If command-line generation fails because the project requires UI modules, run the generated script from the open editor instead.
