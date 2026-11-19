import { ProfileForm } from "./profile";
import { AIRouting, aiNames } from "./ai-routing";
import { DeepFocus } from "./deep-focus";
import { DevicePairing } from "./device-pairing";
import { ComputerWidget } from "./computer-widget";
import { ShortTalkPanel, type ShortTalkHandle } from "./short-talk-panel";
import { FileApprovals, type FilePlan, type ToolEvent } from "./file-approvals";
import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AudioLines,
  ArrowUpRight,
  ArrowUp,
  Bell,
  BrainCircuit,
  Check,
  ChevronRight,
  CircleHelp,
  Code2,
  Command,
  Cpu,
  Focus,
  Globe2,
  LayoutDashboard,
  Laptop,
  Keyboard,
  CalendarCheck,
  LoaderCircle,
  MessageSquare,
  Mic,
  Plus,
  Radio,
  Settings2,
  ShieldCheck,
  Sparkles,
  Square,
  Trash2,
  Volume2,
  VolumeX,
  Wifi,
  X,
} from "lucide-react";
import "./style.css";
import { VoiceCapture } from "./voice";
import { SpeechPlayback, speechText } from "./playback";

type Message = { role: string; content: string; provider?: string };
type Memory = { id: number; content: string; updated: string };
type Reminder = {
  id: number;
  title: string;
  due: string;
  recurrence: string;
  status: string;
};
type Notice = { id: number; content: string; read: number; created: string };
type Status = {
  profile?: {name:string};
  providers: Record<string, boolean>;
  routes: Record<string, string>;
  timezone: string;
  telegram_configured: boolean;
  file_assistant?: {
    available: boolean;
    enabled: boolean;
    locations: string[];
  };
};
type View = "overview" | "chat" | "memory" | "reminders" | "devices";
const labels: Record<View, string> = {
  overview: "Overview",
  devices: "Devices",
  chat: "Conversation",
  memory: "Memory",
  reminders: "Reminders",
};
const session = (() => {
  let s = localStorage.getItem("bujji-session");
  if (!s) {
    s = crypto.randomUUID();
    localStorage.setItem("bujji-session", s);
  }
  return s;
})();
function LiveClock() {
  const [clock, setClock] = useState(new Date());
  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="date-block">
      <strong>
        {clock.toLocaleTimeString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
        })}
      </strong>
      <span>
        {clock
          .toLocaleDateString("en-IN", {
            timeZone: "Asia/Kolkata",
            weekday: "short",
            day: "2-digit",
            month: "short",
          })
          .toUpperCase()}{" "}
        · IST
      </span>
    </div>
  );
}
function App() {
  const [view, setView] = useState<View>("overview"),
    [focus, setFocus] = useState(
      localStorage.getItem("bujji-focus") === "true",
    );
  const [token, setToken] = useState(
      sessionStorage.getItem("bujji-token") || "",
    ),
    [draftToken, setDraftToken] = useState(""),
    [settings, setSettings] = useState(false);
  const [status, setStatus] = useState<Status | null>(null),
    [online, setOnline] = useState(false),
    [error, setError] = useState("");
  const clock = new Date();
  const [filePlans, setFilePlans] = useState<FilePlan[]>([]);
  const [toolEvents, setToolEvents] = useState<ToolEvent[]>([]);
  const [fileOCR, setFileOCR] = useState(false);
  const [confirmingFile, setConfirmingFile] = useState(false);
  const fileConfirmationBusy = useRef(false);
  const [shortActive, setShortActive] = useState(false);
  const shortTalkRef = useRef<ShortTalkHandle>(null);
  useEffect(() => { if(view !== "overview" || focus) { shortTalkRef.current?.end(); setShortActive(false); } },[view,focus]);
  const [messages, setMessages] = useState<Message[]>([]),
    [input, setInput] = useState(""),
    [busy, setBusy] = useState(false),
    [task, setTask] = useState("auto"),
    [provider, setProvider] = useState("auto");
  const [memories, setMemories] = useState<Memory[]>([]),
    [memory, setMemory] = useState(""),
    [reminders, setReminders] = useState<Reminder[]>([]),
    [notices, setNotices] = useState<Notice[]>([]);
  const [remTitle, setRemTitle] = useState(""),
    [due, setDue] = useState(""),
    [repeat, setRepeat] = useState("none");
  const [listening, setListening] = useState(false),
    [speak, setSpeak] = useState(
      localStorage.getItem("bujji-spoken-replies") === "true",
    ),
    [language, setLanguage] = useState("en-IN");
  const [stages, setStages] = useState<
    {
      role: string;
      status: string;
      provider: string;
      model?: string;
      artifact?: string;
      error?: string;
    }[]
  >([]);
  const [collaborate, setCollaborate] = useState(false);
  const [reviewVoice,setReviewVoice]=useState(localStorage.getItem("bujji-review-voice")==="true");
  const [editingMemory, setEditingMemory] = useState<number | null>(null);
  const [desktopPrefs, setDesktopPrefs] = useState<{
    soundEnabled: boolean;
    startAtLogin: boolean;
    notificationsSupported: boolean;
    packaged: boolean;
  } | null>(null);
  useEffect(() => {
    const desktop = window.bujjiDesktop;
    if (!desktop) return;
    let active = true;
    Promise.all([desktop.bootstrap(), desktop.preferences()])
      .then(([boot, prefs]) => {
        if (!active) return;
        if (boot.origin !== location.origin)
          throw new Error("Desktop origin mismatch.");
        sessionStorage.setItem("bujji-token", boot.token);
        setToken(boot.token);
        setDesktopPrefs(prefs);
      })
      .catch(() => setError("Desktop pairing failed. Quit and reopen Bujji."));
    const unsubscribe = desktop.onHidden(() => {
      recognition.current?.abort();
      sttAbort.current?.abort();
      setTranscribing(false);
      setListening(false);
      playback.current?.stop();
      setSpeechStatus("");
      microphoneActive.current = false;
    });
    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  const sending = useRef(false);
  const end = useRef<HTMLDivElement>(null),
    abort = useRef<AbortController | null>(null),
    recognition = useRef<VoiceCapture | null>(null);
  const sttAbort = useRef<AbortController | null>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [voiceDraft, setVoiceDraft] = useState("");
  const submitVoice = useRef<(text: string) => Promise<void>>(async () => {});
  const focusRef = useRef(focus);
  focusRef.current = reviewVoice;
  const [soundTest, setSoundTest] = useState("");
  const playback = useRef<SpeechPlayback | null>(null);
  const speakEnabled = useRef(speak);
  speakEnabled.current = speak;
  const microphoneActive = useRef(false);
  const [speechStatus, setSpeechStatus] = useState("");
  function stopVoice() {
    playback.current?.stop();
    setSpeechStatus("");
  }
  useEffect(() => {
    localStorage.setItem("bujji-spoken-replies", String(speak));
  }, [speak]);
  useEffect(() => {
    const hidden = () => {
      if (document.hidden) {
        playback.current?.stop();
        setSpeechStatus("");
      }
    };
    document.addEventListener("visibilitychange", hidden);
    return () => document.removeEventListener("visibilitychange", hidden);
  }, []);
  async function readReply(content: string) {
    const prepared = speechText(content);
    if (!prepared.text || document.hidden || microphoneActive.current) return;
    if (!playback.current) playback.current = new SpeechPlayback();
    await playback.current.play(
      prepared.text,
      async (text, signal) => {
        const response = await api("/speech/synthesize", {
          method: "POST",
          signal,
          body: JSON.stringify({ text }),
        });
        return response.blob();
      },
      (status) =>
        setSpeechStatus(
          status +
            (status && prepared.shortened
              ? " Reading the first part; code blocks and verification details stay in text."
              : ""),
        ),
      (message) =>
        setSpeechStatus(
          "Voice unavailable: " + message + " Your text reply is ready.",
        ),
    );
  }

  async function api(path: string, options: RequestInit = {}) {
    const r = await fetch("/api" + path, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer " + token,
        ...options.headers,
      },
    });
    if (!r.ok) {
      let message = "Backend request failed.";
      try {
        const d = await r.json();
        message =
          typeof d.detail === "string" ? d.detail : "Check the form values.";
      } catch {}
      throw new Error(message);
    }
    return r;
  }
  const loading = useRef(false);
  async function load() {
    if (loading.current || document.hidden) return;
    loading.current = true;
    try {
      const s = await (await api("/status")).json();
      setStatus((old) => (JSON.stringify(old) === JSON.stringify(s) ? old : s));
      setOnline(true);
      const [m, r, n, h, pendingFiles] = await Promise.all(
        [
          "/memories",
          "/reminders",
          "/notifications",
          "/messages?session=" + session,
          "/assistant/pending?session=" + session,
        ].map(async (p) => (await api(p)).json()),
      );
      if (!sending.current)
        setFilePlans((old) =>
          JSON.stringify(old) === JSON.stringify(pendingFiles)
            ? old
            : pendingFiles,
        );
      setMemories((old) =>
        JSON.stringify(old) === JSON.stringify(m) ? old : m,
      );
      setReminders((old) =>
        JSON.stringify(old) === JSON.stringify(r) ? old : r,
      );
      setNotices((old) =>
        JSON.stringify(old) === JSON.stringify(n) ? old : n,
      );
      if (!sending.current)
        setMessages((old) =>
          JSON.stringify(old) === JSON.stringify(h) ? old : h,
        );
    } catch {
      setOnline(false);
      setStatus(null);
    } finally {
      loading.current = false;
    }
  }
  useEffect(() => {
    load();
    const timer = setInterval(load, 15000);
    const visible = () => {
      if (!document.hidden) void load();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [token]);
  useEffect(()=>{window.scrollTo(0,0)},[view,focus]);
  useEffect(() => {
    document.documentElement.dataset.focus = String(focus);
    localStorage.setItem("bujji-focus", String(focus));
  }, [focus]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, filePlans.length, busy]);
  useEffect(
    () => () => {
      recognition.current?.abort();
      playback.current?.stop();
      abort.current?.abort();
      sttAbort.current?.abort();
    },
    [],
  );
  async function act(action: () => Promise<void>) {
    setError("");
    try {
      await action();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    }
  }
  async function send(text = input) {
    if (!text.trim() || busy || sending.current || fileConfirmationBusy.current)
      return;
    setVoiceDraft("");
    stopVoice();
    setInput("");
    setError("");
    setView("chat");
    setBusy(true);
    sending.current = true;
    const controller = new AbortController();
    abort.current = controller;
    setMessages((m) => [...m, { role: "user", content: text }]);
    setToolEvents([]);
    const allowFileOCR = fileOCR;
    setFileOCR(false);
    try {
      let d: { text: string; provider?: string };
      const fileAgent = !!status?.file_assistant?.enabled;
      if (fileAgent || collaborate) {
        setStages([]);
        const response = await api(fileAgent ? "/assistant" : "/focus", {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            message: text,
            session,
            task,
            provider,
            focus: collaborate,
            collaborate,
            cloud_ocr: allowFileOCR,
          }),
        });
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "",
          final = "", resultProvider = "";
        while (true) {
          const chunk = await reader.read();
          buffer += decoder.decode(chunk.value, { stream: !chunk.done });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            if (!line.trim()) continue;
            const event = JSON.parse(line);
            if (event.type === "error") throw new Error(event.message);
            if (event.type === "tool")
              setToolEvents((current) => [
                ...current.filter((item) => item.step !== event.step),
                event,
              ]);
            if (event.type === "stage")
              setStages((current) => [
                ...current.filter((item) => item.role !== event.role),
                event,
              ]);
            if (event.type === "result") {
              final = event.text; resultProvider = event.provider || "";
              if (event.pending) setFilePlans(event.pending);
            }
          }
          if (chunk.done) break;
        }
        if (!final)
          throw new Error(
            "The assistant run ended without a complete result. Any prepared approvals will appear after refresh.",
          );
        d = { text: final, provider: resultProvider };
      } else {
        setStages([]);
        d = await (
          await api("/chat", {
            method: "POST",
            signal: controller.signal,
            body: JSON.stringify({
              message: text,
              session,
              task,
              provider,
              focus: collaborate,
            }),
          })
        ).json();
      }
      setMessages((m) => [...m, { role: "assistant", content: d.text, provider: d.provider }]);
      if (speakEnabled.current && !document.hidden && !microphoneActive.current)
        void readReply(d.text);
    } catch (e) {
      setStages((current) =>
        current.map((stage) =>
          stage.status === "running"
            ? {
                ...stage,
                status:
                  (e as Error).name === "AbortError" ? "cancelled" : "failed",
                error:
                  (e as Error).name === "AbortError"
                    ? "Cancelled before this stage produced an output."
                    : (e as Error).message,
              }
            : stage,
        ),
      );
      if ((e as Error).name === "AbortError")
        setError(
          "Stopped. No further file tools or model stages will start. An already approved action may finish; requests already received by a provider may consume quota.",
        );
      else {
        setInput(text);
        setError((e as Error).message);
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }
  async function confirmFilePlan(id: string, confirmed: boolean) {
    if (fileConfirmationBusy.current) return;
    fileConfirmationBusy.current = true;
    setConfirmingFile(true);
    setError("");
    try {
      const result = await (
        await api("/assistant/approvals/" + id, {
          method: "POST",
          body: JSON.stringify({ session, confirmed }),
        })
      ).json();
      setFilePlans((current) => current.filter((plan) => plan.id !== id));
      setMessages((current) => [
        ...current,
        { role: "assistant", content: result.text },
      ]);
      await load();
    } catch (error) {
      setError((error as Error).message);
      await load();
    } finally {
      fileConfirmationBusy.current = false;
      setConfirmingFile(false);
    }
  }
  submitVoice.current = send;
  async function mic() {
    shortTalkRef.current?.end();
    setShortActive(false);
    if (transcribing) return;
    if (listening) {
      recognition.current?.stop();
      return;
    }
    if (!online) {
      setError("Connect to Bujji before recording.");
      return;
    }
    setError("");
    stopVoice();
    microphoneActive.current = true;
    if (!recognition.current) recognition.current = new VoiceCapture();
    await recognition.current.start(
      async (blob) => {
        microphoneActive.current = true;
        setTranscribing(true);
        const controller = new AbortController();
        sttAbort.current = controller;
        try {
          const result = await (
            await api(
              "/speech/transcribe?language=" + encodeURIComponent(language),
              {
                method: "POST",
                signal: controller.signal,
                headers: { "Content-Type": blob.type },
                body: blob,
              },
            )
          ).json();
          if (!controller.signal.aborted && !document.hidden) {
            const transcript = String(result.text || "").trim();
            setView("chat");
            if (transcript) {
              setInput(transcript);
              setVoiceDraft(transcript);
              if (!focusRef.current) {
                setVoiceDraft("");
                microphoneActive.current = false;
                setTranscribing(false);
                await submitVoice.current(transcript);
              }
            }
          }
        } catch (error) {
          if ((error as Error).name !== "AbortError")
            setError((error as Error).message);
        } finally {
          microphoneActive.current = false;
          setTranscribing(false);
        }
      },
      (active) => {
        microphoneActive.current = active;
        setListening(active);
      },
      (message) => {
        microphoneActive.current = false;
        setError(message);
      },
    );
  }
  const pending = reminders
    .filter((r) => r.status === "pending")
    .sort((a, b) => a.due.localeCompare(b.due));
  const userName=status?.profile?.name||"";
  const refreshProfile=()=>{void api("/status").then(r=>r.json()).then(setStatus);};
  const activeProvider =
    provider === "auto" ? task === "auto" ? "Auto task" : status?.routes[task] || "not configured" : provider;
  const formatDate = (d: string) =>
    new Date(d).toLocaleString("en-IN", {
      timeZone: status?.timezone || "Asia/Kolkata",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  async function toggleWorkMode(){shortTalkRef.current?.end();setShortActive(false);recognition.current?.abort();sttAbort.current?.abort();microphoneActive.current=false;setListening(false);setTranscribing(false);stopVoice();if(focus){try{const d=await(await api('/work-focus')).json();if(d.active?.status==='running')await api('/work-focus',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'pause'})});}catch(e){setError((e as Error).message)}}setView('overview');setFocus(!focus);}
  const nav: [View, React.ReactNode][] = [
    ["overview", <LayoutDashboard size={18} />],
    ["chat", <MessageSquare size={18} />],
    ["memory", <BrainCircuit size={18} />],
    ["reminders", <Bell size={18} />],
    ["devices", <Command size={18} />],
  ];
  return (
    <div className="shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setView("overview");
          }}
        >

          <span>
            bujji<span className="brand-dot">.</span>

          </span>
        </a>

        <nav>
          {nav.map(([key, icon]) => (
            <button
              key={key}
              className={view === key ? "nav-item active" : "nav-item"}
              onClick={() => setView(key)}
            >
              {icon}
              <span>{labels[key]}</span>
              {key === "reminders" && pending.length > 0 && (
                <b>{pending.length}</b>
              )}
            </button>
          ))}
        </nav>
        <div className="side-divider" />
        <button
          className={"focus-card " + (focus ? "on" : "")}
          onClick={()=>void toggleWorkMode()}
        >
          <div>
            <Focus size={20} />
            <span>Focus mode</span>
            <span className="switch">
              <i />
            </span>
          </div>
        </button>
        <div className="sidebar-bottom">
          {!online && token && <p className="backend-state" role="status">Backend offline</p>}
          <button className="nav-item" onClick={() => setSettings(true)}>
            <Settings2 size={18} />
            Settings
          </button>
          <div className="workspace-profile"><span>{userName.slice(0,1).toUpperCase()||"B"}</span><div>{userName||"Your workspace"}<small>Personal workspace</small></div><i className={online?"online":""}/></div>
        </div>
      </aside>
      <div className="main-shell">
        <main>
          {!(view === "overview" && focus) && <div className="page-title">
            <div>
              <h1>{view === "overview" ? <>Good {clock.getHours() < 12 ? "morning" : clock.getHours() < 17 ? "afternoon" : "evening"},<br/><span className="greeting-name">{userName||"there"}</span></> : labels[view]}<span className="title-dot">.</span></h1>{view==="overview"&&<p>A clear mind. A trusted companion. Let's make today count.</p>}
            </div>
            <div className="page-live"><button onClick={()=>setView("devices")} className="device-status"><i className={online?"online":""}/><Laptop size={16}/>{online?"Laptop online":"Laptop offline"}</button><button className="notice-button" aria-label="Notifications" onClick={()=>setView("reminders")}><Bell size={21}/>{notices.some(n=>!n.read)&&<i/>}</button><LiveClock /></div>
          </div>}
          {(listening || transcribing) && (
            <div role="status" className="pair-banner">
              {listening
                ? "Listening · 3 seconds of quiet to send"
                : "Transcribing…"}
            </div>
          )}
          {voiceDraft && (
            <div className="pair-banner" role="status">
              <span>Voice transcript: {voiceDraft}</span>
              <button
                onClick={() => {
                  setVoiceDraft("");
                  void send(input);
                }}
              >
                Confirm and send
              </button>
              <button onClick={() => setVoiceDraft("")}>Keep as draft</button>
            </div>
          )}
          {speechStatus && (
            <div className="pair-banner" role="status">
              <Volume2 size={16} />
              <span>{speechStatus}</span>
              <button type="button" onClick={stopVoice}>
                Stop voice
              </button>
            </div>
          )}
          {error && (
            <div role="alert" className="error">
              <CircleHelp size={17} />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {!token && (
            <div className="pair-banner">
              <ShieldCheck size={18} />
              <span>
                Connect to your laptop backend.
              </span>
              <button onClick={() => setSettings(true)}>
                Connect <ArrowUpRight size={14} />
              </button>
            </div>
          )}
          {view === "overview" && focus ? <DeepFocus api={api} clock={<LiveClock/>}/> : view === "overview" ? (
            <>
              <div className="dashboard-grid">
                <section className="panel core-panel">
                  <div className="panel-heading">
                    <span>
                      <AudioLines size={20} /> BUJJI CORE
                    </span>
                    <span className="tiny-label">
                      {focus ? "FOCUS PROTOCOL" : "BESTIE MODE"}
                      <i />
                    </span>
                  </div>
                  <div className={"reactor " + (listening ? "listening" : "")}>
                    <div className="orbit orbit-one" />
                    <div className="orbit orbit-two" />
                    <div className="orb" role="img" aria-label={listening ? "Listening" : busy ? "Thinking" : "Bujji orb"}><div className="orb-inner" /></div>
                  </div>
                  <div className="core-copy">
                    <h2>
                      {focus ? "One thing at a time." : "What’s on your mind?"}
                    </h2><p>A question, a big idea, or just your day. I'm listening.</p>
                  </div>
                  <div className="core-actions">
                    <button
                      className={
                        "talk-button " + (listening ? "listening" : "")
                      }
                      onClick={mic}
                    >
                      {listening ? <Square size={18} /> : <Mic size={18} />}{" "}
                      {listening ? "Stop listening" : "Talk to Bujji"}
                    </button>
                    <button className="secondary type-instead" onClick={() => setView("chat")}><Keyboard size={17}/>Type instead</button>
                    <button
                      className="text-button"
                      disabled={!online || busy || transcribing}
                      onClick={() => {
                        if(shortActive) { shortTalkRef.current?.end(); setShortActive(false); return; }
                        recognition.current?.abort(); sttAbort.current?.abort();
                        microphoneActive.current=false; setListening(false); setTranscribing(false); stopVoice(); setShortActive(true);
                      }}
                    >
                      {shortActive ? "End short talk" : "Short talk"} <MessageSquare size={15} />
                    </button>
                  </div>
                  <div className="hero-utilities"><button onClick={()=>setView("reminders")}><Bell size={16}/> Remind me</button><button onClick={()=>{setView("chat");setInput("Find a file in my Downloads");}}><Globe2 size={16}/> Find something</button><button onClick={()=>{setView("chat");setInput("Help me plan my day.");}}><Sparkles size={16}/> Plan my day</button><div className="computer-launch">
                    <button disabled={!window.bujjiDesktop || !online} onClick={async () => {
                      shortTalkRef.current?.end();setShortActive(false);recognition.current?.abort();sttAbort.current?.abort();microphoneActive.current=false;setListening(false);setTranscribing(false);stopVoice();
                      try { await window.bujjiDesktop?.openComputer(); } catch(e) { setError((e as Error).message); }
                    }}><Command size={16}/> Control my computer</button>

                  </div>
                  </div>
                  {shortActive && <ShortTalkPanel ref={shortTalkRef} api={api} provider={provider} language={language} onClose={() => setShortActive(false)} />}
                </section>
                <div className="right-stack">
                  <section className="panel day-panel">
                    <div className="panel-heading">
                      <span>
                        <Bell size={14} /> NEXT REMINDER
                      </span>

                    </div>
                    <div className="day-heading">
                      <h2>Reminders</h2>
                      <span>{pending.length} UPCOMING</span>
                    </div>
                    {pending.length ? (
                      pending.slice(0, 1).map((r) => (
                        <div key={r.id} className="reminder-preview">
                          <span className="square-dot" />
                          <div>
                            <strong>{r.title}</strong>
                            <small>{formatDate(r.due)}</small>
                          </div>
                          <ChevronRight size={15} />
                        </div>
                      ))
                    ) : (
                      <div className="empty-state">
                        <span className="empty-icon">
                          <CalendarCheck size={42} />
                        </span>
                        <strong>No upcoming reminders.</strong>

                      </div>
                    )}
                    <button
                      className="panel-link"
                      onClick={() => setView("reminders")}
                    >
                      Open reminders <ArrowUpRight size={15} />
                    </button>
                  </section>
                  <section className="panel memory-panel">
                    <div className="panel-heading">
                      <span>
                        <BrainCircuit size={14} /> MEMORY
                      </span>
                      <span className="tiny-label">
                        {String(memories.length).padStart(2, "0")} SAVED
                      </span>
                    </div>

                    <p>
                      {memories[0]?.content ||
                        "No saved memories."}
                    </p>
                    <button
                      className="panel-link"
                      onClick={() => setView("memory")}
                    >
                      Open memory <ArrowUpRight size={15} />
                    </button>
                  </section>
                  <section className="panel connected-panel"><div className="panel-heading"><span><Command size={16}/> Connected devices</span></div><button onClick={()=>setView("devices")}><span className={online?"device-dot online":"device-dot"}/><span>This laptop<small>{online?"Bujji running":"Backend offline"}</small></span><ChevronRight size={17}/></button><small>Manage paired phones in Devices.</small></section>
                </div>
              </div>
            </>
          ) : view === "chat" ? (
            <section className="panel chat-panel">
              <div className="chat-toolbar">
                <div>
                  <select
                    aria-label="Task category"
                    value={task}
                    onChange={(e) => setTask(e.target.value)}
                  >
                    <option value="auto">Auto task</option><option value="daily">Daily life</option>
                    <option value="study">Study</option>
                    <option value="coding">Coding</option><option value="research">Web research</option><option value="writing">Writing</option><option value="analysis">Analysis</option>
                  </select>
                  <select
                    aria-label="AI provider"
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    <option value="auto">Auto route</option>
                    <option value="gemini">Gemini</option>
                    <option value="groq">Groq</option>
                    <option value="ollama">Ollama</option><option value="openai">OpenAI</option><option value="anthropic">Claude</option><option value="perplexity">Perplexity</option>
                  </select>
                </div>
              </div>
              {status?.file_assistant?.available && (
                <details className="chat-tool-options"><summary>Tools</summary><div className="chat-file-controls">
                  <label>
                    <input
                      type="checkbox"
                      checked={!!status.file_assistant.enabled}
                      disabled={busy || confirmingFile}
                      onChange={(e) => {
                        const enabled = e.target.checked;
                        void act(async () => {
                          const next = await (
                            await api("/assistant/access", {
                              method: "POST",
                              body: JSON.stringify({ enabled }),
                            })
                          ).json();
                          setStatus((old) =>
                            old ? { ...old, file_assistant: next } : old,
                          );
                          if (!enabled) setFilePlans([]);
                        });
                      }}
                    />{" "}
                    File access
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={fileOCR}
                      disabled={busy}
                      onChange={(e) => setFileOCR(e.target.checked)}
                    />{" "}
                    OCR for images / scans
                  </label>
                  <small>File excerpts go to your AI provider. OCR sends images/PDFs to Gemini. Changes need approval.</small>
                </div></details>
              )}
              <details className="focus-workflow"><summary>AI collaboration</summary>
                <div>
                  <label>
                    <input
                      type="checkbox"
                      checked={collaborate}
                      disabled={busy}
                      onChange={(e) => setCollaborate(e.target.checked)}
                    />{" "}
                    Collaborative AI
                  </label>
                </div>
              </details>
              <label className="voice-review"><input type="checkbox" checked={reviewVoice} onChange={e=>{setReviewVoice(e.target.checked);localStorage.setItem("bujji-review-voice",String(e.target.checked))}}/>Review voice before sending</label>
              {stages.length > 0 && (
                <div className="focus-stages" aria-live="polite">
                  <p className="helper">
                    Open a stage to view its output.
                  </p>
                  {stages.map((stage) => (
                    <details key={stage.role}>
                      <summary>
                        <span>
                          {stage.status === "running" && busy
                            ? "◌"
                            : stage.status === "complete"
                              ? "✓"
                              : "—"}{" "}
                          {stage.role.toUpperCase()}
                        </span>
                        <small>
                          {stage.provider}
                          {stage.model ? " / " + stage.model : ""} ·{" "}
                          {stage.status === "running" && !busy
                            ? "stopped"
                            : stage.status}
                        </small>
                      </summary>
                      {stage.artifact && <pre>{stage.artifact}</pre>}
                      {stage.error && (
                        <p className="helper">
                          {stage.error} No output was completed for this stage;
                          later stages did not run.
                        </p>
                      )}
                    </details>
                  ))}
                </div>
              )}
              {toolEvents.length > 0 && (
                <details className="chat-tool-events">
                  <summary>File tool activity</summary>
                  {toolEvents.map((event) => (
                    <p key={event.step}>
                      {event.step}. {event.tool} · {event.status}
                      {event.target ? " · " + event.target : ""}
                      {event.summary ? " — " + event.summary : ""}
                    </p>
                  ))}
                </details>
              )}
              <div className="chat-messages">
                {!messages.length && (
                  <div className="chat-welcome">
                    <div className="mini-orb" />
                    <h2>What’s on your mind?</h2>
                    <p>
                      Ask Bujji.
                    </p>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={"message " + m.role}>
                    <span>
                      {m.role === "user" ? "P" : <AudioLines size={16} />}
                    </span>
                    <div className="message-body">
                      <small>{m.role === "user" ? "YOU" : "BUJJI"}</small>
                      {m.role === "assistant" && (
                        <button
                          type="button"
                          className="read-aloud"
                          aria-label="Read aloud"
                          onClick={() => readReply(m.content)}
                        >
                          <Volume2 size={14} />
                        </button>
                      )}
                      {m.provider && <small className="helper">{aiNames[m.provider] || m.provider}</small>}
                      <p>
                        {m.role === "assistant"
                          ? m.content.split("\n\nVerification: ")[0]
                          : m.content}
                      </p>
                      {m.role === "assistant" &&
                        m.content.includes("\n\nVerification: ") && (
                          <details className="verification-note">
                            <summary>Review & verification status</summary>
                            <p>
                              {m.content
                                .split("\n\nVerification: ")
                                .slice(1)
                                .join("\n\nVerification: ")}
                            </p>
                          </details>
                        )}
                    </div>
                  </div>
                ))}
                {busy && (
                  <div className="thinking">
                    <LoaderCircle size={15} className="spin" /> Bujji is
                    thinking…
                  </div>
                )}
                <FileApprovals
                  plans={filePlans}
                  disabled={
                    busy || confirmingFile || !status?.file_assistant?.enabled
                  }
                  onDecision={(id, confirmed) => {
                    void confirmFilePlan(id, confirmed);
                  }}
                />
                <div ref={end} />
              </div>
              <form
                className="composer"
                onSubmit={(e) => {
                  e.preventDefault();
                  send();
                }}
              >
                <textarea
                  aria-label="Message Bujji"
                  rows={1}
                  placeholder="Tell me what’s on your mind…"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <div className="composer-tools">
                  <div>
                    <button
                      type="button"
                      className={listening ? "selected" : ""}
                      aria-label={
                        listening ? "Stop listening" : "Start microphone"
                      }
                      onClick={mic}
                    >
                      <Mic size={18} />
                    </button>
                    <small>
                      {activeProvider} · {focus ? "FOCUS" : "BESTIE"}
                    </small>
                  </div>
                  {busy ? (
                    <button
                      type="button"
                      className="send"
                      aria-label="Stop waiting"
                      onClick={() => abort.current?.abort()}
                    >
                      <Square size={16} />
                    </button>
                  ) : (
                    <button
                      className="send"
                      aria-label="Send message"
                      disabled={!input.trim()}
                    >
                      <ArrowUp size={19} />
                    </button>
                  )}
                </div>
              </form>
            </section>
          ) : view === "devices" ? (<section className="panel devices-panel"><DevicePairing api={api} /></section>
          ) : view === "memory" ? (
            <section className="panel content-panel">
              <div className="panel-heading">
                <span>
                  <BrainCircuit size={15} /> SAVED MEMORIES
                </span>
                <span>{memories.length} RECORDS</span>
              </div>
              <form
                className="inline-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(async () => {
                    await api(
                      editingMemory === null
                        ? "/memories"
                        : "/memories/" + editingMemory,
                      {
                        method: editingMemory === null ? "POST" : "PUT",
                        body: JSON.stringify({ content: memory }),
                      },
                    );
                    setMemory("");
                    setEditingMemory(null);
                  });
                }}
              >
                <input
                  aria-label="New memory"
                  placeholder="Something you’d like me to remember…"
                  value={memory}
                  onChange={(e) => setMemory(e.target.value)}
                  maxLength={2000}
                  required
                />
                <button className="primary">
                  <Plus size={16} />
                  {editingMemory === null ? "Save memory" : "Save changes"}
                </button>
                {editingMemory !== null && (
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => {
                      setEditingMemory(null);
                      setMemory("");
                    }}
                  >
                    Cancel edit
                  </button>
                )}
              </form>
              {!memories.length && (
                <div className="empty-state">
                  <BrainCircuit size={32} />
                  <h3>No saved memories.</h3>
                  <p>Add a preference or fact above.</p>
                </div>
              )}
              {memories.map((m) => (
                <div className="record" key={m.id}>
                  <div>
                    <p>{m.content}</p>
                    <small>EXPLICITLY SAVED · {formatDate(m.updated)}</small>
                  </div>
                  <button
                    aria-label="Edit memory"
                    onClick={() => {
                      setEditingMemory(m.id);
                      setMemory(m.content);
                    }}
                  >
                    <Settings2 size={16} />
                  </button>
                  <button
                    aria-label="Delete memory"
                    onClick={() => {
                      if (confirm("Forget this memory?"))
                        act(async () => {
                          await api("/memories/" + m.id, { method: "DELETE" });
                        });
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </section>
          ) : (
            <section className="panel content-panel">
              <div className="panel-heading">
                <span>
                  <Bell size={14} /> REMINDERS
                </span>
                <span>ASIA / KOLKATA</span>
              </div>
              <form
                className="reminder-form"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(async () => {
                    await api("/reminders", {
                      method: "POST",
                      body: JSON.stringify({
                        title: remTitle,
                        due,
                        recurrence: repeat,
                      }),
                    });
                    setRemTitle("");
                    setDue("");
                  });
                }}
              >
                <label>
                  What should I remind you?
                  <input
                    value={remTitle}
                    onChange={(e) => setRemTitle(e.target.value)}
                    placeholder="Submit my Java assignment"
                    required
                    maxLength={500}
                  />
                </label>
                <label>
                  Date & time · IST
                  <input
                    type="datetime-local"
                    value={due}
                    onChange={(e) => setDue(e.target.value)}
                    required
                  />
                </label>
                <label>
                  Repeat
                  <select
                    value={repeat}
                    onChange={(e) => setRepeat(e.target.value)}
                  >
                    <option value="none">Once</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                  </select>
                </label>
                <button className="primary">
                  <Plus size={16} />
                  Add reminder
                </button>
              </form>
              <p className="helper">
                When your laptop is off, reminders wait. Missed reminders are
                surfaced once after restart.
              </p>
              {reminders.map((r) => (
                <div className="record" key={r.id}>
                  <Bell size={18} />
                  <div>
                    <p>{r.title}</p>
                    <small>
                      {formatDate(r.due)} · {r.recurrence.toUpperCase()} ·{" "}
                      {r.status.toUpperCase()}
                    </small>
                  </div>
                  {r.status === "pending" && (
                    <button
                      aria-label="Cancel reminder"
                      onClick={() =>
                        act(async () => {
                          await api("/reminders/" + r.id, { method: "DELETE" });
                        })
                      }
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
              ))}
              <h3 className="subheading">Notification history</h3>
              {notices.length ? (
                notices.map((n) => (
                  <div className="record" key={n.id}>
                    <div>
                      <p>{n.content}</p>
                      <small>{formatDate(n.created)}</small>
                    </div>
                    {!n.read && (
                      <button
                        aria-label="Mark read"
                        onClick={() =>
                          act(async () => {
                            await api("/notifications/" + n.id + "/read", {
                              method: "POST",
                            });
                          })
                        }
                      >
                        <Check size={17} />
                      </button>
                    )}
                  </div>
                ))
              ) : (
                <p className="helper">No reminders have fired yet.</p>
              )}
            </section>
          )}
        </main>
      </div>
      <nav className="mobile-nav">
        {nav.map(([key, icon]) => (
          <button
            key={key}
            className={view === key ? "active" : ""}
            onClick={() => setView(key)}
            aria-label={labels[key]}
          >
            {icon}
            <small>
              {key === "overview"
                ? "Home"
                : key === "memory"
                  ? "Memory"
                  : key === "reminders"
                    ? "Remind"
                    : key === "devices" ? "Devices" : "Chat"}
            </small>
          </button>
        ))}
        <button
          onClick={()=>void toggleWorkMode()}
          className={focus ? "active" : ""}
          aria-label="Toggle Focus Mode"
        >
          <Focus size={18} />
          <small>Focus</small>
        </button>
        <button onClick={() => setSettings(true)} aria-label="Settings"><Settings2 size={18}/><small>Settings</small></button>
      </nav>
      {status && !userName && <div className="modal-backdrop"><section role="dialog" aria-modal="true" aria-labelledby="welcome-title" className="modal"><h2 id="welcome-title">Make Bujji yours.</h2><p>Choose a name for your workspace. AI keys can be added later in Settings.</p><ProfileForm api={api} name="" onSaved={refreshProfile}/></section></div>}
      {settings && (
        <div className="modal-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="settings-title"
            className="modal"
          >
            <button
              className="modal-close"
              aria-label="Close settings"
              onClick={() => setSettings(false)}
            >
              <X />
            </button>
            <ShieldCheck className="modal-symbol" />
            <div className="eyebrow">BUJJI</div>
            <h2 id="settings-title">Settings</h2>
            <p>
              Run the backend on your laptop, then enter the pairing token from
              your local <code>.env</code>. It stays in this tab’s session
              storage.
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                sessionStorage.setItem("bujji-token", draftToken);
                setToken(draftToken);
                setDraftToken("");
                setSettings(false);
                setError("");
              }}
            >
              <label>
                Pairing token
                <input
                  type="password"
                  value={draftToken}
                  onChange={(e) => setDraftToken(e.target.value)}
                  placeholder="Paste your local token"
                  minLength={32}
                  required
                  autoComplete="off"
                />
              </label>
              <button className="primary">
                Connect securely <ArrowUpRight size={16} />
              </button>
            </form>
            {desktopPrefs && (
              <section className="desktop-settings">
                <h3>Windows desktop</h3>
                <p className="helper">
                  Closing the window keeps reminders running in the tray. Use
                  tray → Quit Bujji to stop. The bundled chime plays separately
                  from Windows toast audio. Your app mute setting and Windows
                  output volume still apply.
                </p>
                <label>
                  <input
                    type="checkbox"
                    checked={desktopPrefs.soundEnabled}
                    onChange={(e) => {
                      window
                        .bujjiDesktop!.setPreferences({
                          soundEnabled: e.target.checked,
                        })
                        .then(setDesktopPrefs)
                        .catch(() =>
                          setError("Could not save sound preference."),
                        );
                    }}
                  />
                  Reminder sounds
                </label>
                <button
                  className="primary"
                  type="button"
                  onClick={() =>
                    window
                      .bujjiDesktop!.testNotification()
                      .then((result) => {
                        setSoundTest(
                          result.sound.ok
                            ? "Chime playback started. If you heard nothing, check the Windows output device and Volume mixer for Bujji/backend audio."
                            : "Chime did not start: " +
                                result.sound.reason +
                                ". Check that Reminder sounds is enabled.",
                        );
                      })
                      .catch(() => setError("Notification test failed."))
                  }
                >
                  Test notification & sound
                </button>
                <button
                  className="text-button"
                  type="button"
                  onClick={() =>
                    window
                      .bujjiDesktop!.testSound()
                      .then((result) =>
                        setSoundTest(
                          result.ok
                            ? "Chime playback started. Did you hear it? If not, check your Windows output device and Volume mixer."
                            : "Sound test: " + result.reason,
                        ),
                      )
                      .catch(() =>
                        setSoundTest("Sound test failed to reach the backend."),
                      )
                  }
                >
                  Test sound only
                </button>
                {soundTest && (
                  <p className="helper" role="status">
                    {soundTest}
                  </p>
                )}
                <label>
                  <input
                    type="checkbox"
                    disabled={!desktopPrefs.packaged}
                    checked={desktopPrefs.startAtLogin}
                    onChange={(e) => {
                      window
                        .bujjiDesktop!.setPreferences({
                          startAtLogin: e.target.checked,
                        })
                        .then(setDesktopPrefs)
                        .catch(() =>
                          setError("Could not change sign-in launch."),
                        );
                    }}
                  />
                  Launch at Windows sign-in
                </label>
                {!desktopPrefs.packaged && (
                  <p className="helper">
                    Sign-in launch is available after installing the Windows
                    build.
                  </p>
                )}
              </section>
            )}
            <section className="desktop-settings">
              <h3>Bujji’s voice</h3>
              <p className="helper">
                Read aloud plays a reply. The microphone and Stop voice interrupt playback. Transcription and reply speech use separate providers.
              </p>
              <label>
                <input
                  type="checkbox"
                  checked={speak}
                  onChange={(e) => {
                    speakEnabled.current = e.target.checked;
                    setSpeak(e.target.checked);
                    stopVoice();
                  }}
                />
                Automatically speak replies
              </label>
            </section>
            <label className="language-label">
              Speech recognition language
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              >
                <option value="en-IN">English · India</option>
                <option value="te-IN">తెలుగు · Telugu</option>
              </select>
            </label>
            <p className="helper">
              Tap the microphone to record, then tap again to stop (20 seconds
              maximum). The clip is sent to your configured Gemini/Groq
              transcription provider and placed in the composer for review; it
              is not automatically sent as chat or saved as a recording. Spoken
              reply quality is a separate setting.
            </p>
            <ProfileForm api={api} name={userName} onSaved={refreshProfile}/>
            {window.bujjiDesktop?.openSettingsFolder&&<button className="text-button" onClick={()=>void window.bujjiDesktop!.openSettingsFolder()}>Open configuration folder</button>}
            <AIRouting api={api} onSaved={()=>{api("/status").then(r=>r.json()).then(setStatus).catch(()=>{});}} />
            <div className="provider-list">
              {Object.keys(aiNames).map((p) => (
                <div key={p}>
                  <span>{aiNames[p]}</span>
                  <small>
                    {status?.providers[p] ? "CONFIGURED" : "NOT CONFIGURED"}
                  </small>
                </div>
              ))}
            </div>
            <p className="helper">
              Provider keys and models are configured in your local .env.
            </p>
            {token && (
              <button
                className="text-button"
                onClick={() => {
                  sessionStorage.removeItem("bujji-token");
                  setToken("");
                  setSettings(false);
                }}
              >
                Disconnect this tab
              </button>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {new URLSearchParams(location.search).get("computer")==="1" ? <ComputerWidget/> : <App />}
  </React.StrictMode>,
);
