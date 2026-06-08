import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, tokenStore } from "../api/client";
import type { TokenPair, User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName?: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      setUser(await api.me());
    } catch {
      setUser(null);
    }
  }, []);

  // On mount: if we have a token, try to resolve the current user.
  useEffect(() => {
    (async () => {
      if (tokenStore.access) await refreshUser();
      setLoading(false);
    })();
  }, [refreshUser]);

  const applyTokens = useCallback(
    async (pair: TokenPair) => {
      tokenStore.set(pair);
      await refreshUser();
    },
    [refreshUser]
  );

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      login: async (email, password) => applyTokens(await api.login(email, password)),
      register: async (email, password, displayName) =>
        applyTokens(await api.register(email, password, displayName)),
      loginWithGoogle: async (idToken) => applyTokens(await api.loginWithGoogle(idToken)),
      logout: () => {
        tokenStore.clear();
        setUser(null);
      },
      refreshUser,
    }),
    [user, loading, applyTokens, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
