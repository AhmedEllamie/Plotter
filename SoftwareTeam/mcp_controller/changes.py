"""
SoftwareTeam Project Controller — Change Recording
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).parent.parent


def record_change(file: str, summary: str, diff: str = "") -> dict:
    from init import load_config

    config = load_config()
    if not diff and config.get("enhancements", {}).get("diff_memory", False):
        try:
            from diff_memory import capture_git_diff
            diff = capture_git_diff(file)
        except ImportError:
            pass

    entry = {
        "file": file,
        "summary": summary,
        "diff": diff,
        "mode": "Coder",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    changes_path = BASE / "memory" / "recent_changes.json"
    changes = []
    if changes_path.exists():
        with open(changes_path, encoding="utf-8-sig") as f:
            data = json.load(f)
            changes = data if isinstance(data, list) else data.get("changes", [])

    changes.append(entry)
    with open(changes_path, "w", encoding="utf-8") as f:
        json.dump(changes, f, indent=2)

    md_path = BASE / "docs" / "recent_changes.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    if not md_path.exists():
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("<!--\nAuthor: Ahmed Ellamie\nEmail: ahmed.ellamiee@gmail.com\n-->\n\n# Recent Changes\n")

    with open(md_path, "a", encoding="utf-8") as f:
        f.write(f"\n- **{entry['timestamp']}** `{file}` — {summary}\n")

    return entry
