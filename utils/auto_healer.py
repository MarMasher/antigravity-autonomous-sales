"""
AutoHealer — Self-healing engine for all Antigravity agents.

When an agent crashes:
  1. Captures the full traceback
  2. Identifies exactly which file + line failed
  3. Reads the failing source file
  4. Sends error + code to the AI with a fix request
  5. Writes the patched file back to disk
  6. Reloads the module
  7. Retries the original call (up to MAX_RETRIES times)

Uses GLM 5.1 as primary healer (strongest reasoning), falls back to Kimi → DeepSeek.
"""

import os
import sys
import time
import importlib
import traceback
import re
from pathlib import Path
from typing import Callable, Any

# Healer uses its own AI client to avoid circular dependency issues
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BASE_URL       = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
MAX_RETRIES    = 3
HEAL_TIMEOUT   = 60   # seconds per AI heal call

# Use GLM (best reasoning) → Kimi → DeepSeek for healing
HEALER_MODELS = [
    {
        "name": "primary",
        "id":   os.getenv("LLM_MODEL_PRIMARY", "gpt-4o-mini"),
        "key":  os.getenv("LLM_API_KEY"),
        "kind": "openai",
    },
    {
        "name": "fallback",
        "id":   os.getenv("LLM_MODEL_FALLBACK", "gpt-4o"),
        "key":  os.getenv("LLM_API_KEY"),
        "kind": "openai",
    }
]

HEAL_SYSTEM = """You are an expert Python auto-healing system.
You are given a Python file that crashed with a specific error.
Your job: return the COMPLETE fixed Python file with the bug corrected.

Rules:
- Return ONLY the full Python file content, no explanations, no markdown fences
- Fix ONLY the bug causing the error, do not refactor unrelated code
- Preserve all existing imports, comments, and logic
- If the fix requires a new import, add it at the top
- Never truncate the file — return the entire thing
- Do not wrap in ```python``` blocks — raw code only"""


# ── AI call ───────────────────────────────────────────────────────

