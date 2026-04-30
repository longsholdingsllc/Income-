import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("autopilot_user") || "null"); }
    catch { return null; }
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem("autopilot_token");
    if (token && !user) {
      api.get("/auth/me").then(r => {
        setUser(r.data);
        localStorage.setItem("autopilot_user", JSON.stringify(r.data));
      }).catch(() => {});
    }
  }, []); // eslint-disable-line

  const login = async (email, password) => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("autopilot_token", data.token);
      localStorage.setItem("autopilot_user", JSON.stringify(data.user));
      setUser(data.user);
      return data.user;
    } finally { setLoading(false); }
  };

  const register = async (email, password, name) => {
    setLoading(true);
    try {
      const { data } = await api.post("/auth/register", { email, password, name });
      localStorage.setItem("autopilot_token", data.token);
      localStorage.setItem("autopilot_user", JSON.stringify(data.user));
      setUser(data.user);
      return data.user;
    } finally { setLoading(false); }
  };

  const logout = () => {
    localStorage.removeItem("autopilot_token");
    localStorage.removeItem("autopilot_user");
    setUser(null);
  };

  return (
    <AuthCtx.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
