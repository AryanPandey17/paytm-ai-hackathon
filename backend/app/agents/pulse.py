"""Pulse: the invisible salesperson. Customer concierge on WhatsApp, next-best-action, failed-payment recovery."""
from __future__ import annotations

import random
import re
import time
from typing import Any

from .. import db, llm
from ..events import publish
from ..services import memory, n8n, rails
from .base import customer_by_phone, inr, match_products, merchant, now_iso

AGENT = "pulse"
HERO = "M001"

INTENT_RULES = [
    ("udhaar_balance", r"udhaar|udhar|उधार|baaki|baki|बाकी|kitna dena|hisaab|hisab"),
    ("stock_query", r"hai kya|है क्या|available|milega|मिलेगा|stock|hai\?|है\?"),
    ("pre_order", r"order|bhej|भेज|chahiye|चाहिए|rakh (do|dena)|pack kar|deliver"),
    ("complaint", r"kharab|खराब|shikayat|शिकायत|complain|expired|galat|गलत|refund"),
    ("payment_issue", r"payment fail|paisa kat|पैसा कट|deduct|failed|pending payment"),
    ("greeting", r"^(hi|hello|namaste|नमस्ते|hey)\b"),
]


def _rules_intent(text: str) -> dict[str, Any]:
    t = text.lower()
    for name, pat in INTENT_RULES:
        if re.search(pat, t):
            return {"intent": name}
    return {"intent": "stock_query" if match_products(HERO, t) else "other"}


async def handle_customer(phone: str, text: str, *, mid: str = HERO) -> dict[str, Any]:
    m = merchant(mid)
    c = customer_by_phone(phone)
    name = c["name"] if c else "Guest"
    publish(AGENT, "trigger", f"Customer message · {name}", text)
    parsed, provider = await llm.chat_json(
        "Classify a kirana customer's WhatsApp message. intents: stock_query, udhaar_balance, pre_order, complaint, "
        "payment_issue, greeting, other. Return {\"intent\": str, \"items\": [str], \"language\": \"hi-IN|en-IN|mr-IN|...\"}.",
        text, fallback=lambda: _rules_intent(text), agent=AGENT)
    intent = parsed.get("intent") or _rules_intent(text)["intent"]
    publish(AGENT, "understand", f"Intent: {intent}", f"via {provider}", partner="sarvam" if provider == "sarvam" else "llm")
    if c:
        await memory.recall(memory.dataset_for(mid), f"{c['name']} household purchases preferences", agent=AGENT)

    items_text = " ".join(parsed.get("items") or []) + " " + text
    reply = ""
    if intent == "stock_query":
        prods = match_products(mid, items_text)
        if not prods:
            reply = f"Ji, bataiye kaunsa saaman chahiye? Hum {m['shop']} se check karke batate hain 🙏"
        else:
            parts = []
            for p in prods:
                if p["stock"] > 0:
                    parts.append(f"✅ {p['name']} available hai ({p['stock']} pcs) - {inr(p['price'])}")
                else:
                    parts.append(f"❌ {p['name']} abhi khatam hai, 2 din mein aa jayega")
            reply = "\n".join(parts) + "\nPack karke rakh dein? Reply *HAAN* 🙂"
            if c and c["segment"] == "loyal":
                reply += f"\n🎁 Aapke loyalty points: {int(c['spend_90d'] // 100)}"
    elif intent == "udhaar_balance":
        if c:
            u = db.one("SELECT COALESCE(SUM(amount),0) a FROM udhaar WHERE customer_id=? AND status='open'", (c["id"],))["a"]
            if u:
                link = rails.collect_link(mid, c["id"], u, "Udhaar")
                nick = c["name"].split("(")[-1].rstrip(")") if "(" in c["name"] else c["name"].split()[0] + " ji"
                reply = f"{nick}, aapka {inr(u)} baaki hai. Yahan se pay karein: {link['link']}"
            else:
                reply = "Aapka koi udhaar baaki nahi hai 🙏"
        else:
            reply = "Aapka number humare records mein nahi mila. Dukaan par aake check kar lijiye 🙏"
    elif intent == "pre_order":
        prods = match_products(mid, items_text)
        names = ", ".join(p["name"] for p in prods) or "aapka saaman"
        reply = f"Theek hai! {names} pack karke rakh rahe hain. Aate hi le jaiye, ya Paytm se pay kar dein 🙂"
        await n8n.send_whatsapp(m["phone"], f"🛒 Pre-order from {name}: {names}", agent=AGENT, sender="Pulse")
    elif intent == "complaint":
        reply = "Maaf kijiye 🙏 humne aapki shikayat Ramesh ji tak pahuncha di hai, woh jaldi aapse baat karenge."
        await n8n.send_whatsapp(m["phone"], f"⚠️ Complaint from {name}: “{text}”", agent=AGENT, sender="Pulse")
    elif intent == "payment_issue":
        reply = "Chinta mat kijiye - agar paisa kata hai to 48 ghante mein automatic wapas aa jayega. Naya link bhej rahe hain."
    else:
        res = await llm.chat(
            [{"role": "system", "content": f"You are the friendly WhatsApp assistant of {m['shop']}, a kirana in Mumbai. "
              "Reply in short Hinglish (Roman script), max 2 lines."}, {"role": "user", "content": text}],
            rules=lambda: f"Namaste! {m['shop']} mein aapka swagat hai 🙏 Saaman, udhaar ya order - kuch bhi poochiye.", agent=AGENT)
        reply = res.text

    n8n.log_message(phone, "in", name, text)
    await n8n.send_whatsapp(phone, reply, agent=AGENT, sender=m["shop"], title=f"Concierge reply → {name}")
    await memory.remember(memory.dataset_for(mid), f"{name} asked “{text[:80]}” ({intent}); Pulse replied on WhatsApp.",
                          agent=AGENT, edges=[(name, "Customer", "ASKED", intent, "Intent")], quiet=True)
    return {"intent": intent, "reply": reply, "customer": name}


