"""

SoftwareTeam Project Controller — MCP Server

Author: Ahmed Ellamie

Email: ahmed.ellamiee@gmail.com

"""

import json

from pathlib import Path



from mcp.server.fastmcp import FastMCP



from changes import record_change as do_record_change

from docs_sync import sync_documents

from init import init_project

from init_enrichment import (

    apply_enrichment_patch,

    apply_example_pack,

    get_init_context,

    init_tool_response,

    needs_enrichment,

)

from memory_utils import load_config

from mode import set_mode

from render_docs import write_rendered_docs

from update import update_memory_from_changes



mcp = FastMCP("project_controller")

BASE = Path(__file__).parent.parent





def _config():

    return load_config()





@mcp.tool()

def init_project_tool() -> str:

    """Full code scan per config.json; refresh file_index; preserve curated architecture."""

    state = init_project()

    return json.dumps(init_tool_response(state), indent=2)





@mcp.tool()

def get_init_context_tool() -> str:

    """Compact digest for first-init AI enrichment (folder tree, hints, schema). No source file reads needed."""

    return json.dumps(get_init_context(), indent=2)





@mcp.tool()

def apply_enrichment_patch_tool(architecture_patch: str, modules_patch: str) -> str:

    """Merge curated architecture and functional_areas; sync symbols from file_index; render docs."""

    arch = json.loads(architecture_patch) if isinstance(architecture_patch, str) else architecture_patch

    mods = json.loads(modules_patch) if isinstance(modules_patch, str) else modules_patch

    result = apply_enrichment_patch(arch, mods)

    return json.dumps(result, indent=2)





@mcp.tool()

def apply_example_pack_tool(pack_name: str = "") -> str:

    """Zero-token path: copy curated example memory seeds (e.g. plotter-signature) and sync symbols."""

    result = apply_example_pack(pack_name or None)

    return json.dumps(result, indent=2)





@mcp.tool()

def render_memory_docs_tool() -> str:

    """Regenerate docs/architecture.md, modules.md, documents.md from memory JSON."""

    write_rendered_docs()

    return json.dumps({"status": "rendered", "needs_enrichment": needs_enrichment()}, indent=2)





@mcp.tool()

def update_memory_tool() -> str:

    """Incremental memory update from recent_changes.json only (changed .py files, no full repo scan)."""

    result = update_memory_from_changes()

    return json.dumps(result, indent=2)





@mcp.tool()

def sync_documents_tool() -> str:

    """Sync documentation catalog to memory/documents.json (excludes docs/generated/)."""

    result = sync_documents()

    return json.dumps(result, indent=2)





@mcp.tool()

def set_mode_tool(mode: str) -> str:

    """Switch workflow mode: Init, Architect, Coder, Reviewer, or Tester."""

    state = set_mode(mode)

    return json.dumps({"mode": state.get("mode"), "last_mode": state.get("last_mode")}, indent=2)





@mcp.tool()

def get_state() -> str:

    """Read current memory state from state.json."""

    path = BASE / "memory" / "state.json"

    if not path.exists():

        return json.dumps({"status": "not_initialized", "message": "Run /init first"})

    with open(path, encoding="utf-8-sig") as f:

        return json.dumps(json.load(f), indent=2)





@mcp.tool()

def record_change_tool(file: str, summary: str, diff: str = "") -> str:

    """Record a code change after Coder edits (writes recent_changes.json)."""

    entry = do_record_change(file, summary, diff)

    return json.dumps({"recorded": entry}, indent=2)





def _register_enhancement_tools():

    config = _config()

    enhancements = config.get("enhancements", {})



    if enhancements.get("semantic_memory"):

        @mcp.tool()

        def semantic_search(query: str) -> str:

            """Search indexed project files by keyword (local stub, no API)."""

            from semantic_memory import semantic_search as search

            results = search(query)

            return json.dumps(results, indent=2)



    if enhancements.get("dependency_graph"):

        @mcp.tool()

        def build_dependency_graph() -> str:

            """Build docs/dependencies.graph from imports and includes."""

            from dependencies import build_dependency_graph as build

            edges = build()

            return json.dumps({"edge_count": len(edges), "edges": edges[:50]}, indent=2)



    if enhancements.get("tester"):

        @mcp.tool()

        def run_tests() -> str:

            """Run the configured test_command from config.json."""

            from tester import run_tests as run

            return json.dumps(run(), indent=2)



    if enhancements.get("pipeline"):

        @mcp.tool()

        def run_pipeline(task: str, target_file: str = "") -> str:

            """Prepare multi-agent pipeline handoff for a task."""

            from orchestrator import run_pipeline as pipeline

            return json.dumps(pipeline(task, target_file), indent=2)





_register_enhancement_tools()



if __name__ == "__main__":

    mcp.run()


