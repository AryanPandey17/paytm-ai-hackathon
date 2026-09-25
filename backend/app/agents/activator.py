"""Activator: device -> dispatch -> field agent (if worth it) -> real-time intervention -> first transaction."""
from __future__ import annotations

from typing import Any

from .. import db
from ..events import publish
from ..services import memory, n8n
from .base import now_iso

AGENT = "activator"

FIXES = {
    "device_offline": "Soundbox band dikh raha hai. 1) Power button 5 sec dabaiye 2) Charger lagaiye 3) Green light aane par ek ₹1 test payment kijiye.",
    "qr_not_displayed": "QR standee counter par saamne lagaiye, taaki grahak aasaani se scan kar sake. Photo bhej dijiye, hum check kar lenge ✅",
}


async def intervene() -> list[dict[str, Any]]:
    out = []
    for a in db.q("SELECT * FROM activations WHERE issue IS NOT NULL AND first_txn_at IS NULL"):
        publish(AGENT, "trigger", f"Stuck activation · {a['shop']}", f"{a['issue']} · {a['hours_since_delivery']}h since delivery", status="warn")
        await n8n.send_whatsapp(f"9198000{a['id'][-2:]}777",
                                f"Namaste {a['merchant_name'].split()[0]} ji! {FIXES.get(a['issue'], 'Humari team aapki madad karegi.')}",
                                agent=AGENT, sender="Paytm Activation", title=f"Self-help guide → {a['shop']}")
        action = "self-help sent"
        if a["hours_since_delivery"] > 24 and not a["field_agent"]:
            db.x("UPDATE activations SET field_agent=? WHERE id=?", ("FA-Rohan", a["id"]))
            await n8n.trigger("whatsapp-send", {"to": "field-agent", "text": f"Visit {a['shop']} ({a['area']}): {a['issue']}"},
                              agent=AGENT, title=f"Field agent FA-Rohan assigned → {a['shop']}")
            action += " + field agent"
        await memory.remember("portfolio", f"Activator intervened at {a['shop']} for {a['issue']}: {action}.", agent=AGENT,
                              edges=[("Activator", "Agent", "INTERVENED", a["shop"], "Merchant")], quiet=True)
        out.append({"shop": a["shop"], "issue": a["issue"], "action": action})
    return out


async def first_transaction(activation_id: str) -> dict[str, Any]:
    a = db.one("SELECT * FROM activations WHERE id=?", (activation_id,))
    if not a:
        return {"ok": False}
    db.x("UPDATE activations SET stage='first_txn', issue=NULL, first_txn_at=? WHERE id=?", (now_iso(), activation_id))
    publish(AGENT, "act", f"🎉 First transaction · {a['shop']}", "Handed to Grower with first-transaction context", partner="paytm")
    await memory.remember("portfolio", f"{a['shop']} completed its first transaction; handed over to Grower.", agent=AGENT,
                          edges=[(a["shop"], "Merchant", "ACTIVATED_BY", "Activator", "Agent")])
    return {"ok": True}
