# Unreal Widget Python Notes

## Template-Based Creation

Use a saved Widget Blueprint template with a `CanvasPanel` root named `RootCanvas`. Duplicate the template with `unreal.EditorAssetLibrary.duplicate_asset(template_path, destination_path)`, then add children to the duplicate. This avoids UE Python API gaps where `WidgetBlueprint.widget_tree`, `unreal.WidgetTree`, or `RootWidget` assignment may not be exposed.

Default template path:

```text
/Game/Python/ActorTools/WBP_Python_Template_RootCanvas
```

Default output folder:

```text
/Game/Python/ActorTools
```

## Finding The Widget Tree And Root Canvas

Generated scripts should try several compatibility paths:

1. `widget_blueprint.get_editor_property("widget_tree")`
2. `unreal.find_object(widget_blueprint, "WidgetTree")`
3. `unreal.load_object(None, "/Game/Path/WBP.WBP:WidgetTree")`
4. Find the root canvas by name under the widget tree, usually `RootCanvas`.

Do not require `unreal.WidgetTree` to exist as a Python class. Some projects expose the object but not the class symbol.

## Running Generated Scripts

From Unreal Editor Output Log with the input mode set to Python:

```python
exec(open(r"D:\Project\Content\Python\ActorTools\WBP_Name.py", encoding="utf-8").read())
```

The Output Log Python field executes Python code directly. Do not type `py "file.py"` there because that is shell syntax and causes a Python `SyntaxError`.

## Widget Spec Guidelines

Use a flat JSON list with explicit `parent` names. Each widget should have a stable unique `name`, a `type`, and an optional `slot`:

```json
{"type": "Button", "name": "Battle_Button", "parent": "BottomRight_ActionCluster", "text": "BATTLE!", "slot": {"x": 206, "y": 60, "w": 264, "h": 58, "z": 10}}
```

Supported common slot fields:

```json
{"x": 0, "y": 0, "w": 100, "h": 40, "z": 0, "anchors": [0, 0, 1, 1], "alignment": [0, 0]}
```

Anchor examples:

- Full screen stretch: `anchors: [0, 0, 1, 1]`, position and size often `0,0,0,0`.
- Top left: `anchors: [0, 0, 0, 0]`.
- Top center: `anchors: [0.5, 0, 0.5, 0]`, `alignment: [0.5, 0]`.
- Top right: `anchors: [1, 0, 1, 0]`, use negative X offsets.
- Bottom left: `anchors: [0, 1, 0, 1]`, use negative Y offsets.
- Bottom center: `anchors: [0.5, 1, 0.5, 1]`, `alignment: [0.5, 0]`.
- Bottom right: `anchors: [1, 1, 1, 1]`, use negative X and Y offsets.

## Widget Type Choices

Use these defaults for prototypes:

- `CanvasPanel`: root-level layers and anchored groups.
- `Image`: predefined background, icon placeholders, missing texture placeholders.
- `Border`: simple colored blocks, backplates, and panels.
- `Button`: clickable CTAs, icon buttons, menu entries, and nav buttons.
- `TextBlock`: labels, values, version text, and placeholder icon glyphs.
- `EditableTextBox`: user text input.
- `ComboBoxString`: server/environment selection.
- `CheckBox`: terms/privacy acceptance and toggles.
- `ProgressBar`: resource progress and timers when an actual fill value matters.
- `Slider`: settings-style numeric controls.
- `ScrollBox`: lists that may overflow.
- `HorizontalBox`/`VerticalBox`: repeated controls inside a local group when absolute positions are unnecessary.
- `Overlay`: stacked content inside a button/card when several children share the same bounds.

For project-specific widgets such as `WHQButton`, `LongPressButton`, `TkListView`, or `TkScrollBox`, resolve by class name when possible and gracefully fall back to standard widgets if missing.

## Visual Reconstruction Policy

For screenshots:

1. Separate background/3D/art from functional UI.
2. Put background/3D/art into one `BGLayer` image or engine-scene placeholder.
3. Put interactive widgets into `FunctionLayer`.
4. Group by anchor and purpose rather than by visible art boundaries.
5. Use approximate pixel positions and sizes based on the screenshot's resolution.
6. Use simple colors to mark intended visual roles, but do not spend widget count on texture detail.

## Troubleshooting

- If `KismetEditorUtilities` is missing, try `BlueprintEditorLibrary.compile_blueprint`. If no compile helper exists, save the duplicated asset anyway.
- If `unreal.WidgetTree` is missing, do not import or reference it. Use generic UObject lookup.
- If adding a child fails for a complex panel, fall back to a `CanvasPanel` or `Border` placeholder with a text label.
- If a custom/project widget class cannot be resolved, log a warning and substitute a close standard widget only when the user cares about overall layout more than class fidelity.
- Always end generated scripts with an unconditional `main()` call so both commandlet and in-editor execution create the asset.
