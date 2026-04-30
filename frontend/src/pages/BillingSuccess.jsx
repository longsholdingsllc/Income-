import React, { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { CheckCircle2, Loader2, XCircle, ArrowRight } from "lucide-react";

const MAX_POLLS = 10;
const INTERVAL_MS = 2000;
const SANDBOX_FALLBACK_AFTER = 3; // after N stuck polls, try sandbox confirm

export default function BillingSuccess() {
  const loc = useLocation();
  const nav = useNavigate();
  const [state, setState] = useState("polling"); // polling | paid | expired | failed
  const [message, setMessage] = useState("Checking your payment…");
  const attempts = useRef(0);
  const sandboxTried = useRef(false);

  useEffect(() => {
    const sid = new URLSearchParams(loc.search).get("session_id");
    if (!sid) { setState("failed"); setMessage("No session id"); return; }

    let cancelled = false;

    const trySandboxConfirm = async () => {
      // Only call once; only if server indicates sandbox mode
      try {
        const { data: me } = await api.get("/billing/me");
        if (!me.sandbox_mode) return false;
        await api.post(`/billing/dev/confirm/${sid}`);
        return true;
      } catch {
        return false;
      }
    };

    const poll = async () => {
      if (cancelled) return;
      if (attempts.current >= MAX_POLLS) {
        setState("failed");
        setMessage("Timed out waiting for confirmation. Check your email.");
        return;
      }
      attempts.current += 1;
      try {
        const { data } = await api.get(`/billing/status/${sid}`);
        if (data.payment_status === "paid") {
          setState("paid");
          setMessage("Welcome to Pro. Unlimited AI is unlocked.");
          return;
        }
        if (data.status === "expired") {
          setState("expired");
          setMessage("Your payment session expired.");
          return;
        }
        // Stuck in 'initiated' — sandbox fallback (upstream Stripe sandbox quirk)
        if (attempts.current >= SANDBOX_FALLBACK_AFTER && !sandboxTried.current) {
          sandboxTried.current = true;
          setMessage("Finalizing payment…");
          const ok = await trySandboxConfirm();
          if (ok && !cancelled) {
            setState("paid");
            setMessage("Welcome to Pro. Unlimited AI is unlocked.");
            return;
          }
        } else {
          setMessage("Payment processing…");
        }
        setTimeout(poll, INTERVAL_MS);
      } catch (e) {
        setTimeout(poll, INTERVAL_MS);
      }
    };
    poll();
    return () => { cancelled = true; };
  }, [loc.search]);

  return (
    <div className="p-6 sm:p-10 max-w-xl mx-auto" data-testid="billing-success-page">
      <div className="card p-10 text-center">
        {state === "polling" && (
          <>
            <Loader2 size={42} className="text-[#00D084] mx-auto mb-5 animate-spin" data-testid="billing-polling" />
            <h1 className="font-serif text-3xl tracking-tighter mb-2">{message}</h1>
            <p className="text-sm text-[#A3B3AA]">This usually takes a few seconds.</p>
          </>
        )}
        {state === "paid" && (
          <>
            <CheckCircle2 size={56} className="text-[#00D084] mx-auto mb-5" data-testid="billing-paid" />
            <h1 className="font-serif text-4xl tracking-tighter mb-2">You're Pro.</h1>
            <p className="text-[#A3B3AA] mb-8">{message}</p>
            <button onClick={() => nav("/app")} className="btn-primary" data-testid="billing-to-dashboard-btn">
              Back to dashboard <ArrowRight size={16} />
            </button>
          </>
        )}
        {(state === "expired" || state === "failed") && (
          <>
            <XCircle size={42} className="text-[#EF4444] mx-auto mb-5" data-testid="billing-failed" />
            <h1 className="font-serif text-3xl tracking-tighter mb-2">Payment didn't complete</h1>
            <p className="text-[#A3B3AA] mb-8">{message}</p>
            <button onClick={() => nav("/app/pricing")} className="btn-primary" data-testid="billing-to-pricing-btn">
              Try again
            </button>
          </>
        )}
      </div>
    </div>
  );
}
