import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { ordersApi } from "../api/resources";
import type { OrderStatus } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, PageHeader, Spinner, StatusBadge } from "../components/ui";
import { formatDateTime, formatMoney, STATUS_LABELS } from "../lib/format";

interface Action {
  to: OrderStatus;
  label: string;
  permission: string;
  danger?: boolean;
}

const CANCEL: Action = { to: "cancelled", label: "Cancelar pedido", permission: "orders:cancel", danger: true };

const ACTIONS: Record<OrderStatus, Action[]> = {
  draft: [{ to: "confirmed", label: "Confirmar pedido", permission: "orders:confirm" }, CANCEL],
  confirmed: [{ to: "picking", label: "Iniciar separação", permission: "orders:fulfill" }, CANCEL],
  picking: [{ to: "shipped", label: "Marcar como enviado", permission: "orders:fulfill" }, CANCEL],
  shipped: [{ to: "delivered", label: "Confirmar entrega", permission: "orders:fulfill" }],
  delivered: [],
  cancelled: [],
};

const HINTS: Partial<Record<OrderStatus, string>> = {
  draft: "Ao confirmar, o estoque dos itens é reservado.",
  confirmed: "O estoque está reservado para este pedido.",
  picking: "Ao marcar como enviado, o estoque é baixado.",
};

export function OrderDetailPage() {
  const { id } = useParams();
  const { can } = useAuth();
  const queryClient = useQueryClient();

  const query = useQuery({ queryKey: ["order", id], queryFn: () => ordersApi.get(id as string) });

  const transition = useMutation({
    mutationFn: (to: OrderStatus) => ordersApi.transition(id as string, to),
    onSuccess: (order) => {
      queryClient.setQueryData(["order", id], order);
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  if (query.isPending) return <Spinner />;
  if (query.isError) return <ErrorBox message={getErrorMessage(query.error)} />;
  const order = query.data;

  function run(action: Action) {
    if (action.danger && !window.confirm("Cancelar este pedido? As reservas de estoque serão liberadas.")) return;
    transition.mutate(action.to);
  }

  const actions = ACTIONS[order.status].filter((action) => can(action.permission));
  const hint = HINTS[order.status];

  return (
    <>
      <PageHeader
        title={`Pedido #${order.number}`}
        subtitle={`${order.customer_name} · criado em ${formatDateTime(order.created_at)}`}
        actions={
          order.status === "draft" &&
          can("orders:create") && (
            <Link to={`/orders/${order.id}/edit`} className="btn">
              Editar rascunho
            </Link>
          )
        }
      />

      {transition.isError && <ErrorBox message={getErrorMessage(transition.error)} />}

      <section className="card status-panel">
        <div>
          <StatusBadge status={order.status} />
          {hint && <p className="muted">{hint}</p>}
        </div>
        <div className="row-actions">
          {actions.map((action) => (
            <button
              key={action.to}
              className={action.danger ? "btn btn-danger" : "btn btn-primary"}
              disabled={transition.isPending}
              onClick={() => run(action)}
            >
              {action.label}
            </button>
          ))}
        </div>
      </section>

      <div className="grid-2">
        <section className="card table-wrap">
          <h2 className="card-title">Itens</h2>
          <table>
            <thead>
              <tr>
                <th>Produto</th>
                <th className="num">Qtd.</th>
                <th className="num">Preço</th>
                <th className="num">Subtotal</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <code>{item.sku}</code> {item.name}
                  </td>
                  <td className="num">
                    {item.quantity} {item.unit}
                  </td>
                  <td className="num">{formatMoney(item.unit_price)}</td>
                  <td className="num">{formatMoney(item.line_total)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}>Total</td>
                <td className="num">
                  <strong>{formatMoney(order.total)}</strong>
                </td>
              </tr>
            </tfoot>
          </table>
          {order.notes && <p className="notes">{order.notes}</p>}
        </section>

        <section className="card">
          <h2 className="card-title">Histórico</h2>
          <ol className="timeline">
            {[...order.history].reverse().map((entry, index) => (
              <li key={`${entry.created_at}-${index}`}>
                <StatusBadge status={entry.to_status} />
                <span>
                  {entry.from_status ? `de ${STATUS_LABELS[entry.from_status]} · ` : ""}
                  {entry.changed_by_name}
                </span>
                <small className="muted">{formatDateTime(entry.created_at)}</small>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </>
  );
}
