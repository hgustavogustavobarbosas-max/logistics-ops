import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { getErrorMessage, getFieldErrors } from "../api/client";
import { customersApi } from "../api/resources";
import type { Customer } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ActiveBadge, EmptyState, ErrorBox, Field, Modal, PageHeader, Pagination, Spinner } from "../components/ui";
import { formatDocument } from "../lib/format";
import { useDebounced } from "../lib/useDebounced";

const PAGE_SIZE = 20;

function CustomerModal({ customer, onClose }: { customer: Customer | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: customer?.name ?? "",
    document: customer ? formatDocument(customer.document) : "",
    email: customer?.email ?? "",
    phone: customer?.phone ?? "",
  });
  const mutation = useMutation({
    mutationFn: () => {
      const body = {
        name: form.name.trim(),
        document: form.document,
        email: form.email.trim() || null,
        phone: form.phone.trim() || null,
      };
      return customer ? customersApi.update(customer.id, body) : customersApi.create(body);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
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
    <Modal title={customer ? "Editar cliente" : "Novo cliente"} onClose={onClose}>
      <form className="form" onSubmit={onSubmit}>
        {mutation.isError && !hasFieldErrors && <ErrorBox message={getErrorMessage(mutation.error)} />}
        <Field label="Nome / Razão social" error={errors["name"]}>
          <input value={form.name} onChange={set("name")} required minLength={2} autoFocus />
        </Field>
        <Field label="CPF ou CNPJ" error={errors["document"]}>
          <input value={form.document} onChange={set("document")} required inputMode="numeric" />
        </Field>
        <div className="form-row">
          <Field label="E-mail" error={errors["email"]}>
            <input type="email" value={form.email} onChange={set("email")} />
          </Field>
          <Field label="Telefone" error={errors["phone"]}>
            <input value={form.phone} onChange={set("phone")} />
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

export function CustomersPage() {
  const { can } = useAuth();
  const queryClient = useQueryClient();
  const canWrite = can("customers:write");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [editing, setEditing] = useState<Customer | "new" | null>(null);
  const debounced = useDebounced(search);

  const query = useQuery({
    queryKey: ["customers", page, debounced, showInactive],
    queryFn: () =>
      customersApi.list({ page, page_size: PAGE_SIZE, search: debounced, is_active: showInactive ? undefined : true }),
    placeholderData: keepPreviousData,
  });

  const toggle = useMutation({
    mutationFn: (customer: Customer) => customersApi.update(customer.id, { is_active: !customer.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["customers"] }),
  });

  return (
    <>
      <PageHeader
        title="Clientes"
        subtitle="Empresas e pessoas para quem você despacha pedidos."
        actions={
          canWrite && (
            <button className="btn btn-primary" onClick={() => setEditing("new")}>
              Novo cliente
            </button>
          )
        }
      />
      <div className="toolbar">
        <input
          className="search"
          placeholder="Buscar por nome ou CPF/CNPJ"
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
        <EmptyState title="Nenhum cliente encontrado" hint={canWrite ? "Cadastre o primeiro cliente para criar pedidos." : undefined} />
      ) : (
        query.data && (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>CPF / CNPJ</th>
                  <th>Contato</th>
                  <th>Status</th>
                  {canWrite && <th />}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((customer) => (
                  <tr key={customer.id}>
                    <td>{customer.name}</td>
                    <td>{formatDocument(customer.document)}</td>
                    <td>{[customer.email, customer.phone].filter(Boolean).join(" · ") || "—"}</td>
                    <td>
                      <ActiveBadge active={customer.is_active} />
                    </td>
                    {canWrite && (
                      <td className="row-actions">
                        <button className="btn" onClick={() => setEditing(customer)}>
                          Editar
                        </button>
                        <button className="btn" disabled={toggle.isPending} onClick={() => toggle.mutate(customer)}>
                          {customer.is_active ? "Desativar" : "Reativar"}
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
      {editing && <CustomerModal customer={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </>
  );
}
