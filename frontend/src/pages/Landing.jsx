import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { ArrowRight, Sparkles, TrendingUp, Bot, LineChart, Coins, Target } from "lucide-react";

const HERO_IMG = "https://static.prod-images.emergentagent.com/jobs/2d82098c-b289-4a69-883e-f08e7335e324/images/fe8beaf6bdae82581ac43898864ad75d044dbcdf883e24d88c0214fb5bbb8842.png";

const FEATURES = [
  { icon: TrendingUp, title: "Stream Tracker", desc: "Every dollar, every source — tracked in one command center." },
  { icon: Bot, title: "AI Idea Engine", desc: "Tailored passive-income ideas matched to your skills and budget." },
  { icon: LineChart, title: "DCA Simulator", desc: "See exactly how $500/mo becomes a self-sustaining portfolio." },
  { icon: Coins, title: "Content Autopilot", desc: "SEO-ready affiliate posts generated in minutes, not weeks." },
  { icon: Target, title: "Freedom Number", desc: "Define your monthly target and watch progress in real time." },
  { icon: Sparkles, title: "AI Coach", desc: "Claude Sonnet 4.5 coaching you, 24/7 — weekly plans included." },
];

export default function Landing() {
  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Nav */}
      <nav className="sticky top-0 z-20 backdrop-blur-xl bg-[#04120C]/70 border-b border-[#173627]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2" data-testid="brand-logo">
            <div className="w-8 h-8 rounded-full bg-[#00D084] grid place-items-center text-[#04120C] font-bold">A</div>
            <span className="font-serif text-xl tracking-tight">Autopilot</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="btn-secondary" data-testid="nav-login-btn">Sign in</Link>
            <Link to="/register" className="btn-primary" data-testid="nav-register-btn">
              Start free <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative">
        <div className="absolute inset-0 hero-grid-bg" />
        <img src={HERO_IMG} alt="" className="absolute inset-0 w-full h-full object-cover opacity-25 pointer-events-none" />
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-[#04120C]/60 to-[#04120C]" />
        <div className="max-w-7xl mx-auto px-6 pt-24 pb-32 relative">
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
            className="max-w-4xl"
          >
            <span className="chip" data-testid="hero-tagline-chip">
              <Sparkles size={12} /> Passive income, on autopilot
            </span>
            <h1 className="font-serif text-5xl sm:text-7xl lg:text-8xl tracking-tighter leading-[0.95] mt-6 mb-6">
              Build income<br />
              that works while<br />
              <span className="text-[#00D084] italic">you sleep.</span>
            </h1>
            <p className="text-lg sm:text-xl text-[#A3B3AA] max-w-2xl leading-relaxed">
              A personal wealth operating system. Track every stream, generate ideas with AI,
              auto-draft affiliate content, simulate compound growth, and get a coach in your pocket.
            </p>
            <div className="flex flex-wrap items-center gap-3 mt-10">
              <Link to="/register" className="btn-primary" data-testid="hero-cta-register-btn">
                Start your autopilot <ArrowRight size={16} />
              </Link>
              <Link to="/login" className="btn-secondary" data-testid="hero-cta-login-btn">
                I already have an account
              </Link>
            </div>
          </motion.div>

          {/* Big stat row */}
          <motion.div
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-20"
          >
            {[
              { k: "$4,280", l: "avg monthly passive income after 18 months" },
              { k: "7", l: "income streams tracked per user" },
              { k: "24/7", l: "AI coach availability" },
            ].map((s, i) => (
              <div key={i} className="card p-8" data-testid={`hero-stat-${i}`}>
                <div className="number-hero text-6xl sm:text-7xl mb-2">{s.k}</div>
                <div className="text-sm text-[#A3B3AA]">{s.l}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-7xl mx-auto px-6 py-24 relative">
        <div className="mb-14 max-w-2xl">
          <div className="text-xs uppercase tracking-[0.2em] text-[#00D084] mb-3">Everything, one cockpit</div>
          <h2 className="font-serif text-4xl sm:text-5xl tracking-tighter">
            Six tools. One compounding engine.
          </h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((f, i) => {
            const Icon = f.icon;
            return (
              <motion.div
                key={i}
                className="card p-6"
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.06 }}
                data-testid={`feature-card-${i}`}
              >
                <Icon size={22} strokeWidth={1.5} className="text-[#00D084] mb-4" />
                <h3 className="font-sans text-lg font-semibold mb-1">{f.title}</h3>
                <p className="text-sm text-[#A3B3AA] leading-relaxed">{f.desc}</p>
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-7xl mx-auto px-6 pb-24">
        <div className="card p-10 md:p-16 text-center relative overflow-hidden">
          <div className="absolute inset-0 hero-grid-bg opacity-60" />
          <div className="relative">
            <h3 className="font-serif text-4xl sm:text-5xl tracking-tighter mb-4">
              Your future self <span className="italic text-[#00D084]">thanks you.</span>
            </h3>
            <p className="text-[#A3B3AA] max-w-xl mx-auto mb-8">
              Free to start. No credit card. Five minutes to your first stream.
            </p>
            <Link to="/register" className="btn-primary" data-testid="footer-cta-register-btn">
              Begin <ArrowRight size={16} />
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-[#173627] py-8 text-center text-xs text-[#A3B3AA]">
        © 2026 Autopilot · Built for the builders.
      </footer>
    </div>
  );
}
