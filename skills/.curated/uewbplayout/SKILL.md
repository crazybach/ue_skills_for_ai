---
name: uewbplayout
description: Dump Unreal Engine Widget Blueprint designer/widget-tree layouts to Markdown or text reports. Use when the user says "uewbplayout", "dump widgets", "dump widget tree", "layout widgets", "WBP layout", asks to export Details/layout for UMG Widget Blueprints, provides WBP .uasset names/object paths/reference paths/directories, or wants scripts and .md reports for one or more WBP assets.
metadata:
  version: "0.1.0"
---

# UEWBPLayout

Use this skill to export Unreal UMG Widget Blueprint hierarchy/layout reports from Editor Python.

## Core Rule

Use full Editor Python, not commandlet Python, when designer trees matter:

```bat
UnrealEditor.exe Project.uproject -ExecutePythonScript="...\uewbplayout_editor_commandline.py" -nop4 -nosplash
```

Avoid relying on:

```bat
UnrealEditor-Cmd.exe Project.uproject -run=pythonscript
```

Commandlet mode may expose `WidgetTree` as protected or return an unreadable tree.

## Bundled Scripts

Copy scripts from this skill into the project, usually `Content/Python/WidgetTools/`:

- `scripts/uewbplayout_export_one.py`: reusable Widget Blueprint hierarchy exporter.
- `scripts/uewbplayout_editor_commandline.py`: full-Editor wrapper for one target asset.
- `scripts/uewbplayout_export_folder.py`: batch exporter for a `/Game/...` folder.
- `scripts/uewbplayout_full_editor_run.bat`: portable batch template driven by env vars.

Rename copied scripts per task if useful, for example `export_BP_FireButtonWithReload_layout.py` or `export_buttons_layouts.py`. Keep generated reports under `Content/Python/WidgetTools/Reports/` unless the user asks otherwise.

## Single WBP Workflow

1. Normalize the user input to a WidgetBlueprint object path, for example:

```text
/Script/UMGEditor.WidgetBlueprint'/Game/UI/Widgets/Buttons/BP_FireButtonWithReload.BP_FireButtonWithReload'
```

2. Copy `uewbplayout_export_one.py` and `uewbplayout_editor_commandline.py` into the project tool folder.
3. Run full Editor Python with env vars:

```powershell
$env:UEWBPLAYOUT_TARGET="/Script/UMGEditor.WidgetBlueprint'/Game/UI/Widgets/Buttons/BP_FireButtonWithReload.BP_FireButtonWithReload'"
$env:UEWBPLAYOUT_REPORT_NAME="BP_FireButtonWithReload_widget_hierarchy.md"
$env:UEWBPLAYOUT_ROOT_NAME="InvalidationBox_0" # optional; omit or empty to guess
& .\Content\Python\WidgetTools\uewbplayout_run.bat
```

4. Verify the report header includes `Root widget(s)` and a nonzero `Widget count`.

## Folder Workflow

Use when the user gives a folder such as `/Game/UI/Widgets/Buttons`.

1. Copy `uewbplayout_export_one.py`, `uewbplayout_export_folder.py`, and a runner batch into the project.
2. Set:

```powershell
$env:UEWBPLAYOUT_TARGET_DIR="/Game/UI/Widgets/Buttons"
$env:UEWBPLAYOUT_SUMMARY_NAME="Buttons_widget_hierarchy_summary.md"
```

3. Run `UnrealEditor.exe -ExecutePythonScript` against `uewbplayout_export_folder.py`.
4. Inspect the summary report and any one-widget results; some assets may need a manual root name.

## Root Handling

If the user gives the root element name, pass it directly as `UEWBPLAYOUT_ROOT_NAME` or set `TARGET_ROOT_WIDGET_NAMES` in the script.

If root is missing, use this heuristic:

1. Scan the `.uasset` bytes for likely widget names.
2. Try each candidate as root through full Editor Python.
3. Walk each candidate subtree.
4. Pick the candidate with the largest readable subtree.
5. Tie-break toward containers: `InvalidationBox`, `CanvasPanel`, `Overlay`, panel/box widgets, then leaf widgets like `Image`.

This session found useful examples:

- `BP_BattleScreen`: manual root `CanvasPanel_366`, widget count 84.
- `BP_FireButtonWithReload`: guessed root `InvalidationBox_0`, widget count 14.
- `/Game/UI/Widgets/Buttons`: batch heuristic selected largest readable subtrees and wrote a summary.

## Output Expectations

For each WBP, create or update:

- A Python exporter/wrapper script in the project tooling folder.
- A Markdown report named `<AssetName>_widget_hierarchy.md` or a user-specified name.
- For folder runs, a summary report named `<FolderName>_widget_hierarchy_summary.md`.

The report should include source asset, WidgetTree source, execution context, root widget(s), widget count, dependencies, widget hierarchy, slot layout data, and readable widget properties.

## Troubleshooting

- If the report says `WidgetTree has no accessible root widgets`, rerun with a known root name or use the candidate scan workflow.
- If a guessed root yields only one widget, it may be a leaf. Batch mode should prefer the largest subtree; otherwise ask the user to provide the root from the Designer hierarchy.
- If full Editor Python cannot resolve the root, Python is insufficient for that asset; recommend a small C++ Editor helper exposing `UWidgetBlueprint::WidgetTree` / `UWidgetTree::GetAllWidgets`.
