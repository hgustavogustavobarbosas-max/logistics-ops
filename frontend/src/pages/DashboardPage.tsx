import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { dashboardApi } from "../api/resources";
import type { OrderStatus } from "../api/types";
import { EmptyState, ErrorBox, PageHeader, Spinner } from "../components/ui";
import { formatShortDate, STATUS_LABELS } from "../lib/format";

const STATUS_ORDER: OrderStatus[] = ["draft", "confirmed", "picking", "shipped", "delivered", "cancelled"];

function Kpi({ label, value, hint, tone }: { label: string; value: string | number; hint?: string; tone?: string }) {
  return (
    <div className={`card kpi ${tone ?? ""}`}>
      <span className="muted">{label}</span>
      <strong>{value}</strong>
      {hint && <small className="muted">{hint}</small>}
    </div>
  );
}

export function DashboardPage() {
  const query = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.summary });

  if (query.isPending) return <Spinner />;
  if (query.isError) return <ErrorBox message={getErrorMessage(query.error)} />;
  const data = query.data;

  const maxStatus = Math.max(1, ...STATUS_ORDER.map((s) => data.orders_by_status[s]));
  const maxDay = Math.max(1, ...data.orders_last_7_days.map((d) => d.count));

  return (
    <>
      <PageHeader title="Painel operacional" subtitle="Visão geral de pedidos e estoque." />

      <div className="kpis">
        <Kpi label="Pedidos em andamento" value={data.open_orders} hint="Confirmados e em separação" />
        <Kpi label="Unidades em estoque" value={data.units_on_hand} hint={`${data.units_reserved} reservadas`} />
        <Kpi
          label="Estoque crítico"
          value={data.low_stock_count}
          hint="Produtos abaixo do mínimo"
          tone={data.low_stock_count > 0 ? "warn" : ""}
        />
        <Kpi label="Entregas (30 dias)" value={data.delivered_last_30_days} />
        <Kpi
          label="Tempo médio de atendimento"
          value={data.avg_fulfillment_hours === null ? "—" : `${data.avg_fulfillment_hours} h`}
          hint="Da confirmação à entrega"
        />
      </div>

      <div className="grid-2">
        <section className="card">
          <h2 className="card-title">Pedidos por status</h2>
          <ul className="bars">
            {STATUS_ORDER.map((status) => (
              <li key={status}>
                <span>{STATUS_LABELS[status]}</span>
                <div className="bar-track">
                  <div
                    className={`bar-fill badge-${status}`}
                    style={{ width: `${(data.orders_by_status[status] / maxStatus) * 100}%` }}
                  />
                </div>
                <strong>{data.orders_by_status[status]}</strong>
              </li>
            ))}
          </ul>
        </section>

        <section className="card">
          <h2 className="card-title">Pedidos criados nos últimos 7 dias</h2>
          <div className="columns">
            {data.orders_last_7_days.map((day) => (
              <div key={day.date} className="column">
                <strong>{day.count}</strong>
                <div className="column-bar" style={{ height: `${(day.count / maxDay) * 100}%` }} />
                <small className="muted">{formatShortDate(day.date)}</small>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="card table-wrap">
        <h2 className="card-title">Itens com estoque crítico</h2>
        {data.low_stock_items.length === 0 ? (
          <EmptyState title="Nenhum item abaixo do mínimo" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Produto</th>
                <th className="num">Disponível</th>
                <th className="num">Mínimo</th>
                <th className="num">Físico / Reservado</th>
              </tr>
            </thead>
            <tbody>
              {data.low_stock_items.map((item) => (
                <tr key={item.product_id}>
                  <td>
                    <code>{item.sku}</code> {item.name}
                  </td>
                  <td className="num neg">
                    <strong>{item.available}</strong>
                  </td>
                  <td className="num">{item.min_stock}</td>
                  <td className="num">
                    {item.on_hand} / {item.reserved}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {data.low_stock_count > 0 && (
          <p className="card-footer">
            <Link to="/stock">Ver estoque completo</Link>
          </p>
        )}
      </section>
    </>
  );
}
