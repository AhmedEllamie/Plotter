"""
SoftwareTeam Project Controller — incremental memory update from recent_changes
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from memory_utils import (
    BASE,
    area_ids_for_file,
    load_config,
    load_json,
    project_root,
    save_json,
    sync_functional_area_symbols,
    utc_now_iso,
)
from render_docs import write_rendered_docs
from symbol_scan import normalize_change_path, scan_python_file


def _is_code_change_path(path: str, prefix: str) -> bool:
    norm = normalize_change_path(path)
    return norm.startswith(prefix) and norm.endswith(".py")


def _resolve_abs_path(rel_path: str) -> Path | None:
    candidate = project_root() / rel_path.replace("\\", "/")
    if candidate.is_file():
        return candidate
    return None


def update_memory_from_changes() -> dict[str, Any]:
    config = load_config()
    prefix = config.get("code_package_prefix", "")
    changes_path = BASE / "memory" / "recent_changes.json"
    modules_path = BASE / "memory" / "modules.json"
    state_path = BASE / "memory" / "state.json"
    arch_path = BASE / "memory" / "architecture.json"

    changes = load_json(changes_path, []) or []
    if isinstance(changes, dict):
        changes = changes.get("changes", [])

    modules = load_json(modules_path, {}) or {}
    file_index: dict[str, dict[str, Any]] = modules.get("file_index") or {}
    pending_review: list[str] = []
    processed: list[str] = []
    skipped: list[str] = []
    deferred_docs: list[str] = []

    for entry in changes:
        if entry.get("memory_synced"):
            continue
        if entry.get("track") == "documents":
            entry["memory_synced"] = True
            skipped.append(entry.get("file", ""))
            continue

        rel = normalize_change_path(entry.get("file", ""))
        if not rel:
            entry["memory_synced"] = True
            continue

        if rel.startswith("docs/") or rel.startswith("deploy/"):
            deferred_docs.append(rel)
            entry["memory_synced"] = True
            entry["deferred_to"] = "/docs"
            continue

        if not _is_code_change_path(rel, prefix):
            entry["memory_synced"] = True
            skipped.append(rel)
            continue

        abs_path = _resolve_abs_path(rel)
        if not abs_path:
            entry["memory_synced"] = True
            entry["error"] = "file_not_found"
            skipped.append(rel)
            continue

        file_index[rel] = scan_python_file(abs_path)
        processed.append(rel)

        summary = (entry.get("summary") or "").lower()
        if any(k in summary for k in ("route", "flow", "endpoint", "api/")):
            pending_review.append(rel)

        entry["memory_synced"] = True
        entry["memory_synced_at"] = utc_now_iso()

    modules["file_index"] = file_index
    sync_functional_area_symbols(modules, file_index)
    if pending_review:
        modules["_pending_review"] = sorted(set((modules.get("_pending_review") or []) + pending_review))
    modules["scan_meta"] = {
        **(modules.get("scan_meta") or {}),
        "last_update": utc_now_iso(),
        "last_update_files": processed,
    }
    save_json(modules_path, modules)

    if pending_review:
        arch = load_json(arch_path, {}) or {}
        arch["_pending_review"] = sorted(set((arch.get("_pending_review") or []) + pending_review))
        save_json(arch_path, arch)

    state = load_json(state_path, {}) or {}
    state["last_memory_update"] = utc_now_iso()
    state["last_update"] = {
        "processed": processed,
        "skipped": skipped,
        "deferred_docs": deferred_docs,
        "pending_review": pending_review,
    }
    save_json(state_path, state)
    save_json(changes_path, changes)

    write_rendered_docs()

    return {
        "status": "updated",
        "processed_files": processed,
        "skipped": skipped,
        "deferred_docs": deferred_docs,
        "pending_review": pending_review,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(update_memory_from_changes(), indent=2))
