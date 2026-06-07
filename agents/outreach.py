"""
Agent 4 - The Cold Outreach Agent
Generates human DM scripts + full objection-handling tree for the salesperson to send manually.
"""
from rich.console import Console
from agents.base_agent import BaseAgent
from utils.nvidia_client import NvidiaClient
from utils.state_manager import update_outreach

console = Console()

SYSTEM_PROMPT = """You write hyper-human Instagram DMs for a freelance web designer.
Sound like a real local person. No corporate language. No emojis spam. Under 100 words for openers.
Never fabricate reviews or stats."""


class OutreachAgent(BaseAgent):
    agent_id = "outreach"

    def __init__(self, model: str = "deepseek"):
        self.ai = NvidiaClient(model)

    def run(self, target_id: str | None = None, **kwargs):
        state    = self.state()
        build    = state.get("builds", {}).get(target_id or "", {})
        live_url = build.get("live_url", "PENDING")

        # Find target — prefer explicit target_id, fall back to active_target
        target = next(
            (t for t in state["targets"] if t["id"] == (target_id or "")),
            state.get("active_target", {}),
        )
        if not target:
            self.halt("No target found in state for outreach generation.")

        # Resolve the canonical ID — never key on "" in state
        resolved_id = target_id or target.get("id") or ""

        biz   = target.get("business_name", "Business")
        niche = target.get("niche", "service")
        loc   = target.get("location", "")
        score = target.get("website_score", "low")
        pain  = target.get("pain_points", [])

        console.rule(f"[bold magenta]Agent 4 — Outreach: {biz}")
        self.log("start", {"target": biz, "live_url": live_url})

        opening = self._gen_opening(biz, niche, loc, score, pain, live_url)
        tree    = self._gen_objections(biz, live_url)
        followups = self._gen_followups(biz, live_url)

        doc = self._format_doc(biz, target.get("ig_handle", "@" + biz.lower().replace(" ", "")),
                               live_url, opening, tree, followups)

        update_outreach(resolved_id, {
            "opening_dm": opening,
            "objection_tree": tree,
            "followups": followups,
            "full_doc": doc,
        })
        self.log("complete", {"target": biz})

        console.print(doc)
        console.rule("[bold green]Outreach doc generated")
        return doc

    # ── Generators ────────────────────────────────────────────────

    def _gen_opening(self, biz, niche, loc, score, pain, live_url) -> str:
        demo_context = f"I built them a free custom design demo: {live_url}" if live_url != "PENDING" else "I'd love to build them a free custom design concept to show them what's possible."
        call_to_action = "End with showing them the demo link" if live_url != "PENDING" else "End by asking if they are open to seeing a free custom design concept"
        
        prompt = (
            f"Write an opening Instagram DM for a {niche} business called \"{biz}\" in {loc}.\n"
            f"Their current website score is {score}/10. Pain points: {pain}.\n"
            f"{demo_context}\n\n"
            "Rules:\n"
            "- Under 100 words\n"
            "- No \"Hey there!\" opener\n"
            "- Force the AI to use ONE specific detail from their business (e.g., 'Saw your recent post about...', 'Noticed you do {niche} in {loc}...')\n"
            f"- {call_to_action}, not asking for a meeting\n"
            "- Sound like a local freelancer, not an agency\n"
        )
        return self.ai.complete(prompt, system=SYSTEM_PROMPT, temperature=0.8, max_tokens=300)

    def _gen_objections(self, biz, live_url) -> str:
        demo_context = f"Live demo: {live_url}" if live_url != "PENDING" else ""
        prompt = (
            f"Generate pre-written Instagram DM responses for these objections about building a website for \"{biz}\".\n"
            f"{demo_context}\n\n"
            "Objections to handle (one response each, under 80 words each):\n"
            "1. \"How much does it cost?\"\n"
            "2. \"I already have a website\"\n"
            "3. \"Not interested\"\n"
            "4. \"Who are you?\"\n"
            "5. \"Can I see examples?\"\n"
            "6. \"Let me think about it\"\n\n"
            "Format as numbered list. Sound human. Never discount immediately - offer value-adds first.\n"
        )
        return self.ai.complete(prompt, system=SYSTEM_PROMPT, temperature=0.7, max_tokens=800)

    def _gen_followups(self, biz, live_url) -> str:
        bump_msg = (
            f"- Day 2 bump (if no reply) - gentle, reference the demo: {live_url}"
            if live_url != "PENDING" else
            "- Day 2 bump (if no reply) - gentle, just checking if they saw the previous message"
        )
        prompt = (
            f"Write follow-up DMs for \"{biz}\" if they do not reply.\n\n"
            "Write:\n"
            f"{bump_msg}\n"
            "- Day 5 final message - short, leave door open, no pressure\n\n"
            "Both under 60 words each.\n"
        )
        return self.ai.complete(prompt, system=SYSTEM_PROMPT, temperature=0.7, max_tokens=400)

    def _format_doc(self, biz, handle, live_url, opening, tree, followups) -> str:
        sep = '-' * 60
        return (
            f"\n{sep}\n"
            f"TARGET: {biz} ({handle})\n"
            f"LINKS: {live_url}\n"
            f"{sep}\n\n"
            f"OPENING DM:\n{opening}\n\n"
            f"OBJECTION RESPONSES:\n{tree}\n\n"
            f"FOLLOW-UP SCHEDULE:\n"
            f"Day 0:  Send opening DM\n"
            f"Day 2:  If no reply ->\n"
            f"{followups}\n"
            f"{sep}\n"
        )
