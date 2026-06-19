import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ApiError, api, tokenStore } from "../api/client";
import type { TokenPair, User } from "../api/types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  /** Sign in for the admin surface: authenticates, then rejects non-admins. */
  adminLogin: (email: string, password: string) => Promise<void>;
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
      adminLogin: async (email, password) => {
        // Authenticate first, then verify the resolved user is an admin. If not,
        // drop the session so a non-admin can't linger with a token.
        tokenStore.set(await api.login(email, password));
        const me = await api.me();
        if (!me.is_admin) {
          tokenStore.clear();
          setUser(null);
          throw new ApiError(403, "This account doesn't have admin access.");
        }
        setUser(me);
      },
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
