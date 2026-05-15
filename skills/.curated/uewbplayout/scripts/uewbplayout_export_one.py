from __future__ import annotations

from datetime import datetime
from pathlib import Path
import traceback

import unreal


TARGET_WIDGET_BLUEPRINT = globals().get("TARGET_WIDGET_BLUEPRINT", (
    "/Script/UMGEditor.WidgetBlueprint'"
    "/Game/UI/Widgets/BattleScreen/BP_BattleScreen.BP_BattleScreen'"
))
REPORT_SUBDIR = Path("Content") / "Python" / "WidgetTools" / "Reports"
REPORT_NAME = globals().get("REPORT_NAME", "BP_BattleScreen_widget_hierarchy.md")
ALLOW_LIVE_WIDGET_INSTANCE_FALLBACK = bool(globals().get("ALLOW_LIVE_WIDGET_INSTANCE_FALLBACK", False))
TARGET_ROOT_WIDGET_NAME = globals().get("TARGET_ROOT_WIDGET_NAME", "CanvasPanel_366")


def target_root_widget_names() -> list[str]:
    names = globals().get("TARGET_ROOT_WIDGET_NAMES", None)
    if names is None:
        names = TARGET_ROOT_WIDGET_NAME
    if isinstance(names, str):
        return [name.strip() for name in names.split(",") if name.strip()]
    try:
        return [str(name).strip() for name in names if str(name).strip()]
    except Exception:
        return []


