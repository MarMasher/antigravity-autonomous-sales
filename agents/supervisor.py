"""
supervisor.py — Antigravity Supervisor Agent
==============================================
Validates the quality of emails generated and the presence of videos before outreach.
Re-triggers generation or recording if missing/failed.
"""

import logging
from agents.base_agent import BaseAgent
from agents.video_auditor import VideoAuditorAgent

log = logging.getLogger("antigravity.supervisor")


class SupervisorAgent(BaseAgent):
    agent_id = "supervisor"

    def run(self, targets: list[dict], video_results: dict, **kwargs) -> dict:
        """
        Supervise the targets before email outreach.
        1. Ensure videos are recorded. Re-record if missing.
        2. Ensure email fields (icebreaker, linkedin_msg) are present and quality.
        Returns the updated targets and video_results.
        """
        updated_targets = []
        
        for t in targets:
            tid = t.get("id")
            biz = t.get("business_name") or t.get("title") or "Business"
            lead_niche = t.get("niche", "business")
            loc = t.get("location", "your area")
            
            log.info(f"[supervisor] Auditing payload for {biz}...")
            
            # 1. Supervise Video
            audit_meta = video_results.get(tid, {})
            # Check if video was successfully recorded/uploaded
            has_video = (audit_meta.get("path") or audit_meta.get("public_url")) and not audit_meta.get("error")
            
            if not has_video:
                log.warning(f"[supervisor] Video missing or errored for {biz}. Re-recording...")
                video_agent = VideoAuditorAgent()
                try:
                    retry_res = video_agent.run_safe(max_retries=1, targets=[t])
                    if retry_res and tid in retry_res:
                        video_results[tid] = retry_res[tid]
                        log.info(f"[supervisor] Re-record complete for {biz}.")
                except Exception as e:
                    log.error(f"[supervisor] Video re-record failed for {biz}: {e}")
            else:
                log.info(f"[supervisor] Video valid for {biz}.")

            # 2. Supervise Email Content
            icebreaker = t.get("icebreaker", "")
            linkedin_msg = t.get("linkedin_msg", "")
            
            # Check for common LLM failure modes, repetitions, single-character spam, and Chinese punctuation
            import re
            def is_bad_content(text):
                if not text:
                    return True
                if len(text) < 15 or len(text) > 200: # length constraint prevents repetitive glitches
                    return True
                
                text_lower = text.lower()
                bad_patterns = ["language model", "ai ", "as an ai", "i cannot", "here is", "compliment", "icebreaker", "complimenting"]
                for bp in bad_patterns:
                    if bp in text_lower:
                        return True
                        
                # Repetition check (words)
                words = [w.strip(".,!?()\"' ") for w in text_lower.split() if w.strip()]
                if not words:
                    return True
                for word in set(words):
                    if len(word) > 1 and words.count(word) > 3:  # a word repeated > 3 times
                        return True
                        
                # Gibberish check (many single characters)
                single_chars = [w for w in words if len(w) == 1]
                if len(words) > 5 and len(single_chars) / len(words) > 0.3:
                    return True
                    
                # Non-standard characters/spam symbols
                weird_symbols = ["。", "★", "☆", "■", "●", "▲", "▼"]
                for sym in weird_symbols:
                    if sym in text:
                        return True
                        
                # Repeated symbol characters
                for char in set(text):
                    if char in "。._-* " and text.count(char) > 4:
                        if char != " " and char != ".": # spaces and single periods are fine, but many symbols are not
                            return True
                return False

            if is_bad_content(icebreaker):
                log.warning(f"[supervisor] Fixing bad icebreaker for {biz}")
                t["icebreaker"] = f"I was researching {lead_niche} businesses in {loc} and {biz} stood out to me."
                
            if is_bad_content(linkedin_msg) or len(linkedin_msg) > 300:
                log.warning(f"[supervisor] Fixing bad linkedin_msg for {biz}")
                t["linkedin_msg"] = f"Hi, I recently reviewed {biz}'s website and made a quick 45s video on how to improve its mobile conversions. Let me know if you'd like to see it."
                
            updated_targets.append(t)
            
        return {"targets": updated_targets, "video_results": video_results}
