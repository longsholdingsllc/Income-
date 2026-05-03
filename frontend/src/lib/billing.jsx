import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";

const BillingCtx = createContext(null);

export function BillingProvider({ children }) {
  const { user } = useAuth();
  const [billing, setBilling] = useState(null);

  const refresh = useCallback(async () => {
    if (!user) { setBilling(null); return; }
    try {
      const { data } = await api.get("/billing/me");
      setBilling(data);
    } catch { /* ignore */ }
  }, [user]);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <BillingCtx.Provider value={{ billing, refresh }}>
      {children}
    </BillingCtx.Provider>
  );
}

export const useBilling = () => useContext(BillingCtx) || { billing: null, refresh: () => {} };
