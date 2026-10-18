import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { ordersApi } from "../api/resources";
import { useAuth } from "../auth/AuthContext";
import { EmptyState, ErrorBox, PageHeader, Pagination, Spinner, StatusBadge } from "../components/ui";
import { formatDateTime, formatMoney, STATUS_LABELS } from "../lib/format";
import { useDebounced } from "../lib/useDebounced";

const PAGE_SIZE = 20;

export function OrdersPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const debounced = useDebounced(search);

  const query = useQuery({
    queryKey: ["orders", page, debounced, status],
    queryFn: () => ordersApi.list({ page, page_size: PAGE_SIZE, search: debounced, status }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        title="Pedidos"
        subtitle="Acompanhe o fluxo de cada pedido, do rascunho à entrega."
        actions={
          can("orders:create") && (
            <Link to="/orders/new" className="btn btn-primary">
              Novo pedido
            </Link>
          )
        }
      />
      <div className="toolbar">
        <input
          className="search"
          placeholder="Buscar por número ou cliente"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
        <select
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Todos os status</option>
          {Object.entries(STATUS_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>

      {query.isError && <ErrorBox message={getErrorMessage(query.error)} />}
      {query.isPending ? (
        <Spinner />
      ) : query.data && query.data.items.length === 0 ? (
        <EmptyState title="Nenhum pedido encontrado" hint="Ajuste os filtros ou crie um novo pedido." />
      ) : (
        query.data && (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Pedido</th>
                  <th>Cliente</th>
                  <th>Status</th>
                  <th className="num">Total</th>
                  <th>Atualizado em</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((order) => (
                  <tr key={order.id} className="clickable" onClick={() => navigate(`/orders/${order.id}`)}>
                    <td>
                      <Link to={`/orders/${order.id}`} onClick={(e) => e.stopPropagation()}>
                        #{order.number}
                      </Link>
                    </td>
                    <td>{order.customer_name}</td>
                    <td>
                      <StatusBadge status={order.status} />
                    </td>
                    <td className="num">{formatMoney(order.total)}</td>
                    <td>{formatDateTime(order.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
      {query.data && <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onChange={setPage} />}
    </>
  );
}
