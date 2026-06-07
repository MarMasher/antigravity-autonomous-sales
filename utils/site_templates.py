"""
Puter.js powered multi-page site templates.
AI chat widget auto-selects best model: Opus 4.5 → GPT-4o → Gemini → etc.
"""

SHARED_CSS = '''<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#0a0a0f;--bg2:#12121a;--bg3:#1a1a26;--bd:#2a2a3a;--tx:#f0f0ff;--tx2:#8888aa;--ac:#7c6cf8;--ac2:#6356e8;--ac3:rgba(124,108,248,.15);--glass:rgba(18,18,26,.85)}
body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--tx);-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:none}
button{border:none;cursor:pointer;font:inherit}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-thumb{background:var(--bd);border-radius:3px}

/* NAV */
nav{position:fixed;top:0;left:0;right:0;z-index:100;padding:0 24px;height:64px;display:flex;align-items:center;justify-content:space-between;background:var(--glass);backdrop-filter:blur(20px);border-bottom:1px solid var(--bd)}
.nav-brand{font-size:18px;font-weight:800;background:linear-gradient(135deg,var(--ac),#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.nav-links{display:flex;align-items:center;gap:32px}
.nav-links a{font-size:14px;font-weight:500;color:var(--tx2);transition:color .2s}.nav-links a:hover{color:var(--tx)}
.nav-cta{padding:8px 20px;background:var(--ac);color:#fff!important;border-radius:10px;font-weight:600!important;transition:background .2s!important}.nav-cta:hover{background:var(--ac2)!important}

/* HERO */
.hero{min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;padding:80px 24px 40px;position:relative;overflow:hidden}
.hero::before{content:'';position:absolute;inset:0;background:radial-gradient(ellipse 80% 50% at 50% -10%,rgba(124,108,248,.25),transparent)}
.hero-content{max-width:820px;position:relative;z-index:1}
.hero-badge{display:inline-flex;align-items:center;gap:8px;padding:6px 16px;border:1px solid var(--bd);border-radius:999px;font-size:12px;font-weight:600;color:var(--tx2);letter-spacing:.5px;text-transform:uppercase;margin-bottom:28px;background:var(--bg2)}
h1{font-size:clamp(2.5rem,6vw,5rem);font-weight:800;line-height:1.1;letter-spacing:-1px;margin-bottom:24px}
.gradient-text{background:linear-gradient(135deg,#fff 0%,var(--ac) 60%,#a78bfa 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{font-size:1.2rem;color:var(--tx2);line-height:1.7;max-width:600px;margin:0 auto 40px}
.hero-btns{display:flex;gap:16px;justify-content:center;flex-wrap:wrap}
.btn-primary{padding:14px 32px;background:var(--ac);color:#fff;border-radius:12px;font-weight:700;font-size:16px;transition:all .2s;box-shadow:0 0 40px rgba(124,108,248,.3)}.btn-primary:hover{background:var(--ac2);transform:translateY(-2px)}
.btn-ghost{padding:14px 32px;border:1px solid var(--bd);color:var(--tx);border-radius:12px;font-weight:600;font-size:16px;transition:all .2s}.btn-ghost:hover{border-color:var(--ac);background:var(--ac3)}

/* SECTIONS */
section{padding:96px 24px}
.container{max-width:1100px;margin:0 auto}
.section-label{font-size:12px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--ac);margin-bottom:16px}
h2{font-size:clamp(2rem,4vw,3rem);font-weight:800;letter-spacing:-0.5px;margin-bottom:16px}
.section-sub{font-size:1.1rem;color:var(--tx2);line-height:1.7;max-width:600px}

/* CARDS */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;margin-top:60px}
.card{padding:32px;background:var(--bg2);border:1px solid var(--bd);border-radius:20px;transition:all .3s}
.card:hover{border-color:var(--ac);transform:translateY(-4px);box-shadow:0 20px 60px rgba(124,108,248,.1)}
.card-icon{width:48px;height:48px;background:var(--ac3);border:1px solid rgba(124,108,248,.3);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:22px;margin-bottom:20px}
.card h3{font-size:18px;font-weight:700;margin-bottom:10px}
.card p{font-size:14px;color:var(--tx2);line-height:1.7}

/* STATS */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:24px;margin-top:60px;text-align:center}
.stat-n{font-size:3rem;font-weight:800;background:linear-gradient(135deg,var(--ac),#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-l{font-size:14px;color:var(--tx2);margin-top:4px}

/* PRICING */
.pricing{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:24px;margin-top:60px;align-items:start}
.plan{padding:36px;background:var(--bg2);border:1px solid var(--bd);border-radius:20px;transition:all .3s}
.plan.featured{border-color:var(--ac);background:linear-gradient(135deg,var(--bg2),rgba(124,108,248,.08));box-shadow:0 0 60px rgba(124,108,248,.15)}
.plan-badge{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--ac);margin-bottom:12px}
.plan-price{font-size:3rem;font-weight:800;margin:8px 0 4px}
.plan-period{font-size:14px;color:var(--tx2)}
.plan-features{list-style:none;margin:24px 0;display:flex;flex-direction:column;gap:12px}
.plan-features li{font-size:14px;color:var(--tx2);display:flex;align-items:center;gap:10px}
.plan-features li::before{content:'✓';color:#10b981;font-weight:700;flex-shrink:0}
.btn-plan{width:100%;padding:14px;border-radius:12px;font-weight:700;font-size:15px;transition:all .2s;margin-top:8px}
.btn-plan-primary{background:var(--ac);color:#fff}.btn-plan-primary:hover{background:var(--ac2)}
.btn-plan-ghost{border:1px solid var(--bd);color:var(--tx)}.btn-plan-ghost:hover{border-color:var(--ac)}

/* FORM */
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media(max-width:600px){.form-grid{grid-template-columns:1fr}}
.field{display:flex;flex-direction:column;gap:8px}
.field.full{grid-column:1/-1}
label{font-size:13px;font-weight:600;color:var(--tx2)}
input,textarea,select{padding:12px 16px;background:var(--bg2);border:1px solid var(--bd);border-radius:12px;color:var(--tx);font-size:14px;font-family:inherit;transition:border .2s;resize:vertical}
input:focus,textarea:focus{outline:none;border-color:var(--ac)}
textarea{min-height:120px}

/* AI CHAT WIDGET */
#ai-chat-btn{position:fixed;bottom:28px;right:28px;width:60px;height:60px;border-radius:50%;background:var(--ac);color:#fff;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;box-shadow:0 8px 32px rgba(124,108,248,.4);transition:all .3s;z-index:1000;font-size:24px}
#ai-chat-btn:hover{transform:scale(1.1);background:var(--ac2)}
#ai-chat-panel{position:fixed;bottom:104px;right:28px;width:380px;max-height:520px;background:var(--bg2);border:1px solid var(--bd);border-radius:20px;display:none;flex-direction:column;box-shadow:0 24px 80px rgba(0,0,0,.5);z-index:999;overflow:hidden}
#ai-chat-panel.open{display:flex}
.chat-head{padding:16px 20px;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:12px}
.chat-head-av{width:36px;height:36px;background:var(--ac3);border:1px solid var(--ac);border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:18px}
.chat-head-info h4{font-size:14px;font-weight:700}
.chat-head-info p{font-size:11px;color:var(--tx2)}
.chat-msgs{flex:1;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.chat-msg{padding:10px 14px;border-radius:12px;font-size:13px;line-height:1.6;max-width:85%}
.chat-msg.user{background:var(--ac);color:#fff;align-self:flex-end;border-bottom-right-radius:4px}
.chat-msg.bot{background:var(--bg3);border:1px solid var(--bd);align-self:flex-start;border-bottom-left-radius:4px}
.chat-input-row{padding:12px;border-top:1px solid var(--bd);display:flex;gap:8px}
.chat-input-row input{flex:1;padding:10px 14px;background:var(--bg3);border:1px solid var(--bd);border-radius:10px;color:var(--tx);font-size:13px}
.chat-input-row input:focus{outline:none;border-color:var(--ac)}
.chat-send{padding:10px 16px;background:var(--ac);color:#fff;border-radius:10px;font-size:13px;font-weight:600;transition:background .2s}.chat-send:hover{background:var(--ac2)}

/* FOOTER */
footer{padding:48px 24px;border-top:1px solid var(--bd);text-align:center;color:var(--tx2);font-size:13px}
.footer-brand{font-size:20px;font-weight:800;margin-bottom:12px;background:linear-gradient(135deg,var(--ac),#a78bfa);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
</style>'''

