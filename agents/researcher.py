"""
researcher.py — Antigravity Lead Researcher
=============================================
Sweeps all niches × all locations (shuffled randomly each run).
Audits every site, scrapes every contact detail, ranks by opportunity,
and sends a premium HTML dossier email — zero AI calls required.
"""

import re
import uuid
import random
import logging
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from agents.base_agent import BaseAgent
from utils.llm_client import LLMClient
from utils.web_search import search_businesses, audit_website, scrape_contacts
from utils.email_sender import send_dossier_email, send_outreach_emails

log     = logging.getLogger("antigravity.researcher")
console = Console()

AGGREGATORS = [
    "yelp.com", "yellowpages.com", "thumbtack.com", "angi.com", "homeadvisor.com",
    "bbb.org", "expertise.com", "houzz.com", "porch.com", "nextdoor.com",
    "groupon.com", "mapquest.com", "chamberofcommerce.com", "bark.com", "checkatrade.com"
]

# ── Master niche list ─────────────────────────────────────────────────────────
ALL_NICHES: list[str] = [
    # Auto / Transport
    "auto detailing", "mobile car wash", "auto repair shop", "car wrap",
    "tire shop", "windshield repair", "towing service", "car rental",
    # Home Services
    "landscaping", "lawn care", "house cleaning", "pressure washing",
    "window cleaning", "gutter cleaning", "junk removal", "move-out cleaning",
    "carpet cleaning", "upholstery cleaning", "chimney sweep", "dryer vent cleaning",
    # Trades
    "HVAC", "plumbing", "electrician", "painting contractor", "roofing",
    "handyman", "general contractor", "flooring contractor", "drywall contractor",
    "fence installation", "deck builder", "concrete contractor", "waterproofing",
    # Outdoor / Property
    "pest control", "pool service", "irrigation system", "tree service",
    "snow removal", "power washing", "graffiti removal",
    # Personal Services
    "barbershop", "nail salon", "massage therapy", "personal trainer",
    "dog grooming", "dog walking", "pet boarding", "tattoo studio",
    # Food & Hospitality
    "food truck", "catering service", "meal prep service", "bakery",
    # Professional Services
    "accountant", "tax preparer", "notary public", "photography studio",
    "videographer", "graphic designer", "marketing agency", "bookkeeper",
    # Health & Wellness
    "chiropractor", "physical therapy", "dentist", "optometrist",
    "mental health counselor", "acupuncture", "yoga studio", "pilates studio",
]

# ── Master location list (USA + Europe) ───────────────────────────────────────
ALL_LOCATIONS: list[str] = [
    # USA — South
    "Houston TX", "Dallas TX", "San Antonio TX", "Austin TX", "Fort Worth TX",
    "Miami FL", "Orlando FL", "Tampa FL", "Jacksonville FL", "Fort Lauderdale FL",
    "Atlanta GA", "Charlotte NC", "Raleigh NC", "Nashville TN", "Memphis TN",
    "New Orleans LA", "Louisville KY", "Birmingham AL", "Richmond VA",
    # USA — Northeast
    "New York NY", "Brooklyn NY", "Philadelphia PA", "Boston MA",
    "Newark NJ", "Baltimore MD", "Washington DC", "Pittsburgh PA",
    "Buffalo NY", "Hartford CT", "Providence RI",
    # USA — Midwest
    "Chicago IL", "Columbus OH", "Indianapolis IN", "Detroit MI",
    "Milwaukee WI", "Minneapolis MN", "Kansas City MO", "St Louis MO",
    "Cleveland OH", "Cincinnati OH", "Omaha NE", "Wichita KS",
    # USA — West
    "Los Angeles CA", "San Diego CA", "San Francisco CA", "San Jose CA",
    "Sacramento CA", "Fresno CA", "Las Vegas NV", "Phoenix AZ", "Tucson AZ",
    "Denver CO", "Colorado Springs CO", "Salt Lake City UT",
    "Portland OR", "Seattle WA", "Spokane WA", "Boise ID", "Albuquerque NM",
    "Anchorage AK", "Honolulu HI",
    # UK
    "London UK", "Manchester UK", "Birmingham UK", "Leeds UK",
    "Glasgow UK", "Liverpool UK", "Bristol UK", "Sheffield UK",
    "Edinburgh UK", "Cardiff UK", "Belfast UK", "Nottingham UK",
    # Germany
    "Berlin Germany", "Munich Germany", "Hamburg Germany", "Frankfurt Germany",
    "Cologne Germany", "Stuttgart Germany", "Dusseldorf Germany", "Bremen Germany",
    # Netherlands
    "Amsterdam Netherlands", "Rotterdam Netherlands", "The Hague Netherlands", "Utrecht Netherlands",
    # Spain
    "Madrid Spain", "Barcelona Spain", "Valencia Spain", "Seville Spain", "Malaga Spain",
    # France
    "Paris France", "Lyon France", "Marseille France", "Toulouse France", "Bordeaux France",
    # Italy
    "Rome Italy", "Milan Italy", "Naples Italy", "Turin Italy", "Florence Italy",
    # Other Europe
    "Brussels Belgium", "Zurich Switzerland", "Vienna Austria", "Geneva Switzerland",
    "Warsaw Poland", "Krakow Poland", "Prague Czech Republic", "Budapest Hungary",
    "Stockholm Sweden", "Gothenburg Sweden", "Oslo Norway", "Copenhagen Denmark",
    "Lisbon Portugal", "Porto Portugal", "Dublin Ireland",   # L7 fix: removed duplicate Amsterdam
    "Helsinki Finland", "Athens Greece", "Bucharest Romania",
]


