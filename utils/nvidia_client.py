"""
NVIDIA API client — DeepSeek V4 Pro, Kimi K2.6, GLM 5.1.
Hard 45-second timeout per attempt. Auto-fallback across all 3 models.
If all models fail, returns empty string (never raises to caller).
"""
import os
import time
import requests
import concurrent.futures
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
TIMEOUT_S = 45   # hard wall-clock timeout per model attempt

MODELS = {
    "deepseek": {
        "id":    "deepseek-ai/deepseek-v4-pro",
        "key":   os.getenv("NVIDIA_DEEPSEEK_KEY"),
        "extra": {"chat_template_kwargs": {"thinking": False}},
        "kind":  "openai",
    },
    "kimi": {
        "id":  "moonshotai/kimi-k2.6",
        "key": os.getenv("NVIDIA_KIMI_KEY"),
        "kind": "kimi",
    },
    "glm": {
        "id":    "z-ai/glm-5.1",
        "key":   os.getenv("NVIDIA_GLM_KEY"),
        "extra": {"chat_template_kwargs": {"enable_thinking": True, "clear_thinking": False}},
        "kind":  "openai",
    },
}


def _build_messages(prompt: str, system: str) -> list[dict]:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    return msgs


def _call_openai(cfg: dict, prompt: str, system: str, temperature: float, max_tokens: int) -> str:
    client = OpenAI(base_url=BASE_URL, api_key=cfg["key"], timeout=TIMEOUT_S)
    msgs   = _build_messages(prompt, system)
    stream = client.chat.completions.create(
        model=cfg["id"],
        messages=msgs,
        temperature=temperature,
        top_p=0.95,
        max_tokens=max_tokens,
        extra_body=cfg.get("extra", {}),
        stream=True,
    )
    out = []
    for chunk in stream:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        if getattr(delta, "reasoning_content", None):
            out.append(delta.reasoning_content)
        if getattr(delta, "content", None):
            out.append(delta.content)
    return "".join(out)


def _call_kimi(cfg: dict, prompt: str, system: str, temperature: float, max_tokens: int) -> str:
    msgs = _build_messages(prompt, system)
    resp = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {cfg['key']}", "Accept": "application/json"},
        json={
            "model": cfg["id"], "messages": msgs,
            "max_tokens": max_tokens, "temperature": temperature,
            "top_p": 1.0, "stream": False,
            "chat_template_kwargs": {"thinking": False},
        },
        timeout=TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


class NvidiaClient:
    """
    Unified NVIDIA client with:
    - 45-second hard timeout per attempt (won't hang for minutes)
    - Automatic fallback across DeepSeek → Kimi → GLM
    - Returns "" if all models fail (never crashes the pipeline)
    """

    def __init__(self, model: str = "deepseek"):
        if model not in MODELS:
            raise ValueError(f"Unknown model: {model}. Choose: {list(MODELS)}")
        self.preferred = model

    def complete(
        self,
        prompt:      str,
        system:      str   = "",
        temperature: float = 0.7,
        max_tokens:  int   = 4096,
    ) -> str:
        # Try preferred model first, then others
        order = [self.preferred] + [m for m in MODELS if m != self.preferred]

        for name in order:
            cfg = MODELS[name]
            fn  = _call_kimi if cfg["kind"] == "kimi" else _call_openai
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            print(f"[NvidiaClient] Trying {name}…")
            try:
                future = executor.submit(fn, cfg, prompt, system, temperature, max_tokens)
                result = future.result(timeout=TIMEOUT_S + 5)  # ThreadPoolExecutor timeout
                if result and result.strip():
                    print(f"[NvidiaClient] ✓ {name} responded ({len(result)} chars)")
                    return result
            except concurrent.futures.TimeoutError:
                print(f"[NvidiaClient] ✗ {name} timed out after {TIMEOUT_S}s — trying fallback…")
            except Exception as e:
                print(f"[NvidiaClient] ✗ {name} error: {type(e).__name__}: {str(e)[:80]} — trying fallback…")
            finally:
                executor.shutdown(wait=False)
            time.sleep(1)

        print("[NvidiaClient] All models failed — returning empty string")
        return ""
