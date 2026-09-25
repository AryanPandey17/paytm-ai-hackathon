import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { inr } from "../api";

type Day = { day: string; total: number; upi: number; txns: number };

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Day }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-xl border border-line bg-white px-3 py-2 text-xs shadow-lg">
      <div className="font-semibold text-navy">{new Date(d.day).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}</div>
      <div className="mt-1 text-ink">Sales <b className="tabular-nums">{inr(d.total)}</b></div>
      <div className="text-muted">via UPI <span className="tabular-nums">{inr(d.upi)}</span> · {d.txns} txns</div>
    </div>
  );
}

/** Single series (daily sales) → no legend; the card title names it. */
export default function SalesChart({ data, height = 220 }: { data: Day[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#00BAF2" stopOpacity={0.28} />
            <stop offset="100%" stopColor="#00BAF2" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#E3EAF3" vertical={false} />
        <XAxis dataKey="day" tickFormatter={(d) => new Date(d).getDate().toString()} tick={{ fontSize: 11, fill: "#5B6B82" }}
          axisLine={false} tickLine={false} interval={4} />
        <YAxis tickFormatter={(v) => inr(v, true)} tick={{ fontSize: 11, fill: "#5B6B82" }} axisLine={false} tickLine={false} width={54} />
        <Tooltip content={<Tip />} cursor={{ stroke: "#002E6E", strokeDasharray: "3 3" }} />
        <Area type="monotone" dataKey="total" stroke="#00BAF2" strokeWidth={2} fill="url(#salesFill)"
          activeDot={{ r: 5, stroke: "#fff", strokeWidth: 2, fill: "#002E6E" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
}
