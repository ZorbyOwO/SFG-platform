import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { services } from "../services";

interface AuthContextValue {
  authenticated: boolean;
  setAuthenticated(value: boolean): void;
  signOut(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState(() => services.auth.hasSession());
  const value = useMemo<AuthContextValue>(() => ({
    authenticated,
    setAuthenticated,
    async signOut() {
      await services.auth.logout();
      setAuthenticated(false);
    },
  }), [authenticated]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is missing");
  return value;
}
