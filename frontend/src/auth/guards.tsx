import type { ReactNode } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { EmptyState, Spinner } from "../components/ui";
import { useAuth } from "./AuthContext";

export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <Spinner label="Carregando sessão..." />;
  if (status === "anonymous") return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <Outlet />;
}

export function RequirePermission({ permission, children }: { permission: string; children: ReactNode }) {
  const { can } = useAuth();
  if (!can(permission)) {
    return <EmptyState title="Acesso negado" hint="Seu perfil não tem permissão para ver esta página." />;
  }
  return <>{children}</>;
}
