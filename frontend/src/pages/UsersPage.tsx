import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { getErrorMessage, getFieldErrors } from "../api/client";
import { usersApi } from "../api/resources";
import type { Role, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ActiveBadge, EmptyState, ErrorBox, Field, Modal, PageHeader, Pagination, Spinner } from "../components/ui";
import { ROLE_LABELS } from "../lib/format";
import { useDebounced } from "../lib/useDebounced";

const PAGE_SIZE = 20;
const ROLES = Object.keys(ROLE_LABELS) as Role[];

function UserModal({ user, isSelf, onClose }: { user: User | null; isSelf: boolean; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    full_name: user?.full_name ?? "",
    email: user?.email ?? "",
    password: "",
    role: (user?.role ?? "operator") as Role,
    is_active: user?.is_active ?? true,
  });
  const mutation = useMutation({
    mutationFn: () => {
      if (user) {
        return usersApi.update(user.id, {
          full_name: form.full_name.trim(),
          ...(isSelf ? {} : { role: form.role, is_active: form.is_active }),
          ...(form.password && !isSelf ? { password: form.password } : {}),
        });
      }
      return usersApi.create({
        email: form.email.trim(),
        full_name: form.full_name.trim(),
        password: form.password,
        role: form.role,
      });
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
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
    <Modal title={user ? "Editar usuário" : "Novo usuário"} onClose={onClose}>
      <form className="form" onSubmit={onSubmit}>
        {mutation.isError && !hasFieldErrors && <ErrorBox message={getErrorMessage(mutation.error)} />}
        {isSelf && <p className="muted">Você não pode alterar seu próprio perfil de acesso nem desativar a si mesmo.</p>}
        <Field label="Nome" error={errors["full_name"]}>
          <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required minLength={2} autoFocus />
        </Field>
        <Field label="E-mail" error={errors["email"]}>
          <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required disabled={user !== null} />
        </Field>
        <div className="form-row">
          <Field label="Perfil" error={errors["role"]}>
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })} disabled={isSelf}>
              {ROLES.map((role) => (
                <option key={role} value={role}>
                  {ROLE_LABELS[role]}
                </option>
              ))}
            </select>
          </Field>
          {user && (
            <label className="check inline-check">
              <input
                type="checkbox"
                checked={form.is_active}
                disabled={isSelf}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
              />
              Usuário ativo
            </label>
          )}
        </div>
        {!isSelf && (
          <Field
            label={user ? "Nova senha (opcional)" : "Senha inicial"}
            error={errors["password"]}
            hint="Mínimo de 10 caracteres, com letras e números."
          >
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required={user === null}
              minLength={10}
              autoComplete="new-password"
            />
          </Field>
        )}
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

export function UsersPage() {
  const { user: me, can } = useAuth();
  const canManage = can("users:manage");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [editing, setEditing] = useState<User | "new" | null>(null);
  const debounced = useDebounced(search);

  const query = useQuery({
    queryKey: ["users", page, debounced, role],
    queryFn: () => usersApi.list({ page, page_size: PAGE_SIZE, search: debounced, role }),
    placeholderData: keepPreviousData,
  });

  return (
    <>
      <PageHeader
        title="Usuários"
        subtitle="Quem acessa a plataforma da sua empresa e com qual perfil."
        actions={
          canManage && (
            <button className="btn btn-primary" onClick={() => setEditing("new")}>
              Novo usuário
            </button>
          )
        }
      />
      <div className="toolbar">
        <input
          className="search"
          placeholder="Buscar por nome ou e-mail"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
        />
        <select
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Todos os perfis</option>
          {ROLES.map((value) => (
            <option key={value} value={value}>
              {ROLE_LABELS[value]}
            </option>
          ))}
        </select>
      </div>

      {query.isError && <ErrorBox message={getErrorMessage(query.error)} />}
      {query.isPending ? (
        <Spinner />
      ) : query.data && query.data.items.length === 0 ? (
        <EmptyState title="Nenhum usuário encontrado" />
      ) : (
        query.data && (
          <div className="card table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>E-mail</th>
                  <th>Perfil</th>
                  <th>Status</th>
                  {canManage && <th />}
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((user) => (
                  <tr key={user.id}>
                    <td>
                      {user.full_name} {user.id === me?.id && <small className="muted">(você)</small>}
                    </td>
                    <td>{user.email}</td>
                    <td>{ROLE_LABELS[user.role]}</td>
                    <td>
                      <ActiveBadge active={user.is_active} />
                    </td>
                    {canManage && (
                      <td className="row-actions">
                        <button className="btn" onClick={() => setEditing(user)}>
                          Editar
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
      {editing && (
        <UserModal
          user={editing === "new" ? null : editing}
          isSelf={editing !== "new" && editing.id === me?.id}
          onClose={() => setEditing(null)}
        />
      )}
    </>
  );
}
