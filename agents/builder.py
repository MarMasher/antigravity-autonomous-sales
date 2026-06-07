"""
Agent 2 — The Builder
Generates a 4-page HTML+CSS+JS website using Puter.js for AI features.

Pages: index.html / services.html / about.html / contact.html
AI widget on every page uses best available model (Opus 4.5 → GPT-4o → Gemini etc.)
Hosted on GitHub Pages (free, instant, no build step).
"""
import re
from rich.console import Console
from agents.base_agent   import BaseAgent
from utils.github_client import create_repo, push_file, get_repo_url, enable_pages
from utils.state_manager import update_build
from utils.site_pages    import generate_all_pages

console = Console()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9-]", "-", name.lower().strip()).strip("-")
    return s[:40] or "business"


class BuilderAgent(BaseAgent):
    agent_id = "builder"

    def __init__(self, model: str = "deepseek"):
        pass  # no AI needed — templates are instant

    def run(self, target_id: str | None = None, **kwargs):
        state  = self.state()
        target = state.get("active_target") or {}

        if not target:
            targets = state.get("targets", [])
            if target_id:
                hits = [t for t in targets if t.get("id") == target_id]
                target = hits[0] if hits else {}
            if not target and targets:
                target = targets[0]

        if not target:
            self.halt("No active_target in state.")

        biz   = target.get("business_name", target.get("title", "Business"))
        niche = target.get("niche", "service")
        loc   = target.get("location", "your area")
        slug  = _slug(biz)
        repo  = slug + "-site"
        gh_user = state["config"].get("github_username") or os.getenv("GITHUB_USERNAME", "")

        console.rule(f"[bold cyan]Agent 2 — Builder: {biz}")
        self.log("start", {"target": biz, "repo": repo})

        # ── Step 1: Create GitHub repo ────────────────────────────
        console.print(f"[cyan]Creating repo:[/cyan] {repo}")
        try:
            create_repo(repo, description=f"Website for {biz} — {niche} in {loc}", private=False)
            console.print("[green]✓ Repo created[/green]")
        except Exception as e:
            console.print(f"[yellow]Repo note: {e}[/yellow]")

        # ── Step 2: Generate all pages instantly ──────────────────
        console.print("[cyan]Generating 4-page Puter.js site…[/cyan]")
        pages = generate_all_pages(biz, niche, loc)
        console.print(f"[green]✓ {len(pages)} pages generated (instant)[/green]")

        # ── Step 3: Push to GitHub ────────────────────────────────
        console.print("[cyan]Pushing to GitHub…[/cyan]")
        push_ok = 0
        for filename, html in pages.items():
            try:
                push_file(repo, filename, html, message=f"feat: add {filename}")
                console.print(f"  [dim]✓ {filename}[/dim]")
                push_ok += 1
            except Exception as e:
                console.print(f"  [yellow]⚠ {filename}: {e}[/yellow]")

        repo_url = get_repo_url(repo)

        # ── Step 4: Enable GitHub Pages ───────────────────────────
        live_url = f"https://{gh_user.lower()}.github.io/{repo}/"
        try:
            enable_pages(repo)
            console.print(f"[bold green]✓ GitHub Pages enabled → {live_url}[/bold green]")
        except Exception as e:
            console.print(f"[yellow]Pages: {e}[/yellow]")
            live_url = repo_url   # fallback to repo URL

        build_data = {
            "build_status": "complete" if push_ok > 0 else "partial",
            "live_url":     live_url,
            "repo_url":     repo_url,
            "pages_pushed": push_ok,
            "target_id":    target.get("id", ""),
        }
        update_build(target.get("id", ""), build_data)
        self.log("complete", build_data)
        console.rule(f"[bold green]Builder complete — {push_ok} pages live")
        return build_data
