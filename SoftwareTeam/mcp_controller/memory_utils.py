"""
SoftwareTeam Project Controller — shared memory I/O
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).parent / "config.json"
BASE = Path(__file__).parent.parent
MCP_DIR = Path(__file__).parent


def load_config() -> dict[str, Any]:
    with open(CONFIG_PATH, encoding="utf-8-sig") as f:
        return json.load(f)


def project_root() -> Path:
    config = load_config()
    return (MCP_DIR / config.get("project_root", "../..")).resolve()


def code_scan_root() -> Path:
    config = load_config()
    scan_root = config.get("scan_root", "../..")
    root = Path(scan_root)
    if root.is_absolute():
        return root
    proj = project_root()
    candidate = (proj / scan_root).resolve()
    if candidate.is_dir():
        return candidate
    return (MCP_DIR / scan_root).resolve()


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def preserve_merge(existing: dict[str, Any], new_data: dict[str, Any], preserve_keys: list[str]) -> dict[str, Any]:
    merged = dict(new_data)
    for key in preserve_keys:
        if key in existing:
            merged[key] = existing[key]
    return merged


def scan_code_files() -> list[Path]:
    config = load_config()
    root_path = code_scan_root()
    extensions = tuple(config.get("scan_extensions", [".py"]))
    exclude_dirs = set(config.get("scan_exclude_dirs", []))
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            if filename.endswith(extensions):
                files.append(Path(dirpath) / filename)
    return sorted(files)


def rel_code_paths(abs_files: list[Path]) -> list[str]:
    root = project_root()
    return [p.resolve().relative_to(root).as_posix() for p in abs_files]


def build_file_index(abs_files: list[Path]) -> dict[str, dict[str, Any]]:
    from symbol_scan import rel_path_from_project, scan_python_file

    root = project_root()
    index: dict[str, dict[str, Any]] = {}
    for path in abs_files:
        rel = rel_path_from_project(path, root)
        try:
            index[rel] = scan_python_file(path)
        except (OSError, SyntaxError, UnicodeDecodeError):
            index[rel] = {"classes": [], "functions": [], "mtime": None, "error": "scan_failed"}
    return index


def sync_functional_area_symbols(modules: dict[str, Any], file_index: dict[str, dict[str, Any]]) -> None:
    areas = modules.get("functional_areas") or []
    for area in areas:
        for file_entry in area.get("files") or []:
            rel = file_entry.get("path", "").replace("\\", "/")
            scanned = file_index.get(rel)
            if not scanned:
                continue
            if scanned.get("classes"):
                file_entry["classes"] = scanned["classes"]
            if scanned.get("functions"):
                file_entry["functions"] = scanned["functions"]


def area_ids_for_file(rel_path: str, modules: dict[str, Any]) -> list[str]:
    rel = rel_path.replace("\\", "/")
    ids: list[str] = []
    for area in modules.get("functional_areas") or []:
        for file_entry in area.get("files") or []:
            if file_entry.get("path", "").replace("\\", "/") == rel:
                ids.append(area.get("id", ""))
    return [i for i in ids if i]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
