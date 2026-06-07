"""
daemon.py — Antigravity Autonomous Sales Machine v3.0
=======================================================
Full 4-phase lifecycle:

  Phase 1 — State reset (preserves all history: contacts, conversations, videos)
  Phase 2 — ApifyLeadAgent → new deduplicated leads → ResearcherAgent scoring
  Phase 3 — VideoAuditorAgent → per-lead screen recording → video outreach email
  Phase 4 — process_followups() → process_replies() (autonomous inbox closer)

Safety:
  • All agent calls use run_safe(max_retries=2) — crash → auto-heal → retry
  • Graceful Ctrl+C / SIGTERM shutdown
  • Hot .env reload every cycle
"""

import sys
import time
import logging
import signal
from pathlib import Path
from datetime import datetime

# Force UTF-8 for Windows console (solves UnicodeEncodeError with emojis)
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# ── Logging setup ──────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "daemon.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("antigravity")

# ── Config ─────────────────────────────────────────────────────────────────────
INTERVAL_HOURS = 24
MAX_TARGETS    = 10

_shutdown = False   # set True by signal handler for graceful exit


def _handle_exit(sig, frame):
    global _shutdown
    log.info("Shutdown signal received — will exit after current cycle completes.")
    _shutdown = True


signal.signal(signal.SIGINT,  _handle_exit)
signal.signal(signal.SIGTERM, _handle_exit)


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _phase_header(num: int, name: str) -> None:
    log.info("")
    log.info(f"  ── Phase {num}: {name} {'─' * (50 - len(name))}")


