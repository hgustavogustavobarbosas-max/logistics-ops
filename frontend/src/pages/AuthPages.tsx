import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { getErrorMessage, getFieldErrors } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, Field } from "../components/ui";

function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="brand brand-light">
          <span className="brand-mark">LO</span>
          <strong>Logistics Ops</strong>
        </div>
        <h1>{title}</h1>
        <p className="muted">{subtitle}</p>
        {children}
      </div>
    </div>
  );
}

export function LoginPage() {
  const { status, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  const from = (location.state as { from?: string } | null)?.from ?? "/";

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Entrar" subtitle="Acesse o painel de operações da sua empresa.">
      <form onSubmit={onSubmit} className="form">
        {error && <ErrorBox message={error} />}
        <Field label="E-mail">
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="username" />
        </Field>
        <Field label="Senha">
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        </Field>
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Entrando..." : "Entrar"}
        </button>
      </form>
      <p className="auth-alt">
        Ainda não tem conta? <Link to="/register">Cadastre sua empresa</Link>
      </p>
    </AuthShell>
  );
}

export function RegisterPage() {
  const { status, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ company_name: "", full_name: "", email: "", password: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  if (status === "authenticated") return <Navigate to="/" replace />;

  const fieldErrors = getFieldErrors(error);
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: e.target.value }));

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register({ ...form, company_name: form.company_name.trim(), full_name: form.full_name.trim(), email: form.email.trim() });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Cadastrar empresa" subtitle="Você será o administrador e poderá convidar sua equipe.">
      <form onSubmit={onSubmit} className="form">
        {error !== null && Object.keys(fieldErrors).length === 0 && <ErrorBox message={getErrorMessage(error)} />}
        <Field label="Nome da empresa" error={fieldErrors["company_name"]}>
          <input value={form.company_name} onChange={set("company_name")} required minLength={2} autoFocus />
        </Field>
        <Field label="Seu nome" error={fieldErrors["full_name"]}>
          <input value={form.full_name} onChange={set("full_name")} required minLength={2} />
        </Field>
        <Field label="E-mail" error={fieldErrors["email"]}>
          <input type="email" value={form.email} onChange={set("email")} required autoComplete="username" />
        </Field>
        <Field label="Senha" error={fieldErrors["password"]} hint="Mínimo de 10 caracteres, com letras e números.">
          <input type="password" value={form.password} onChange={set("password")} required minLength={10} autoComplete="new-password" />
        </Field>
        <button className="btn btn-primary" disabled={busy}>
          {busy ? "Criando..." : "Criar conta"}
        </button>
      </form>
      <p className="auth-alt">
        Já tem conta? <Link to="/login">Entrar</Link>
      </p>
    </AuthShell>
  );
}
