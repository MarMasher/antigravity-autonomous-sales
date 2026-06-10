import json
import streamlit as st
from pathlib import Path

st.set_page_config(page_title="Antigravity Sales Machine", page_icon="🚀", layout="wide")

STATE_FILE = Path("shared_state.json")

def load_state():
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

state = load_state()

st.title("🚀 Autonomous Sales Pipeline")

# Get data
meta_list = state.get("contacted_emails_meta", [])
conversations = state.get("conversations", {})
closed_lost = set(state.get("closed_lost", []))
videos = state.get("video_audits", {})

# Categorize leads
pipeline = {
    "Contacted": [],
    "Replied": [],
    "Closed/Lost": []
}

for m in meta_list:
    email = m.get("email", "").lower()
    biz = m.get("business_name") or m.get("biz") or "Unknown"
    
    # Enrich with video URL
    tid = m.get("id")
    video_url = videos.get(tid, {}).get("public_url", "")
    m["video_url"] = video_url
    
    if email in closed_lost:
        pipeline["Closed/Lost"].append(m)
    elif email in conversations:
        pipeline["Replied"].append(m)
    else:
        pipeline["Contacted"].append(m)

# Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Total Prospects Reached", len(meta_list))
col2.metric("Active Conversations", len(pipeline["Replied"]))
col3.metric("Closed/Lost", len(pipeline["Closed/Lost"]))

st.divider()

# Kanban view
st.subheader("Kanban Pipeline")
k1, k2, k3 = st.columns(3)

with k1:
    st.markdown("### 📤 Outbound Sent")
    for lead in reversed(pipeline["Contacted"]):
        with st.container(border=True):
            st.markdown(f"**{lead.get('business_name', 'Unknown')}**")
            st.caption(f"📧 {lead.get('email')}")
            if lead.get('video_url'):
                st.markdown(f"[🎥 View Video Audit]({lead['video_url']})")
            if lead.get('linkedin_msg'):
                with st.expander("LinkedIn Message"):
                    st.code(lead['linkedin_msg'], language="text")

with k2:
    st.markdown("### 💬 Replied (AI Handling)")
    for lead in reversed(pipeline["Replied"]):
        with st.container(border=True):
            st.markdown(f"**{lead.get('business_name', 'Unknown')}**")
            st.caption(f"📧 {lead.get('email')}")
            email_key = lead.get("email", "").lower()
            conv = conversations.get(email_key, [])
            with st.expander(f"Thread ({len(conv)} msgs)"):
                for msg in conv:
                    role = msg.get("role", "unknown")
                    prefix = "🤖" if role == "agent" else "👤"
                    if role == "agent":
                        st.markdown(f"**{prefix} AI Agent:** *Replied via Email (Intent: {msg.get('intent')})*")
                    else:
                        st.markdown(f"**{prefix} Lead:** {msg.get('content', '')}")

with k3:
    st.markdown("### 🛑 Closed / Lost")
    for lead in reversed(pipeline["Closed/Lost"]):
        with st.container(border=True):
            st.markdown(f"~~**{lead.get('business_name', 'Unknown')}**~~")
            st.caption(f"📧 {lead.get('email')}")

st.divider()
st.caption("Refresh the page to sync with latest state.json updates.")
