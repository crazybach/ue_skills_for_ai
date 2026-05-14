#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


SCRIPT_TEMPLATE = r'''import json
import unreal

SPEC = json.loads(r''' + "'''" + '''__SPEC_JSON__''' + "'''" + r''')


def log(message):
    unreal.log("[UEWBPGen] %s" % message)


def warn(message):
    unreal.log_warning("[UEWBPGen] %s" % message)


def safe_name(name):
    text = "".join(char if char.isalnum() or char == "_" else "_" for char in str(name))
    if text and text[0].isdigit():
        text = "_%s" % text
    return text or "GeneratedWidget"


def asset_name_from_path(asset_path):
    return asset_path.rstrip("/").split("/")[-1]


def asset_folder_from_path(asset_path):
    return "/".join(asset_path.rstrip("/").split("/")[:-1])


def load_class_by_path(script_path):
    try:
        return unreal.load_class(None, script_path)
    except Exception:
        return None


def resolve_widget_class(type_name):
    fallback_map = {
        "Text": "TextBlock",
        "TextBox": "EditableTextBox",
        "ComboBox": "ComboBoxString",
        "Panel": "CanvasPanel",
    }
    type_name = fallback_map.get(type_name, type_name)

    if hasattr(unreal, type_name):
        return getattr(unreal, type_name)

    candidates = [
        "/Script/UMG.%s" % type_name,
        "/Script/CommonUI.%s" % type_name,
        "/Script/CommonGame.%s" % type_name,
        "/Script/AdvancedWidgets.%s" % type_name,
        "/Script/WHQ.%s" % type_name,
        "/Script/Boom.%s" % type_name,
        "/Script/BoomUI.%s" % type_name,
    ]
    for candidate in candidates:
        widget_class = load_class_by_path(candidate)
        if widget_class:
            return widget_class

    return None


def find_inner_object(outer, object_name):
    for fn in (unreal.find_object, unreal.load_object):
        try:
            obj = fn(outer, object_name)
            if obj:
                return obj
        except Exception:
            pass
    return None


def get_widget_tree(widget_blueprint, asset_name, asset_folder):
    try:
        return widget_blueprint.get_editor_property("widget_tree")
    except Exception:
        pass

    for inner_name in ("WidgetTree", "%s:WidgetTree" % asset_name):
        widget_tree = find_inner_object(widget_blueprint, inner_name)
        if widget_tree:
            return widget_tree

    full_asset_path = "%s/%s.%s" % (asset_folder, asset_name, asset_name)
    for object_path in ("%s:WidgetTree" % full_asset_path, "%s.WidgetTree" % full_asset_path):
        try:
            widget_tree = unreal.load_object(None, object_path)
            if widget_tree:
                return widget_tree
        except Exception:
            pass

    raise RuntimeError("Could not find WidgetTree inside %s." % full_asset_path)


def find_root_canvas(widget_tree, root_canvas_name, asset_path):
    root_canvas = find_inner_object(widget_tree, root_canvas_name)
    if root_canvas:
        return root_canvas

    asset_name = asset_name_from_path(asset_path)
    full_asset_path = "%s.%s" % (asset_path, asset_name)
    for object_path in (
        "%s:WidgetTree.%s" % (full_asset_path, root_canvas_name),
        "%s:WidgetTree/%s" % (full_asset_path, root_canvas_name),
        "%s:%s" % (full_asset_path, root_canvas_name),
    ):
        try:
            root_canvas = unreal.load_object(None, object_path)
            if root_canvas:
                return root_canvas
        except Exception:
            pass

    raise RuntimeError("Could not find root canvas named '%s'." % root_canvas_name)


def construct_widget(widget_tree, widget_class, name):
    object_name = safe_name(name)
    if hasattr(widget_tree, "construct_widget"):
        return widget_tree.construct_widget(widget_class, object_name)
    return unreal.new_object(widget_class, outer=widget_tree, name=object_name, base_type=unreal.Widget)


def linear_color(value, default=(1.0, 1.0, 1.0, 1.0)):
    if value is None:
        value = default
    if len(value) == 3:
        value = [value[0], value[1], value[2], 1.0]
    return unreal.LinearColor(float(value[0]), float(value[1]), float(value[2]), float(value[3]))


def set_linear_color_property(widget, property_name, value):
    color = linear_color(value)
    try:
        widget.set_editor_property(property_name, color)
        return True
    except Exception:
        pass
    try:
        widget.set_editor_property(property_name, unreal.SlateColor(color))
        return True
    except Exception:
        return False


def set_text_if_supported(widget, text):
    if text is None:
        return False
    try:
        widget.set_text(str(text))
        return True
    except Exception:
        pass
    for property_name in ("text", "content_text", "hint_text"):
        try:
            widget.set_editor_property(property_name, str(text))
            return True
        except Exception:
            pass
    return False


def set_font_size_if_supported(widget, size):
    if size is None:
        return False
    try:
        font_info = widget.get_editor_property("font")
        font_info.set_editor_property("size", int(size))
        widget.set_editor_property("font", font_info)
        return True
    except Exception:
        return False


def set_slot(slot, slot_spec):
    slot_spec = slot_spec or {}
    x = float(slot_spec.get("x", 0.0))
    y = float(slot_spec.get("y", 0.0))
    w = float(slot_spec.get("w", slot_spec.get("width", 100.0)))
    h = float(slot_spec.get("h", slot_spec.get("height", 40.0)))
    z = int(slot_spec.get("z", slot_spec.get("z_order", 0)))

    try:
        slot.set_position(unreal.Vector2D(x, y))
    except Exception:
        pass
    try:
        slot.set_size(unreal.Vector2D(w, h))
    except Exception:
        pass
    try:
        slot.set_z_order(z)
    except Exception:
        pass

    anchors = slot_spec.get("anchors")
    if anchors:
        try:
            anchor_obj = unreal.Anchors(
                minimum=unreal.Vector2D(float(anchors[0]), float(anchors[1])),
                maximum=unreal.Vector2D(float(anchors[2]), float(anchors[3])),
            )
            slot.set_anchors(anchor_obj)
        except Exception:
            try:
                anchor_obj = unreal.Anchors()
                anchor_obj.set_editor_property("minimum", unreal.Vector2D(float(anchors[0]), float(anchors[1])))
                anchor_obj.set_editor_property("maximum", unreal.Vector2D(float(anchors[2]), float(anchors[3])))
                slot.set_editor_property("anchors", anchor_obj)
            except Exception:
                pass

    alignment = slot_spec.get("alignment")
    if alignment:
        try:
            slot.set_alignment(unreal.Vector2D(float(alignment[0]), float(alignment[1])))
        except Exception:
            try:
                slot.set_editor_property("alignment", unreal.Vector2D(float(alignment[0]), float(alignment[1])))
            except Exception:
                pass


def add_child(parent, child, slot_spec):
    slot = None
    if hasattr(parent, "add_child_to_canvas"):
        slot = parent.add_child_to_canvas(child)
        set_slot(slot, slot_spec)
        return slot
    try:
        return parent.add_child(child)
    except Exception:
        pass
    try:
        return parent.set_content(child)
    except Exception:
        pass
    warn("Could not attach %s to %s" % (child.get_name(), parent.get_name()))
    return None


def make_text_child(widget_tree, parent, text, name, font_size=None, color=None):
    text_class = resolve_widget_class("TextBlock")
    text_widget = construct_widget(widget_tree, text_class, name)
    set_text_if_supported(text_widget, text)
    set_font_size_if_supported(text_widget, font_size)
    if color:
        set_linear_color_property(text_widget, "color_and_opacity", color)
    add_child(parent, text_widget, None)
    return text_widget


def configure_widget(widget_tree, widget, spec):
    widget_type = spec.get("type", "")
    text = spec.get("text")
    set_text_if_supported(widget, text)
    set_font_size_if_supported(widget, spec.get("font_size"))

    if spec.get("color"):
        for prop in ("color_and_opacity", "brush_color", "background_color", "fill_color_and_opacity", "tint_color"):
            set_linear_color_property(widget, prop, spec.get("color"))

    if widget_type == "Button" and text is not None:
        make_text_child(widget_tree, widget, text, "%s_Label" % spec["name"], spec.get("font_size", 18), spec.get("text_color", [1, 1, 1, 1]))

    if widget_type == "CheckBox":
        try:
            state = unreal.CheckBoxState.CHECKED if spec.get("checked", True) else unreal.CheckBoxState.UNCHECKED
            widget.set_checked_state(state)
        except Exception:
            pass

    if widget_type == "ComboBoxString":
        for option in spec.get("options", []):
            try:
                widget.add_option(str(option))
            except Exception:
                pass
        if spec.get("selected") is not None:
            try:
                widget.set_selected_option(str(spec.get("selected")))
            except Exception:
                pass

    if widget_type in ("EditableText", "EditableTextBox", "MultiLineEditableText", "MultiLineEditableTextBox"):
        if spec.get("hint"):
            try:
                widget.set_hint_text(str(spec.get("hint")))
            except Exception:
                pass

    if widget_type in ("ProgressBar", "Slider", "SpinBox") and spec.get("value") is not None:
        for method_name in ("set_percent", "set_value"):
            try:
                getattr(widget, method_name)(float(spec.get("value")))
                break
            except Exception:
                pass


def compile_if_possible(widget_blueprint):
    if hasattr(unreal, "KismetEditorUtilities"):
        unreal.KismetEditorUtilities.compile_blueprint(widget_blueprint)
    elif hasattr(unreal, "BlueprintEditorLibrary"):
        unreal.BlueprintEditorLibrary.compile_blueprint(widget_blueprint)
    else:
        warn("No Python blueprint compile helper is available; saving without compiling.")


def main():
    asset_path = SPEC["asset_path"].rstrip("/")
    asset_name = asset_name_from_path(asset_path)
    asset_folder = asset_folder_from_path(asset_path)
    template_path = SPEC.get("template_asset_path", "/Game/Python/ActorTools/WBP_Python_Template_RootCanvas")
    root_canvas_name = SPEC.get("root_canvas_name", "RootCanvas")

    if not unreal.EditorAssetLibrary.does_asset_exist(template_path):
        raise RuntimeError("Template asset not found: %s" % template_path)

    unreal.EditorAssetLibrary.make_directory(asset_folder)
    duplicated = unreal.EditorAssetLibrary.duplicate_asset(template_path, asset_path)
    if not duplicated:
        raise RuntimeError("Failed to duplicate template %s to %s" % (template_path, asset_path))

    widget_tree = get_widget_tree(duplicated, asset_name, asset_folder)
    root_canvas = find_root_canvas(widget_tree, root_canvas_name, asset_path)

    created = {root_canvas_name: root_canvas}
    skipped = []

    for spec in SPEC.get("widgets", []):
        name = safe_name(spec.get("name", spec.get("type", "Widget")))
        parent_name = spec.get("parent", root_canvas_name)
        parent = created.get(parent_name)
        if not parent:
            skipped.append("%s: parent not found: %s" % (name, parent_name))
            continue

        widget_class = resolve_widget_class(spec.get("type", "CanvasPanel"))
        if not widget_class:
            skipped.append("%s: class not found: %s" % (name, spec.get("type")))
            continue

        try:
            widget = construct_widget(widget_tree, widget_class, name)
            configure_widget(widget_tree, widget, spec)
            add_child(parent, widget, spec.get("slot"))
            created[name] = widget
        except Exception as error:
            skipped.append("%s: %s" % (name, error))

    compile_if_possible(duplicated)
    unreal.EditorAssetLibrary.save_loaded_asset(duplicated)

    log("Generated Widget Blueprint asset: %s" % asset_path)
    if skipped:
        warn("Skipped %d widgets:" % len(skipped))
        for item in skipped:
            warn("  %s" % item)


main()
'''


