"""Merchant Memory Graph (MMG).

MEMORY_BACKEND=cognee -> writes go to Cognee (add + batched cognify), reads use Cognee GRAPH_COMPLETION search.
MEMORY_BACKEND=local  -> lightweight graph in SQLite (edges + event log) with keyword recall.

The local graph is ALWAYS written too, so the dashboard can draw the graph and the demo works
offline if Cognee is not installed or its LLM key is exhausted.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from .. import db
from ..config import settings
from ..events import publish

_cognee = None
_cognee_error = ""
_pending_cognify: set[str] = set()
_stats = {"writes": 0, "reads": 0, "cognee_writes": 0, "cognee_reads": 0, "cognify_runs": 0}


def _load_cognee():
    global _cognee, _cognee_error
    if settings.memory_backend != "cognee" or _cognee is not None or _cognee_error:
        return _cognee
    try:
        import os

        if settings.cognee_llm_api_key:
            os.environ.setdefault("LLM_API_KEY", settings.cognee_llm_api_key)
        import cognee  # type: ignore

        _cognee = cognee
    except Exception as e:  # noqa: BLE001
        _cognee_error = f"cognee import failed: {e}"
    return _cognee


def backend() -> str:
    return "cognee" if _load_cognee() else "local"


def status() -> dict[str, Any]:
    _load_cognee()
    n_events = db.one("SELECT COUNT(*) c FROM mem_events")["c"]
    n_edges = db.one("SELECT COUNT(*) c FROM mem_edges")["c"]
    return {"requested": settings.memory_backend, "active": backend(), "error": _cognee_error,
            "events": n_events, "edges": n_edges, "pending_cognify": sorted(_pending_cognify), **_stats}


def dataset_for(merchant_id: str) -> str:
    return f"merchant_{merchant_id}"


async def remember(
    dataset: str,
    text: str,
    *,
    agent: str = "system",
    edges: list[tuple[str, str, str, str, str]] | None = None,
    quiet: bool = False,
) -> None:
    """edges: (src, src_type, rel, dst, dst_type)"""
    now = datetime.now().isoformat(timespec="seconds")
    db.x("INSERT INTO mem_events(dataset, agent, text, entities, ts) VALUES (?,?,?,?,?)",
         (dataset, agent, text, db.dumps([e[0] for e in edges or []] + [e[3] for e in edges or []]), now))
    for e in edges or []:
        db.x("INSERT INTO mem_edges(dataset, src, src_type, rel, dst, dst_type, ts) VALUES (?,?,?,?,?,?,?)",
             (dataset, e[0], e[1], e[2], e[3], e[4], now))
    _stats["writes"] += 1
    cg = _load_cognee()
    if cg:
        try:
            await cg.add(text, dataset_name=dataset)
            _pending_cognify.add(dataset)
            _stats["cognee_writes"] += 1
        except Exception as e:  # noqa: BLE001
            publish(agent, "system", "Cognee write failed → local graph only", str(e)[:140], partner="cognee", status="warn")
    if not quiet:
        publish(agent, "learn", "Memory updated", text[:160], partner="cognee" if cg else "memory")


async def cognify(dataset: str | None = None) -> dict[str, Any]:
    cg = _load_cognee()
    if not cg:
        return {"ok": False, "reason": "cognee not active"}
    targets = [dataset] if dataset else sorted(_pending_cognify)
    if not targets:
        return {"ok": True, "datasets": []}
    try:
        await cg.cognify(datasets=targets)
        for t in targets:
            _pending_cognify.discard(t)
        _stats["cognify_runs"] += 1
        publish("system", "learn", "Cognee graph rebuilt", ", ".join(targets), partner="cognee")
        return {"ok": True, "datasets": targets}
    except Exception as e:  # noqa: BLE001
        publish("system", "system", "Cognee cognify failed", str(e)[:160], partner="cognee", status="warn")
        return {"ok": False, "reason": str(e)}


async def recall(dataset: str, query: str, *, k: int = 6, agent: str = "system") -> dict[str, Any]:
    """Returns {answer, facts[], backend}."""
    _stats["reads"] += 1
    local = _local_recall(dataset, query, k)
    cg = _load_cognee()
    if cg and dataset not in _pending_cognify:
        try:
            from cognee import SearchType  # type: ignore

            res = await asyncio.wait_for(
                cg.search(query_text=query, query_type=SearchType.GRAPH_COMPLETION, datasets=[dataset]), timeout=30)
            _stats["cognee_reads"] += 1
            answer = res[0] if isinstance(res, list) and res else str(res)
            if isinstance(answer, dict):
                answer = answer.get("search_result") or answer.get("text") or str(answer)
            publish(agent, "recall", "Recalled from Cognee graph", query, partner="cognee", data={"answer": str(answer)[:400]})
            return {"answer": str(answer), "facts": local, "backend": "cognee"}
        except Exception as e:  # noqa: BLE001
            publish(agent, "system", "Cognee search failed → local recall", str(e)[:140], partner="cognee", status="warn")
    publish(agent, "recall", "Recalled from memory graph", query, partner="cognee" if cg else "memory",
            data={"facts": local[:4]})
    return {"answer": " ".join(local[:3]), "facts": local, "backend": "local"}


def _local_recall(dataset: str, query: str, k: int) -> list[str]:
    terms = {t for t in re.findall(r"[\wऀ-ॿ]+", query.lower()) if len(t) > 2}
    rows = db.q("SELECT text FROM mem_events WHERE dataset IN (?, 'portfolio') ORDER BY id DESC LIMIT 400", (dataset,))
    scored = []
    for i, r in enumerate(rows):
        words = set(re.findall(r"[\wऀ-ॿ]+", r["text"].lower()))
        s = len(terms & words) + (0.001 * (len(rows) - i))
        if s >= 1:
            scored.append((s, r["text"]))
    scored.sort(reverse=True)
    return [t for _, t in scored[:k]]


def neighbours(dataset: str, entity: str) -> list[dict[str, Any]]:
    return db.q(
        "SELECT src, src_type, rel, dst, dst_type FROM mem_edges WHERE dataset=? AND (src=? OR dst=?) ORDER BY id DESC LIMIT 50",
        (dataset, entity, entity))


def graph(dataset: str, limit: int = 160) -> dict[str, Any]:
    edges = db.q("SELECT DISTINCT src, src_type, rel, dst, dst_type FROM mem_edges WHERE dataset=? ORDER BY id DESC LIMIT ?",
                 (dataset, limit))
    nodes: dict[str, dict[str, Any]] = {}
    for e in edges:
        nodes.setdefault(e["src"], {"id": e["src"], "type": e["src_type"]})
        nodes.setdefault(e["dst"], {"id": e["dst"], "type": e["dst_type"]})
    return {"nodes": list(nodes.values()), "edges": edges}


def recent(dataset: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
    if dataset:
        return db.q("SELECT * FROM mem_events WHERE dataset=? ORDER BY id DESC LIMIT ?", (dataset, limit))
    return db.q("SELECT * FROM mem_events ORDER BY id DESC LIMIT ?", (limit,))