# ── Snippet signal extractor ──────────────────────────────────────────────────
# Runs on the raw DDG search result description (free text).
# Extracts buyer-quality signals WITHOUT any API call.

_RE_RATING    = re.compile(r'(\d[\.,]\d)\s*(?:star|★|☆|out of 5|/5)', re.I)
_RE_REVIEWS   = re.compile(r'(\d[\d,]+)\s*(?:review|rating|feedback)', re.I)
_RE_YEARS     = re.compile(r'(?:since|established|founded|serving)\s+(\d{4})', re.I)
_RE_AWARD     = re.compile(r'\b(?:award|best in|top rated|#1|voted|certified)\b', re.I)


def _extract_snippet_signals(snippet: str) -> dict:
    """
    Parse a DDG snippet for buyer quality signals.
    Returns:
      has_reviews  — review count mentioned
      has_rating   — star rating mentioned
      high_rating  — rating >= 4.0
      established  — years in business / award signals
    """
    if not snippet:
        return {}

    signals: dict[str, bool] = {}

    # Reviews
    m = _RE_REVIEWS.search(snippet)
    if m:
        signals["has_reviews"] = True

    # Rating
    m = _RE_RATING.search(snippet)
    if m:
        signals["has_rating"] = True
        try:
            val = float(m.group(1).replace(",", "."))
            if val >= 4.0:
                signals["high_rating"] = True
        except ValueError:
            pass

    # Established / credibility
    if _RE_YEARS.search(snippet) or _RE_AWARD.search(snippet):
        signals["established"] = True

    return signals


