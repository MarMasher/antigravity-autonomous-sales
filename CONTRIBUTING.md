# Contributing to Antigravity

Thank you for your interest in contributing! This document covers how to get started.

## Development Setup

```bash
git clone https://github.com/MarMasher/antigravity-autonomous-sales.git
cd antigravity-autonomous-sales

python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
cp .env.example .env
# Fill in your credentials
```

## Code Style

- Follow PEP 8 with 100-character line limit
- Type hints are required for all public functions
- Docstrings for all modules and classes
- Comments explain *why*, not *what*

## Adding an Agent

1. Create `agents/my_agent.py` inheriting from `BaseAgent`
2. Implement the `run(**kwargs) -> any` method
3. Use `self.state()` / `self.save()` for shared state
4. Use `self.log(action, data)` for all significant actions
5. Use `self.halt(reason)` for unrecoverable blockers
6. Wire it into `daemon.py` in the appropriate pipeline stage

## Secrets Policy

**Zero secrets in code.** All credentials must come from `.env` via `os.getenv()`.

- Never hardcode API keys, tokens, passwords, or personal identifiers
- Never use real email addresses, usernames, or handles as default fallbacks
- Never add `.env` or `shared_state.json` to commits

## Pull Request Process

1. Fork → branch → commit → push → open PR against `main`
2. Describe what you changed and why
3. Ensure no secrets are included (the PR bot will reject if found)
4. One approval required from a maintainer

## Reporting Issues

Open a GitHub Issue with:
- Steps to reproduce
- Expected vs actual behavior
- Python version and OS
- Sanitized error output (no credentials)

## License

By contributing you agree that your contributions will be licensed under the MIT License.
