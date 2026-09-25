"""Hunter: zero-PII profiling -> fit score -> Thompson-sampling outreach -> qualified handoff to Onboarder."""
from __future__ import annotations

import random
from typing import Any

from .. import db, llm
from ..events import publish
from ..services import memory
from .base import now_iso

AGENT = "hunter"
CATEGORY_PRIOR = {"kirana": 0.85, "pharmacy": 0.8, "food": 0.75, "dairy": 0.8, "fruits-veg": 0.6, "meat": 0.65,
                  "retail": 0.6, "services": 0.5}
# Beta(alpha, beta) priors per channel - updated from responses (contextual bandit in production)
ARMS = {"whatsapp_voice": [6, 4], "field_visit": [8, 5], "ivr_call": [3, 6], "whatsapp_text": [4, 5]}
QUALIFY = 0.6


def fit_score(lead: dict[str, Any]) -> float:
    """Only non-personal signals: category, footfall, digital readiness, source quality."""
    foot = min(lead["footfall"] / 300, 1)
    src = {"referral": 0.9, "ondc-seller-list": 0.8, "soundbox-lookalike": 0.75, "field-survey": 0.6, "gmaps-scrape": 0.5}.get(lead["source"], 0.5)
    return round(0.3 * CATEGORY_PRIOR.get(lead["category"], 0.5) + 0.25 * foot + 0.3 * lead["digital_readiness"] + 0.15 * src, 2)


def choose_channel() -> str:
    return max(ARMS, key=lambda k: random.betavariate(*ARMS[k]))


async def run(limit: int = 6) -> list[dict[str, Any]]:
    publish(AGENT, "trigger", "Hunter sweep", "Zero-PII profiling of new leads")
    out = []
    for lead in db.q("SELECT * FROM leads WHERE status='new' LIMIT ?", (limit,)):
        s = fit_score(lead)
        ch = choose_channel()
        status = "qualified" if s >= QUALIFY else "nurture"
        db.x("UPDATE leads SET fit_score=?, channel=?, status=? WHERE id=?", (s, ch, status, lead["id"]))
        publish(AGENT, "decide", f"{lead['shop']} · fit {s} · {status}", f"{lead['category']} · footfall {lead['footfall']} · channel {ch}")
        if status == "qualified":
            ARMS[ch][0] += 1
            res = await llm.chat(
                [{"role": "system", "content": "Write a 2-line friendly outreach message (Hinglish, Roman script) inviting a small shop owner "
                  "to try Paytm Soundbox + free business insights. No personal data."},
                 {"role": "user", "content": f"Shop category {lead['category']} in {lead['area']}, Mumbai."}],
                rules=lambda: f"Namaste! {lead['area']} ki dukaanon ke liye Paytm Soundbox + free AI business partner. 5 min mein shuru karein? 🙂",
                agent=AGENT)
            case_id = f"OB{random.randint(100, 999)}"
            tracks = {k: "in_progress" for k in ("docs", "compliance", "banking", "hardware", "legal")}
            db.x("INSERT INTO onboarding_cases VALUES (?,?,?,?,?,?,?,?,?)",
                 (case_id, lead["id"], lead["name"], lead["shop"], db.dumps(tracks), None, "in_progress",
                  None, now_iso()))
            publish(AGENT, "act", f"Handoff → Onboarder ({case_id})", f"Context packet: category, area, language {lead['language']}, channel {ch}",
                    data={"outreach": res.text})
            await memory.remember("portfolio", f"Hunter qualified {lead['shop']} ({lead['category']}, {lead['area']}) with fit {s}; outreach via {ch}.",
                                  agent=AGENT, edges=[("Hunter", "Agent", "QUALIFIED", lead["shop"], "Lead")], quiet=True)
        else:
            ARMS[ch][1] += 1
        out.append({"lead": lead["shop"], "fit": s, "status": status, "channel": ch})
    return out
