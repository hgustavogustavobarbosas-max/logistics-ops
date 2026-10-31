import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { getErrorMessage, getFieldErrors } from "../api/client";
import { authApi } from "../api/resources";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, Field, PageHeader } from "../components/ui";
import { ROLE_LABELS } from "../lib/format";

export function AccountPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  const mutation = useMutation({
    mutationFn: () => authApi.changePassword(current, next),
    // Trocar a senha encerra todas as sessões: o usuário entra de novo com a senha nova.
    onSuccess: async () => {
      await logout();
      navigate("/login", { replace: true });
    },
  });
  const errors = getFieldErrors(mutation.error);
  const hasFieldErrors = Object.keys(errors).length > 0;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    mutation.mutate();
  }

  return (
    <>
      <PageHeader title="Minha conta" />
      <section className="card account">
        <dl>
          <dt>Nome</dt>
          <dd>{user?.full_name}</dd>
          <dt>E-mail</dt>
          <dd>{user?.email}</dd>
          <dt>Empresa</dt>
          <dd>{user?.tenant_name}</dd>
          <dt>Perfil</dt>
          <dd>{user ? ROLE_LABELS[user.role] : ""}</dd>
        </dl>
      </section>

      <form className="card form account" onSubmit={onSubmit}>
        <h2 className="card-title">Trocar senha</h2>
        <p className="muted">Ao trocar a senha, todas as suas sessões serão encerradas.</p>
        {mutation.isError && !hasFieldErrors && <ErrorBox message={getErrorMessage(mutation.error)} />}
        <Field label="Senha atual" error={errors["current_password"]}>
          <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required autoComplete="current-password" />
        </Field>
        <Field label="Nova senha" error={errors["new_password"]} hint="Mínimo de 10 caracteres, com letras e números.">
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} required minLength={10} autoComplete="new-password" />
        </Field>
        <div className="form-actions">
          <button className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending ? "Salvando..." : "Trocar senha"}
          </button>
        </div>
      </form>
    </>
  );
}
