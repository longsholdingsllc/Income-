import React, { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Plus, MessageSquare } from "lucide-react";
import { useBilling } from "../lib/billing";

const COACH_AVATAR = "https://static.prod-images.emergentagent.com/jobs/2d82098c-b289-4a69-883e-f08e7335e324/images/237bc905f8e7e878395d8dbc1a6e866d4260767447fadb0ddbb6b149766374b2.png";

const SUGGESTIONS = [
  "Give me a 90-day passive income roadmap for a beginner with $1,000",
  "Review my current streams and tell me what's missing",
  "What should I do this week to hit my monthly goal?",
  "Rank affiliate vs. digital products for my situation",
];

export default function Coach() {
  const { refresh: refreshBilling } = useBilling();
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef(null);

  const loadSessions = async () => {
    const { data } = await api.get("/ai/coach/sessions");
    setSessions(data);
  };
  useEffect(() => { loadSessions(); }, []);

  const loadMessages = async (sid) => {
    const { data } = await api.get(`/ai/coach/sessions/${sid}/messages`);
    setMessages(data);
    setActiveId(sid);
  };

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  const send = async (text) => {
    const msg = (text ?? input).trim();
    if (!msg || sending) return;
    setInput("");
    setSending(true);

    const nowIso = new Date().toISOString();
    setMessages((m) => [...m, { role: "user", content: msg, created_at: nowIso }]);

    try {
      const { data } = await api.post("/ai/coach/chat", { session_id: activeId, message: msg });
      if (!activeId) setActiveId(data.session_id);
      setMessages((m) => [...m, { role: "assistant", content: data.reply, created_at: new Date().toISOString() }]);
      loadSessions();
    } catch (e) {
      const status = e.response?.status;
      const detail = e.response?.data?.detail || "Coach is unavailable right now. Try again in a moment.";
      const friendly = status === 402
        ? `${detail} Upgrade to Pro for unlimited coaching.`
        : (status === 502 || status === 503 || status === 504)
          ? "Our AI is briefly throttled. Please try again in ~30 seconds."
          : detail;
      setMessages((m) => [...m, { role: "assistant", content: friendly, created_at: new Date().toISOString() }]);
    } finally { setSending(false); refreshBilling(); }
  };

  const newChat = () => { setActiveId(null); setMessages([]); };

  return (
    <div className="flex h-screen" data-testid="coach-page">
      {/* Sessions sidebar */}
      <aside className="w-64 shrink-0 border-r border-[#173627] bg-[#04120C] flex flex-col">
        <div className="p-4 border-b border-[#173627]">
          <button onClick={newChat} className="btn-primary w-full justify-center" data-testid="coach-new-chat-btn">
            <Plus size={16} /> New chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {sessions.length === 0 ? (
            <div className="text-xs text-[#A3B3AA] p-3">No conversations yet.</div>
          ) : sessions.map((s) => (
            <button
              key={s.id}
              onClick={() => loadMessages(s.id)}
              className={`w-full text-left p-3 rounded-lg mb-1 text-sm truncate flex items-center gap-2 ${activeId === s.id ? "bg-[#0C2419] text-[#F4F0E6]" : "text-[#A3B3AA] hover:bg-[#0C2419]/60"}`}
              data-testid={`coach-session-${s.id}`}
            >
              <MessageSquare size={14} className="shrink-0" />
              <span className="truncate">{s.title}</span>
            </button>
          ))}
        </div>
      </aside>

      {/* Chat */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="px-6 py-4 border-b border-[#173627] flex items-center gap-3">
          <img src={COACH_AVATAR} alt="" className="w-9 h-9 rounded-full bg-[#0C2419] object-cover" />
          <div>
            <div className="font-sans font-semibold">Autopilot Coach</div>
            <div className="text-xs text-[#A3B3AA]">Claude Sonnet 4.5 · always on</div>
          </div>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 space-y-4" data-testid="coach-messages">
          {messages.length === 0 && (
            <div className="max-w-2xl mx-auto pt-8">
              <div className="text-center mb-8">
                <img src={COACH_AVATAR} alt="" className="w-16 h-16 rounded-full mx-auto mb-4" />
                <h2 className="font-serif text-4xl tracking-tighter mb-2">How can I help you today?</h2>
                <p className="text-[#A3B3AA] text-sm">Start fresh or try a prompt:</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {SUGGESTIONS.map((s, i) => (
                  <button key={i} onClick={() => send(s)} className="card p-4 text-left text-sm text-[#F4F0E6]" data-testid={`coach-suggestion-${i}`}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <AnimatePresence initial={false}>
            {messages.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                data-testid={`coach-msg-${i}`}
              >
                <div className={`max-w-2xl px-4 py-3 rounded-2xl whitespace-pre-wrap text-sm leading-relaxed ${
                  m.role === "user"
                    ? "bg-[#00D084] text-[#04120C]"
                    : "bg-[#0C2419] border border-[#173627] text-[#F4F0E6]"
                }`}>{m.content}</div>
              </motion.div>
            ))}
          </AnimatePresence>

          {sending && (
            <div className="flex justify-start" data-testid="coach-typing">
              <div className="max-w-2xl px-4 py-3 rounded-2xl bg-[#0C2419] border border-[#173627] text-[#A3B3AA] text-sm">
                <span className="inline-block animate-pulse">Coach is thinking…</span>
              </div>
            </div>
          )}
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send(); }} className="p-4 border-t border-[#173627] flex gap-2" data-testid="coach-input-form">
          <input
            className="input flex-1"
            placeholder="Ask your coach anything…"
            value={input}
            onChange={e=>setInput(e.target.value)}
            disabled={sending}
            data-testid="coach-input"
          />
          <button type="submit" className="btn-primary" disabled={sending || !input.trim()} data-testid="coach-send-btn">
            <Send size={16} /> Send
          </button>
        </form>
      </div>
    </div>
  );
}
