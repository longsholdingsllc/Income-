import React from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, RefreshCw, Sparkles } from "lucide-react";

/**
 * Friendlier AI error surfaces:
 * - 402 (quota) -> upgrade CTA
 * - 502/503/504 -> "transient" with retry button
 * - else -> generic error with retry
 */
export function AIError({ error, onRetry, testIdPrefix = "ai-error" }) {
  if (!error) return null;
  const status = error.response?.status;
  const detail = error.response?.data?.detail || error.message || "Something went wrong.";

  if (status === 402) {
    return (
      <div className="card p-5 border-[#F59E0B]/40 bg-[#F59E0B]/5" data-testid={`${testIdPrefix}-quota`}>
        <div className="flex items-start gap-3">
          <Sparkles size={18} className="text-[#F59E0B] mt-0.5 shrink-0" />
          <div className="flex-1">
            <div className="font-sans font-semibold text-[#F4F0E6] mb-1">You've hit the free-tier limit</div>
            <div className="text-sm text-[#A3B3AA] mb-4">{detail}</div>
            <Link to="/app/pricing" className="btn-primary" data-testid={`${testIdPrefix}-upgrade-btn`}>
              Upgrade to Pro
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const isTransient = status === 502 || status === 503 || status === 504;
  return (
    <div className="card p-5 border-[#EF4444]/40 bg-[#EF4444]/5" data-testid={`${testIdPrefix}-generic`}>
      <div className="flex items-start gap-3">
        <AlertTriangle size={18} className="text-[#EF4444] mt-0.5 shrink-0" />
        <div className="flex-1">
          <div className="font-sans font-semibold text-[#F4F0E6] mb-1">
            {isTransient ? "Our AI is briefly throttled" : "Something went wrong"}
          </div>
          <div className="text-sm text-[#A3B3AA] mb-4">
            {isTransient ? "This usually passes in 20–30 seconds. Try again in a moment." : detail}
          </div>
          {onRetry && (
            <button onClick={onRetry} className="btn-secondary" data-testid={`${testIdPrefix}-retry-btn`}>
              <RefreshCw size={14} /> Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
