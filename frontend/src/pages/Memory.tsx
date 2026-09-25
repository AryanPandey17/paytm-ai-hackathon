import { useMemo, useState } from "react";
import { Network, Search, Brain } from "lucide-react";
import { api, ago, useData } from "../api";
import { AgentBadge, Card } from "../components/ui";

type G = { nodes: { id: string; type: string }[]; edges: { src: string; rel: string; dst: string }[] };
type MemEvt = { id: number; dataset: string; agent: string; text: string; ts: string };

const TYPE_COLOR: Record<string, string> = {
  Merchant: "#002E6E", Customer: "#00BAF2", Household: "#7C3AED", Agent: "#C2410C", Supplier: "#B45309",
  Offer: "#0A8F4E", Signal: "#D93A3A",
};
const color = (t: string) => TYPE_COLOR[t] ?? "#94A3B8";

function layout(g: G, W: number, H: number) {
  const n = g.nodes.length;
  const pos = new Map(g.nodes.map((nd, i) => [nd.id, { x: W / 2 + Math.cos((i / n) * 6.283) * W * 0.35, y: H / 2 + Math.sin((i / n) * 6.283) * H * 0.35, vx: 0, vy: 0 }]));
  const E = g.edges.filter((e) => pos.has(e.src) && pos.has(e.dst));
  for (let it = 0; it < 260; it++) {
    const arr = [...pos.values()];
    for (let i = 0; i < arr.length; i++) for (let j = i + 1; j < arr.length; j++) {
      const a = arr[i], b = arr[j];
      let dx = a.x - b.x, dy = a.y - b.y; const d2 = Math.max(dx * dx + dy * dy, 40);
      const f = 2600 / d2; dx *= f / Math.sqrt(d2); dy *= f / Math.sqrt(d2);
      a.vx += dx; a.vy += dy; b.vx -= dx; b.vy -= dy;
    }
    for (const e of E) {
      const a = pos.get(e.src)!, b = pos.get(e.dst)!;
      const dx = b.x - a.x, dy = b.y - a.y; const d = Math.sqrt(dx * dx + dy * dy) || 1; const f = (d - 90) * 0.02;
      a.vx += (dx / d) * f; a.vy += (dy / d) * f; b.vx -= (dx / d) * f; b.vy -= (dy / d) * f;
    }
    for (const p of pos.values()) {
      p.vx += (W / 2 - p.x) * 0.004; p.vy += (H / 2 - p.y) * 0.004;
      p.x = Math.min(W - 30, Math.max(30, p.x + p.vx * 0.5)); p.y = Math.min(H - 20, Math.max(20, p.y + p.vy * 0.5));
      p.vx *= 0.6; p.vy *= 0.6;
    }
  }
  return { pos, E };
}

export default function Memory() {
  const [ds, setDs] = useState("merchant_M001");
  const { data: g } = useData<G>(`/api/memory/graph?dataset=${ds}&limit=140`, [ds]);
  const { data: recent } = useData<MemEvt[]>("/api/memory/recent?limit=40");
  const [q, setQ] = useState("Sharma ji payment behaviour");
  const [ans, setAns] = useState<{ answer: string; facts: string[]; backend: string } | null>(null);
  const [hover, setHover] = useState<string | null>(null);
  const W = 820, H = 520;
  const L = useMemo(() => (g ? layout(g, W, H) : null), [g]);
  const present = new Set(g?.nodes.map((n) => n.type) ?? []);
  const types = Object.keys(TYPE_COLOR).filter((t) => present.has(t));
  const hasOther = [...present].some((t) => !TYPE_COLOR[t]);

  return (
    <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_420px]">
      <div className="space-y-6 min-w-0">
        <Card title="Merchant Memory Graph" icon={<Network size={17} className="text-violet-600" />}
          action={
            <select className="rounded-lg border border-line px-2 py-1 text-sm" value={ds} onChange={(e) => setDs(e.target.value)}>
              <option value="merchant_M001">Ramesh Kirana Stores</option><option value="portfolio">Portfolio</option>
            </select>}>
          <div className="mb-2 flex flex-wrap gap-3 text-[12px] text-muted">
            {types.map((t) => <span key={t} className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: color(t) }} />{t}</span>)}
            {hasOther && <span className="flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-full" style={{ background: color("Other") }} />Other (events, intents, places)</span>}
          </div>
          <div className="overflow-hidden rounded-xl bg-canvas">
            {L && g ? (
              <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full">
                {L.E.map((e, i) => {
                  const a = L.pos.get(e.src)!, b = L.pos.get(e.dst)!;
                  const on = hover && (hover === e.src || hover === e.dst);
                  return <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={on ? "#00BAF2" : "#C9D6E6"} strokeWidth={on ? 2 : 1} />;
                })}
                {g.nodes.map((n) => {
                  const p = L.pos.get(n.id)!; const big = n.type === "Merchant" || n.type === "Agent";
                  const show = big || hover === n.id || n.type === "Household";
                  return (
                    <g key={n.id} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} className="cursor-pointer">
                      <circle cx={p.x} cy={p.y} r={big ? 11 : 7} fill={color(n.type)} stroke="#fff" strokeWidth={2} />
                      {show && <text x={p.x} y={p.y - (big ? 15 : 11)} textAnchor="middle" fontSize={11} fontWeight={600} fill="#0B1B35"
                        style={{ paintOrder: "stroke", stroke: "#F4F8FC", strokeWidth: 4 }}>{n.id.length > 28 ? n.id.slice(0, 27) + "…" : n.id}</text>}
                      <title>{`${n.type}: ${n.id}`}</title>
                    </g>
                  );
                })}
              </svg>
            ) : <div className="h-[420px] animate-pulse" />}
          </div>
          <p className="mt-2 text-[12px] text-muted">Every agent writes outcomes here and reads context before it decides. With <code>MEMORY_BACKEND=cognee</code> the same writes go to Cognee (add + cognify) and recall uses Cognee graph search.</p>
        </Card>
        <Card title="Ask the memory" icon={<Search size={17} className="text-violet-600" />}>
          <form className="flex gap-2" onSubmit={async (e) => { e.preventDefault(); setAns(await api.post("/api/memory/search", { query: q })); }}>
            <input value={q} onChange={(e) => setQ(e.target.value)} className="flex-1 rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-sky" />
            <button className="btn-primary">Recall</button>
          </form>
          {ans && (
            <div className="mt-3 space-y-1.5 text-[13px]">
              <div className="label">via {ans.backend}</div>
              {ans.facts.length ? ans.facts.map((f, i) => <div key={i} className="rounded-lg bg-violet-50/60 px-3 py-2">{f}</div>) : <div className="text-muted">{ans.answer || "No matching memories"}</div>}
            </div>
          )}
        </Card>
      </div>
      <Card title="Latest memories" icon={<Brain size={17} className="text-violet-600" />} pad={false}>
        <div className="max-h-[980px] space-y-1 overflow-y-auto p-2">
          {recent?.map((m) => (
            <div key={m.id} className="flex gap-2.5 rounded-xl px-2.5 py-2 hover:bg-canvas">
              <AgentBadge agent={m.agent} size={26} />
              <div className="min-w-0"><div className="text-[12.5px] leading-snug">{m.text}</div><div className="mt-0.5 text-[11px] text-muted">{m.dataset} · {ago(m.ts)}</div></div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
