import { useState } from "react";
import { Bell, Boxes, HandCoins, Headphones, MapPin, PackageCheck, Sparkles, Users, Wallet } from "lucide-react";
import { api, inr, speak, useData } from "../api";
import SalesChart from "../components/SalesChart";
import { Card, Stat, StatusPill } from "../components/ui";

type Detail = {
  merchant: { id: string; name: string; shop: string; area: string; city: string; language: string; stage: string; credit_limit: number };
  stats: { last7: number; wow_pct: number; last30: number; avg_daily: number; upi_share: number };
  daily: { day: string; total: number; upi: number; txns: number }[];
  customers: { id: string; name: string; household: string; segment: string; visits_90d: number; spend_90d: number; churn_risk: number; last_visit: string }[];
  udhaar: { id: number; name: string; amount: number; created: string; status: string; nudges: number; last_nudged: string | null; segment: string }[];
  products: { sku: string; name: string; name_local: string; stock: number; reorder_level: number; price: number; category: string; festival_multiplier: number }[];
  offers: { id: number; amount: number; status: string; daily_repay_pct: number; tenure_days: number; reason: string }[];
  purchase_orders: { id: number; supplier: string; total: number; status: string; items: { name: string; qty: number }[] }[];
};

export default function Merchant() {
  const { data: d, reload } = useData<Detail>("/api/merchant/M001");
  const [busy, setBusy] = useState<string | null>(null);
  const [brief, setBrief] = useState<{ text: string; audio_url: string | null; tts_provider: string } | null>(null);
  if (!d) return <div className="h-96 animate-pulse rounded-3xl bg-white" />;
  const m = d.merchant;
  const openU = d.udhaar.filter((u) => u.status === "open");
  const low = d.products.filter((p) => p.stock <= p.reorder_level);

  const act = async (key: string, fn: () => Promise<unknown>) => { setBusy(key); try { await fn(); } finally { setBusy(null); reload(); } };
  const playBrief = async () => {
    setBusy("brief");
    try {
      const b = await api.post<{ text: string; audio_url: string | null; tts_provider: string }>("/api/agents/grower/brief?send=false");
      setBrief(b);
      if (b.audio_url) new Audio(b.audio_url).play().catch(() => speak(b.text)); else speak(b.text);
    } finally { setBusy(null); }
  };

  return (
    <div className="space-y-6">
      <section className="card flex flex-wrap items-center gap-5 p-5">
        <div className="grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-sky to-navy text-2xl font-extrabold text-white">RK</div>
        <div className="min-w-0">
          <div className="flex items-center gap-2"><h2 className="text-xl font-extrabold text-navy">{m.shop}</h2><StatusPill s={m.stage} /></div>
          <div className="mt-0.5 flex flex-wrap items-center gap-3 text-sm text-muted">
            <span>{m.name}</span><span className="flex items-center gap-1"><MapPin size={13} />{m.area}, {m.city}</span>
            <span>Language: Hindi</span><span>Credit limit {inr(m.credit_limit)}</span>
          </div>
        </div>
        <div className="ml-auto flex flex-wrap gap-2">
          <button className="btn-ghost" disabled={!!busy} onClick={playBrief}><Headphones size={15} />{busy === "brief" ? "Writing…" : "Play weekly brief"}</button>
          <button className="btn-ghost" disabled={!!busy} onClick={() => act("grow", () => api.post("/api/agents/grower/run"))}><Sparkles size={15} />{busy === "grow" ? "Running…" : "Run growth loops"}</button>
          <button className="btn-primary" disabled={!!busy} onClick={() => act("fest", () => api.post("/api/agents/grower/festival"))}><PackageCheck size={15} />{busy === "fest" ? "Planning…" : "Diwali prep + credit"}</button>
        </div>
      </section>

      {brief && (
        <div className="card animate-in border-sky/40 bg-sky-50/60 p-4 text-[13.5px] leading-relaxed">
          <div className="label mb-1">Weekly brief · {brief.tts_provider}</div>{brief.text}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Sales this week" value={inr(d.stats.last7)} sub={`${d.stats.wow_pct >= 0 ? "+" : ""}${d.stats.wow_pct.toFixed(1)}% vs last week`} />
        <Stat label="UPI share" value={`${Math.round(d.stats.upi_share * 100)}%`} sub="digital footprint for credit" tone="sky" />
        <Stat label="Open udhaar" value={inr(openU.reduce((a, u) => a + u.amount, 0))} sub={`${openU.length} customers`} tone="warn" />
        <Stat label="Low stock SKUs" value={low.length} sub="before the festival" tone="warn" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Card title="Daily sales · last 30 days" icon={<Wallet size={17} className="text-sky" />}><SalesChart data={d.daily.slice(-30)} /></Card>
        <Card title="Udhaar book" icon={<HandCoins size={17} className="text-sky" />} pad={false}>
          <div className="max-h-[260px] overflow-y-auto">
            <table className="tbl w-full">
              <thead><tr><th>Customer</th><th>Amount</th><th>Status</th><th /></tr></thead>
              <tbody>
                {d.udhaar.map((u) => (
                  <tr key={u.id}>
                    <td><div className="font-medium">{u.name}</div><div className="text-[11px] text-muted">{u.segment} · {u.nudges} nudges</div></td>
                    <td className="font-semibold tabular-nums">{inr(u.amount)}</td>
                    <td><StatusPill s={u.status} /></td>
                    <td className="text-right">
                      {u.status === "open" && (
                        <div className="flex justify-end gap-1">
                          <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => act(`n${u.id}`, () => api.post(`/api/udhaar/${u.id}/nudge`))}><Bell size={12} />Nudge</button>
                          <button className="btn-ghost !px-2 !py-1 !text-[11px]" onClick={() => act(`p${u.id}`, () => api.post(`/api/udhaar/${u.id}/pay`))}>Paid</button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card title="Stock & festival readiness" icon={<Boxes size={17} className="text-sky" />} pad={false}>
          <div className="max-h-[340px] overflow-y-auto">
            <table className="tbl w-full">
              <thead><tr><th>Item</th><th>Stock</th><th>Reorder at</th><th>Festive lift</th></tr></thead>
              <tbody>
                {d.products.map((p) => {
                  const pct = Math.min(100, (p.stock / Math.max(p.reorder_level * 2, 1)) * 100);
                  return (
                    <tr key={p.sku}>
                      <td><div className="font-medium">{p.name}</div><div className="text-[11px] text-muted">{p.name_local} · {inr(p.price)}</div></td>
                      <td className="w-40">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 flex-1 rounded-full bg-canvas"><div className={`h-1.5 rounded-full ${p.stock <= p.reorder_level ? "bg-warn" : "bg-sky"}`} style={{ width: `${pct}%` }} /></div>
                          <span className="w-7 text-right text-xs font-semibold tabular-nums">{p.stock}</span>
                        </div>
                      </td>
                      <td className="tabular-nums text-muted">{p.reorder_level}</td>
                      <td>{p.festival_multiplier >= 2 ? <span className="chip bg-amber-50 text-amber-700">×{p.festival_multiplier}</span> : <span className="text-muted">×{p.festival_multiplier}</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
        <div className="space-y-6">
          <Card title="Credit & purchase orders" icon={<PackageCheck size={17} className="text-sky" />}>
            <div className="space-y-2">
              {d.offers.length === 0 && d.purchase_orders.length === 0 && <div className="text-sm text-muted">No offers or POs yet. Try <b>Diwali prep + credit</b>.</div>}
              {d.offers.map((o) => (
                <div key={`o${o.id}`} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2">
                  <span className="chip bg-sky-50 text-sky-700">Offer #{o.id}</span>
                  <div className="min-w-0 flex-1 text-[13px]"><b>{inr(o.amount)}</b> · {o.daily_repay_pct}% of daily UPI · {o.tenure_days}d <div className="truncate text-[11px] text-muted">{o.reason}</div></div>
                  <StatusPill s={o.status} />
                  {o.status === "offered" && <button className="btn-primary !px-2.5 !py-1 !text-xs" onClick={() => act(`a${o.id}`, () => api.post(`/api/offers/${o.id}/accept`))}>Accept</button>}
                </div>
              ))}
              {d.purchase_orders.map((p) => (
                <div key={`p${p.id}`} className="flex items-center gap-3 rounded-xl border border-line px-3 py-2">
                  <span className="chip bg-amber-50 text-amber-700">PO #{p.id}</span>
                  <div className="min-w-0 flex-1 text-[13px]"><b>{inr(p.total)}</b> · {p.supplier}<div className="truncate text-[11px] text-muted">{p.items.map((i) => `${i.name}×${i.qty}`).join(", ")}</div></div>
                  <StatusPill s={p.status} />
                </div>
              ))}
            </div>
          </Card>
          <Card title="Customers (Pulse)" icon={<Users size={17} className="text-sky" />} pad={false}>
            <div className="max-h-[260px] overflow-y-auto">
              <table className="tbl w-full">
                <thead><tr><th>Customer</th><th>Household</th><th>90d spend</th><th>Churn risk</th></tr></thead>
                <tbody>
                  {d.customers.map((c) => (
                    <tr key={c.id}>
                      <td><div className="font-medium">{c.name}</div><div className="text-[11px] text-muted">{c.segment} · {c.visits_90d} visits</div></td>
                      <td className="text-muted">{c.household}</td>
                      <td className="tabular-nums">{inr(c.spend_90d)}</td>
                      <td>{c.churn_risk > 0.6 ? <span className="chip bg-red-50 text-red-700">high</span> : c.churn_risk > 0.25 ? <span className="chip bg-slate-100 text-slate-600">medium</span> : <span className="chip bg-green-50 text-green-700">low</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
