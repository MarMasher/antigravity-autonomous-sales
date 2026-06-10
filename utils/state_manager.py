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

def _read_state_unlocked() -> dict:
    """Read and decode state without lock. Must be called inside a locked context."""
    if not STATE_FILE.exists():
        state = _default_state()
        _atomic_write(state)
        return state
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[StateManager] Warning: state file corrupted ({e}). Resetting to default.")
        state = _default_state()
        _atomic_write(state)
        return state

def read_state() -> dict:
    with FileLock(str(LOCK_FILE)):
        return _read_state_unlocked()

def _atomic_write(state: dict) -> None:
    """Helper to write state atomically using a temporary file."""
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)

def write_state(state: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        _atomic_write(state)


# ── Helpers ───────────────────────────────────────────────────────

def log_action(agent_id: str, action: str, data: dict | None = None) -> None:
    """Atomic read-modify-write — single lock acquisition prevents race window."""
    with FileLock(str(LOCK_FILE)):
        state = _read_state_unlocked()
        state["handoff_log"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id":  agent_id,
            "action":    action,
            "data":      data or {},
        })
        _atomic_write(state)


def add_target(target: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        state = _read_state_unlocked()
        if "id" not in target:
            target["id"] = str(uuid.uuid4())
        state["targets"].append(target)
        _atomic_write(state)


def set_active_target(target_id: str) -> None:
    with FileLock(str(LOCK_FILE)):
        state = _read_state_unlocked()
        matches = [t for t in state["targets"] if t.get("id") == target_id]
        state["active_target"] = matches[0] if matches else {}
        _atomic_write(state)


def update_build(target_id: str, build_data: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        state = _read_state_unlocked()
        state["builds"][target_id] = build_data
        _atomic_write(state)


def update_outreach(target_id: str, outreach_data: dict) -> None:
    with FileLock(str(LOCK_FILE)):
        state = _read_state_unlocked()
        state["outreach"][target_id] = outreach_data
        _atomic_write(state)


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
