import React from "react";
import { NavLink, Outlet, useNavigate, Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useBilling } from "../lib/billing";
import { LayoutDashboard, Wallet, Lightbulb, FileText, LineChart, Bot, Target, LogOut, Sparkles, Infinity as InfinityIcon } from "lucide-react";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true, tid: "nav-dashboard" },
  { to: "/app/streams", label: "Streams", icon: Wallet, tid: "nav-streams" },
  { to: "/app/ideas", label: "AI Ideas", icon: Lightbulb, tid: "nav-ideas" },
  { to: "/app/content", label: "Content", icon: FileText, tid: "nav-content" },
  { to: "/app/simulator", label: "Simulator", icon: LineChart, tid: "nav-simulator" },
  { to: "/app/coach", label: "AI Coach", icon: Bot, tid: "nav-coach" },
  { to: "/app/goals", label: "Goals", icon: Target, tid: "nav-goals" },
  { to: "/app/pricing", label: "Upgrade", icon: Sparkles, tid: "nav-pricing" },
];

function QuotaChip() {
  const { billing } = useBilling();
  if (!billing) return null;

  if (billing.is_pro) {
    return (
      <Link to="/app/pricing" className="block mx-3 mb-3" data-testid="quota-chip-pro">
        <div className="rounded-lg border border-[#00D084]/40 bg-[#00D084]/5 px-3 py-2.5">
          <div className="flex items-center gap-2 text-[#00D084] text-xs font-medium uppercase tracking-[0.1em]">
            <InfinityIcon size={14} /> Pro · Unlimited
          </div>
          {billing.pro_until && (
            <div className="text-[11px] text-[#A3B3AA] mt-1">
              through {new Date(billing.pro_until).toLocaleDateString()}
            </div>
          )}
        </div>
      </Link>
    );
  }

  const used = billing.ai_calls_used_this_month || 0;
  const limit = billing.ai_calls_limit;
  const left = Math.max(0, limit - used);
  const pct = Math.min(100, (used / Math.max(1, limit)) * 100);
  const isLow = left <= 1;
  const barColor = isLow ? "#F59E0B" : "#00D084";
  const textColor = isLow ? "text-[#F59E0B]" : "text-[#A3B3AA]";

  return (
    <Link to="/app/pricing" className="block mx-3 mb-3 group" data-testid="quota-chip-free">
      <div className="rounded-lg border border-[#173627] bg-[#04120C] px-3 py-2.5 hover:border-[#00D084]/40 transition-colors">
        <div className="flex items-center justify-between mb-1.5">
          <span className={`text-[11px] uppercase tracking-[0.1em] ${textColor}`}>
            {left} of {limit} AI left
          </span>
          <Sparkles size={12} className="text-[#00D084] opacity-70 group-hover:opacity-100" />
        </div>
        <div className="h-1 rounded-full bg-[#0C2419] overflow-hidden">
          <div className="h-full transition-all" style={{ width: `${pct}%`, background: barColor }} />
        </div>
        {isLow && (
          <div className="text-[11px] text-[#F59E0B] mt-1.5">Almost out — upgrade to Pro</div>
        )}
      </div>
    </Link>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const doLogout = () => { logout(); nav("/"); };

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 shrink-0 border-r border-[#173627] bg-[#071B13] min-h-screen sticky top-0 flex flex-col">
        <div className="px-6 py-6 border-b border-[#173627]">
          <div className="flex items-center gap-2" data-testid="app-brand">
            <div className="w-8 h-8 rounded-full bg-[#00D084] grid place-items-center text-[#04120C] font-bold">A</div>
            <span className="font-serif text-xl">Autopilot</span>
          </div>
        </div>
        <nav className="flex-1 py-4 px-3 space-y-1">
          {NAV.map(({ to, label, icon: Icon, end, tid }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              data-testid={tid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-[#0C2419] text-[#F4F0E6] border border-[#173627]"
                    : "text-[#A3B3AA] hover:text-[#F4F0E6] hover:bg-[#0C2419]/60"
                }`
              }
            >
              <Icon size={16} strokeWidth={1.5} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <QuotaChip />
        <div className="px-3 pb-4 pt-2 border-t border-[#173627]">
          <div className="px-3 py-2 text-xs text-[#A3B3AA] truncate" data-testid="app-user-email">{user?.email}</div>
          <button onClick={doLogout} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[#A3B3AA] hover:text-[#EF4444] hover:bg-[#0C2419]/60" data-testid="logout-btn">
            <LogOut size={16} strokeWidth={1.5} /> Sign out
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 min-w-0">
        <Outlet />
      </main>
    </div>
  );
}
