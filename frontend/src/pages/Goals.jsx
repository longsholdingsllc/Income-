import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Target, Save } from "lucide-react";

const fmt = (n) => "$" + Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });

export default function Goals() {
  const [goal, setGoal] = useState({ monthly_target: 0, freedom_number: 0 });
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/goals").then(r => setGoal({
      monthly_target: r.data.monthly_target || 0,
      freedom_number: r.data.freedom_number || 0,
    })).finally(() => setLoading(false));
  }, []);

  const save = async (e) => {
    e.preventDefault();
    await api.post("/goals", {
      monthly_target: Number(goal.monthly_target),
      freedom_number: Number(goal.freedom_number),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="p-6 sm:p-10 max-w-3xl" data-testid="goals-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.2em] text-[#00D084] mb-2">North star</div>
        <h1 className="font-serif text-4xl sm:text-5xl tracking-tighter">Define freedom.</h1>
        <p className="text-[#A3B3AA] mt-2 max-w-xl">Your monthly target keeps you focused. Your freedom number is the finish line.</p>
      </div>

      {loading ? <div className="text-[#A3B3AA]">Loading…</div> : (
        <form onSubmit={save} className="card p-8" data-testid="goals-form">
          <label className="label">Monthly passive income target</label>
          <div className="relative mb-6">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[#A3B3AA]">$</span>
            <input className="input pl-8" type="number" min={0} step="50" value={goal.monthly_target} onChange={e=>setGoal({...goal, monthly_target: e.target.value})} data-testid="goal-monthly-input" />
          </div>

          <label className="label">Freedom number (monthly passive to quit your day job)</label>
          <div className="relative mb-6">
            <span className="absolute left-4 top-1/2 -translate-y-1/2 text-[#A3B3AA]">$</span>
            <input className="input pl-8" type="number" min={0} step="100" value={goal.freedom_number} onChange={e=>setGoal({...goal, freedom_number: e.target.value})} data-testid="goal-freedom-input" />
          </div>

          <div className="flex items-center gap-3">
            <button className="btn-primary" data-testid="goal-save-btn">
              <Save size={16} /> {saved ? "Saved" : "Save goal"}
            </button>
            <Target size={18} className="text-[#00D084]" />
            <span className="text-sm text-[#A3B3AA]">
              Targeting {fmt(goal.monthly_target || 0)}/mo · Freedom at {fmt(goal.freedom_number || 0)}/mo
            </span>
          </div>
        </form>
      )}
    </div>
  );
}
