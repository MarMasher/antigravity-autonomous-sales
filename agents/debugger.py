"""
Agent 3 — The Debugger
Post-build QA gate. Runs 3 sequential checks on every deployed site.
Blocks outreach until PASS verdict.

Checks (in order):
  1. HTTP reachability on 4 pages (/, /services, /about, /contact)
  2. SSL / HTTPS presence
  3. HTML quality on home page (meta description, viewport, h1)

Report shape:
  {
    "issues_found":      [],  # blocks outreach
    "issues_fixed":      [],  # reserved — auto-repair not yet implemented
    "lighthouse_scores": {},  # reserved — Lighthouse pending
    "security_flags":    [],  # HTTPS issues land here
    "final_verdict":     "PASS" | "FAIL",
  }

PASS  → issues_found is empty AND security_flags is empty
FAIL  → any entry in either list
"""
import time
import requests
from rich.console import Console
from agents.base_agent import BaseAgent

console = Console()

HEADERS      = {"User-Agent": "Mozilla/5.0 (Antigravity-Debugger/1.0)"}
TIMEOUT      = 15          # seconds per request
PAGES        = ["/", "/services", "/about", "/contact"]
# GitHub Pages can take up to 90s to propagate after first push.
# We retry up to MAX_REACH_RETRIES times with REACH_RETRY_DELAY seconds between.
MAX_REACH_RETRIES  = 3
REACH_RETRY_DELAY  = 30    # seconds