def _safe_call(fn, label: str, *args, **kwargs):
    """Call fn with *args/**kwargs; catch + log any exception without crashing the cycle."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        log.exception(f"[daemon] {label} raised an unhandled exception — continuing cycle")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  RUN CYCLE
# ══════════════════════════════════════════════════════════════════════════════

def run_cycle(cycle_num: int) -> dict:
    """
    Execute one full 4-phase autonomous sales cycle.
    Returns a stats dict for logging.
    """
    from dotenv import load_dotenv
    load_dotenv(override=True)   # re-read .env each cycle (hot config)

    import os
    from utils.state_manager import reset_state, read_state

    log.info(f"{'=' * 64}")
    log.info(f"  Cycle {cycle_num} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"{'=' * 64}")

    # ── Phase 1: Safe State Reset ─────────────────────────────────────────────
    _phase_header(1, "Safe State Reset")
    # reset_state() now preserves all 5 history keys (contacted_emails,
    # contacted_emails_meta, conversations, closed_lost, video_audits)
    reset_state()
    log.info("  State wiped. History keys preserved.")

    state = read_state()
    cfg   = state.get("config", {})
    niche  = os.getenv("TARGET_NICHE",  cfg.get("niche",  "landscaping"))
    region = os.getenv("TARGET_REGION", cfg.get("region", "Dallas TX"))
    log.info(f"  Niche: {niche!r}  |  Region: {region!r}  |  Cap: {MAX_TARGETS}")

    # ── Phase 2: Lead Generation + Research ───────────────────────────────────
    _phase_header(2, "Lead Generation → Research")

    # 2a. Apify — scrape fresh leads, deduplicated against contacted history
    from agents.apify_lead_agent import ApifyLeadAgent
    apify_agent = ApifyLeadAgent()
    raw_leads: list[dict] = []
    try:
        raw_leads = apify_agent.run_safe(
            max_retries=2,
            niche=niche,
            region=region,
            count=MAX_TARGETS,
        ) or []
    except Exception:
        log.exception("  [phase2] ApifyLeadAgent failed after retries — will rely on Researcher DDG")

    log.info(f"  New leads from Apify: {len(raw_leads)}")

    # 2b. ResearcherAgent — score + audit each lead's website via its own DDG search
    from agents.researcher import ResearcherAgent
    researcher = ResearcherAgent(model="deepseek")
    researcher_targets: list[dict] = []
    
    needed_targets = MAX_TARGETS - len(raw_leads)
    if needed_targets > 0:
        log.info(f"  Need {needed_targets} more leads — running Researcher fallback…")
        try:
            researcher_targets = researcher.run_safe(
                max_retries=2,
                niche=niche,
                region=region,
                count=needed_targets,
            ) or []
        except Exception:
            log.exception("  [phase2] ResearcherAgent failed after retries")

    # 2c. Merge: Apify leads (which have real emails from Google Maps) take priority;
    #     researcher's DDG leads fill the remaining cap up to MAX_TARGETS.
    #     Dedup by URL so we don't double-contact the same business.
    seen_urls: set[str] = set()
    scored_targets: list[dict] = []

    for lead in raw_leads:
        url = (lead.get("url") or "").rstrip("/")
        if url and url not in seen_urls:
            seen_urls.add(url)
            scored_targets.append(lead)

    for t in researcher_targets:
        if len(scored_targets) >= MAX_TARGETS:
            break
        url = (t.get("url") or "").rstrip("/")
        if url and url not in seen_urls:
            seen_urls.add(url)
            scored_targets.append(t)

    log.info(f"  Final scored targets: {len(scored_targets)} (Apify: {len(raw_leads)}, Researcher fill: {len(scored_targets) - len(raw_leads)})")

    # ── Phase 3: Video Audit + Email Outreach ─────────────────────────────────
    _phase_header(3, "Video Audit → Outreach")

    videos_recorded = 0
    emails_sent     = 0

    if scored_targets:
        # 3a. Record a video audit for every scored target (run_safe embedded in agent)
        from agents.video_auditor import VideoAuditorAgent
        video_agent = VideoAuditorAgent()
        video_results: dict = {}
        try:
            video_results = video_agent.run_safe(
                max_retries=2,
                targets=scored_targets,
            ) or {}
        except Exception:
            log.exception("  [phase3] VideoAuditorAgent failed — sending text-only emails")

        videos_recorded = sum(
            1 for v in video_results.values()
            if v.get("path") and not v.get("error")
        )
        log.info(f"  Videos recorded: {videos_recorded}/{len(scored_targets)}")

        # Save video audit metadata to state
        from utils.state_manager import read_state, write_state
        _st = read_state()
        _st.setdefault("video_audits", {}).update(video_results)
        write_state(_st)

        # 3b. Send the Humanized Video Template for each target
        from utils.email_sender import send_video_outreach_email
        from utils.nvidia_client import NvidiaClient
        llm = NvidiaClient()

        for t in scored_targets:
            biz = t.get("business_name", t.get("title", "this business"))
            niche = t.get("niche", "business")
            loc = t.get("location", "your area")
            
            if not t.get("icebreaker"):
                prompt = f"Write a 1-sentence personalized cold email opener (icebreaker) for a {niche} in {loc} named {biz}. Just the sentence, no quotes, no 'Hi name', sound natural."
                t["icebreaker"] = llm.complete(prompt, temperature=0.7).strip(' "')
                
            if not t.get("linkedin_msg"):
                prompt = f"Write a casual 2-sentence LinkedIn connection request message (under 300 chars) for the owner of {biz}. Mention you recorded a quick 45-sec video showing how to fix a leak on their mobile site. No quotes, no placeholders."
                t["linkedin_msg"] = llm.complete(prompt, temperature=0.7).strip(' "')

            tid = t.get("id") or ""
            audit_meta = video_results.get(tid, {})
            video_path = audit_meta.get("path")
            video_url  = audit_meta.get("public_url")

            sent = _safe_call(
                send_video_outreach_email,
                f"email→{t.get('business_name', '?')}",
                t,
                video_path=video_path,
                video_url=video_url,
            )
            if sent:
                emails_sent += 1

        log.info(f"  Emails sent: {emails_sent}/{len(scored_targets)}")

    # ── Phase 4: Follow-ups + Autonomous Reply Closer ─────────────────────────
    _phase_header(4, "Follow-ups + Reply Closer")

    # 4a. Follow-ups (existing 2-day / 5-day nudges)
    try:
        from utils.email_sender import process_followups
        log.info("  Processing follow-up nudges…")
        process_followups()
    except Exception:
        log.exception("  [phase4] process_followups() failed")

    # 4b. Autonomous inbox closer — read + classify + reply
    replies_stats = {"processed": 0}
    try:
        from utils.reply_processor import process_replies
        log.info("  Processing inbox replies…")
        replies_stats = process_replies() or {"processed": 0}
    except Exception:
        log.exception("  [phase4] process_replies() failed")

    replies_processed = replies_stats.get("processed", 0)
    log.info(
        f"  Replies: {replies_processed} processed "
        f"({replies_stats.get('yes',0)} yes · "
        f"{replies_stats.get('price',0)} price · "
        f"{replies_stats.get('no',0)} no)"
    )

    # ── Stats table ───────────────────────────────────────────────────────────
    stats = {
        "cycle":             cycle_num,
        "timestamp":         datetime.now().isoformat(),
        "niche":             niche,
        "region":            region,
        "new_leads_found":   len(raw_leads),
        "targets_scored":    len(scored_targets),
        "videos_recorded":   videos_recorded,
        "emails_sent":       emails_sent,
        "replies_processed": replies_processed,
    }

    _print_stats_table(stats, scored_targets)
    return stats


# ── Console summary table ─────────────────────────────────────────────────────

def _print_stats_table(stats: dict, targets: list[dict]) -> None:
    log.info("")
    log.info("  ╔══════════════════════════════════════════════════════════╗")
    log.info("  ║                 CYCLE SUMMARY                           ║")
    log.info("  ╠══════════════════════════════════════════════════════════╣")
    log.info(f"  ║  New Leads Found   : {stats['new_leads_found']:<35} ║")
    log.info(f"  ║  Leads Scored      : {stats['targets_scored']:<35} ║")
    log.info(f"  ║  Videos Recorded   : {stats['videos_recorded']:<35} ║")
    log.info(f"  ║  Emails Sent       : {stats['emails_sent']:<35} ║")
    log.info(f"  ║  Replies Processed : {stats['replies_processed']:<35} ║")
    log.info("  ╚══════════════════════════════════════════════════════════╝")
    log.info("")

    if targets:
        log.info(f"  {'#':<4} {'Business':<38} {'Score':>5}  {'Contact'}")
        log.info("  " + "─" * 60)
        for i, t in enumerate(targets, 1):
            biz     = (t.get("business_name") or t.get("title") or "?")[:36]
            score   = t.get("website_score", "?")
            contact = t.get("email") or t.get("phone") or "—"
            log.info(f"  {i:<4} {biz:<38} {score:>5}/10  {contact}")
        log.info("  " + "─" * 60)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

def main():
    log.info("")
    log.info("  ╔══════════════════════════════════════════╗")
    log.info("  ║  ANTIGRAVITY — Autonomous Sales Machine  ║")
    log.info("  ║  Full Lifecycle Pipeline v3.0            ║")
    log.info("  ╚══════════════════════════════════════════╝")
    log.info("")
    log.info(f"  Phases  : Lead Gen → Research → Video → Email → Reply Closer")
    log.info(f"  Interval: every {INTERVAL_HOURS}h")
    log.info(f"  Max leads: {MAX_TARGETS} per cycle")
    log.info(f"  Log file: {LOG_DIR / 'daemon.log'}")
    log.info("")

    cycle = 1
    while not _shutdown:
        t_start = time.time()
        try:
            stats = run_cycle(cycle)
            elapsed = time.time() - t_start
            log.info(
                f"Cycle {cycle} complete in {elapsed:.0f}s — "
                f"{stats['new_leads_found']} leads | "
                f"{stats['emails_sent']} emails | "
                f"{stats['replies_processed']} replies"
            )
        except Exception:
            log.exception(f"Cycle {cycle} crashed at top level")

        if _shutdown:
            break

        # Single-run mode (default): exit after one full cycle
        # To run continuously: comment out the break below and re-enable the sleep
        # log.info("Finished autonomous cycle. Exiting (single-run mode).")
        # break

        # ── Continuous mode (uncomment to enable) ──
        log.info(f"Sleeping {INTERVAL_HOURS}h until next cycle…")
        for _ in range(INTERVAL_HOURS * 3600):
            if _shutdown:
                break
            time.sleep(1)
        cycle += 1

    log.info("Antigravity daemon shut down cleanly. Goodbye.")
    sys.exit(0)


if __name__ == "__main__":
    main()
