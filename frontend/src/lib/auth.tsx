"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, getToken, login as apiLogin, LOGOUT_EVENT, setToken } from "./api";
import type { Me } from "./types";

interface AuthState {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<Me>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(() => getToken() !== null);

  // On page load: if a token is stored, ask the API who we are.
  useEffect(() => {
    if (!getToken()) return;
    api<Me>("/auth/me")
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  // The API client fires this event when the token has expired.
  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener(LOGOUT_EVENT, onLogout);
    return () => window.removeEventListener(LOGOUT_EVENT, onLogout);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setToken(await apiLogin(email, password));
    const me = await api<Me>("/auth/me");
    setUser(me);
    return me;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}

/** Who may change what (mirrors the API's role checks, only to hide buttons). */
export function canEdit(user: Me | null, plantId?: number | null): boolean {
  if (!user) return false;
  if (user.role === "sqm") return true;
  return user.role === "plant_lead" && plantId != null && plantId === user.plant_id;
}
