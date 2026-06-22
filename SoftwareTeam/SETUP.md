<!--
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
-->

# SoftwareTeam Setup Guide

## After Running SoftwareTeam-Setup.exe

1. **Restart Cursor** (required)
2. Open the **whole project** as workspace (not just SoftwareTeam/)
3. Check **Settings → MCP** — `project_controller` should be green
4. In chat, run `/init` then `/docs` once

## Chat Commands (convention via rules + MCP)

These are **not** native Cursor slash commands. Rules in `.cursor/rules/commands.mdc` route them to MCP tools.

| Command | Action |
|---------|--------|
| `/init` | Full code scan; build code memory + render architecture/modules docs |
| `/update` | Incremental code memory from `recent_changes.json` |
| `/docs` | Sync documentation catalog to `documents.json` |
| `/architect` | Architecture mode (read-only) |
| `/coder` | Edit one specified file |
| `/reviewer` | Review one file |
| `/state` | Show current memory |
| `/test` | Run tests (if Tester enhancement enabled) |
| `/pipeline <task>` | Multi-agent handoff (if Pipeline enabled) |

## Three memory tracks

- **Code** (`/init`, `/update`) — `architecture.json`, `modules.json`
- **Docs** (`/docs`) — `documents.json` (excludes `docs/generated/`)
- **Changes** (Coder) — `recent_changes.json` → `/update`

## Token Savings

- **INIT once** — Python scans code; AI reads cached docs after
- **UPDATE** — only changed `.py` files, not full repo
- **Architect** — reads `docs/` + `memory/` only
- **Coder** — edits one file; records diff to `recent_changes.json`
- **Reviewer** — reviews one file; reads change history

## Re-run Setup

Setup is **additive** — user memory JSON is protected. Framework files (`mcp_controller/*.py`, rules) are upgraded on each install run.

## Configure Tests (Enhancement 4)

Edit `mcp_controller/config.json`:

```json
"test_command": "pytest tests/"
```

## Author

Ahmed Ellamie — ahmed.ellamiee@gmail.com
