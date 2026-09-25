import { useState } from "react";
import { ArrowRight, BadgeIndianRupee, Clock, HandCoins, Hand, Radar, ShieldCheck, TrendingUp, Wand2, Zap } from "lucide-react";
import { api, inr, useData, useLive } from "../api";
import Feed from "../components/Feed";
import SalesChart from "../components/SalesChart";
import { AgentBadge, AGENTS, Card, Stat } from "../components/ui";

type Kpis = {
  gmv_30d: number; hero_week: number; hero_wow_pct: number; hero_upi_share: number; merchants: number;
  ttft_hours: number; auto_resolve_pct: number; udhaar_recovered: number; udhaar_open: number; credit_deployed: number;
  human_touches: number; agent_actions: number; leads_total: number; leads_qualified: number; compliance_open: number;
  daily: { day: string; total: number; upi: number; txns: number }[];
};
type Plan = { plan: { headline?: string; priorities?: { objective: string; action: string; owner: string }[]; crisis?: string[] }; provider: string; ts: string } | null;

const JOURNEY = [
  { k: "hunter", t: "Find" }, { k: "onboarder", t: "Onboard" }, { k: "activator", t: "Activate" },
  { k: "grower", t: "Grow" }, { k: "capital", t: "Fund" }, { k: "pulse", t: "Serve" },
];

const ACTIONS: { agent: string; label: string; url: string }[] = [
  { agent: "commander", label: "Plan today", url: "/api/agents/commander/plan" },
  { agent: "hunter", label: "Score leads", url: "/api/agents/hunter/run" },
  { agent: "onboarder", label: "Resolve exceptions", url: "/api/agents/onboarder/resolve" },
  { agent: "activator", label: "Unstick devices", url: "/api/agents/activator/intervene" },
  { agent: "grower", label: "Run growth loops", url: "/api/agents/grower/run" },
  { agent: "bazaar", label: "Diwali restock", url: "/api/agents/grower/festival" },
  { agent: "capital", label: "Underwrite ₹30k", url: "/api/agents/capital/evaluate" },
  { agent: "pulse", label: "Failed UPI → recover", url: "/api/agents/pulse/failed-payment" },
];

