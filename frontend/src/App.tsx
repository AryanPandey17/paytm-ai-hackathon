import { useEffect, useState } from "react";
import {
  LayoutDashboard, MessagesSquare, Store, GitBranch, ShieldCheck, Network, Settings2, Sparkles, Play, RotateCcw,
} from "lucide-react";
import { LiveContext, useLiveStream, useData, api } from "./api";
import CommandCenter from "./pages/CommandCenter";
import DemoStudio from "./pages/DemoStudio";
import Merchant from "./pages/Merchant";
import Lifecycle from "./pages/Lifecycle";
import Approvals from "./pages/Approvals";
import Memory from "./pages/Memory";
import System from "./pages/System";

const NAV = [
  { id: "command", label: "Command Center", icon: LayoutDashboard, el: CommandCenter },
  { id: "studio", label: "WhatsApp Studio", icon: MessagesSquare, el: DemoStudio },
  { id: "merchant", label: "Merchant 360", icon: Store, el: Merchant },
  { id: "lifecycle", label: "Lifecycle", icon: GitBranch, el: Lifecycle },
  { id: "approvals", label: "Human-in-loop", icon: ShieldCheck, el: Approvals },
  { id: "memory", label: "Memory Graph", icon: Network, el: Memory },
  { id: "system", label: "System & Partners", icon: Settings2, el: System },
];

function useHash() {
  const [h, setH] = useState(() => location.hash.slice(1) || "command");
  useEffect(() => {
    const f = () => setH(location.hash.slice(1) || "command");
    addEventListener("hashchange", f);
    return () => removeEventListener("hashchange", f);
  }, []);
  return h;
}

function Shell() {
  const route = useHash();
  const page = NAV.find((n) => n.id === route) ?? NAV[0];
  const Page = page.el;
  const { data: approvals } = useData<{ status: string }[]>("/api/approvals");
  const pending = approvals?.filter((a) => a.status === "pending").length ?? 0;
  const [busy, setBusy] = useState(false);

  const runDemo = async () => {
    setBusy(true);
    await api.post("/api/demo/run").catch(() => {});
    location.hash = "studio";
    setTimeout(() => setBusy(false), 4000);
  };

  return (
    <div className="flex h-full">
      <aside className="hidden w-64 shrink-0 flex-col bg-navy text-white lg:flex">
        <div className="flex items-center gap-2.5 px-5 pt-6 pb-5">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-sky shadow-[0_8px_20px_-6px_rgba(0,186,242,.8)]">
            <Sparkles size={20} />
          </div>
          <div>
            <div className="text-[17px] font-extrabold leading-tight tracking-tight">Commerce<span className="text-sky">OS</span></div>
            <div className="text-[11px] text-white/60">AI teammates for merchants</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((n) => {
            const active = n.id === page.id;
            const Icon = n.icon;
            return (
              <a key={n.id} href={`#${n.id}`}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${active ? "bg-white text-navy shadow" : "text-white/75 hover:bg-white/10 hover:text-white"}`}>
                <Icon size={18} className={active ? "text-sky" : ""} />
                {n.label}
                {n.id === "approvals" && pending > 0 && (
                  <span className="ml-auto rounded-full bg-amber-400 px-2 py-0.5 text-[11px] font-bold text-navy">{pending}</span>
                )}
              </a>
            );
          })}
        </nav>
        <div className="m-3 rounded-2xl bg-white/10 p-4">
          <div className="text-xs font-semibold text-white/80">Built with</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {["Sarvam", "Cognee", "n8n", "WhatsApp"].map((p) => <span key={p} className="chip bg-white/15 text-white">{p}</span>)}
          </div>
          <div className="mt-3 text-[11px] leading-snug text-white/55">Paytm Build for India · Track 3 prototype</div>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-line bg-white/80 px-6 py-3.5 backdrop-blur">
          <div>
            <div className="text-lg font-bold text-navy">{page.label}</div>
            <div className="text-xs text-muted">Find · Onboard · Activate · Grow · Fund, with humans only by exception</div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button className="btn-ghost" onClick={() => api.post("/api/demo/reset")}><RotateCcw size={15} />Reset data</button>
            <button className="btn-primary" disabled={busy} onClick={runDemo}><Play size={15} />{busy ? "Running…" : "Run live demo"}</button>
          </div>
        </header>
        <div className="flex gap-1 overflow-x-auto border-b border-line bg-white px-3 py-2 lg:hidden">
          {NAV.map((n) => <a key={n.id} href={`#${n.id}`} className={`chip whitespace-nowrap px-3 py-1.5 ${n.id === page.id ? "bg-navy text-white" : "bg-canvas text-navy"}`}>{n.label}</a>)}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-6"><Page /></div>
      </main>
    </div>
  );
}

export default function App() {
  const live = useLiveStream();
  return <LiveContext.Provider value={live}><Shell /></LiveContext.Provider>;
}