class ResearcherAgent(BaseAgent):
    agent_id = "researcher"

    def __init__(self, model: str = "deepseek"):
        self.ai = LLMClient(model)

    # ─────────────────────────────────────────────────────────────────────────

    def run(self, niche: str = "all", region: str = "USA and Europe",
            count: int = 10, **kwargs) -> list[dict]:

        self.log("start", {"niche": niche, "region": region})
        console.rule("[bold cyan]Agent 1 — Researcher")

        # ── Pick a random niche + location mix ────────────────────────────
        niches    = list(ALL_NICHES if niche == "all" else [niche])
        locations = list(ALL_LOCATIONS)

        # Filter locations by region keywords if provided
        region_terms = [r.strip().lower() for r in re.split(r"\band\b|,", region) if r.strip()]
        if region_terms:
            filtered = [l for l in locations
                        if any(t in l.lower() for t in region_terms)]
            locations = filtered or locations   # fall back to all if filter too strict

        random.shuffle(niches)
        random.shuffle(locations)

        # We loop until we have at least `count` valid scored targets.
        final_scored: list[dict] = []
        seen_urls:   set[str] = set()
        cities_hit:  set[str] = set()
        total_raw_found = 0
        total_audited = 0
        
        while len(final_scored) < count and (locations or niches):
            raw: list[dict] = []
            
            # Pull a batch of locations/niches
            batch_locs = locations[:8]
            locations = locations[8:]
            
            console.print(f"[dim]Sweeping batch of {len(batch_locs)} cities…[/dim]")
            
            for loc in batch_locs:
                for nch in niches[:10]: # Try a few niches per city
                    console.print(f"  [dim]Searching:[/dim] [bold]{nch}[/bold] in [bold]{loc}[/bold]")
                    results = search_businesses(nch, loc, max_results=6)
                    for r in results:
                        url = r.get("href") or r.get("url") or ""
                        if url and url not in seen_urls:
                            if any(agg in url.lower() for agg in AGGREGATORS):
                                continue
                            seen_urls.add(url)
                            cities_hit.add(loc)
                            raw.append({
                                "niche":    nch,
                                "location": loc,
                                "title":    r.get("title", ""),
                                "url":      url,
                                "snippet":  r.get("body", ""),
                                "_snippet_signals": _extract_snippet_signals(r.get("body", "")),
                            })
            
            if not raw:
                continue
                
            console.print(f"[green]Batch collected {len(raw)} raw candidates[/green]")

            # ── Step 2: Parallel audit + contact scrape ───────────────────────
            console.print(f"[cyan]Auditing sites & scraping contacts (parallel)…[/cyan]")
            audited: list[dict] = []
            audit_candidates = raw
            audit_pool = min(20, len(audit_candidates))

            def _audit_and_scrape(c: dict) -> dict:
                url   = c["url"]
                audit = audit_website(url)
                c["audit"]         = audit
                c["website_score"] = audit["score"]
                c["load_ms"]       = audit.get("load_ms")
                c["reachable"]     = audit.get("reachable", False)
                contacts = scrape_contacts(url)
                c.update(contacts)
                import urllib.parse as _up
                if c.get("email"):
                    c["email"] = _up.unquote(c["email"]).strip()
                if c.get("phone"):
                    c["phone"] = _up.unquote(c["phone"]).strip()
                return c

            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
                          BarColumn(), TaskProgressColumn(), console=console) as progress:
                task = progress.add_task("[cyan]Auditing…", total=len(audit_candidates))
                with ThreadPoolExecutor(max_workers=audit_pool) as pool:
                    futures = {pool.submit(_audit_and_scrape, c): c for c in audit_candidates}
                    for fut in as_completed(futures):
                        try:
                            audited.append(fut.result())
                        except Exception as exc:
                            log.debug(f"Audit error: {exc}")
                        finally:
                            progress.advance(task)
            
            total_raw_found += len(raw)
            total_audited += len(audited)

            # ── Step 3: Score & rank (local heuristic — zero API calls) ───────
            console.print("[cyan]Ranking batch by opportunity score…[/cyan]")
            # Count how many more we need
            needed = count - len(final_scored)
            scored = self._score_and_rank(audited, needed * 2) # Score excess
            final_scored.extend(scored)
            
            # Deduplicate just in case
            seen_biz = set()
            deduped = []
            for s in final_scored:
                if s["url"] not in seen_biz:
                    seen_biz.add(s["url"])
                    deduped.append(s)
            final_scored = deduped
            
            if len(final_scored) >= count:
                break
                
        # Truncate to exact count requested
        final_scored = final_scored[:count]

        if not final_scored:
            log.warning("Could not find any valid targets across all locations")
            return []

        # ── Step 4: Finalise target records ───────────────────────────────
        targets: list[dict] = []
        for i, biz in enumerate(final_scored, 1):
            biz["id"]   = str(uuid.uuid4())
            biz["rank"] = i
            targets.append(biz)
            name = biz.get("business_name", biz.get("title", "?"))
            score = biz.get("website_score", 0)
            has_contact = "✅" if (biz.get("phone") or biz.get("email")) else "❌"
            console.print(
                f"  [bold green]#{i:02d}[/bold green] [white]{name[:55]}[/white]  "
                f"[dim]score={score}/10  contact={has_contact}[/dim]"
            )

        # ── Step 5: Save to shared state ──────────────────────────────────
        state = self.state()
        state["targets"]       = targets
        state["last_run_date"] = date.today().isoformat()
        state["cycle_stats"]   = {
            "raw_found":     total_raw_found,
            "audited":       total_audited,
            "final_targets": len(targets),
            "cities_hit":    len({t.get("location") for t in targets}),
            "niches_hit":    len({t.get("niche") for t in targets}),
        }
        self.save(state)
        self.log("targets_saved", {"count": len(targets)})

        # ── Step 6: Send dossier to operator ───────────────────────────────────
        send_dossier_email(targets)

        # ── Step 7: Autonomous outreach ───────────────────────────────────
        # Sends beautiful cold emails directly to critical leads' inboxes.
        # Only fires if SEND_OUTREACH_EMAILS=true in .env
        import os
        if os.getenv("SEND_OUTREACH_EMAILS", "false").lower() == "true":
            # Read caps from env — .env has OUTREACH_MAX_PER_CYCLE=50 and
            # OUTREACH_SCORE_THRESHOLD=10 (send to ALL leads, not just bad sites).
            # Hardcoded fallbacks intentionally permissive so cold emails aren't silently suppressed.
            _threshold  = int(os.getenv("OUTREACH_SCORE_THRESHOLD", "10"))
            _max_emails = int(os.getenv("OUTREACH_MAX_PER_CYCLE",    "50"))
            console.print(
                f"[cyan]Sending autonomous outreach (threshold≤{_threshold}, max={_max_emails})…[/cyan]"
            )
            outreach_results = send_outreach_emails(
                targets,
                score_threshold=_threshold,
                max_per_cycle=_max_emails,
            )
            state = self.state()
            state["last_outreach"] = outreach_results
            self.save(state)
            self.log("outreach_sent", {
                "sent":   len(outreach_results.get("sent",   [])),
                "failed": len(outreach_results.get("failed", [])),
                "skipped": len(outreach_results.get("skipped", [])),
            })
            console.print(
                f"[green]Outreach: {len(outreach_results.get('sent',[]))} sent, "
                f"{len(outreach_results.get('failed',[]))} failed, "
                f"{len(outreach_results.get('skipped',[]))} skipped (already contacted)[/green]"
            )
        else:
            console.print(
                "[dim]Autonomous outreach disabled. "
                "Set SEND_OUTREACH_EMAILS=true in .env to enable.[/dim]"
            )

        console.rule("[bold green]Researcher complete")
        return targets

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _score_and_rank(self, candidates: list[dict], count: int) -> list[dict]:
        """
        TWO-AXIS SCORING SYSTEM
        =======================
        The IDEAL client scores HIGH on BOTH axes:

        AXIS 1 — BUYER QUALITY (is this business thriving & able to pay?)
          + Has active social media (Instagram/TikTok/Facebook)  → audience exists
          + Has phone number                                      → real operating business
          + Has email address                                     → reachable
          + Reviews/ratings mentioned in snippet                  → customers love them
          + Star rating mentioned (4★+)                          → trusted
          + Multiple platforms (social + phone + email)          → established
          + Snippet mentions years in business / awards          → credibility
          — No social, no phone, no email                        → DISQUALIFIED (dead)

        AXIS 2 — WEBSITE PAIN (do they desperately need us?)
          + Low website_score                                    → weak/bad site
          + Not mobile-ready                                     → losing 70% of traffic
          + No SSL                                               → losing trust
          + Slow load time                                       → users bouncing
          + No contact/booking form                              → losing conversions
          + No meta description                                  → invisible on Google
          — Already has great website (score 8+)                 → skip them

        FINAL SCORE = BUYER_QUALITY × WEBSITE_PAIN
        Only businesses with BOTH high buyer quality AND high website pain are selected.
        """
        scored = []
        for c in candidates:
            ws    = c.get("website_score", 5)
            audit = c.get("audit", {})
            sigs  = c.get("_snippet_signals", {})

            # ── HARD DISQUALIFIERS (skip entirely) ──────────────────────
            # 1. Site not reachable at all
            if not c.get("reachable", False):
                continue
            # 2. Must have a working email address
            if not c.get("email"):
                continue
            # 3. Website already excellent — they don't need us
            if ws >= 9:
                continue

            # ── BUYER QUALITY SCORE (0–40) ──────────────────────────────
            bq = 0
            # Social presence = audience exists
            if c.get("instagram"):  bq += 10   # Instagram = visual audience, perfect for us
            if c.get("tiktok"):     bq += 8    # TikTok = viral potential
            if c.get("facebook"):   bq += 5
            if c.get("twitter"):    bq += 3
            # Reachability = real business
            if c.get("phone"):      bq += 6
            if c.get("email"):
                email_str = c["email"].lower()
                generic_prefixes = ["info@", "contact@", "support@", "admin@", "sales@", "hello@"]
                if any(email_str.startswith(prefix) for prefix in generic_prefixes):
                    bq += 2   # Penalized score for generic emails
                else:
                    bq += 10  # Massive boost for personal/founder emails
            if c.get("whatsapp"):   bq += 4
            # Review signals from DDG snippet (pre-extracted)
            if sigs.get("has_reviews"):   bq += 8   # people are talking about them
            if sigs.get("high_rating"):   bq += 6   # 4+ stars = loved by audience
            if sigs.get("has_rating"):    bq += 3
            if sigs.get("established"):   bq += 4   # years in business / award signals
            # Multiple contact channels = serious business
            channels = sum([
                bool(c.get("phone")), bool(c.get("email")),
                bool(c.get("instagram")), bool(c.get("facebook")),
                bool(c.get("tiktok"))
            ])
            bq += channels * 2   # bonus per extra channel (max +10)

            # ── WEBSITE PAIN SCORE (0–30) ───────────────────────────────
            wp = 0
            wp += (10 - ws) * 2                                      # max +18 for score=1
            wp += 4 if not audit.get("mobile_ready") else 0
            wp += 3 if not audit.get("has_ssl")      else 0
            wp += 3 if not audit.get("has_contact")  else 0
            wp += 2 if not audit.get("has_meta_desc")else 0
            wp += 3 if c.get("load_ms") and c["load_ms"] > 4000 else 0
            # Bonus: business with social fans but no website = golden
            if (c.get("instagram") or c.get("tiktok")) and ws <= 4:
                wp += 5  # social audience with terrible website = slam dunk

            # ── FINAL COMBINED SCORE ────────────────────────────────────
            # We want HIGH buyer quality AND HIGH website pain
            # Businesses that score low on buyer quality are skipped
            # M8 fix: lowered threshold 8→6 so email-only businesses qualify
            # (email=+7 + channels=+2 = 9, well above; phone-only=+6+2=8 still passes)
            if bq < 6:  # minimum viability threshold
                continue

            final_score = (bq * 0.6) + (wp * 0.4)  # buyer quality weighted heavier

            # ── Clean business name ─────────────────────────────────────
            raw_title = c.get("title", "")
            name = raw_title.split("|")[0].split("–")[0].split("-")[0].strip()
            name = re.sub(r"\s+", " ", name)[:70] or "Unknown Business"

            scored.append({
                "business_name":          name,
                "niche":                  c.get("niche", "service"),
                "location":               c.get("location", ""),
                "url":                    c.get("url", ""),
                "snippet":                c.get("snippet", "")[:400],
                "website_score":          ws,
                "load_ms":                c.get("load_ms"),
                "reachable":              c.get("reachable", False),
                "phone":                  c.get("phone", ""),
                "email":                  c.get("email", ""),
                "instagram":              c.get("instagram", ""),
                "facebook":               c.get("facebook", ""),
                "tiktok":                 c.get("tiktok", ""),
                "whatsapp":               c.get("whatsapp", ""),
                "twitter":                c.get("twitter", ""),
                "audit":                  c.get("audit", {}),
                "buyer_quality":          round(bq),
                "website_pain":           round(wp),
                "pain_points":            self._pain_points(ws, c.get("audit", {}), c),
                "estimated_revenue_tier": self._revenue_tier(bq, c),
                "_final_score":           final_score,
            })

        scored.sort(key=lambda x: x.pop("_final_score", 0), reverse=True)

        # H5 fix: diversity pass now uses AND so both niche AND city must be new
        # This prevents one high-volume city (e.g. Houston) flooding all slots
        seen_niches: set[str] = set()
        seen_locs:   set[str] = set()
        priority, rest = [], []
        for s in scored:
            n, l = s["niche"], s["location"]
            if n not in seen_niches and l not in seen_locs:  # H5: AND not OR
                seen_niches.add(n)
                seen_locs.add(l)
                priority.append(s)
            else:
                rest.append(s)
        return (priority + rest)[:count]

    @staticmethod
    def _pain_points(score: int, audit: dict, c: dict) -> list[str]:
        pts: list[str] = []
        if score <= 2:
            pts.append("Website critically broken — customers are bouncing instantly")
        elif score <= 4:
            pts.append("Poor website — losing bookings to competitors daily")
        if not audit.get("mobile_ready"):
            pts.append("Not mobile-friendly — 70%+ of traffic lost")
        if not audit.get("has_ssl"):
            pts.append("No HTTPS — Chrome shows 'Not Secure' to every visitor")
        if not audit.get("has_contact"):
            pts.append("No booking/contact form — customers can't convert online")
        if not audit.get("has_meta_desc"):
            pts.append("No SEO meta — practically invisible on Google")
        if c.get("load_ms") and c["load_ms"] > 4000:
            pts.append(f"Extremely slow ({c['load_ms']}ms) — 53% of users abandon after 3s")
        if (c.get("instagram") or c.get("tiktok")) and score <= 5:
            pts.append("Active social following but website doesn't match — leaking revenue")
        return pts[:4]

    @staticmethod
    def _revenue_tier(buyer_quality: int, c: dict) -> str:
        """Estimate revenue tier from buyer quality signal strength."""
        has_tiktok = bool(c.get("tiktok"))
        has_insta  = bool(c.get("instagram"))
        if buyer_quality >= 28 or (has_tiktok and has_insta):
            return "medium"       # $1k–$5k/month+ revenue likely
        if buyer_quality >= 16:
            return "small_team"   # growing, has some following
        return "solo"             # early stage but viable

    # ── Legacy ────────────────────────────────────────────────────────────────

    def _send_email(self, targets: list[dict], to_email: str) -> None:
        send_dossier_email(targets)
