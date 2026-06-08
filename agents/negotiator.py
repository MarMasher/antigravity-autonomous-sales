"""
Agent 5 — The Negotiator
{SENDER_NAME} pastes in the owner's reply → gets the optimal negotiation response instantly.
"""
from rich.console import Console
from agents.base_agent import BaseAgent
from utils.llm_client import LLMClient

console = Console()

SYSTEM_PROMPT = """You are a freelance web design negotiation coach.
Strategy: anchor high, never discount immediately, offer value-adds first,
create soft urgency, always close with a specific next step.
Pricing tiers: Starter $300-500 | Standard $500-900 | Premium $900-1500 | Retainer $50-100/mo
Anchor at the TOP of each tier. Come down only if they push back twice."""


class NegotiatorAgent(BaseAgent):
    agent_id = "negotiator"

    def __init__(self, model: str = "deepseek"):
        try:
            self.ai = LLMClient(model)
        except Exception as e:
            console.print(f"[red]Failed to initialize LLMClient: {e}[/red]")
            self.ai = None

    def run(self, owner_message: str, target_id: str | None = None, **kwargs):
        state   = self.state()
        target  = next(
            (t for t in state["targets"] if t["id"] == (target_id or "")),
            state.get("active_target", {}),
        )
        biz      = target.get("business_name", "this business")
        live_url = state.get("builds", {}).get(target_id or "", {}).get("live_url", "")

        console.rule("[bold blue]Agent 5 — Negotiator")
        self.log("start", {"owner_msg_preview": owner_message[:80]})

        prompt = f"""
Business: {biz}
Live demo URL: {live_url}
Your handle: {SENDER_HANDLE}

The business owner just replied with this message:
\"\"\"
{owner_message}
\"\"\"

Analyze their intent (curious / objecting / ready to buy / ghosting / negotiating price).
Then generate:

1. RECOMMENDED RESPONSE (copy-paste ready, under 120 words, sounds human)
2. REASONING (1 sentence — why this response)
3. WATCH FOR (what to look for in their next reply)
4. NEXT STEP IF THEY SAY YES (specific action for the salesperson to take)

Format clearly with those 4 headers.
"""
        try:
            if self.ai:
                response = self.ai.complete(prompt, system=SYSTEM_PROMPT, temperature=0.6, max_tokens=600)
            else:
                response = "Error: LLM client not initialized."
        except Exception as e:
            console.print(f"[red]LLM completion failed: {e}[/red]")
            response = "Error: Failed to generate response from LLM."

        console.print(response)
        self.log("response_generated", {"target": biz})

        # Single state read — avoids stale snapshot from a second self.state() call
        s = self.state()
        outreach = s.setdefault("outreach", {}).setdefault(target_id or "", {})
        outreach.setdefault("negotiation_log", []).append({
            "owner_msg": owner_message,
            "response":  response,
        })
        self.save(s)

        return response
