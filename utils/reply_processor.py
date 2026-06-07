"""
reply_processor.py — Antigravity Autonomous Conversation Closer
================================================================
Reads Gmail inbox via IMAP, identifies replies to outreach emails,
classifies intent, and auto-replies to close the conversation.

Uses ONLY the existing GMAIL_APP_PASSWORD credential — no new MCP needed.
No AI call for classification — pure regex pattern matching is faster,
cheaper, and less brittle for the 3 clear intent categories.

Reply logic:
  YES / SEND CODE  → attach header snippet + soft pricing upsell
  HOW MUCH / PRICE → pricing + full mockup offer
  NO / UNSUBSCRIBE → polite farewell + mark Closed-Lost in state

Conversation history is saved in state['conversations'][email]
so every cycle builds on prior context, never loses thread.
"""

import os
import re
import imaplib
import email
import smtplib
import logging
import textwrap
from datetime import datetime, timezone
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

from utils.state_manager import read_state, write_state

log = logging.getLogger("antigravity.reply_processor")

_SENDER_NAME   = os.getenv("SENDER_NAME", "Your Name")
_SENDER_HANDLE = os.getenv("SENDER_HANDLE", "@your-handle")

# ── Intent patterns ───────────────────────────────────────────────────────────

_YES_PATTERNS = re.compile(
    r"\b(yes|yeah|yep|sure|send|show me|send it|send the|"
    r"love to|would love|let me see|absolutely|interested|"
    r"send code|show code|the code|link please|send link|"
    r"go ahead|sounds good|i'm in|im in|ok|okay)\b",
    re.IGNORECASE,
)

_PRICE_PATTERNS = re.compile(
    r"\b(how much|what.?s (the )?cost|what do you charge|"
    r"what.?s (the )?price|pricing|rates?|fees?|"
    r"cost[s ]|how much (does|would|do)|budget|afford)\b",
    re.IGNORECASE,
)

_NO_PATTERNS = re.compile(
    r"\b(no thanks|not interested|don.?t (contact|email|message|reach)"
    r"|stop|unsubscribe|remove me|please don.?t|no need|"
    r"we already have|have a web|not looking|pass)\b",
    re.IGNORECASE,
)

# ── Reply templates ───────────────────────────────────────────────────────────

_PRICE = os.getenv("OUTREACH_PRICE", "$1,500")


def _reply_yes(biz_name: str) -> tuple[str, str]:
    """Subject + body for a YES reply."""
    subject = "Re: Quick video about your mobile site"
    body = textwrap.dedent(f"""
        Brilliant! Here's the quick fix for the mobile header.

        I've attached a snippet you can drop into your existing site right now
        — it adds a sticky "Call Now" button that shows on every page on mobile.

        It's yours, no strings attached.

        If you want me to build the full site (mobile-first, fast, bookings-ready)
        I charge {_PRICE} flat — design, build, and launch. Includes basic SEO
        so you start ranking in your area within weeks.

        Want me to put together a full mockup so you can see exactly what it
        would look like before committing to anything?

        — {_SENDER_NAME} | {_SENDER_HANDLE}
    """).strip()
    return subject, body


def _reply_price(biz_name: str) -> tuple[str, str]:
    """Subject + body for a PRICE inquiry."""
    subject = "Re: Quick video about your mobile site"
    body = textwrap.dedent(f"""
        Good question — I like to keep it simple.

        For a full mobile-first site: {_PRICE} flat.

        That includes:
        • Custom design built for your niche
        • Mobile & speed optimised (Lighthouse 90+)
        • Booking / quote request form
        • On-page SEO + local schema so you rank in your city
        • 30 days of revisions after launch

        No monthly fees. No hidden extras. You own it completely.

        Want me to put together a free mockup for {biz_name} first?
        You'd see the full design before agreeing to anything.

        — {_SENDER_NAME} | {_SENDER_HANDLE}
    """).strip()
    return subject, body


