"""Capital: continuous underwriting -> proactive offer -> (human approval if above threshold) -> one-tap accept -> disbursal."""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .. import db, llm
from ..config import settings
from ..events import publish
from ..services import memory, n8n, rails
from . import approvals, bazaar
from .base import inr, merchant, now_iso, open_udhaar, sales_stats

AGENT = "capital"


def underwrite(mid: str) -> dict[str, Any]:
    m = merchant(mid)
    s = sales_stats(mid)
    u_open = sum(u["amount"] for u in open_udhaar(mid))
    repaid = db.one("SELECT COUNT(*) c FROM offers WHERE merchant_id=? AND status IN ('repaid','repaying')", (mid,))["c"]
    # Transparent scorecard (bandits/causal models replace this in production)
    score = 0.45
    score += min(0.2, s["upi_share"] * 0.25)            # digital footprint
    score += 0.15 * max(0, 1 - s["volatility"])          # stable daily sales
    score += 0.1 if s["wow_pct"] > -10 else -0.05        # not declining
    score -= min(0.1, u_open / max(s["last30"], 1))      # udhaar exposure
    score += 0.05 * min(repaid, 2)
    score -= 0.3 if m["risk_flag"] else 0
    score = round(max(0.05, min(0.97, score)), 2)
    limit = round(min(s["last30"] * 0.6, 150000) * score / 0.5, -3)
    return {"score": score, "limit": max(limit, 0), "avg_daily": s["avg_daily"], "last30": s["last30"],
            "upi_share": s["upi_share"], "volatility": s["volatility"], "udhaar_open": u_open, "risk_flag": bool(m["risk_flag"])}


async def evaluate(mid: str, need: float, reason: str) -> dict[str, Any]:
    m = merchant(mid)
    publish(AGENT, "trigger", f"Liquidity signal from Grower: {inr(need)}", reason)
    await memory.recall(memory.dataset_for(mid), f"{m['shop']} credit history repayment liquidity gap", agent=AGENT)
    uw = underwrite(mid)
    publish(AGENT, "decide", f"Underwritten · score {uw['score']} · limit {inr(uw['limit'])}",
            f"30d sales {inr(uw['last30'])} · UPI {round(uw['upi_share']*100)}% · volatility {uw['volatility']:.2f}", data=uw)
    db.x("UPDATE merchants SET credit_limit=? WHERE id=?", (uw["limit"], mid))
    amount = min(math.ceil(need / 5000) * 5000, uw["limit"])
    if amount < 5000 or uw["score"] < 0.4:
        publish(AGENT, "decide", "No offer: below credit policy", f"score {uw['score']}", status="warn")
        return {"ok": False, "underwriting": uw}
    tenure = 90
    fee = round(amount * 0.02 * (tenure / 30) * (1.2 - uw["score"]), -1)
    daily_pct = round(min(15, (amount + fee) / tenure / max(uw["avg_daily"] * uw["upi_share"], 1) * 100), 1)
    offer_id = db.x("INSERT INTO offers(merchant_id, amount, tenure_days, daily_repay_pct, fee, status, reason, score, created) VALUES (?,?,?,?,?,?,?,?,?)",
                    (mid, amount, tenure, daily_pct, fee, "pending", reason, uw["score"], now_iso()))
    offer = db.one("SELECT * FROM offers WHERE id=?", (offer_id,))
    await memory.remember(memory.dataset_for(mid), f"Capital prepared offer #{offer_id}: {inr(amount)} for {tenure} days, {daily_pct}% of daily UPI sales, reason: {reason}.",
                          agent=AGENT, edges=[("Ramesh Kirana Stores", "Merchant", "OFFERED", f"Loan offer #{offer_id}", "Offer")], quiet=True)

    needs_human = amount > settings.capital_approval_threshold or uw["risk_flag"]
    if needs_human:
        why = f"amount {inr(amount)} > threshold {inr(settings.capital_approval_threshold)}" if amount > settings.capital_approval_threshold else "merchant risk flag"
        db.x("UPDATE offers SET status='awaiting_approval' WHERE id=?", (offer_id,))
        await approvals.create("capital_offer", str(offer_id), AGENT,
                               f"Approve {inr(amount)} working-capital offer for {m['shop']}?",
                               f"{reason}. Score {uw['score']}, limit {inr(uw['limit'])}, repay {daily_pct}% of daily UPI for {tenure} days. Escalated because {why}.",
                               amount, {"merchant_id": mid, "offer_id": offer_id}, workflow="capital-offer")
        return {"ok": True, "offer": offer, "status": "awaiting_approval", "underwriting": uw}
    await send_offer(offer_id)
    return {"ok": True, "offer": db.one("SELECT * FROM offers WHERE id=?", (offer_id,)), "status": "offered", "underwriting": uw}


