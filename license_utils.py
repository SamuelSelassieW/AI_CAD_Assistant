import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
LICENSE_FILE = BASE_DIR / "license.json"
DEFAULT_FREE_CREDITS = 3

def load_state() -> dict:
    if not LICENSE_FILE.exists():
        # free edition with N trial pro credits
        return {"edition": "free", "pro_credits": DEFAULT_FREE_CREDITS}
    try:
        data = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
        data.setdefault("edition", "free")
        data.setdefault("pro_credits", 0)
        return data
    except Exception:
        return {"edition": "free", "pro_credits": DEFAULT_FREE_CREDITS}

def save_state(state: dict) -> None:
    LICENSE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")

def is_pro(state: dict) -> bool:
    return str(state.get("edition", "free")).lower() == "pro"

def can_use_pro_feature(state: dict) -> bool:
    """True if Pro edition, or free edition with remaining trial credits."""
    return is_pro(state) or state.get("pro_credits", 0) > 0

def consume_pro_credit(state: dict) -> None:
    if not is_pro(state):
        credits = state.get("pro_credits", 0)
        if credits > 0:
            state["pro_credits"] = credits - 1
            save_state(state)