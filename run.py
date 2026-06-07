"""
Antigravity — Lead Research & Outreach Pipeline
===============================================
Runs the streamlined pipeline:
  1. Researcher  → finds 10 targets, scrapes contacts, emails rich dossier
  2. Outreach    → generates personalized DMs per target

Usage:
  python run.py                  # full research + outreach loop
  python run.py --targets 3      # only process top N targets
  python run.py --skip-research  # skip research, use existing state targets
  python run.py --loop           # repeat every 24 h
"""

import time
import argparse
import sys

# Force UTF-8 for Windows console (solves UnicodeEncodeError with emojis)
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import traceback
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich import box

load_dotenv()

from utils.state_manager import read_state, write_state, reset_state
from agents.researcher   import ResearcherAgent
from agents.outreach     import OutreachAgent

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# Status tracker
# ─────────────────────────────────────────────────────────────────────────────

class PipelineStatus:
    """Maintains a rich live-updating status table."""

    def __init__(self):
        self.rows: list[dict] = []

    def add(self, rank: int, name: str):
        self.rows.append({
            "rank": rank, "name": name,
            "research": "⏳", "contact": "⏳", "outreach": "⏳",
            "email": "—",
        })

    def update(self, rank: int, **kwargs):
        for r in self.rows:
            if r["rank"] == rank:
                r.update(kwargs)

    def table(self) -> Table:
        t = Table(
            "#", "Business", "Research", "Contact Scrape", "Outreach DM", "Contact Found",
            box=box.ROUNDED, style="bold", header_style="bold magenta",
            show_lines=True,
        )
        for r in self.rows:
            t.add_row(
                str(r["rank"]),
                r["name"][:35],
                r["research"], r["contact"], r["outreach"],
                r["email"][:40],
            )
        return t


# ─────────────────────────────────────────────────────────────────────────────
# Core pipeline
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(max_targets: int = 10, skip_research: bool = False):
    console.print(Panel.fit(
        "[bold cyan]ANTIGRAVITY — Streamlined Lead Gen & Outreach[/bold cyan]\n"
        f"[dim]Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}[/dim]",
        border_style="cyan",
    ))

    state   = read_state()
    status  = PipelineStatus()

    # ── AGENT 1: Researcher ───────────────────────────────────────
    if not skip_research:
        console.rule("[bold cyan]Phase 1 — Deep Research")
        try:
            researcher = ResearcherAgent(model="deepseek")
            targets = researcher.run(
                niche=state["config"].get("niche", "all"),
                region=state["config"].get("region", "USA and Europe"),
                count=max_targets,
            )
        except Exception as e:
            console.print(f"[bold red]Researcher failed: {e}[/bold red]")
            traceback.print_exc()
            targets = []
    else:
        console.print("[yellow]Skipping research — using existing targets from state.[/yellow]")
        targets = read_state().get("targets", [])

    if not targets:
        console.print("[red]No targets found. Exiting.[/red]")
        return

    targets = targets[:max_targets]
    for t in targets:
        status.add(t.get("rank", 0), t.get("business_name", t.get("title", "?")))

    console.print(f"\n[green]✓ {len(targets)} targets ready[/green]\n")

    # ── AGENT 4: Outreach (per target) ───────────────────────────
    outreach = OutreachAgent(model="deepseek")

    with Live(status.table(), refresh_per_second=2, console=console) as live:
        for target in targets:
            rank = target.get("rank", 0)
            tid  = target.get("id", "")
            biz  = target.get("business_name", target.get("title", "?"))
            contact = target.get("email") or target.get("phone") or target.get("instagram") or "—"

            # Set as active
            s = read_state()
            s["active_target"] = target
            write_state(s)

            status.update(rank, research="✅", contact="✅", email=contact)
            live.update(status.table())

            # ── AGENT 4: Outreach DM Generation ───────────────────
            status.update(rank, outreach="🔨")
            live.update(status.table())
            try:
                outreach.run(target_id=tid)
                status.update(rank, outreach="✅")
            except Exception as e:
                console.print(f"\n[red][Outreach] {biz}: {e}[/red]")
                status.update(rank, outreach="❌")
            
            live.update(status.table())
            time.sleep(1)

    # ── Final summary ─────────────────────────────────────────────
    console.print("\n")
    console.print(status.table())

    final_state = read_state()
    console.print(Panel.fit(
        f"[bold green]Pipeline complete![/bold green]\n"
        f"Targets researched: {len(targets)}\n"
        f"Outreach DMs ready: {len(final_state.get('outreach', {}))}\n\n"
        f"[dim]Check your email for the rich dossier with all contact info.\n"
        f"Run [bold]python orchestrator.py negotiate[/bold] when an owner replies.[/dim]",
        border_style="green",
    ))


# ─────────────────────────────────────────────────────────────────────────────
# Continuous loop mode
# ─────────────────────────────────────────────────────────────────────────────

def run_loop(max_targets: int, interval_hours: int = 24):
    """Runs the pipeline on a schedule — resets state and reruns every N hours."""
    cycle = 1
    while True:
        console.rule(f"[bold magenta]── Cycle {cycle} ──")
        # Preserve outreach history across cycles — same fix as daemon.py
        old_state = read_state()
        contacted_emails = list(old_state.get("contacted_emails", []))
        reset_state()
        new_state = read_state()
        new_state["contacted_emails"] = contacted_emails
        write_state(new_state)
        run_pipeline(max_targets=max_targets)
        next_run = datetime.now().strftime("%H:%M:%S")
        console.print(
            f"\n[dim]Cycle {cycle} done. Next run in {interval_hours}h "
            f"(sleeping from {next_run})…[/dim]\n"
        )
        cycle += 1
        time.sleep(interval_hours * 3600)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Antigravity Streamlined Pipeline")
    parser.add_argument("--targets",       type=int,  default=10,    help="Max targets to process")
    parser.add_argument("--skip-research", action="store_true",       help="Use existing targets")
    parser.add_argument("--loop",          action="store_true",       help="Run continuously every 24 h")
    parser.add_argument("--interval",      type=int,  default=24,    help="Loop interval in hours")
    args = parser.parse_args()

    if args.loop:
        run_loop(max_targets=args.targets, interval_hours=args.interval)
    else:
        run_pipeline(max_targets=args.targets, skip_research=args.skip_research)
