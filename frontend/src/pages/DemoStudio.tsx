import { useEffect, useRef, useState } from "react";
import { CheckCheck, Mic, Pause, Play, Send, Square, Volume2, ShieldCheck, BadgeIndianRupee, Wallet } from "lucide-react";
import { api, inr, speak, useData } from "../api";
import Feed from "../components/Feed";

type Msg = { id: number; direction: "in" | "out"; sender: string; text: string; kind: string; meta: Record<string, any>; ts: string; via: string };
type Thread = { phone: string; name: string; role: string; subtitle: string; count: number };

const QUICK_MERCHANT = [
  "Sharma ji ka 1200 udhaar pending hai, aur Diwali ka stock kam hai",
  "Is hafte ka hisaab bhejo",
  "Bikri kaisi rahi is hafte?",
];
const QUICK_CUSTOMER = ["Bhaiya atta hai kya?", "Mera udhaar kitna baaki hai?", "2 kilo cheeni aur ghee pack kar do", "Diye hai kya?"];

function linkify(t: string) {
  return t.split(/(https?:\/\/\S+|upi:\/\/\S+|\*[^*\n]+\*)/g).map((p, i) =>
    /^(https?|upi):\/\//.test(p) ? <span key={i} className="break-all text-sky-600 underline">{p}</span>
      : /^\*[^*]+\*$/.test(p) ? <b key={i}>{p.slice(1, -1)}</b> : <span key={i}>{p}</span>);
}

function Bubble({ m, onAct }: { m: Msg; onAct: () => void }) {
  const mine = m.direction === "in"; // sent by the phone owner
  const [playing, setPlaying] = useState(false);
  const time = new Date(m.ts).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
  const act = async (url: string, body?: unknown) => { await api.post(url, body); onAct(); };

  const playAudio = () => {
    if (m.meta?.audio_url) {
      const a = new Audio(m.meta.audio_url);
      setPlaying(true);
      a.onended = () => setPlaying(false);
      a.play().catch(() => { setPlaying(false); speak(m.text, m.meta?.lang || "hi-IN"); });
    } else {
      speak(m.text, m.meta?.lang || "hi-IN");
    }
  };

  return (
    <div className={`animate-in flex ${mine ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[86%] rounded-2xl px-3 py-2 text-[13px] leading-snug shadow-sm ${mine ? "rounded-tr-md bg-wa-out" : "rounded-tl-md bg-white"}`}>
        {!mine && <div className="mb-0.5 text-[11px] font-bold text-sky-600">{m.sender}</div>}
        {m.kind === "voice" && (
          <div className="mb-1 flex items-center gap-2 rounded-xl bg-black/5 px-2 py-1.5 text-[12px] text-muted">
            <Mic size={14} className="text-good" /> Voice note · transcribed by Sarvam
          </div>
        )}
        {m.kind === "audio" ? (
          <div>
            <button onClick={playAudio} className="flex w-full items-center gap-2 rounded-xl bg-sky-50 px-2.5 py-2 text-left">
              <span className="grid h-8 w-8 place-items-center rounded-full bg-sky text-white">{playing ? <Pause size={14} /> : <Play size={14} />}</span>
              <span className="flex-1">
                <span className="block text-[12px] font-semibold text-navy">Weekly voice brief · ~90s</span>
                <span className="block text-[11px] text-muted">{m.meta?.tts === "browser-tts" ? "Browser voice (add Sarvam key for Bulbul)" : "Sarvam Bulbul TTS"}</span>
              </span>
              <Volume2 size={15} className="text-sky-600" />
            </button>
            <details className="mt-1.5 text-[12px] text-muted"><summary className="cursor-pointer">Transcript</summary><div className="mt-1 whitespace-pre-line text-ink">{m.text}</div></details>
          </div>
        ) : (
          <div className="whitespace-pre-line text-ink">{linkify(m.text)}</div>
        )}

        {m.kind === "payment_request" && m.meta?.udhaar_id && (
          <button className="btn mt-2 w-full justify-center bg-navy !py-1.5 text-white hover:bg-navy-700" onClick={() => act(`/api/udhaar/${m.meta.udhaar_id}/pay`)}>
            <Wallet size={14} />Pay {inr(m.meta.amount)} with Paytm
          </button>
        )}
        {m.kind === "loan_offer" && m.meta?.offer_id && (
          <button className="btn mt-2 w-full justify-center bg-sky !py-1.5 text-white hover:bg-sky-600" onClick={() => act(`/api/offers/${m.meta.offer_id}/accept`)}>
            <BadgeIndianRupee size={14} />Accept {inr(m.meta.amount)} (one tap)
          </button>
        )}
        {m.kind === "approval" && m.meta?.approval_id && (
          <div className="mt-2 grid grid-cols-2 gap-1.5">
            <button className="btn justify-center bg-good !py-1.5 text-white" onClick={() => act(`/api/approvals/${m.meta.approval_id}`, { decision: "approve", by: "ops (whatsapp)" })}><ShieldCheck size={14} />Approve</button>
            <button className="btn justify-center bg-white !py-1.5 text-bad ring-1 ring-red-200" onClick={() => act(`/api/approvals/${m.meta.approval_id}`, { decision: "reject", by: "ops (whatsapp)" })}>Reject</button>
          </div>
        )}
        <div className="mt-1 flex items-center justify-end gap-1 text-[10px] text-muted">{time}{mine && <CheckCheck size={12} className="text-sky" />}</div>
      </div>
    </div>
  );
}