export default function CommandCenter() {
  const { data: k } = useData<Kpis>("/api/kpis");
  const { data: plan } = useData<Plan>("/api/commander/plan");
  const { events } = useLive();
  const [running, setRunning] = useState<string | null>(null);
  const counts = events.reduce<Record<string, number>>((a, e) => ((a[e.agent] = (a[e.agent] || 0) + 1), a), {});

  const run = async (a: (typeof ACTIONS)[number]) => {
    setRunning(a.label);
    try { await api.post(a.url, a.agent === "capital" ? { amount: 30000, reason: "Working capital top-up" } : {}); } finally { setRunning(null); }
  };

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
      <div className="space-y-6 min-w-0">
        {/* Hero */}
        <section className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-navy via-navy-800 to-navy-700 p-7 text-white">
          <div className="absolute -right-16 -top-16 h-64 w-64 rounded-full bg-sky/25 blur-3xl" />
          <div className="absolute bottom-0 right-24 h-40 w-40 rounded-full bg-sky/20 blur-2xl" />
          <div className="relative">
            <span className="chip bg-sky/20 text-sky ring-1 ring-sky/40"><Zap size={12} />AI teammates that get the job done</span>
            <h1 className="mt-3 max-w-2xl text-3xl font-extrabold leading-tight tracking-tight">
              From <span className="text-sky">first hello</span> to a growing, <span className="text-sky">credit-backed</span> business: run by agents, on WhatsApp.
            </h1>
            <div className="mt-6 flex flex-wrap items-center gap-2">
              {JOURNEY.map((j, i) => (
                <div key={j.k} className="flex items-center gap-2">
                  <div className="flex items-center gap-2 rounded-xl bg-white/10 px-3 py-2 ring-1 ring-white/10">
                    <AgentBadge agent={j.k} size={26} />
                    <div>
                      <div className="text-[13px] font-bold">{j.t}</div>
                      <div className="text-[10.5px] text-white/60">{AGENTS[j.k].label}</div>
                    </div>
                  </div>
                  {i < JOURNEY.length - 1 && <ArrowRight size={14} className="text-white/40" />}
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* KPIs */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <Stat label="Portfolio GMV · 30d" value={inr(k?.gmv_30d, true)} sub={`${k?.merchants ?? "–"} merchants`} icon={<TrendingUp size={16} />} />
          <Stat label="Udhaar recovered" value={inr(k?.udhaar_recovered)} sub={`${inr(k?.udhaar_open)} still open`} tone="good" icon={<HandCoins size={16} />} />
          <Stat label="Credit deployed" value={inr(k?.credit_deployed, true)} sub="one-tap, daily % repay" tone="sky" icon={<BadgeIndianRupee size={16} />} />
          <Stat label="Avg TTFT" value={`${k?.ttft_hours ?? "–"}h`} sub="time to first txn" icon={<Clock size={16} />} />
          <Stat label="Auto-resolved" value={`${k?.auto_resolve_pct ?? "–"}%`} sub={`${k?.compliance_open ?? 0} KYC open`} tone="good" icon={<ShieldCheck size={16} />} />
          <Stat label="Human touches" value={k?.human_touches ?? "–"} sub={`vs ${k?.agent_actions ?? 0} agent actions`} tone="warn" icon={<Hand size={16} />} />
        </div>

        <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <Card title="Ramesh Kirana Stores · daily sales (30d)" icon={<TrendingUp size={17} className="text-sky" />}
            action={<span className="chip bg-sky-50 text-sky-700">{k ? `${k.hero_wow_pct >= 0 ? "+" : ""}${k.hero_wow_pct}% WoW · ${k.hero_upi_share}% UPI` : ""}</span>}>
            {k ? <SalesChart data={k.daily} /> : <div className="h-[220px] animate-pulse rounded-xl bg-canvas" />}
          </Card>

          <Card title="Commander's plan for today" icon={<Radar size={17} className="text-sky" />}
            action={<button className="btn-ghost !py-1.5 !text-xs" onClick={() => api.post("/api/agents/commander/plan")}><Wand2 size={13} />Re-plan</button>}>
            {plan?.plan?.headline ? (
              <div className="space-y-3">
                <p className="text-[14px] font-semibold leading-snug text-navy">{plan.plan.headline}</p>
                <ul className="space-y-2">
                  {plan.plan.priorities?.slice(0, 4).map((p, i) => (
                    <li key={i} className="flex gap-2.5 text-[13px]">
                      <span className="chip mt-0.5 h-fit bg-navy text-white">{p.objective}</span>
                      <span className="text-ink/85">{p.action}</span>
                    </li>
                  ))}
                </ul>
                {!!plan.plan.crisis?.length && (
                  <div className="rounded-xl bg-red-50 px-3 py-2 text-[12.5px] text-red-700">⚠ {plan.plan.crisis.join(" · ")}</div>
                )}
                <div className="text-[11px] text-muted">via {plan.provider}</div>
              </div>
            ) : (
              <div className="py-8 text-center text-sm text-muted">No plan yet. Click <b>Re-plan</b> or run the demo.</div>
            )}
          </Card>
        </div>

        <Card title="Your AI team" icon={<Zap size={17} className="text-sky" />}>
          <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
            {ACTIONS.map((a) => {
              const meta = AGENTS[a.agent];
              return (
                <div key={a.label} className="group rounded-2xl border border-line p-3.5 transition hover:border-sky hover:shadow-md">
                  <div className="flex items-center gap-2.5">
                    <AgentBadge agent={a.agent} size={34} />
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold text-navy">{meta.label}</div>
                      <div className="text-[11.5px] text-muted">{meta.role} · {counts[a.agent] ?? 0} events</div>
                    </div>
                  </div>
                  <button className="btn-ghost mt-3 w-full justify-center !py-1.5 !text-xs" disabled={!!running} onClick={() => run(a)}>
                    {running === a.label ? "Working…" : a.label}
                  </button>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <div className="card h-[calc(100vh-150px)] overflow-hidden xl:sticky xl:top-0"><Feed /></div>
    </div>
  );
}
