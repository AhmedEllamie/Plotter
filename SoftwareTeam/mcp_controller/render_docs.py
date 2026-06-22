"""
SoftwareTeam Project Controller — render human docs from JSON memory
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

BASE = Path(__file__).parent.parent
DOCS = BASE / "docs"
MEMORY = BASE / "memory"

HEADER = "<!--\nAuthor: Ahmed Ellamie\nEmail: ahmed.ellamiee@gmail.com\n-->\n\n"


def render_architecture_md(arch: dict[str, Any]) -> str:
    lines = [HEADER, "# Architecture\n\n"]
    project = arch.get("project") or {}
    if project:
        lines.append(f"**{project.get('name', 'project')}** — {project.get('description', '')}\n\n")
    design = arch.get("system_design") or {}
    if design:
        lines.append("## System design\n\n")
        lines.append(f"- **Pattern:** {design.get('pattern', 'n/a')}\n")
        lines.append(f"- **Description:** {design.get('description', '')}\n")
        lines.append(f"- **Composition root:** `{design.get('composition_root', '')}`\n\n")
    rules = arch.get("dependency_rules") or []
    if rules:
        lines.append("## Dependency rules\n\n")
        for rule in rules:
            lines.append(f"- {rule}\n")
        lines.append("\n")
    layers = arch.get("layers") or []
    if layers:
        lines.append("## Layers\n\n")
        lines.append("| Layer | Path | Purpose |\n|-------|------|--------|\n")
        for layer in layers:
            lines.append(f"| {layer.get('id', '')} | `{layer.get('path', '')}` | {layer.get('purpose', '')} |\n")
        lines.append("\n")
    interactions = arch.get("layer_interactions") or []
    if interactions:
        lines.append("## Layer interactions\n\n")
        for edge in interactions:
            lines.append(f"- **{edge.get('from', '')}** → **{edge.get('to', '')}** via `{edge.get('via', '')}` ")
            lines.append(f"({edge.get('contract', '')})\n")
            for ex in edge.get("examples") or []:
                lines.append(f"  - {ex}\n")
        lines.append("\n")
    entry_points = arch.get("entry_points") or []
    if entry_points:
        lines.append("## Entry points\n\n")
        for ep in entry_points:
            lines.append(f"### {ep.get('id', '')}\n\n")
            lines.append(f"- Symbol: `{ep.get('symbol', '')}`\n")
            if ep.get("default_port"):
                lines.append(f"- Default port: {ep['default_port']}\n")
            cmds = ep.get("commands") or []
            if cmds:
                lines.append(f"- Commands: {', '.join(f'`{c}`' for c in cmds)}\n")
            lines.append("\n")
    externals = arch.get("external_systems") or []
    if externals:
        lines.append("## External systems\n\n")
        for ext in externals:
            lines.append(f"- **{ext.get('id', '')}** — {ext.get('via', '')} ({ext.get('settings', ext.get('default', ''))})\n")
        lines.append("\n")
    flows = arch.get("flows") or []
    if flows:
        lines.append("## Flows\n\n")
        for flow in flows:
            lines.append(f"### {flow.get('id', '')}\n\n")
            lines.append(f"- **Trigger:** {flow.get('trigger', '')}\n")
            if flow.get("description"):
                lines.append(f"- **Description:** {flow['description']}\n")
            lines.append("\n**Steps:**\n\n")
            for i, step in enumerate(flow.get("steps") or [], 1):
                lines.append(f"{i}. `{step.get('file', '')}` → `{step.get('symbol', '')}` — {step.get('note', '')}\n")
            lines.append("\n")
    notes = arch.get("notes") or []
    if notes:
        lines.append("## Notes\n\n")
        for note in notes:
            lines.append(f"- {note}\n")
        lines.append("\n")
    meta = arch.get("scan_meta") or {}
    if meta:
        lines.append(f"\n---\n\n*Code scan: {meta.get('file_count', 0)} Python files, last init {meta.get('last_init', 'n/a')}*\n")
    return "".join(lines)


def render_modules_md(modules: dict[str, Any]) -> str:
    lines = [HEADER, "# Modules\n\n"]
    areas = modules.get("functional_areas") or []
    for area in areas:
        lines.append(f"## {area.get('name', area.get('id', ''))}\n\n")
        if area.get("description"):
            lines.append(f"{area['description']}\n\n")
        flow_ids = area.get("flow_ids") or []
        if flow_ids:
            lines.append(f"**Flows:** {', '.join(f'`{f}`' for f in flow_ids)}\n\n")
        doc_refs = area.get("doc_refs") or []
        if doc_refs:
            lines.append(f"**Doc refs:** {', '.join(f'`{d}`' for d in doc_refs)}\n\n")
        http = area.get("http_routes") or {}
        if http:
            lines.append("**HTTP routes:**\n\n")
            for surface, routes in http.items():
                if routes:
                    lines.append(f"- {surface}: {', '.join(f'`{r}`' for r in routes)}\n")
            lines.append("\n")
        cli_cmds = area.get("cli_commands") or []
        if cli_cmds:
            lines.append(f"**CLI:** {', '.join(f'`{c}`' for c in cli_cmds)}\n\n")
        lines.append("**Files:**\n\n")
        for fe in area.get("files") or []:
            lines.append(f"- `{fe.get('path', '')}` — {fe.get('role', '')}\n")
            classes = fe.get("classes") or []
            funcs = fe.get("functions") or []
            if classes:
                lines.append(f"  - classes: {', '.join(f'`{c}`' for c in classes)}\n")
            if funcs:
                shown = funcs[:12]
                suffix = f" (+{len(funcs) - 12} more)" if len(funcs) > 12 else ""
                lines.append(f"  - functions: {', '.join(f'`{f}`' for f in shown)}{suffix}\n")
        lines.append("\n")
    index = modules.get("file_index") or {}
    lines.append(f"---\n\n*File index: {len(index)} Python source files*\n")
    return "".join(lines)


def render_documents_md(documents: dict[str, Any]) -> str:
    lines = [HEADER, "# Project documentation catalog\n\n"]
    lines.append("Use this catalog for documentation tasks. Do not load `docs/generated/` into agent context.\n\n")
    meta = documents.get("_meta") or {}
    if meta.get("last_sync"):
        lines.append(f"Last sync: {meta['last_sync']}\n\n")
    for category in documents.get("categories") or []:
        if category.get("index_in_memory") is False:
            lines.append(f"## {category.get('name', '')} (excluded from index)\n\n")
            lines.append(f"{category.get('note', '')}\n\n")
            continue
        lines.append(f"## {category.get('name', category.get('id', ''))}\n\n")
        if category.get("purpose"):
            lines.append(f"{category['purpose']}\n\n")
        for doc in category.get("docs") or []:
            title = doc.get("title") or doc.get("path", "")
            lines.append(f"- `{doc.get('path', '')}` — {title}")
            areas = doc.get("related_areas") or []
            if areas:
                lines.append(f" (areas: {', '.join(areas)})")
            lines.append("\n")
        lines.append("\n")
    return "".join(lines)


def write_rendered_docs() -> None:
    arch = _load(MEMORY / "architecture.json")
    modules = _load(MEMORY / "modules.json")
    documents = _load(MEMORY / "documents.json")
    DOCS.mkdir(parents=True, exist_ok=True)
    if arch:
        (DOCS / "architecture.md").write_text(render_architecture_md(arch), encoding="utf-8")
    if modules:
        (DOCS / "modules.md").write_text(render_modules_md(modules), encoding="utf-8")
    if documents:
        (DOCS / "documents.md").write_text(render_documents_md(documents), encoding="utf-8")


def _load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    import json

    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)
