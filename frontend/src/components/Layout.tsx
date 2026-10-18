import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ROLE_LABELS } from "../lib/format";

const NAV = [
  { to: "/", label: "Painel", permission: "dashboard:read", end: true },
  { to: "/orders", label: "Pedidos", permission: "orders:read", end: false },
  { to: "/stock", label: "Estoque", permission: "stock:read", end: false },
  { to: "/products", label: "Produtos", permission: "products:read", end: false },
  { to: "/customers", label: "Clientes", permission: "customers:read", end: false },
  { to: "/users", label: "Usuários", permission: "users:read", end: false },
  { to: "/audit", label: "Auditoria", permission: "audit:read", end: false },
];

export function Layout() {
  const { user, can, logout } = useAuth();
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">LO</span>
          <div>
            <strong>Logistics Ops</strong>
            <small>{user?.tenant_name}</small>
          </div>
        </div>
        <nav>
          {NAV.filter((item) => can(item.permission)).map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-box">
            <strong>{user?.full_name}</strong>
            <small>{user ? ROLE_LABELS[user.role] : ""}</small>
          </div>
          <NavLink to="/account" className="nav-link">
            Minha conta
          </NavLink>
          <button type="button" className="nav-link nav-button" onClick={() => void logout()}>
            Sair
          </button>
        </div>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
