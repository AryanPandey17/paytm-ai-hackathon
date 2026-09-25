"""Grower: the merchant's business partner. Udhaar recovery, win-back, festival prep, weekly voice brief."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .. import db, llm
from ..config import settings
from ..events import publish
from ..services import memory, n8n, rails, sarvam
from . import bazaar
from .base import inr, match_customer, merchant, next_festival, now_iso, open_udhaar, sales_stats

AGENT = "grower"


# ---------------------------------------------------------------- udhaar recovery
async def recover_udhaar(mid: str, customer_hint: str | None = None, amount_hint: float | None = None,
                         *, force: bool = False) -> dict[str, Any]:
    m = merchant(mid)
    pool = open_udhaar(mid)
    entry = None
    if customer_hint:
        c = match_customer(mid, customer_hint, pool)
        entry = next((u for u in pool if c and u["customer_id"] == c["id"]), None)
    if entry is None and amount_hint:
        entry = next((u for u in pool if abs(u["amount"] - amount_hint) < 1), None)
    if entry is None:
        publish(AGENT, "decide", "No matching open udhaar", f"hint={customer_hint!r} amount={amount_hint}", status="warn")
        return {"ok": False, "reason": "no matching udhaar entry"}

    # Guardrail: nudge frequency cap
    if entry["last_nudged"] and not force:
        last = datetime.fromisoformat(entry["last_nudged"])
        if datetime.now() - last < timedelta(days=settings.nudge_cooldown_days):
            publish(AGENT, "decide", f"Skip nudge for {entry['name']}", f"Nudged {entry['last_nudged']}; cap is 1 per {settings.nudge_cooldown_days} days")
            return {"ok": False, "reason": "cooldown", "customer": entry["name"]}

    age = (datetime.now() - datetime.fromisoformat(entry["created"])).days
    publish(AGENT, "decide", f"Udhaar recovery: {entry['name']} owes {inr(entry['amount'])}", f"{age} days old · segment {entry['segment']}")
    ctx = await memory.recall(memory.dataset_for(mid), f"{entry['name']} udhaar payment behaviour reminder preference", agent=AGENT)

    tone = "polite" if entry["segment"] in ("loyal", "regular") or age < 30 else "firm-but-respectful"
    link = rails.collect_link(mid, entry["customer_id"], entry["amount"], "Udhaar")
    first = entry["name"].split("(")[-1].rstrip(")") if "(" in entry["name"] else entry["name"].split()[0] + " ji"

    def rules_msg() -> str:
        return (f"Namaste {first} 🙏\n{m['shop']} se yaad dilana tha - aapka {inr(entry['amount'])} ka udhaar baaki hai. "
                f"Aap is link se turant Paytm par pay kar sakte hain: {link['link']}\nDhanyavaad! - {m['name']}")

    res = await llm.chat(
        [{"role": "system", "content":
          "You write short WhatsApp payment reminders for an Indian kirana shop, in friendly Hinglish (Roman script). "
          "Max 3 lines, respectful, no threats, include the exact amount and the payment link exactly once, sign with the shop owner's name."},
         {"role": "user", "content":
          f"Shop: {m['shop']} (owner {m['name']}). Customer: {first}. Amount: {inr(entry['amount'])}. Days pending: {age}. "
          f"Tone: {tone}. What we know: {ctx['answer'][:500]}. Payment link: {link['link']}"}],
        rules=rules_msg, agent=AGENT, temperature=0.5)
    text = res.text if link["link"] in res.text else rules_msg()
    publish(AGENT, "decide", f"Drafted {tone} nudge", text[:180], partner="sarvam" if res.provider == "sarvam" else "llm",
            data={"provider": res.provider})

    await n8n.send_whatsapp(entry["phone"], text, agent=AGENT, sender=m["shop"], kind="payment_request",
                            meta={"udhaar_id": entry["id"], "amount": entry["amount"], "link": link},
                            workflow="udhaar-nudge", title=f"Collect link sent to {entry['name']}",
                            extra={"udhaar_id": entry["id"], "amount": entry["amount"], "collect_link": link["link"],
                                   "customer_name": entry["name"], "merchant_phone": m["phone"]})
    db.x("UPDATE udhaar SET last_nudged=?, nudges=nudges+1 WHERE id=?", (now_iso(), entry["id"]))
    await memory.remember(memory.dataset_for(mid),
                          f"Grower sent a {tone} udhaar reminder to {entry['name']} for {inr(entry['amount'])} on {datetime.now():%d %b %Y} with a Paytm Collect link.",
                          agent=AGENT, edges=[("Grower", "Agent", "NUDGED", entry["name"], "Customer")])
    return {"ok": True, "customer": entry["name"], "amount": entry["amount"], "link": link, "tone": tone, "provider": res.provider}


async def mark_udhaar_paid(udhaar_id: int) -> dict[str, Any]:
    u = db.one("SELECT u.*, c.name, c.phone FROM udhaar u JOIN customers c ON c.id=u.customer_id WHERE u.id=?", (udhaar_id,))
    if not u or u["status"] != "open":
        return {"ok": False}
    db.x("UPDATE udhaar SET status='paid', recovered=amount WHERE id=?", (udhaar_id,))
    db.x("INSERT INTO transactions(merchant_id, customer_id, amount, ts, method, status) VALUES (?,?,?,?,?,?)",
         (u["merchant_id"], u["customer_id"], u["amount"], now_iso(), "upi", "success"))
    m = merchant(u["merchant_id"])
    publish(AGENT, "act", f"💸 {u['name']} paid {inr(u['amount'])}", "Udhaar recovered via Paytm Collect", partner="paytm")
    await n8n.send_whatsapp(u["phone"], f"Dhanyavaad! {inr(u['amount'])} mil gaye. 🙏 - {m['shop']}", agent=AGENT, sender=m["shop"])
    await n8n.send_whatsapp(m["phone"], f"✅ {u['name']} ne {inr(u['amount'])} udhaar chuka diya (Paytm Collect).", agent=AGENT,
                            sender="CommerceOS")
    await memory.remember(memory.dataset_for(u["merchant_id"]),
                          f"{u['name']} paid udhaar of {inr(u['amount'])} after {u['nudges']} reminder(s) on {datetime.now():%d %b %Y}.",
                          agent=AGENT, edges=[(u["name"], "Customer", "PAID", "Ramesh Kirana Stores", "Merchant")])
    return {"ok": True}


# ---------------------------------------------------------------- win-back
async def win_back(mid: str, limit: int = 3) -> list[dict[str, Any]]:
    m = merchant(mid)
    lapsing = db.q("SELECT * FROM customers WHERE merchant_id=? AND churn_risk>0.6 ORDER BY spend_90d DESC LIMIT ?", (mid, limit))
    out = []
    for c in lapsing:
        offer = "₹30 cashback on next Paytm payment above ₹300"
        text = (f"Namaste {c['name'].split()[0]} ji! {m['shop']} mein aapki kami mehsoos ho rahi hai. "
                f"Is hafte aane par {offer}. Diwali ka naya stock bhi aa raha hai 🪔")
        await n8n.send_whatsapp(c["phone"], text, agent=AGENT, sender=m["shop"], kind="offer",
                                title=f"Win-back offer → {c['name']}")
        await memory.remember(memory.dataset_for(mid), f"Grower sent win-back offer ({offer}) to lapsing customer {c['name']}.",
                              agent=AGENT, edges=[("Grower", "Agent", "WIN_BACK", c["name"], "Customer")], quiet=True)
        out.append({"customer": c["name"], "offer": offer})
    publish(AGENT, "decide", f"Win-back campaign: {len(out)} lapsing customers", ", ".join(o["customer"] for o in out))
    return out


# ---------------------------------------------------------------- festival prep -> Bazaar -> Capital
async def festival_prep(mid: str, festival_hint: str | None = None) -> dict[str, Any]:
    fest, days = next_festival()
    if festival_hint and festival_hint.lower() not in fest.lower():
        fest = festival_hint.title()
    publish(AGENT, "decide", f"Festival prep: {fest} in {days} days", "Forecasting demand with Bazaar")
    plan = await bazaar.plan_restock(mid, fest, days)
    stats = sales_stats(mid)
    cash_on_hand = round(stats["avg_daily"] * 1.5, -2)  # proxy: ~1.5 days of sales free as working capital
    gap = max(0.0, plan["total"] - cash_on_hand)
    publish(AGENT, "decide", f"Liquidity gap {inr(gap)}",
            f"Restock needs {inr(plan['total'])}, est. free cash {inr(cash_on_hand)}", data={"gap": gap})
    await memory.remember(memory.dataset_for(mid),
                          f"Before {fest}, Grower estimated a restock bill of {inr(plan['total'])} against about {inr(cash_on_hand)} free cash: liquidity gap {inr(gap)}.",
                          agent=AGENT, edges=[("Ramesh Kirana Stores", "Merchant", "HAS_SIGNAL", "Liquidity gap", "Signal")])
    return {"festival": fest, "days": days, "plan": plan, "cash_on_hand": cash_on_hand, "gap": gap}


# ---------------------------------------------------------------- weekly voice brief
async def weekly_brief(mid: str, *, send: bool = True) -> dict[str, Any]:
    m = merchant(mid)
    s = sales_stats(mid)
    open_u = open_udhaar(mid)
    recovered = db.one("SELECT COALESCE(SUM(recovered),0) r FROM udhaar WHERE merchant_id=? AND status='paid'", (mid,))["r"]
    at_risk = db.q("SELECT name FROM customers WHERE merchant_id=? AND churn_risk>0.6 ORDER BY spend_90d DESC LIMIT 3", (mid,))
    low = db.q("SELECT name, name_local, stock FROM products WHERE merchant_id=? AND stock<=reorder_level ORDER BY festival_multiplier DESC LIMIT 4", (mid,))
    fest, days = next_festival()
    facts = {
        "week_sales": inr(s["last7"]), "change_pct": round(s["wow_pct"], 1), "upi_share_pct": round(s["upi_share"] * 100),
        "open_udhaar": inr(sum(u["amount"] for u in open_u)), "open_udhaar_count": len(open_u), "recovered_total": inr(recovered),
        "at_risk_customers": [a["name"] for a in at_risk], "low_stock": [f"{p['name_local']} ({p['stock']})" for p in low],
        "festival": fest, "days_to_festival": days,
    }

    def rules_brief() -> str:
        return (f"नमस्ते {m['name'].split()[0]} जी! इस हफ्ते आपकी बिक्री {facts['week_sales']} रही, पिछले हफ्ते से {facts['change_pct']} प्रतिशत "
                f"{'ज़्यादा' if facts['change_pct'] >= 0 else 'कम'}। {facts['upi_share_pct']} प्रतिशत पेमेंट Paytm UPI से आए। "
                f"अभी {facts['open_udhaar_count']} ग्राहकों का कुल {facts['open_udhaar']} उधार बाकी है, हमने उन्हें याद दिला दिया है। "
                f"{', '.join(facts['at_risk_customers'][:2])} काफ़ी दिनों से नहीं आए, उन्हें कैशबैक ऑफर भेजा है। "
                f"{facts['festival']} {facts['days_to_festival']} दिन में है — {', '.join(facts['low_stock'][:3])} का स्टॉक कम है, "
                f"ऑर्डर की तैयारी हो चुकी है। अगले हफ्ते: शाम 6 से 9 बजे भीड़ ज़्यादा रहती है, उस समय काउंटर पर एक और हाथ रखें। धन्यवाद!")

    res = await llm.chat(
        [{"role": "system", "content":
          "You are Grower, an AI business partner for an Indian kirana owner. Write a warm spoken weekly brief in simple Hindi "
          "(Devanagari), about 150-180 words (~90 seconds of speech). Structure: greeting, what happened (sales, UPI, udhaar), "
          "customers to watch, stock/festival prep, 1-2 concrete actions for next week. Numbers in words-friendly form. No markdown."},
         {"role": "user", "content": f"Owner: {m['name']}. Shop: {m['shop']}. Facts: {db.dumps(facts)}"}],
        rules=rules_brief, agent=AGENT, temperature=0.6, max_tokens=900)
    text = res.text
    publish(AGENT, "decide", "Weekly voice brief written", text[:200], partner="sarvam" if res.provider == "sarvam" else "llm",
            data={"provider": res.provider})
    tts = await sarvam.text_to_speech(text, m["language"] or "hi-IN")
    publish(AGENT, "act", "Brief voiced", f"TTS via {tts['provider']}", partner="sarvam" if tts["provider"].startswith("sarvam") else None)
    if send:
        audio_url = f"{settings.public_backend_url}{tts['audio_url']}" if tts["audio_url"] else None
        await n8n.send_whatsapp(m["phone"], text, agent=AGENT, sender="CommerceOS", kind="audio",
                                meta={"audio_url": tts["audio_url"], "tts": tts["provider"], "lang": m["language"]},
                                extra={"audio_url": audio_url}, title="Weekly voice brief → Ramesh")
    await memory.remember(memory.dataset_for(mid), f"Weekly brief delivered to {m['name']}: week sales {facts['week_sales']}, open udhaar {facts['open_udhaar']}.",
                          agent=AGENT, quiet=True)
    return {"text": text, "facts": facts, "audio_url": tts["audio_url"], "tts_provider": tts["provider"], "llm_provider": res.provider}


# ---------------------------------------------------------------- loops (dashboard "Run Grower")
async def run_loops(mid: str) -> dict[str, Any]:
    publish(AGENT, "trigger", "Grower loops started", "udhaar · win-back · festival prep")
    nudged = []
    for u in open_udhaar(mid)[:3]:
        r = await recover_udhaar(mid, u["name"])
        if r.get("ok"):
            nudged.append(r["customer"])
    wb = await win_back(mid)
    return {"nudged": nudged, "win_back": wb}