def _call_ai(model_cfg: dict, prompt: str) -> str:
    """Make a single AI call with hard timeout."""
    import concurrent.futures

    def _do_call():
        if model_cfg["kind"] == "kimi":
            resp = requests.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {model_cfg['key']}", "Accept": "application/json"},
                json={
                    "model": model_cfg["id"],
                    "messages": [
                        {"role": "system", "content": HEAL_SYSTEM},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens": 8192, "temperature": 0.1,
                    "stream": False,
                    "chat_template_kwargs": {"thinking": False},
                },
                timeout=HEAL_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
        else:
            client = OpenAI(base_url=BASE_URL, api_key=model_cfg["key"], timeout=HEAL_TIMEOUT)
            stream = client.chat.completions.create(
                model=model_cfg["id"],
                messages=[
                    {"role": "system", "content": HEAL_SYSTEM},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.1, max_tokens=8192,
                extra_body=model_cfg.get("extra", {}),
                stream=True,
            )
            out = []
            for chunk in stream:
                if not getattr(chunk, "choices", None):
                    continue
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    out.append(delta.content)
            return "".join(out)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_do_call)
        return future.result(timeout=HEAL_TIMEOUT + 10)


def _ask_ai_for_fix(error_msg: str, tb: str, file_path: Path, file_content: str) -> str | None:
    """Try each healer model in order. Returns fixed code or None."""
    prompt = f"""FILE: {file_path.name}

ERROR:
{error_msg}

TRACEBACK:
{tb}

CURRENT FILE CONTENT:
{file_content}

Return the complete fixed Python file. Raw code only, no markdown."""

    for model in HEALER_MODELS:
        print(f"[AutoHealer] Asking {model['name']} to fix {file_path.name}…")
        try:
            result = _call_ai(model, prompt)
            if result and len(result.strip()) > 50:
                # Strip any accidental markdown fences
                result = re.sub(r"^```python\s*", "", result.strip(), flags=re.MULTILINE)
                result = re.sub(r"^```\s*",       "", result.strip(), flags=re.MULTILINE)
                result = re.sub(r"\s*```$",        "", result.strip(), flags=re.MULTILINE)
                return result
        except Exception as e:
            print(f"[AutoHealer] {model['name']} failed: {e}")
    return None


# ── File identification ───────────────────────────────────────────

def _extract_project_files(tb_str: str, project_root: Path) -> list[Path]:
    """
    Parse a traceback string and return all project source files mentioned,
    ordered by most-recent frame first (most likely culprit).
    """
    pattern = re.compile(r'File "([^"]+)", line (\d+)')
    files   = []
    for match in reversed(pattern.findall(tb_str)):
        fpath = Path(match[0])
        try:
            fpath.relative_to(project_root)   # only project files
            if fpath.suffix == ".py" and fpath not in files:
                files.append(fpath)
        except ValueError:
            pass
    return files


# ── Main heal entry point ─────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent   # project root (auto-detected)


def heal_and_retry(
    fn:          Callable,
    fn_args:     tuple = (),
    fn_kwargs:   dict | None = None,
    max_retries: int   = MAX_RETRIES,
    agent_name:  str   = "agent",
) -> Any:
    """
    Call fn(*fn_args, **fn_kwargs).
    On any exception: identify failing file → ask AI for fix →
    patch file → reload module → retry. Up to max_retries times.

    Returns the function's return value on success.
    Raises the last exception if all retries fail.
    """
    fn_kwargs    = fn_kwargs or {}
    last_exc     = None
    healed_files: set[str] = set()

    for attempt in range(1, max_retries + 2):   # +1 for initial attempt
        try:
            return fn(*fn_args, **fn_kwargs)

        except Exception as exc:
            last_exc = exc
            tb_str   = traceback.format_exc()
            err_msg  = f"{type(exc).__name__}: {exc}"

            print(f"\n[AutoHealer] ⚠️  {agent_name} crashed (attempt {attempt})")
            print(f"[AutoHealer] Error: {err_msg}")

            if attempt > max_retries:
                print(f"[AutoHealer] ✗ Max retries ({max_retries}) exhausted. Giving up.")
                raise

            # Find project files in traceback
            failing_files = _extract_project_files(tb_str, PROJECT_ROOT)
            if not failing_files:
                print("[AutoHealer] Could not find a project file in traceback — cannot heal.")
                raise

            healed_this_round = False
            for fpath in failing_files:
                fpath_str = str(fpath)
                if fpath_str in healed_files:
                    continue   # already tried healing this file

                print(f"[AutoHealer] 🔧 Attempting to heal: {fpath.name}")
                try:
                    original  = fpath.read_text(encoding="utf-8")
                    fixed     = _ask_ai_for_fix(err_msg, tb_str, fpath, original)

                    if not fixed:
                        print(f"[AutoHealer] AI returned no fix for {fpath.name}")
                        continue

                    # Sanity check: must compile to valid Python AST
                    try:
                        import ast
                        ast.parse(fixed)
                    except SyntaxError as e:
                        print(f"[AutoHealer] AI response failed syntax check ({e}) — skipping")
                        continue

                    # Back up the original
                    backup = fpath.with_suffix(f".py.bak{attempt}")
                    backup.write_text(original, encoding="utf-8")
                    print(f"[AutoHealer] Backed up original → {backup.name}")

                    # Write the fix atomically
                    tmp_path = fpath.with_suffix(".tmp")
                    tmp_path.write_text(fixed, encoding="utf-8")
                    tmp_path.replace(fpath)
                    print(f"[AutoHealer] ✓ Patched {fpath.name}")

                    # Reload the affected module
                    _reload_module(fpath)

                    healed_files.add(fpath_str)
                    healed_this_round = True
                    break   # heal one file at a time, then retry

                except Exception as heal_err:
                    print(f"[AutoHealer] Heal attempt failed: {heal_err}")

            if not healed_this_round:
                print("[AutoHealer] Could not heal any file — raising original error.")
                raise last_exc

            print(f"[AutoHealer] Retrying {agent_name} (attempt {attempt + 1}/{max_retries + 1})…\n")
            time.sleep(1)

    if last_exc is not None:
        raise last_exc
    raise Exception("Heal loop exhausted without recording an exception")


def _reload_module(fpath: Path):
    """Reload the Python module corresponding to a file path."""
    try:
        # Convert file path to dotted module name relative to project root
        rel      = fpath.relative_to(PROJECT_ROOT)
        mod_name = ".".join(rel.with_suffix("").parts)
        if mod_name in sys.modules:
            importlib.reload(sys.modules[mod_name])
            print(f"[AutoHealer] Reloaded module: {mod_name}")
    except Exception as e:
        print(f"[AutoHealer] Module reload skipped: {e}")
