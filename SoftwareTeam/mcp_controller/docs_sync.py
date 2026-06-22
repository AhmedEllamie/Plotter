"""
SoftwareTeam Project Controller — documentation catalog sync (/docs)
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Any

from memory_utils import BASE, load_config, load_json, preserve_merge, project_root, save_json, utc_now_iso
from render_docs import render_documents_md

AUTHOR = {"_author": "Ahmed Ellamie", "_email": "ahmed.ellamiee@gmail.com"}


def _title_from_md(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return path.stem.replace("_", " ")


def _infer_category(rel_path: str) -> str:
    norm = rel_path.replace("\\", "/")
    if "api-pre-security" in norm or "api-grouped" in norm:
        return "api_reference"
    if "UBUNTU" in norm or "deploy/" in norm:
        return "deployment"
    if "UAT" in norm or "POSTMAN" in norm or "TECHNICAL" in norm:
        return "testing_and_guides"
    if "SCANNER" in norm or "INTEGRATION" in norm or "CHANGE_PEN" in norm:
        return "integration"
    if "API_REFERENCE" in norm:
        return "api_reference"
    return "general"


def _infer_related_areas(rel_path: str, title: str) -> list[str]:
    text = (rel_path + " " + title).lower()
    areas: list[str] = []
    mapping = {
        "printing": ["print", "bulk", "void", "gcode", "svg"],
        "pen_change": ["pen", "change-pen", "distance"],
        "serial_connection": ["serial", "connect", "port"],
        "scanner_integration": ["scanner", "capture", "stream", "mjpg"],
        "ui_profile": ["config", "ui-profile", "profile"],
        "auth": ["security", "api-key", "auth"],
        "approval_workflow": ["approval", "void"],
        "http_shell": ["health", "status", "ubuntu", "deploy", "flask"],
    }
    for area_id, keywords in mapping.items():
        if any(k in text for k in keywords):
            areas.append(area_id)
    return areas or ["http_shell"]


def _should_exclude(rel_posix: str, exclude_dirs: set[str], exclude_globs: list[str]) -> bool:
    parts = rel_posix.split("/")
    if any(p in exclude_dirs for p in parts):
        return True
    for pattern in exclude_globs:
        if fnmatch.fnmatch(rel_posix, pattern):
            return True
    return False


def scan_document_files() -> list[str]:
    config = load_config()
    docs_cfg = config.get("docs_scan", {})
    roots = docs_cfg.get("roots", ["../docs"])
    extensions = tuple(docs_cfg.get("extensions", [".md"]))
    exclude_dirs = set(docs_cfg.get("exclude_dirs", ["generated", "doxygen"]))
    exclude_globs = docs_cfg.get("exclude_globs", [])
    proj = project_root()
    found: list[str] = []

    for root_rel in roots:
        root_path = (proj / root_rel).resolve()
        if not root_path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
            for filename in filenames:
                if not filename.endswith(extensions):
                    continue
                abs_path = Path(dirpath) / filename
                rel = abs_path.resolve().relative_to(proj).as_posix()
                if _should_exclude(rel, exclude_dirs, exclude_globs):
                    continue
                found.append(rel)
    return sorted(set(found))


def _default_categories() -> list[dict[str, Any]]:
    return [
        {
            "id": "api_reference",
            "name": "API reference",
            "purpose": "Endpoint contracts and request/response shapes",
            "docs": [],
        },
        {
            "id": "deployment",
            "name": "Deployment",
            "purpose": "Release and Ubuntu deployment guides",
            "docs": [],
        },
        {
            "id": "integration",
            "name": "Integration guides",
            "purpose": "Scanner HTTP integration and pen-change documentation",
            "docs": [],
        },
        {
            "id": "testing_and_guides",
            "name": "Testing and technical guides",
            "purpose": "UAT, Postman, and technical documentation",
            "docs": [],
        },
        {
            "id": "general",
            "name": "General documentation",
            "purpose": "Top-level and miscellaneous project docs",
            "docs": [],
        },
        {
            "id": "generated_artifacts",
            "name": "Generated (do not index)",
            "index_in_memory": False,
            "note": "docs/generated/ — Doxygen HTML; regenerate via build, never load into agent context",
            "path": "docs/generated/",
        },
    ]


def sync_documents() -> dict[str, Any]:
    config = load_config()
    doc_paths = scan_document_files()
    proj = project_root()
    categories = _default_categories()
    cat_by_id = {c["id"]: c for c in categories if c.get("index_in_memory", True)}

    for rel in doc_paths:
        cat_id = _infer_category(rel)
        category = cat_by_id.get(cat_id) or cat_by_id["general"]
        abs_path = proj / rel
        title = _title_from_md(abs_path)
        doc_type = "endpoint" if "api-pre-security" in rel or "POST_api" in rel or "GET_api" in rel else "guide"
        category.setdefault("docs", []).append(
            {
                "path": rel,
                "title": title,
                "type": doc_type,
                "related_areas": _infer_related_areas(rel, title),
                "generated": False,
            }
        )

    for cat in categories:
        if cat.get("docs"):
            cat["docs"] = sorted(cat["docs"], key=lambda d: d.get("path", ""))

    documents: dict[str, Any] = {
        **AUTHOR,
        "_meta": {
            "last_sync": utc_now_iso(),
            "scan_roots": config.get("docs_scan", {}).get("roots", []),
            "doc_count": len(doc_paths),
        },
        "exclude_patterns": ["docs/generated/**", "docs/doxygen/**", "**/*.html"],
        "categories": categories,
    }

    docs_path = BASE / "memory" / "documents.json"
    existing = load_json(docs_path, {}) or {}
    preserve = config.get("preserve_keys", {}).get("documents.json", ["categories"])
    if existing.get("categories") and not doc_paths:
        documents = preserve_merge(existing, documents, preserve)
    save_json(docs_path, documents)

    (BASE / "docs" / "documents.md").write_text(render_documents_md(documents), encoding="utf-8")

    state_path = BASE / "memory" / "state.json"
    state = load_json(state_path, {}) or {}
    tracks = state.get("tracks") or {}
    tracks["documents"] = {"last_sync": utc_now_iso(), "doc_count": len(doc_paths)}
    state["tracks"] = tracks
    save_json(state_path, state)

    return {
        "status": "synced",
        "doc_count": len(doc_paths),
        "categories": [c["id"] for c in categories if c.get("index_in_memory", True)],
    }


if __name__ == "__main__":
    import json

    print(json.dumps(sync_documents(), indent=2))
