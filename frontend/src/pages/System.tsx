import { useState } from "react";
import { Bot, Cpu, Mic, Network, RefreshCw, Workflow, CheckCircle2, CircleDashed, AlertCircle } from "lucide-react";
import { api, useData } from "../api";
import { Card } from "../components/ui";

type Health = {
  llm: { name: string; model: string; configured: boolean; state: string; calls: number; failures: number; last_error: string; latency_ms: number }[];
  sarvam: { configured: boolean; stt_calls: number; tts_calls: number; translate_calls: number; last_error: string };
  n8n: { configured: boolean; base_url: string | null; calls: number; ok: number; simulated: number; errors: number; last_error: string };
  memory: { requested: string; active: string; error: string; events: number; edges: number; writes: number; reads: number; cognee_writes: number; cognee_reads: number };
  phones: Record<string, string>;
};

function State({ ok, warn, label }: { ok: boolean; warn?: boolean; label: string }) {
  const Icon = ok ? CheckCircle2 : warn ? AlertCircle : CircleDashed;
  return <span className={`chip ${ok ? "bg-green-50 text-green-700" : warn ? "bg-amber-50 text-amber-700" : "bg-slate-100 text-slate-500"}`}><Icon size={12} />{label}</span>;
}

export default function System() {
  const { data: h, reload } = useData<Health>("/api/health");
  const [prompt, setPrompt] = useState("Ek line mein batao: kirana dukaan ke liye UPI kyun zaroori hai?");
  const [out, setOut] = useState<{ text: string; provider: string; model: string; fallback_used: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  if (!h) return <div className="h-96 animate-pulse rounded-3xl bg-white" />;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
        <div className="card p-4"><div className="flex items-center justify-between"><span className="label">Sarvam · voice + Indic LLM</span><Mic size={16} className="text-orange-500" /></div>
          <div className="mt-2"><State ok={h.sarvam.configured} label={h.sarvam.configured ? "key set" : "no key → browser voice / fallbacks"} /></div>
          <div className="mt-2 text-[12px] text-muted">STT {h.sarvam.stt_calls} · TTS {h.sarvam.tts_calls} · translate {h.sarvam.translate_calls}</div>
          {h.sarvam.last_error && <div className="mt-1 truncate text-[11px] text-bad">{h.sarvam.last_error}</div>}</div>
        <div className="card p-4"><div className="flex items-center justify-between"><span className="label">Cognee · memory graph</span><Network size={16} className="text-violet-600" /></div>
          <div className="mt-2"><State ok={h.memory.active === "cognee"} warn={h.memory.requested === "cognee" && h.memory.active !== "cognee"} label={`active: ${h.memory.active}`} /></div>
          <div className="mt-2 text-[12px] text-muted">{h.memory.events} memories · {h.memory.edges} edges · {h.memory.cognee_writes} Cognee writes</div>
          {h.memory.error && <div className="mt-1 truncate text-[11px] text-bad">{h.memory.error}</div>}</div>
        <div className="card p-4"><div className="flex items-center justify-between"><span className="label">n8n · actions + approvals</span><Workflow size={16} className="text-rose-600" /></div>
          <div className="mt-2"><State ok={h.n8n.configured && h.n8n.errors === 0} warn={h.n8n.configured && h.n8n.errors > 0} label={h.n8n.configured ? h.n8n.base_url ?? "live" : "simulated"} /></div>
          <div className="mt-2 text-[12px] text-muted">{h.n8n.ok} live · {h.n8n.simulated} simulated · {h.n8n.errors} errors</div>
          {h.n8n.last_error && <div className="mt-1 truncate text-[11px] text-bad">{h.n8n.last_error}</div>}</div>
        <div className="card p-4"><div className="flex items-center justify-between"><span className="label">WhatsApp demo phones</span><Bot size={16} className="text-green-600" /></div>
          <div className="mt-2 space-y-0.5 text-[12px]">{Object.entries(h.phones).map(([k, v]) => <div key={k} className="flex justify-between"><span className="capitalize text-muted">{k}</span><code>+{v}</code></div>)}</div></div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Card title="LLM fallback chain" icon={<Cpu size={17} className="text-sky" />}
          action={<button className="btn-ghost !py-1.5 !text-xs" onClick={async () => { await api.post("/api/llm/reset"); reload(); }}><RefreshCw size={13} />Reset cooldowns</button>}>
          <p className="mb-3 text-[12.5px] text-muted">Tried top to bottom. A provider is skipped when its key is missing and put on cooldown when tokens/credits run out (402/429/quota), the key is rejected, it errors or it times out. <b>rules</b> is the offline safety net.</p>
          <div className="space-y-2">
            {h.llm.map((p, i) => (
              <div key={p.name} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2.5">
                <span className="grid h-7 w-7 place-items-center rounded-lg bg-navy text-xs font-bold text-white">{i + 1}</span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-bold capitalize text-navy">{p.name}</div>
                  <div className="truncate text-[11.5px] text-muted">{p.model}{p.last_error ? ` · ${p.last_error}` : ""}</div>
                </div>
                <span className="text-[11.5px] text-muted tabular-nums">{p.calls} calls · {p.failures} fails{p.latency_ms ? ` · ${p.latency_ms}ms` : ""}</span>
                <State ok={p.state === "ready"} warn={p.state.startsWith("cooldown") || p.state === "disabled"} label={p.state} />
              </div>
            ))}
          </div>
        </Card>
        <Card title="Try the chain" icon={<Bot size={17} className="text-sky" />}>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} className="w-full rounded-xl border border-line p-3 text-sm outline-none focus:border-sky" />
          <button className="btn-primary mt-2" disabled={busy} onClick={async () => { setBusy(true); try { setOut(await api.post("/api/llm/test", { prompt })); reload(); } finally { setBusy(false); } }}>
            {busy ? "Thinking…" : "Send"}
          </button>
          {out && (
            <div className="mt-3 rounded-xl bg-canvas p-3 text-[13px]">
              <div className="label mb-1">answered by {out.provider} · {out.model}{out.fallback_used ? " · after fallback" : ""}</div>
              <div className="whitespace-pre-line">{out.text}</div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
