"""
apify_lead_agent.py — Antigravity Apify Lead Sourcer
======================================================
Uses the Apify Google Maps Scraper to find fresh local businesses.
Deduplicates against shared_state['contacted_emails'] before returning.

If APIFY_API_TOKEN is not set in .env, falls back to DuckDuckGo search
so the pipeline degrades gracefully rather than crashing.

Output: list of {name, url, email, phone, place_id} dicts, max 10 leads,
        all guaranteed to NOT be in the already-contacted set.
"""

import os
import logging
import requests
import time
import re
from urllib.parse import urlparse

from agents.base_agent import BaseAgent
from utils.state_manager import read_state

log = logging.getLogger("antigravity.apify_lead_agent")

# ── Aggregator blocklist (mirrors researcher.py) ──────────────────────────────
AGGREGATORS = {
    "yelp.com", "yellowpages.com", "thumbtack.com", "angi.com", "homeadvisor.com",
    "bbb.org", "expertise.com", "houzz.com", "porch.com", "nextdoor.com",
    "groupon.com", "mapquest.com", "chamberofcommerce.com", "bark.com",
    "checkatrade.com", "threebestrated.com", "tripadvisor.com",
    "google.com", "facebook.com", "instagram.com",
}

APIFY_BASE_URL = "https://api.apify.com/v2"
MAPS_ACTOR_ID  = "compass/crawler-google-places"


class ApifyLeadAgent(BaseAgent):
    agent_id = "apify_lead_agent"

    def run(
        self,
        niche: str = "landscaping",
        region: str = "Dallas TX",
        count: int = 10,
        **kwargs,
    ) -> list[dict]:
        """
        Scrape `count` new leads via Apify, deduplicate, return clean list.
        Falls back to DuckDuckGo if APIFY_API_TOKEN is absent.
        """
        api_token = os.getenv("APIFY_API_TOKEN", "")

        # Load already-contacted emails so we skip them
        state = read_state()
        contacted_emails: set[str] = {
            e.lower() for e in state.get("contacted_emails", [])
        }
        closed_lost: set[str] = {
            e.lower() for e in state.get("closed_lost", [])
        }
        skip_emails = contacted_emails | closed_lost

        log.info(f"[apify] Sourcing leads: niche={niche!r} region={region!r} (skip={len(skip_emails)})")

        if api_token:
            raw = self._scrape_apify(api_token, niche, region, count * 3)
        else:
            log.warning("[apify] No APIFY_API_TOKEN — falling back to DuckDuckGo")
            raw = self._scrape_ddg(niche, region, count * 3)

        # ── Dedup + filter ────────────────────────────────────────────────────
        seen_urls:  set[str] = set()
        candidates: list[dict] = []

        for lead in raw:
            url   = (lead.get("url") or "").strip().rstrip("/")
            email = (lead.get("email") or "").strip().lower()

            # Skip aggregators
            domain = _domain(url)
            if domain and any((domain == agg or domain.endswith("." + agg)) for agg in AGGREGATORS):
                continue

            # Skip already-contacted
            if email and email in skip_emails:
                log.debug(f"[apify] Skip (already contacted): {email}")
                continue

            # Skip duplicate URLs
            if url and url in seen_urls:
                continue

            seen_urls.add(url)
            candidates.append(lead)

            if len(candidates) >= count:
                break

        log.info(f"[apify] Returning {len(candidates)} new leads after dedup")
        return candidates

    # ── Apify API call ────────────────────────────────────────────────────────

    def _scrape_apify(
        self, token: str, niche: str, region: str, limit: int
    ) -> list[dict]:
        """
        Run the Apify Google Maps Scraper actor synchronously.
        Returns a list of raw place dicts.
        """
        search_query = f"{niche} in {region}"
        log.info(f"[apify] Starting actor run: {search_query!r}")

        # 1. Start the actor run
        run_url = f"{APIFY_BASE_URL}/acts/{MAPS_ACTOR_ID}/runs"
        payload = {
            "searchStringsArray": [search_query],
            "maxCrawledPlacesPerSearch": limit,
            "language": "en",
            "exportPlaceUrls": False,
            "includeHistogram": False,
            "includeOpeningHours": False,
            "includePeopleAlsoSearch": False,
            "maxImages": 0,
            "maxReviews": 0,
        }

        try:
            resp = requests.post(
                run_url,
                params={"token": token},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            run_id = resp.json()["data"]["id"]
            log.info(f"[apify] Actor run started: {run_id}")
        except Exception as exc:
            log.error(f"[apify] Failed to start actor: {exc}")
            return []

        status = ""
        status_url = f"{APIFY_BASE_URL}/actor-runs/{run_id}"
        for _ in range(24):   # 24 × 5s = 120s max
            time.sleep(5)
            try:
                st = requests.get(status_url, params={"token": token}, timeout=15)
                st.raise_for_status()
                status = st.json()["data"]["status"]
                if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                    break
                log.debug(f"[apify] Run status: {status}")
            except Exception as exc:
                log.warning(f"[apify] Status poll failed: {exc}")

        if status != "SUCCEEDED":
            log.error(f"[apify] Actor run ended with status: {status}")
            return []

        # 3. Fetch dataset items
        dataset_url = f"{APIFY_BASE_URL}/actor-runs/{run_id}/dataset/items"
        try:
            data_resp = requests.get(
                dataset_url,
                params={"token": token, "format": "json", "limit": limit},
                timeout=30,
            )
            data_resp.raise_for_status()
            items = data_resp.json()
            log.info(f"[apify] Fetched {len(items)} raw places from Maps")
        except Exception as exc:
            log.error(f"[apify] Dataset fetch failed: {exc}")
            return []

        return [_normalize_apify_item(item) for item in items]

    # ── DuckDuckGo fallback ───────────────────────────────────────────────────

    def _scrape_ddg(self, niche: str, region: str, limit: int) -> list[dict]:
        """Simple DuckDuckGo fallback — matches existing researcher.py logic."""
        from utils.web_search import search_businesses
        results = search_businesses(niche, region, max_results=limit)
        out = []
        for r in results:
            url = r.get("href") or r.get("url") or ""
            out.append({
                "name":     r.get("title", ""),
                "url":      url,
                "email":    "",
                "phone":    "",
                "place_id": "",
            })
        return out


# ── Normalisers ───────────────────────────────────────────────────────────────

def _normalize_apify_item(item: dict) -> dict:
    """
    Convert an Apify Google Maps Scraper result into the canonical
    lead format expected by ResearcherAgent.
    """
    # Phone: prefer direct field, fall back to phoneUnformatted
    phone = (
        item.get("phone")
        or item.get("phoneUnformatted")
        or ""
    )

    # Website URL: Apify returns 'website' or 'url'
    url = (
        item.get("website")
        or item.get("url")
        or ""
    ).strip().rstrip("/")

    # Email: Apify sometimes embeds in additionalInfo or custom fields
    email = (item.get("email") or "").strip()

    return {
        "name":     item.get("title") or item.get("name") or "",
        "url":      url,
        "email":    email,
        "phone":    phone,
        "place_id": item.get("placeId") or item.get("place_id") or "",
        # Pass-through extras for researcher scoring
        "address":  item.get("address") or "",
        "rating":   item.get("totalScore"),
        "reviews":  item.get("reviewsCount"),
    }


def _domain(url: str) -> str:
    """Extract bare domain from a URL for aggregator matching."""
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""
