"""
web_search.py — Antigravity Search & Audit Engine
===================================================
• DuckDuckGo-only (no broken Yandex/Mojeek/Brave engines)
• Every URL is HEAD-checked before acceptance — zero dead links
• 45+ blocked domains: directories, social media, search engines
• Google Maps scraper for extra contact data
• Full contact scraper: phone, email, Instagram, Facebook, TikTok, WhatsApp
• Duplicate-aware (strips tracking params before dedup)
• Exponential back-off on DDG rate limits
"""

import re
import time
import random
import logging
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ddgs import DDGS

log = logging.getLogger("antigravity.search")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "DNT": "1",
}

# ── Block list ────────────────────────────────────────────────────────────────
# Every domain here is a directory, aggregator, social network, or search engine.
# Any URL whose host matches (or is a subdomain of) these is silently dropped.
BLOCKED_DOMAINS: frozenset[str] = frozenset({
    # ── Directories & aggregators ─────────────────────────────────────────
    "yelp.com", "yelp.co.uk", "bbb.org", "angi.com", "homeadvisor.com",
    "thumbtack.com", "yellowpages.com", "tripadvisor.com", "expertise.com",
    "houzz.com", "porch.com", "nextdoor.com", "groupon.com", "mapquest.com",
    "chamberofcommerce.com", "bark.com", "checkatrade.com", "ratedpeople.com",
    "mybuilder.com", "fixr.co.uk", "hipages.com.au", "airtasker.com",
    "angieslist.com", "manta.com", "cylex.us", "yell.com", "trustpilot.com",
    "businessfinder.net", "localstack.com", "merchant-circle.com",
    "brownbook.net", "n49.com", "foursquare.com", "opentable.com",
    "freeindex.co.uk", "scoot.co.uk", "hotfrog.com", "localbd.com",
    "businesslist.com", "elocal.com", "findlaw.com", "avvo.com",
    "houzz.co.uk", "checkatrade.com", "trustatrader.com", "which.co.uk",
    # ── Job boards & recruitment (must NEVER appear as leads) ────────────
    "indeed.com", "glassdoor.com", "linkedin.com", "monster.com",
    "totaljobs.com", "reed.co.uk", "cv-library.co.uk", "jobsite.co.uk",
    "simplyhired.com", "ziprecruiter.com", "careerbuilder.com",
    "jobs.com", "seek.com.au", "jooble.org", "snagajob.com",
    "workable.com", "lever.co", "greenhouse.io", "jobvite.com",
    "myworkdayjobs.com", "icims.com", "bamboohr.com",
    "jobs.google.com", "talent.com", "adzuna.com", "adzuna.co.uk",
    "stepstone.de", "xing.com", "emplois.ch", "jobup.ch",
    "infojobs.net", "trabajos.com", "monster.co.uk", "workindenmark.dk",
    # ── Social / content ──────────────────────────────────────────────────
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "pinterest.com", "tiktok.com", "youtube.com", "snapchat.com",
    "reddit.com", "quora.com", "medium.com", "substack.com",
    "tumblr.com", "blogger.com", "wordpress.com",
    # ── Search engines ────────────────────────────────────────────────────
    "google.com", "bing.com", "yahoo.com", "duckduckgo.com",
    "yandex.com", "yandex.ru", "mojeek.com", "search.brave.com", "brave.com",
    "grokipedia.com", "startpage.com", "ecosia.org",
    # ── Reference / encyclopaedic ─────────────────────────────────────────
    "wikipedia.org", "wikihow.com", "wikimedia.org", "britannica.com",
    # ── Marketplaces ─────────────────────────────────────────────────────
    "amazon.com", "amazon.co.uk", "ebay.com", "etsy.com", "shopify.com",
    "walmart.com", "aliexpress.com", "alibaba.com",
    # ── Government & non-profit ───────────────────────────────────────────
    "gov.uk", "usa.gov", "state.gov", "irs.gov", "sba.gov",
    "nhs.uk", "europa.eu", "ec.europa.eu",
    # ── News & media ──────────────────────────────────────────────────────
    "cnn.com", "bbc.com", "bbc.co.uk", "dailymail.co.uk", "theguardian.com",
    "nytimes.com", "wsj.com", "forbes.com", "bloomberg.com",
    "businessinsider.com", "huffpost.com", "buzzfeed.com",
    # ── Franchise / chain portals (we want local owners not HQs) ─────────
    "franchiseopportunities.com", "franchise.org", "bfa.org.uk",
})


