from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import time
import traceback

import unreal


TARGET = os.environ.get("UEDUMPMAT_TARGET", "").strip()
OUTPUT_ROOT = Path(os.environ.get("UEDUMPMAT_OUTPUT_ROOT", "Content/Python/MaterialDump"))
SHADER_KEYWORDS = [
    item.strip()
    for item in os.environ.get("UEDUMPMAT_SHADER_KEYWORDS", "BasePassPixelShader,BasePass").split(",")
    if item.strip()
]
RECURSIVE = os.environ.get("UEDUMPMAT_RECURSIVE", "1").strip().lower() not in {"0", "false", "no"}
MAX_SHADER_COPIES = int(os.environ.get("UEDUMPMAT_MAX_SHADER_COPIES", "24"))
WAIT_SECONDS = float(os.environ.get("UEDUMPMAT_WAIT_SECONDS", "45"))
DEBUG = os.environ.get("UEDUMPMAT_DEBUG", "0") == "1"


MATERIAL_PROPERTY_NAMES = [
    "material_domain",
    "blend_mode",
    "shading_model",
    "two_sided",
    "dithered_lod_transition",
    "use_material_attributes",
    "opacity_mask_clip_value",
    "num_customized_u_vs",
    "phys_material",
    "subsurface_profile",
    "b_used_with_skeletal_mesh",
    "b_used_with_static_lighting",
    "b_used_with_instanced_static_meshes",
    "b_used_with_niagara_sprites",
    "b_used_with_niagara_mesh_particles",
]

EXPRESSION_PROPERTY_NAMES = [
    "desc",
    "parameter_name",
    "group",
    "sort_priority",
    "default_value",
    "default_value_r",
    "default_value_g",
    "default_value_b",
    "default_value_a",
    "texture",
    "sampler_type",
    "const_coordinate",
    "material_expression_editor_x",
    "material_expression_editor_y",
    "node_pos_x",
    "node_pos_y",
    "coordinates",
    "a",
    "b",
    "r",
    "g",
    "alpha",
    "base_color",
    "metallic",
    "specular",
    "roughness",
    "emissive_color",
    "opacity",
    "opacity_mask",
    "normal",
    "world_position_offset",
]