def asset_name_from_path(asset_path: str) -> str:
    return asset_path.rstrip("/").split("/")[-1]


def normalize_asset_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name.strip())
    if not name.startswith("WBP_"):
        name = "WBP_" + name
    return name


def main() -> None:
    parser = argparse.ArgumentParser(description="Write a per-WBP Unreal Python generator script from a JSON widget spec.")
    parser.add_argument("spec", help="Path to JSON widget spec")
    parser.add_argument("--out-dir", required=True, help="Directory where WBP_Name.py should be written")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output script")
    args = parser.parse_args()

    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    if "asset_path" not in spec:
        raise SystemExit("Spec must include asset_path, for example /Game/Python/ActorTools/WBP_LoginMockup")

    asset_name = normalize_asset_name(asset_name_from_path(spec["asset_path"]))
    asset_folder = "/".join(spec["asset_path"].rstrip("/").split("/")[:-1]) or "/Game/Python/ActorTools"
    spec["asset_path"] = "%s/%s" % (asset_folder, asset_name)

    spec.setdefault("template_asset_path", "/Game/Python/ActorTools/WBP_Python_Template_RootCanvas")
    spec.setdefault("root_canvas_name", "RootCanvas")
    spec.setdefault("screen_size", [1920, 1080])
    spec.setdefault("widgets", [])

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (asset_name + ".py")

    if out_path.exists() and not args.force:
        raise SystemExit("Output script already exists: %s. Use --force to overwrite." % out_path)

    spec_json = json.dumps(spec, indent=2, sort_keys=True)
    script_text = SCRIPT_TEMPLATE.replace("__SPEC_JSON__", spec_json)
    out_path.write_text(script_text, encoding="utf-8")

    print("[UEWBPGen] Wrote %s" % out_path)
    print("[UEWBPGen] Asset path: %s" % spec["asset_path"])


if __name__ == "__main__":
    main()
