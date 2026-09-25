"""LLM gateway with an ordered fallback chain.

Order comes from LLM_PROVIDER_ORDER (default: sarvam -> gemini -> groq -> openrouter -> openai -> rules).
A provider is skipped when its key is missing. When a call fails because tokens/credits are
exhausted (402/429/quota), the key is rejected (401/403), the server errors (5xx) or times out,
the provider is put on cooldown and the next one is tried. The final `rules` provider is a
deterministic offline fallback so the demo never dies.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from .config import settings
from .events import publish


@dataclass
class Provider:
    name: str
    url: str
    model: str
    key: str
    auth: str = "bearer"  # bearer | sarvam
    extra_headers: dict[str, str] = field(default_factory=dict)
    cooldown_until: float = 0.0
    disabled_reason: str = ""
    calls: int = 0
    failures: int = 0
    last_error: str = ""
    last_latency_ms: int = 0

    @property
    def configured(self) -> bool:
        return bool(self.key)

    def available(self) -> bool:
        return self.configured and not self.disabled_reason and time.time() >= self.cooldown_until

    def headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", **self.extra_headers}
        if self.auth == "sarvam":
            h["api-subscription-key"] = self.key
        else:
            h["Authorization"] = f"Bearer {self.key}"
        return h


def _build_providers() -> dict[str, Provider]:
    s = settings
    return {
        "sarvam": Provider("sarvam", f"{s.sarvam_base_url}/v1/chat/completions", s.sarvam_chat_model, s.sarvam_api_key, auth="sarvam"),
        "gemini": Provider("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", s.gemini_model, s.gemini_api_key),
        "groq": Provider("groq", "https://api.groq.com/openai/v1/chat/completions", s.groq_model, s.groq_api_key),
        "openrouter": Provider(
            "openrouter", "https://openrouter.ai/api/v1/chat/completions", s.openrouter_model, s.openrouter_api_key,
            extra_headers={"HTTP-Referer": "https://commerceos.local", "X-Title": "Paytm Commerce OS"},
        ),
        "openai": Provider("openai", "https://api.openai.com/v1/chat/completions", s.openai_model, s.openai_api_key),
    }


PROVIDERS = _build_providers()
ORDER = [p.strip() for p in settings.llm_provider_order.split(",") if p.strip()]

_THINK = re.compile(r"<think>.*?</think>", re.S)
_EXHAUSTED_HINTS = ("quota", "insufficient", "credit", "exhausted", "rate limit", "limit exceeded", "billing")


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    fallback_used: bool


class LLMUnavailable(Exception):
    pass


async def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    max_tokens: int = 700,
    json_mode: bool = False,
    rules: Callable[[], str] | None = None,
    agent: str = "system",
) -> LLMResult:
    tried: list[str] = []
    async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
        for name in ORDER:
            if name == "rules":
                break
            p = PROVIDERS.get(name)
            if not p or not p.available():
                continue
            tried.append(name)
            body: dict[str, Any] = {
                "model": p.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if json_mode and name in ("openai", "groq", "gemini"):
                body["response_format"] = {"type": "json_object"}
            t0 = time.time()
            p.calls += 1
            try:
                r = await client.post(p.url, headers=p.headers(), json=body)
                p.last_latency_ms = int((time.time() - t0) * 1000)
                if r.status_code >= 400:
                    _handle_http_error(p, r)
                    continue
                data = r.json()
                text = data["choices"][0]["message"].get("content") or ""
                text = _THINK.sub("", text).strip()
                if not text:
                    raise ValueError("empty completion")
                if len(tried) > 1:
                    publish(agent, "system", f"LLM fallback → {name}", f"Skipped: {', '.join(tried[:-1])}", partner="llm", status="warn")
                return LLMResult(text, name, p.model, fallback_used=len(tried) > 1)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                _cool(p, f"network: {type(e).__name__}", 60)
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                _cool(p, f"bad response: {e}", 30)

    if rules is not None and "rules" in ORDER:
        if tried:
            publish(agent, "system", "LLM fallback → offline rules", f"All providers failed: {', '.join(tried)}", partner="llm", status="warn")
        return LLMResult(rules(), "rules", "deterministic", fallback_used=bool(tried))
    raise LLMUnavailable(f"No LLM provider available (tried: {tried or 'none configured'})")


def _handle_http_error(p: Provider, r: httpx.Response) -> None:
    msg = r.text[:200].lower()
    p.failures += 1
    if r.status_code in (401, 403) and not any(h in msg for h in _EXHAUSTED_HINTS):
        p.disabled_reason = f"auth error {r.status_code}"
        p.last_error = p.disabled_reason
    elif r.status_code in (402, 429) or any(h in msg for h in _EXHAUSTED_HINTS):
        _cool(p, f"exhausted/rate-limited ({r.status_code})", settings.llm_cooldown_s)
    elif r.status_code >= 500:
        _cool(p, f"server error {r.status_code}", 60)
    else:
        _cool(p, f"http {r.status_code}: {r.text[:120]}", 30)


def _cool(p: Provider, reason: str, seconds: int) -> None:
    p.failures += 1
    p.last_error = reason
    p.cooldown_until = time.time() + seconds


async def chat_json(
    system: str,
    user: str,
    *,
    fallback: Callable[[], dict[str, Any]],
    agent: str = "system",
    temperature: float = 0.2,
) -> tuple[dict[str, Any], str]:
    """Ask for JSON. Returns (parsed_dict, provider). Falls back to `fallback()` if parsing fails."""
    res = await chat(
        [{"role": "system", "content": system + "\nRespond with a single valid JSON object only. No prose, no markdown."},
         {"role": "user", "content": user}],
        json_mode=True,
        temperature=temperature,
        rules=lambda: json.dumps(fallback()),
        agent=agent,
    )
    parsed = extract_json(res.text)
    if parsed is None:
        return fallback(), "rules"
    return parsed, res.provider


def extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else None
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                v = json.loads(m.group(0))
                return v if isinstance(v, dict) else None
            except json.JSONDecodeError:
                return None
    return None


def status() -> list[dict[str, Any]]:
    now = time.time()
    out = []
    for name in ORDER:
        if name == "rules":
            out.append({"name": "rules", "model": "deterministic", "configured": True, "state": "ready", "calls": 0,
                        "failures": 0, "last_error": "", "latency_ms": 0})
            continue
        p = PROVIDERS.get(name)
        if not p:
            continue
        if not p.configured:
            state = "no key"
        elif p.disabled_reason:
            state = "disabled"
        elif now < p.cooldown_until:
            state = f"cooldown {int(p.cooldown_until - now)}s"
        else:
            state = "ready"
        out.append({"name": name, "model": p.model, "configured": p.configured, "state": state, "calls": p.calls,
                    "failures": p.failures, "last_error": p.last_error, "latency_ms": p.last_latency_ms})
    return out


def reset(name: str | None = None) -> None:
    for p in PROVIDERS.values():
        if name is None or p.name == name:
            p.cooldown_until = 0
            p.disabled_reason = ""
            p.last_error = ""
