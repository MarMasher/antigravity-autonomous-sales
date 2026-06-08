"""
supervisor.py — Antigravity Supervisor Agent
==============================================
Validates the quality of emails generated and the presence of videos before outreach.
Re-triggers generation or recording if missing/failed.
"""

import logging
from agents.base_agent import BaseAgent
from agents.video_auditor import VideoAuditorAgent
from utils.llm_client import LLMClient

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
        try:
            llm = LLMClient()
        except Exception as e:
            log.error(f"[supervisor] Failed to initialize LLMClient: {e}")
            llm = None
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
                if not text or len(text) < 10:
                    return True
                for bp in bad_patterns:
                    if bp.lower() in text.lower():
                        return True
                return False

            if is_bad(icebreaker):
                log.warning(f"[supervisor] Fixing bad icebreaker for {biz}")
                prompt = f"Write a single, highly realistic and short 1-sentence personalized cold email opener for a {lead_niche} in {loc} named {biz}. Do not use quotes or placeholder text. Just the sentence."
                if llm:
                    try:
                        t["icebreaker"] = llm.complete(prompt, temperature=0.7).strip(' "')
                    except Exception as e:
                        log.error(f"[supervisor] LLM complete failed for icebreaker: {e}")
                        t["icebreaker"] = f"I was researching {lead_niche} businesses in {loc} and {biz} stood out to me."
                else:
                    t["icebreaker"] = f"I was researching {lead_niche} businesses in {loc} and {biz} stood out to me."
                
            if is_bad(linkedin_msg):
                log.warning(f"[supervisor] Fixing bad linkedin_msg for {biz}")
                prompt = f"Write a 2-sentence LinkedIn connection request (under 300 chars) for the owner of {biz}. Mention you made a 45s video on their mobile site. No quotes, no placeholders."
                if llm:
                    try:
                        t["linkedin_msg"] = llm.complete(prompt, temperature=0.7).strip(' "')
                    except Exception as e:
                        log.error(f"[supervisor] LLM complete failed for linkedin_msg: {e}")
                        t["linkedin_msg"] = f"Hi, I recently reviewed {biz}'s website and made a quick 45s video on how to improve its mobile conversions. Let me know if you'd like to see it."
                else:
                    t["linkedin_msg"] = f"Hi, I recently reviewed {biz}'s website and made a quick 45s video on how to improve its mobile conversions. Let me know if you'd like to see it."
                
            # Secondary check
            if llm:
                check_prompt = f"Does this text look like a robotic AI apology or contains placeholders? Text: '{t['icebreaker']}'. Reply YES if it's robotic/bad, NO if it's a good opener."
                try:
                    if "YES" in llm.complete(check_prompt, temperature=0.1).upper():
                        log.warning(f"[supervisor] Icebreaker failed secondary quality check. Forcing safe fallback.")
                        t["icebreaker"] = f"I was researching {lead_niche} businesses in {loc} and {biz} stood out to me."
                except Exception as e:
                    log.error(f"[supervisor] LLM complete failed for secondary check: {e}")
                
            updated_targets.append(t)
            
        return {"targets": updated_targets, "video_results": video_results}
