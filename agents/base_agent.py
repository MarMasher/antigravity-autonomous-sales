"""
BaseAgent — all 5 agents inherit from this.
Provides: shared state access, logging, blocker signalling,
and self-healing via AutoHealer.
"""
from abc import ABC, abstractmethod
from utils.state_manager import read_state, write_state, log_action
from utils.auto_healer   import heal_and_retry


class BaseAgent(ABC):
    agent_id: str = "base"

    # ── Shared state ──────────────────────────────────────────────

    def log(self, action: str, data: dict | None = None) -> None:
        log_action(self.agent_id, action, data)

    def state(self) -> dict:
        return read_state()

    def save(self, state: dict) -> None:
        write_state(state)

    def halt(self, reason: str) -> None:
        """Write a blocker to state and raise so the orchestrator can notify the operator."""
        s = self.state()
        s.setdefault("blockers", []).append({"agent": self.agent_id, "reason": reason})
        self.save(s)
        raise RuntimeError(f"[{self.agent_id}] BLOCKED: {reason}")

    # ── Self-healing run wrapper ───────────────────────────────────

    def run_safe(self, max_retries: int = 3, **kwargs):
        """
        Calls self.run(**kwargs) with full auto-healing.
        On any exception:
          1. Identifies the failing source file from the traceback
          2. Sends error + file to the AI (GLM → Kimi → DeepSeek)
          3. Patches the file and reloads the module
          4. Retries up to max_retries times

        Use this from the daemon/orchestrator instead of calling .run() directly.
        """
        return heal_and_retry(
            fn         = self.run,
            fn_kwargs  = kwargs,
            max_retries= max_retries,
            agent_name = self.agent_id,
        )

    # ── Subclass interface ────────────────────────────────────────

    @abstractmethod
    def run(self, **kwargs):
        """Override in each agent. Called by run_safe()."""
        ...
