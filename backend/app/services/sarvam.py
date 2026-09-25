"""Sarvam speech + translation. Every call degrades gracefully when no key / credits are exhausted."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import httpx

from ..config import settings
from ..events import publish

LANG_NAMES = {
    "hi-IN": "Hindi", "mr-IN": "Marathi", "gu-IN": "Gujarati", "ta-IN": "Tamil", "te-IN": "Telugu",
    "kn-IN": "Kannada", "ml-IN": "Malayalam", "bn-IN": "Bengali", "pa-IN": "Punjabi", "od-IN": "Odia",
    "en-IN": "English",
}

_state = {"stt_calls": 0, "tts_calls": 0, "translate_calls": 0, "last_error": ""}


def configured() -> bool:
    return bool(settings.sarvam_api_key)


def status() -> dict:
    return {"configured": configured(), **_state}


def _headers() -> dict[str, str]:
    return {"api-subscription-key": settings.sarvam_api_key}


async def speech_to_text(audio: bytes, filename: str, content_type: str, language: str = "unknown") -> dict:
    """Returns {transcript, language_code, provider}."""
    if not configured():
        raise RuntimeError("SARVAM_API_KEY not set")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{settings.sarvam_base_url}/speech-to-text",
            headers=_headers(),
            files={"file": (filename, audio, content_type or "audio/ogg")},
            data={"model": settings.sarvam_stt_model, "language_code": language},
        )
    _state["stt_calls"] += 1
    if r.status_code >= 400:
        _state["last_error"] = f"STT {r.status_code}: {r.text[:120]}"
        raise RuntimeError(_state["last_error"])
    d = r.json()
    return {"transcript": d.get("transcript", ""), "language_code": d.get("language_code") or language, "provider": "sarvam"}


async def text_to_speech(text: str, language: str = "hi-IN") -> dict:
    """Returns {audio_url|None, provider}. Caches by hash so demos replay without spending credits."""
    cache = Path(settings.audio_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{language}|{settings.sarvam_tts_speaker}|{text}".encode()).hexdigest()[:16]
    path = cache / f"{key}.wav"
    if path.exists():
        return {"audio_url": f"/audio/{path.name}", "provider": "sarvam-cache"}
    if not configured():
        return {"audio_url": None, "provider": "browser-tts"}
    chunks = _chunk(text, 2400)
    wavs: list[bytes] = []
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            for ch in chunks:
                r = await c.post(
                    f"{settings.sarvam_base_url}/text-to-speech",
                    headers={**_headers(), "Content-Type": "application/json"},
                    json={"text": ch, "target_language_code": language, "model": settings.sarvam_tts_model,
                          "speaker": settings.sarvam_tts_speaker},
                )
                _state["tts_calls"] += 1
                if r.status_code >= 400:
                    raise RuntimeError(f"TTS {r.status_code}: {r.text[:120]}")
                wavs.extend(base64.b64decode(a) for a in r.json().get("audios", []))
    except Exception as e:  # noqa: BLE001
        _state["last_error"] = str(e)
        publish("grower", "system", "Sarvam TTS unavailable → browser voice", str(e)[:140], partner="sarvam", status="warn")
        return {"audio_url": None, "provider": "browser-tts"}
    path.write_bytes(_join_wavs(wavs))
    return {"audio_url": f"/audio/{path.name}", "provider": "sarvam"}


async def translate(text: str, target: str, source: str = "auto") -> tuple[str, str]:
    """Returns (translated_text, provider). Falls back to the LLM chain, then to the original text."""
    if target.startswith("en") or not text.strip():
        return text, "none"
    if configured():
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    f"{settings.sarvam_base_url}/translate",
                    headers={**_headers(), "Content-Type": "application/json"},
                    json={"input": text[:1000], "source_language_code": source, "target_language_code": target,
                          "model": settings.sarvam_translate_model, "mode": "modern-colloquial"},
                )
            _state["translate_calls"] += 1
            if r.status_code < 400:
                return r.json().get("translated_text", text), "sarvam"
            _state["last_error"] = f"translate {r.status_code}: {r.text[:120]}"
        except httpx.HTTPError as e:
            _state["last_error"] = str(e)
    from .. import llm

    lang = LANG_NAMES.get(target, "Hindi")
    res = await llm.chat(
        [{"role": "system", "content": f"Translate the user's message to conversational {lang} (Devanagari/native script). Output only the translation."},
         {"role": "user", "content": text}],
        rules=lambda: text,
        agent="system",
    )
    return res.text, res.provider


def _chunk(text: str, n: int) -> list[str]:
    parts, cur = [], ""
    for sent in text.replace("।", "।\n").replace(". ", ".\n").split("\n"):
        if len(cur) + len(sent) + 1 > n and cur:
            parts.append(cur.strip())
            cur = ""
        cur += " " + sent
    if cur.strip():
        parts.append(cur.strip())
    return parts or [text[:n]]


def _join_wavs(wavs: list[bytes]) -> bytes:
    if len(wavs) == 1:
        return wavs[0]
    import io
    import wave

    out = io.BytesIO()
    params = None
    frames = []
    for w in wavs:
        with wave.open(io.BytesIO(w)) as wf:
            params = params or wf.getparams()
            frames.append(wf.readframes(wf.getnframes()))
    with wave.open(out, "wb") as wo:
        wo.setparams(params)
        for f in frames:
            wo.writeframes(f)
    return out.getvalue()
