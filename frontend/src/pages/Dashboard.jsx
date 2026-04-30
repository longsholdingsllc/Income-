import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { motion } from "framer-motion";
import { ArrowUpRight, Wallet, TrendingUp, Banknote, Target } from "lucide-react";
import {
  ResponsiveContainer, LineChart, Line, Tooltip, XAxis, YAxis, CartesianGrid,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { useAuth } from "../lib/auth";
import { Link } from "react-router-dom";

const CHART_COLORS = ["#00D084", "#059669", "#34D399", "#A7F3D0", "#064E3B", "#10B981"];

function Stat({ label, value, hint, icon: Icon, testId }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
      className="card p-6"
      data-testid={testId}
    >
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs uppercase tracking-[0.15em] text-[#A3B3AA]">{label}</div>
        {Icon && <Icon size={16} strokeWidth={1.5} className="text-[#00D084]" />}
      </div>
      <div className="number-hero text-5xl sm:text-6xl">{value}</div>
      {hint && <div className="mt-3 text-xs text-[#A3B3AA]">{hint}</div>}
    </motion.div>
  );
}

const fmt = (n) => "$" + Number(n || 0).toLocaleString("en-US", { maximumFractionDigits: 0 });
const fmt2 = (n) => "$" + Number(n || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const CAT_LABEL = {
  affiliate: "Affiliate", dividends: "Dividends", rentals: "Rentals",
  digital_products: "Digital Products", crypto_staking: "Crypto Staking",
  print_on_demand: "Print-on-Demand", royalties: "Royalties",
  interest: "Interest", ads: "Ads", other: "Other",
};

export default function Dashboard() {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get("/dashboard/summary")
      .then(r => setData(r.data))
      .catch(e => setErr(e.response?.data?.detail || "Failed to load"));
  }, []);

  if (err) return <div className="p-10 text-[#EF4444]" data-testid="dashboard-error">{err}</div>;
  if (!data) return <div className="p-10 text-[#A3B3AA]" data-testid="dashboard-loading">Loading your cockpit…</div>;

  const pieData = (data.breakdown || []).map(b => ({ name: CAT_LABEL[b.category] || b.category, value: b.amount }));

  return (
    <div className="p-6 sm:p-10 max-w-7xl" data-testid="dashboard-page">
      <div className="flex items-end justify-between mb-10 flex-wrap gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-[#00D084] mb-2">Good to see you, {user?.name?.split(" ")[0] || "friend"}</div>
          <h1 className="font-serif text-4xl sm:text-5xl tracking-tighter">Your autopilot</h1>
        </div>
        <Link to="/app/streams" className="btn-primary" data-testid="dashboard-add-stream-btn">
          Log income <ArrowUpRight size={16} />
        </Link>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
        <Stat label="This month" value={fmt(data.monthly_income)} hint="passive income received" icon={Banknote} testId="stat-monthly" />
        <Stat label="All-time earned" value={fmt(data.total_earned)} hint="across all streams" icon={TrendingUp} testId="stat-total-earned" />
        <Stat label="Invested" value={fmt(data.total_invested)} hint="initial capital deployed" icon={Wallet} testId="stat-invested" />
        <Stat label="Active streams" value={data.active_streams} hint="compounding right now" icon={Target} testId="stat-streams" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-8">
        <div className="card p-6 lg:col-span-2" data-testid="trend-card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-sans text-lg font-semibold">Last 6 months</h3>
              <div className="text-xs text-[#A3B3AA]">Passive income trend</div>
            </div>
          </div>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={data.trend}>
                <CartesianGrid stroke="#173627" vertical={false} />
                <XAxis dataKey="month" stroke="#A3B3AA" fontSize={12} />
                <YAxis stroke="#A3B3AA" fontSize={12} tickFormatter={(v) => `$${v}`} />
                <Tooltip
                  contentStyle={{ background: "#0C2419", border: "1px solid #173627", borderRadius: 8, color: "#F4F0E6" }}
                  formatter={(v) => fmt2(v)}
                />
                <Line type="monotone" dataKey="income" stroke="#00D084" strokeWidth={2} dot={{ fill: "#00D084", r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-6" data-testid="breakdown-card">
          <h3 className="font-sans text-lg font-semibold mb-1">Income mix</h3>
          <div className="text-xs text-[#A3B3AA] mb-4">By category (all-time)</div>
          {pieData.length === 0 ? (
            <div className="text-sm text-[#A3B3AA] py-12 text-center">Log an income entry to see the mix.</div>
          ) : (
            <div style={{ width: "100%", height: 260 }}>
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={pieData} innerRadius={60} outerRadius={90} paddingAngle={3} dataKey="value">
                    {pieData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "#0C2419", border: "1px solid #173627", borderRadius: 8, color: "#F4F0E6" }}
                    formatter={(v) => fmt2(v)}
                  />
                  <Legend wrapperStyle={{ color: "#A3B3AA", fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Goal + Recent */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="card p-6" data-testid="goal-card">
          <h3 className="font-sans text-lg font-semibold mb-1">Monthly goal</h3>
          <div className="text-xs text-[#A3B3AA] mb-4">Progress toward your target</div>
          {data.goal.monthly_target > 0 ? (
            <>
              <div className="number-hero text-4xl">{fmt(data.monthly_income)} <span className="text-[#A3B3AA] text-2xl font-serif">/ {fmt(data.goal.monthly_target)}</span></div>
              <div className="w-full h-2 rounded-full bg-[#0C2419] mt-4 overflow-hidden">
                <div className="h-full bg-[#00D084] transition-all" style={{ width: `${Math.min(100, data.goal.progress_percent)}%` }} />
              </div>
              <div className="text-xs text-[#A3B3AA] mt-2">{data.goal.progress_percent}% of the way</div>
              {data.goal.freedom_number > 0 && (
                <div className="mt-6 text-sm text-[#A3B3AA]">
                  Freedom number: <span className="text-[#F4F0E6] font-semibold">{fmt(data.goal.freedom_number)}/mo</span>
                </div>
              )}
            </>
          ) : (
            <div>
              <div className="text-sm text-[#A3B3AA] mb-4">No goal yet. Set one to track progress.</div>
              <Link to="/app/goals" className="btn-secondary" data-testid="goal-set-btn">Set goal</Link>
            </div>
          )}
        </div>

        <div className="card p-6 lg:col-span-2" data-testid="recent-card">
          <h3 className="font-sans text-lg font-semibold mb-1">Recent income</h3>
          <div className="text-xs text-[#A3B3AA] mb-4">Latest entries across all streams</div>
          {data.recent_entries.length === 0 ? (
            <div className="text-sm text-[#A3B3AA] py-10 text-center">No entries yet. Add a stream and log income.</div>
          ) : (
            <div className="divide-y divide-[#173627]">
              {data.recent_entries.map(e => (
                <div key={e.id} className="flex items-center justify-between py-3" data-testid={`recent-entry-${e.id}`}>
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">{e.stream_name}</div>
                    <div className="text-xs text-[#A3B3AA] truncate">{new Date(e.date).toLocaleDateString()} · {e.note || "—"}</div>
                  </div>
                  <div className="number-hero text-2xl shrink-0">+{fmt2(e.amount)}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
