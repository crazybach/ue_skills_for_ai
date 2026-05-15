from __future__ import annotations

import os
from pathlib import Path
import re
import traceback

import unreal


TARGET_GAME_PATH = os.environ.get("UEWBPLAYOUT_TARGET_DIR", "/Game/UI/Widgets/Buttons").rstrip("/")
TARGET_CONTENT_DIR = Path("Content") / Path(TARGET_GAME_PATH.removeprefix("/Game/").replace("/", os.sep))
SUMMARY_REPORT_NAME = os.environ.get("UEWBPLAYOUT_SUMMARY_NAME") or (TARGET_GAME_PATH.rsplit("/", 1)[-1] + "_widget_hierarchy_summary.md")
REPORT_SUBDIR = Path("Content") / "Python" / "WidgetTools" / "Reports"
EXPORTER_RELATIVE_PATH = Path(os.environ.get("UEWBPLAYOUT_EXPORTER_RELATIVE_PATH", str(Path("Content") / "Python" / "WidgetTools" / "uewbplayout_export_one.py")))


def log(message: str) -> None:
    unreal.log(f"[WidgetHierarchyBatch] {message}")


def warn(message: str) -> None:
    unreal.log_warning(f"[WidgetHierarchyBatch] {message}")


def load_exporter_namespace(project_dir: Path) -> dict:
    script_path = project_dir / EXPORTER_RELATIVE_PATH
    namespace = {
        "__name__": "__widget_hierarchy_exporter__",
        "__file__": str(script_path),
        "ALLOW_LIVE_WIDGET_INSTANCE_FALLBACK": True,
    }
    source = script_path.read_text(encoding="utf-8")
    exec(compile(source, str(script_path), "exec"), namespace)
    return namespace


def read_asset_strings(asset_file: Path) -> list[str]:
    try:
        data = asset_file.read_bytes()
    except Exception:
        return []

    names = set()
    for match in re.findall(rb"[A-Za-z][A-Za-z0-9_]{2,96}", data):
        try:
            names.add(match.decode("ascii", errors="ignore"))
        except Exception:
            pass
    return sorted(names)


def is_likely_widget_name(name: str) -> bool:
    tokens = (
        "Root",
        "Canvas",
        "Panel",
        "Overlay",
        "InvalidationBox",
        "Button",
        "Image",
        "Border",
        "Box",
        "Progress",
        "Text",
        "ScaleBox",
        "SizeBox",
    )
    if not any(token in name for token in tokens):
        return False
    if name.startswith(("Default__", "MovieScene", "DTransformTrack", "ExecuteUbergraph")):
        return False
    if name in ("CanvasPanel", "CanvasPanelSlot", "ButtonSlot", "PanelSlot", "OverlaySlot"):
        return False
    return True


def candidate_score(name: str) -> tuple[int, str]:
    score = 1000
    if name in ("Root", "RootWidget", "RootCanvas"):
        score = 0
    elif name.startswith("Root"):
        score = 10
    elif name.startswith("InvalidationBox"):
        score = 20
    elif name.startswith("CanvasPanel_"):
        score = 30
    elif name.startswith("CanvasPanel"):
        score = 40
    elif name.endswith("Overlay") or name.startswith("Overlay"):
        score = 50
    elif name.endswith("Panel") or "Panel" in name:
        score = 60
    elif name.endswith("ButtonOverlay"):
        score = 70
    elif "Button" in name:
        score = 80
    elif "Image" in name:
        score = 90
    return score, name


def guess_root_candidates(asset_file: Path) -> list[str]:
    raw_names = read_asset_strings(asset_file)
    candidates = [name for name in raw_names if is_likely_widget_name(name)]
    return sorted(set(candidates), key=candidate_score)


def widget_asset_path(asset_file: Path) -> str:
    stem = asset_file.stem
    return f"/Script/UMGEditor.WidgetBlueprint'{TARGET_GAME_PATH}/{stem}.{stem}'"


def report_name_for_asset(asset_file: Path) -> str:
    return f"{asset_file.stem}_widget_hierarchy.md"


def extract_report_value(markdown: str, prefix: str) -> str:
    for line in markdown.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def parse_widget_count(markdown: str) -> int:
    value = extract_report_value(markdown, "- Widget count").strip("` ")
    try:
        return int(value)
    except Exception:
        return 0


def parse_root_class(root_line: str) -> str:
    match = re.search(r"`([^`]+)`", root_line)
    return match.group(1) if match else ""


def root_class_priority(root_class: str) -> int:
    if root_class in ("InvalidationBox", "CanvasPanel", "Overlay"):
        return 0
    if root_class.endswith("Panel") or root_class.endswith("Box"):
        return 1
    if root_class == "Button":
        return 2
    if root_class == "Image":
        return 3
    return 4


