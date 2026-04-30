import React, { useState } from "react";
import { api } from "../lib/api";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from "recharts";
import { LineChart as LineChartIcon } from "lucide-react";

const fmt = (n) => "$" + Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const fmt2 = (n) => "$" + Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function Simulator() {
  const [form, setForm] = useState({ asset: "S&P 500 ETF", monthly_contribution: 500, apy_percent: 8, years: 20 });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await api.post("/simulator/dca", {
        ...form,
        monthly_contribution: Number(form.monthly_contribution),
        apy_percent: Number(form.apy_percent),
        years: Number(form.years),
      });
      setResult(data);
    } finally { setLoading(false); }
  };

  return (
    <div className="p-6 sm:p-10 max-w-6xl" data-testid="simulator-page">
      <div className="mb-10">
        <div className="text-xs uppercase tracking-[0.2em] text-[#00D084] mb-2">DCA simulator</div>
        <h1 className="font-serif text-4xl sm:text-5xl tracking-tighter">Compound your future.</h1>
        <p className="text-[#A3B3AA] mt-2 max-w-xl">Pick an asset, a monthly contribution, and expected APY. See the full growth curve.</p>
      </div>

      <form onSubmit={run} className="card p-6 mb-8" data-testid="simulator-form">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="label">Asset</label>
            <input className="input" value={form.asset} onChange={e=>setForm({...form, asset: e.target.value})} data-testid="sim-asset-input" />
          </div>
          <div>
            <label className="label">Monthly ($)</label>
            <input className="input" type="number" min={1} value={form.monthly_contribution} onChange={e=>setForm({...form, monthly_contribution: e.target.value})} data-testid="sim-monthly-input" />
          </div>
          <div>
            <label className="label">Expected APY (%)</label>
            <input className="input" type="number" step="0.1" value={form.apy_percent} onChange={e=>setForm({...form, apy_percent: e.target.value})} data-testid="sim-apy-input" />
          </div>
          <div>
            <label className="label">Years</label>
            <input className="input" type="number" min={1} max={50} value={form.years} onChange={e=>setForm({...form, years: e.target.value})} data-testid="sim-years-input" />
          </div>
        </div>
        <button className="btn-primary mt-6" disabled={loading} data-testid="sim-run-btn">
          <LineChartIcon size={16} /> {loading ? "Running…" : "Run simulation"}
        </button>
      </form>

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-8" data-testid="sim-results">
            <div className="card p-6">
              <div className="text-xs uppercase tracking-[0.15em] text-[#A3B3AA] mb-2">Final value</div>
              <div className="number-hero text-4xl">{fmt(result.final_value)}</div>
            </div>
            <div className="card p-6">
              <div className="text-xs uppercase tracking-[0.15em] text-[#A3B3AA] mb-2">Contributed</div>
              <div className="number-hero text-4xl">{fmt(result.total_contributed)}</div>
            </div>
            <div className="card p-6">
              <div className="text-xs uppercase tracking-[0.15em] text-[#A3B3AA] mb-2">Interest earned</div>
              <div className="number-hero text-4xl">{fmt(result.total_interest)}</div>
            </div>
            <div className="card p-6">
              <div className="text-xs uppercase tracking-[0.15em] text-[#A3B3AA] mb-2">Passive /mo at end</div>
              <div className="number-hero text-4xl">{fmt(result.monthly_passive_at_end)}</div>
            </div>
          </div>

          <div className="card p-6">
            <h3 className="font-sans text-lg font-semibold mb-1">Growth curve</h3>
            <div className="text-xs text-[#A3B3AA] mb-4">{result.asset} · {form.years} years · {form.apy_percent}% APY</div>
            <div className="w-full min-h-[360px]" style={{ height: 360 }}>
              <ResponsiveContainer width="100%" height="100%" minHeight={200} minWidth={200} debounce={50}>
                <AreaChart data={result.series}>
                  <defs>
                    <linearGradient id="gValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00D084" stopOpacity={0.6} />
                      <stop offset="100%" stopColor="#00D084" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="gContrib" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#A7F3D0" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#A7F3D0" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#173627" vertical={false} />
                  <XAxis dataKey="month" stroke="#A3B3AA" fontSize={12} tickFormatter={(m) => `${Math.round(m/12)}y`} />
                  <YAxis stroke="#A3B3AA" fontSize={12} tickFormatter={(v) => `$${Math.round(v/1000)}k`} />
                  <Tooltip
                    contentStyle={{ background: "#0C2419", border: "1px solid #173627", borderRadius: 8, color: "#F4F0E6" }}
                    formatter={(v) => fmt2(v)}
                    labelFormatter={(m) => `Month ${m}`}
                  />
                  <Legend wrapperStyle={{ color: "#A3B3AA", fontSize: 12 }} />
                  <Area type="monotone" dataKey="contributed" stroke="#A7F3D0" fill="url(#gContrib)" name="Contributed" />
                  <Area type="monotone" dataKey="value" stroke="#00D084" fill="url(#gValue)" name="Portfolio value" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
