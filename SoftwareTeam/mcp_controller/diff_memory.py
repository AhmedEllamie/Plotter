"""
SoftwareTeam Project Controller — Git Diff Capture
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
import subprocess
from pathlib import Path

from memory_utils import load_config, project_root


def capture_git_diff(file: str) -> str:
    config = load_config()
    if not config.get("enhancements", {}).get("diff_memory", False):
        return ""

    root = project_root()
    try:
        result = subprocess.run(
            ["git", "diff", "--", file],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ""