def _reply_no(biz_name: str) -> tuple[str, str]:
    """Subject + body for a NO / unsubscribe reply."""
    subject = "Re: Quick video about your mobile site"
    body = textwrap.dedent(f"""
        No problem at all — I completely understand.

        I won't reach out again. Best of luck with everything at {biz_name}!

        If you ever do want to look at your website in the future,
        you know where to find me.

        — {_SENDER_NAME} | {_SENDER_HANDLE}
    """).strip()
    return subject, body


# ── Header code snippet attachment ────────────────────────────────────────────

_HEADER_SNIPPET = textwrap.dedent("""
    /* ── Sticky mobile CTA — paste in your <head> or CSS file ── */
    @media (max-width: 768px) {
        .mobile-cta-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #2563eb;
            color: #fff;
            text-align: center;
            padding: 14px 20px;
            font-size: 17px;
            font-weight: 700;
            letter-spacing: 0.3px;
            z-index: 9999;
            box-shadow: 0 -4px 20px rgba(0,0,0,0.2);
            text-decoration: none;
            display: block;
        }
        .mobile-cta-bar:hover { background: #1d4ed8; }
    }
    /* Drop this just before </body> in your HTML */
    /* <a href="tel:YOUR_PHONE_NUMBER" class="mobile-cta-bar">📞 Call Now — Free Estimate</a> */
""").strip()


def _build_yes_email(biz_name: str, to_email: str, from_email: str) -> MIMEMultipart:
    """Build the YES reply email with the code snippet attached."""
    subject, body = _reply_yes(biz_name)

    msg = MIMEMultipart("mixed")
    msg["Subject"]  = subject
    msg["From"]     = f"{_SENDER_NAME} <{from_email}>"
    msg["To"]       = to_email
    msg["Reply-To"] = from_email

    msg.attach(MIMEText(body, "plain"))

    # Attach the CSS snippet as a file
    snippet_bytes = _HEADER_SNIPPET.encode("utf-8")
    attachment = MIMEBase("text", "css")
    attachment.set_payload(snippet_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename="mobile_cta_fix.css",
    )
    msg.attach(attachment)

    return msg


# ── IMAP inbox reader ─────────────────────────────────────────────────────────

def _fetch_unread_emails(email_addr: str, app_password: str, limit: int = 50) -> list[dict]:
    """
    Read the last `limit` unread emails from Gmail via IMAP.
    Returns list of {from_email, subject, body, message_id}.
    """
    results = []
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(email_addr, app_password)
        mail.select("INBOX")

        # Search unseen (unread) messages
        _, search_data = mail.search(None, "UNSEEN")
        ids = search_data[0].split()

        # Take last N (most recent)
        if len(ids) > limit:
            ids = ids[-limit:]

        for uid in ids:
            _, msg_data = mail.fetch(uid, "(RFC822)")
            raw = b""
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    raw = response_part[1]
                    break
            
            if not raw:
                continue

            msg = email.message_from_bytes(raw)

            from_raw = msg.get("From", "")
            from_email = _parse_email_addr(from_raw)
            subject = _decode_header_str(msg.get("Subject", ""))
            body = _extract_body(msg)
            message_id = msg.get("Message-ID", "")

            results.append({
                "uid":        uid,
                "from_email": from_email.lower(),
                "from_raw":   from_raw,
                "subject":    subject,
                "body":       body,
                "message_id": message_id,
            })

        mail.logout()
    except Exception as exc:
        log.error(f"[replies] IMAP error: {exc}")

    return results


