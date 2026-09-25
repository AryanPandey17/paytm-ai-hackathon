"""Human-in-the-loop queue. Created by agents when a guardrail fires; decided from WhatsApp (via n8n callback) or the dashboard."""
from __future__ import annotations

from typing import Any

from .. import db
from ..config import settings
from ..events import publish
from ..services import memory, n8n
from .base import inr, now_iso


async def create(kind: str, ref_id: str, agent: str, title: str, detail: str, amount: float | None,
                 payload: dict[str, Any], *, workflow: str) -> int:
    aid = db.x("INSERT INTO approvals(kind, ref_id, agent, title, detail, amount, status, channel, created, payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
               (kind, ref_id, agent, title, detail, amount, "pending", "whatsapp", now_iso(), db.dumps(payload)))
    publish(agent, "escalate", "🙋 Human approval needed", title, data={"approval_id": aid, "kind": kind})
    text = (f"🔔 *Approval #{aid}* ({agent})\n{title}\n{detail}\n\n"
            f"Reply *APPROVE {aid}* or *REJECT {aid}* (or tap the button).")
    n8n.log_message(settings.demo_ops_phone, "out", "CommerceOS", text, kind="approval", meta={"approval_id": aid})
    await n8n.trigger(workflow, {"needs_approval": True, "approval_id": aid, "ops_phone": settings.demo_ops_phone,
                                 "text": text, "title": title, "detail": detail, "amount": amount, **payload,
                                 "callback_url": f"{settings.public_backend_url}/api/callbacks/n8n"},
                      agent=agent, title=f"Approval request → ops WhatsApp (#{aid})")
    return aid


async def decide(approval_id: int, decision: str, by: str = "dashboard") -> dict[str, Any]:
    a = db.one("SELECT * FROM approvals WHERE id=?", (approval_id,))
    if not a:
        return {"ok": False, "reason": "not found"}
    if a["status"] != "pending":
        return {"ok": False, "reason": f"already {a['status']}"}
    decision = "approved" if decision.lower().startswith(("app", "yes", "haan", "ok")) else "rejected"
    db.x("UPDATE approvals SET status=?, decided=?, decided_by=? WHERE id=?", (decision, now_iso(), by, approval_id))
    a = {**a, "status": decision, "decided_by": by}
    publish(a["agent"], "escalate", f"Human {decision} #{approval_id}", f"via {by} · {a['title']}",
            status="ok" if decision == "approved" else "warn")
    n8n.log_message(settings.demo_ops_phone, "in", "Ops", f"{decision.upper()} {approval_id}", via=by)
    await memory.remember("portfolio", f"Human ({by}) {decision} {a['kind']} #{approval_id}: {a['title']}"
                          + (f" amount {inr(a['amount'])}" if a["amount"] else ""), agent=a["agent"], quiet=True)
    if a["kind"] == "capital_offer":
        from . import capital
        await capital.on_approval(a, decision)
    elif a["kind"] == "onboarding_exception":
        from . import onboarder
        await onboarder.on_approval(a, decision)
    return {"ok": True, "status": decision}


def pending() -> list[dict[str, Any]]:
    return db.q("SELECT * FROM approvals ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, id DESC LIMIT 50")
