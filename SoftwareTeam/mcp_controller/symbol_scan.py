"""
SoftwareTeam Project Controller — AST symbol extraction
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
from __future__ import annotations

import ast
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROUTE_DECORATORS = frozenset({"route", "get", "post", "put", "delete", "patch", "api_route"})
LAYER_FOLDER_HINTS = ("domain", "services", "infrastructure", "web", "desktop", "api", "cli")


def extract_symbols_from_source(source: str) -> dict[str, list[str]]:
    tree = ast.parse(source)
    classes: list[str] = []
    functions: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
    return {"classes": sorted(classes), "functions": sorted(functions)}


def scan_python_file(abs_path: Path) -> dict[str, Any]:
    source = abs_path.read_text(encoding="utf-8")
    symbols = extract_symbols_from_source(source)
    mtime = datetime.fromtimestamp(abs_path.stat().st_mtime, tz=timezone.utc).isoformat()
    return {
        "classes": symbols["classes"],
        "functions": symbols["functions"],
        "mtime": mtime,
    }


def scan_python_files(abs_paths: list[Path]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in abs_paths:
        if not path.is_file() or path.suffix != ".py":
            continue
        try:
            rel = path.as_posix()
            index[rel] = scan_python_file(path)
        except (OSError, SyntaxError, UnicodeDecodeError):
            index[path.as_posix()] = {
                "classes": [],
                "functions": [],
                "mtime": None,
                "error": "scan_failed",
            }
    return index


def rel_path_from_project(abs_path: Path, project_root: Path) -> str:
    return abs_path.resolve().relative_to(project_root.resolve()).as_posix()


def normalize_change_path(file_path: str) -> str:
    return file_path.replace("\\", "/").lstrip("./")


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _route_from_decorator(dec: ast.expr) -> str | None:
    if not isinstance(dec, ast.Call) or not dec.args:
        return None
    first = dec.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _extract_file_hints(source: str, rel_path: str) -> dict[str, Any]:
    hints: dict[str, Any] = {
        "entry_points": [],
        "route_hints": [],
        "cli_hints": [],
        "import_modules": [],
    }
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return hints

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                hints["import_modules"].append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            hints["import_modules"].append(node.module)

    if rel_path.endswith("__main__.py") or rel_path.endswith("cli.py"):
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in ("main", "create_app"):
                hints["entry_points"].append(f"{rel_path}:{node.name}")

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                name = _decorator_name(dec)
                if name in ROUTE_DECORATORS:
                    route = _route_from_decorator(dec) if isinstance(dec, ast.Call) else None
                    if route:
                        hints["route_hints"].append({"file": rel_path, "route": route, "handler": node.name})
            if node.name in ("create_app", "main") and not any(ep.endswith(node.name) for ep in hints["entry_points"]):
                hints["entry_points"].append(f"{rel_path}:{node.name}")

    if "cli.py" in rel_path.replace("\\", "/"):
        for match in re.finditer(r'add_parser\(\s*["\']([\w-]+)["\']', source):
            hints["cli_hints"].append(match.group(1))
        for match in re.finditer(r'subparsers\.add_parser\(\s*["\']([\w-]+)["\']', source):
            hints["cli_hints"].append(match.group(1))

    return hints


def extract_enrichment_hints(
    abs_files: list[Path],
    file_index: dict[str, dict[str, Any]],
    project_root: Path,
) -> dict[str, Any]:
    """Compact digest for AI enrichment — no full symbol lists."""
    folder_tree: dict[str, list[str]] = {}
    symbol_counts: dict[str, dict[str, int]] = {}
    entry_points: list[str] = []
    route_hints: list[dict[str, str]] = []
    cli_hints: list[str] = []
    import_edges: list[str] = []
    layer_candidates: list[dict[str, str]] = []
    seen_layers: set[str] = set()

    for path in abs_files:
        rel = rel_path_from_project(path, project_root)
        parts = rel.split("/")
        top = parts[0] if parts else "(root)"
        folder_tree.setdefault(top, []).append(rel)

        scanned = file_index.get(rel, {})
        symbol_counts[rel] = {
            "class_count": len(scanned.get("classes") or []),
            "function_count": len(scanned.get("functions") or []),
        }

        for part in parts:
            if part in LAYER_FOLDER_HINTS and part not in seen_layers:
                seen_layers.add(part)
                layer_candidates.append({"id": part, "path": "/".join(parts[: parts.index(part) + 1])})

        try:
            source = path.read_text(encoding="utf-8")
            file_hints = _extract_file_hints(source, rel)
            entry_points.extend(file_hints["entry_points"])
            route_hints.extend(file_hints["route_hints"])
            cli_hints.extend(file_hints["cli_hints"])
            src_name = Path(rel).name
            for mod in file_hints["import_modules"]:
                tgt = mod.split(".")[-1]
                if tgt and tgt != src_name.replace(".py", ""):
                    import_edges.append(f"{src_name} -> {tgt}")
        except OSError:
            continue

    return {
        "folder_tree": {k: sorted(v) for k, v in sorted(folder_tree.items())},
        "symbol_counts": symbol_counts,
        "import_edges": sorted(set(import_edges))[:30],
        "entry_points": sorted(set(entry_points)),
        "route_hints": route_hints[:40],
        "cli_hints": sorted(set(cli_hints)),
        "layer_candidates": layer_candidates,
    }


ENRICHMENT_SCHEMA = {
    "architecture_patch": {
        "project": {"name": "", "version": "", "description": ""},
        "system_design": {"pattern": "", "description": "", "composition_root": ""},
        "dependency_rules": [],
        "layers": [{"id": "", "path": "", "purpose": ""}],
        "layer_interactions": [{"from": "", "to": "", "via": "", "contract": "", "examples": []}],
        "entry_points": [{"id": "", "symbol": "", "default_port": None, "commands": []}],
        "external_systems": [{"id": "", "via": "", "settings": ""}],
        "flows": [{"id": "", "trigger": "", "description": "", "steps": [{"file": "", "symbol": "", "note": ""}]}],
        "notes": [],
    },
    "modules_patch": {
        "functional_areas": [
            {
                "id": "",
                "name": "",
                "description": "",
                "files": [{"path": "", "role": ""}],
                "http_routes": {},
                "cli_commands": [],
                "flow_ids": [],
            }
        ]
    },
}