async def recover_failed_payment(mid: str = HERO, customer_id: str | None = None) -> dict[str, Any]:
    t0 = time.perf_counter()
    c = db.one("SELECT * FROM customers WHERE id=?", (customer_id,)) if customer_id else \
        random.choice(db.q("SELECT * FROM customers WHERE merchant_id=? AND segment IN ('regular','loyal')", (mid,)))
    amount = random.choice([240, 385, 512, 760])
    db.x("INSERT INTO transactions(merchant_id, customer_id, amount, ts, method, status) VALUES (?,?,?,?,?,?)",
         (mid, c["id"], amount, now_iso(), "upi", "failed"))
    publish(AGENT, "trigger", f"UPI payment failed · {c['name']} · {inr(amount)}", "Bank timeout (U30)", status="warn")
    link = rails.collect_link(mid, c["id"], amount, "Retry")
    channel = "whatsapp" if c["segment"] in ("loyal", "regular") else "soundbox+sms"
    await n8n.send_whatsapp(c["phone"], f"Aapka {inr(amount)} ka payment fail ho gaya (bank timeout). Ek tap mein dobara karein: {link['upi_intent']}",
                            agent=AGENT, sender="Paytm", kind="payment_request", meta={"link": link},
                            title=f"Payment recovery via {channel}")
    ms = int((time.perf_counter() - t0) * 1000)
    publish(AGENT, "act", f"Recovery sent in {ms} ms", f"Channel: {channel} · UPI intent", partner="paytm")
    await memory.remember(memory.dataset_for(mid), f"Pulse recovered a failed UPI payment of {inr(amount)} from {c['name']} via {channel} in {ms} ms.",
                          agent=AGENT, quiet=True)
    return {"customer": c["name"], "amount": amount, "latency_ms": ms, "channel": channel}
