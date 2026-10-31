import type { TokenResponse } from "./types";

const BASE = "/api/v1";

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details: FieldError[];

  constructor(status: number, code: string, message: string, details: FieldError[] = []) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// O access token vive só em memória; o refresh token fica em cookie httpOnly (inacessível ao JS).
let accessToken: string | null = null;
let sessionExpiredHandler: (() => void) | null = null;

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  sessionExpiredHandler = handler;
}

export function clearAccessToken(): void {
  accessToken = null;
}

type QueryValue = string | number | boolean | null | undefined;

function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return `${BASE}${path}${qs ? `?${qs}` : ""}`;
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function toApiError(response: Response, body: unknown): ApiError {
  const error = (body as { error?: { code?: string; message?: string; details?: FieldError[] } })?.error;
  return new ApiError(
    response.status,
    error?.code ?? "http_error",
    error?.message ?? "Erro inesperado. Tente novamente.",
    error?.details ?? [],
  );
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function performRefresh(): Promise<TokenResponse | null> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const response = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "same-origin" });
    if (response.ok) {
      const data = (await response.json()) as TokenResponse;
      accessToken = data.access_token;
      return data;
    }
    if (response.status !== 401) break;
    // Outra aba pode ter rotacionado o cookie agora mesmo; a nova tentativa já usa o cookie novo.
    await wait(300);
  }
  accessToken = null;
  return null;
}

let refreshing: Promise<TokenResponse | null> | null = null;

/** Renova a sessão. Chamadas simultâneas compartilham a mesma requisição (evita reuso do token). */
export function refreshSession(): Promise<TokenResponse | null> {
  if (!refreshing) {
    refreshing = performRefresh().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

export function setSession(data: TokenResponse): void {
  accessToken = data.access_token;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, QueryValue>;
  auth?: boolean;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, auth = true } = options;
  const url = buildUrl(path, query);

  const send = (): Promise<Response> => {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && accessToken) headers["Authorization"] = `Bearer ${accessToken}`;
    return fetch(url, {
      method,
      headers,
      credentials: "same-origin",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let response = await send();
  if (response.status === 401 && auth) {
    const session = await refreshSession();
    if (session) {
      response = await send();
    } else {
      sessionExpiredHandler?.();
    }
  }

  const data = await parseBody(response);
  if (!response.ok) throw toApiError(response, data);
  return data as T;
}

export function getErrorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Erro inesperado. Tente novamente.";
}

/** Mapa campo -> mensagem, para exibir erros de validação do servidor junto aos campos. */
export function getFieldErrors(error: unknown): Record<string, string> {
  const result: Record<string, string> = {};
  if (error instanceof ApiError) {
    for (const detail of error.details) result[detail.field] = detail.message;
  }
  return result;
}
