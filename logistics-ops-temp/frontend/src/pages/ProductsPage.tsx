import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { getErrorMessage, getFieldErrors } from "../api/client";
import { productsApi } from "../api/resources";
import type { Product } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ActiveBadge, EmptyState, ErrorBox, Field, Modal, PageHeader, Pagination, Spinner } from "../components/ui";
import { formatMoney } from "../lib/format";
import { useDebounced } from "../lib/useDebounced";

const PAGE_SIZE = 20;

function ProductModal({ product, onClose }: { product: Product | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    sku: product?.sku ?? "",
    name: product?.name ?? "",
    description: product?.description ?? "",
    unit: product?.unit ?? "UN",
    unit_price: product?.unit_price ?? "0.00",
    min_stock: String(product?.min_stock ?? 0),
  });
  const mutation = useMutation({
    mutationFn: () => {
      const common = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        unit: form.unit.trim(),
        unit_price: form.unit_price.replace(",", "."),
        min_stock: Number(form.min_stock),
      };
      return product
        ? productsApi.update(product.id, common)
        : productsApi.create({ sku: form.sku.trim(), ...common });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
      onClose();
    },
  });
  const errors = getFieldErrors(mutation.error);
  const hasFieldErrors = Object.keys(errors).length > 0;
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: e.target.value }));

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <Modal title={product ? "Editar produto" : "Novo produto"} onClose={onClose}>
      <form className="form" onSubmit={onSubmit}>
        {mutation.isError && !hasFieldErrors && <ErrorBox message={getErrorMessage(mutation.error)} />}
        <div className="form-row">
          <Field label="SKU" error={errors["sku"]} hint={product ? "O SKU não pode ser alterado." : undefined}>
            <input value={form.sku} onChange={set("sku")} required disabled={product !== null} autoFocus={!product} />
          </Field>
          <Field label="Unidade" error={errors["unit"]}>
            <input value={form.unit} onChange={set("unit")} required maxLength={10} />
          </Field>
        </div>
        <Field label="Nome" error={errors["name"]}>
          <input value={form.name} onChange={set("name")} required minLength={2} />
        </Field>
        <Field label="Descrição" error={errors["description"]}>
          <textarea value={form.description} onChange={set("description")} rows={2} />
        </Field>
        <div className="form-row">
          <Field label="Preço unitário (R$)" error={errors["unit_price"]}>
            <input value={form.unit_price} onChange={set("unit_price")} required inputMode="decimal" />
          </Field>
          <Field label="Estoque mínimo" error={errors["min_stock"]} hint="Abaixo disso o item aparece como crítico.">
            <input type="number" min={0} value={form.min_stock} onChange={set("min_stock")} required />
          </Field>
        </div>
        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function ProductsPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can("products:write");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Product | "new" | null>(null);
  const debounced = useDebounced(search);

  const query = useQuery({
    queryKey: ["products", page, debounced, showInactive],
    queryFn: () =>
      productsApi.list({ page, page_size: PAGE_SIZE, search: debounced, is_active: showInactive ? undefined : true }),
    placeholderData: keepPreviousData,
  });

  const toggle = useMutation({
    mutationFn: (product: Product) => productsApi.update(product.id, { is_active: !product.is_active }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["products"] });
      void queryClient.invalidateQueries({ queryKey: ["stock"] });
    },
  });

  return (
    <>
      <PageHeader
        title="Produtos"
        subtitle="Catálogo de itens movimentados no estoque."
        actions={
          canWrite && (
            <button className="btn btn-primary" onClick={() => setEditing("new")}>
              Novo produto
            </button>
          )
        }
      />
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
            checked={showInactive}
            onChange={(e) => {
              setShowInactive(e.target.checked);
              setPage(1);
            }}
          />
          Mostrar inativos
        </label>
      </div>

      {query.isError && <ErrorBox message={getErrorMessage(query.error)} />}
      {toggle.isError && <ErrorBox message={getErrorMessage(toggle.error)} />}
      {query.isPending ? (
        <Spinner />
      ) : query.data && query.data.items.length === 0 ? (
        <EmptyState title="Nenhum produto encontrado" hint={canWrite ? "Cadastre produtos para controlar o estoque." : undefined} />
      ) : (
        query.data && (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Nome</th>
                  <th className="num">Preço</th>
                  <th className="num">Mínimo</th>
                  <th>Status</th>
                  {canWrite && <th />}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((product) => (
                  <tr key={product.id}>
                    <td>
                      <code>{product.sku}</code>
                    </td>
                    <td>{product.name}</td>
                    <td className="num">
                      {formatMoney(product.unit_price)} / {product.unit}
                    </td>
                    <td className="num">{product.min_stock}</td>
                    <td>
                      <ActiveBadge active={product.is_active} />
                    </td>
                    {canWrite && (
                      <td className="row-actions">
                        <button className="btn" onClick={() => setEditing(product)}>
                          Editar
                        </button>
                        <button className="btn" disabled={toggle.isPending} onClick={() => toggle.mutate(product)}>
                          {product.is_active ? "Desativar" : "Reativar"}
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
      {query.data && <Pagination page={page} pageSize={PAGE_SIZE} total={query.data.total} onChange={setPage} />}
      {editing && <ProductModal product={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}
