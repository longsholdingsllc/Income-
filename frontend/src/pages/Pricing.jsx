import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { motion } from "framer-motion";
import { Check, Sparkles, ArrowRight, Infinity as InfinityIcon } from "lucide-react";

const FREE_FEATURES = [
  "Track unlimited income streams",
  "Full dashboard & 6-month trend",
  "DCA compound simulator",
  "Goals & freedom number",
  "5 AI generations / month",
];

const PRO_FEATURES = [
  "Everything in Free",
  "Unlimited AI idea generations",
  "Unlimited AI blog post drafts",
  "Unlimited AI coach conversations",
  "Priority model capacity",
  "30 days of Pro access",
];

export default function Pricing() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");

  const loadStatus = async () => {
    try {
      const { data } = await api.get("/billing/me");
      setStatus(data);
    } catch (e) { /* ignore */ }
  };
  useEffect(() => { loadStatus(); }, []);

  const upgrade = async () => {
    setErr(""); setLoading(true);
    try {
      const { data } = await api.post("/billing/checkout", {
        package_id: "pro_monthly",
        origin_url: window.location.origin,
      });
      window.location.href = data.url;
    } catch (e) {
      setErr(e.response?.data?.detail || "Could not start checkout. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div className="p-6 sm:p-10 max-w-5xl" data-testid="pricing-page">
      <div className="mb-10 text-center">
        <div className="text-xs uppercase tracking-[0.2em] text-[#00D084] mb-2">Pricing</div>
        <h1 className="font-serif text-4xl sm:text-6xl tracking-tighter mb-3">
          Simple. Compounding. <span className="italic text-[#00D084]">Worth it.</span>
        </h1>
        <p className="text-[#A3B3AA] max-w-xl mx-auto">One flat tier. Unlimited AI. Cancel any time — your data stays yours forever.</p>
      </div>

      {status?.is_pro && (
        <div className="card p-5 mb-8 border-[#00D084]/40 text-center" data-testid="pro-active-banner">
          <Sparkles size={18} className="inline text-[#00D084] mr-2" />
          <span className="font-medium">Pro active</span>
          <span className="text-[#A3B3AA]"> — extends through {new Date(status.pro_until).toLocaleDateString()}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Free */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          className="card p-8"
          data-testid="plan-free"
        >
          <div className="text-xs uppercase tracking-[0.15em] text-[#A3B3AA] mb-2">Free</div>
          <div className="flex items-baseline gap-2 mb-6">
            <span className="number-hero text-6xl">$0</span>
            <span className="text-[#A3B3AA]">/ forever</span>
          </div>
          <ul className="space-y-3 mb-8">
            {FREE_FEATURES.map((f, i) => (
              <li key={i} className="flex items-start gap-3 text-sm">
                <Check size={16} className="text-[#00D084] mt-0.5 shrink-0" />
                <span className="text-[#F4F0E6]">{f}</span>
              </li>
            ))}
          </ul>
          <button disabled className="btn-secondary w-full justify-center opacity-60 cursor-default" data-testid="free-current-btn">
            Current plan
          </button>
        </motion.div>

        {/* Pro */}
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="card p-8 relative overflow-hidden border-[#00D084]/40"
          data-testid="plan-pro"
        >
          <div className="absolute top-5 right-5">
            <span className="chip"><Sparkles size={11} /> Most popular</span>
          </div>
          <div className="text-xs uppercase tracking-[0.15em] text-[#00D084] mb-2">Pro</div>
          <div className="flex items-baseline gap-2 mb-1">
            <span className="number-hero text-6xl">$9</span>
            <span className="text-[#A3B3AA]">/ 30 days</span>
          </div>
          <div className="text-xs text-[#A3B3AA] mb-6">One-time payment. Extends on re-purchase. No auto-charge.</div>
          <ul className="space-y-3 mb-8">
            {PRO_FEATURES.map((f, i) => (
              <li key={i} className="flex items-start gap-3 text-sm">
                {f.toLowerCase().includes("unlimited")
                  ? <InfinityIcon size={16} className="text-[#00D084] mt-0.5 shrink-0" />
                  : <Check size={16} className="text-[#00D084] mt-0.5 shrink-0" />}
                <span className="text-[#F4F0E6]">{f}</span>
              </li>
            ))}
          </ul>
          <button onClick={upgrade} disabled={loading} className="btn-primary w-full justify-center" data-testid="upgrade-pro-btn">
            {loading ? "Redirecting…" : <>Upgrade to Pro <ArrowRight size={16} /></>}
          </button>
          {err && <div className="text-[#EF4444] text-sm mt-3" data-testid="pricing-error">{err}</div>}
        </motion.div>
      </div>

      <div className="text-center text-xs text-[#A3B3AA] mt-8">
        Secure checkout powered by Stripe · Test mode — use card <span className="font-mono">4242 4242 4242 4242</span>
      </div>
    </div>
  );
}
