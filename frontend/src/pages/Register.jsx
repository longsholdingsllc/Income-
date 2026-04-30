import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useAuth } from "../lib/auth";
import { ArrowRight } from "lucide-react";

const AUTH_BG = "https://static.prod-images.emergentagent.com/jobs/2d82098c-b289-4a69-883e-f08e7335e324/images/6705995315c5e421787564407532667ecdf22e6050e03877cf5d69e87cbcde17.png";

export default function Register() {
  const nav = useNavigate();
  const { register, loading } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      await register(email, password, name);
      nav("/app");
    } catch (e2) {
      setErr(e2.response?.data?.detail || "Registration failed");
    }
  };

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2">
      <div className="hidden md:block relative">
        <img src={AUTH_BG} alt="" className="absolute inset-0 w-full h-full object-cover" />
        <div className="absolute inset-0 bg-gradient-to-br from-[#04120C]/60 via-transparent to-[#04120C]/90" />
        <div className="absolute bottom-12 left-12 right-12">
          <div className="font-serif text-5xl tracking-tighter leading-tight">
            Build once.<br />
            <span className="italic text-[#00D084]">Earn forever.</span>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center p-8">
        <motion.form
          onSubmit={submit}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="w-full max-w-md"
          data-testid="register-form"
        >
          <Link to="/" className="inline-flex items-center gap-2 mb-8" data-testid="register-brand-link">
            <div className="w-8 h-8 rounded-full bg-[#00D084] grid place-items-center text-[#04120C] font-bold">A</div>
            <span className="font-serif text-xl">Autopilot</span>
          </Link>
          <h1 className="font-serif text-4xl tracking-tighter mb-2">Create your account</h1>
          <p className="text-sm text-[#A3B3AA] mb-8">Five minutes to your first stream.</p>

          <label className="label">Your name</label>
          <input className="input mb-4" value={name} onChange={e=>setName(e.target.value)} required data-testid="register-name-input" />

          <label className="label">Email</label>
          <input className="input mb-4" type="email" value={email} onChange={e=>setEmail(e.target.value)} required data-testid="register-email-input" />

          <label className="label">Password (min 6 chars)</label>
          <input className="input mb-4" type="password" minLength={6} value={password} onChange={e=>setPassword(e.target.value)} required data-testid="register-password-input" />

          {err && <div className="text-[#EF4444] text-sm mb-4" data-testid="register-error">{err}</div>}

          <button className="btn-primary w-full justify-center" disabled={loading} data-testid="register-submit-btn">
            {loading ? "Creating..." : "Create account"} <ArrowRight size={16} />
          </button>

          <div className="text-sm text-[#A3B3AA] mt-6">
            Already a member? <Link to="/login" className="text-[#00D084] underline" data-testid="register-to-login-link">Sign in</Link>
          </div>
        </motion.form>
      </div>
    </div>
  );
}
