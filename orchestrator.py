"""
Antigravity Master Orchestrator
Usage:
  python orchestrator.py research          — Run Agent 1 (Researcher)
  python orchestrator.py build [target_id] — Run Agents 2+3 (Builder + Debugger)
  python orchestrator.py outreach [id]     — Run Agent 4 (Outreach)
  python orchestrator.py negotiate         — Run Agent 5 (Negotiator, interactive)
  python orchestrator.py status            — Print current shared state summary
  python orchestrator.py reset             — Reset shared state
"""
import sys
# Force UTF-8 for Windows console (solves UnicodeEncodeError with emojis)
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
from rich.console import Console
from rich.table import Table
from rich import box
from dotenv import load_dotenv

load_dotenv()

from utils.state_manager import read_state, reset_state, set_active_target
from agents.researcher  import ResearcherAgent
from agents.builder     import BuilderAgent
from agents.debugger    import DebuggerAgent
from agents.outreach    import OutreachAgent
from agents.negotiator  import NegotiatorAgent

console = Console()


# ── Commands ──────────────────────────────────────────────────────

def cmd_research():
    state  = read_state()
    cfg    = state.get("config", {})
    agent  = ResearcherAgent(model="deepseek")
    agent.run(niche=cfg.get("niche", "all"), region=cfg.get("region", "USA and Europe"))


def cmd_build(target_id: str | None = None):
    """Run Builder + Debugger in parallel (Builder leads, Debugger reviews)."""
    state = read_state()

    # Select target
    targets = state.get("targets", [])
    if not targets:
        console.print("[red]No targets found. Run 'research' first.[/red]")
        return

    if target_id:
        matches = [t for t in targets if t["id"] == target_id or str(t.get("rank","")) == target_id]
        if not matches:
            console.print(f"[red]Target '{target_id}' not found.[/red]")
            _list_targets(targets)
            return
        target = matches[0]
    else:
        _list_targets(targets)
        choice = console.input("[bold]Enter rank or ID to build: [/bold]").strip()
        matches = [t for t in targets if str(t.get("rank","")) == choice or t["id"] == choice]
        if not matches:
            console.print("[red]Invalid choice.[/red]")
            return
        target = matches[0]

    set_active_target(target["id"])
    tid = target["id"]

    builder  = BuilderAgent(model="deepseek")
    debugger = DebuggerAgent()

    # Builder runs first; debugger runs post-build
    build_data = builder.run(target_id=tid)

    if build_data.get("build_status") == "complete":
        report = debugger.run(target_id=tid)
        verdict = report.get("final_verdict", "FAIL")
        if verdict == "PASS":
            console.print("[bold green]✓ Debugger PASS — site is production-ready.[/bold green]")
            console.print(f"[dim]Run outreach: python orchestrator.py outreach {tid}[/dim]")
        else:
            console.print("[bold red]✗ Debugger FAIL — fix issues before running outreach.[/bold red]")
            issues = report.get("issues_found", []) + report.get("security_flags", [])
            for i in issues:
                console.print(f"  [red]→[/red] {i}")
            console.print(f"[dim]Re-run after fixing: python orchestrator.py build {tid}[/dim]")
    else:
        console.print("[yellow]Build had issues — skipping debugger.[/yellow]")


