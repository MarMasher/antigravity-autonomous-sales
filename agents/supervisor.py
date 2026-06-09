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
            
            # Check for common LLM failure modes (apologies, empty, exact template leakage)
            bad_patterns = ["language model", "AI", "I cannot", "As an", "Here is"]
            
            def is_bad(text):
                # Added length constraints to prevent repetitive glitches
                if not text or len(text) < 10 or len(text) > 150:
                    return True
                for bp in bad_patterns:
                    if bp.lower() in text.lower():
                        return True
                return False

            if is_bad(icebreaker):
                log.warning(f"[supervisor] Fixing bad icebreaker for {biz}")
                t["icebreaker"] = f"I was researching {lead_niche} businesses in {loc} and {biz} stood out to me."
                
            if is_bad(linkedin_msg) or len(linkedin_msg) > 300:
                log.warning(f"[supervisor] Fixing bad linkedin_msg for {biz}")
                t["linkedin_msg"] = f"Hi, I recently reviewed {biz}'s website and made a quick 45s video on how to improve its mobile conversions. Let me know if you'd like to see it."
                
            updated_targets.append(t)
            
        return {"targets": updated_targets, "video_results": video_results}
