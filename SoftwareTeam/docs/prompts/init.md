/init

Run INIT — scan the project and build SoftwareTeam memory and docs.

## Phase 1

Call `init_project_tool`.

## Phase 2 (only if response `needs_enrichment` is true)

### Option A — example pack (preferred, 0 AI tokens)

If `example_pack_available` is set (e.g. `plotter-signature`):

```
apply_example_pack_tool(pack_name="<example_pack_available>")
```

### Option B — AI enrichment (token-efficient)

1. Call `get_init_context_tool` — **only** context source; do not read application source files.
2. Fill patches from digest (`folder_tree`, `route_hints`, `cli_hints`, `layer_candidates`, `import_edges`).
3. Call `apply_enrichment_patch_tool` with JSON strings for both patches.

## Minimal patch schema

**architecture_patch** — omit `scan_meta`:

```json
{
  "project": {"name": "", "version": "1.0.0", "description": ""},
  "system_design": {"pattern": "", "description": "", "composition_root": ""},
  "dependency_rules": ["rule one", "rule two"],
  "layers": [{"id": "domain", "path": "pkg/domain", "purpose": ""}],
  "layer_interactions": [{"from": "", "to": "", "via": "", "contract": "", "examples": []}],
  "entry_points": [{"id": "cli", "symbol": "pkg.cli:main", "commands": []}],
  "external_systems": [{"id": "", "via": "", "settings": ""}],
  "flows": [{"id": "", "trigger": "", "steps": [{"file": "", "symbol": "", "note": ""}]}]
}
```

**modules_patch** — paths and roles only; **omit** `classes` and `functions`:

```json
{
  "functional_areas": [
    {
      "id": "printing",
      "name": "Short area title",
      "description": "One sentence",
      "files": [{"path": "pkg/services/printer.py", "role": "What this file does"}],
      "http_routes": {"flask": ["POST /api/cmd/print"]},
      "cli_commands": ["print"],
      "flow_ids": ["flask_print"]
    }
  ]
}
```

Python runs `sync_functional_area_symbols` after patch — symbols come from `file_index`.

## After first init

Tell user to run `/docs` for the documentation catalog.

## Re-init (curated memory exists)

`needs_enrichment` is false — report file_count and scan_root only.