def _parse_email_addr(raw: str) -> str:
    """Extract bare email address from 'Name <email@domain.com>' format."""
    match = re.search(r"<([^>]+)>", raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


def _decode_header_str(raw: str) -> str:
    """Decode RFC 2047 encoded email headers."""
    try:
        parts = decode_header(raw)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return "".join(decoded)
    except Exception:
        return raw


def _extract_body(msg) -> str:
    """Extract plaintext body from a MIME email message."""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                charset = part.get_content_charset() or "utf-8"
                try:
                    return part.get_payload(decode=True).decode(charset, errors="replace")
                except Exception:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
    else:
        charset = msg.get_content_charset() or "utf-8"
        try:
            return msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            return ""
            
    return ""


# ── Intent classifier ─────────────────────────────────────────────────────────

def _classify_intent(body: str) -> tuple[str, str]:
    """
    Classify reply intent as 'yes', 'price', 'no', or 'unknown'.
    Pattern-first: no AI call needed for these clear signals.
    """
    text = (body or "").strip()

    import json
    from utils.nvidia_client import NvidiaClient
    llm = NvidiaClient()
    
    prompt = f"""You are a freelance web designer. You sent a cold email with a video audit of their mobile website.
Read the lead's reply below and determine their intent. 
If they want to book a call or are interested, draft a natural reply asking what day/time works best for a 10-minute chat (do not use Calendly).
If they ask for price, state it is a $1,500 flat fee and ask for a time to chat.
If they are not interested, draft a polite goodbye.

Lead's message:
"{text}"

Return EXACTLY a JSON object with two keys:
- "intent": one of ["yes", "price", "no", "question"]
- "reply_body": "The exact plain text email reply to send to them."
"""
    try:
        response = llm.complete(prompt, temperature=0.2)
        # basic cleanup if the model wraps in markdown
        response = response.strip().strip("```json").strip("```").strip()
        data = json.loads(response)
        return data.get("intent", "unknown"), data.get("reply_body", "")
    except Exception as e:
        log.error(f"AI Classification failed: {e}")
        return "unknown", ""


# ── Auto-send reply ───────────────────────────────────────────────────────────

def _send_reply(
    intent: str,
    ai_body: str,
    to_email: str,
    biz_name: str,
    from_email: str,
    app_password: str,
    bcc_email: str = "",
) -> bool:
    """Send the appropriate reply email. Returns True on success."""
    try:
        if intent == "yes":
            # For yes, we build a multipart to attach the CSS snippet
            msg = MIMEMultipart("mixed")
            msg["Subject"]  = f"Re: {biz_name} mobile site"
            msg["From"]     = f"{_SENDER_NAME} <{from_email}>"
            msg["To"]       = to_email
            msg["Reply-To"] = from_email

            msg.attach(MIMEText(ai_body, "plain"))

            # Attach the CSS snippet
            snippet_bytes = _HEADER_SNIPPET.encode("utf-8")
            attachment = MIMEBase("text", "css")
            attachment.set_payload(snippet_bytes)
            encoders.encode_base64(attachment)
            attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename="mobile_cta_fix.css",
            )
            msg.attach(attachment)
        elif intent in ("price", "no", "question"):
            msg = MIMEMultipart("alternative")
            msg["Subject"]  = f"Re: {biz_name} mobile site"
            msg["From"]     = f"{_SENDER_NAME} <{from_email}>"
            msg["To"]       = to_email
            msg["Reply-To"] = from_email
            msg.attach(MIMEText(ai_body, "plain"))
        else:
            return False   # unknown intent — don't auto-reply

        if bcc_email:
            msg["Bcc"] = bcc_email

        recipients = [to_email]
        if bcc_email:
            recipients.append(bcc_email)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(from_email, app_password)
            smtp.sendmail(from_email, recipients, msg.as_string())

        log.info(f"[replies] ✓ Sent {intent!r} reply to {to_email}")
        return True

    except Exception as exc:
        log.error(f"[replies] Failed to send reply to {to_email}: {exc}")
        return False


# ── Main entry point ──────────────────────────────────────────────────────────