async def send_offer(offer_id: int) -> None:
    o = db.one("SELECT * FROM offers WHERE id=?", (offer_id,))
    m = merchant(o["merchant_id"])
    daily_example = round(10000 * o["daily_repay_pct"] / 100)

    def rules_msg() -> str:
        return (f"🎉 {m['name'].split()[0]} ji, {o['reason']} ke liye aapke liye {inr(o['amount'])} ka Paytm working-capital offer ready hai.\n"
                f"• Koi EMI nahi, sirf roz ki UPI bikri ka {o['daily_repay_pct']}% (₹10,000 bikri par {inr(daily_example)})\n"
                f"• {o['tenure_days']} din · processing fee {inr(o['fee'])}\n"
                f"Accept karne ke liye reply karein: *HAAN {o['id']}*")

    res = await llm.chat(
        [{"role": "system", "content": "Write a short, clear WhatsApp loan offer in Hinglish (Roman script) for a kirana owner. "
          "Mention: amount, why now, repayment as % of daily UPI sales with a ₹10,000 example, tenure, fee. "
          "End with exactly this line: Accept karne ke liye reply karein: *HAAN {id}*. Max 6 lines."},
         {"role": "user", "content": db.dumps({**o, "owner": m["name"], "shop": m["shop"], "example_repay_on_10000": daily_example})}],
        rules=rules_msg, agent=AGENT, temperature=0.4)
    text = res.text if f"HAAN {o['id']}" in res.text else rules_msg()
    db.x("UPDATE offers SET status='offered' WHERE id=?", (offer_id,))
    await n8n.send_whatsapp(m["phone"], text, agent=AGENT, sender="Paytm Capital", kind="loan_offer",
                            meta={"offer_id": offer_id, "amount": o["amount"]}, title=f"One-tap offer → {m['name']} ({inr(o['amount'])})")


async def accept(offer_id: int) -> dict[str, Any]:
    o = db.one("SELECT * FROM offers WHERE id=?", (offer_id,))
    if not o or o["status"] != "offered":
        return {"ok": False, "reason": f"offer not in offered state ({o and o['status']})"}
    m = merchant(o["merchant_id"])
    d = rails.disburse(o["merchant_id"], o["amount"])
    db.x("UPDATE offers SET status='disbursed', decided=? WHERE id=?", (now_iso(), offer_id))
    publish(AGENT, "act", f"💰 Disbursed {inr(o['amount'])} to {m['shop']}", f"Txn {d['txn_id']} · instant", partner="paytm", data=d)
    await n8n.send_whatsapp(m["phone"], f"✅ {inr(o['amount'])} aapke account mein bhej diye gaye (Txn {d['txn_id']}). "
                            f"Repayment roz ki UPI bikri se automatically hoga. Diwali ka stock order bhi place kar diya hai 🪔",
                            agent=AGENT, sender="Paytm Capital")
    await memory.remember(memory.dataset_for(o["merchant_id"]), f"{m['name']} accepted offer #{offer_id} ({inr(o['amount'])}) with one tap; disbursed instantly on {datetime.now():%d %b %Y}.",
                          agent=AGENT, edges=[(m["name"], "Person", "ACCEPTED", f"Loan offer #{offer_id}", "Offer")])
    placed = await bazaar.place_draft_pos(o["merchant_id"], funded_by_offer=offer_id)
    return {"ok": True, "disbursal": d, "pos": placed}


async def on_approval(approval: dict[str, Any], decision: str) -> None:
    offer_id = int(approval["ref_id"])
    if decision == "approved":
        await send_offer(offer_id)
    else:
        db.x("UPDATE offers SET status='declined' WHERE id=?", (offer_id,))
        publish(AGENT, "decide", f"Offer #{offer_id} declined by human", approval.get("decided_by") or "", status="warn")