# ── URL path patterns that signal non-business pages ─────────────────────────
# Even if the domain passes, these path segments indicate it's a job posting,
# article, listing, or other non-business page.
_BLOCKED_PATH_SEGMENTS: frozenset[str] = frozenset({
    "/jobs", "/job-", "/careers", "/vacancy", "/vacancies",
    "/recruitment", "/hiring", "/apply", "/job-listing", "/job-board",
    "/news/", "/blog/", "/article/", "/press-release/",
    "/category/", "/tag/", "/search?", "/results?",
    "/listing/", "/listings/", "/directory/", "/find/",
})


def _host(url: str) -> str:
    """Return hostname without www. prefix — uses removeprefix to avoid lstrip char-set bug."""

    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.removeprefix("www.")   # C1 fix: lstrip("www.") strips wrong chars
    except Exception:
        return ""


import ipaddress

def _is_blocked(url: str) -> bool:
    host = _host(url)
    if not host:
        return True

    # SSRF Prevention: Block local, private, and loopback IPs
    try:
        ip_host = host.split(":")[0] if ":" in host else host
        ip_host = ip_host.strip("[]") # Handle IPv6 brackets
        ip = ipaddress.ip_address(ip_host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return True
    except ValueError:
        pass
        
    if host in ("localhost", "metadata.google.internal"):
        return True

    # Domain-level block
    if any(host == b or host.endswith("." + b) for b in BLOCKED_DOMAINS):
        return True
    # Path-level block — catches job listings on otherwise legit domains
    try:
        path = urlparse(url).path.lower()
        if any(seg in path for seg in _BLOCKED_PATH_SEGMENTS):
            return True
    except Exception:
        pass
    return False


def _canonical(url: str) -> str:
    """Strip tracking params and trailing slash for deduplication."""
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/").lower()
    except Exception:
        return url.lower()


# ── Liveness check ────────────────────────────────────────────────────────────

def _is_live(url: str, timeout: int = 7) -> bool:
    """
    Returns True only if the page exists and isn't a 4xx/5xx error.
    Tries HEAD first (cheap), falls back to GET if server rejects HEAD.
    M7 fix: logs exceptions so transient failures are visible in logs.
    """
    for method in (requests.head, requests.get):
        try:
            kw: dict = {"headers": HEADERS, "timeout": timeout, "allow_redirects": True}
            r = method(url, **kw)
            if r.status_code < 400:
                return True
            if r.status_code in (403, 405):
                continue
            return False
        except Exception as exc:
            log.debug(f"[is_live] {method.__name__} {url[:60]}: {exc}")
    return False


# ── DDG search with retry ─────────────────────────────────────────────────────

def _ddg(query: str, max_results: int = 15) -> list[dict]:
    """DuckDuckGo text search with exponential back-off on rate-limit."""
    for attempt in range(3):
        try:
            with DDGS() as d:
                return list(d.text(query, max_results=max_results))
        except Exception as exc:
            msg = str(exc).lower()
            if "ratelimit" in msg or "202" in msg or "429" in msg:
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                log.warning(f"[DDG] rate-limited — waiting {wait:.1f}s")
                time.sleep(wait)
            else:
                log.debug(f"[DDG] error: {exc}")
                break
    return []


# ── Main search function ──────────────────────────────────────────────────────

# ── Location verification ─────────────────────────────────────────────────────

def _location_match(result: dict, location: str) -> bool:
    """
    Returns True if the result's title or snippet contains the city name
    or the full expanded state/country name.
    L8 fix: use city name (>=4 chars) + expanded state name only.
    Avoids short tokens like 'co', 'or', 'in' matching unrelated words.
    """
    loc_lower = location.lower()
    parts = loc_lower.replace(",", " ").split()

    # C2 fix: removed duplicate 'de' key (was 'germany', overwriting 'delaware')
    _abbr_map = {
        "tx": "texas", "fl": "florida", "ca": "california", "ny": "new york",
        "il": "illinois", "pa": "pennsylvania", "ga": "georgia", "nc": "north carolina",
        "tn": "tennessee", "oh": "ohio", "mi": "michigan", "wa": "washington",
        "az": "arizona", "nv": "nevada", "ut": "utah", "mo": "missouri",
        "mn": "minnesota", "wi": "wisconsin", "ky": "kentucky", "la": "louisiana",
        "al": "alabama", "va": "virginia", "md": "maryland", "ma": "massachusetts",
        "ct": "connecticut", "nj": "new jersey", "ri": "rhode island", "ne": "nebraska",
        "ks": "kansas", "ok": "oklahoma", "nm": "new mexico", "ak": "alaska",
        "hi": "hawaii", "de": "delaware", "sc": "south carolina",  # 'de' = delaware only
        "uk": "united kingdom",
        # European country suffixes — 'co' and 'or' are NOT abbreviations here
    }

    # Build token set: only use city word (first part) if it's long enough,
    # plus the expanded abbreviation if there is one
    tokens: set[str] = set()
    for part in parts:
        if len(part) >= 4:          # L8 fix: skip very short tokens like 'co','or','in'
            tokens.add(part)
        if part in _abbr_map:
            tokens.add(_abbr_map[part])  # add expanded form ('tx' → 'texas')

    if not tokens:
        # Fallback: use raw location string
        tokens = {loc_lower}

    haystack = " ".join([
        (result.get("title") or "").lower(),
        (result.get("body") or "").lower(),
        (result.get("href") or "").lower(),
    ])

    return any(tok in haystack for tok in tokens)


# ── Main search function ──────────────────────────────────────────────────────

def search_businesses(niche: str, location: str, max_results: int = 8) -> list[dict]:
    """
    Search DuckDuckGo for real local business websites.

    Pipeline:
      1. Run 4 targeted DDG queries (all quote the location)
      2. Drop blocked / social / aggregator domains
      3. Verify the result actually mentions the target location (kills geo-bias)
      4. Deduplicate by canonical URL
      5. HEAD-verify every URL is live before accepting it
      6. Return up to max_results * 2 verified records
    """
    city = location.split(",")[0].strip()   # "Houston TX" or "London UK"

    # All queries quote the location so DDG can't ignore it
    queries = [
        f'"{niche}" "{city}" -site:yelp.com -site:bbb.org -site:angi.com -site:facebook.com',
        f'"{niche}" "{city}" local business website contact',
        f'"{city}" "{niche}" services phone OR email',
        f'site:.com OR site:.co.uk "{niche}" "{city}"',
    ]

    # L6 fix: use appropriate DDG region — eu locations get neutral wt-wt
    _eu_keywords = {
        "uk", "germany", "france", "spain", "italy", "netherlands", "belgium",
        "switzerland", "austria", "poland", "czech", "hungary", "sweden",
        "norway", "denmark", "portugal", "ireland", "finland", "greece",
        "romania", "scotland", "wales", "england",
    }
    loc_lower_check = location.lower()
    _ddg_region = "wt-wt" if any(eu in loc_lower_check for eu in _eu_keywords) else "us-en"

    seen: set[str]   = set()
    raw:  list[dict] = []

    for q in queries:
        try:
            with DDGS() as d:
                hits = list(d.text(q, max_results=max_results * 3, region=_ddg_region))
        except Exception:
            hits = _ddg(q, max_results * 3)   # fallback without region

        for r in hits:
            href = r.get("href") or r.get("url") or ""
            if not href or not href.startswith("http"):
                continue
            if _is_blocked(href):
                continue
            # ── Hard location gate: drop results that don't mention the city ──
            if not _location_match(r, location):
                log.debug(f"[search] location mismatch dropped: {href[:60]}")
                continue
            key = _canonical(href)
            if key in seen:
                continue
            seen.add(key)
            raw.append(r)
        time.sleep(random.uniform(0.8, 1.5))

    # ── Liveness gate ─────────────────────────────────────────────────────────
    verified: list[dict] = []
    for r in raw:
        if len(verified) >= max_results * 2:
            break
        href = r.get("href") or r.get("url") or ""
        if _is_live(href):
            verified.append(r)
        time.sleep(0.25)

    return verified[:max_results * 2]



# ── Site audit ────────────────────────────────────────────────────────────────

def audit_website(url: str, timeout: int = 10) -> dict:
    """
    Lightweight technical audit.
    score 1-10 where LOW score = weak site = prime prospect.

    Checks:
      • HTTPS / SSL
      • HTTP status (reachable)
      • Viewport meta (mobile-ready)
      • Contact / booking keywords
      • Load time
      • Legacy table layout
      • Meta description presence
    """
    result: dict = {
        "url":          url,
        "reachable":    False,
        "load_ms":      None,
        "mobile_ready": False,
        "has_contact":  False,
        "has_ssl":      url.startswith("https://"),
        "has_meta_desc":False,
        "score":        1,
        "issues":       [],
    }
    try:
        t0   = time.time()
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        result["load_ms"]  = int((time.time() - t0) * 1000)
        # C5 fix: read has_ssl from the FINAL redirected URL, not the input URL
        result["has_ssl"] = resp.url.startswith("https://")
        
        if _is_blocked(resp.url):
            result["reachable"] = False
            result["issues"].append("Redirected to blocked aggregator/directory")
            return result
            
        result["reachable"] = (resp.status_code == 200)

        if not result["reachable"]:
            result["issues"].append(f"HTTP {resp.status_code}")
            return result

        soup = BeautifulSoup(resp.text, "lxml")

        # Mobile
        if soup.find("meta", attrs={"name": re.compile("viewport", re.I)}):
            result["mobile_ready"] = True

        # H2 fix: has_contact is now strict — requires a real form, tel: anchor, or tel input
        result["has_contact"] = bool(
            soup.find("form") or
            soup.find("a", href=re.compile(r"^tel:", re.I)) or
            soup.find("input", attrs={"type": "tel"})
        )

        # Meta description
        if soup.find("meta", attrs={"name": re.compile("description", re.I)}):
            result["has_meta_desc"] = True
        else:
            result["issues"].append("Missing meta description")

        # H1 fix: removed tautological 'reachable +2' (always True inside this block)
        # Score starts at 3 (base for any reachable site) instead of 1 + tautology
        score = 3
        if result["has_ssl"]:      score += 1
        if result["mobile_ready"]: score += 2
        if result["has_contact"]:  score += 1
        if result["load_ms"] and result["load_ms"] < 3000: score += 1
        if result["has_meta_desc"]: score += 1
        if soup.find("table", attrs={"width": True}):
            score -= 2          # old table-based layout
            result["issues"].append("Legacy table layout detected")
        if result["load_ms"] and result["load_ms"] > 5000:
            score -= 1
            result["issues"].append("Very slow load time")

        result["score"] = max(1, min(10, score))

    except requests.exceptions.SSLError:
        result["issues"].append("SSL certificate error")
    except requests.exceptions.ConnectionError:
        result["issues"].append("Connection refused / DNS failure")
    except requests.exceptions.Timeout:
        result["issues"].append("Request timed out")
    except Exception as exc:
        result["issues"].append(str(exc)[:120])

    return result


# ── Contact scraper ───────────────────────────────────────────────────────────

# L4 fix: anchored phone regex — requires 10-digit NANP or international format
_RE_PHONE   = re.compile(
    r'(?<!\d)'                          # not preceded by digit
    r'(\+?1[-.\s]?)?'                   # optional country code
    r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'  # NXX-NXX-XXXX
    r'(?!\d)'                           # not followed by digit
)
_RE_EMAIL   = re.compile(r'[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9.\-]{2,}')
_RE_INSTA   = re.compile(r'instagram\.com/([A-Za-z0-9_.]+)', re.I)
_RE_FB      = re.compile(r'facebook\.com/([A-Za-z0-9_.]+)', re.I)
_RE_TIKTOK  = re.compile(r'tiktok\.com/@([A-Za-z0-9_.]+)', re.I)
_RE_WA      = re.compile(r'wa\.me/([0-9]+)|whatsapp\.com/send\?phone=([0-9]+)', re.I)
_RE_TWITTER = re.compile(r'(?:twitter|x)\.com/([A-Za-z0-9_]+)', re.I)

# M2 fix: expanded Facebook skip list to avoid photo.php, events, etc.
_FB_SKIP = frozenset({
    "sharer", "share", "pages", "login", "home", "photo.php", "video",
    "events", "groups", "permalink", "story", "posts", "marketplace",
    "watch", "media", "hashtag", "help", "privacy",
})

# M1 fix: EMAIL_JUNK is checked against exact local-part, not as substring
_EMAIL_JUNK = frozenset({
    "example", "placeholder", "domain", "email", "yourname",
    "test", "user", "noreply", "no-reply", "webmaster", "admin",
    "info", "support", "hello", "contact", "mail",
})





def scrape_contacts(url: str, timeout: int = 10) -> dict:
    """
    Fetch a business page and extract every piece of contact/social info.
    Returns a dict with keys: phone, email, instagram, facebook, tiktok,
    whatsapp, twitter.  Missing values are empty strings.
    """
    contacts: dict[str, str] = {
        "phone": "", "email": "", "instagram": "",
        "facebook": "", "tiktok": "", "whatsapp": "", "twitter": "",
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        # Prevent scraping aggregators if a redirect happened
        if _is_blocked(resp.url):
            return contacts
        # M3 fix: only parse if the response is 200 — error pages have hosting-company contacts
        if resp.status_code != 200:
            return contacts
        soup = BeautifulSoup(resp.text, "lxml")
        # Also check href= attributes for mailto: and tel:
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("tel:") and not contacts["phone"]:
                contacts["phone"] = href[4:].strip()
            if href.startswith("mailto:") and not contacts["email"]:
                addr = href[7:].split("?")[0].strip()
                import urllib.parse as _up
                addr = _up.unquote(addr).strip()
                # M1 fix: check exact local-part, not substring
                local_part = addr.split("@")[0].lower() if "@" in addr else ""
                if addr and local_part not in _EMAIL_JUNK:
                    contacts["email"] = addr

        text = soup.get_text(" ", strip=True)

        # Phone fallback
        if not contacts["phone"]:
            m = _RE_PHONE.search(text)
            if m:
                contacts["phone"] = m.group(0).strip()

        # Email fallback — M1 fix: check exact local-part, not substring
        if not contacts["email"]:
            for m in _RE_EMAIL.finditer(text):
                addr = m.group(0)
                local_part = addr.split("@")[0].lower() if "@" in addr else ""
                if local_part not in _EMAIL_JUNK:
                    contacts["email"] = addr
                    break

        # Social
        html = resp.text
        for pat, key, prefix in [
            (_RE_INSTA,   "instagram", "@"),
            (_RE_FB,      "facebook",  "facebook.com/"),
            (_RE_TIKTOK,  "tiktok",    "@"),
            (_RE_TWITTER, "twitter",   "@"),
        ]:
            if not contacts[key]:
                m = pat.search(html)
                if m:
                    handle = m.group(1)
                    # M2 fix: use expanded _FB_SKIP for Facebook, basic set for others
                    skip_set = _FB_SKIP if key == "facebook" else {"sharer", "share", "login", "home"}
                    if handle.lower() not in skip_set and not handle.endswith(".php"):
                        contacts[key] = prefix + handle

        # WhatsApp
        m = _RE_WA.search(html)
        if m:
            number = m.group(1) or m.group(2)
            contacts["whatsapp"] = f"wa.me/{number}"

    except Exception as exc:
        log.debug(f"[scrape_contacts] {url}: {exc}")

    return contacts


def fetch_page_text(url: str, timeout: int = 10, max_chars: int = 5000) -> str:
    """Return visible text content from a URL (for AI analysis)."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if _is_blocked(resp.url):
            return ""
        soup = BeautifulSoup(resp.text, "lxml")
        # Remove script/style noise
        for tag in soup(["script", "style", "noscript", "svg"]):
            tag.decompose()
        return soup.get_text(" ", strip=True)[:max_chars]
    except Exception:
        return ""
