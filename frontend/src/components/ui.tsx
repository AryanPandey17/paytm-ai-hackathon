import {
  Brain, Crosshair, Rocket, Sprout, Store, Landmark, HeartHandshake, Radar, Route, Bot, UserCheck, Cpu,
} from "lucide-react";
import type { ReactNode } from "react";

export const AGENTS: Record<string, { label: string; color: string; bg: string; icon: typeof Bot; role: string }> = {
  commander: { label: "RevOps Commander", color: "#002E6E", bg: "#E6ECF5", icon: Radar, role: "Plans the day" },
  hunter: { label: "Hunter", color: "#7C3AED", bg: "#F1EBFE", icon: Crosshair, role: "Finds merchants" },
  onboarder: { label: "Onboarder", color: "#0E7490", bg: "#E0F4F7", icon: UserCheck, role: "KYC in parallel" },
  activator: { label: "Activator", color: "#C2410C", bg: "#FDEEE6", icon: Rocket, role: "First transaction" },
  grower: { label: "Grower", color: "#0A8F4E", bg: "#E4F6EC", icon: Sprout, role: "Grows the business" },
  bazaar: { label: "Bazaar", color: "#B45309", bg: "#FDF3E1", icon: Store, role: "Smart restocking" },
  capital: { label: "Capital", color: "#0099D6", bg: "#E1F5FD", icon: Landmark, role: "Credit on time" },
  pulse: { label: "Pulse", color: "#DB2777", bg: "#FCE7F1", icon: HeartHandshake, role: "Serves customers" },
  router: { label: "Router", color: "#334155", bg: "#EEF2F6", icon: Route, role: "Understands intent" },
  system: { label: "System", color: "#475569", bg: "#EEF2F6", icon: Cpu, role: "" },
  demo: { label: "Demo", color: "#00BAF2", bg: "#E8F8FE", icon: Bot, role: "" },
};

export const PARTNERS: Record<string, { label: string; cls: string }> = {
  sarvam: { label: "Sarvam", cls: "bg-orange-50 text-orange-700 ring-1 ring-orange-200" },
  cognee: { label: "Cognee", cls: "bg-violet-50 text-violet-700 ring-1 ring-violet-200" },
  memory: { label: "Memory", cls: "bg-violet-50 text-violet-700 ring-1 ring-violet-200" },
  n8n: { label: "n8n", cls: "bg-rose-50 text-rose-700 ring-1 ring-rose-200" },
  paytm: { label: "Paytm rails", cls: "bg-sky-50 text-sky-700 ring-1 ring-sky-200" },
  llm: { label: "LLM", cls: "bg-slate-100 text-slate-700 ring-1 ring-slate-200" },
};

export function AgentBadge({ agent, size = 28 }: { agent: string; size?: number }) {
  const a = AGENTS[agent] ?? AGENTS.system;
  const Icon = a.icon;
  return (
    <span className="grid place-items-center rounded-lg shrink-0" style={{ width: size, height: size, background: a.bg, color: a.color }}>
      <Icon size={size * 0.55} strokeWidth={2.2} />
    </span>
  );
}

export function PartnerChip({ p }: { p?: string | null }) {
  if (!p || !PARTNERS[p]) return null;
  return <span className={`chip ${PARTNERS[p].cls}`}>{PARTNERS[p].label}</span>;
}

export function Card({ title, icon, action, children, className = "", pad = true }: {
  title?: ReactNode; icon?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; pad?: boolean;
}) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <header className="flex items-center justify-between gap-3 px-5 pt-4 pb-3">
          <h3 className="flex items-center gap-2 font-semibold text-navy">{icon}{title}</h3>
          {action}
        </header>
      )}
      <div className={pad ? "px-5 pb-5" : ""}>{children}</div>
    </section>
  );
}

export function Stat({ label, value, sub, tone = "navy", icon }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "navy" | "sky" | "good" | "warn"; icon?: ReactNode }) {
  const ring = { navy: "from-navy/10", sky: "from-sky/15", good: "from-good/15", warn: "from-warn/15" }[tone];
  return (
    <div className={`card relative overflow-hidden p-4 bg-gradient-to-br ${ring} to-white`}>
      <div className="flex items-center justify-between">
        <span className="label">{label}</span>
        <span className="text-sky-600">{icon}</span>
      </div>
      <div className="mt-1.5 text-2xl font-extrabold tracking-tight text-navy tabular-nums">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
    </div>
  );
}

export function StatusPill({ s }: { s: string }) {
  const map: Record<string, string> = {
    done: "bg-green-50 text-green-700", complete: "bg-green-50 text-green-700", paid: "bg-green-50 text-green-700",
    approved: "bg-green-50 text-green-700", disbursed: "bg-green-50 text-green-700", repaying: "bg-green-50 text-green-700",
    qualified: "bg-green-50 text-green-700", first_txn: "bg-green-50 text-green-700", placed: "bg-green-50 text-green-700", ready: "bg-green-50 text-green-700",
    in_progress: "bg-sky-50 text-sky-700", offered: "bg-sky-50 text-sky-700", dispatched: "bg-sky-50 text-sky-700", draft: "bg-slate-100 text-slate-600",
    new: "bg-slate-100 text-slate-600", allocated: "bg-slate-100 text-slate-600", delivered: "bg-sky-50 text-sky-700", nurture: "bg-slate-100 text-slate-600",
    open: "bg-amber-50 text-amber-700", pending: "bg-amber-50 text-amber-700", awaiting_approval: "bg-amber-50 text-amber-700",
    exception: "bg-red-50 text-red-700", escalated: "bg-amber-50 text-amber-700", rejected: "bg-red-50 text-red-700",
    declined: "bg-red-50 text-red-700", blocked: "bg-red-50 text-red-700", at_risk: "bg-red-50 text-red-700",
  };
  return <span className={`chip ${map[s] ?? "bg-slate-100 text-slate-600"}`}>{s.replace(/_/g, " ")}</span>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="grid place-items-center py-10 text-sm text-muted">{children}</div>;
}

export { Brain };