def log(message: str) -> None:
    unreal.log(f"[WidgetHierarchyExport] {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"[WidgetHierarchyExport] {message}")


def normalize_object_path(object_path: str) -> str:
    value = str(object_path).strip()
    if "'" in value:
        value = value.split("'", 1)[1].rsplit("'", 1)[0]
    return value


def asset_name_from_path(object_path: str) -> str:
    object_path = normalize_object_path(object_path)
    return object_path.rsplit("/", 1)[-1].split(".", 1)[0]


def package_name_from_path(object_path: str) -> str:
    object_path = normalize_object_path(object_path)
    return object_path.split(".", 1)[0]


def generated_class_path_from_path(object_path: str) -> str:
    clean_path = normalize_object_path(object_path)
    if clean_path.endswith("_C"):
        return clean_path
    return f"{clean_path}_C"


def load_asset(object_path: str) -> unreal.Object:
    clean_path = normalize_object_path(object_path)

    for loader in (
        lambda path: unreal.EditorAssetLibrary.load_asset(path),
        lambda path: unreal.load_object(None, path),
        lambda path: unreal.load_object(None, package_name_from_path(path)),
    ):
        try:
            asset = loader(clean_path)
            if asset:
                return asset
        except Exception:
            pass

    raise RuntimeError(f"Could not load WidgetBlueprint asset: {object_path}")


def try_get_editor_property(obj: object, property_name: str):
    if obj is None:
        return None
    try:
        value = obj.get_editor_property(property_name)
        if value is not None:
            return value
    except Exception:
        pass

    try:
        value = getattr(obj, property_name)
        if callable(value):
            value = value()
        return value
    except Exception:
        return None


def try_call(obj: object, method_name: str):
    if obj is None or not hasattr(obj, method_name):
        return None
    try:
        return getattr(obj, method_name)()
    except Exception:
        return None


def try_call_with_args(obj: object, method_name: str, *args):
    if obj is None or not hasattr(obj, method_name):
        return None
    try:
        return getattr(obj, method_name)(*args)
    except Exception:
        return None


def get_default_object(class_obj: object):
    try:
        default_object = unreal.get_default_object(class_obj)
        if default_object:
            return default_object
    except Exception:
        pass

    return try_call(class_obj, "get_default_object")


def get_editor_world():
    subsystem_class = getattr(unreal, "UnrealEditorSubsystem", None)
    if subsystem_class:
        try:
            subsystem = unreal.get_editor_subsystem(subsystem_class)
            world = try_call(subsystem, "get_editor_world")
            if world:
                return world
        except Exception:
            pass

    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    world = try_call(editor_level_library, "get_editor_world")
    if world:
        return world

    return None


def get_player_controller(world: unreal.Object):
    gameplay_statics = getattr(unreal, "GameplayStatics", None)
    if gameplay_statics and world:
        controller = try_call_with_args(gameplay_statics, "get_player_controller", world, 0)
        if controller:
            return controller
    return None


def create_live_widget_instance(object_path: str):
    widget_class = None
    try:
        widget_class = unreal.load_class(None, generated_class_path_from_path(object_path))
    except Exception:
        widget_class = None
    if not widget_class:
        return None, "could not load generated widget class"

    world = get_editor_world()
    if not world:
        return None, "no editor world is available"

    player_controller = get_player_controller(world)
    widget_blueprint_library = getattr(unreal, "WidgetBlueprintLibrary", None)
    create_method = getattr(widget_blueprint_library, "create", None) if widget_blueprint_library else None
    if callable(create_method):
        for args in (
            (world, widget_class, player_controller),
            (world, widget_class, None),
            (player_controller, widget_class),
            (world, widget_class),
        ):
            try:
                widget = create_method(*args)
                if widget:
                    return widget, "WidgetBlueprintLibrary.create"
            except Exception:
                pass

    module_create_widget = getattr(unreal, "create_widget", None)
    if callable(module_create_widget):
        for args in (
            (world, widget_class, player_controller),
            (world, widget_class),
            (player_controller, widget_class),
        ):
            try:
                widget = module_create_widget(*args)
                if widget:
                    return widget, "unreal.create_widget"
            except Exception:
                pass

    return None, "no available Python CreateWidget API accepted the generated class"


def try_get_live_widget_tree(object_path: str):
    if not ALLOW_LIVE_WIDGET_INSTANCE_FALLBACK:
        return None, None, "live widget instance fallback is disabled"

    widget, source = create_live_widget_instance(object_path)
    if not widget:
        return None, None, source

    # CreateWidget normally initializes the instance. These calls are best-effort
    # probes for editor builds that defer WidgetTree construction.
    for method_name in ("initialize", "rebuild_widget", "force_layout_prepass"):
        try_call(widget, method_name)

    widget_tree = try_get_editor_property(widget, "widget_tree")
    if widget_tree:
        return widget_tree, widget, f"live widget instance via {source}"

    return None, widget, f"live widget instance via {source}, but widget_tree was not readable"


def find_inner_object(outer: unreal.Object, object_name: str):
    for finder in (unreal.find_object, unreal.load_object):
        try:
            found = finder(outer, object_name)
            if found:
                return found
        except Exception:
            pass
    return None


def find_named_widget(widget_tree: unreal.Object, widget_name: str):
    if not widget_tree or not widget_name:
        return None

    for method_name in ("find_widget", "find_widget_by_name"):
        found = try_call_with_args(widget_tree, method_name, widget_name)
        if found:
            return found

    found = find_inner_object(widget_tree, widget_name)
    if found:
        return found

    try:
        tree_path = widget_tree.get_path_name()
    except Exception:
        tree_path = None

    if tree_path:
        for candidate in (f"{tree_path}.{widget_name}", f"{tree_path}/{widget_name}"):
            try:
                found = unreal.load_object(None, candidate)
                if found:
                    return found
            except Exception:
                pass

    return None


def get_widget_tree(widget_blueprint: unreal.Object, object_path: str):
    widget_tree = try_get_editor_property(widget_blueprint, "widget_tree")
    if widget_tree:
        return widget_tree

    asset_name = asset_name_from_path(object_path)
    for inner_name in ("WidgetTree", f"{asset_name}:WidgetTree"):
        widget_tree = find_inner_object(widget_blueprint, inner_name)
        if widget_tree:
            return widget_tree

    clean_path = normalize_object_path(object_path)
    for candidate in (f"{clean_path}:WidgetTree", f"{clean_path}.WidgetTree"):
        try:
            widget_tree = unreal.load_object(None, candidate)
            if widget_tree:
                return widget_tree
        except Exception:
            pass

    generated_class = try_get_editor_property(widget_blueprint, "generated_class")
    class_default_object = get_default_object(generated_class)
    widget_tree = try_get_editor_property(class_default_object, "widget_tree")
    if widget_tree:
        return widget_tree

    widget_class = try_call(widget_blueprint, "get_class")
    class_default_object = get_default_object(widget_class)
    widget_tree = try_get_editor_property(class_default_object, "widget_tree")
    if widget_tree:
        return widget_tree

    try:
        compiled_class = unreal.load_class(None, generated_class_path_from_path(object_path))
    except Exception:
        compiled_class = None
    class_default_object = get_default_object(compiled_class)
    widget_tree = try_get_editor_property(class_default_object, "widget_tree")
    if widget_tree:
        return widget_tree

    raise RuntimeError(f"Could not find WidgetTree inside {clean_path}")


def get_root_widget(widget_tree: unreal.Object):
    for property_name in ("root_widget", "RootWidget"):
        root = try_get_editor_property(widget_tree, property_name)
        if root:
            return root

    for method_name in ("get_root_widget",):
        root = try_call(widget_tree, method_name)
        if root:
            return root

    for root_widget_name in target_root_widget_names():
        named_root = find_named_widget(widget_tree, root_widget_name)
        if named_root:
            return named_root

    return None


def get_object_name(obj: object) -> str:
    if obj is None:
        return "None"
    try:
        return obj.get_name()
    except Exception:
        return str(obj)


def get_class_name(obj: object) -> str:
    if obj is None:
        return "None"
    try:
        return obj.get_class().get_name()
    except Exception:
        return type(obj).__name__


def format_unreal_object(obj: unreal.Object) -> str:
    try:
        return obj.get_path_name()
    except Exception:
        return get_object_name(obj)


def format_value(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, unreal.Object):
        return format_unreal_object(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(format_value(item) for item in value) + "]"

    class_name = get_class_name(value)
    if class_name in ("Vector2D", "IntPoint"):
        x = try_get_editor_property(value, "x")
        y = try_get_editor_property(value, "y")
        return f"({x}, {y})"
    if class_name == "Margin":
        parts = []
        for property_name in ("left", "top", "right", "bottom"):
            parts.append(f"{property_name}={try_get_editor_property(value, property_name)}")
        return ", ".join(parts)
    if class_name == "Anchors":
        minimum = try_get_editor_property(value, "minimum")
        maximum = try_get_editor_property(value, "maximum")
        return f"min={format_value(minimum)}, max={format_value(maximum)}"
    if class_name == "AnchorData":
        parts = []
        for property_name in ("anchors", "offsets", "alignment"):
            item = try_get_editor_property(value, property_name)
            if item is not None:
                parts.append(f"{property_name}={format_value(item)}")
        return ", ".join(parts)
    if class_name in ("LinearColor", "SlateColor"):
        return str(value)
    if class_name == "SlateBrush":
        parts = []
        for property_name in ("draw_as", "image_size", "resource_object", "tint_color"):
            item = try_get_editor_property(value, property_name)
            if item is not None:
                parts.append(f"{property_name}={format_value(item)}")
        return ", ".join(parts) if parts else str(value)

    return str(value)


def collect_properties(obj: object, property_names: list[str]) -> list[tuple[str, str]]:
    result = []
    for property_name in property_names:
        value = try_get_editor_property(obj, property_name)
        if value is not None:
            result.append((property_name, format_value(value)))
    return result


def collect_widget_properties(widget: unreal.Object) -> list[tuple[str, str]]:
    property_names = [
        "visibility",
        "is_enabled",
        "render_opacity",
        "render_transform",
        "render_transform_pivot",
        "clipping",
        "tool_tip_text",
        "text",
        "hint_text",
        "content_text",
        "brush",
        "image",
        "color_and_opacity",
        "foreground_color",
        "font",
        "justification",
        "orientation",
    ]
    return collect_properties(widget, property_names)


def collect_slot_properties(widget: unreal.Object) -> list[tuple[str, str]]:
    slot = try_get_editor_property(widget, "slot")
    if not slot:
        return []

    result = [("slot_class", get_class_name(slot))]
    slot_properties = [
        "layout_data",
        "anchors",
        "offsets",
        "alignment",
        "auto_size",
        "z_order",
        "padding",
        "horizontal_alignment",
        "vertical_alignment",
        "size",
        "size_rule",
        "value",
        "row",
        "column",
        "row_span",
        "column_span",
        "layer",
    ]
    result.extend(collect_properties(slot, slot_properties))

    for method_name, label in (
        ("get_position", "position"),
        ("get_size", "size"),
        ("get_alignment", "alignment"),
        ("get_anchors", "anchors"),
        ("get_z_order", "z_order"),
        ("get_auto_size", "auto_size"),
    ):
        value = try_call(slot, method_name)
        if value is not None and not any(existing_label == label for existing_label, _ in result):
            result.append((label, format_value(value)))

    return result


def get_children(widget: unreal.Object) -> list[unreal.Object]:
    children = []

    try:
        child_count = widget.get_children_count()
        for index in range(child_count):
            child = widget.get_child_at(index)
            if child:
                children.append(child)
    except Exception:
        pass

    if not children:
        for method_name in ("get_content", "get_child"):
            child = try_call(widget, method_name)
            if child:
                children.append(child)

    return children


def get_all_widgets(widget_tree: unreal.Object) -> list[unreal.Object]:
    for method_name in ("get_all_widgets", "get_all_widgets_and_descendants"):
        widgets = try_call(widget_tree, method_name)
        if widgets:
            return list(widgets)
    return []


def flatten_widget_subtree(widget: unreal.Object, visited: set[str] | None = None) -> list[unreal.Object]:
    if not widget:
        return []
    if visited is None:
        visited = set()

    widget_path = format_unreal_object(widget)
    if widget_path in visited:
        return []
    visited.add(widget_path)

    widgets = [widget]
    for child in get_children(widget):
        widgets.extend(flatten_widget_subtree(child, visited))
    return widgets


def infer_root_widgets(widget_tree: unreal.Object) -> list[unreal.Object]:
    root_widget = get_root_widget(widget_tree)
    if root_widget:
        return [root_widget]

    all_widgets = get_all_widgets(widget_tree)
    if not all_widgets:
        return []

    child_paths = set()
    for widget in all_widgets:
        for child in get_children(widget):
            child_paths.add(format_unreal_object(child))

    roots = [widget for widget in all_widgets if format_unreal_object(widget) not in child_paths]
    if roots:
        return sorted(roots, key=lambda item: (get_class_name(item) != "CanvasPanel", get_object_name(item)))

    return [all_widgets[0]]


def append_widget_block(lines: list[str], widget: unreal.Object, depth: int, visited: set[str]) -> None:
    widget_path = format_unreal_object(widget)
    if widget_path in visited:
        lines.append(f"{'  ' * depth}- {get_object_name(widget)} [{get_class_name(widget)}] (already listed)")
        return
    visited.add(widget_path)

    indent = "  " * depth
    lines.append(f"{indent}- **{get_object_name(widget)}** `{get_class_name(widget)}`")

    slot_properties = collect_slot_properties(widget)
    if slot_properties:
        lines.append(f"{indent}  - layout:")
        for key, value in slot_properties:
            lines.append(f"{indent}    - `{key}`: {value}")

    widget_properties = collect_widget_properties(widget)
    if widget_properties:
        lines.append(f"{indent}  - properties:")
        for key, value in widget_properties:
            lines.append(f"{indent}    - `{key}`: {value}")

    children = get_children(widget)
    if children:
        lines.append(f"{indent}  - children:")
        for child in children:
            append_widget_block(lines, child, depth + 2, visited)


def collect_asset_dependencies(object_path: str) -> list[str]:
    package_name = package_name_from_path(object_path)
    try:
        registry = unreal.AssetRegistryHelpers.get_asset_registry()
    except Exception:
        return []

    dependency_options = None
    try:
        dependency_options = unreal.AssetRegistryDependencyOptions()
        for property_name in (
            "include_hard_package_references",
            "include_soft_package_references",
            "include_hard_management_references",
            "include_soft_management_references",
            "include_searchable_names",
        ):
            try:
                dependency_options.set_editor_property(property_name, property_name != "include_searchable_names")
            except Exception:
                pass
    except Exception:
        dependency_options = None

    for args in ((package_name, dependency_options), (package_name,)):
        try:
            dependencies = registry.get_dependencies(*args)
            return sorted({str(item) for item in dependencies})
        except Exception:
            pass

    return []


def collect_bound_widget_fields(owner: object) -> list[tuple[str, str]]:
    if not owner:
        return []

    fields = []
    for name in dir(owner):
        lowered = name.lower()
        if "widget" not in lowered:
            continue
        if name.startswith("__"):
            continue
        try:
            value = getattr(owner, name)
            if callable(value):
                continue
            fields.append((name, format_value(value)))
        except Exception as exc:
            fields.append((name, f"<unreadable: {type(exc).__name__}: {exc}>"))

    return sorted(fields, key=lambda item: item[0])


def describe_execution_context() -> str:
    if ALLOW_LIVE_WIDGET_INSTANCE_FALLBACK:
        return "full Editor Python with live widget instance fallback enabled"
    return "commandlet or asset-only Python"


def describe_tree_probe(widget_tree: object) -> list[str]:
    if not widget_tree:
        return ["- WidgetTree object: `None`"]

    all_widgets = get_all_widgets(widget_tree)
    root_widget = get_root_widget(widget_tree)
    return [
        f"- WidgetTree object: `{format_value(widget_tree)}`",
        f"- WidgetTree class: `{get_class_name(widget_tree)}`",
        f"- Root widget probe: `{format_value(root_widget)}`",
        f"- All widgets probe count: `{len(all_widgets)}`",
        f"- Has `get_all_widgets`: `{hasattr(widget_tree, 'get_all_widgets')}`",
        f"- Has `get_all_widgets_and_descendants`: `{hasattr(widget_tree, 'get_all_widgets_and_descendants')}`",
    ]


def build_unavailable_tree_report(object_path: str, reason: str) -> str:
    clean_path = normalize_object_path(object_path)
    asset = None
    try:
        asset = load_asset(clean_path)
    except Exception:
        pass

    compiled_class = None
    compiled_cdo = None
    try:
        compiled_class = unreal.load_class(None, generated_class_path_from_path(clean_path))
        compiled_cdo = get_default_object(compiled_class)
    except Exception:
        pass

    lines = [
        f"# {asset_name_from_path(clean_path)} Widget Hierarchy",
        "",
        f"- Source asset: `{clean_path}`",
        f"- Asset class: `{get_class_name(asset)}`",
        f"- Compiled class: `{format_value(compiled_class)}`",
        f"- Execution context: `{describe_execution_context()}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## Widget Tree",
        "",
        "The WidgetTree could not be walked from this Python context. For this asset, Unreal either exposes the designer WidgetTree as protected or returns a tree with no readable root/widgets.",
        "",
        "Reason:",
        "",
        "```text",
        reason.strip(),
        "```",
        "",
        "## WidgetTree Probe",
        "",
    ]

    widget_tree = None
    if asset:
        try:
            widget_tree = get_widget_tree(asset, clean_path)
        except Exception:
            widget_tree = None
    lines.extend(describe_tree_probe(widget_tree))
    lines.extend(["", "## Bound Widget Fields", ""])

    fields = collect_bound_widget_fields(compiled_cdo)
    if fields:
        for name, value in fields:
            lines.append(f"- `{name}`: {value}")
    else:
        lines.append("- No readable bound widget fields found.")

    lines.extend(["", "## Referenced Assets", ""])
    dependencies = collect_asset_dependencies(clean_path)
    if dependencies:
        lines.extend(f"- `{dependency}`" for dependency in dependencies)
    else:
        lines.append("- No dependencies found through AssetRegistry, or dependency lookup is unavailable.")

    lines.append("")
    return "\n".join(lines)


def resolve_widget_tree_for_report(clean_path: str, asset: unreal.Object):
    errors = []

    try:
        widget_tree = get_widget_tree(asset, clean_path)
        all_widgets = get_all_widgets(widget_tree)
        root_widgets = infer_root_widgets(widget_tree)
        if root_widgets:
            if not all_widgets:
                all_widgets = flatten_widget_subtree(root_widgets[0])
            return widget_tree, root_widgets, all_widgets, "asset designer WidgetTree", None
        errors.append("asset WidgetTree was found, but no readable root/widgets were exposed")
    except Exception as exc:
        widget_tree = None
        errors.append(f"asset WidgetTree probe failed: {type(exc).__name__}: {exc}")

    if ALLOW_LIVE_WIDGET_INSTANCE_FALLBACK:
        try:
            live_tree, live_widget, live_source = try_get_live_widget_tree(clean_path)
            if live_tree:
                all_widgets = get_all_widgets(live_tree)
                root_widgets = infer_root_widgets(live_tree)
                if root_widgets:
                    if not all_widgets:
                        all_widgets = flatten_widget_subtree(root_widgets[0])
                    return live_tree, root_widgets, all_widgets, live_source, live_widget
                errors.append(f"{live_source} returned a WidgetTree, but no readable root/widgets were exposed")
            else:
                errors.append(f"live widget fallback failed: {live_source}")
        except Exception as exc:
            errors.append(f"live widget fallback raised {type(exc).__name__}: {exc}")
    else:
        errors.append("live widget instance fallback is disabled")

    raise RuntimeError(f"WidgetTree has no accessible root widgets: {clean_path}\n" + "\n".join(errors))


def build_report(object_path: str) -> str:
    clean_path = normalize_object_path(object_path)
    asset = load_asset(clean_path)
    widget_tree, root_widgets, all_widgets, tree_source, live_widget = resolve_widget_tree_for_report(clean_path, asset)

    root_names = ", ".join(f"{get_object_name(widget)} `{get_class_name(widget)}`" for widget in root_widgets)
    visited: set[str] = set()
    lines = [
        f"# {asset_name_from_path(clean_path)} Widget Hierarchy",
        "",
        f"- Source asset: `{clean_path}`",
        f"- Asset class: `{get_class_name(asset)}`",
        f"- WidgetTree: `{format_unreal_object(widget_tree)}`",
        f"- WidgetTree source: `{tree_source}`",
        f"- Live widget instance: `{format_value(live_widget)}`",
        f"- Execution context: `{describe_execution_context()}`",
        f"- Root widget(s): {root_names}",
        f"- Widget count: `{len(all_widgets)}`",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        "",
        "## Referenced Assets",
        "",
    ]

    dependencies = collect_asset_dependencies(clean_path)
    if dependencies:
        lines.extend(f"- `{dependency}`" for dependency in dependencies)
    else:
        lines.append("- No dependencies found through AssetRegistry, or dependency lookup is unavailable.")

    lines.extend(["", "## Widget Tree", ""])
    for root_widget in root_widgets:
        append_widget_block(lines, root_widget, 0, visited)

    unlisted_widgets = []
    for widget in all_widgets:
        widget_path = format_unreal_object(widget)
        if widget_path not in visited:
            unlisted_widgets.append(widget)

    if unlisted_widgets:
        lines.extend(["", "## Unparented Widgets", ""])
        for widget in unlisted_widgets:
            append_widget_block(lines, widget, 0, visited)

    lines.append("")
    return "\n".join(lines)


def write_report(markdown: str) -> Path:
    report_dir = Path(unreal.Paths.project_dir()).resolve() / REPORT_SUBDIR
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / REPORT_NAME
    report_path.write_text(markdown, encoding="utf-8")
    return report_path


def main() -> None:
    try:
        report = build_report(TARGET_WIDGET_BLUEPRINT)
    except Exception:
        report = build_unavailable_tree_report(TARGET_WIDGET_BLUEPRINT, traceback.format_exc())
    report_path = write_report(report)
    log(f"Wrote widget hierarchy report: {report_path}")


if __name__ == "__main__":
    main()