def build_report_with_candidates(namespace: dict, object_path: str, candidates: list[str]) -> str:
    namespace["TARGET_ROOT_WIDGET_NAME"] = ",".join(candidates)
    namespace["TARGET_ROOT_WIDGET_NAMES"] = candidates
    return namespace["build_report"](object_path)


def choose_best_root_report(namespace: dict, object_path: str, candidates: list[str]) -> tuple[str, str, int]:
    best_markdown = ""
    best_candidate = ""
    best_rank = (-1, 999, 999)

    # First try each candidate independently. Some assets expose multiple named
    # children; the root is usually the one that yields the largest subtree.
    for index, candidate in enumerate(candidates):
        try:
            markdown = build_report_with_candidates(namespace, object_path, [candidate])
        except Exception:
            continue

        count = parse_widget_count(markdown)
        root_line = extract_report_value(markdown, "- Root widget(s)")
        root_class = parse_root_class(root_line)
        rank = (count, -root_class_priority(root_class), -index)
        if rank > best_rank:
            best_markdown = markdown
            best_candidate = candidate
            best_rank = rank

    if best_markdown:
        return best_markdown, best_candidate, best_rank[0]

    # Fall back to the whole candidate list so the failure report still records
    # the same broad probe path as manual single-asset runs.
    return build_report_with_candidates(namespace, object_path, candidates), "", 0


def export_asset(namespace: dict, asset_file: Path) -> dict:
    object_path = widget_asset_path(asset_file)
    report_name = report_name_for_asset(asset_file)
    candidates = guess_root_candidates(asset_file)

    namespace["TARGET_WIDGET_BLUEPRINT"] = object_path
    namespace["REPORT_NAME"] = report_name
    log(f"Exporting {object_path} with {len(candidates)} root candidates.")

    try:
        markdown, best_candidate, best_candidate_count = choose_best_root_report(namespace, object_path, candidates)
        status = "OK"
        error = ""
    except Exception:
        error = traceback.format_exc()
        markdown = namespace["build_unavailable_tree_report"](object_path, error)
        status = "FAILED"
        best_candidate = ""
        best_candidate_count = 0

    report_path = namespace["write_report"](markdown)
    root = extract_report_value(markdown, "- Root widget(s)")
    count = extract_report_value(markdown, "- Widget count")

    return {
        "asset": asset_file.stem,
        "object_path": object_path,
        "report": report_path.name,
        "status": status,
        "root": root or "<none>",
        "widget_count": count or "<none>",
        "candidate_count": str(len(candidates)),
        "candidates": ", ".join(candidates[:20]),
        "best_candidate": best_candidate or "<none>",
        "best_candidate_count": str(best_candidate_count) if best_candidate_count else "<none>",
        "error": error.strip().splitlines()[-1] if error else "",
    }


def write_summary(project_dir: Path, rows: list[dict]) -> Path:
    report_dir = project_dir / REPORT_SUBDIR
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / SUMMARY_REPORT_NAME

    lines = [
        f"# {TARGET_GAME_PATH} Widget Hierarchy Export Summary",
        "",
        "| Asset | Status | Root | Widget Count | Candidates | Report |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| `{asset}` | {status} | {root} | {widget_count} | {candidate_count} | `{report}` |".format(**row)
        )

    lines.extend(["", "## Root Candidate Details", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row['asset']}",
                "",
                f"- Object path: `{row['object_path']}`",
                f"- Status: `{row['status']}`",
                f"- Selected root: {row['root']}",
                f"- Widget count: {row['widget_count']}",
                f"- Candidate count: `{row['candidate_count']}`",
                f"- Best candidate: `{row['best_candidate']}`",
                f"- Best candidate widget count: `{row['best_candidate_count']}`",
                f"- First candidates: `{row['candidates'] or '<none>'}`",
            ]
        )
        if row["error"]:
            lines.append(f"- Error tail: `{row['error']}`")
        lines.append("")

    summary_path.write_text("\n".join(lines), encoding="utf-8")
    return summary_path


def main() -> None:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    namespace = load_exporter_namespace(project_dir)
    asset_dir = project_dir / TARGET_CONTENT_DIR
    asset_files = sorted(asset_dir.glob("*.uasset"))
    if not asset_files:
        raise RuntimeError(f"No .uasset files found under {asset_dir}")

    rows = []
    for asset_file in asset_files:
        rows.append(export_asset(namespace, asset_file))

    summary_path = write_summary(project_dir, rows)
    log(f"Wrote summary: {summary_path}")


main()



