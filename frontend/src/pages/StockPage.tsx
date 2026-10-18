import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { getErrorMessage, getFieldErrors } from "../api/client";
import { productsApi, stockApi } from "../api/resources";
import type { MovementType } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Badge, EmptyState, ErrorBox, Field, Modal, PageHeader, Pagination, Spinner } from "../components/ui";
import { formatDateTime, MOVEMENT_LABELS } from "../lib/format";
import { useDebounced } from "../lib/useDebounced";

const PAGE_SIZE = 20;

function MovementModal({ onClose }: { onClose: () => void }) {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const [productId, setProductId] = useState("");
  const [type, setType] = useState<MovementType>("inbound");
  const [quantity, setQuantity] = useState("");
  const [reason, setReason] = useState("");

  const products = useQuery({
    queryKey: ["products", "options"],
    queryFn: () => productsApi.list({ page_size: 100, is_active: true }),
  });

  const mutation = useMutation({
    mutationFn: () =>
      stockApi.move({
        product_id: productId,
        movement_type: type,
        quantity: Number(quantity),
        reason: reason.trim() || null,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      onClose();
    },
  });
  const errors = getFieldErrors(mutation.error);
  const hasFieldErrors = Object.keys(errors).length > 0;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <Modal title="Nova movimentação" onClose={onClose}>
      <form className="form" onSubmit={onSubmit}>
        {mutation.isError && !hasFieldErrors && <ErrorBox message={getErrorMessage(mutation.error)} />}
        <Field label="Produto" error={errors["product_id"]}>
          <select value={productId} onChange={(e) => setProductId(e.target.value)} required>
            <option value="">Selecione...</option>
            {products.data?.items.map((product) => (
              <option key={product.id} value={product.id}>
                {product.sku} — {product.name}
              </option>
            ))}
          </select>
        </Field>
        <div className="form-row">
          <Field label="Tipo" error={errors["movement_type"]}>
            <select value={type} onChange={(e) => setType(e.target.value as MovementType)}>
              <option value="inbound">Entrada</option>
              <option value="outbound">Saída</option>
              {can("stock:adjust") && <option value="adjustment">Ajuste (+/−)</option>}
            </select>
          </Field>
          <Field
            label="Quantidade"
            error={errors["quantity"]}
            hint={type === "adjustment" ? "Use valor negativo para reduzir o saldo." : undefined}
          >
            <input
              type="number"
              step={1}
              min={type === "adjustment" ? undefined : 1}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              required
            />
          </Field>
        </div>
        <Field label={type === "adjustment" ? "Motivo (obrigatório)" : "Motivo"} error={errors["reason"]}>
          <input value={reason} onChange={(e) => setReason(e.target.value)} required={type === "adjustment"} maxLength={255} />
        </Field>
        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Registrando..." : "Registrar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function BalancesTab() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [onlyLow, setOnlyLow] = useState(false);
  const debounced = useDebounced(search);
  const query = useQuery({
    queryKey: ["stock", "balances", page, debounced, onlyLow],
    queryFn: () => stockApi.balances({ page, page_size: PAGE_SIZE, search: debounced, only_low: onlyLow }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <div className="toolbar">
        <input
          className="search"
          placeholder="Buscar por SKU ou nome"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
        <label className="check">
          <input
            type="checkbox"
            checked={onlyLow}
            onChange={(e) => {
              setOnlyLow(e.target.checked);
              setPage(1);
            }}
          />
          Somente estoque crítico
        </label>
      </div>
      {query.isError && <ErrorBox message={getErrorMessage(query.error)} />}
      {query.isPending ? (
        <Spinner />
      ) : query.data && query.data.items.length === 0 ? (
        <EmptyState title="Nenhum item de estoque" hint="Cadastre produtos e registre entradas para começar." />
      ) : (
        query.data && (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Produto</th>
                  <th className="num">Físico</th>
                  <th className="num">Reservado</th>
                  <th className="num">Disponível</th>
                  <th className="num">Mínimo</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((item) => (
                  <tr key={item.product_id}>
                    <td>
                      <code>{item.sku}</code>
                    </td>
                    <td>{item.name}</td>
                    <td className="num">
                      {item.on_hand} {item.unit}
                    </td>
                    <td className="num">{item.reserved}</td>
                    <td className="num">
                      <strong>{item.available}</strong>
                    </td>
                    <td className="num">{item.min_stock}</td>
                    <td>{item.is_low && <Badge tone="cancelled">Crítico</Badge>}</td>
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

function MovementsTab() {
  const [page, setPage] = useState(1);
  const [type, setType] = useState("");
  const query = useQuery({
    queryKey: ["stock", "movements", page, type],
    queryFn: () => stockApi.movements({ page, page_size: PAGE_SIZE, movement_type: type }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <div className="toolbar">
        <select
          value={type}
          onChange={(e) => {
            setType(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Todos os tipos</option>
          <option value="inbound">Entradas</option>
          <option value="outbound">Saídas</option>
          <option value="adjustment">Ajustes</option>
        </select>
      </div>
      {query.isError && <ErrorBox message={getErrorMessage(query.error)} />}
      {query.isPending ? (
        <Spinner />
      ) : query.data && query.data.items.length === 0 ? (
        <EmptyState title="Nenhuma movimentação registrada" />
      ) : (
        query.data && (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Produto</th>
                  <th>Tipo</th>
                  <th className="num">Quantidade</th>
                  <th className="num">Saldo após</th>
                  <th>Origem</th>
                  <th>Usuário</th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((movement) => (
                  <tr key={movement.id}>
                    <td>{formatDateTime(movement.created_at)}</td>
                    <td>
                      <code>{movement.sku}</code> {movement.product_name}
                    </td>
                    <td>{MOVEMENT_LABELS[movement.movement_type]}</td>
                    <td className={movement.quantity < 0 ? "num neg" : "num pos"}>
                      {movement.quantity > 0 ? `+${movement.quantity}` : movement.quantity}
                    </td>
                    <td className="num">{movement.balance_after}</td>
                    <td>
                      {movement.order_id ? <Link to={`/orders/${movement.order_id}`}>{movement.reason}</Link> : (movement.reason ?? "—")}
                    </td>
                    <td>{movement.created_by_name}</td>
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

export function StockPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState<"balances" | "movements">("balances");
  const [moving, setMoving] = useState(false);

  return (
    <>
      <PageHeader
        title="Estoque"
        subtitle="Saldo físico, reservas por pedidos confirmados e histórico de movimentações."
        actions={
          can("stock:move") && (
            <button className="btn btn-primary" onClick={() => setMoving(true)}>
              Nova movimentação
            </button>
          )
        }
      />
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "balances"} className={tab === "balances" ? "tab active" : "tab"} onClick={() => setTab("balances")}>
          Saldos
        </button>
        <button role="tab" aria-selected={tab === "movements"} className={tab === "movements" ? "tab active" : "tab"} onClick={() => setTab("movements")}>
          Movimentações
        </button>
      </div>
      {tab === "balances" ? <BalancesTab /> : <MovementsTab />}
      {moving && <MovementModal onClose={() => setMoving(false)} />}
    </>
  );
}
