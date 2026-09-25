"""Onboarder: 5 parallel tracks + LLM/rule exception resolver + human escalation below confidence threshold."""
from __future__ import annotations

import re
from typing import Any

from .. import db, llm
from ..config import settings
from ..events import publish
from ..services import memory, n8n
from . import approvals

AGENT = "onboarder"


def _norm(s: str) -> list[str]:
    return [t for t in re.sub(r"[^a-z ]", " ", s.lower()).split() if t]


def _rule_confidence(exc: dict[str, Any]) -> tuple[float, str]:
    t = exc["type"]
    if t == "name_mismatch":
        names = re.findall(r"'([^']+)'", exc["detail"])
        if len(names) == 2:
            a, b = _norm(names[0]), _norm(names[1])
            short, long_ = (a, b) if len(a) <= len(b) else (b, a)
            matched = sum(1 for tok in short if any(t2 == tok or (len(tok) == 1 and t2.startswith(tok)) for t2 in long_))
            conf = matched / max(len(short), 1)
            return (0.93 if conf == 1 else 0.5 * conf), "Initial expands to middle name; first and last names match"
    if t == "unreadable_document":
        return 0.9, "Ask merchant to re-upload a clearer photo over WhatsApp with capture tips"
    if t == "penny_drop_failed":
        return 0.35, "Bank reports dormant/frozen account - cannot auto-fix, needs a different account or bank visit"
    return 0.4, "Unknown exception type"


async def resolve(case_id: str) -> dict[str, Any]:
    case = db.one("SELECT * FROM onboarding_cases WHERE id=?", (case_id,))
    if not case or case["status"] != "exception":
        return {"ok": False, "reason": "no open exception"}
    exc = db.loads(case["exception"], {})
    publish(AGENT, "trigger", f"Exception on {case['shop']} · {exc['track']}", exc["detail"])
    rule_conf, rule_note = _rule_confidence(exc)
    parsed, provider = await llm.chat_json(
        "You are a KYC exception resolver for Paytm merchant onboarding. Given an exception, decide if it can be safely "
        "auto-resolved. Return {\"resolution\": str, \"confidence\": 0-1, \"action\": \"auto_fix|request_reupload|escalate\"}.",
        db.dumps({"exception": exc, "rule_hint": rule_note}),
        fallback=lambda: {"resolution": rule_note, "confidence": rule_conf,
                          "action": "escalate" if rule_conf < settings.resolver_confidence_threshold else
                          ("request_reupload" if exc["type"] == "unreadable_document" else "auto_fix")},
        agent=AGENT)
    llm_conf = float(parsed.get("confidence", rule_conf) or rule_conf)
    conf = round(min(rule_conf, llm_conf) if exc["type"] == "penny_drop_failed" else (rule_conf + llm_conf) / 2, 2)
    publish(AGENT, "decide", f"Resolver confidence {conf} ({'rules+LLM' if provider != 'rules' else 'rules'})",
            parsed.get("resolution", rule_note)[:200], partner="sarvam" if provider == "sarvam" else "llm")

    tracks = db.loads(case["tracks"], {})
    if conf >= settings.resolver_confidence_threshold:
        if exc["type"] == "unreadable_document":
            await n8n.send_whatsapp(f"91970000{case_id[-2:]}88",
                                    f"Namaste {case['merchant_name'].split()[0]} ji, aapka dukaan certificate photo saaf nahi aaya. "
                                    "Kripya roshni mein, seedha upar se photo khinch kar yahin bhej dijiye 📸",
                                    agent=AGENT, sender="Paytm Onboarding", title=f"Re-upload request → {case['merchant_name']}")
        tracks[exc["track"]] = "done"
        status = "complete" if all(v == "done" for v in tracks.values()) else "in_progress"
        db.x("UPDATE onboarding_cases SET status=?, tracks=?, resolution=? WHERE id=?",
             (status, db.dumps(tracks), f"auto ({conf}): {parsed.get('resolution', rule_note)}", case_id))
        publish(AGENT, "act", f"Auto-resolved {case['shop']}", parsed.get("resolution", rule_note)[:160])
        await memory.remember("portfolio", f"Onboarder auto-resolved {exc['type']} for {case['shop']} (confidence {conf}).",
                              agent=AGENT, edges=[("Onboarder", "Agent", "AUTO_RESOLVED", case["shop"], "Merchant")])
        return {"ok": True, "auto": True, "confidence": conf}

    db.x("UPDATE onboarding_cases SET status='escalated' WHERE id=?", (case_id,))
    await approvals.create("onboarding_exception", case_id, AGENT, f"Onboarding exception: {case['shop']} ({exc['track']})",
                           f"{exc['detail']}. Resolver confidence {conf} < {settings.resolver_confidence_threshold}. Suggested: {parsed.get('resolution', rule_note)}",
                           None, {"case_id": case_id, "exception": exc}, workflow="onboarding-escalation")
    return {"ok": True, "auto": False, "confidence": conf}


async def resolve_all() -> list[dict[str, Any]]:
    return [await resolve(c["id"]) for c in db.q("SELECT id FROM onboarding_cases WHERE status='exception'")]


async def on_approval(approval: dict[str, Any], decision: str) -> None:
    case = db.one("SELECT * FROM onboarding_cases WHERE id=?", (approval["ref_id"],))
    if not case:
        return
    if decision == "approved":
        tracks = db.loads(case["tracks"], {})
        exc = db.loads(case["exception"], {})
        tracks[exc.get("track", "compliance")] = "done"
        db.x("UPDATE onboarding_cases SET status='complete', tracks=?, resolution=? WHERE id=?",
             (db.dumps(tracks), f"human-approved by {approval.get('decided_by')}", case["id"]))
        publish(AGENT, "act", f"{case['shop']} onboarding complete", "Handed to Activator with hardware request")
    else:
        db.x("UPDATE onboarding_cases SET status='blocked', resolution=? WHERE id=?", ("human rejected", case["id"]))
