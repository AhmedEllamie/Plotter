"""
SoftwareTeam Project Controller — INIT (full code scan)
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from memory_utils import (
    BASE,
    build_file_index,
    load_config,
    load_json,
    preserve_merge,
    rel_code_paths,
    save_json,
    scan_code_files,
    sync_functional_area_symbols,
    utc_now_iso,
)
from render_docs import write_rendered_docs

AUTHOR = {"_author": "Ahmed Ellamie", "_email": "ahmed.ellamiee@gmail.com"}


def init_project() -> dict[str, Any]:
    config = load_config()
    abs_files = scan_code_files()
    rel_files = rel_code_paths(abs_files)
    file_index = build_file_index(abs_files)

    (BASE / "memory").mkdir(exist_ok=True)
    (BASE / "docs").mkdir(exist_ok=True)

    preserve = config.get("preserve_keys", {})
    arch_path = BASE / "memory" / "architecture.json"
    modules_path = BASE / "memory" / "modules.json"
    existing_arch = load_json(arch_path, {}) or {}
    existing_modules = load_json(modules_path, {}) or {}

    modules_data: dict[str, Any] = {**AUTHOR}
    if existing_modules.get("functional_areas"):
        modules_data["functional_areas"] = existing_modules["functional_areas"]
    else:
        modules_data["functional_areas"] = []

    modules_data["file_index"] = file_index
    modules_data["scan_meta"] = {
        "last_init": utc_now_iso(),
        "file_count": len(rel_files),
        "scan_root": config.get("scan_root", "../.."),
    }
    sync_functional_area_symbols(modules_data, file_index)
    modules_data = preserve_merge(existing_modules, modules_data, preserve.get("modules.json", ["functional_areas"]))
    save_json(modules_path, modules_data)

    arch_data: dict[str, Any] = {**AUTHOR}
    arch_data["scan_meta"] = {
        "last_init": utc_now_iso(),
        "file_count": len(rel_files),
        "scan_root": config.get("scan_root", "../.."),
    }
    arch_data = preserve_merge(existing_arch, arch_data, preserve.get("architecture.json", []))
    save_json(arch_path, arch_data)

    state_path = BASE / "memory" / "state.json"
    existing_state = load_json(state_path, {}) or {}
    state: dict[str, Any] = {
        **AUTHOR,
        "files": rel_files,
        "last_mode": "INIT",
        "mode": "Init",
        "last_memory_update": utc_now_iso(),
        "enabled_enhancements": [k for k, v in config.get("enhancements", {}).items() if v],
        "tracks": {
            "code": {
                "last_init": utc_now_iso(),
                "file_count": len(rel_files),
            },
            "documents": existing_state.get("tracks", {}).get("documents", {"last_sync": None}),
        },
    }
    save_json(state_path, state)

    write_rendered_docs()
    print("INIT DONE")
    return state


def scan_files(root=None) -> list[str]:
    """Legacy API for optional enhancement modules."""
    return [str(p) for p in scan_code_files()]


if __name__ == "__main__":
    init_project()
