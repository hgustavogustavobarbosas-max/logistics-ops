export type Role = "admin" | "manager" | "operator" | "viewer";
export type OrderStatus = "draft" | "confirmed" | "picking" | "shipped" | "delivered" | "cancelled";
export type MovementType = "inbound" | "outbound" | "adjustment";

export interface Me {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  tenant_id: string;
  tenant_name: string;
  permissions: string[];
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: Me;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export interface Customer {
  id: string;
  name: string;
  document: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  sku: string;
  name: string;
  description: string | null;
  unit: string;
  unit_price: string;
  min_stock: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StockBalance {
  product_id: string;
  sku: string;
  name: string;
  unit: string;
  on_hand: number;
  reserved: number;
  available: number;
  min_stock: number;
  is_low: boolean;
}

export interface StockMovement {
  id: string;
  product_id: string;
  sku: string;
  product_name: string;
  movement_type: MovementType;
  quantity: number;
  balance_after: number;
  reason: string | null;
  order_id: string | null;
  created_by_id: string;
  created_by_name: string;
  created_at: string;
}

export interface OrderSummary {
  id: string;
  number: number;
  status: OrderStatus;
  customer_id: string;
  customer_name: string;
  total: string;
  created_at: string;
  updated_at: string;
}

export interface OrderItem {
  id: string;
  product_id: string;
  sku: string;
  name: string;
  unit: string;
  quantity: number;
  unit_price: string;
  line_total: string;
}

export interface OrderHistoryEntry {
  from_status: OrderStatus | null;
  to_status: OrderStatus;
  changed_by_name: string;
  note: string | null;
  created_at: string;
}

export interface OrderDetail extends OrderSummary {
  notes: string | null;
  items: OrderItem[];
  history: OrderHistoryEntry[];
}

export interface LowStockItem {
  product_id: string;
  sku: string;
  name: string;
  unit: string;
  on_hand: number;
  reserved: number;
  available: number;
  min_stock: number;
}

export interface DashboardSummary {
  orders_by_status: Record<OrderStatus, number>;
  open_orders: number;
  units_on_hand: number;
  units_reserved: number;
  low_stock_count: number;
  low_stock_items: LowStockItem[];
  orders_last_7_days: { date: string; count: number }[];
  delivered_last_30_days: number;
  avg_fulfillment_hours: number | null;
}

export interface AuditLog {
  id: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  created_at: string;
}
