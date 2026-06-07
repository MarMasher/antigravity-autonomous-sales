"""
video_auditor.py — Antigravity Video Audit Agent
=================================================
Records a 30s mobile-viewport screen capture of each target's website,
producing proof-of-pain video to embed in outreach emails.

Dependencies (add to requirements.txt):
  playwright>=1.45.0

First-time setup:
  pip install playwright && python -m playwright install chromium

If Playwright is unavailable, falls back to a static screenshot (PNG).
All recording is wrapped in run_safe(max_retries=2) via BaseAgent.

Output per target:
  artifacts/audit_<slug>.webm  — local video file (or .png fallback)
  Returns: {target_id, path, public_url, recorded_at, fallback}
"""

import os
import re
import time
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from agents.base_agent import BaseAgent

log = logging.getLogger("antigravity.video_auditor")

# ── Artifacts folder ──────────────────────────────────────────────────────────
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

# Max video size before we upload to Drive (bytes)
VIDEO_SIZE_LIMIT = 20 * 1024 * 1024   # 20 MB


class VideoAuditorAgent(BaseAgent):
    agent_id = "video_auditor"

    def run(self, targets: list[dict] | None = None, **kwargs) -> dict:
        """
        Record a video audit for each target in `targets`.
        Returns a dict keyed by target_id with audit result metadata.
        """
        if not targets:
            log.info("[video] No targets — skipping video audit phase")
            return {}

        results = {}
        for target in targets:
            tid  = target.get("id", _slug(target.get("business_name", "biz")))
            url  = target.get("url", "")
            name = target.get("business_name") or target.get("title") or "Business"

            if not url:
                log.warning(f"[video] No URL for {name!r} — skip")
                continue

            log.info(f"[video] Recording audit for {name!r} → {url}")

            try:
                result = self._record_audit(tid, name, url)
                results[tid] = result
                log.info(
                    f"[video] ✓ {name!r}: {result.get('path')} "
                    f"({'video' if not result.get('fallback') else 'screenshot'})"
                )
            except Exception as exc:
                log.error(f"[video] Failed to audit {name!r}: {exc}")
                results[tid] = {
                    "target_id": tid,
                    "path": None,
                    "public_url": None,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "fallback": True,
                    "error": str(exc),
                }

        return results

    # ── Core recording ────────────────────────────────────────────────────────

    def _record_audit(self, tid: str, name: str, url: str) -> dict:
        """
        Attempt Playwright video capture. Falls back to screenshot on failure.
        Returns metadata dict.
        """
        slug      = _slug(name)
        video_path = ARTIFACTS_DIR / f"audit_{slug}.webm"
        shot_path  = ARTIFACTS_DIR / f"audit_{slug}.png"
        recorded_at = datetime.now(timezone.utc).isoformat()

        try:
            from playwright.sync_api import sync_playwright
            _playwright_available = True
        except ImportError:
            _playwright_available = False
            log.warning("[video] Playwright not installed — falling back to screenshot mode")

        if _playwright_available:
            return self._playwright_record(tid, url, video_path, shot_path, recorded_at)
        else:
            return self._requests_screenshot(tid, url, shot_path, recorded_at)

    def _playwright_record(
        self, tid: str, url: str,
        video_path: Path, shot_path: Path,
        recorded_at: str,
    ) -> dict:
        """Record a 30s session at mobile viewport using Playwright."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 375, "height": 812},
                user_agent=(
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
                    "Mobile/15E148 Safari/604.1"
                ),
                record_video_dir=str(ARTIFACTS_DIR),
                record_video_size={"width": 375, "height": 812},
            )
            page = context.new_page()

            try:
                # Navigate with generous timeout
                page.goto(url, timeout=20_000, wait_until="domcontentloaded")

                # Highlight missing CTA if present
                page.evaluate("""() => {
                    const cta = document.querySelector(
                        'a[href^="tel:"], button, [class*="book"], [class*="contact"], [class*="call"]'
                    );
                    if (!cta) {
                        const banner = document.createElement('div');
                        banner.style.cssText = [
                            'position:fixed', 'top:0', 'left:0', 'right:0',
                            'background:#ef4444', 'color:#fff', 'padding:10px',
                            'font-size:14px', 'font-weight:bold', 'z-index:999999',
                            'text-align:center'
                        ].join(';');
                        banner.textContent = '⚠️ No Call-to-Action button found on this page';
                        document.body.prepend(banner);
                    }
                }""")

                # Slow scroll to show load behaviour
                for scroll_y in [200, 400, 600, 800, 600, 400, 200, 0]:
                    page.evaluate(f"window.scrollTo(0, {scroll_y})")
                    time.sleep(0.5)

                # Take a screenshot fallback regardless
                page.screenshot(path=str(shot_path), full_page=False)

            except Exception as exc:
                log.warning(f"[video] Page interaction error (continuing): {exc}")
            finally:
                context.close()
                browser.close()

            # Playwright saves video with a generated name — find and rename it
            raw_video = _find_newest_webm(ARTIFACTS_DIR)
            if raw_video and raw_video != video_path:
                raw_video.rename(video_path)

        # Determine if upload needed
        public_url = None
        if video_path.exists():
            log.info(f"[video] Uploading video to Drive (cloud-only mode)…")
            public_url = _upload_to_drive(video_path)
            
            # Delete local file to save space if upload succeeded
            if public_url:
                try:
                    video_path.unlink()
                    log.info(f"[video] Deleted local copy: {video_path.name}")
                except Exception:
                    pass
        elif shot_path.exists():
            log.info("[video] No video recorded — using screenshot fallback")
            return {
                "target_id":   tid,
                "path":        str(shot_path),
                "public_url":  None,
                "recorded_at": recorded_at,
                "fallback":    True,
            }

        return {
            "target_id":   tid,
            "path":        str(video_path) if video_path.exists() else str(shot_path),
            "public_url":  public_url,
            "recorded_at": recorded_at,
            "fallback":    not video_path.exists(),
        }

    def _requests_screenshot(
        self, tid: str, url: str, shot_path: Path, recorded_at: str
    ) -> dict:
        """
        Ultra-light fallback: use the website-screenshot.io free API
        (no key needed for low volume) to get a mobile screenshot.
        """
        import requests as req
        try:
            api_url = (
                f"https://api.screenshotone.com/take"
                f"?access_key=free&url={req.utils.quote(url, safe='')}"
                f"&device_scale_factor=2&viewport_width=375&viewport_height=812"
                f"&format=png&timeout=30"
            )
            resp = req.get(api_url, timeout=35)
            if resp.status_code == 200 and resp.content:
                shot_path.write_bytes(resp.content)
                log.info(f"[video] Screenshot saved: {shot_path.name}")
            else:
                log.warning(f"[video] Screenshot API returned {resp.status_code}")
        except Exception as exc:
            log.error(f"[video] Screenshot fallback failed: {exc}")

        return {
            "target_id":   tid,
            "path":        str(shot_path) if shot_path.exists() else None,
            "public_url":  None,
            "recorded_at": recorded_at,
            "fallback":    True,
        }


# ── Google Drive upload ───────────────────────────────────────────────────────

def _upload_to_drive(file_path: Path) -> str | None:
    """
    Upload a file to Google Drive and return a public sharing link.
    Requires GOOGLE_DRIVE_CREDENTIALS_JSON in .env (path to service account JSON).
    Falls back gracefully — returns None if Drive isn't configured.
    """
    creds_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_JSON", "")
    if not creds_path or not Path(creds_path).exists():
        log.warning("[video] GOOGLE_DRIVE_CREDENTIALS_JSON not set — skipping Drive upload")
        return None

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/drive.file"],
        )
        service = build("drive", "v3", credentials=creds)

        file_metadata = {"name": file_path.name}
        media = MediaFileUpload(str(file_path), mimetype="video/webm", resumable=True)
        upload = service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()
        file_id = upload.get("id")

        # Make it publicly readable
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

        # Share directly with the user's email so it shows in their Google Drive
        user_email = os.getenv("EMAIL_FROM")
        if user_email:
            try:
                service.permissions().create(
                    fileId=file_id,
                    body={"type": "user", "role": "writer", "emailAddress": user_email},
                ).execute()
            except Exception as e:
                log.warning(f"[video] Could not explicitly share with {user_email}: {e}")

        public_url = f"https://drive.google.com/file/d/{file_id}/view"
        log.info(f"[video] Uploaded to Drive: {public_url}")
        return public_url

    except ImportError:
        log.warning("[video] google-api-python-client not installed — skip Drive upload")
        return None
    except Exception as exc:
        log.error(f"[video] Drive upload failed: {exc}")
        return None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(text: str) -> str:
    """Convert a business name to a safe filename slug."""
    s = re.sub(r"[^a-z0-9]+", "_", text.lower().strip())
    return s[:40].strip("_") or hashlib.md5(text.encode()).hexdigest()[:8]


def _find_newest_webm(directory: Path) -> Path | None:
    """Find the most recently modified .webm file in a directory."""
    webms = list(directory.glob("*.webm"))
    if not webms:
        return None
    return max(webms, key=lambda p: p.stat().st_mtime)
