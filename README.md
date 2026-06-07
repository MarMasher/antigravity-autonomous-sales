# Antigravity — Autonomous Sales Machine

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/MarMasher/antigravity-autonomous-sales?style=for-the-badge&color=f59e0b)](https://github.com/MarMasher/antigravity-autonomous-sales/stargazers)

**A fully autonomous, self-healing AI pipeline that finds small business leads, audits their websites, and sends personalized cold outreach — while you sleep.**

[Quick Start](#quick-start) · [Architecture](#architecture) · [Configuration](#configuration) · [Agents](#agents) · [Contributing](#contributing)

</div>

---

## What It Does

Antigravity runs a 5-agent pipeline, every 24 hours, on autopilot:

| Step | Agent | What happens |
|------|-------|-------------|
| 1 | **Researcher** | Sweeps 70+ niches × 150+ cities. Scrapes contacts, audits websites, scores leads by buyer quality × website pain. |
| 2 | **Builder** | Generates a live demo site (Puter.js, deployed to Vercel/GitHub Pages) personalized to the lead's business. |
| 3 | **Outreach** | Writes a human-sounding cold DM + full objection-handling tree, ready to copy-paste. |
| 4 | **Reply Processor** | Reads your Gmail inbox, classifies replies (YES / PRICE / NO), and auto-responds to close the conversation. |
| 5 | **Negotiator** | Given the owner's reply, generates the optimal negotiation response with reasoning and next steps. |

**Self-healing:** If any agent crashes, AutoHealer identifies the failing file, sends it to an AI model for a fix, patches the file, reloads the module, and retries — all without human intervention.

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/MarMasher/antigravity-autonomous-sales.git
cd antigravity-autonomous-sales

python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure secrets

```bash
cp .env.example .env
```

Open `.env` and fill in your credentials. See [Configuration](#configuration) for details.

### 3. Run

```bash
# Single pipeline run (research 10 leads + outreach)
python run.py

# Run the full daemon (repeats every 24 hours)
python daemon.py

# Or double-click START_DAEMON.bat on Windows
```

### 4. Watch the dashboard

```bash
python orchestrator.py status
```

---

## Architecture

```
daemon.py  ←  orchestrates all agents in sequence, every 24h
    │
    ├── agents/researcher.py       (Lead discovery + scoring)
    ├── agents/builder.py          (Live demo site generation)
    ├── agents/outreach.py         (Cold DM generation)
    ├── agents/video_auditor.py    (Screen-capture audit emails)
    ├── agents/negotiator.py       (Reply → negotiation response)
    │
    ├── utils/email_sender.py      (Gmail SMTP outreach)
    ├── utils/reply_processor.py   (Gmail IMAP + auto-reply)
    ├── utils/auto_healer.py       (Self-healing via AI patch loop)
    ├── utils/nvidia_client.py     (NVIDIA NIM AI client)
    ├── utils/github_client.py     (GitHub API for demo repos)
    └── utils/state_manager.py     (Persistent JSON state)
```

**State machine:** All agents share `shared_state.json` (git-ignored). This file tracks targets, outreach history, conversations, and closed-lost leads across cycles.

---

## Configuration

Copy `.env.example` to `.env` and configure:

### Required

| Variable | Description |
|----------|-------------|
| `NVIDIA_GLM_KEY` | NVIDIA NIM API key for GLM 5.1 (primary AI) |
| `NVIDIA_KIMI_KEY` | NVIDIA NIM API key for Kimi K2 (fallback) |
| `NVIDIA_DEEPSEEK_KEY` | NVIDIA NIM API key for DeepSeek V4 (fallback) |
| `EMAIL_FROM` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail App Password ([how to get one](https://support.google.com/accounts/answer/185833)) |
| `EMAIL_TO` | Your email for receiving lead dossiers |
| `GITHUB_TOKEN` | GitHub Personal Access Token (for repo creation) |
| `GITHUB_USERNAME` | Your GitHub username |

### Identity (shown in outreach emails)

| Variable | Description |
|----------|-------------|
| `SENDER_NAME` | Your name (used in email signatures) |
| `SENDER_HANDLE` | Your social handle (e.g. `@yourhandle`) |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `SEND_OUTREACH_EMAILS` | `false` | Set `true` to enable autonomous cold emails |
| `OUTREACH_MAX_PER_CYCLE` | `50` | Max cold emails per cycle |
| `OUTREACH_SCORE_THRESHOLD` | `10` | Min score to receive outreach |
| `OUTREACH_PRICE` | `$1,500` | Price quoted in outreach templates |
| `APIFY_TOKEN` | — | For Apify-powered lead scraping |
| `VERCEL_TOKEN` | — | For Vercel deployment of demo sites |

---

## Agents

### Researcher
Sweeps `70+ niches × 150+ cities` using DuckDuckGo. Scores leads on a **two-axis system**:
- **Buyer Quality (0–40):** Social presence, phone, email, reviews, credibility signals
- **Website Pain (0–30):** Low score, no mobile, no SSL, slow load, no meta

Only businesses with HIGH quality AND HIGH pain are selected — the best ROI for cold outreach.

### Builder
For each top lead, generates a complete 4-page Puter.js website (Home, Services, About, Contact) with the business's real name, niche, and location. Deploys to GitHub Pages and creates a Vercel live URL.

### Reply Processor
IMAP-reads your Gmail inbox every cycle. Classifies unread replies from known leads using regex + AI. Auto-replies with:
- **YES** → CSS snippet attachment + full-site upsell
- **PRICE** → Flat fee quote + mockup offer
- **NO** → Polite farewell, marks Closed-Lost in state

### Negotiator
Interactive CLI agent. Paste in an owner's reply, get: recommended response (copy-paste ready), reasoning, signals to watch for, and next steps.

```bash
python orchestrator.py negotiate
```

### AutoHealer
Wraps every agent call. On crash:
1. Identifies the failing source file from the traceback
2. Reads the file and sends it to GLM 5.1 → Kimi → DeepSeek with the error
3. AI returns the complete fixed file
4. Validates it compiles (AST parse)
5. Backs up original, patches, reloads the module
6. Retries — up to 3 times

---

## CLI Reference

```bash
# Run the full pipeline (research + outreach)
python run.py

# Specify number of targets
python run.py --targets 5

# Skip research, use existing state targets
python run.py --skip-research

# Run continuously (every 24h)
python run.py --loop

# Orchestrator CLI commands
python orchestrator.py status        # Live pipeline status
python orchestrator.py negotiate     # Negotiator interactive mode
python orchestrator.py reset         # Reset state

# Windows Task Scheduler setup (runs at 8AM daily)
powershell -File schedule_task.ps1
```

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for code style and testing guidelines.

---

## License

MIT © 2026 — see [LICENSE](LICENSE) for details.

> **Disclaimer:** Use responsibly. Ensure your cold outreach complies with CAN-SPAM, GDPR, and applicable local laws. The authors are not responsible for misuse.
