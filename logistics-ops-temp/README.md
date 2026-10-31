# Logistics Ops

Plataforma **B2B multi-tenant de gestão de operações logísticas**: cadastro de clientes e produtos,
controle de estoque com livro-razão de movimentações, pedidos com fluxo de status validado,
auditoria imutável e painel de indicadores — com RBAC real e isolamento total entre empresas.

Projeto de portfólio, construído para demonstrar modelagem de domínio, APIs, segurança,
autorização, transações e testes em Python. É autônomo: não integra com WMS, TMS, ERP ou bancos.

## Sumário

- [Stack](#stack) · [Arquitetura](#arquitetura) · [Estrutura](#estrutura)
- [Configuração](#configuração) · [Execução com Docker](#execução-com-docker) · [Execução local](#execução-local)
- [Migrations](#migrations) · [Testes](#testes) · [Qualidade](#qualidade)
- [Autenticação](#autenticação-e-sessão) · [Perfis e permissões](#perfis-e-permissões) · [Regras de negócio](#regras-de-negócio)
- [Principais endpoints](#principais-endpoints) · [Decisões arquiteturais](#decisões-arquiteturais)

## Stack

| Camada | Tecnologias |
| --- | --- |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, PostgreSQL 16, Argon2, PyJWT |
| Frontend | React, TypeScript, Vite, React Router, TanStack Query |
| Qualidade | Pytest, Ruff (lint + format), MyPy, pre-commit, GitHub Actions |
| Infra | Docker, Docker Compose, Nginx |

## Arquitetura

Monólito modular: um único serviço FastAPI organizado **por domínio**. Cada módulo tem `router`
(HTTP), `schemas` (contratos), `service` (regras de negócio e transações) e `models` (persistência).
As rotas só traduzem HTTP; toda regra vive nos services, que usam a `Session` do SQLAlchemy
diretamente (sem repositório genérico).

```mermaid
flowchart LR
    UI[React SPA] -->|/api/v1 + Bearer| API[FastAPI routers]
    API -->|Depends| AUTH[AuthContext: usuário, tenant, papel]
    API --> SVC[Services: regras + transação]
    SVC --> DB[(PostgreSQL)]
    SVC --> AUD[audit_logs append-only]
```

## Estrutura

```
backend/
  app/
    core/        config, banco, segurança, erros, paginação, rate limit, logging
    modules/
      auth/ users/ tenants/ customers/ products/
      inventory/ orders/ audit/ dashboard/      # router · schemas · service · models
    scripts/seed.py                             # dados de demonstração
    api.py  main.py
  migrations/                                   # Alembic (0001 = schema completo)
  tests/                                        # unitários + integração (PostgreSQL)
frontend/
  src/ api/ auth/ components/ pages/ lib/
docker-compose.yml  .env.example  .github/workflows/ci.yml
```

## Configuração

```bash
cp .env.example .env
# edite POSTGRES_PASSWORD e gere a chave de assinatura:
openssl rand -hex 32     # cole em SECRET_KEY
```

| Variável | Descrição |
| --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://usuário:senha@host:5432/banco` |
| `SECRET_KEY` | Chave de assinatura dos JWT (mín. 32 caracteres) |
| `ENVIRONMENT` | `development`, `test` ou `production` |
| `COOKIE_SECURE` | `true` obrigatório em produção (cookie só via HTTPS) |
| `CORS_ORIGINS` | Lista JSON de origens permitidas; `*` é recusado em produção |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Validade dos tokens (15 min / 7 dias) |
| `RATE_LIMIT_ENABLED` | Limite de tentativas em login/cadastro/refresh |

Em produção a aplicação **não sobe** com `SECRET_KEY` de exemplo, sem `COOKIE_SECURE` ou com CORS `*`.

## Execução com Docker

```bash
cp .env.example .env     # ajuste as senhas
docker compose up --build
```

- Aplicação: <http://localhost:8080> (Nginx serve o frontend e encaminha `/api` ao backend)
- Documentação interativa da API: <http://localhost:8000/docs>
- As migrations rodam automaticamente na subida do backend.

Dados de demonstração (login `admin@demo.com`, `gestor@demo.com`, `operador@demo.com`,
`visualizador@demo.com`, senha `Demo12345678`):

```bash
docker compose exec backend python -m app.scripts.seed
```

## Execução local

Requer Python 3.12+, Node 22+ e um PostgreSQL (use `docker compose up db`).

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload            # http://localhost:8000/docs

cd ../frontend
npm install
npm run dev                              # http://localhost:5173 (proxy de /api para :8000)
```

## Migrations

Toda mudança estrutural passa por Alembic.

```bash
alembic upgrade head                              # aplica
alembic revision --autogenerate -m "descrição"    # gera a partir dos models
alembic check                                     # falha se models e migrations divergirem
alembic downgrade -1
```

O schema usa constraints nomeadas, FKs compostas `(tenant_id, id)` e `CHECK`s; veja
[Decisões arquiteturais](#decisões-arquiteturais).

## Testes

Os testes de integração usam um **PostgreSQL real** (o schema é criado pelas próprias migrations).

```bash
docker compose exec db createdb -U logistics logistics_test
export TEST_DATABASE_URL=postgresql+psycopg://logistics:<senha>@localhost:5432/logistics_test
cd backend && pytest -q
```

Sem `TEST_DATABASE_URL`, rodam apenas os testes unitários (segurança, permissões, máquina de
estados, rate limit, validação de documentos).

O que é coberto: autenticação (rotação e reuso de refresh token, troca de senha, usuário
desativado), **isolamento entre tenants**, matriz de RBAC por endpoint, movimentações e saldos,
fluxo completo de pedidos (reserva, baixa, cancelamento, transições inválidas, atomicidade),
**concorrência sem overselling**, triggers/constraints do banco e o dashboard.

## Qualidade

```bash
cd backend
ruff format . && ruff check --fix .
mypy
pre-commit install                       # hooks de lint/format no commit
cd ../frontend && npm run typecheck
```

Usa-se **Ruff** para lint e formatação (dispensa Black), **MyPy** em modo estrito e
**pre-commit**. O CI roda lint, tipos e testes (com PostgreSQL) e o build do frontend.

## Autenticação e sessão

- Senhas com **Argon2id**; política: 10–128 caracteres com letras e números.
- **Access token** JWT (15 min) mantido só em memória no frontend. Só `sub` e `tid` vão no token;
  usuário, papel e status são lidos do banco a cada requisição — desativar ou rebaixar vale na hora.
- **Refresh token** opaco, em cookie `HttpOnly` + `SameSite=Strict` (+ `Secure` em produção),
  guardado no banco apenas como hash SHA-256, com **rotação** a cada uso.
- **Detecção de reuso**: apresentar um refresh token já rotacionado revoga toda a cadeia
  (com tolerância de 10 s para abas simultâneas).
- Trocar/redefinir senha ou desativar o usuário revoga todos os refresh tokens.
- Login com mensagem única para e-mail inexistente e senha errada, com tempo equalizado.
- Rate limit em login, cadastro e refresh (em memória; para várias réplicas, use um store compartilhado).

## Perfis e permissões

| Permissão | Visualizador | Operador | Gestor | Admin |
| --- | :-: | :-: | :-: | :-: |
| Ler clientes, produtos, estoque, pedidos, painel | ✔ | ✔ | ✔ | ✔ |
| Movimentar estoque (entrada/saída) | | ✔ | ✔ | ✔ |
| Criar/editar pedidos em rascunho | | ✔ | ✔ | ✔ |
| Separar, enviar e entregar pedidos | | ✔ | ✔ | ✔ |
| Confirmar e cancelar pedidos | | | ✔ | ✔ |
| Ajustar estoque (± com motivo) | | | ✔ | ✔ |
| Gerir clientes e produtos | | | ✔ | ✔ |
| Ver auditoria e listar usuários | | | ✔ | ✔ |
| Criar/editar usuários | | | | ✔ |

Os endpoints exigem **permissões**, não papéis; a matriz fica em `modules/auth/permissions.py`.

## Regras de negócio

Fluxo do pedido (cada transição exige a permissão do status de destino):

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> confirmed: reserva estoque
    confirmed --> picking
    picking --> shipped: baixa estoque
    shipped --> delivered
    draft --> cancelled
    confirmed --> cancelled: libera reserva
    picking --> cancelled: libera reserva
```

- **Reserva** na confirmação (`disponível = físico − reservado`); tudo ou nada: se um item não tem
  saldo, nenhuma reserva é feita.
- **Baixa** no envio, com saída gravada no livro-razão ligada ao pedido.
- O saldo físico nunca fica negativo nem abaixo do reservado (validação no service e `CHECK` no banco).
- Preço do item é **congelado** no pedido; só rascunhos são editáveis.
- Usuários não podem rebaixar/desativar a si mesmos (evita ficar sem administrador).
- Exclusão lógica (`is_active`) em vez de DELETE, para preservar integridade histórica.

## Principais endpoints

Prefixo `/api/v1`. Listagens são paginadas (`page`, `page_size`) e aceitam filtros.

| Recurso | Endpoints |
| --- | --- |
| Auth | `POST /auth/register` · `/auth/login` · `/auth/refresh` · `/auth/logout` · `/auth/change-password` · `GET /auth/me` |
| Usuários | `GET/POST /users` · `GET/PATCH /users/{id}` |
| Clientes | `GET/POST /customers` · `GET/PATCH /customers/{id}` |
| Produtos | `GET/POST /products` · `GET/PATCH /products/{id}` |
| Estoque | `GET /stock/balances` · `GET/POST /stock/movements` |
| Pedidos | `GET/POST /orders` · `GET/PATCH /orders/{id}` · `POST /orders/{id}/transitions` |
| Painel | `GET /dashboard/summary` |
| Auditoria | `GET /audit-logs` |

Erros seguem `{"error": {"code", "message", "details?"}}` e nunca expõem detalhes internos; erros de
validação não ecoam os valores enviados. `409` = conflito de estado/estoque, `422` = dados ou regra
de negócio inválidos, `404` também para recursos de outro tenant.

## Decisões arquiteturais

- **Multi-tenancy por coluna** (`tenant_id` em toda tabela). O tenant vem do token, nunca do payload;
  todo acesso passa por `get_or_404(tenant_id, id)`. No banco, **FKs compostas** `(tenant_id, id)`
  impedem que um pedido referencie cliente, produto ou usuário de outra empresa — mesmo com bug na aplicação.
- **Livro-razão imutável** para movimentações, histórico de status e auditoria: triggers do PostgreSQL
  recusam `UPDATE`/`DELETE`.
- **Concorrência**: saldos são travados com `SELECT … FOR UPDATE` em ordem fixa de id (sem deadlock entre
  pedidos); o pedido também é travado durante a transição. Há teste com duas confirmações simultâneas.
- **Numeração de pedidos** por tenant via contador na linha do tenant (`UPDATE … RETURNING`) na mesma
  transação — sem lacunas e sem sequences globais. Serializa a criação de pedidos *dentro* do tenant.
- **Transação por operação**: o service faz as mudanças, a auditoria e o `commit` juntos; falhou, nada persiste.
- **Sem repositório genérico nem camadas extras**: o SQLAlchemy já é a abstração de persistência.
- **Refresh em cookie `HttpOnly`** e API atrás do mesmo domínio (Nginx/proxy do Vite): sem token em
  `localStorage` e sem necessidade de CORS em produção.
- **Quantidades inteiras** e **um depósito por tenant** (escopo deliberado; depósitos múltiplos seriam
  uma tabela `warehouses` e a chave do saldo passaria a incluí-lo).

### Limitações conhecidas

- Rate limit em memória (uma instância). Access tokens já emitidos valem até expirar (15 min) mesmo
  após troca de senha, embora desativação e mudança de papel valham imediatamente.
- Seletores de produto/cliente no formulário de pedido carregam até 100 itens.
- Sem recuperação de senha por e-mail (um administrador redefine a senha do usuário).