function Phone({ thread, threads, onSwitch, quick, voice }: {
  thread: Thread; threads?: Thread[]; onSwitch?: (p: string) => void; quick: string[]; voice?: boolean;
}) {
  const { data: msgs, reload } = useData<Msg[]>(`/api/messages?phone=${thread.phone}`, [thread.phone]);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => { scroller.current?.scrollTo({ top: 1e9, behavior: "smooth" }); }, [msgs?.length]);

  const send = async (t = text) => {
    if (!t.trim()) return;
    setSending(true); setText("");
    try { await api.post("/api/ingest/text", { phone: thread.phone, text: t }); } finally { setSending(false); reload(); }
  };

  const toggleRec = async () => {
    if (rec) { rec.stop(); setRec(null); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      mr.ondataavailable = (e) => chunks.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setSending(true);
        await api.voice(new Blob(chunks, { type: "audio/webm" }), thread.phone, text || quick[0]);
        setText(""); setSending(false); reload();
      };
      mr.start(); setRec(mr);
    } catch {
      setSending(true);
      await api.voice(null, thread.phone, text || quick[0]);
      setText(""); setSending(false); reload();
    }
  };

  const initials = thread.name.replace(/\(.*\)/, "").split(" ").map((s) => s[0]).slice(0, 2).join("");
  return (
    <div className="flex h-[680px] w-full flex-col overflow-hidden rounded-[2.2rem] border-[7px] border-navy-900 bg-navy-900 shadow-2xl">
      <div className="flex items-center gap-2.5 bg-[#075E54] px-3.5 pb-2.5 pt-3 text-white">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-white/20 text-sm font-bold">{initials}</div>
        <div className="min-w-0 flex-1">
          {threads && onSwitch ? (
            <select value={thread.phone} onChange={(e) => onSwitch(e.target.value)}
              className="w-full truncate bg-transparent text-[14px] font-semibold outline-none [&>option]:text-ink">
              {threads.map((t) => <option key={t.phone} value={t.phone}>{t.name}</option>)}
            </select>
          ) : <div className="truncate text-[14px] font-semibold">{thread.name}</div>}
          <div className="truncate text-[11px] text-white/70">{thread.subtitle} · WhatsApp</div>
        </div>
        <span className="chip bg-white/15 text-white capitalize">{thread.role}</span>
      </div>
      <div ref={scroller} className="wa-pattern flex-1 space-y-2 overflow-y-auto px-3 py-3">
        <div className="mx-auto w-fit rounded-lg bg-[#fff5c4] px-2.5 py-1 text-center text-[10.5px] text-ink/70">🔒 Messages are end-to-end encrypted. Commerce OS demo.</div>
        {msgs?.map((m) => <Bubble key={m.id} m={m} onAct={reload} />)}
        {sending && <div className="w-fit rounded-2xl bg-white px-3 py-2 text-[12px] text-muted shadow-sm">Agents are working…</div>}
      </div>
      <div className="bg-[#f0f2f5] px-2 pb-2 pt-1.5">
        <div className="mb-1.5 flex gap-1.5 overflow-x-auto pb-0.5">
          {quick.map((q) => (
            <button key={q} onClick={() => send(q)} className="chip shrink-0 bg-white px-2.5 py-1 text-[11px] font-medium text-navy ring-1 ring-line hover:ring-sky">{q}</button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <input value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="Type a message" className="min-w-0 flex-1 rounded-full bg-white px-3.5 py-2 text-[13px] outline-none ring-1 ring-line focus:ring-sky" />
          {voice && (
            <button onClick={toggleRec} title="Record a voice note"
              className={`grid h-9 w-9 place-items-center rounded-full text-white ${rec ? "bg-bad animate-pulse" : "bg-[#00a884]"}`}>
              {rec ? <Square size={14} /> : <Mic size={16} />}
            </button>
          )}
          <button onClick={() => send()} className="grid h-9 w-9 place-items-center rounded-full bg-[#00a884] text-white"><Send size={15} /></button>
        </div>
      </div>
    </div>
  );
}

export default function DemoStudio() {
  const { data: threads } = useData<Thread[]>("/api/threads");
  const [cust, setCust] = useState<string | null>(null);
  if (!threads) return <div className="h-96 animate-pulse rounded-3xl bg-white" />;
  const merchant = threads.find((t) => t.role === "merchant")!;
  const ops = threads.find((t) => t.role === "ops")!;
  const customers = threads.filter((t) => t.role === "customer");
  const customer = customers.find((c) => c.phone === cust) ?? customers[0];

  return (
    <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_380px]">
      <div className="min-w-0 space-y-4">
        <div className="card flex flex-wrap items-center gap-3 px-5 py-3.5 text-[13px]">
          <b className="text-navy">How to demo:</b>
          <span>① Ramesh sends a voice note or quick chip</span><span className="text-muted">→</span>
          <span>② Ops taps <b>Approve</b></span><span className="text-muted">→</span>
          <span>③ Ramesh taps <b>Accept</b></span><span className="text-muted">→</span>
          <span>④ Sharma ji taps <b>Pay</b></span>
          <span className="ml-auto text-muted">Real WhatsApp messages show here too (via n8n).</span>
        </div>
        <div className="grid gap-5 lg:grid-cols-3">
          <Phone thread={merchant} quick={QUICK_MERCHANT} voice />
          <Phone thread={customer} threads={customers} onSwitch={setCust} quick={QUICK_CUSTOMER} />
          <Phone thread={ops} quick={["Aaj ka plan?"]} />
        </div>
      </div>
      <div className="card h-[760px] overflow-hidden"><Feed /></div>
    </div>
  );
}
