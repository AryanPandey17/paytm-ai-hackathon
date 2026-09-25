"""Bazaar (embedded in Grower): demand forecast -> multi-supplier quotes -> allocation -> auto-PO."""
from __future__ import annotations

import math
from typing import Any

from .. import db
from ..events import publish
from ..services import memory, n8n
from .base import inr, merchant, now_iso

AGENT = "bazaar"
COVER_DAYS = 14


def forecast(mid: str, festival: str, days_to_festival: int) -> list[dict[str, Any]]:
    """Need = velocity x festival multiplier x cover days - stock. Festival lift ramps in when <30 days away."""
    lift_weight = 1.0 if days_to_festival <= 45 else max(0.3, 45 / max(days_to_festival, 1))  # festive buying starts ~6 weeks out
    items = []
    for p in db.q("SELECT * FROM products WHERE merchant_id=?", (mid,)):
        mult = 1 + (p["festival_multiplier"] - 1) * lift_weight
        demand = p["daily_velocity"] * mult * COVER_DAYS
        need = math.ceil(max(0, demand - p["stock"]))
        if need > 0 and (p["stock"] <= p["reorder_level"] or p["category"] == "festive"):
            items.append({"sku": p["sku"], "name": p["name"], "name_local": p["name_local"], "qty": need,
                          "unit_cost": round(p["price"] * 0.82, 2), "stock": p["stock"], "category": p["category"]})
    return items


def quote_and_allocate(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-item supplier choice on effective cost = price - credit benefit + delivery penalty (MILP in production)."""
    suppliers = db.q("SELECT * FROM suppliers")
    alloc: dict[str, list[dict[str, Any]]] = {}
    quotes = []
    for it in items:
        best = None
        for s in suppliers:
            price = it["unit_cost"] * s["price_index"] * (1.03 if it["category"] == "festive" and s["channel"] == "api" else 1)
            eff = price * (1 - 0.0004 * s["credit_days"]) * (1 + 0.01 * s["delivery_days"])
            q = {"sku": it["sku"], "supplier": s["id"], "supplier_name": s["name"], "unit_price": round(price, 2), "effective": eff}
            quotes.append(q)
            if best is None or eff < best["effective"]:
                best = q
        line = {**it, "unit_price": best["unit_price"], "line_total": round(best["unit_price"] * it["qty"], 2)}
        alloc.setdefault(best["supplier"], []).append(line)
    total = round(sum(li["line_total"] for lines in alloc.values() for li in lines), 2)
    return {"allocation": alloc, "quotes": quotes, "total": total,
            "suppliers": {s["id"]: s["name"] for s in suppliers}}


async def plan_restock(mid: str, festival: str, days: int) -> dict[str, Any]:
    items = forecast(mid, festival, days)
    publish(AGENT, "decide", f"Demand forecast: {len(items)} SKUs to restock",
            ", ".join(f"{i['name_local']}×{i['qty']}" for i in items[:6]), data={"items": items})
    alloc = quote_and_allocate(items)
    publish(AGENT, "decide", f"Quotes from {len(alloc['suppliers'])} suppliers → best mix {inr(alloc['total'])}",
            " · ".join(f"{alloc['suppliers'][sid]}: {len(lines)} items" for sid, lines in alloc["allocation"].items()))
    po_ids = []
    for sid, lines in alloc["allocation"].items():
        po_ids.append(db.x("INSERT INTO purchase_orders(merchant_id, supplier_id, items, total, status, created, quotes) VALUES (?,?,?,?,?,?,?)",
                           (mid, sid, db.dumps(lines), round(sum(l["line_total"] for l in lines), 2), "draft", now_iso(),
                            db.dumps([q for q in alloc["quotes"] if q["supplier"] == sid]))))
    await memory.remember(memory.dataset_for(mid),
                          f"Bazaar drafted {len(po_ids)} purchase orders worth {inr(alloc['total'])} for {festival} restock.",
                          agent=AGENT, edges=[("Bazaar", "Agent", "DRAFTED_PO", f"{festival} restock", "PurchaseOrder")], quiet=True)
    return {"items": items, **alloc, "po_ids": po_ids}


async def place_draft_pos(mid: str, *, funded_by_offer: int | None = None) -> list[dict[str, Any]]:
    m = merchant(mid)
    placed = []
    for po in db.q("SELECT p.*, s.name sname, s.phone sphone, s.channel FROM purchase_orders p JOIN suppliers s ON s.id=p.supplier_id "
                   "WHERE p.merchant_id=? AND p.status='draft'", (mid,)):
        db.x("UPDATE purchase_orders SET status='placed' WHERE id=?", (po["id"],))
        lines = db.loads(po["items"], [])
        await n8n.trigger("bazaar-po", {"po_id": po["id"], "supplier": po["sname"], "supplier_phone": po["sphone"],
                                        "channel": po["channel"], "merchant": m["shop"], "items": lines, "total": po["total"],
                                        "advance_via": "Paytm Collect", "funded_by_offer": funded_by_offer},
                          agent=AGENT, title=f"PO #{po['id']} → {po['sname']} ({inr(po['total'])})")
        placed.append({"po_id": po["id"], "supplier": po["sname"], "total": po["total"]})
    if placed:
        await memory.remember(memory.dataset_for(mid), f"Bazaar placed {len(placed)} POs totalling {inr(sum(p['total'] for p in placed))}.",
                              agent=AGENT, edges=[("Bazaar", "Agent", "PLACED_PO", p["supplier"], "Supplier") for p in placed])
    return placed
