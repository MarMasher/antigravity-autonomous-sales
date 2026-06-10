"""
email_sender.py — Antigravity Premium Dossier Email
=====================================================
Dark-mode, executive-quality HTML email.
Every lead gets: full contact info, technical audit, pain points,
a ready-to-send outreach DM, and a one-click Gmail compose button.
Zero AI calls — instant generation.
"""
import os
import urllib.parse
import smtplib
import logging
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import html

load_dotenv()
log = logging.getLogger("antigravity.email")

EMAIL_FROM         = os.getenv("EMAIL_FROM", "")
EMAIL_TO           = os.getenv("EMAIL_TO", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")


# ── Small UI helpers ──────────────────────────────────────────────────────────

def _badge(score: int, max_val: int = 10) -> str:
    pct = int((score / max_val) * 100)
    if pct <= 25:   col, label = "#ef4444", "CRITICAL"
    elif pct <= 45: col, label = "#f97316", "POOR"
    elif pct <= 65: col, label = "#eab308", "WEAK"
    elif pct <= 80: col, label = "#3b82f6", "FAIR"
    else:           col, label = "#22c55e", "GOOD"
    return (
        f'<span style="background:{col};color:#fff;padding:4px 12px;'
        f'border-radius:20px;font-size:11px;font-weight:800;letter-spacing:1px">'
        f'{score}/{max_val} {label}</span>'
    )


def _row(icon: str, label: str, value: str, link: str = "") -> str:
    val_html = (
        f'<a href="{link}" style="color:#818cf8;text-decoration:none" target="_blank">{value}</a>'
        if link else
        f'<span style="color:#e2e8f0">{value}</span>'
    )
    return (
        f'<tr><td style="padding:9px 14px;font-size:17px;vertical-align:top">{icon}</td>'
        f'<td style="padding:9px 0;color:#64748b;font-size:12px;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:.5px;white-space:nowrap;width:110px;vertical-align:top">{label}</td>'
        f'<td style="padding:9px 12px;font-size:13px;line-height:1.4;vertical-align:top">{val_html}</td></tr>'
    )


def _check(ok: bool, good: str, bad: str) -> str:
    icon = "✅" if ok else "❌"
    text = good if ok else bad
    color = "#22c55e" if ok else "#ef4444"
    return f'<span style="color:{color}">{icon} {text}</span>'


def _pill(text: str, col: str = "#ef4444") -> str:
    return (
        f'<span style="display:inline-block;margin:3px 4px 3px 0;padding:4px 12px;'
        f'background:{col}18;color:{col};border:1px solid {col}33;'
        f'border-radius:20px;font-size:11px;font-weight:700;letter-spacing:.5px">'
        f'{text.upper()}</span>'
    )


# ── Per-target card ───────────────────────────────────────────────────────────

def _card(t: dict, idx: int) -> str:
    biz      = html.escape(t.get("business_name") or t.get("title") or "Unknown Business")
    niche    = html.escape(t.get("niche", "—"))
    location = html.escape(t.get("location", "—"))
    url      = html.escape(t.get("url", ""))
    score    = t.get("website_score", 0)
    pain     = [html.escape(p) for p in (t.get("pain_points") or [])]
    tier     = html.escape(t.get("estimated_revenue_tier", "solo"))
    audit    = t.get("audit") or {}
    snippet  = html.escape((t.get("snippet") or "")[:320])
    load_ms  = t.get("load_ms")

    # Contact / social
    phone    = html.escape(t.get("phone", ""))
    email    = html.escape(t.get("email", ""))
    insta    = html.escape(t.get("instagram", ""))
    facebook = html.escape(t.get("facebook", ""))
    tiktok   = html.escape(t.get("tiktok", ""))
    whatsapp = html.escape(t.get("whatsapp", ""))
    twitter  = html.escape(t.get("twitter", ""))

    # ── Adaptive Outreach DM (unique per lead) ─────────────────────────────
    channel = "Instagram" if insta else ("TikTok" if tiktok else ("Facebook" if facebook else "email"))

    if score <= 2:
        site_hook = "your current website is essentially broken — it's not loading correctly on mobile, has no security certificate, and won't rank on Google"
    elif score <= 4:
        site_hook = "your website isn't converting visitors into customers — it's missing a booking system and loads too slowly for most people to wait"
    elif score <= 6:
        site_hook = "your website has potential but is missing a few key things that are quietly costing you bookings every week"
    else:
        site_hook = "your website could be working a lot harder for your business — especially on the local SEO and conversion side"

    first_pain = pain[0].lower() if pain else f"the online presence doesn't match the quality of the {niche} work"

    if insta or tiktok:
        social_line = f"I found your {channel} — your work genuinely looks great and you clearly have people following you."
        social_cta  = f"That {channel} audience deserves a website that closes them into paying customers."
    elif snippet and len(snippet) > 40:
        social_line = f"I came across your business while researching {niche} services in {location}."
        social_cta  = "Your customers clearly rate you — your website should reflect that."
    else:
        social_line = f"I was looking for top {niche} businesses in {location} and came across your profile."
        social_cta  = "A great website means more inbound leads without spending a penny on ads."

    dm = (
        f"Hey {biz}! 👋\n\n"
        f"{social_line}\n\n"
        f"I noticed {site_hook}. "
        f"Specifically — {first_pain}.\n\n"
        f"I'm a freelance web designer and I have a few ideas for a new website for {biz} "
        f"to show you exactly what's possible. {social_cta}\n\n"
        f"Want me to send over the link?\n\n"
        f"— {SENDER_NAME} | {SENDER_HANDLE}"
    )

    # ── Adaptive Website Blueprint (unique per lead) ────────────────────────
    niche_lower = niche.lower()

    if any(k in niche_lower for k in ["auto", "car", "detailing", "wrap", "tire", "tow"]):
        palette  = "Gunmetal #1a1a2e + Carbon Fibre texture + Chrome Silver + Red highlight"
        hero_img = "Cinematic 4K video bg of freshly detailed car / garage environment"
        gallery  = "Before/After split-screen slider with high-contrast lighting"
        cta_copy = "Book Your Detail Session — Online in 60 Seconds"
    elif any(k in niche_lower for k in ["landscape", "lawn", "tree", "garden", "pool", "irrigation", "snow"]):
        palette  = "Deep Forest #0f1f0f + Emerald Green + Warm Gold accents"
        hero_img = "Aerial drone shot of a perfectly manicured property"
        gallery  = "Seasonal transformation grid — before/after"
        cta_copy = f"Get Your Free {location.split()[0]} Yard Assessment"
    elif any(k in niche_lower for k in ["clean", "maid", "pressure", "window", "carpet", "gutter", "chimney"]):
        palette  = "Clean White #f8fafc + Sky Blue + Mint Green — ultra-clean minimal"
        hero_img = "Sparkling clean interior with warm natural light"
        gallery  = "Time-lapse before/after cleaning transformations"
        cta_copy = f"Book a Free Quote — Same-Day Response in {location.split()[0]}"
    elif any(k in niche_lower for k in ["hvac", "plumb", "electr", "roof", "handyman", "contrac", "floor", "fence", "deck", "concrete"]):
        palette  = "Industrial Dark #111827 + Electric Orange + Steel Blue accents"
        hero_img = "Professional tradesperson on-site with modern tools"
        gallery  = "Project portfolio: before/after renovation photos"
        cta_copy = f"Get a Free Estimate — 24-Hour Response in {location.split()[0]}"
    elif any(k in niche_lower for k in ["barber", "salon", "nail", "massage", "tattoo", "groom", "spa"]):
        palette  = "Luxury Black #0a0a0a + Rose Gold + Champagne — upscale editorial"
        hero_img = "Moody editorial-style photo of the studio environment"
        gallery  = "Client transformation portfolio with clean studio photography"
        cta_copy = "Book Your Appointment — Instant Online Confirmation"
    elif any(k in niche_lower for k in ["food", "cater", "bakery", "meal", "restaurant", "truck"]):
        palette  = "Warm Charcoal #1c1410 + Amber + Cream — rich food editorial"
        hero_img = "Close-up food photography with steam and warm lighting"
        gallery  = "Menu showcase with full-bleed food photography"
        cta_copy = f"Order or Book Now — Serving {location.split()[0]}"
    elif any(k in niche_lower for k in ["photo", "video", "creative", "design", "market", "brand"]):
        palette  = "Jet Black #050505 + Electric Indigo + White — ultra-minimal portfolio"
        hero_img = "Full-screen portfolio reel or signature hero image"
        gallery  = "Masonry portfolio grid with lightbox viewer"
        cta_copy = "View My Work — Book a Discovery Call"
    elif any(k in niche_lower for k in ["chiro", "physio", "therapy", "dental", "health", "wellness", "yoga", "pilates", "acupuncture", "optom"]):
        palette  = "Calm White #fafbff + Soft Navy + Sage Green — clinical trust"
        hero_img = "Bright welcoming clinic or studio interior"
        gallery  = "Service cards with wellness lifestyle photography"
        cta_copy = f"Book Your First Appointment in {location.split()[0]}"
    elif any(k in niche_lower for k in ["dog", "pet", "groom", "boarding", "walk"]):
        palette  = "Playful Warm White + Sunny Yellow + Sky Blue — friendly and approachable"
        hero_img = "Happy pets in a bright clean environment"
        gallery  = "Client pet photos with before/after grooming grid"
        cta_copy = "Book Your Pet's Appointment Today"
    else:
        palette  = "Deep Dark #0b0f19 + Electric Blue #6366f1 + Neon Purple #8b5cf6"
        hero_img = "High-quality professional brand or service photo"
        gallery  = "Portfolio / before-after showcase grid"
        cta_copy = f"Get Started in {location.split()[0]} — Book Online Today"

    features = []
    if not audit.get("mobile_ready"):   features.append("• Mobile-first design — Lighthouse 95+ score")
    if not audit.get("has_contact"):    features.append("• Integrated booking / quote request form")
    if not audit.get("has_ssl"):        features.append("• HTTPS + SSL from day one")
    if not audit.get("has_meta_desc"): features.append("• Full on-page SEO: title, meta, local schema markup")
    if load_ms and load_ms > 3000:     features.append(f"• Speed fix: {load_ms}ms → target <1.5s")
    if insta or tiktok:                features.append(f"• {channel} feed embed for live social proof")
    features.append(f"• Google Maps embed + local schema for {location} SEO")
    features.append("• Smooth scroll animations (Framer Motion)")
    features_str = "\n".join(features)

    blueprint = (
        f"{'━'*46}\n"
        f"BLUEPRINT: {biz.upper()}\n"
        f"{'━'*46}\n"
        f"BUSINESS:  {niche.title()} · {location}\n"
        f"TIER:      {tier.replace('_',' ').title()} | Site Score: {score}/10\n\n"
        f"STACK:\n"
        f"  Next.js 14 (App Router) + Tailwind CSS + Framer Motion\n\n"
        f"DESIGN:\n"
        f"  Palette: {palette}\n"
        f"  Hero:    {hero_img}\n"
        f"  Gallery: {gallery}\n\n"
        f"PAGES:\n"
        f"  1. Home     — Hero + services + social proof + CTA\n"
        f"  2. Services — Detailed service cards with pricing\n"
        f"  3. Gallery  — Portfolio / before-after showcase\n"
        f"  4. About    — Story, team, trust signals\n"
        f"  5. Contact  — Booking form + Google Maps + hours\n\n"
        f"KEY FEATURES (pain-driven for this lead):\n"
        f"{features_str}\n\n"
        f"HERO HEADLINE:\n"
        f'  \"The #{location.split()[0]} {niche.title()} People Trust Most — Book in 60 Seconds.\"\n\n'
        f"CTA BUTTON:\n"
        f'  \"{cta_copy}\"\n\n'
        f"SEO TARGETS:\n"
        f'  Primary:   \"{niche} {location}\"\n'
        f'  Secondary: \"best {niche} near me\", \"{niche} {location.split()[0]}\"'
    )

    # ── Gmail compose link ─────────────────────────────────────────────────
    gmail_link = ""
    if email:
        subject = f"Quick question about {biz}"
        gmail_link = (
            "https://mail.google.com/mail/?view=cm"
            f"&to={urllib.parse.quote(email)}"
            f"&su={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(dm)}"
        )

    # ── Audit checks ───────────────────────────────────────────────────────
    ssl_str     = _check(bool(audit.get("has_ssl")),      "HTTPS Active",         "No SSL — Insecure")
    mobile_str  = _check(bool(audit.get("mobile_ready")), "Mobile Optimised",     "Not Mobile-Friendly")
    contact_str = _check(bool(audit.get("has_contact")),  "Contact Form Present", "No Contact Form")
    meta_str    = _check(bool(audit.get("has_meta_desc")),"SEO Meta Present",     "No Meta Description")
    speed_str   = (
        _check(load_ms and load_ms < 3000,
               f"Fast ({load_ms}ms)", f"Slow ({load_ms}ms)")
        if load_ms else '<span style="color:#64748b">⏱ Speed Unknown</span>'
    )

    # ── Pain pills ─────────────────────────────────────────────────────────
    pain_html = "".join(_pill(p) for p in pain) if pain else _pill("No major issues", "#22c55e")

    # ── Tier badge ─────────────────────────────────────────────────────────
    tier_colors = {"solo": "#f97316", "small_team": "#3b82f6", "medium": "#8b5cf6"}
    tier_col = tier_colors.get(tier, "#6366f1")
    tier_badge = (
        f'<span style="padding:3px 10px;background:{tier_col}22;color:{tier_col};'
        f'border:1px solid {tier_col}44;border-radius:20px;font-size:10px;font-weight:800;'
        f'letter-spacing:1px">{tier.upper().replace("_"," ")}</span>'
    )

    # ── Intelligence rows ──────────────────────────────────────────────────
    intel_rows = ""
    if url:
        intel_rows += _row("🌐", "Website", url[:50] + ("…" if len(url) > 50 else ""), url)
    if phone:
        intel_rows += _row("📞", "Phone", phone, f"tel:{phone}")
    if email:
        intel_rows += _row("✉️", "Email", email, f"mailto:{email}")
    if insta:
        handle = insta.lstrip("@")
        intel_rows += _row("📸", "Instagram", insta, f"https://instagram.com/{handle}")
    if facebook:
        fb_link = facebook if facebook.startswith("http") else f"https://{facebook}"
        intel_rows += _row("👥", "Facebook", "View Page", fb_link)
    if tiktok:
        handle = tiktok.lstrip("@")
        intel_rows += _row("🎵", "TikTok", tiktok, f"https://tiktok.com/@{handle}")
    if twitter:
        handle = twitter.lstrip("@")
        intel_rows += _row("🐦", "Twitter/X", twitter, f"https://x.com/{handle}")
    if whatsapp:
        intel_rows += _row("💬", "WhatsApp", "Message Now", f"https://{whatsapp}")
    if not intel_rows:
        intel_rows = _row("⚠️", "Status", "No digital footprint found — prime target", "")

    # ── Gmail button ───────────────────────────────────────────────────────
    gmail_btn = ""
    if gmail_link:
        gmail_btn = (
            f'<a href="{gmail_link}" target="_blank" style="display:inline-block;'
            f'margin-top:16px;padding:12px 28px;'
            f'background:linear-gradient(90deg,#ec4899,#8b5cf6);color:#fff;'
            f'border-radius:8px;font-weight:800;font-size:13px;text-decoration:none;'
            f'letter-spacing:.5px">📧 OPEN IN GMAIL →</a>'
        )

    # ── Snippet ────────────────────────────────────────────────────────────
    snippet_html = ""
    if snippet:
        snippet_html = (
            f'<div style="background:rgba(255,255,255,0.02);border-left:3px solid #6366f1;'
            f'padding:14px 18px;color:#94a3b8;font-size:13px;line-height:1.6;'
            f'font-style:italic;margin-bottom:24px;border-radius:0 8px 8px 0">'
            f'"{snippet}"</div>'
        )

    return f'''
<div style="background:#111520;border:1px solid rgba(255,255,255,0.07);
            border-radius:18px;margin-bottom:28px;overflow:hidden;
            box-shadow:0 12px 40px -10px rgba(0,0,0,0.8)">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,rgba(99,102,241,0.15),rgba(11,15,25,1));
              padding:28px 32px;border-bottom:1px solid rgba(255,255,255,0.05)">
    <table style="width:100%;border-collapse:collapse"><tr>
      <td style="vertical-align:top">
        <div style="color:#6366f1;font-size:10px;font-weight:900;letter-spacing:2px;
                    text-transform:uppercase;margin-bottom:6px">
          TARGET #{idx:02d} · {niche.upper()}
        </div>
        <div style="color:#ffffff;font-size:24px;font-weight:900;
                    letter-spacing:-0.5px;margin-bottom:6px">{biz}</div>
        <div style="color:#94a3b8;font-size:13px">📍 {location}</div>
      </td>
      <td style="text-align:right;vertical-align:top;min-width:130px">
        <div style="margin-bottom:8px">{_badge(score)}</div>
        <div>{tier_badge}</div>
      </td>
    </tr></table>
  </div>

  <div style="padding:28px 32px">
    {snippet_html}

    <!-- 2-col: Intel + Audit -->
    <table style="width:100%;border-collapse:collapse;margin-bottom:24px"><tr>
      <td style="width:52%;padding-right:10px;vertical-align:top">
        <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                    border-radius:12px;overflow:hidden">
          <div style="padding:10px 16px;background:rgba(255,255,255,0.03);
                      border-bottom:1px solid rgba(255,255,255,0.05);
                      font-size:11px;font-weight:800;color:#94a3b8;
                      letter-spacing:1.5px;text-transform:uppercase">
            🔍 Intelligence
          </div>
          <table style="width:100%;border-collapse:collapse">{intel_rows}</table>
        </div>
      </td>
      <td style="width:48%;padding-left:10px;vertical-align:top">
        <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
                    border-radius:12px;overflow:hidden">
          <div style="padding:10px 16px;background:rgba(255,255,255,0.03);
                      border-bottom:1px solid rgba(255,255,255,0.05);
                      font-size:11px;font-weight:800;color:#94a3b8;
                      letter-spacing:1.5px;text-transform:uppercase">
            ⚙️ Technical Audit
          </div>
          <table style="width:100%;border-collapse:collapse">
            {_row("🔒", "SSL",     ssl_str)}
            {_row("📱", "Mobile",  mobile_str)}
            {_row("📥", "Contact", contact_str)}
            {_row("🔎", "SEO",     meta_str)}
            {_row("⚡", "Speed",   speed_str)}
          </table>
        </div>
      </td>
    </tr></table>

    <!-- Pain Points -->
    <div style="margin-bottom:24px">
      <div style="font-size:11px;font-weight:800;color:#94a3b8;letter-spacing:1.5px;
                  text-transform:uppercase;margin-bottom:10px">⚠️ Pain Points</div>
      {pain_html}
    </div>

    <!-- Blueprint Prompt -->
    <div style="background:rgba(99,102,241,0.06);border:1px solid rgba(99,102,241,0.2);
                border-radius:12px;padding:22px;margin-bottom:20px">
      <div style="font-size:11px;font-weight:800;color:#818cf8;letter-spacing:1.5px;
                  text-transform:uppercase;margin-bottom:12px">🏗️ Website Blueprint</div>
      <pre style="white-space:pre-wrap;font-size:12px;color:#cbd5e1;
                  font-family:Consolas,'SF Mono',monospace;
                  line-height:1.7;margin:0">{blueprint}</pre>
    </div>

    <!-- Outreach DM -->
    <div style="background:rgba(236,72,153,0.05);border:1px solid rgba(236,72,153,0.2);
                border-radius:12px;padding:22px">
      <div style="font-size:11px;font-weight:800;color:#f472b6;letter-spacing:1.5px;
                  text-transform:uppercase;margin-bottom:12px">💬 Outreach Message</div>
      <pre style="white-space:pre-wrap;font-size:13px;color:#f8fafc;
                  font-family:-apple-system,BlinkMacSystemFont,sans-serif;
                  line-height:1.7;margin:0">{dm}</pre>
      {gmail_btn}
    </div>
  </div>
</div>'''


# ── Master HTML builder ───────────────────────────────────────────────────────

def build_html(targets: list[dict]) -> str:
    today  = date.today().strftime("%B %d, %Y")
    cards  = "".join(_card(t, i + 1) for i, t in enumerate(targets))
    n      = len(targets)
    critical = sum(1 for t in targets if t.get("website_score", 10) <= 3)
    comms    = sum(1 for t in targets if t.get("phone") or t.get("email"))
    socials  = sum(1 for t in targets if t.get("instagram") or t.get("facebook") or t.get("tiktok"))

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Antigravity Intelligence Report — {today}</title>
<style>
  body{{margin:0;padding:0;background:#050810;
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
  a{{color:#818cf8;text-decoration:none}}
  a:hover{{text-decoration:underline}}
  pre{{margin:0}}
</style>
</head>
<body style="background:#050810;padding:40px 0">
<div style="max-width:820px;margin:0 auto;padding:0 16px">

  <!-- Masthead -->
  <div style="background:linear-gradient(180deg,#111520,#0a0c10);
              border:1px solid rgba(255,255,255,0.07);border-radius:24px;
              padding:48px 36px;margin-bottom:36px;text-align:center;
              box-shadow:0 24px 60px rgba(0,0,0,0.6)">
    <div style="display:inline-block;padding:5px 16px;
                background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.25);
                border-radius:30px;color:#818cf8;font-size:10px;font-weight:900;
                letter-spacing:2.5px;text-transform:uppercase;margin-bottom:20px">
      Antigravity · Autonomous Intelligence
    </div>
    <div style="color:#fff;font-size:36px;font-weight:900;
                letter-spacing:-1px;margin-bottom:10px;line-height:1.1">
      Target Dossier
    </div>
    <div style="color:#64748b;font-size:14px;margin-bottom:32px">{today}</div>

    <!-- Stats row -->
    <table style="width:100%;max-width:480px;margin:0 auto;border-collapse:collapse">
      <tr>
        <td style="text-align:center;padding:8px;border-right:1px solid rgba(255,255,255,0.07)">
          <div style="color:#fff;font-size:32px;font-weight:900">{n}</div>
          <div style="color:#64748b;font-size:10px;font-weight:800;
                      letter-spacing:1px;text-transform:uppercase;margin-top:2px">Verified</div>
        </td>
        <td style="text-align:center;padding:8px;border-right:1px solid rgba(255,255,255,0.07)">
          <div style="color:#ef4444;font-size:32px;font-weight:900">{critical}</div>
          <div style="color:#64748b;font-size:10px;font-weight:800;
                      letter-spacing:1px;text-transform:uppercase;margin-top:2px">Critical</div>
        </td>
        <td style="text-align:center;padding:8px;border-right:1px solid rgba(255,255,255,0.07)">
          <div style="color:#10b981;font-size:32px;font-weight:900">{comms}</div>
          <div style="color:#64748b;font-size:10px;font-weight:800;
                      letter-spacing:1px;text-transform:uppercase;margin-top:2px">Contactable</div>
        </td>
        <td style="text-align:center;padding:8px">
          <div style="color:#f59e0b;font-size:32px;font-weight:900">{socials}</div>
          <div style="color:#64748b;font-size:10px;font-weight:800;
                      letter-spacing:1px;text-transform:uppercase;margin-top:2px">Social Found</div>
        </td>
      </tr>
    </table>
  </div>

  <!-- Lead Cards -->
  {cards}

  <!-- Footer -->
  <div style="text-align:center;color:#334155;font-size:12px;
              padding:32px 0;letter-spacing:.5px">
    ✦ ANTIGRAVITY AUTONOMOUS PIPELINE ✦<br>
    <span style="font-size:10px;opacity:.5;display:block;margin-top:6px">
      Built autonomously · Next cycle in 24 hours
    </span>
  </div>

</div>
</body>
</html>'''


# ── Send ──────────────────────────────────────────────────────────────────────

def send_dossier_email(targets: list[dict]) -> bool:
    """Build and send the full dossier email. Returns True on success."""
    if not targets:
        log.warning("[email] No targets — skipping send")
        return False

    today   = date.today().strftime("%B %d, %Y")
    subject = f"🎯 {len(targets)} Fresh Leads — Antigravity · {today}"
    html    = build_html(targets)

    # Plain-text fallback
    lines = []
    for i, t in enumerate(targets, 1):
        biz = t.get("business_name") or t.get("title") or "?"
        lines.append(
            f"#{i:02d} {biz} | {t.get('niche','?')} | {t.get('location','?')} | "
            f"Score:{t.get('website_score','?')}/10 | "
            f"Phone:{t.get('phone') or '—'} | Email:{t.get('email') or '—'} | "
            f"IG:{t.get('instagram') or '—'} | URL:{t.get('url','')}"
        )
    text = "\n".join(lines)

    if not GMAIL_APP_PASSWORD:
        print(f"[email] No app password configured — printing to console:\n{text}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(EMAIL_FROM, GMAIL_APP_PASSWORD)
            smtp.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        log.info(f"[email] ✓ Dossier sent → {EMAIL_TO}")
        print(f"[email] ✓ Rich dossier sent → {EMAIL_TO}")
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("[email] ✗ Authentication failed — check GMAIL_APP_PASSWORD in .env")
        print("[email] ✗ Gmail auth failed — check your app password in .env")
    except smtplib.SMTPException as exc:
        log.error(f"[email] ✗ SMTP error: {exc}")
        print(f"[email] ✗ SMTP error: {exc}")
    except Exception as exc:
        log.error(f"[email] ✗ Unexpected error: {exc}")
        print(f"[email] ✗ Failed: {exc}")
    return False


# ══════════════════════════════════════════════════════════════════════════════
#  AUTONOMOUS OUTREACH — sends cold emails directly to each critical lead
# ══════════════════════════════════════════════════════════════════════════════

import hashlib as _hashlib

def _stable_hash(s: str) -> int:
    """H3 fix: MD5-based hash — stable across Python processes (unlike hash())."""
    return int(_hashlib.md5(s.encode("utf-8", errors="replace")).hexdigest(), 16)


def _outreach_subject(t: dict) -> str:
    """5 rotating subject lines — stable per business name (MD5, not hash())."""
    biz   = t.get("business_name") or "your business"
    # M4 fix: guard against empty location — split() on empty string returns []
    loc_parts = (t.get("location") or "").split()
    location  = loc_parts[0] if loc_parts else "your area"

    variants = [
        f"Quick question about {biz}",
        f"thoughts on your website",
        f"found your business in {location}",
        f"quick thing about {biz}'s website",
        f"trying to reach the owner of {biz}",
    ]
    idx = _stable_hash(biz) % len(variants)
    return variants[idx]


def _outreach_html(t: dict) -> str:
    """
    Beautiful light-mode cold outreach email.
    Looks hand-crafted, not like a mass mailer.
    Renders perfectly in Gmail, Outlook, Apple Mail.
    """
    biz      = html.escape(t.get("business_name") or t.get("title") or "there")
    niche    = html.escape(t.get("niche", "service"))
    location = html.escape(t.get("location", "your area"))
    score    = t.get("website_score", 0)
    pain     = [html.escape(p) for p in (t.get("pain_points") or [])]
    insta    = html.escape(t.get("instagram", ""))
    tiktok   = html.escape(t.get("tiktok", ""))
    snippet  = html.escape((t.get("snippet") or "")[:200])

    city = location.split()[0] if location else "your city"

    # ── Pick a voice (deterministic per business — MD5 stable across processes) ─
    voice = _stable_hash(biz) % 5

    if score <= 2:
        problem_line = (
            f"I checked out {biz}'s website and honestly — "
            f"it's barely working. No HTTPS, breaks on mobile, "
            f"and Google can't even index it properly."
        )
    elif score <= 4:
        problem_line = (
            f"I pulled up {biz}'s website and a few things "
            f"jumped out — it's not mobile-friendly and there's "
            f"no way for people to book or contact you online. "
            f"That's real money walking out the door every week."
        )
    else:
        problem_line = (
            f"I had a look at {biz}'s website — the foundation "
            f"is there but it's missing the things that actually "
            f"turn visitors into paying customers."
        )

    if insta or tiktok:
        channel = "Instagram" if insta else "TikTok"
        opener_lines = [
            f"saw your {channel} — the work speaks for itself.",
            f"came across your {channel} and actually impressed.",
            f"your {channel} content is solid. had to reach out.",
            f"found you through {channel} — great stuff.",
            f"your {channel} audience clearly loves what you do.",
        ]
        opener = opener_lines[voice]
        bridge = (
            f"You've clearly got an audience that trusts you. "
            f"The gap is your website — it's not matching the "
            f"quality of what you actually do."
        )
    elif snippet:
        openers = [
            f"was searching for {niche} in {city} and your name kept coming up.",
            f"researching {niche} businesses in {city} — yours stood out.",
            f"came across {biz} while looking into {niche} in {city}.",
            f"found your business while digging into {niche} in {city}.",
            f"your {niche} business in {city} popped up and I had to look closer.",
        ]
        opener = openers[voice]
        bridge = (
            f"Your customers clearly rate you. "
            f"The problem is your website isn't closing them — "
            f"most people will check online before calling."
        )
    else:
        openers = [
            f"was looking for top {niche} businesses in {city}.",
            f"researching {niche} services in {city} this week.",
            f"came across {biz} while doing some market research.",
            f"found your {niche} business in {city}.",
            f"I was digging into local {niche} services in {city}.",
        ]
        opener = openers[voice]
        bridge = (
            f"A better website means people find you, "
            f"trust you instantly, and book — without you "
            f"having to chase anyone."
        )

    cta_lines = [
        "Want me to send you the link?",
        "Can I send it over?",
        "Should I drop the link?",
        "Want to take a look?",
        "Keen to see it?",
    ]
    cta = cta_lines[voice]

    first_pain = pain[0] if pain else f"the website isn't reflecting the quality of your {niche} work"

    # ── What I built section ──────────────────────────────────────────────
    niche_lower = niche.lower()
    if any(k in niche_lower for k in ["auto", "car", "detail", "wrap", "tire"]):
        built_desc = f"a dark, high-energy site with a cinematic before/after gallery, an instant booking form, and your services laid out cleanly with pricing"
    elif any(k in niche_lower for k in ["landscape", "lawn", "tree", "pool", "garden"]):
        built_desc = f"a clean, property-focused site with a transformation gallery, free quote form, and local SEO targeting {city}"
    elif any(k in niche_lower for k in ["clean", "maid", "pressure", "carpet", "window"]):
        built_desc = f"a bright, trust-first site with before/after photos, same-day quote request, and a results section that shows the difference"
    elif any(k in niche_lower for k in ["hvac", "plumb", "electr", "roof", "handyman"]):
        built_desc = f"a solid, no-nonsense trades site with a free estimate form, project gallery, service area map, and 24/7 emergency call button"
    elif any(k in niche_lower for k in ["barber", "salon", "nail", "massage", "tattoo"]):
        built_desc = f"an editorial-style booking site with a client transformation gallery, online appointment calendar, and a portfolio that sells the experience"
    elif any(k in niche_lower for k in ["food", "cater", "bakery", "meal"]):
        built_desc = f"a warm, food-focused site with full-bleed menu photography, an order/enquiry form, and a story section that makes people hungry"
    elif any(k in niche_lower for k in ["photo", "video", "design", "market"]):
        built_desc = f"a minimal, portfolio-first site with a masonry gallery, case study section, and a discovery call booking flow"
    elif any(k in niche_lower for k in ["chiro", "physio", "dental", "health", "yoga"]):
        built_desc = f"a calm, trust-building site with a new patient booking form, services overview, practitioner bio, and local SEO for {city}"
    elif any(k in niche_lower for k in ["dog", "pet", "groom", "boarding"]):
        built_desc = f"a friendly, photo-led site with a pet booking form, meet-the-team section, and a gallery of happy clients"
    else:
        built_desc = f"a clean, professional site with a booking/quote form, services overview, testimonial section, and local SEO for {city}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A website built for {biz}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif">
<div style="max-width:580px;margin:40px auto;padding:0 16px">

  <!-- Card -->
  <div style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

    <!-- Top accent bar -->
    <div style="height:4px;background:linear-gradient(90deg,#6366f1,#ec4899)"></div>

    <!-- Body -->
    <div style="padding:40px 36px">

      <!-- Greeting -->
      <p style="margin:0 0 24px;font-size:16px;color:#0f172a;line-height:1.6">
        Hey {biz},
      </p>

      <!-- Opener -->
      <p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.7">
        {opener}
      </p>

      <!-- Problem -->
      <p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.7">
        {problem_line}
      </p>

      <!-- Bridge -->
      <p style="margin:0 0 28px;font-size:16px;color:#0f172a;line-height:1.7">
        {bridge}
      </p>

      <!-- What I built box -->
      <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:24px;margin-bottom:28px">
        <p style="margin:0 0 10px;font-size:12px;font-weight:700;color:#6366f1;letter-spacing:1.5px;text-transform:uppercase">
          What I have in mind for you
        </p>
        <p style="margin:0;font-size:15px;color:#1e293b;line-height:1.7">
          I have a few ideas for {built_desc} — completely free, no commitment. 
          I can put something together for you to see if you like it.
        </p>
      </div>

      <!-- Key issue callout -->
      <div style="border-left:3px solid #f97316;padding:14px 18px;background:#fff7ed;border-radius:0 8px 8px 0;margin-bottom:28px">
        <p style="margin:0;font-size:14px;color:#9a3412;line-height:1.6">
          <strong>The main issue I spotted:</strong> {first_pain}
        </p>
      </div>

      <!-- The ask -->
      <p style="margin:0 0 8px;font-size:16px;color:#0f172a;line-height:1.7">
        If you don't like my ideas, keep the feedback, no hard feelings.
      </p>

      <p style="margin:0 0 32px;font-size:16px;color:#0f172a;line-height:1.7">
        {cta}
      </p>

      <!-- Signature -->
      <p style="margin:0 0 4px;font-size:15px;color:#0f172a;font-weight:600">{SENDER_NAME}</p>
      <p style="margin:0;font-size:14px;color:#64748b">{SENDER_HANDLE} · Freelance Web Designer</p>

    </div>

    <!-- Footer -->
    <div style="padding:20px 36px;background:#f8fafc;border-top:1px solid #e2e8f0">
      <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.6">
        You're receiving this because your business came up while I was researching
        {niche} services in {location}. This is a one-time personal outreach — not a mailing list.
        If you'd rather not hear from me, just reply with "no thanks" and I won't reach out again.
      </p>
    </div>

  </div>

  <!-- Bottom note -->
  <p style="text-align:center;margin:20px 0 0;font-size:12px;color:#94a3b8">
    Sent personally · Not a bulk mailer
  </p>

</div>
</body>
</html>"""


def _outreach_text(t: dict) -> str:
    """Plain-text version of the outreach email with Spintax."""
    import random
    biz   = t.get("business_name") or "there"
    niche = t.get("niche", "service")
    location = t.get("location", "")
    pain  = t.get("pain_points") or []
    first_pain = pain[0].lower() if pain else f"the online presence doesn't match the quality of the {niche} work"

    greetings = [f"Hey {biz},", f"Hi {biz},", f"Hello {biz},"]
    openers = [
        f"I came across your business while looking at {niche} services in {location}.",
        f"I was researching top {niche} businesses in {location} and found your profile.",
        f"I noticed your {niche} business while searching around {location}."
    ]
    hooks = [
        f"I had a look at your website and noticed {first_pain}.",
        f"Main thing I spotted on your site: {first_pain}.",
        f"I realized your website might be costing you bookings. Specifically, {first_pain}."
    ]
    ctas = [
        "I'm a freelance web designer and I have a few ideas for a new website. Want me to send over a quick link to show you what's possible?",
        "I'd love to build you a free custom design concept to show you what's possible. Open to seeing it?",
        "I have a few ideas that would fix this and get you more inbound leads. Want me to send them over?"
    ]
    signoffs = ["Best,", "Cheers,", "Thanks,", "—"]

    return (
        f"{random.choice(greetings)}\n\n"
        f"{random.choice(openers)} {random.choice(hooks)}\n\n"
        f"{random.choice(ctas)}\n\n"
        f"{random.choice(signoffs)}\n"
        f"{SENDER_NAME} | {SENDER_HANDLE}\n\n"
        f"---\n"
        f"This is a one-time personal outreach. Reply 'no thanks' to opt out."
    )


def _is_business_hours(location: str) -> bool:
    from datetime import datetime
    utc_hour = datetime.utcnow().hour
    loc = location.lower()
    
    offset = 0 # default UTC (UK)
    if any(x in loc for x in ["ca", "nv", "wa", "or", "los angeles", "san", "las vegas", "seattle", "portland"]):
        offset = -8 # PT
    elif any(x in loc for x in ["co", "az", "nm", "ut", "id", "denver", "phoenix", "salt lake"]):
        offset = -7 # MT
    elif any(x in loc for x in ["tx", "il", "mn", "mo", "ks", "ne", "wi", "chicago", "dallas", "houston"]):
        offset = -6 # CT
    elif any(x in loc for x in ["ny", "fl", "ga", "nc", "va", "pa", "ma", "new york", "miami", "atlanta", "boston"]):
        offset = -5 # ET
    elif any(x in loc for x in ["germany", "netherlands", "spain", "france", "italy", "switzerland", "poland", "sweden", "norway", "denmark", "berlin", "paris", "madrid", "rome"]):
        offset = +1 # CET
        
    local_hour = (utc_hour + offset) % 24
    return 8 <= local_hour <= 17


def send_outreach_emails(
    targets: list[dict],
    score_threshold: int = 8,
    max_per_cycle: int = 5,
) -> dict:
    """
    Autonomously sends cold outreach emails to every critical lead that
    has an email address. Called automatically by the Researcher after each cycle.

    Fixes applied (per Sonnet audit):
      C4: Auth failure marks ALL un-attempted targets as failed
      C6: Credentials read lazily (not frozen at module import time)
      L3: Single SMTP connection reused for all emails — no repeated TLS handshakes
      M6: skipped = O(1) slice, not O(n²) list membership test
      L2: No sleep after the last email
      C3: Tracks contacted_emails in shared state to prevent repeat outreach
    """
    import os
    # C6 fix: read credentials HERE (not at module level) so hot-reload works
    app_password = os.getenv("GMAIL_APP_PASSWORD", "")
    email_from   = os.getenv("EMAIL_FROM", "")
    email_to     = os.getenv("EMAIL_TO", email_from)

    if not app_password:
        log.warning("[outreach] No Gmail app password - skipping autonomous outreach")
        return {"sent": [], "skipped": targets, "failed": []}

    # Load contacted history - prevents same business getting emailed every cycle
    from utils.state_manager import read_state, write_state
    state         = read_state()
    contacted_set = set(state.get("contacted_emails", []))
    contacted_meta = state.get("contacted_emails_meta", [])

    # Filter: must have email, score below threshold, and not already contacted
    eligible = [
        t for t in targets
        if t.get("email")
        and t.get("website_score", 10) <= score_threshold
        and t["email"].lower() not in contacted_set
        and _is_business_hours(t.get("location", ""))
    ]

    if not eligible:
        log.info("[outreach] No eligible leads inside business hours this cycle")
        return {"sent": [], "skipped": targets, "failed": []}

    to_send = eligible[:max_per_cycle]
    skipped = eligible[max_per_cycle:]   # M6 fix: O(1) slice

    log.info(f"[outreach] {len(eligible)} eligible leads - sending to {len(to_send)} (cap={max_per_cycle})")
    print(f"\n[outreach] Sending autonomous outreach to {len(to_send)} critical leads...")

    results: dict = {"sent": [], "skipped": skipped, "failed": []}
    from datetime import datetime

    try:
        # L3 fix: single SMTP connection for all emails (no repeated TLS handshakes)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(email_from, app_password)

            for i, t in enumerate(to_send):
                biz      = t.get("business_name") or t.get("title") or "?"
                to_email = t["email"]
                subject  = _outreach_subject(t)
                html     = _outreach_html(t)
                plain    = _outreach_text(t)

                msg = MIMEMultipart("alternative")
                msg["Subject"]  = subject
                msg["From"]     = "{SENDER_NAME} <" + email_from + ">"
                msg["To"]       = to_email
                msg["Reply-To"] = email_from
                if email_to:
                    msg["Bcc"] = email_to
                msg.attach(MIMEText(plain, "plain", "utf-8"))
                msg.attach(MIMEText(html,  "html", "utf-8"))

                try:
                    recipients = [to_email]
                    if email_to:
                        recipients.append(email_to)
                    smtp.sendmail(email_from, recipients, msg.as_string())
                    log.info(f"[outreach] Sent to {to_email} ({biz})")
                    print(f"  OK: {biz} / {to_email} | subject: {subject}")
                    results["sent"].append({"biz": biz, "email": to_email, "subject": subject})
                    contacted_set.add(to_email.lower())
                    contacted_meta.append({
                        "email": to_email.lower(),
                        "target_id": t.get("id"),
                        "sent_at": datetime.utcnow().isoformat()
                    })
                except smtplib.SMTPRecipientsRefused:
                    log.warning(f"[outreach] Recipient refused: {to_email}")
                    results["failed"].append({"biz": biz, "email": to_email, "reason": "refused"})
                except Exception as exc:
                    log.error(f"[outreach] Failed {to_email}: {exc}")
                    results["failed"].append({"biz": biz, "email": to_email, "reason": str(exc)})

                # L2 fix: no sleep after the last email
                if i < len(to_send) - 1:
                    import time
                    import random
                    time.sleep(random.uniform(8, 15))

    except smtplib.SMTPAuthenticationError:
        # C4 fix: mark ALL un-attempted targets as failed
        already_attempted = {r["email"] for r in results["sent"] + results["failed"]}
        for t in to_send:
            if t["email"] not in already_attempted:
                results["failed"].append({
                    "biz":    t.get("business_name", "?"),
                    "email":  t["email"],
                    "reason": "auth_failure",
                })
        log.error("[outreach] Gmail auth failed - check GMAIL_APP_PASSWORD in .env")
    except Exception as exc:
        log.error(f"[outreach] SMTP connection error: {exc}")

    # Persist contacted_emails so next cycle skips already-reached businesses
    state["contacted_emails"] = list(contacted_set)
    state["contacted_emails_meta"] = contacted_meta
    write_state(state)

    total_sent = len(results["sent"])
    print(
        f"\n[outreach] Done - {total_sent} sent, "
        f"{len(results['failed'])} failed, "
        f"{len(results['skipped'])} skipped (over cap)\n"
    )
    return results


# ══════════════════════════════════════════════════════════════════════════════
#  HUMANIZED VIDEO OUTREACH — sends proof-of-pain video emails (Phase 3)
# ══════════════════════════════════════════════════════════════════════════════

def _video_subject(t: dict) -> str:
    """
    Optimized subject line formula — curiosity gap + specificity.
    Fixes Problem #6: subject line is now the campaign, not an afterthought.

    Rotating between 4 high-converting formats, stable per business (MD5).
    """
    biz       = t.get("business_name") or "your business"
    loc_parts = (t.get("location") or "").split()
    city      = loc_parts[0] if loc_parts else "your area"
    load_ms   = t.get("load_ms")
    load_s    = f"{load_ms/1000:.0f}s" if load_ms else "slow"

    variants = [
        f"Quick video about {biz}'s mobile site",
        f"Saw {biz} online — noticed one thing",
        f"{city} {(t.get('niche') or 'business')} — your site loads in {load_s} (quick fix inside)",
        f"quick question about {biz}",
    ]
    idx = _stable_hash(biz) % len(variants)
    return variants[idx]


def _video_outreach_html(t: dict, video_url: str | None, video_path: str | None) -> str:
    """
    Humanized video outreach email template.
    - Subject-level specificity (fixes Problem #3: generic opener)
    - NO pricing in message #1 (fixes Problem #4)
    - NO fake demo claim — video IS the proof (fixes Problem #2)
    - Single CTA: reply "Yes" (fixes ONE ASK PER MESSAGE principle)
    """
    biz      = html.escape(t.get("business_name") or t.get("title") or "there")
    niche    = html.escape(t.get("niche", "business"))
    location = html.escape(t.get("location", "your area"))
    score    = t.get("website_score", 0)
    audit    = t.get("audit") or {}
    insta    = html.escape(t.get("instagram", ""))
    tiktok   = html.escape(t.get("tiktok", ""))
    pain     = [html.escape(p) for p in (t.get("pain_points") or [])]
    load_ms  = t.get("load_ms")

    city = location.split()[0] if location else "your city"

    # ── Specific flaw line (from video evidence) ──────────────────────────
    flaws = []
    if not audit.get("mobile_ready"):
        flaws.append("the layout breaks on mobile")
    if not audit.get("has_contact"):
        flaws.append('there\'s no "Call Now" or booking button visible')
    if load_ms and load_ms > 4000:
        flaws.append(f"it takes {load_ms/1000:.0f} seconds to load (most people leave after 3s)")
    if not audit.get("has_ssl"):
        flaws.append("Chrome shows 'Not Secure' to every visitor")
    if not audit.get("has_meta_desc"):
        flaws.append("Google can't find it properly")

    specific_flaw = flaws[0] if flaws else pain[0] if pain else "something that's costing you bookings"

    # ── Opener specificity (social vs search) ────────────────────────────
    if t.get("icebreaker"):
        opener = t.get("icebreaker")
        social_note = ""
    elif insta or tiktok:
        channel = "Instagram" if insta else "TikTok"
        opener = f"Saw you rank near the top on Maps while I was looking at {niche} in {city}."
        social_note = f'I also found your {channel} — the work looks great. Just wanted to flag this.'
    else:
        opener = f"Found {biz} while researching {niche} businesses in {city}."
        social_note = "Your reviews are solid. Just wanted to flag something I spotted."

    # ── Video proof section ───────────────────────────────────────────────
    if video_url:
        # We have a Drive/public link → show a thumbnail-style CTA
        video_section = f'''
      <!-- Video proof -->
      <div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:12px;
                  padding:24px;margin-bottom:28px;text-align:center">
        <p style="margin:0 0 12px;font-size:12px;font-weight:700;color:#6366f1;
                  letter-spacing:1.5px;text-transform:uppercase">
          45-Second Screen Recording
        </p>
        <a href="{html.escape(video_url)}" target="_blank"
           style="display:inline-block;padding:12px 28px;background:#1e293b;
                  color:#fff;border-radius:8px;font-weight:700;font-size:14px;
                  text-decoration:none">
          ▶ Watch the Recording
        </a>
        <p style="margin:12px 0 0;font-size:13px;color:#64748b">
          I recorded exactly what a customer on their phone sees when they visit your site.
        </p>
      </div>'''
    elif video_path:
        # Local file only (too small to upload) — reference it exists
        video_section = '''
      <div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:12px;
                  padding:24px;margin-bottom:28px">
        <p style="margin:0 0 8px;font-size:14px;font-weight:600;color:#1e293b">
          📱 I recorded a 45-second screen capture of your mobile site.
        </p>
        <p style="margin:0;font-size:14px;color:#475569;line-height:1.7">
          Reply "Yes" and I'll send it over — you'll see exactly what your
          customers see when they visit on their phone.
        </p>
      </div>'''
    else:
        # No video — use the screenshot approach
        video_section = '''
      <div style="border-left:3px solid #f97316;padding:14px 18px;
                  background:#fff7ed;border-radius:0 8px 8px 0;margin-bottom:28px">
        <p style="margin:0;font-size:14px;color:#9a3412;line-height:1.6">
          I did a quick mobile audit of your site and spotted a few things
          worth fixing — reply "Yes" and I'll send you a recording of what I found.
        </p>
      </div>'''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Quick note about {biz}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
<div style="max-width:580px;margin:40px auto;padding:0 16px">

  <div style="background:#ffffff;border-radius:16px;overflow:hidden;
              box-shadow:0 4px 24px rgba(0,0,0,0.08)">

    <!-- Top accent -->
    <div style="height:4px;background:linear-gradient(90deg,#6366f1,#ec4899)"></div>

    <!-- Body -->
    <div style="padding:40px 36px">

      <p style="margin:0 0 20px;font-size:16px;color:#0f172a;line-height:1.6">
        Hey {biz},
      </p>

      <p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.7">
        {opener}
      </p>

      <p style="margin:0 0 16px;font-size:16px;color:#0f172a;line-height:1.7">
        {social_note}
      </p>

      <!-- Specific flaw callout -->
      <div style="border-left:3px solid #ef4444;padding:14px 18px;
                  background:#fef2f2;border-radius:0 8px 8px 0;margin-bottom:28px">
        <p style="margin:0;font-size:14px;color:#991b1b;line-height:1.6">
          <strong>What I noticed:</strong> {specific_flaw}.
        </p>
      </div>

      {video_section}

      <!-- Single CTA — low friction -->
      <p style="margin:0 0 8px;font-size:16px;color:#0f172a;line-height:1.7">
        No pitch — just wanted to share. Reply <strong>"Yes"</strong>
        if you want me to send it over.
      </p>

      <p style="margin:0 0 32px;font-size:14px;color:#64748b;line-height:1.7">
        If it's not useful, no worries at all.
      </p>

      <!-- Signature -->
      <p style="margin:0 0 4px;font-size:15px;color:#0f172a;font-weight:600">{SENDER_NAME}</p>
      <p style="margin:0;font-size:14px;color:#64748b">{SENDER_HANDLE} · Freelance Web Designer</p>

    </div>

    <!-- Footer -->
    <div style="padding:20px 36px;background:#f8fafc;border-top:1px solid #e2e8f0">
      <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.6">
        You're receiving this because your business came up while I was researching
        {niche} services in {location}. One-time personal outreach — not a mailing list.
        Reply "no thanks" to opt out permanently.
      </p>
    </div>

  </div>
</div>
</body>
</html>"""


def send_video_outreach_email(
    t: dict,
    video_path: str | None = None,
    video_url: str | None = None,
) -> bool:
    """
    Send the Humanized Video Template to a single lead.
    Called by daemon.py Phase 3 after the VideoAuditorAgent runs.

    Args:
        t          — target dict from researcher
        video_path — local path to the .webm/.png file (optional)
        video_url  — public Drive/CDN URL to the video (optional, preferred)

    Returns True on success.
    """
    import os
    from datetime import datetime, timezone
    app_password = os.getenv("GMAIL_APP_PASSWORD", "")
    email_from   = os.getenv("EMAIL_FROM", "")
    email_to_bcc = os.getenv("EMAIL_TO", email_from)

    if not app_password or not email_from:
        log.warning("[video_email] Gmail credentials not configured — skipping")
        return False

    to_email = (t.get("email") or "").strip()
    if not to_email:
        log.warning("[video_email] No email for target — skipping")
        return False

    # Load contacted state to prevent re-send
    from utils.state_manager import read_state, write_state
    state = read_state()
    contacted_set  = set(e.lower() for e in state.get("contacted_emails", []))
    contacted_meta = state.get("contacted_emails_meta", [])

    if to_email.lower() in contacted_set:
        log.info(f"[video_email] Already contacted {to_email} — skipping")
        return False

    biz     = t.get("business_name") or t.get("title") or "there"
    subject = _video_subject(t)
    body_html = _video_outreach_html(t, video_url, video_path)

    # Plain text fallback
    plain = (
        f"Hey {biz},\n\n"
        f"I found your business while looking at {t.get('niche', 'services')} in "
        f"{t.get('location', 'your area')}.\n\n"
        f"I recorded a quick 45-second screen capture of your mobile site — "
        f"there's something worth seeing. Reply 'Yes' and I'll send it over.\n\n"
        f"— {SENDER_NAME} | {SENDER_HANDLE}\n\n"
        f"---\nOne-time personal outreach. Reply 'no thanks' to opt out."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"]  = subject
    msg["From"]     = f"{SENDER_NAME} <{email_from}>"
    msg["To"]       = to_email
    msg["Reply-To"] = email_from

    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        recipients = [to_email]

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(email_from, app_password)
            smtp.sendmail(email_from, recipients, msg.as_string())

        log.info(f"[video_email] ✓ Sent to {to_email} | subject: {subject}")

        # Mark as contacted
        contacted_set.add(to_email.lower())
        contacted_meta.append({
            "email":         to_email.lower(),
            "target_id":     t.get("id"),
            "business_name": biz,
            "sent_at":       datetime.now(timezone.utc).isoformat(),
            "followup_count": 0,
        })
        state["contacted_emails"]      = list(contacted_set)
        state["contacted_emails_meta"] = contacted_meta
        write_state(state)
        return True

    except smtplib.SMTPAuthenticationError:
        log.error("[video_email] Gmail auth failed — check GMAIL_APP_PASSWORD")
    except Exception as exc:
        log.error(f"[video_email] Send failed: {exc}")
    return False


def process_followups():
    import os
    from datetime import datetime, timezone
    from utils.state_manager import read_state, write_state

    app_password = os.getenv("GMAIL_APP_PASSWORD", "")
    email_from   = os.getenv("EMAIL_FROM", "")
    email_to     = os.getenv("EMAIL_TO", email_from)
    
    if not app_password:
        return

    state = read_state()
    meta = state.get("contacted_emails_meta", [])
    if not meta:
        return
        
    now = datetime.now(timezone.utc)
    to_update = []
    sent_count = 0
    
    for m in meta:
        try:
            sent_at = datetime.fromisoformat(m["sent_at"].replace("Z", "+00:00"))
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        days_since = (now - sent_at).days
        count = m.get("followup_count", 0)
        
        should_followup = False
        if days_since >= 2 and count == 0:
            should_followup = True
            msg_text = "Hi there, just bubbling this up in your inbox. Let me know if you have any questions!"
        elif days_since >= 5 and count == 1:
            should_followup = True
            msg_text = "Hi again, I don't want to be a bother so this will be my last email. If you're ever looking to upgrade your digital presence, feel free to reach out!"
            
        if should_followup:
            try:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
                    smtp.login(email_from, app_password)
                    
                    msg = MIMEMultipart("alternative")
                    msg["Subject"]  = "Re: Quick question about your website"
                    msg["From"]     = "{SENDER_NAME} <" + email_from + ">"
                    msg["To"]       = m["email"]
                    msg["Reply-To"] = email_from
                    if email_to:
                        msg["Bcc"] = email_to
                    msg.attach(MIMEText(msg_text, "plain", "utf-8"))
                    
                    recipients = [m["email"]]
                    if email_to:
                        recipients.append(email_to)
                        
                    smtp.sendmail(email_from, recipients, msg.as_string())
                    log.info(f"[outreach] Sent followup to {m['email']}")
                    m["followup_count"] = count + 1
                    sent_count += 1
            except Exception as e:
                log.error(f"[outreach] Failed to send followup to {m['email']}: {e}")
                
        to_update.append(m)
        
    if sent_count > 0:
        state["contacted_emails_meta"] = to_update
        write_state(state)
