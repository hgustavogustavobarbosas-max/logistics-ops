import { request } from "./client";
import type {
  AuditLog,
  Customer,
  DashboardSummary,
  MovementType,
  OrderDetail,
  OrderStatus,
  OrderSummary,
  Page,
  Product,
  Role,
  StockBalance,
  StockMovement,
  TokenResponse,
  User,
  Me,
} from "./types";

type Query = Record<string, string | number | boolean | null | undefined>;

export const authApi = {
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", { method: "POST", body: { email, password }, auth: false }),
  register: (body: { company_name: string; full_name: string; email: string; password: string }) =>
    request<TokenResponse>("/auth/register", { method: "POST", body, auth: false }),
  logout: () => request<void>("/auth/logout", { method: "POST", auth: false }),
  me: () => request<Me>("/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("/auth/change-password", { method: "POST", body: { current_password, new_password } }),
};

export interface CustomerInput {
  name: string;
  document: string;
  email: string | null;
  phone: string | null;
}

export const customersApi = {
  list: (query: Query) => request<Page<Customer>>("/customers", { query }),
  create: (body: CustomerInput) => request<Customer>("/customers", { method: "POST", body }),
  update: (id: string, body: Partial<CustomerInput> & { is_active?: boolean }) =>
    request<Customer>(`/customers/${id}`, { method: "PATCH", body }),
};

export interface ProductInput {
  sku: string;
  name: string;
  description: string | null;
  unit: string;
  unit_price: string;
  min_stock: number;
}

export const productsApi = {
  list: (query: Query) => request<Page<Product>>("/products", { query }),
  create: (body: ProductInput) => request<Product>("/products", { method: "POST", body }),
  update: (id: string, body: Partial<Omit<ProductInput, "sku">> & { is_active?: boolean }) =>
    request<Product>(`/products/${id}`, { method: "PATCH", body }),
};

export interface MovementInput {
  product_id: string;
  movement_type: MovementType;
  quantity: number;
  reason: string | null;
}

export const stockApi = {
  balances: (query: Query) => request<Page<StockBalance>>("/stock/balances", { query }),
  movements: (query: Query) => request<Page<StockMovement>>("/stock/movements", { query }),
  move: (body: MovementInput) => request<StockMovement>("/stock/movements", { method: "POST", body }),
};

export interface OrderInput {
  customer_id: string;
  notes: string | null;
  items: { product_id: string; quantity: number }[];
}

export const ordersApi = {
  list: (query: Query) => request<Page<OrderSummary>>("/orders", { query }),
  get: (id: string) => request<OrderDetail>(`/orders/${id}`),
  create: (body: OrderInput) => request<OrderDetail>("/orders", { method: "POST", body }),
  update: (id: string, body: Partial<OrderInput>) =>
    request<OrderDetail>(`/orders/${id}`, { method: "PATCH", body }),
  transition: (id: string, to_status: OrderStatus, note?: string) =>
    request<OrderDetail>(`/orders/${id}/transitions`, {
      method: "POST",
      body: { to_status, note: note ?? null },
    }),
};

export interface UserInput {
  email: string;
  full_name: string;
  password: string;
  role: Role;
}

export const usersApi = {
  list: (query: Query) => request<Page<User>>("/users", { query }),
  create: (body: UserInput) => request<User>("/users", { method: "POST", body }),
  update: (id: string, body: { full_name?: string; role?: Role; is_active?: boolean; password?: string }) =>
    request<User>(`/users/${id}`, { method: "PATCH", body }),
};

export const dashboardApi = {
  summary: () => request<DashboardSummary>("/dashboard/summary"),
};

export const auditApi = {
  list: (query: Query) => request<Page<AuditLog>>("/audit-logs", { query }),
};
