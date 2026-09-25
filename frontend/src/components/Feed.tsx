import { useLive, ago, type AgentEvent } from "../api";
import { AgentBadge, AGENTS, PartnerChip } from "./ui";
import { AlertTriangle, BrainCircuit, Ear, Hand, Lightbulb, Save, Zap, Activity } from "lucide-react";

const KIND: Record<string, { label: string; icon: typeof Zap; cls: string }> = {
  trigger: { label: "Hear", icon: Ear, cls: "text-slate-500" },
  understand: { label: "Understand", icon: Lightbulb, cls: "text-orange-500" },
  recall: { label: "Remember", icon: BrainCircuit, cls: "text-violet-500" },
  decide: { label: "Decide", icon: Activity, cls: "text-navy" },
  act: { label: "Act", icon: Zap, cls: "text-sky-600" },
  escalate: { label: "Human", icon: Hand, cls: "text-amber-600" },
  learn: { label: "Learn", icon: Save, cls: "text-violet-500" },
  system: { label: "System", icon: Activity, cls: "text-slate-400" },
};

export function FeedItem({ e }: { e: AgentEvent }) {
  const k = KIND[e.kind] ?? KIND.system;
  const Icon = k.icon;
  const warn = e.status === "warn" || e.status === "error";
  if (e.agent === "demo") {
    return (
      <div className="animate-in my-2 flex items-center gap-2 rounded-xl bg-gradient-to-r from-navy to-navy-700 px-3 py-2 text-white">
        <span className="chip shrink-0 whitespace-nowrap bg-sky text-white">{e.title}</span>
        <span className="text-[13px] font-medium">{e.detail}</span>
      </div>
    );
  }
  return (
    <div className={`animate-in group flex gap-3 rounded-xl px-2.5 py-2 hover:bg-canvas ${warn ? "bg-amber-50/60" : ""}`}>
      <AgentBadge agent={e.agent} size={30} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[12px] font-bold" style={{ color: (AGENTS[e.agent] ?? AGENTS.system).color }}>
            {(AGENTS[e.agent] ?? AGENTS.system).label}
          </span>
          <span className={`inline-flex items-center gap-0.5 text-[11px] font-semibold ${k.cls}`}>
            <Icon size={12} />{k.label}
          </span>
          <PartnerChip p={e.partner} />
          {(e.data as { mode?: string })?.mode === "simulated" && <span className="chip bg-slate-100 text-slate-500">simulated</span>}
          {(e.data as { mode?: string })?.mode === "live" && <span className="chip bg-green-50 text-green-700">live</span>}
          <span className="ml-auto text-[11px] text-muted tabular-nums">{ago(e.ts)}</span>
        </div>
        <div className="mt-0.5 flex items-start gap-1 text-[13px] font-semibold text-ink">
          {warn && <AlertTriangle size={14} className="mt-0.5 shrink-0 text-warn" />}
          <span>{e.title}</span>
        </div>
        {e.detail && <div className="mt-0.5 line-clamp-3 whitespace-pre-line text-[12.5px] leading-snug text-muted">{e.detail}</div>}
      </div>
    </div>
  );
}

export default function Feed({ max = 60, filter }: { max?: number; filter?: (e: AgentEvent) => boolean }) {
  const { events, connected } = useLive();
  const list = (filter ? events.filter(filter) : events).slice(0, max);
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
        <span className={`h-2.5 w-2.5 rounded-full ${connected ? "bg-sky live-dot" : "bg-slate-300"}`} />
        <span className="font-semibold text-navy">Live agent activity</span>
        <span className="ml-auto text-xs text-muted">{connected ? "streaming" : "reconnecting…"}</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {list.length === 0 ? <div className="p-6 text-center text-sm text-muted">Waiting for agents…</div> : list.map((e) => <FeedItem key={e.id} e={e} />)}
      </div>
    </div>
  );
}
