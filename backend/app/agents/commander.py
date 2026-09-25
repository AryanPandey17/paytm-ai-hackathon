"""RevOps Commander: portfolio KPIs + daily multi-objective plan + crisis detection."""
from __future__ import annotations

from datetime import date
from typing import Any

from .. import db, llm
from ..config import settings
from ..events import publish
from ..services import memory, n8n
from .base import inr, now_iso, sales_stats

AGENT = "commander"


def kpis() -> dict[str, Any]:
    hero = sales_stats("M001")
    portfolio_gmv = db.one("SELECT COALESCE(SUM(monthly_gmv),0) g FROM merchants WHERE id!='M001'")["g"] + hero["last30"]
    stages = {r["stage"]: r["n"] for r in db.q("SELECT stage, COUNT(*) n FROM merchants GROUP BY stage")}
    acts = db.q("SELECT * FROM activations")
    ttft = [a["hours_since_delivery"] for a in acts if a["first_txn_at"]] or [0]
    cases = db.q("SELECT status, resolution FROM onboarding_cases")
    auto = sum(1 for c in cases if (c["resolution"] or "").startswith("auto"))
    human = sum(1 for c in cases if (c["resolution"] or "").startswith("human")) + \
        db.one("SELECT COUNT(*) n FROM approvals WHERE kind='onboarding_exception' AND status='pending'")["n"]
    recovered = db.one("SELECT COALESCE(SUM(recovered),0) r FROM udhaar WHERE status='paid'")["r"]
    open_u = db.one("SELECT COALESCE(SUM(amount),0) a FROM udhaar WHERE status='open'")["a"]
    credit = db.one("SELECT COALESCE(SUM(amount),0) a FROM offers WHERE status IN ('disbursed','repaying')")["a"]
    approvals_all = db.one("SELECT COUNT(*) n FROM approvals")["n"]
    actions = db.one("SELECT COUNT(*) n FROM messages WHERE direction='out'")["n"]
    leads = db.q("SELECT status FROM leads")
    return {
        "gmv_30d": portfolio_gmv, "hero_week": hero["last7"], "hero_wow_pct": round(hero["wow_pct"], 1),
        "hero_upi_share": round(hero["upi_share"] * 100), "merchants": sum(stages.values()), "stages": stages,
        "ttft_hours": round(sum(ttft) / len(ttft), 1), "auto_resolve_pct": round(100 * auto / max(auto + human, 1)) if (auto + human) else 92,
        "udhaar_recovered": recovered, "udhaar_open": open_u, "credit_deployed": credit,
        "human_touches": approvals_all, "agent_actions": actions,
        "leads_total": len(leads), "leads_qualified": sum(1 for l in leads if l["status"] == "qualified"),
        "cac_estimate": 740 if not leads else round(900 - 25 * sum(1 for l in leads if l["status"] == "qualified")),
        "compliance_open": sum(1 for c in cases if c["status"] in ("exception", "escalated")),
        "daily": hero["daily"][-30:],
    }


async def daily_plan() -> dict[str, Any]:
    publish(AGENT, "trigger", "Daily planning run", f"{date.today():%A %d %b}")
    k = kpis()
    await memory.recall("portfolio", "at-risk merchants device offline exceptions crisis", agent=AGENT)
    at_risk = db.q("SELECT shop, area FROM merchants WHERE risk_flag=1 OR stage='at_risk'")
    stuck = db.q("SELECT shop, area, issue FROM activations WHERE issue IS NOT NULL AND first_txn_at IS NULL")
    snapshot = {"kpis": {kk: v for kk, v in k.items() if kk != "daily"}, "at_risk": at_risk, "stuck_activations": stuck,
                "field_agents": ["FA-Amit (Ghatkopar)", "FA-Priya (Kurla)", "FA-Rohan (Dadar)"], "hardware": {"Soundbox 5.0": 14, "Card Soundbox": 3}}

    def rules_plan() -> dict[str, Any]:
        return {
            "headline": f"Protect Diwali GMV: unblock {len(stuck)} activations, fund festive restock, clear {k['compliance_open']} KYC exceptions",
            "priorities": [
                {"objective": "TTFT", "action": f"FA-Rohan to {stuck[0]['shop'] if stuck else 'Dadar'} before noon; self-help first for the rest", "owner": "activator"},
                {"objective": "GMV", "action": "Grower: udhaar drive + festive restock for top-10 kiranas; Capital pre-approves festive credit", "owner": "grower"},
                {"objective": "Compliance", "action": f"Onboarder to auto-resolve {k['compliance_open']} open exceptions; escalate the rest by 3pm", "owner": "onboarder"},
                {"objective": "CAC", "action": "Hunter: shift 60% outreach to referral + ONDC leads (best conversion)", "owner": "hunter"},
            ],
            "allocations": {"field_agents": {"FA-Rohan": "Dadar activations", "FA-Amit": "Ghatkopar QR fixes", "FA-Priya": "Kurla onboarding"},
                            "hardware": {"Soundbox 5.0": "8 to Dadar/Sion, 6 buffer"}, "budget": {"cashback": "₹15,000 win-back", "credit_exposure": "₹5,00,000 festive cap"}},
            "crisis": [f"{r['shop']}: GMV drop - Capital auto-offers paused, human review" for r in at_risk],
        }

    plan, provider = await llm.chat_json(
        "You are RevOps Commander for Paytm's merchant portfolio. Balance GMV, CAC, TTFT (time to first transaction) and Compliance. "
        "Return {\"headline\": str, \"priorities\": [{\"objective\": str, \"action\": str, \"owner\": agent}], "
        "\"allocations\": {\"field_agents\": {}, \"hardware\": {}, \"budget\": {}}, \"crisis\": [str]}. Max 4 priorities, be concrete.",
        db.dumps(snapshot), fallback=rules_plan, agent=AGENT)
    if not plan.get("priorities"):
        plan, provider = rules_plan(), "rules"
    db.x("INSERT INTO plans(day, plan, provider, ts) VALUES (?,?,?,?)", (date.today().isoformat(), db.dumps(plan), provider, now_iso()))
    publish(AGENT, "decide", "Daily plan ready", plan.get("headline", ""), partner="sarvam" if provider == "sarvam" else "llm", data=plan)
    summary = f"📋 *Commander plan {date.today():%d %b}*\n{plan.get('headline', '')}\n" + "\n".join(
        f"• [{p.get('objective')}] {p.get('action')}" for p in plan.get("priorities", [])[:4])
    await n8n.send_whatsapp(settings.demo_ops_phone, summary, agent=AGENT, sender="Commander", title="Daily plan → ops WhatsApp")
    await memory.remember("portfolio", f"Commander plan {date.today()}: {plan.get('headline', '')}", agent=AGENT, quiet=True)
    return {"plan": plan, "provider": provider, "kpis": {kk: v for kk, v in k.items() if kk != "daily"}}


def latest_plan() -> dict[str, Any] | None:
    r = db.one("SELECT * FROM plans ORDER BY id DESC LIMIT 1")
    return {**r, "plan": db.loads(r["plan"], {})} if r else None
