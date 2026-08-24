import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { services } from "../services";

interface AuthContextValue {
  authenticated: boolean;
  initializing: boolean;
  setAuthenticated(value: boolean): void;
  signOut(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(() => services.auth.hasSession());
  const [initializing, setInitializing] = useState(true);
  useEffect(() => {
    let active = true;
    services.auth.restoreSession()
      .then((valid) => { if (active) setAuthenticated(valid); })
      .catch(() => { if (active) setAuthenticated(false); })
      .finally(() => { if (active) setInitializing(false); });
    return () => { active = false; };
  }, []);
  const value = useMemo<AuthContextValue>(() => ({
    authenticated,
    initializing,
    setAuthenticated,
    async signOut() {
      await services.auth.logout();
      setAuthenticated(false);
    },
  }), [authenticated, initializing]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}
