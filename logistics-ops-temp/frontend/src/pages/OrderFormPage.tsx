import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getErrorMessage } from "../api/client";
import { customersApi, ordersApi, productsApi } from "../api/resources";
import { EmptyState, ErrorBox, Field, PageHeader, Spinner } from "../components/ui";
import { formatMoney } from "../lib/format";

interface Line {
  key: number;
  productId: string;
  quantity: string;
}

let nextKey = 1;
const newLine = (productId = "", quantity = "1"): Line => ({ key: nextKey++, productId, quantity });

export function OrderFormPage() {
  const { id } = useParams();
  const editing = id !== undefined;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [customerId, setCustomerId] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([newLine()]);
  const [formError, setFormError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(!editing);

  const customers = useQuery({
    queryKey: ["customers", "options"],
    queryFn: () => customersApi.list({ page_size: 100, is_active: true }),
  });
  const products = useQuery({
    queryKey: ["products", "options"],
    queryFn: () => productsApi.list({ page_size: 100, is_active: true }),
  });
  const existing = useQuery({
    queryKey: ["order", id],
    queryFn: () => ordersApi.get(id as string),
    enabled: editing,
  });

  // Preenche o formulário uma única vez com o pedido em edição.
  useEffect(() => {
    if (existing.data && !loaded) {
      setCustomerId(existing.data.customer_id);
      setNotes(existing.data.notes ?? "");
      setLines(existing.data.items.map((item) => newLine(item.product_id, String(item.quantity))));
      setLoaded(true);
    }
  }, [existing.data, loaded]);

  const priceOf = (productId: string): number =>
    Number(products.data?.items.find((p) => p.id === productId)?.unit_price ?? 0);
  const total = lines.reduce((sum, line) => sum + priceOf(line.productId) * (Number(line.quantity) || 0), 0);

  const mutation = useMutation({
    mutationFn: () => {
      const body = {
        customer_id: customerId,
        notes: notes.trim() || null,
        items: lines.map((line) => ({ product_id: line.productId, quantity: Number(line.quantity) })),
      };
      return editing ? ordersApi.update(id as string, body) : ordersApi.create(body);
    },
    onSuccess: (order) => {
      queryClient.setQueryData(["order", order.id], order);
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      navigate(`/orders/${order.id}`);
    },
  });

  function updateLine(key: number, patch: Partial<Line>) {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  }

  function validate(): string | null {
    if (!customerId) return "Selecione o cliente.";
    if (lines.some((line) => !line.productId)) return "Selecione o produto em todas as linhas.";
    const ids = lines.map((line) => line.productId);
    if (new Set(ids).size !== ids.length) return "Há produtos repetidos no pedido.";
    if (lines.some((line) => !Number.isInteger(Number(line.quantity)) || Number(line.quantity) < 1)) {
      return "A quantidade deve ser um número inteiro maior que zero.";
    }
    return null;
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const problem = validate();
    setFormError(problem);
    if (!problem) mutation.mutate();
  }

  if (editing && existing.isPending) return <Spinner />;
  if (editing && existing.isError) return <ErrorBox message={getErrorMessage(existing.error)} />;
  if (editing && existing.data && existing.data.status !== "draft") {
    return <EmptyState title="Este pedido não pode mais ser editado" hint="Somente pedidos em rascunho são editáveis." />;
  }

  return (
    <>
      <PageHeader title={editing ? `Editar pedido #${existing.data?.number ?? ""}` : "Novo pedido"} />
      <form className="card form order-form" onSubmit={onSubmit}>
        {formError && <ErrorBox message={formError} />}
        {mutation.isError && <ErrorBox message={getErrorMessage(mutation.error)} />}

        <Field label="Cliente">
          <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} required>
            <option value="">Selecione...</option>
            {customers.data?.items.map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.name}
              </option>
            ))}
          </select>
        </Field>

        <div className="lines">
          <div className="lines-head">
            <span>Produto</span>
            <span>Quantidade</span>
            <span className="num">Subtotal</span>
            <span />
          </div>
          {lines.map((line) => (
            <div className="line" key={line.key}>
              <select value={line.productId} onChange={(e) => updateLine(line.key, { productId: e.target.value })} aria-label="Produto">
                <option value="">Selecione...</option>
                {products.data?.items.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.sku} — {product.name} ({formatMoney(product.unit_price)})
                  </option>
                ))}
              </select>
              <input
                type="number"
                min={1}
                step={1}
                value={line.quantity}
                onChange={(e) => updateLine(line.key, { quantity: e.target.value })}
                aria-label="Quantidade"
              />
              <span className="num">{formatMoney(priceOf(line.productId) * (Number(line.quantity) || 0))}</span>
              <button
                type="button"
                className="btn btn-ghost"
                disabled={lines.length === 1}
                onClick={() => setLines((current) => current.filter((l) => l.key !== line.key))}
                aria-label="Remover item"
              >
                ✕
              </button>
            </div>
          ))}
          <button type="button" className="btn" onClick={() => setLines((current) => [...current, newLine()])}>
            + Adicionar item
          </button>
        </div>

        <Field label="Observações">
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} maxLength={2000} />
        </Field>

        <div className="form-footer">
          <strong>Total: {formatMoney(total)}</strong>
          <div className="form-actions">
            <Link to={editing ? `/orders/${id}` : "/orders"} className="btn">
              Cancelar
            </Link>
            <button className="btn btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? "Salvando..." : editing ? "Salvar alterações" : "Criar rascunho"}
            </button>
          </div>
        </div>
      </form>
    </>
  );
}
