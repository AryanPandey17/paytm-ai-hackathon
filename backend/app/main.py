"""Paytm Commerce OS - FastAPI entrypoint.

Run:  uv run uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, events, llm, seed
from .agents import activator, approvals, capital, commander, grower, hunter, onboarder, pulse, router
from .agents.base import sales_stats
from .config import ROOT, settings
from .events import publish
from .services import memory, n8n, sarvam

HERO = seed.HERO
DEMO_TRANSCRIPT = "Sharma ji ka 1200 udhaar pending hai, aur Diwali ka stock kam hai. Paise ki bhi thodi tangi hai."


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not db.one("SELECT COUNT(*) n FROM merchants")["n"]:
        seed.seed()
        await seed.seed_memory()
    Path(settings.audio_cache_dir).mkdir(parents=True, exist_ok=True)
    publish("system", "system", "Commerce OS online",
            f"LLM chain: {' → '.join(llm.ORDER)} · memory: {memory.backend()} · n8n: {'live' if n8n.configured() else 'simulated'}")
    yield


app = FastAPI(title="Paytm Commerce OS", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ models
class TextIn(BaseModel):
    from_: str | None = None
    phone: str | None = None
    text: str

    model_config = {"populate_by_name": True}


class WhatsAppIn(BaseModel):
    """Payload from n8n WF1 (whatsapp-inbound)."""
    from_number: str
    type: str = "text"  # text | audio | button | interactive
    text: str | None = None
    button_payload: str | None = None
    audio_base64: str | None = None
    mime_type: str | None = "audio/ogg"


class Decision(BaseModel):
    decision: str
    by: str = "dashboard"


class CallbackIn(BaseModel):
    approval_id: int | None = None
    decision: str | None = None
    by: str = "ops (whatsapp)"
    event: str | None = None
    data: dict[str, Any] | None = None


class EvalIn(BaseModel):
    amount: float = 30000
    reason: str = "Working capital top-up"


class PromptIn(BaseModel):
    prompt: str


class SearchIn(BaseModel):
    query: str
    dataset: str | None = None


# ------------------------------------------------------------------ system
@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "llm": llm.status(), "sarvam": sarvam.status(), "n8n": n8n.status(), "memory": memory.status(),
            "guardrails": {"capital_approval_threshold": settings.capital_approval_threshold,
                           "resolver_confidence_threshold": settings.resolver_confidence_threshold,
                           "nudge_cooldown_days": settings.nudge_cooldown_days},
            "phones": {"merchant": settings.demo_merchant_phone, "customer": settings.demo_customer_phone, "ops": settings.demo_ops_phone}}


@app.get("/api/events")
async def sse():
    return StreamingResponse(events.stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/events/history")
def event_history(limit: int = 120):
    return events.history(limit)


@app.post("/api/llm/reset")
def llm_reset(name: str | None = None):
    llm.reset(name)
    return llm.status()


@app.post("/api/llm/test")
async def llm_test(body: PromptIn):
    res = await llm.chat([{"role": "user", "content": body.prompt}], rules=lambda: "(offline rules provider) OK", agent="system")
    return {"text": res.text, "provider": res.provider, "model": res.model, "fallback_used": res.fallback_used}


# ------------------------------------------------------------------ data
@app.get("/api/kpis")
def get_kpis():
    return commander.kpis()


@app.get("/api/merchants")
def merchants():
    return db.q("SELECT * FROM merchants ORDER BY id")


@app.get("/api/merchant/{mid}")
def merchant_detail(mid: str):
    m = db.one("SELECT * FROM merchants WHERE id=?", (mid,))
    if not m:
        raise HTTPException(404)
    s = sales_stats(mid)
    return {
        "merchant": m, "stats": {k: v for k, v in s.items() if k != "daily"}, "daily": s["daily"],
        "customers": db.q("SELECT c.*, h.name household FROM customers c LEFT JOIN households h ON h.id=c.household_id WHERE c.merchant_id=? ORDER BY spend_90d DESC", (mid,)),
        "udhaar": db.q("SELECT u.*, c.name, c.segment FROM udhaar u JOIN customers c ON c.id=u.customer_id WHERE u.merchant_id=? ORDER BY u.status, u.amount DESC", (mid,)),
        "products": db.q("SELECT * FROM products WHERE merchant_id=? ORDER BY (stock*1.0/reorder_level)", (mid,)),
        "offers": db.q("SELECT * FROM offers WHERE merchant_id=? ORDER BY id DESC", (mid,)),
        "purchase_orders": [{**p, "items": db.loads(p["items"], [])} for p in
                            db.q("SELECT p.*, s.name supplier FROM purchase_orders p JOIN suppliers s ON s.id=p.supplier_id WHERE merchant_id=? ORDER BY p.id DESC", (mid,))],
        "suppliers": db.q("SELECT * FROM suppliers"),
    }


@app.get("/api/pipeline")
def pipeline():
    return {
        "leads": db.q("SELECT * FROM leads ORDER BY COALESCE(fit_score,0) DESC, id"),
        "onboarding": [{**c, "tracks": db.loads(c["tracks"], {}), "exception": db.loads(c["exception"])}
                       for c in db.q("SELECT * FROM onboarding_cases ORDER BY created DESC")],
        "activations": db.q("SELECT * FROM activations ORDER BY id"),
        "portfolio": db.q("SELECT * FROM merchants ORDER BY monthly_gmv DESC"),
    }


@app.get("/api/approvals")
def list_approvals():
    return [{**a, "payload": db.loads(a["payload"], {})} for a in approvals.pending()]


@app.post("/api/approvals/{aid}")
async def decide_approval(aid: int, body: Decision):
    return await approvals.decide(aid, body.decision, by=body.by)


@app.get("/api/threads")
def threads():
    people = [{"phone": settings.demo_merchant_phone, "name": "Ramesh Gupta", "role": "merchant", "subtitle": "Ramesh Kirana Stores"},
              {"phone": settings.demo_ops_phone, "name": "Ops Approver", "role": "ops", "subtitle": "Paytm credit & KYC desk"}]
    for c in db.q("SELECT id, name, phone, segment FROM customers WHERE merchant_id=? ORDER BY CASE id WHEN 'C01' THEN 0 WHEN 'C04' THEN 1 ELSE 2 END, spend_90d DESC LIMIT 8", (HERO,)):
        people.append({"phone": c["phone"], "name": c["name"], "role": "customer", "subtitle": f"{c['segment']} customer"})
    for p in people:
        last = db.one("SELECT text, ts FROM messages WHERE phone=? ORDER BY id DESC LIMIT 1", (p["phone"],))
        p["last"] = last
        p["count"] = db.one("SELECT COUNT(*) n FROM messages WHERE phone=?", (p["phone"],))["n"]
    return people


@app.get("/api/messages")
def messages(phone: str):
    return [{**m, "meta": db.loads(m["meta"], {})} for m in db.q("SELECT * FROM messages WHERE phone=? ORDER BY id", (phone,))]


# ------------------------------------------------------------------ inbound (WhatsApp via n8n, or the simulator)
@app.post("/api/ingest/text")
async def ingest_text(body: TextIn):
    phone = body.phone or body.from_ or settings.demo_merchant_phone
    return await router.handle_inbound(phone, body.text, source="simulator")


@app.post("/api/ingest/voice")
async def ingest_voice(file: UploadFile | None = File(None), from_number: str = Form(settings.demo_merchant_phone),
                       transcript_hint: str | None = Form(None), language: str = Form("unknown"), source: str = Form("simulator")):
    text, how = await _transcribe(await file.read() if file else None, file.filename if file else "voice.ogg",
                                  file.content_type if file else "audio/ogg", transcript_hint, language)
    return {"transcript": text, "stt": how, **(await router.handle_inbound(from_number, text, source=source, voice=True))}


@app.post("/api/ingest/whatsapp")
async def ingest_whatsapp(body: WhatsAppIn, x_commerceos_secret: str | None = Header(None)):
    _check_secret(x_commerceos_secret)
    if body.type == "audio" and body.audio_base64:
        text, how = await _transcribe(base64.b64decode(body.audio_base64), "voice.ogg", body.mime_type or "audio/ogg", None, "unknown")
        res = await router.handle_inbound(body.from_number, text, source="whatsapp", voice=True)
        return {"transcript": text, "stt": how, **res}
    text = body.button_payload or body.text or ""
    return await router.handle_inbound(body.from_number, text, source="whatsapp")


async def _transcribe(audio: bytes | None, name: str, ctype: str, hint: str | None, language: str) -> tuple[str, str]:
    if audio and sarvam.configured():
        try:
            r = await sarvam.speech_to_text(audio, name, ctype, language)
            publish("router", "understand", "🎙️ Voice note transcribed", r["transcript"], partner="sarvam",
                    data={"language": r["language_code"], "model": settings.sarvam_stt_model})
            return r["transcript"], "sarvam"
        except Exception as e:  # noqa: BLE001
            publish("router", "system", "Sarvam STT failed → fallback transcript", str(e)[:140], partner="sarvam", status="warn")
    text = hint or DEMO_TRANSCRIPT
    publish("router", "understand", "🎙️ Voice note (demo transcript)", text,
            partner="sarvam", data={"note": "Set SARVAM_API_KEY and send real audio for live STT"})
    return text, "demo-transcript"


@app.post("/api/callbacks/n8n")
async def n8n_callback(body: CallbackIn, x_commerceos_secret: str | None = Header(None)):
    _check_secret(x_commerceos_secret)
    if body.approval_id and body.decision:
        return await approvals.decide(body.approval_id, body.decision, by=body.by)
    publish("system", "act", f"n8n callback: {body.event or 'event'}", str(body.data or "")[:160], partner="n8n")
    return {"ok": True}


def _check_secret(secret: str | None) -> None:
    if n8n.configured() and secret != settings.n8n_webhook_secret:
        raise HTTPException(401, "bad X-CommerceOS-Secret")


# ------------------------------------------------------------------ agent actions (dashboard buttons)
@app.post("/api/agents/grower/run")
async def grower_run(mid: str = HERO):
    return await grower.run_loops(mid)


@app.post("/api/agents/grower/brief")
async def grower_brief(mid: str = HERO, send: bool = True):
    return await grower.weekly_brief(mid, send=send)


@app.post("/api/agents/grower/festival")
async def grower_festival(mid: str = HERO):
    fp = await grower.festival_prep(mid)
    if fp["gap"] > 0:
        fp["capital"] = await capital.evaluate(mid, fp["gap"], f"{fp['festival']} restock")
    return fp


@app.post("/api/udhaar/{uid}/nudge")
async def udhaar_nudge(uid: int):
    u = db.one("SELECT u.*, c.name FROM udhaar u JOIN customers c ON c.id=u.customer_id WHERE u.id=?", (uid,))
    if not u:
        raise HTTPException(404)
    return await grower.recover_udhaar(u["merchant_id"], u["name"], force=True)


@app.post("/api/udhaar/{uid}/pay")
async def udhaar_pay(uid: int):
    return await grower.mark_udhaar_paid(uid)


@app.post("/api/agents/capital/evaluate")
async def capital_eval(body: EvalIn, mid: str = HERO):
    return await capital.evaluate(mid, body.amount, body.reason)


@app.post("/api/offers/{oid}/accept")
async def offer_accept(oid: int):
    o = db.one("SELECT * FROM offers WHERE id=?", (oid,))
    if not o:
        raise HTTPException(404)
    m = db.one("SELECT * FROM merchants WHERE id=?", (o["merchant_id"],))
    n8n.log_message(m["phone"], "in", m["name"], f"HAAN {oid}", via="simulator")
    return await capital.accept(oid)


@app.post("/api/agents/pulse/failed-payment")
async def pulse_failed(mid: str = HERO):
    return await pulse.recover_failed_payment(mid)


@app.post("/api/agents/onboarder/resolve")
async def onboarder_resolve(case_id: str | None = None):
    return await onboarder.resolve(case_id) if case_id else await onboarder.resolve_all()


@app.post("/api/agents/activator/intervene")
async def activator_intervene():
    return await activator.intervene()


@app.post("/api/activations/{aid}/first-txn")
async def activation_first(aid: str):
    return await activator.first_transaction(aid)


@app.post("/api/agents/hunter/run")
async def hunter_run():
    return await hunter.run()


@app.post("/api/agents/commander/plan")
async def commander_plan():
    return await commander.daily_plan()


@app.get("/api/commander/plan")
def commander_latest():
    return commander.latest_plan()


# ------------------------------------------------------------------ memory
@app.get("/api/memory/graph")
def memory_graph(dataset: str = f"merchant_{HERO}", limit: int = 160):
    return memory.graph(dataset, limit)


@app.get("/api/memory/recent")
def memory_recent(dataset: str | None = None, limit: int = 30):
    return memory.recent(dataset, limit)


@app.post("/api/memory/search")
async def memory_search(body: SearchIn):
    return await memory.recall(body.dataset or memory.dataset_for(HERO), body.query, agent="system")


@app.post("/api/memory/cognify")
async def memory_cognify():
    return await memory.cognify()


# ------------------------------------------------------------------ demo
_demo_task: asyncio.Task | None = None


@app.post("/api/demo/reset")
async def demo_reset():
    seed.seed()
    await seed.seed_memory()
    llm.reset()
    publish("system", "system", "Demo data reset", "Fresh synthetic merchant, customers and ledger")
    return {"ok": True}


@app.post("/api/demo/run")
async def demo_run():
    global _demo_task
    if _demo_task and not _demo_task.done():
        return {"ok": False, "reason": "demo already running"}
    _demo_task = asyncio.create_task(_hero_demo())
    return {"ok": True}


async def _hero_demo() -> None:
    step = lambda n, t: publish("demo", "system", f"Demo step {n}", t)  # noqa: E731
    try:
        step(1, "Ramesh sends a Hindi voice note on WhatsApp")
        sample = ROOT / "demo" / "ramesh_voice_note.ogg"
        audio = sample.read_bytes() if sample.exists() else None
        text, _ = await _transcribe(audio, sample.name, "audio/ogg", DEMO_TRANSCRIPT, "hi-IN")
        await router.handle_inbound(settings.demo_merchant_phone, text, source="whatsapp", voice=True)
        await asyncio.sleep(3)
        step(2, "A customer asks the shop's WhatsApp: “atta hai kya?”")
        await router.handle_inbound("919800000499", "Bhaiya atta hai kya? Aur 2 kilo cheeni bhi chahiye", source="whatsapp")
        await asyncio.sleep(3)
        step(3, "A UPI payment fails at the counter → Pulse recovers it")
        await pulse.recover_failed_payment(HERO, "C09")
        await asyncio.sleep(3)
        step(4, "Grower sends the weekly Hindi voice brief")
        await grower.weekly_brief(HERO)
        await asyncio.sleep(2)
        step(5, "Commander publishes the daily plan")
        await commander.daily_plan()
        publish("demo", "system", "Demo complete ✅", "Approve the pending credit offer, then accept it as Ramesh (HAAN <id>)")
    except Exception as e:  # noqa: BLE001
        publish("demo", "system", "Demo error", repr(e)[:200], status="error")
        raise


# ------------------------------------------------------------------ static
@app.get("/audio/{name}")
def audio(name: str):
    p = Path(settings.audio_cache_dir) / Path(name).name
    if not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="audio/wav")


_dist = ROOT / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="ui")
