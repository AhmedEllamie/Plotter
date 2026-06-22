<!--
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
-->

# SoftwareTeam — Cursor Project Controller

Token-efficient multi-mode workflow for Cursor using MCP + structured memory.

## Goal

SoftwareTeam helps the agent avoid re-reading the whole repository on every task.
Memory is split into **three isolated tracks** so code scans never pull in generated HTML or unrelated assets.

## Three memory tracks

| Track | JSON | Human doc | Use when |
|-------|------|-----------|----------|
| Code architecture | `memory/architecture.json` | `docs/architecture.md` | System design, layers, flows, layer interactions |
| Code modules | `memory/modules.json` | `docs/modules.md` | Files, functions, functional areas, routes |
| Project documentation | `memory/documents.json` | `docs/documents.md` | API guides, deployment, guides — doc tasks only |
| Change log | `memory/recent_changes.json` | `docs/recent_changes.md` | `/update` input; Coder appends after edits |

**Hard rule:** `docs/generated/` never appears in code memory. Run `/docs` for the documentation catalog only.

## Quick Start

1. Run the installer from your project root.
2. Restart Cursor.
3. Open the project as workspace.
4. Confirm MCP server `project_controller` is connected in Settings → MCP.
5. In chat, run:

```
/init
/docs
```

## Day-to-Day Workflow

```
/init        -> full code scan per config.json (first setup / major refactor)
/update      -> patch code memory from recent_changes.json only
/docs        -> sync documentation catalog (excludes docs/generated/)
/architect   -> read-only architecture analysis (code memory)
/coder       -> implement focused code changes → record_change → /update
/reviewer    -> bug-focused review mode
/state       -> inspect current memory state
/test        -> run configured tests (if tester enabled)
```

Recommended loop:

1. `/init` once after install or major refactors.
2. `/coder` for implementation → `record_change_tool` → `/update`.
3. `/architect` before complex changes (reads `architecture.json` + `modules.json`).
4. `/docs` after markdown documentation changes.
5. Re-run `/init` only when package structure changes significantly.

## Command reference

| Command | Scope | When |
|---------|-------|------|
| `/init` | Full `.py` AST scan per `config.json` | First setup, new folders, major refactor |
| `/update` | `recent_changes.json` → changed `.py` only | After every Coder session |
| `/docs` | `docs/**/*.md` catalog (no generated HTML) | After doc edits |
| `/architect` | Code memory only | Design questions |
| `/coder` | Code memory; records changes | Implementation |

### `/init` example

```text
/init
```

Expected: refreshes `file_index` in `modules.json`, preserves curated `functional_areas` and `architecture.json` content.

### `/update` example

```text
/update
```

Expected: reads `recent_changes.json`, AST-scans only changed Python files, patches `file_index`, regenerates `docs/architecture.md` and `docs/modules.md`.

### `/docs` example

```text
/docs
```

Expected: builds `memory/documents.json` and `docs/documents.md`; excludes `docs/generated/`.

## Memory schema

### architecture.json (system design)

Curated keys preserved across `/init`: `project`, `system_design`, `layers`, `flows`, `notes`, etc.
`/init` refreshes `scan_meta` only unless you add content manually or from an example pack.

### modules.json (code map)

- `functional_areas` — curated groupings (preserve across `/init`)
- `file_index` — AST symbols per `.py` file (auto-refreshed by `/init` or `/update`)

### documents.json (doc catalog)

Built by `/docs` from markdown under configured `docs_scan.roots`.

## Folder guide

```
SoftwareTeam/
├── docs/
│   ├── architecture.md      # Rendered from architecture.json
│   ├── modules.md           # Rendered from modules.json
│   ├── documents.md         # Rendered from documents.json
│   ├── recent_changes.md    # Change log
│   └── prompts/
├── memory/
│   ├── architecture.json    # System design + flows (code track)
│   ├── modules.json         # Functional areas + file_index (code track)
│   ├── documents.json       # Doc catalog (doc track)
│   ├── recent_changes.json  # Changelog → /update input
│   └── state.json           # Mode, tracks, last sync timestamps
└── mcp_controller/
    ├── server.py            # MCP tools
    ├── init.py              # Full code scan
    ├── update.py            # Incremental update from recent_changes
    ├── docs_sync.py         # Documentation catalog sync
    ├── symbol_scan.py       # AST extraction
    ├── memory_utils.py      # Shared I/O
    ├── render_docs.py       # JSON → markdown
    └── config.json          # Scan scope + preserve_keys
```

## Example project packs

See `templates/examples/` in the SoftwareTeam repo for curated `architecture.json` / `modules.json` seeds (e.g. plotter-signature). Copy seeds before `/init` to get rich architecture on first scan.

## Best practices

- **Code tasks:** read `architecture.json` + `modules.json` only.
- **Doc tasks:** read `documents.json` + one specific doc file.
- After Coder edits: `record_change_tool` then `/update` (not `/init`).
- After doc edits: `/docs` (does not touch code memory).

## When to re-run commands

| Event | Command |
|-------|---------|
| Coder edits `.py` | `/update` |
| New API route or flow | Update `architecture.json` manually (Architect mode) |
| New/edited markdown doc | `/docs` |
| Major package restructure | `/init` |

## Troubleshooting

- MCP not connected: restart Cursor, check `.cursor/mcp.json`
- `/init` scans wrong scope: verify `scan_root` and `project_root` in `config.json`
- `/update` processes nothing: check `recent_changes.json` entries are not already `memory_synced`
- Commands not mapping: verify `.cursor/rules/commands.mdc` exists

## Author

Ahmed Ellamie — ahmed.ellamiee@gmail.com
