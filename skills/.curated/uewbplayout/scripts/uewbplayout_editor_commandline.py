from __future__ import annotations

import os
from pathlib import Path
import traceback

import unreal


def log(message: str) -> None:
    unreal.log(f"[WidgetHierarchyExport] {message}")


def request_editor_quit() -> None:
    system_library = getattr(unreal, "SystemLibrary", None)
    quit_editor = getattr(system_library, "quit_editor", None) if system_library else None
    if callable(quit_editor):
        try:
            quit_editor()
            return
        except Exception:
            unreal.log_warning("[WidgetHierarchyExport] SystemLibrary.quit_editor failed:\n" + traceback.format_exc())

    editor_level_library = getattr(unreal, "EditorLevelLibrary", None)
    editor_world = None
    getter = getattr(editor_level_library, "get_editor_world", None) if editor_level_library else None
    if callable(getter):
        try:
            editor_world = getter()
        except Exception:
            editor_world = None

    execute_console_command = getattr(system_library, "execute_console_command", None) if system_library else None
    if callable(execute_console_command):
        try:
            execute_console_command(editor_world, "QUIT_EDITOR")
        except Exception:
            unreal.log_warning("[WidgetHierarchyExport] Console QUIT_EDITOR failed:\n" + traceback.format_exc())


def main() -> None:
    project_dir = Path(unreal.Paths.project_dir()).resolve()
    script_override = os.environ.get("UEWBPLAYOUT_EXPORTER_SCRIPT")
    script_path = Path(script_override) if script_override else project_dir / "Content" / "Python" / "WidgetTools" / "uewbplayout_export_one.py"
    if not script_path.exists():
        raise RuntimeError(f"Exporter script was not found: {script_path}")

    log(f"Running exporter from full Editor command line: {script_path}")
    try:
        globals_for_exporter = {
            "__name__": "__main__",
            "__file__": str(script_path),
            "ALLOW_LIVE_WIDGET_INSTANCE_FALLBACK": True,
        }

        target_asset = os.environ.get("UEWBPLAYOUT_TARGET")
        report_name = os.environ.get("UEWBPLAYOUT_REPORT_NAME")
        root_name = os.environ.get("UEWBPLAYOUT_ROOT_NAME")
        if target_asset:
            globals_for_exporter["TARGET_WIDGET_BLUEPRINT"] = target_asset
            log(f"Target override: {target_asset}")
        if report_name:
            globals_for_exporter["REPORT_NAME"] = report_name
            log(f"Report override: {report_name}")
        if root_name is not None:
            globals_for_exporter["TARGET_ROOT_WIDGET_NAME"] = root_name
            globals_for_exporter["TARGET_ROOT_WIDGET_NAMES"] = root_name
            log(f"Root widget override: {root_name or '<disabled>'}")

        source = script_path.read_text(encoding="utf-8")
        exec(compile(source, str(script_path), "exec"), globals_for_exporter)
    finally:
        log("Requesting Editor shutdown after command-line export.")
        request_editor_quit()


main()

