import type { MovementType, OrderStatus, Role } from "../api/types";

const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const dateTimeFormat = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const dateFormat = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit" });

export const formatMoney = (value: string | number): string => currency.format(Number(value));
export const formatDateTime = (iso: string): string => dateTimeFormat.format(new Date(iso));
export const formatShortDate = (isoDate: string): string => dateFormat.format(new Date(`${isoDate}T12:00:00`));

export function formatDocument(digits: string): string {
  if (digits.length === 11) return digits.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
  if (digits.length === 14) return digits.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");
  return digits;
}

export const STATUS_LABELS: Record<OrderStatus, string> = {
  draft: "Rascunho",
  confirmed: "Confirmado",
  picking: "Em separação",
  shipped: "Enviado",
  delivered: "Entregue",
  cancelled: "Cancelado",
};

export const MOVEMENT_LABELS: Record<MovementType, string> = {
  inbound: "Entrada",
  outbound: "Saída",
  adjustment: "Ajuste",
};

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrador",
  manager: "Gestor",
  operator: "Operador",
  viewer: "Visualizador",
};

export const AUDIT_ACTION_LABELS: Record<string, string> = {
  "tenant.registered": "Empresa cadastrada",
  "auth.login": "Login",
  "user.created": "Usuário criado",
  "user.updated": "Usuário alterado",
  "user.password_reset": "Senha redefinida",
  "user.password_changed": "Senha alterada",
  "customer.created": "Cliente criado",
  "customer.updated": "Cliente alterado",
  "product.created": "Produto criado",
  "product.updated": "Produto alterado",
  "stock.inbound": "Entrada de estoque",
  "stock.outbound": "Saída de estoque",
  "stock.adjustment": "Ajuste de estoque",
  "order.created": "Pedido criado",
  "order.updated": "Pedido alterado",
  "order.confirmed": "Pedido confirmado",
  "order.picking": "Separação iniciada",
  "order.shipped": "Pedido enviado",
  "order.delivered": "Pedido entregue",
  "order.cancelled": "Pedido cancelado",
};
