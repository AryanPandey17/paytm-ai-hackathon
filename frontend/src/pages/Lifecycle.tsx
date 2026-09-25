import { useState } from "react";
import { Check, Crosshair, Loader2, Rocket, UserCheck, X, AlertTriangle, Building2 } from "lucide-react";
import { api, inr, useData } from "../api";
import { Card, StatusPill } from "../components/ui";

type Pipeline = {
  leads: { id: string; name: string; shop: string; category: string; area: string; source: string; footfall: number; digital_readiness: number; fit_score: number | null; status: string; channel: string | null }[];
  onboarding: { id: string; merchant_name: string; shop: string; tracks: Record<string, string>; exception: { track: string; type: string; detail: string } | null; status: string; resolution: string | null }[];
  activations: { id: string; merchant_name: string; shop: string; area: string; device: string; stage: string; field_agent: string | null; issue: string | null; hours_since_delivery: number; first_txn_at: string | null }[];
  portfolio: { id: string; shop: string; name: string; category: string; area: string; stage: string; monthly_gmv: number; language: string }[];
};

const TRACKS = ["docs", "compliance", "banking", "hardware", "legal"];
const ACT_STAGES = ["allocated", "dispatched", "delivered", "first_txn"];

function TrackDot({ s }: { s: string }) {
  if (s === "done") return <span className="grid h-6 w-6 place-items-center rounded-full bg-green-500 text-white"><Check size={13} strokeWidth={3} /></span>;
  if (s === "exception") return <span className="grid h-6 w-6 place-items-center rounded-full bg-red-500 text-white"><X size={13} strokeWidth={3} /></span>;
  return <span className="grid h-6 w-6 place-items-center rounded-full bg-sky-100 text-sky-600"><Loader2 size={13} className="animate-spin" /></span>;
}

