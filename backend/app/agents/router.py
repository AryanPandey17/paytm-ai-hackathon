"""Router: every inbound WhatsApp message (text or transcribed voice) lands here and is sent to the right agent."""
from __future__ import annotations

import re
from typing import Any

from .. import db, llm
from ..config import settings
from ..events import publish
from ..services import n8n
from . import approvals, capital, grower, pulse
from .base import inr, merchant_by_phone

MERCHANT_INTENTS = "udhaar_recovery, stock_concern, cash_need, weekly_brief, sales_query, accept_offer, other"


def _rules_merchant_intents(text: str) -> dict[str, Any]:
    t = text.lower()
    intents: list[dict[str, Any]] = []
    if re.search(r"udhaar|udhar|उधार|baaki|बाकी|pending|dena hai", t):
        amt = re.search(r"(\d[\d,]{2,})", t)
        name = re.search(r"([a-zऀ-ॿ]+)\s*(ji|जी)", t)
        intents.append({"type": "udhaar_recovery", "customer": name.group(1) if name else None,
                        "amount": float(amt.group(1).replace(",", "")) if amt else None})
    if re.search(r"stock|स्टॉक|maal|माल|diwali|दिवाली|festival|tyohar|त्योहार|khatam|kam hai|कम", t):
        fest = re.search(r"(diwali|दिवाली|holi|christmas|eid)", t)
        intents.append({"type": "stock_concern", "festival": ("Diwali" if fest and fest.group(1) in ("diwali", "दिवाली") else (fest.group(1).title() if fest else None))})
    if re.search(r"paisa|paise|पैसे|loan|udhar chahiye|tangi|तंगी|cash|capital", t) and not any(i["type"] == "stock_concern" for i in intents):
        intents.append({"type": "cash_need"})
    if re.search(r"brief|report|hisaab|हिसाब|summary|kaisa raha|कैसा", t):
        intents.append({"type": "weekly_brief"})
    m = re.search(r"\b(haan|accept|yes)\s*#?(\d+)", t)
    if m:
        intents.append({"type": "accept_offer", "offer_id": int(m.group(2))})
    if not intents:
        intents.append({"type": "other"})
    return {"intents": intents, "language": "hi-IN"}


async def handle_inbound(phone: str, text: str, *, source: str = "whatsapp", voice: bool = False) -> dict[str, Any]:
    if phone == settings.demo_ops_phone:
        m = re.search(r"(approve|reject|haan|nahi|yes|no)\s*#?(\d+)", text.lower())
        if m:
            n8n.log_message(phone, "in", "Ops", text, via=source)
            res = await approvals.decide(int(m.group(2)), "approved" if m.group(1) in ("approve", "haan", "yes") else "rejected", by=f"ops ({source})")
            return {"handled_by": "approvals", **res}
        if re.search(r"plan|aaj|today|status", text.lower()):
            from . import commander
            n8n.log_message(phone, "in", "Ops", text, via=source)
            res = await commander.daily_plan()
            return {"handled_by": "commander", "plan": res["plan"]}
    m = merchant_by_phone(phone)
    if not m:
        return {"handled_by": "pulse", **(await pulse.handle_customer(phone, text))}

    n8n.log_message(phone, "in", m["name"], text, kind="voice" if voice else "text", via=source)
    publish("router", "trigger", f"{'🎙️ Voice note' if voice else '💬 Message'} from {m['name']}", text,
            partner="sarvam" if voice else "n8n")
    parsed, provider = await llm.chat_json(
        f"Extract all intents from a kirana merchant's message (Hindi/Hinglish/English). Allowed types: {MERCHANT_INTENTS}. "
        "Return {\"intents\": [{\"type\": str, \"customer\": str|null, \"amount\": number|null, \"festival\": str|null, \"offer_id\": number|null}], "
        "\"language\": \"hi-IN|en-IN|mr-IN|...\"}. A message can contain several intents.",
        text, fallback=lambda: _rules_merchant_intents(text), agent="router")
    intents = [i for i in parsed.get("intents", []) if isinstance(i, dict)] or _rules_merchant_intents(text)["intents"]
    publish("router", "understand", f"{len(intents)} intent(s): " + ", ".join(i.get("type", "?") for i in intents),
            f"via {provider}", partner="sarvam" if provider == "sarvam" else "llm", data={"intents": intents})

    summary: list[str] = []
    results: dict[str, Any] = {}
    for it in intents:
        t = it.get("type")
        if t == "udhaar_recovery":
            r = await grower.recover_udhaar(m["id"], it.get("customer"), it.get("amount"), force=True)
            results["udhaar"] = r
            summary.append(f"✅ {r['customer']} ko {inr(r['amount'])} ka Paytm payment link bhej diya" if r.get("ok")
                           else "⚠️ Udhaar entry nahi mili - naam dobara bataiye")
        elif t in ("stock_concern", "cash_need"):
            fp = await grower.festival_prep(m["id"], it.get("festival"))
            results["festival"] = {k: v for k, v in fp.items() if k != "plan"} | {"total": fp["plan"]["total"], "items": fp["plan"]["items"]}
            top = ", ".join(i["name_local"] for i in fp["plan"]["items"][:4])
            summary.append(f"📦 {fp['festival']} ({fp['days']} din) ke liye {len(fp['plan']['items'])} items ka order ready: {top}… total {inr(fp['plan']['total'])}")
            if fp["gap"] > 0:
                cr = await capital.evaluate(m["id"], fp["gap"], f"{fp['festival']} restock ({inr(fp['plan']['total'])})")
                results["capital"] = cr
                if cr.get("ok"):
                    summary.append(f"💰 {inr(cr['offer']['amount'])} working capital " +
                                   ("approval ke liye bheja - 2 min mein offer aayega" if cr["status"] == "awaiting_approval" else "offer bhej diya"))
        elif t == "weekly_brief":
            b = await grower.weekly_brief(m["id"])
            results["brief"] = b
            summary.append("🎧 Is hafte ka voice brief bhej diya")
        elif t == "accept_offer" and it.get("offer_id"):
            r = await capital.accept(int(it["offer_id"]))
            results["accept"] = r
            if not r.get("ok"):
                summary.append(f"⚠️ Offer #{it['offer_id']} accept nahi ho paya: {r.get('reason')}")
            continue
        elif t == "sales_query":
            from .base import sales_stats
            s = sales_stats(m["id"])
            summary.append(f"📊 Is hafte bikri {inr(s['last7'])} ({s['wow_pct']:+.0f}% vs pichhla hafta), UPI {round(s['upi_share']*100)}%")
    if summary:
        reply = f"{m['name'].split()[0]} ji, kaam ho gaya 👇\n" + "\n".join(summary)
        await n8n.send_whatsapp(phone, reply, agent="router", sender="CommerceOS", title="Summary reply → merchant")
    elif not results:
        reply = "Ji, bataiye kya madad karun? Udhaar, stock, bikri ya loan - kuch bhi bolo 🙂"
        await n8n.send_whatsapp(phone, reply, agent="router", sender="CommerceOS")
    else:
        reply = ""
    return {"handled_by": "merchant", "intents": intents, "results": results, "reply": reply, "llm_provider": provider}
