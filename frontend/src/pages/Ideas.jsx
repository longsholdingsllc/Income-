import React, { useState } from "react";
import { api } from "../lib/api";
import { motion } from "framer-motion";
import { Sparkles, Clock, DollarSign, AlertTriangle, Wrench, ArrowRight } from "lucide-react";

export default function Ideas() {
  const [form, setForm] = useState({ skills: "", budget_usd: 500, hours_per_week: 5, risk_tolerance: "medium", interests: "" });
  const [ideas, setIdeas] = useState([]);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setIdeas([]); setLoading(true);
    try {
      const { data } = await api.post("/ai/ideas", {
        ...form, budget_usd: Number(form.budget_usd), hours_per_week: Number(form.hours_per_week)
      });
      setIdeas(data.ideas || []);
    } catch (e2) {
      setErr(e2.response?.data?.detail || "Generation failed");
    } finally { setLoading(false); }
  };

  return (
    <div className="p-6 sm:p-10 max-w-6xl" data-testid="ideas-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.2em] text-[#00D084] mb-2">Powered by Claude Sonnet 4.5</div>
        <h1 className="font-serif text-4xl sm:text-5xl tracking-tighter">AI idea engine</h1>
        <p className="text-[#A3B3AA] mt-2 max-w-xl">Give us your constraints. Get 5 tailored passive-income ideas with step-by-step action plans.</p>
      </div>

      <form onSubmit={submit} className="card p-6 mb-8" data-testid="ideas-form">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <label className="label">Your skills</label>
            <input className="input" placeholder="e.g. React, copywriting, photography" value={form.skills} onChange={e=>setForm({...form, skills: e.target.value})} required data-testid="ideas-skills-input" />
          </div>
          <div>
            <label className="label">Budget (USD)</label>
            <input className="input" type="number" min={0} value={form.budget_usd} onChange={e=>setForm({...form, budget_usd: e.target.value})} required data-testid="ideas-budget-input" />
          </div>
          <div>
            <label className="label">Hours / week</label>
            <input className="input" type="number" min={0} max={80} value={form.hours_per_week} onChange={e=>setForm({...form, hours_per_week: e.target.value})} required data-testid="ideas-hours-input" />
          </div>
          <div>
            <label className="label">Risk tolerance</label>
            <select className="input" value={form.risk_tolerance} onChange={e=>setForm({...form, risk_tolerance: e.target.value})} data-testid="ideas-risk-select">
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div>
            <label className="label">Interests (optional)</label>
            <input className="input" placeholder="e.g. fitness, finance, gaming" value={form.interests} onChange={e=>setForm({...form, interests: e.target.value})} data-testid="ideas-interests-input" />
          </div>
        </div>
        <button className="btn-primary mt-6" disabled={loading} data-testid="ideas-generate-btn">
          <Sparkles size={16} /> {loading ? "Brewing ideas…" : "Generate 5 ideas"}
        </button>
        {err && <div className="text-[#EF4444] text-sm mt-4" data-testid="ideas-error">{err}</div>}
      </form>

      {ideas.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {ideas.map((idea, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.08 }}
              className="card p-6"
              data-testid={`idea-card-${i}`}
            >
              <span className="chip">{idea.category}</span>
              <h3 className="font-serif text-3xl tracking-tighter mt-3 mb-2">{idea.title}</h3>
              <p className="text-sm text-[#A3B3AA] leading-relaxed mb-5">{idea.summary}</p>

              <div className="grid grid-cols-2 gap-3 mb-5">
                <Stat icon={DollarSign} label="Monthly" value={idea.estimated_monthly_income} />
                <Stat icon={Wrench} label="Startup" value={idea.startup_cost} />
                <Stat icon={Clock} label="First $" value={idea.time_to_first_dollar} />
                <Stat icon={AlertTriangle} label="Risk" value={idea.risk} />
              </div>

              <div className="text-xs uppercase tracking-[0.15em] text-[#00D084] mb-2">Action plan</div>
              <ol className="space-y-2 mb-5">
                {idea.action_plan.map((s, k) => (
                  <li key={k} className="flex gap-3 text-sm text-[#F4F0E6]">
                    <span className="font-mono text-[#00D084] shrink-0">{String(k+1).padStart(2,"0")}</span>
                    <span className="text-[#A3B3AA]">{s}</span>
                  </li>
                ))}
              </ol>

              <div className="text-xs uppercase tracking-[0.15em] text-[#00D084] mb-2">Tools</div>
              <div className="flex flex-wrap gap-2">
                {idea.tools_needed.map((t, k) => (
                  <span key={k} className="text-xs px-2.5 py-1 rounded-full bg-[#0C2419] border border-[#173627] text-[#A3B3AA]">{t}</span>
                ))}
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="bg-[#0C2419] border border-[#173627] rounded-lg p-3">
      <div className="flex items-center gap-1.5 text-xs text-[#A3B3AA] mb-1">
        <Icon size={12} /> {label}
      </div>
      <div className="text-sm font-medium text-[#F4F0E6]">{value}</div>
    </div>
  );
}
