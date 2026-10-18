import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { clearAccessToken, refreshSession, setSession, setSessionExpiredHandler } from "../api/client";
import { authApi } from "../api/resources";
import type { Me, TokenResponse } from "../api/types";

type Status = "loading" | "authenticated" | "anonymous";

interface RegisterInput {
  company_name: string;
  full_name: string;
  email: string;
  password: string;
}

interface AuthContextValue {
  status: Status;
  user: Me | null;
  login: (email: string, password: string) => Promise<void>;
  register: (input: RegisterInput) => Promise<void>;
  logout: () => Promise<void>;
  can: (permission: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<Me | null>(null);
  const [status, setStatus] = useState<Status>("loading");

  const startSession = useCallback((data: TokenResponse) => {
    setSession(data);
    setUser(data.user);
    setStatus("authenticated");
  }, []);

  const endSession = useCallback(() => {
    clearAccessToken();
    queryClient.clear();
    setUser(null);
    setStatus("anonymous");
  }, [queryClient]);

  // Restaura a sessão ao abrir o app usando o cookie do refresh token.
  useEffect(() => {
    let cancelled = false;
    void refreshSession().then((data) => {
      if (cancelled) return;
      if (data) {
        setUser(data.user);
        setStatus("authenticated");
      } else {
        setStatus("anonymous");
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Se uma requisição descobrir que a sessão expirou, volta para o login.
  useEffect(() => {
    setSessionExpiredHandler(endSession);
    return () => setSessionExpiredHandler(null);
  }, [endSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      login: async (email, password) => startSession(await authApi.login(email, password)),
      register: async (input) => startSession(await authApi.register(input)),
      logout: async () => {
        try {
          await authApi.logout();
        } finally {
          endSession();
        }
      },
      can: (permission) => user?.permissions.includes(permission) ?? false,
    }),
    [status, user, startSession, endSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth deve ser usado dentro de AuthProvider");
  return context;
}
