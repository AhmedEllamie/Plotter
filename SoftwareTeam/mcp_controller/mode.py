"""
SoftwareTeam Project Controller — Mode Switcher
Author: Ahmed Ellamie
Email: ahmed.ellamiee@gmail.com
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
STATE_PATH = BASE / "memory" / "state.json"

VALID_MODES = ("Init", "Architect", "Coder", "Reviewer", "Tester")


def set_mode(mode: str) -> dict:
    mode = mode.strip().capitalize()
    if mode == "Init":
        pass
    elif mode not in VALID_MODES and mode != "Init":
        for m in VALID_MODES:
            if m.lower() == mode.lower():
                mode = m
                break

    if not STATE_PATH.exists():
        state = {
            "_author": "Ahmed Ellamie",
            "_email": "ahmed.ellamiee@gmail.com",
            "mode": mode,
            "last_mode": mode,
        }
    else:
        with open(STATE_PATH, encoding="utf-8-sig") as f:
            state = json.load(f)
        state["mode"] = mode
        state["last_mode"] = mode

    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"Mode set to {mode}")
    return state


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python mode.py <Mode>")
        sys.exit(1)
    set_mode(sys.argv[1])