class DebuggerAgent(BaseAgent):
    agent_id = "debugger"

    # ── Public entry point ─────────────────────────────────────────

    def run(self, target_id: str | None = None, **kwargs):
        state    = self.state()
        build    = state.get("builds", {}).get(target_id or "", {})
        live_url = build.get("live_url", "").rstrip("/")

        console.rule("[bold yellow]Agent 3 — Debugger")
        self.log("start", {"target_id": target_id, "live_url": live_url})

        from typing import Any
        report: dict[str, Any] = {
            "issues_found":      [],
            "issues_fixed":      [],
            "lighthouse_scores": {},
            "security_flags":    [],
            "final_verdict":     "FAIL",
        }

        # Guard: need a valid HTTP(S) URL to proceed at all
        if not live_url or not live_url.startswith("http"):
            report["issues_found"].append("No valid live URL to audit.")
            self._write(target_id, report)
            return report

        # ── Check 1: HTTP reachability ─────────────────────────────
        home_response = self._check_reachability(live_url, report)

        # ── Check 2: SSL / HTTPS ──────────────────────────────────
        self._check_ssl(live_url, report)

        # ── Check 3: HTML quality (reuse home response from Check 1)
        self._check_html_quality(live_url, home_response, report)

        # ── Verdict ────────────────────────────────────────────────
        total_issues = len(report["issues_found"]) + len(report["security_flags"])
        if total_issues == 0:
            report["final_verdict"] = "PASS"
            console.print("[bold green]✓ Debugger verdict: PASS[/bold green]")
        else:
            report["final_verdict"] = "FAIL"
            console.print(
                f"[bold red]✗ Debugger verdict: FAIL "
                f"({len(report['issues_found'])} issue(s), "
                f"{len(report['security_flags'])} security flag(s))[/bold red]"
            )
            for issue in report["issues_found"]:
                console.print(f"  [red]• Issue:[/red] {issue}")
            for flag in report["security_flags"]:
                console.print(f"  [yellow]• Security:[/yellow] {flag}")

        self._write(target_id, report)
        return report

    # ── Check implementations ──────────────────────────────────────

    def _check_reachability(self, live_url: str, report: dict):
        """
        Check 1 — HTTP 200 on 4 pages.
        Retries up to MAX_REACH_RETRIES times to handle GitHub Pages propagation lag.
        Returns the home-page Response object if successful (used by Check 3),
        or None if home page never returned 200.
        """
        console.print(f"\n[cyan]Check 1 — HTTP Reachability[/cyan]")
        home_response = None

        for attempt in range(1, MAX_REACH_RETRIES + 1):
            attempt_issues = []

            for path in PAGES:
                url = live_url + path
                try:
                    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
                    if r.status_code == 200:
                        console.print(f"  [green]✓[/green] {url}")
                        if path == "/" and home_response is None:
                            home_response = r           # cache for Check 3
                    else:
                        attempt_issues.append(f"HTTP {r.status_code} on {url}")
                        console.print(f"  [red]✗[/red] {url}  →  HTTP {r.status_code}")
                except Exception as e:
                    attempt_issues.append(f"Unreachable: {url} — {e}")
                    console.print(f"  [red]✗[/red] {url}  →  {e}")

            if not attempt_issues:
                break   # all pages OK — no retry needed

            if attempt < MAX_REACH_RETRIES:
                console.print(
                    f"  [yellow]Attempt {attempt}/{MAX_REACH_RETRIES} had issues. "
                    f"Waiting {REACH_RETRY_DELAY}s (GitHub Pages propagation)…[/yellow]"
                )
                time.sleep(REACH_RETRY_DELAY)
            else:
                # Final attempt still has issues — add them to report
                report["issues_found"].extend(attempt_issues)

        return home_response

    def _check_ssl(self, live_url: str, report: dict):
        """Check 2 — HTTPS presence. Failures go to security_flags, not issues_found."""
        console.print(f"\n[cyan]Check 2 — SSL / HTTPS[/cyan]")
        if live_url.startswith("https://"):
            console.print("  [green]✓[/green] HTTPS confirmed")
        else:
            flag = "Live URL is plain HTTP — no SSL/TLS certificate in use."
            report["security_flags"].append(flag)
            console.print(f"  [yellow]⚠[/yellow]  {flag}")

    def _check_html_quality(self, live_url: str, home_response, report: dict):
        """
        Check 3 — HTML quality on home page.
        Re-uses the cached response from Check 1 to avoid a second network round-trip.
        Falls back to a fresh fetch only if Check 1 never got a 200 for home.
        """
        console.print(f"\n[cyan]Check 3 — HTML Quality[/cyan]")
        try:
            from bs4 import BeautifulSoup

            if home_response is None:
                # Home page was never reachable — attempt a direct fetch for HTML audit
                home_response = requests.get(
                    live_url + "/", headers=HEADERS, timeout=TIMEOUT
                )

            soup = BeautifulSoup(home_response.text, "lxml")

            # a) Meta description (SEO)
            if soup.find("meta", attrs={"name": "description"}):
                console.print("  [green]✓[/green] <meta name=\"description\"> present")
            else:
                issue = "Missing <meta name='description'> — SEO will suffer"
                report["issues_found"].append(issue)
                console.print(f"  [red]✗[/red] {issue}")

            # b) Viewport meta (mobile-readiness)
            if soup.find("meta", attrs={"name": "viewport"}):
                console.print("  [green]✓[/green] Viewport meta present")
            else:
                issue = "Missing <meta name='viewport'> — site is not mobile-ready"
                report["issues_found"].append(issue)
                console.print(f"  [red]✗[/red] {issue}")

            # c) H1 heading (heading structure)
            if soup.find("h1"):
                console.print("  [green]✓[/green] <h1> present")
            else:
                issue = "No <h1> found on home page — heading structure broken"
                report["issues_found"].append(issue)
                console.print(f"  [red]✗[/red] {issue}")

        except ImportError:
            report["issues_found"].append(
                "beautifulsoup4 or lxml not installed — run: pip install beautifulsoup4 lxml"
            )
        except Exception as e:
            report["issues_found"].append(f"HTML parse error: {e}")

    # ── State write-back ───────────────────────────────────────────

    def _write(self, target_id: str | None, report: dict):
        """Persist the debugger report into shared state."""
        if target_id:
            state = self.state()
            if target_id in state.get("builds", {}):
                state["builds"][target_id]["debugger_report"] = report
                self.save(state)
        self.log("complete", {
            "verdict":       report["final_verdict"],
            "issues_count":  len(report["issues_found"]),
            "security_count": len(report["security_flags"]),
        })

    # ── Extension point ────────────────────────────────────────────
    # To add a new check, follow this pattern inside run() before the Verdict block:
    #
    #   # ── Check N: [Name] ───────────────────────────────────────
    #   try:
    #       [your check logic]
    #       if [fail condition]:
    #           report["issues_found"].append("[clear description]")
    #   except Exception as e:
    #       report["issues_found"].append(f"[Check N error]: {e}")
    #
    # The verdict logic handles it automatically — no other changes needed.