def process_replies() -> dict:
    """
    Public entry point called by daemon.py.

    Workflow:
      1. Load state — get contacted_emails_meta for lookup
      2. Fetch last 50 unread Gmail messages via IMAP
      3. Filter to replies from known leads (sender in contacted_emails)
      4. Classify intent + auto-reply
      5. Save conversation history to state['conversations']
      6. Mark Closed-Lost leads in state['closed_lost']

    Returns stats dict: {processed, yes, price, no, unknown}
    """
    app_password = os.getenv("GMAIL_APP_PASSWORD", "")
    email_from   = os.getenv("EMAIL_FROM", "")
    email_to     = os.getenv("EMAIL_TO", email_from)   # BCC self

    if not app_password or not email_from:
        log.warning("[replies] Gmail credentials not configured — skipping reply processing")
        return {"processed": 0, "yes": 0, "price": 0, "no": 0, "unknown": 0}

    state = read_state()
    meta_list = state.get("contacted_emails_meta", [])
    contacted = {}
    for m in meta_list:
        email_key = m["email"].lower()
        if email_key not in contacted:
            contacted[email_key] = m
    closed_lost_set = set(state.get("closed_lost", []))
    conversations = state.get("conversations", {})

    if not contacted:
        log.info("[replies] No outreach sent yet — nothing to check")
        return {"processed": 0, "yes": 0, "price": 0, "no": 0, "unknown": 0}

    log.info(f"[replies] Checking inbox for replies from {len(contacted)} contacted leads…")

    # Fetch unread emails
    unread = _fetch_unread_emails(email_from, app_password, limit=50)
    log.info(f"[replies] Found {len(unread)} unread emails in inbox")

    stats = {"processed": 0, "yes": 0, "price": 0, "no": 0, "unknown": 0}
    state_dirty = False

    for email_data in unread:
        sender = email_data["from_email"]

        # Only process replies from known leads
        if sender not in contacted:
            continue

        # Skip already closed-lost (don't re-process)
        if sender in closed_lost_set:
            continue

        # Skip if we've already seen this message_id
        existing_conv = conversations.get(sender, [])
        existing_mids = {m.get("message_id") for m in existing_conv}
        if email_data["message_id"] and email_data["message_id"] in existing_mids:
            continue

        stats["processed"] += 1

        # Get business name from meta
        meta = contacted.get(sender, {})
        biz_name = meta.get("business_name") or meta.get("biz") or sender

        # Classify intent and generate AI reply
        intent, ai_body = _classify_intent(email_data["body"])
        log.info(f"[replies] {sender} intent={intent!r} (biz={biz_name!r})")

        # Save to conversation history
        ts = datetime.now(timezone.utc).isoformat()
        if sender not in conversations:
            conversations[sender] = []

        conversations[sender].append({
            "role":       "lead",
            "content":    email_data["body"][:1000],   # cap at 1000 chars per entry
            "subject":    email_data["subject"],
            "message_id": email_data["message_id"],
            "ts":         ts,
        })

        # Auto-reply
        replied = _send_reply(
            intent    = intent,
            ai_body   = ai_body,
            to_email  = sender,
            biz_name  = biz_name,
            from_email= email_from,
            app_password= app_password,
            bcc_email = email_to,
        )

        if replied:
            # Record our reply in conversation history
            conversations[sender].append({
                "role":    "agent",
                "intent":  intent,
                "ts":      datetime.now(timezone.utc).isoformat(),
            })

        # Handle Closed-Lost
        if intent == "no":
            closed_lost_set.add(sender)
            state["closed_lost"] = list(closed_lost_set)
            log.info(f"[replies] Marked Closed-Lost: {sender}")

        stats[intent if intent in stats else "unknown"] += 1
        state_dirty = True

    # Persist conversation history + closed-lost updates
    if state_dirty:
        state["conversations"] = conversations
        write_state(state)

    log.info(
        f"[replies] Done — total_processed={stats['processed']} "
        f"(yes={stats['yes']} price={stats['price']} "
        f"no={stats['no']} unknown={stats['unknown']})"
    )
    return stats