def cmd_outreach(target_id: str | None = None):
    state   = read_state()
    targets = state.get("targets", [])
    if not targets:
        console.print("[red]No targets. Run 'research' first.[/red]")
        return

    if not target_id:
        _list_targets(targets)
        choice = console.input("[bold]Enter rank or ID: [/bold]").strip()
        matches = [t for t in targets if str(t.get("rank","")) == choice or t["id"] == choice]
        target_id = matches[0]["id"] if matches else None

    if not target_id:
        console.print("[red]No valid target.[/red]")
        return

    # ── Debugger gate: block outreach if site QA has not PASSed ──
    build = state.get("builds", {}).get(target_id, {})
    debugger_report = build.get("debugger_report", {})
    verdict = debugger_report.get("final_verdict", None)

    if verdict is None:
        console.print(
            "[red]No debugger report found for this target. "
            f"Run 'build' first: python orchestrator.py build {target_id}[/red]"
        )
        return
    if verdict != "PASS":
        console.print("[bold red]Outreach BLOCKED — debugger verdict is FAIL.[/bold red]")
        issues = debugger_report.get("issues_found", []) + debugger_report.get("security_flags", [])
        for i in issues:
            console.print(f"  [red]→[/red] {i}")
        console.print(
            f"[dim]Fix the site issues then rebuild: python orchestrator.py build {target_id}[/dim]"
        )
        return

    agent = OutreachAgent(model="deepseek")
    agent.run(target_id=target_id)


def cmd_negotiate():
    state   = read_state()
    targets = state.get("targets", [])
    if targets:
        _list_targets(targets)
        choice = console.input("[bold]Target rank or ID (or Enter to skip): [/bold]").strip()
        matches = [t for t in targets if str(t.get("rank","")) == choice or t["id"] == choice]
        target_id = matches[0]["id"] if matches else ""
    else:
        target_id = ""

    console.print("[bold]Paste the owner's reply below. Press Enter twice when done:[/bold]")
    lines, empty = [], 0
    while empty < 1:
        line = input()
        if line == "":
            empty += 1
        else:
            empty = 0
            lines.append(line)
    owner_msg = "\n".join(lines)

    agent = NegotiatorAgent(model="deepseek")
    agent.run(owner_message=owner_msg, target_id=target_id)


def cmd_status():
    state = read_state()
    console.rule("[bold]Shared State Summary")
    console.print(f"Session ID : {state['session_id']}")
    console.print(f"Targets    : {len(state.get('targets',[]))}")
    console.print(f"Builds     : {len(state.get('builds',{}))}")
    console.print(f"Outreach   : {len(state.get('outreach',{}))}")
    console.print(f"Log entries: {len(state.get('handoff_log',[]))}")

    targets = state.get("targets", [])
    if targets:
        _list_targets(targets)

    blockers = state.get("blockers", [])
    if blockers:
        console.print("[bold red]BLOCKERS:[/bold red]")
        for b in blockers:
            console.print(f"  [{b['agent']}] {b['reason']}")


def cmd_reset():
    confirm = console.input("[bold red]Reset ALL state? (yes/no): [/bold red]").strip()
    if confirm == "yes":
        reset_state()
        console.print("[green]State reset.[/green]")
    else:
        console.print("Aborted.")


# ── Helpers ───────────────────────────────────────────────────────

def _list_targets(targets: list):
    t = Table("Rank", "Name", "Niche", "Location", "Site Score", "ID (short)", box=box.SIMPLE)
    for tgt in targets:
        t.add_row(
            str(tgt.get("rank", "?")),
            tgt.get("business_name", tgt.get("title", "—"))[:30],
            tgt.get("niche", "—"),
            tgt.get("location", "—"),
            str(tgt.get("website_score", "?")),
            tgt.get("id", "")[:8],
        )
    console.print(t)


# ── Entry point ───────────────────────────────────────────────────

COMMANDS = {
    "research":  cmd_research,
    "build":     cmd_build,
    "outreach":  cmd_outreach,
    "negotiate": cmd_negotiate,
    "status":    cmd_status,
    "reset":     cmd_reset,
}

if __name__ == "__main__":
    args = sys.argv[1:]
    cmd  = args[0] if args else "status"

    if cmd not in COMMANDS:
        console.print(f"[red]Unknown command '{cmd}'[/red]")
        console.print(f"Available: {', '.join(COMMANDS)}")
        sys.exit(1)

    fn    = COMMANDS[cmd]
    extra = args[1] if len(args) > 1 else None

    if extra and cmd in ("build", "outreach"):
        fn(target_id=extra)
    else:
        fn()
