import type { ReactNode } from "react";
import { Route, Routes } from "react-router-dom";
import { RequireAuth, RequirePermission } from "./auth/guards";
import { Layout } from "./components/Layout";
import { EmptyState } from "./components/ui";
import { AccountPage } from "./pages/AccountPage";
import { AuditPage } from "./pages/AuditPage";
import { CustomersPage } from "./pages/CustomersPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { OrderDetailPage } from "./pages/OrderDetailPage";
import { OrderFormPage } from "./pages/OrderFormPage";
import { OrdersPage } from "./pages/OrdersPage";
import { ProductsPage } from "./pages/ProductsPage";
import { StockPage } from "./pages/StockPage";
import { UsersPage } from "./pages/UsersPage";

const guard = (permission: string, element: ReactNode) => (
  <RequirePermission permission={permission}>{element}</RequirePermission>
);

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<Layout />}>
          <Route index element={guard("dashboard:read", <DashboardPage />)} />
          <Route path="orders" element={guard("orders:read", <OrdersPage />)} />
          <Route path="orders/new" element={guard("orders:create", <OrderFormPage />)} />
          <Route path="orders/:id" element={guard("orders:read", <OrderDetailPage />)} />
          <Route path="orders/:id/edit" element={guard("orders:create", <OrderFormPage />)} />
          <Route path="stock" element={guard("stock:read", <StockPage />)} />
          <Route path="products" element={guard("products:read", <ProductsPage />)} />
          <Route path="customers" element={guard("customers:read", <CustomersPage />)} />
          <Route path="users" element={guard("users:read", <UsersPage />)} />
          <Route path="audit" element={guard("audit:read", <AuditPage />)} />
          <Route path="account" element={<AccountPage />} />
          <Route path="*" element={<EmptyState title="Página não encontrada" />} />
        </Route>
      </Route>
      <Route path="*" element={<EmptyState title="Página não encontrada" />} />
    </Routes>
  );
}
