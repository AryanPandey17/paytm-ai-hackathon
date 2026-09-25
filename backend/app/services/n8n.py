"""n8n action layer. Agents never talk to WhatsApp/Paytm directly: they call n8n webhooks.

If N8N_BASE_URL is empty or n8n is unreachable, the action is SIMULATED locally (logged to the
activity feed and shown in the in-app WhatsApp simulator) so the demo still runs end-to-end.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from .. import db
from ..config import settings
from ..events import publish

_stats = {"calls": 0, "ok": 0, "simulated": 0, "errors": 0, "last_error": ""}

PATHS = {
    "udhaar-nudge": lambda: settings.n8n_path_udhaar,
    "capital-offer": lambda: settings.n8n_path_capital,
    "onboarding-escalation": lambda: settings.n8n_path_escalation,
    "whatsapp-send": lambda: settings.n8n_path_send,
    "bazaar-po": lambda: settings.n8n_path_po,
}


def configured() -> bool:
    return bool(settings.n8n_base_url)


def status() -> dict[str, Any]:
    return {"configured": configured(), "base_url": settings.n8n_base_url or None, **_stats}


async def trigger(workflow: str, payload: dict[str, Any], *, agent: str, title: str) -> dict[str, Any]:
    _stats["calls"] += 1
    if configured():
        url = settings.n8n_base_url.rstrip("/") + PATHS[workflow]()
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(url, json=payload, headers={"X-CommerceOS-Secret": settings.n8n_webhook_secret})
            if r.status_code < 400:
                _stats["ok"] += 1
                try:
                    body = r.json()
                except ValueError:
                    body = {"raw": r.text[:200]}
                publish(agent, "act", title, f"n8n workflow `{workflow}` executed", partner="n8n",
                        data={"workflow": workflow, "mode": "live", "response": body})
                return {"mode": "live", "response": body}
            _stats["errors"] += 1
            _stats["last_error"] = f"{r.status_code}: {r.text[:120]}"
        except httpx.HTTPError as e:
            _stats["errors"] += 1
            _stats["last_error"] = str(e)
        publish(agent, "system", "n8n unreachable → simulating action", _stats["last_error"][:140], partner="n8n", status="warn")
    _stats["simulated"] += 1
    publish(agent, "act", title, f"n8n workflow `{workflow}` (simulated)", partner="n8n",
            data={"workflow": workflow, "mode": "simulated"})
    return {"mode": "simulated"}


def log_message(phone: str, direction: str, sender: str, text: str, *, kind: str = "text",
                meta: dict[str, Any] | None = None, via: str = "whatsapp") -> int:
    return db.x(
        "INSERT INTO messages(thread, phone, direction, sender, text, kind, meta, ts, via) VALUES (?,?,?,?,?,?,?,?,?)",
        (phone, phone, direction, sender, text, kind, db.dumps(meta or {}), datetime.now().isoformat(timespec="seconds"), via))


async def send_whatsapp(phone: str, text: str, *, agent: str, sender: str = "CommerceOS", kind: str = "text",
                        meta: dict[str, Any] | None = None, workflow: str = "whatsapp-send",
                        extra: dict[str, Any] | None = None, title: str | None = None) -> dict[str, Any]:
    """Log the outbound message (for the simulator) and ask n8n to deliver it on WhatsApp."""
    log_message(phone, "out", sender, text, kind=kind, meta=meta)
    payload = {"to": phone, "text": text, "kind": kind, "meta": meta or {}, **(extra or {})}
    return await trigger(workflow, payload, agent=agent, title=title or f"WhatsApp → {phone[-4:]}")
