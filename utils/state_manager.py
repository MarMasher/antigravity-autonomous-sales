"""
Shared state manager — all agents read/write through here.
Uses FileLock for thread-safety; JSON on disk for persistence.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from filelock import FileLock

STATE_FILE = Path(__file__).parent.parent / "shared_state.json"
LOCK_FILE  = STATE_FILE.with_suffix(".lock")


def _default_state() -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "config": {
            "niche": "all",
            "region": "USA and Europe",
            "email":            os.getenv("EMAIL_FROM", ""),
            "github_username":  os.getenv("GITHUB_USERNAME", ""),
            "instagram_handle": os.getenv("SENDER_HANDLE", ""),
        },
        "targets": [],
        "active_target": {},
        "builds": {},
        "outreach": {},
        "handoff_log": [],
        # ── Lifecycle v2 keys (preserved across safe-wipe) ──────────
        "contacted_emails":      [],   # set of emails already outreached
        "contacted_emails_meta": [],   # [{email, target_id, sent_at, followup_count}]
        "conversations":         {},   # {email: [{role, content, ts}]} full thread history
        "closed_lost":           [],   # emails politely declined — never outreach again
        "video_audits":          {},   # {target_id: {path, public_url, recorded_at}}
    }


# ── Core R/W ─────────────────────────────────────────────────────

def read_state() -> dict:
    with FileLock(str(LOCK_FILE)):
        if not STATE_FILE.exists():
            state = _default_state()
            STATE_FILE.write_text(json.dumps(state, indent=2))
            return state
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError as e:
            print(f"[StateManager] Warning: state file corrupted ({e}). Resetting to default.")
            state = _default_state()
            STATE_FILE.write_text(json.dumps(state, indent=2))
            return state


def write_state(state: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Helpers ───────────────────────────────────────────────────────

def log_action(agent_id: str, action: str, data: dict | None = None) -> None:
    """Atomic read-modify-write — single lock acquisition prevents race window."""
    with FileLock(str(LOCK_FILE)):
        if STATE_FILE.exists():
            state = json.loads(STATE_FILE.read_text())
        else:
            state = _default_state()
        state["handoff_log"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id":  agent_id,
            "action":    action,
            "data":      data or {},
        })
        STATE_FILE.write_text(json.dumps(state, indent=2))


def add_target(target: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else _default_state()
        if "id" not in target:
            target["id"] = str(uuid.uuid4())
        state["targets"].append(target)
        STATE_FILE.write_text(json.dumps(state, indent=2))


def set_active_target(target_id: str) -> None:
    with FileLock(str(LOCK_FILE)):
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else _default_state()
        matches = [t for t in state["targets"] if t.get("id") == target_id]
        state["active_target"] = matches[0] if matches else {}
        STATE_FILE.write_text(json.dumps(state, indent=2))


def update_build(target_id: str, build_data: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else _default_state()
        state["builds"][target_id] = build_data
        STATE_FILE.write_text(json.dumps(state, indent=2))


def update_outreach(target_id: str, outreach_data: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else _default_state()
        state["outreach"][target_id] = outreach_data
        STATE_FILE.write_text(json.dumps(state, indent=2))


# Keys that survive a safe-wipe — never lose outreach history or conversations
_PRESERVED_KEYS = [
    "contacted_emails",
    "contacted_emails_meta",
    "conversations",
    "closed_lost",
    "video_audits",
]


def reset_state() -> None:
    """
    Safe reset — clears transient cycle data (targets, builds, outreach)
    while preserving all long-lived history keys so we never re-contact
    the same businesses or lose conversation threads across cycles.
    """
    old = read_state()
    fresh = _default_state()
    for key in _PRESERVED_KEYS:
        if key in old:
            fresh[key] = old[key]
    write_state(fresh)
