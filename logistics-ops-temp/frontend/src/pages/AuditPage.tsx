import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getErrorMessage } from "../api/client";
import { auditApi } from "../api/resources";
import { EmptyState, ErrorBox, PageHeader, Pagination, Spinner } from "../components/ui";
import { AUDIT_ACTION_LABELS, formatDateTime } from "../lib/format";

const PAGE_SIZE = 25;
const ENTITY_TYPES: Record<string, string> = {
  order: "Pedidos",
  product: "Produtos",
  customer: "Clientes",
  user: "Usuários",
  tenant: "Empresa",
};

export function AuditPage() {
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState("");
  const query = useQuery({
    queryKey: ["audit", page, entityType],
    queryFn: () => auditApi.list({ page, page_size: PAGE_SIZE, entity_type: entityType }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader title="Auditoria" subtitle="Registro imutável das operações relevantes realizadas na plataforma." />
      <div className="toolbar">
        <select
          value={entityType}
          onChange={(e) => {
            setEntityType(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Todas as entidades</option>
          {Object.entries(ENTITY_TYPES).map(([value, label]) => (
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
        <EmptyState title="Nenhum registro de auditoria" />
      ) : (
        query.data && (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Usuário</th>
                  <th>Ação</th>
                  <th>Detalhes</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((log) => (
                  <tr key={log.id}>
                    <td>{formatDateTime(log.created_at)}</td>
                    <td>{log.actor_name ?? "Sistema"}</td>
                    <td>{AUDIT_ACTION_LABELS[log.action] ?? log.action}</td>
                    <td>
                      {log.before || log.after ? (
                        <details>
                          <summary>Ver alterações</summary>
                          <pre>{JSON.stringify({ antes: log.before, depois: log.after }, null, 2)}</pre>
                        </details>
                      ) : (
                        "—"
                      )}
                    </td>
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