def log(message: str) -> None:
    unreal.log(f"[UEDumpMat] {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"[UEDumpMat] {message}")


def normalize_object_path(value: str) -> str:
    text = str(value).strip()
    if "'" in text:
        text = text.split("'", 1)[1].rsplit("'", 1)[0]
    return text


def asset_name_from_path(value: str) -> str:
    clean = normalize_object_path(value).rstrip("/")
    return clean.rsplit("/", 1)[-1].split(".", 1)[0] or "MaterialDump"


def safe_name(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return result or "MaterialDump"


def object_label(value: object) -> str:
    if value is None:
        return "None"
    for method_name in ("get_path_name", "get_name"):
        method = getattr(value, method_name, None)
        if callable(method):
            try:
                return str(method())
            except Exception:
                pass
    return str(value)


def get_class_name(value: object) -> str:
    try:
        return str(value.get_class().get_name())
    except Exception:
        return value.__class__.__name__


def try_get_editor_property(obj: object, name: str):
    try:
        return obj.get_editor_property(name), True
    except Exception:
        return None, False


def try_call(obj: object, name: str, *args):
    method = getattr(obj, name, None)
    if not callable(method):
        return None, False
    try:
        return method(*args), True
    except Exception:
        return None, False


def format_value(value: object, depth: int = 0) -> str:
    if value is None:
        return "`None`"
    if isinstance(value, bool):
        return "`true`" if value else "`false`"
    if isinstance(value, (int, float)):
        return f"`{value}`"
    if isinstance(value, str):
        text = value.replace("\r", " ").replace("\n", " ").strip()
        return f"`{text}`" if len(text) <= 100 else f"`{text[:97]}...`"
    if depth >= 2:
        return f"`{object_label(value)}`"
    if isinstance(value, (list, tuple)):
        if not value:
            return "`[]`"
        items = [format_value(item, depth + 1) for item in list(value)[:10]]
        if len(value) > 10:
            items.append(f"`... {len(value) - 10} more`")
        return ", ".join(items)
    if isinstance(value, dict):
        if not value:
            return "`{}`"
        parts = []
        for index, (key, item) in enumerate(value.items()):
            if index >= 10:
                parts.append(f"`... {len(value) - 10} more`")
                break
            parts.append(f"{key}: {format_value(item, depth + 1)}")
        return "; ".join(parts)
    return f"`{object_label(value)}`"


def markdown_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return ["_None found._", ""]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        escaped = [str(cell).replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    lines.append("")
    return lines


def load_asset(path: str):
    clean = normalize_object_path(path)
    candidates = [clean]
    if clean.startswith("/Game/") and "." not in clean.rsplit("/", 1)[-1]:
        candidates.append(f"{clean}.{clean.rsplit('/', 1)[-1]}")
    for candidate in candidates:
        for loader in (
            lambda item: unreal.EditorAssetLibrary.load_asset(item),
            lambda item: unreal.load_object(None, item),
        ):
            try:
                asset = loader(candidate)
                if asset:
                    return asset
            except Exception:
                pass
    return None


def is_material_asset(asset: object) -> bool:
    class_name = get_class_name(asset)
    return class_name == "Material" or class_name.startswith("MaterialInstance")


def list_materials_in_folder(folder_path: str) -> list[object]:
    assets = []
    for asset_path in unreal.EditorAssetLibrary.list_assets(folder_path, RECURSIVE, False):
        asset = load_asset(str(asset_path))
        if asset and is_material_asset(asset):
            assets.append(asset)
    return unique_assets(assets)


def unique_assets(assets: list[object]) -> list[object]:
    unique = []
    seen = set()
    for asset in assets:
        key = object_label(asset)
        if key in seen:
            continue
        seen.add(key)
        unique.append(asset)
    return unique


def resolve_targets() -> tuple[str, list[object]]:
    if not TARGET:
        raise RuntimeError("Set UEDUMPMAT_TARGET to a material object path or /Game folder.")
    all_assets = []
    target_parts = [part.strip() for part in TARGET.split(";") if part.strip()]
    output_slug_source = target_parts[0] if len(target_parts) == 1 else "MultipleMaterials"
    for raw_target in target_parts:
        clean = normalize_object_path(raw_target).rstrip("/")
        try:
            is_directory = unreal.EditorAssetLibrary.does_directory_exist(clean)
        except Exception:
            is_directory = False
        if is_directory:
            all_assets.extend(list_materials_in_folder(clean))
            continue
        asset = load_asset(clean)
        if not asset:
            warn(f"Could not load target: {raw_target}")
            continue
        if is_material_asset(asset):
            all_assets.append(asset)
        else:
            warn(f"Skipping non-material asset: {object_label(asset)} ({get_class_name(asset)})")
    return safe_name(asset_name_from_path(output_slug_source)), unique_assets(all_assets)


def project_relative(project_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(project_dir.resolve()))
    except Exception:
        return str(path)


def collect_named_properties(obj: object, names: list[str]) -> list[tuple[str, object]]:
    rows = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        value, ok = try_get_editor_property(obj, name)
        if ok and value is not None:
            rows.append((name, value))
    return rows


def get_objects_with_outer_safe(outer: object) -> list[object]:
    getter = getattr(unreal, "get_objects_with_outer", None)
    if not callable(getter):
        return []
    for args in ((outer, True), (outer, False), (outer,)):
        try:
            values = getter(*args)
            if values:
                return list(values)
        except Exception:
            pass
    return []


def is_material_expression_object(obj: object) -> bool:
    return get_class_name(obj).startswith("MaterialExpression")


def get_material_expressions(material: object) -> list[object]:
    expressions = []
    library = getattr(unreal, "MaterialEditingLibrary", None)
    if library:
        count, ok = try_call(library, "get_num_material_expressions", material)
        if ok and isinstance(count, int):
            for index in range(count):
                expression, expression_ok = try_call(library, "get_material_expression", material, index)
                if expression_ok and expression:
                    expressions.append(expression)
            if expressions:
                return expressions
    for property_name in ("expressions", "editor_comments"):
        value, ok = try_get_editor_property(material, property_name)
        if ok and value:
            return [item for item in value if item]
    return [obj for obj in get_objects_with_outer_safe(material) if is_material_expression_object(obj)]


def get_node_position(expression: object) -> str:
    for x_name, y_name in (
        ("material_expression_editor_x", "material_expression_editor_y"),
        ("node_pos_x", "node_pos_y"),
    ):
        x, ok_x = try_get_editor_property(expression, x_name)
        y, ok_y = try_get_editor_property(expression, y_name)
        if ok_x or ok_y:
            return f"{x if ok_x else '?'} , {y if ok_y else '?'}"
    return "unknown"


def get_expression_inputs(expression: object) -> list[tuple[str, object]]:
    inputs = []
    library = getattr(unreal, "MaterialEditingLibrary", None)
    value, ok = try_call(library, "get_inputs_for_material_expression", expression) if library else (None, False)
    if ok and value:
        for index, item in enumerate(value):
            name, name_ok = try_get_editor_property(item, "input_name")
            inputs.append((str(name) if name_ok and name else f"Input {index}", item))
    for property_name in EXPRESSION_PROPERTY_NAMES:
        input_obj, prop_ok = try_get_editor_property(expression, property_name)
        if not prop_ok or input_obj is None:
            continue
        linked, linked_ok = try_get_editor_property(input_obj, "expression")
        if linked_ok:
            inputs.append((property_name, input_obj))
    return inputs


def normalize_parameter_names(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, tuple):
        names = []
        for item in value:
            names.extend(normalize_parameter_names(item))
        return names
    try:
        return [str(item) for item in list(value)]
    except Exception:
        return [str(value)]


def get_parameter_rows(material: object, expressions: list[object]) -> list[list[str]]:
    rows = []
    for expression in expressions:
        parameter_name, ok = try_get_editor_property(expression, "parameter_name")
        if not ok or not parameter_name:
            continue
        group, _ = try_get_editor_property(expression, "group")
        default_value, _ = try_get_editor_property(expression, "default_value")
        rows.append([str(parameter_name), get_class_name(expression), str(group or ""), format_value(default_value), object_label(expression)])

    seen = {(row[0], row[1]) for row in rows}
    library = getattr(unreal, "MaterialEditingLibrary", None)
    if library:
        methods = [
            ("Scalar", "get_scalar_parameter_names", "get_material_default_scalar_parameter_value"),
            ("Vector", "get_vector_parameter_names", "get_material_default_vector_parameter_value"),
            ("Texture", "get_texture_parameter_names", "get_material_default_texture_parameter_value"),
            ("Static Switch", "get_static_switch_parameter_names", "get_material_default_static_switch_parameter_value"),
        ]
        for parameter_type, names_method, default_method in methods:
            names, ok = try_call(library, names_method, material)
            if not ok:
                continue
            for parameter_name in normalize_parameter_names(names):
                default_value, default_ok = try_call(library, default_method, material, parameter_name)
                key = (parameter_name, parameter_type)
                if key in seen:
                    continue
                rows.append([
                    parameter_name,
                    parameter_type,
                    "",
                    format_value(default_value) if default_ok else "",
                    "MaterialEditingLibrary",
                ])
                seen.add(key)
    return sorted(rows, key=lambda row: (row[2], row[0], row[1]))


def get_root_input_rows(material: object) -> list[list[str]]:
    rows = []
    library = getattr(unreal, "MaterialEditingLibrary", None)
    material_property_enum = getattr(unreal, "MaterialProperty", None)
    get_input_node = getattr(library, "get_material_property_input_node", None) if library else None
    if not callable(get_input_node) or not material_property_enum:
        return rows
    for attr_name in dir(material_property_enum):
        if not attr_name.startswith("MP_") or attr_name.endswith("MAX"):
            continue
        try:
            node = get_input_node(material, getattr(material_property_enum, attr_name))
            if node:
                rows.append([attr_name, object_label(node)])
        except Exception:
            pass
    return sorted(rows)


def get_used_texture_rows(material: object) -> list[list[str]]:
    library = getattr(unreal, "MaterialEditingLibrary", None)
    if not library:
        return []
    for method_name in ("get_used_textures", "get_used_textures_for_material"):
        textures, ok = try_call(library, method_name, material)
        if ok and textures:
            return [[object_label(texture)] for texture in sorted(textures, key=object_label)]
    return []


def uasset_path_for_material(project_dir: Path, material: object) -> Path | None:
    path = object_label(material).split(".", 1)[0]
    if not path.startswith("/Game/"):
        return None
    return project_dir / "Content" / Path(path[len("/Game/"):] + ".uasset")


def extract_ascii_strings(data: bytes) -> list[str]:
    values = set()
    for raw in re.findall(rb"[ -~]{3,}", data):
        value = raw.decode("utf-8", errors="ignore").strip()
        if value:
            values.add(value)
    return sorted(values)


def get_serialized_symbol_rows(project_dir: Path, material: object) -> list[list[str]]:
    asset_file = uasset_path_for_material(project_dir, material)
    if not asset_file or not asset_file.exists():
        return []
    strings = extract_ascii_strings(asset_file.read_bytes())
    rows = [["Asset File", "", asset_file.name, str(asset_file)]]
    groups = [
        ("Expression Class Symbol", [item for item in strings if item.startswith("MaterialExpression") and ":" not in item and "." not in item]),
        ("Expression Object Ref", [item for item in strings if ":MaterialExpression" in item]),
        ("Asset/Function Symbol", [item for item in strings if item.startswith("/Game/") or item.startswith("MF_") or item.startswith("T_")]),
        ("Parameter-Like Symbol", [
            item for item in strings
            if len(item) <= 64 and any(token in item.lower() for token in ("color", "normal", "rough", "metal", "mask", "emissive", "opacity"))
        ]),
    ]
    for category, values in groups:
        for index, value in enumerate(values[:120], start=1):
            rows.append([category, str(index), "", value])
        if len(values) > 120:
            rows.append([category, "...", "", f"{len(values) - 120} more omitted"])
    return rows


def execute_console(command: str) -> None:
    executor = getattr(getattr(unreal, "SystemLibrary", None), "execute_console_command", None)
    if not callable(executor):
        return
    try:
        executor(None, command)
    except Exception:
        warn(f"Console command failed: {command}")


def enable_shader_debug_dump() -> None:
    for command in (
        "r.ShaderDevelopmentMode 1",
        "r.DumpShaderDebugInfo 1",
        "r.DumpShaderDebugShortNames 1",
        "r.DumpShaderDebugWorkerCommandLine 1",
        "r.ShaderCompiler.DebugDumpJobDiagnostics 1",
        "r.ShaderCompiler.DebugDumpDetailedShaderSource 1",
    ):
        execute_console(command)


def recompile_material_if_possible(material: object) -> bool:
    if get_class_name(material) != "Material":
        return False
    library = getattr(unreal, "MaterialEditingLibrary", None)
    recompile = getattr(library, "recompile_material", None) if library else None
    if not callable(recompile):
        return False
    try:
        recompile(material)
        return True
    except Exception:
        warn(f"Material recompile failed for {object_label(material)}")
        return False


def shader_debug_root(project_dir: Path) -> Path:
    return project_dir / "Saved" / "ShaderDebugInfo"


def material_debug_dirs(project_dir: Path, material_name: str) -> list[Path]:
    root = shader_debug_root(project_dir)
    if not root.exists():
        return []
    prefix = material_name + "_"
    return sorted(
        [path for path in root.rglob("*") if path.is_dir() and path.name.startswith(prefix)],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )


def wait_for_debug_dir(project_dir: Path, material_name: str, start_time: float) -> Path | None:
    deadline = time.time() + WAIT_SECONDS
    best = None
    while time.time() < deadline:
        dirs = material_debug_dirs(project_dir, material_name)
        if dirs:
            best = dirs[0]
            if best.stat().st_mtime >= start_time - 1.0:
                return best
        time.sleep(1.0)
    return best


def source_match_score(path: Path) -> tuple[int, float, str]:
    text = str(path).lower()
    name = path.name.lower()
    score = 0
    for index, keyword in enumerate(SHADER_KEYWORDS):
        if keyword.lower() in text:
            score -= 100 - index
    if name.endswith(".usf"):
        score -= 20
    if "pixelshader" in name:
        score -= 10
    if "vertexshader" in name:
        score -= 5
    if name.startswith("preprocessed_"):
        score += 3
    if name.startswith("stripped_"):
        score += 5
    return score, -path.stat().st_mtime, str(path)


def collect_shader_sources(debug_dir: Path | None) -> list[Path]:
    if not debug_dir or not debug_dir.exists():
        return []
    files = [
        path for path in debug_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".usf", ".ush", ".hlsl", ".txt"}
    ]
    matching = [path for path in files if any(keyword.lower() in str(path).lower() for keyword in SHADER_KEYWORDS)]
    return sorted(matching or files, key=source_match_score)


def copy_shader_sources(project_dir: Path, files: list[Path], dest_dir: Path) -> list[tuple[Path, Path]]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    used = set()
    for source in files[:MAX_SHADER_COPIES]:
        dest_name = safe_name("__".join(source.parts[-6:]))
        if not dest_name:
            dest_name = source.name
        base = dest_name
        index = 2
        while dest_name.lower() in used:
            dest_name = f"{Path(base).stem}_{index}{Path(base).suffix}"
            index += 1
        used.add(dest_name.lower())
        dest = dest_dir / dest_name
        shutil.copy2(source, dest)
        copied.append((source, dest))
    return copied


def capture_hlsl(project_dir: Path, material: object, material_output_dir: Path) -> dict[str, object]:
    material_name = asset_name_from_path(object_label(material))
    start_time = time.time()
    enable_shader_debug_dump()
    recompiled = recompile_material_if_possible(material)
    debug_dir = wait_for_debug_dir(project_dir, material_name, start_time)
    source_files = collect_shader_sources(debug_dir)
    copied = copy_shader_sources(project_dir, source_files, material_output_dir / "Shaders" / material_name)
    return {
        "recompiled": recompiled,
        "debug_dir": debug_dir,
        "sources": copied,
        "primary": copied[0] if copied else None,
    }


def read_preview(path: Path, max_chars: int = 24000) -> tuple[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def build_material_report(project_dir: Path, material: object, hlsl_info: dict[str, object]) -> str:
    material_path = object_label(material)
    material_name = asset_name_from_path(material_path)
    expressions = get_material_expressions(material)
    expression_ids = {object_label(expression): str(index + 1) for index, expression in enumerate(expressions)}

    lines = [
        f"# {material_name} Material Dump",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Asset: `{material_path}`",
        f"- Class: `{get_class_name(material)}`",
        f"- Expression count: `{len(expressions)}`",
        f"- Shader keywords: `{', '.join(SHADER_KEYWORDS)}`",
        "",
        "## Material Properties",
        "",
    ]
    lines.extend(markdown_table(["Property", "Value"], [[name, format_value(value)] for name, value in collect_named_properties(material, MATERIAL_PROPERTY_NAMES)]))

    lines.extend(["## Parameters", ""])
    lines.extend(markdown_table(["Name", "Type", "Group", "Default", "Source"], get_parameter_rows(material, expressions)))

    lines.extend(["## Material Root Inputs", ""])
    lines.extend(markdown_table(["Material Property", "Input Node"], get_root_input_rows(material)))

    lines.extend(["## Expression Nodes", ""])
    node_rows = []
    for expression in expressions:
        label = object_label(expression)
        properties = collect_named_properties(expression, EXPRESSION_PROPERTY_NAMES)
        compact = ", ".join(
            f"{name}={format_value(value)}"
            for name, value in properties
            if name not in {"material_expression_editor_x", "material_expression_editor_y", "node_pos_x", "node_pos_y"}
        )
        node_rows.append([expression_ids.get(label, ""), get_class_name(expression), label, get_node_position(expression), compact])
    lines.extend(markdown_table(["#", "Class", "Object", "Graph Position", "Key Properties"], node_rows))

    lines.extend(["## Node Connections", ""])
    connection_rows = []
    for expression in expressions:
        target_label = object_label(expression)
        for input_name, input_obj in get_expression_inputs(expression):
            linked, ok = try_get_editor_property(input_obj, "expression")
            if not ok or not linked:
                continue
            output_index, _ = try_get_editor_property(input_obj, "output_index")
            masks = []
            for mask_name in ("mask", "mask_r", "mask_g", "mask_b", "mask_a"):
                mask_value, mask_ok = try_get_editor_property(input_obj, mask_name)
                if mask_ok and mask_value:
                    masks.append(mask_name)
            source_label = object_label(linked)
            connection_rows.append([
                expression_ids.get(source_label, ""),
                source_label,
                str(output_index),
                " ".join(masks),
                expression_ids.get(target_label, ""),
                target_label,
                input_name,
            ])
    lines.extend(markdown_table(["From #", "From Node", "Output", "Mask", "To #", "To Node", "Input"], connection_rows))

    lines.extend(["## Used Textures", ""])
    lines.extend(markdown_table(["Texture"], get_used_texture_rows(material)))

    if len(expressions) < 2:
        lines.extend(["## Serialized Asset Symbols", ""])
        lines.extend(markdown_table(["Category", "#", "Class", "Value"], get_serialized_symbol_rows(project_dir, material)))
        lines.extend([
            "## Graph Access Notes",
            "",
            "- Unreal Python exposed zero or partial live expression nodes for this material in commandlet mode.",
            "- Parameter and texture sections are still queried through Unreal editor APIs where available.",
            "- Exact full graph/pin reconstruction may require a small reflected C++ editor helper.",
            "",
        ])

    lines.extend(["## HLSL / Shader Source", ""])
    debug_dir = hlsl_info.get("debug_dir")
    sources = hlsl_info.get("sources") or []
    primary = hlsl_info.get("primary")
    lines.append(f"- Recompile requested: `{bool(hlsl_info.get('recompiled'))}`")
    lines.append(f"- Selected debug directory: `{project_relative(project_dir, debug_dir) if isinstance(debug_dir, Path) else 'None'}`")
    lines.append("")
    lines.extend(markdown_table(
        ["#", "Source", "Copied To", "Bytes"],
        [
            [str(index), project_relative(project_dir, source), project_relative(project_dir, dest), str(dest.stat().st_size)]
            for index, (source, dest) in enumerate(sources, start=1)
        ],
    ))
    if primary:
        source, dest = primary
        preview, truncated = read_preview(dest)
        lines.extend([
            "### Primary HLSL Preview",
            "",
            f"Source: `{project_relative(project_dir, source)}`",
            "",
            "```hlsl",
            preview.rstrip(),
        ])
        if truncated:
            lines.append("")
            lines.append("/* Preview truncated. See copied shader source file for full text. */")
        lines.extend(["```", ""])
    else:
        lines.extend([
            "_No shader source was copied. The material information dump above may still be valid._",
            "",
        ])

    lines.extend([
        "## Notes",
        "",
        "- This report uses Unreal Python reflection where available.",
        "- The HLSL section is generated shader debug source from `Saved/ShaderDebugInfo`, not byte-for-byte UI text from the Material Editor HLSL tab.",
        "- Missing graph nodes or connections are a known Unreal Python exposure limit for some engine versions/assets.",
        "",
    ])
    return "\n".join(lines)


def write_summary(output_dir: Path, rows: list[list[str]]) -> None:
    lines = [
        "# UEDumpMat Summary",
        "",
        f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- Target: `{TARGET}`",
        f"- Shader keywords: `{', '.join(SHADER_KEYWORDS)}`",
        "",
    ]
    lines.extend(markdown_table(["Material", "Status", "Report", "Notes"], rows))
    (output_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    output_slug, materials = resolve_targets()
    output_dir = project_dir / OUTPUT_ROOT / output_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    if not materials:
        write_summary(output_dir, [["", "Failed", "", "No material assets resolved from UEDUMPMAT_TARGET."]])
        raise RuntimeError("No material assets resolved from UEDUMPMAT_TARGET.")

    rows = []
    log(f"Dumping {len(materials)} material(s) to {output_dir}")
    for material in materials:
        material_name = asset_name_from_path(object_label(material))
        report_path = output_dir / f"{safe_name(material_name)}.layout.md"
        try:
            hlsl_info = capture_hlsl(project_dir, material, output_dir)
            report = build_material_report(project_dir, material, hlsl_info)
            report_path.write_text(report, encoding="utf-8")
            rows.append([object_label(material), "OK", project_relative(project_dir, report_path), ""])
            log(f"Wrote report: {report_path}")
        except Exception:
            error = traceback.format_exc()
            rows.append([object_label(material), "Failed", project_relative(project_dir, report_path), error.splitlines()[-1] if error else ""])
            warn(f"Failed dumping {object_label(material)}:\n{error}")

    write_summary(output_dir, rows)
    log(f"Wrote summary: {output_dir / 'summary.md'}")


try:
    main()
except Exception:
    warn("UEDumpMat failed:\n" + traceback.format_exc())
    raise
