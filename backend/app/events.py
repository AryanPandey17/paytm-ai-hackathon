"""In-process event bus. Every agent step is published here and streamed to the UI over SSE."""
import asyncio
import itertools
import json
import time
from collections import deque
from typing import Any

_counter = itertools.count(1)
_history: deque[dict[str, Any]] = deque(maxlen=300)
_subscribers: set[asyncio.Queue] = set()


def publish(
    agent: str,
    kind: str,
    title: str,
    detail: str = "",
    *,
    partner: str | None = None,
    data: dict[str, Any] | None = None,
    status: str = "ok",
) -> dict[str, Any]:
    """kind: trigger | understand | recall | decide | act | escalate | learn | system"""
    evt = {
        "id": next(_counter),
        "ts": time.time(),
        "agent": agent,
        "kind": kind,
        "title": title,
        "detail": detail,
        "partner": partner,
        "status": status,
        "data": data or {},
    }
    _history.append(evt)
    for q in list(_subscribers):
        try:
            q.put_nowait(evt)
        except asyncio.QueueFull:
            pass
    return evt


def history(limit: int = 100) -> list[dict[str, Any]]:
    return list(_history)[-limit:]


async def stream():
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _subscribers.add(q)
    try:
        yield "retry: 2000\n\n"
        while True:
            try:
                evt = await asyncio.wait_for(q.get(), timeout=15)
                yield f"data: {json.dumps(evt, default=str)}\n\n"
            except asyncio.TimeoutError:
                yield ": ping\n\n"
    finally:
        _subscribers.discard(q)
