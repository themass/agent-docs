"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getAuthContext, type AuthContext } from "@/lib/api/auth";

type AuthState = {
  context: AuthContext | null;
  loading: boolean;
  refresh: () => Promise<void>;
};

const AuthContextReact = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [context, setContext] = useState<AuthContext | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const ctx = await getAuthContext();
      setContext(ctx);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ context, loading, refresh }),
    [context, loading, refresh],
  );

  return <AuthContextReact.Provider value={value}>{children}</AuthContextReact.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContextReact);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