export default function Lifecycle() {
  const { data: p, reload } = useData<Pipeline>("/api/pipeline");
  const [busy, setBusy] = useState<string | null>(null);
  const act = async (k: string, url: string) => { setBusy(k); try { await api.post(url); } finally { setBusy(null); reload(); } };
  if (!p) return <div className="h-96 animate-pulse rounded-3xl bg-white" />;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 2xl:grid-cols-2">
        <Card title="1 · Hunter: find & qualify (zero-PII)" icon={<Crosshair size={17} className="text-violet-600" />} pad={false}
          action={<button className="btn-primary !py-1.5 !text-xs" disabled={!!busy} onClick={() => act("h", "/api/agents/hunter/run")}>{busy === "h" ? "Scoring…" : "Run Hunter"}</button>}>
          <div className="max-h-[420px] overflow-y-auto">
            <table className="tbl w-full">
              <thead><tr><th>Lead</th><th>Signals</th><th>Fit</th><th>Channel</th><th>Status</th></tr></thead>
              <tbody>
                {p.leads.map((l) => (
                  <tr key={l.id}>
                    <td><div className="font-medium">{l.shop}</div><div className="text-[11px] text-muted">{l.category} · {l.area}</div></td>
                    <td className="text-[12px] text-muted">{l.footfall}/day · digital {Math.round(l.digital_readiness * 100)}% · {l.source}</td>
                    <td>{l.fit_score != null ? (
                      <div className="flex items-center gap-2"><div className="h-1.5 w-14 rounded-full bg-canvas"><div className="h-1.5 rounded-full bg-violet-500" style={{ width: `${l.fit_score * 100}%` }} /></div><span className="text-xs font-semibold tabular-nums">{l.fit_score}</span></div>
                    ) : <span className="text-muted">–</span>}</td>
                    <td className="text-[12px]">{l.channel?.replace(/_/g, " ") ?? "–"}</td>
                    <td><StatusPill s={l.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="2 · Onboarder: 5 parallel tracks" icon={<UserCheck size={17} className="text-cyan-700" />}
          action={<button className="btn-primary !py-1.5 !text-xs" disabled={!!busy} onClick={() => act("o", "/api/agents/onboarder/resolve")}>{busy === "o" ? "Resolving…" : "Resolve exceptions"}</button>}>
          <div className="mb-2 grid grid-cols-[1fr_repeat(5,44px)_110px] gap-1 px-1 text-center text-[10px] font-semibold uppercase tracking-wider text-muted">
            <span className="text-left">Merchant</span>{["Docs", "KYC", "Bank", "Device", "Legal"].map((t) => <span key={t}>{t}</span>)}<span>Status</span>
          </div>
          <div className="max-h-[380px] space-y-1.5 overflow-y-auto">
            {p.onboarding.map((c) => (
              <div key={c.id} className="rounded-xl border border-line px-2 py-2">
                <div className="grid grid-cols-[1fr_repeat(5,44px)_110px] items-center gap-1">
                  <div className="min-w-0"><div className="truncate text-[13px] font-semibold">{c.shop}</div><div className="truncate text-[11px] text-muted">{c.merchant_name} · {c.id}</div></div>
                  {TRACKS.map((t) => <span key={t} className="grid place-items-center"><TrackDot s={c.tracks[t] ?? "in_progress"} /></span>)}
                  <span className="text-center"><StatusPill s={c.status} /></span>
                </div>
                {c.exception && c.status !== "complete" && (
                  <div className="mt-1.5 flex items-start gap-1.5 rounded-lg bg-red-50 px-2 py-1.5 text-[11.5px] text-red-700"><AlertTriangle size={13} className="mt-0.5 shrink-0" />{c.exception.detail}</div>
                )}
                {c.resolution && <div className="mt-1 px-1 text-[11.5px] text-muted">↳ {c.resolution}</div>}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card title="3 · Activator: guarantee the first transaction" icon={<Rocket size={17} className="text-orange-600" />}
        action={<button className="btn-primary !py-1.5 !text-xs" disabled={!!busy} onClick={() => act("a", "/api/agents/activator/intervene")}>{busy === "a" ? "Intervening…" : "Intervene on stuck merchants"}</button>}>
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-5">
          {p.activations.map((a) => {
            const idx = ACT_STAGES.indexOf(a.stage);
            return (
              <div key={a.id} className={`rounded-2xl border p-3.5 ${a.issue ? "border-amber-300 bg-amber-50/40" : "border-line"}`}>
                <div className="text-[13px] font-bold text-navy">{a.shop}</div>
                <div className="text-[11px] text-muted">{a.device} · {a.area}</div>
                <div className="mt-3 flex items-center gap-1">
                  {ACT_STAGES.map((s, i) => <div key={s} className={`h-1.5 flex-1 rounded-full ${i <= idx ? (s === "first_txn" ? "bg-good" : "bg-sky") : "bg-canvas"}`} />)}
                </div>
                <div className="mt-1.5 flex items-center justify-between text-[11px]"><StatusPill s={a.stage} />{a.field_agent && <span className="text-muted">{a.field_agent}</span>}</div>
                {a.issue && <div className="mt-2 text-[11.5px] font-medium text-amber-700">⚠ {a.issue.replace(/_/g, " ")} · {a.hours_since_delivery}h</div>}
                {!a.first_txn_at && <button className="btn-ghost mt-2 w-full justify-center !py-1 !text-[11px]" onClick={() => act(a.id, `/api/activations/${a.id}/first-txn`)}>Mark first txn</button>}
              </div>
            );
          })}
        </div>
      </Card>

      <Card title="Portfolio (Commander view)" icon={<Building2 size={17} className="text-navy" />} pad={false}>
        <table className="tbl w-full">
          <thead><tr><th>Merchant</th><th>Category</th><th>Area</th><th>Language</th><th>Monthly GMV</th><th>Stage</th></tr></thead>
          <tbody>
            {p.portfolio.map((m) => (
              <tr key={m.id}>
                <td><div className="font-medium">{m.shop}</div><div className="text-[11px] text-muted">{m.name}</div></td>
                <td className="text-muted">{m.category}</td><td className="text-muted">{m.area}</td><td className="text-muted">{m.language}</td>
                <td className="tabular-nums">{m.monthly_gmv ? inr(m.monthly_gmv) : "–"}</td><td><StatusPill s={m.stage} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