PUTER_AI_WIDGET = '''<script src="https://js.puter.com/v2/"></script>
<script>
// ── Puter.js AI Chat Widget ──────────────────────────────────────
// Auto-selects BEST available model: Opus 4.5 → GPT-4o → Gemini etc.
const PRIORITY_MODELS = [
  'claude-opus-4-5','claude-opus-4','claude-3-7-sonnet-20250219',
  'claude-3-5-sonnet','gpt-4o','o3-mini','o3',
  'gemini-2.0-flash-exp','gemini-2.0-flash','gemini-1.5-pro',
  'meta-llama-3.1-70b-instruct','mistral-large-latest'
];

let bestModel = 'claude-3-5-sonnet';
let chatHistory = [];
const BIZ_NAME = document.querySelector('meta[name="biz-name"]')?.content || document.title;
const BIZ_NICHE = document.querySelector('meta[name="biz-niche"]')?.content || 'service';
const BIZ_LOC   = document.querySelector('meta[name="biz-loc"]')?.content   || 'your area';

async function findBestModel() {
  try {
    const result = await puter.ai.listModels();
    const available = (result.models || result || []).map(m => (m.id || m.model || m+'').toLowerCase());
    for (const m of PRIORITY_MODELS) {
      if (available.some(a => a.includes(m.split('-')[0]) && a.includes(m.split('-').pop()))) {
        bestModel = m; break;
      }
    }
  } catch(e) { /* use default */ }
  console.log('[AI Widget] Using model:', bestModel);
}
findBestModel();

const SYSTEM_PROMPT = `You are a helpful AI assistant for ${BIZ_NAME}, a ${BIZ_NICHE} business in ${BIZ_LOC}. 
Answer customer questions warmly and professionally. Help with bookings, pricing, and services.
Keep answers short (2-3 sentences). Be friendly and encourage them to contact us.`;

const chatBtn   = document.getElementById('ai-chat-btn');
const chatPanel = document.getElementById('ai-chat-panel');
const chatInput = document.getElementById('chat-input');
const chatMsgs  = document.getElementById('chat-msgs');

chatBtn.addEventListener('click', () => {
  chatPanel.classList.toggle('open');
  if (chatPanel.classList.contains('open') && chatHistory.length === 0) {
    addMsg('bot', `Hi! I'm the AI assistant for ${BIZ_NAME}. How can I help you today?`);
  }
});

function addMsg(role, text) {
  const div = document.createElement('div');
  div.className = `chat-msg ${role}`;
  div.textContent = text;
  chatMsgs.appendChild(div);
  chatMsgs.scrollTop = chatMsgs.scrollHeight;
  return div;
}

async function sendChat() {
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = '';
  addMsg('user', text);
  chatHistory.push({ role: 'user', content: text });
  const thinkingEl = addMsg('bot', '...');
  try {
    const messages = [
      { role: 'system', content: SYSTEM_PROMPT },
      ...chatHistory.slice(-6)
    ];
    const resp = await puter.ai.chat(messages, { model: bestModel });
    const reply = typeof resp === 'string' ? resp : (resp?.message?.content || resp?.text || 'Sorry, I had trouble responding.');
    thinkingEl.textContent = reply;
    chatHistory.push({ role: 'assistant', content: reply });
  } catch(e) {
    thinkingEl.textContent = 'Sorry, I\'m having trouble right now. Please contact us directly!';
  }
}

document.getElementById('chat-send').addEventListener('click', sendChat);
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });
</script>'''


