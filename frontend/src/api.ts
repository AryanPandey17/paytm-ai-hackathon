import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

export type AgentEvent = {
  id: number;
  ts: number;
  agent: string;
  kind: string;
  title: string;
  detail: string;
  partner?: string | null;
  status: string;
  data: Record<string, unknown>;
};

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const api = {
  get: <T,>(u: string) => req<T>("GET", u),
  post: <T,>(u: string, b?: unknown) => req<T>("POST", u, b ?? {}),
  voice: async (blob: Blob | null, from: string, hint?: string) => {
    const fd = new FormData();
    if (blob) fd.append("file", blob, "voice.webm");
    fd.append("from_number", from);
    if (hint) fd.append("transcript_hint", hint);
    const r = await fetch("/api/ingest/voice", { method: "POST", body: fd });
    return r.json();
  },
};

/* ---------------- live event stream (SSE) ---------------- */
type LiveCtx = { events: AgentEvent[]; connected: boolean; tick: number };
export const LiveContext = createContext<LiveCtx>({ events: [], connected: false, tick: 0 });
export const useLive = () => useContext(LiveContext);

export function useLiveStream(): LiveCtx {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [tick, setTick] = useState(0);
  const tickTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    api.get<AgentEvent[]>("/api/events/history?limit=150").then((h) => setEvents(h.reverse())).catch(() => {});
    const es = new EventSource("/api/events");
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (m) => {
      const e = JSON.parse(m.data) as AgentEvent;
      setEvents((prev) => (prev.some((p) => p.id === e.id) ? prev : [e, ...prev].slice(0, 300)));
      window.clearTimeout(tickTimer.current);
      tickTimer.current = window.setTimeout(() => setTick((t) => t + 1), 250);
    };
    return () => es.close();
  }, []);
  return { events, connected, tick };
}

/** Fetch + auto-refresh whenever agents emit events. */
export function useData<T>(url: string | null, deps: unknown[] = []) {
  const { tick } = useLive();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    if (!url) return;
    api.get<T>(url).then((d) => { setData(d); setError(null); }).catch((e) => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, ...deps]);
  useEffect(load, [load, tick]);
  return { data, error, reload: load };
}

/* ---------------- formatting ---------------- */
export function inr(v: number | null | undefined, compact = false) {
  const n = Number(v || 0);
  if (compact) {
    if (n >= 1e7) return `₹${(n / 1e7).toFixed(2)} Cr`;
    if (n >= 1e5) return `₹${(n / 1e5).toFixed(2)} L`;
    if (n >= 1e3) return `₹${(n / 1e3).toFixed(1)}k`;
  }
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

export function ago(ts: number | string) {
  const t = typeof ts === "number" ? ts * 1000 : new Date(ts).getTime();
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export function speak(text: string, lang = "hi-IN") {
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    u.rate = 0.95;
    window.speechSynthesis.speak(u);
  } catch {
    /* ignore */
  }
}
