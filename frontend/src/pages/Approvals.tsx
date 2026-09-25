import { ShieldCheck, ShieldAlert, MessageCircle } from "lucide-react";
import { api, ago, inr, useData } from "../api";
import { AgentBadge, AGENTS, Card, Empty, StatusPill } from "../components/ui";

type Approval = { id: number; kind: string; agent: string; title: string; detail: string; amount: number | null; status: string; created: string; decided: string | null; decided_by: string | null };
type Health = { guardrails: { capital_approval_threshold: number; resolver_confidence_threshold: number; nudge_cooldown_days: number } };

export default function Approvals() {
  const { data, reload } = useData<Approval[]>("/api/approvals");
  const { data: h } = useData<Health>("/api/health");
  const decide = async (id: number, decision: string) => { await api.post(`/api/approvals/${id}`, { decision, by: "dashboard" }); reload(); };
  const pending = data?.filter((a) => a.status === "pending") ?? [];
  const done = data?.filter((a) => a.status !== "pending") ?? [];

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-6">
        <Card title={`Waiting for a human (${pending.length})`} icon={<ShieldAlert size={17} className="text-amber-600" />}>
          {pending.length === 0 ? <Empty>Nothing needs you right now. Agents are handling it 🎉</Empty> : (
            <div className="space-y-3">
              {pending.map((a) => (
                <div key={a.id} className="animate-in rounded-2xl border border-amber-200 bg-amber-50/40 p-4">
                  <div className="flex items-start gap-3">
                    <AgentBadge agent={a.agent} size={36} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-[12px] text-muted">
                        <b style={{ color: AGENTS[a.agent]?.color }}>{AGENTS[a.agent]?.label}</b>· #{a.id} · {ago(a.created)}
                        <span className="chip bg-white text-navy ring-1 ring-line"><MessageCircle size={11} />also sent to ops WhatsApp</span>
                      </div>
                      <div className="mt-1 text-[15px] font-bold text-navy">{a.title}</div>
                      <p className="mt-1 text-[13px] text-ink/80">{a.detail}</p>
                    </div>
                    {a.amount != null && <div className="text-right text-xl font-extrabold text-navy tabular-nums">{inr(a.amount)}</div>}
                  </div>
                  <div className="mt-3 flex justify-end gap-2">
                    <button className="btn-ghost !text-bad" onClick={() => decide(a.id, "reject")}>Reject</button>
                    <button className="btn bg-good text-white hover:brightness-110" onClick={() => decide(a.id, "approve")}><ShieldCheck size={15} />Approve</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title="Decision log" pad={false}>
          {done.length === 0 ? <Empty>No decisions yet</Empty> : (
            <table className="tbl w-full">
              <thead><tr><th>#</th><th>Request</th><th>Decision</th><th>By</th></tr></thead>
              <tbody>{done.map((a) => (
                <tr key={a.id}><td className="text-muted">{a.id}</td><td>{a.title}</td><td><StatusPill s={a.status} /></td><td className="text-muted">{a.decided_by}</td></tr>
              ))}</tbody>
            </table>
          )}
        </Card>
      </div>
      <Card title="Guardrails" icon={<ShieldCheck size={17} className="text-sky" />}>
        <ul className="space-y-3 text-[13px]">
          <li className="rounded-xl bg-canvas p-3"><b className="text-navy">Capital</b>: offers above <b>{inr(h?.guardrails.capital_approval_threshold)}</b> or with a risk flag need a human.</li>
          <li className="rounded-xl bg-canvas p-3"><b className="text-navy">Onboarder</b>: resolver confidence below <b>{h?.guardrails.resolver_confidence_threshold}</b> goes to a human.</li>
          <li className="rounded-xl bg-canvas p-3"><b className="text-navy">Grower</b>: max 1 udhaar nudge per customer every <b>{h?.guardrails.nudge_cooldown_days}</b> days.</li>
          <li className="rounded-xl bg-canvas p-3"><b className="text-navy">Commander</b>: agent conflicts (lend vs churn risk) pause auto-offers.</li>
        </ul>
        <p className="mt-4 text-[12px] text-muted">In production the approver taps Approve/Reject on WhatsApp (n8n send-and-wait) and n8n calls back the backend.</p>
      </Card>
    </div>
  );
}