def render_nav(biz: str, pages: list) -> str:
    links = ''.join(f'<a href="{p[1]}">{p[0]}</a>' for p in pages[:-1])
    last = pages[-1]
    return f'''<nav>
  <div class="nav-brand">{biz[:22]}</div>
  <div class="nav-links">{links}<a href="{last[1]}" class="nav-cta">{last[0]}</a></div>
</nav>'''


def render_footer(biz: str, loc: str) -> str:
    return f'''<footer>
  <div class="footer-brand">{biz}</div>
  <p>Proudly serving {loc} and surrounding areas.</p>
  <p style="margin-top:8px">© 2025 {biz}. All rights reserved.</p>
</footer>'''


def render_chat_widget(biz: str, niche: str, loc: str) -> str:
    return f'''<meta name="biz-name" content="{biz}">
<meta name="biz-niche" content="{niche}">
<meta name="biz-loc" content="{loc}">
<button id="ai-chat-btn" title="Chat with AI Assistant">💬</button>
<div id="ai-chat-panel">
  <div class="chat-head">
    <div class="chat-head-av">🤖</div>
    <div class="chat-head-info"><h4>AI Assistant</h4><p>Powered by Puter.js</p></div>
  </div>
  <div class="chat-msgs" id="chat-msgs"></div>
  <div class="chat-input-row">
    <input id="chat-input" placeholder="Ask anything…">
    <button class="chat-send" id="chat-send">Send</button>
  </div>
</div>
{PUTER_AI_WIDGET}'''


def page_shell(title: str, desc: str, biz: str, niche: str, loc: str, nav: str, body: str, extra_head: str = '') -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
{SHARED_CSS}
{extra_head}
</head>
<body>
{nav}
{body}
{render_footer(biz, loc)}
{render_chat_widget(biz, niche, loc)}
</body>
</html>'''
