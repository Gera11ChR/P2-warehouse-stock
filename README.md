# DMS-TELECOM — Warehouse Management System (WMS) for Telecom Operations

[![Status](https://img.shields.io/badge/Status-v1.0.0_Stable-blue.svg)](#4-recent-consolidation--technical-milestones)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](#2-technology-stack)
[![FastAPI](https://img.shields.io/badge/FastAPI-Pydantic_V2-009688.svg)](#2-technology-stack)
[![Database](https://img.shields.io/badge/PostgreSQL-18_PL%2FpgSQL-336791.svg)](#2-technology-stack)
[![Backend Tests](https://img.shields.io/badge/Pytest-209%2F209_Passed-success.svg)](#8-quality-assurance)
[![Frontend Tests](https://img.shields.io/badge/Vitest-45%2F45_Passed-success.svg)](#8-quality-assurance)
[![Types](https://img.shields.io/badge/Mypy-0_Errors_68_files-success.svg)](#8-quality-assurance)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)

Enterprise **fiber-optic logistics and fleet inventory platform** built on **FastAPI + PostgreSQL 18** with a **React 19** console. Designed under the principles of transactional atomicity, immutable auditability and strict specification-driven governance.

> All quality figures in this document were **re-verified on 2026-09-30** by executing the suites in this repository (see [Quality Assurance](#8-quality-assurance)).

---

## 1. What is Project P2 and what is its purpose?

### 1.1 Definition

Project P2 (commercial name **DMS-TELECOM**) is a **Warehouse Management System (WMS)** purpose-built for telecom field operations: the controlled custody of critical materials — fiber hardware, reels, splitters, connectors, modems and drop cables — as they move from a central warehouse to field crews (*cuadrillas*) and back, across deployment cycles.

It replaces spreadsheet-driven inventory control with a transactional system of record where:

* Stock is owned by exactly one physical custodian at any point in time (warehouse, crew/fleet node, or fiber-optic module).
* Every state change is executed by the database and recorded in an **append-only audit ledger**.
* Nothing can be silently overwritten, double-allocated or driven negative.

### 1.2 Business problem solved

| Pain point in the operation | How P2 resolves it |
| --- | --- |
| Materials dispatched to crews are never returned/corroborated | `TEAMS` (dispatch) and `DEVOL` (return) movements, atomically processed and reversible via cancellation |
| Stock discrepancies discovered after the fact | Mandatory justification codes on adjustments and counter-adjustments, all ledgered |
| Fiber-optic stock treated as an anonymous lump sum | Dedicated **FO modules** (`PAQUETE` / `EN_USO`) with their own isolated inventory, CRUD and audit trail |
| Deployments (lists of materials taken vs. surplus) tracked informally | `DESPLIEGUE` lifecycle per crew: open → close, with taken/surplus reconciliation and CSV reporting |
| No forensics on who changed what | Immutable `auditoria_eventos` ledger (LEFT-JOIN readable), correlation `trace_id` per request |

### 1.3 General architecture

The system follows a **zero-legacy, database-authoritative** pattern: the API layer is pure transport and strict validation; all concurrency control, stock arithmetic and state mutation are delegated to PostgreSQL stored functions.

```text
┌──────────────────────────────────────────────────────────────┐
│   React 19 / Vite SPA  (TypeScript, TanStack Query, TW4)     │
└──────────────────────────────────────────────────────────────┘
                              │  HTTP / JSON  (/api/v1, X-Actor)
                              ▼
┌──────────────────────────────────────────────────────────────┐
│   FastAPI + Pydantic V2 (extra="forbid")                     │
│   Routers · Services · Schemas · RBAC scopes · Telemetry     │
└──────────────────────────────────────────────────────────────┘
                              │  SQLAlchemy 2 async / psycopg 3
                              ▼
┌──────────────────────────────────────────────────────────────┐
│   PostgreSQL 18 — PL/pgSQL is the transactional authority    │
│   ├── fn_procesar_movimiento()      FOR UPDATE / locking     │
│   ├── fn_cancelar_movimiento()      atomic reversal          │
│   ├── fn_cargar_stock_inicial()     idempotent first load    │
│   ├── fn_cargar_stock_inicial_fibra() routed FO load         │
│   ├── fn_ajustar_stock_almacen()    justified differentials  │
│   ├── fn_ajustar_stock_fibra()      FO manual adjustment     │
│   ├── fn_eliminar_inventario_fibra() FO delete + ledger      │
│   └── fn_crear_despliegue() / fn_cerrar_despliegue()         │
└──────────────────────────────────────────────────────────────┘
```

The eight functions above are declared as **mandatory** in `openspec/openspec.yaml` under `domain_rules.transaction_delegation`, together with the explicit prohibition: *"Stock arithmetic in Python/FastAPI is forbidden"*.

### 1.4 Functional scope

Six operational screens (one React page each) over ten backend routers:

| Module | What it does |
| --- | --- |
| **Sección General** | Master catalog (SKUs, categories, units of measure), initial stock loads, warehouse-level inventory |
| **Inventario por Equipos** | Fleet/crew-scoped inventory, local configuration, crew membership |
| **Fibra Óptica** | Isolated `PAQUETE` / `EN_USO` roots: view, edit, adjust, delete (motivo mandatory) |
| **Transferencias** | `TEAMS` (warehouse/FO → crew) and `DEVOL` (crew → warehouse/FO) with cart review and cancellation |
| **Reportes** | Deployment (DESPLIEGUE) reporting with CSV export |
| **Auditoría** | Read-only, human-readable immutable ledger |

---

## 2. Technology stack

### 2.1 Backend — `backend/`

| Technology | Version | Role in the system |
| --- | --- | --- |
| **Python** | 3.12 (`requires-python >= 3.12`) | Runtime for the API and the QA harness |
| **FastAPI** | `>= 0.115` | HTTP framework: routing, DI, OpenAPI/Swagger generation (`/docs`, `/redoc`) |
| **Pydantic** | V2 (`extra="forbid"`) | Strict request/response schemas; mass-assignment and payload-injection defense (Constitution 3.5) |
| **SQLAlchemy 2** | `[asyncio] >= 2.0.41` (installed 2.0.52) | Async ORM for reads and models; **never** for stock arithmetic |
| **psycopg 3** | `[binary] >= 3.2` | PostgreSQL async driver under SQLAlchemy |
| **PostgreSQL** | 18, PL/pgSQL | System of record, locking, stored functions, triggers, audit ledger |
| **Alembic** | `>= 1.16` | Schema migrations — 15 revisions, `0001_initial` → `0015_fo_crud_management` |
| **pytest / pytest-asyncio** | `>= 8` / `>= 1.0` | 209-case integration suite against a real, isolated database |
| **HTTPX** | `>= 0.27` | Async ASGI test client (`ASGITransport`) for endpoint contracts |
| **mypy** | `>= 1.11` (installed 2.3.1) | Static type verification over `app/` + `tests/` |
| **pyotp + cryptography** | `>= 2.9` / `>= 44` | MFA primitives: Fernet key handling and TOTP attempt/lockout knobs in `app/config.py` — **not yet exposed by any endpoint** (see §10) |
| **uvicorn** | ASGI server | Local/production serving (`--reload` in development) |

Canonical DDL lives in `backend/db/ddl.sql`; runtime wiring in `backend/app/{main,config,db,errors,security,telemetry}.py`.

### 2.2 Frontend — `frontend/`

| Technology | Version | Role in the system |
| --- | --- | --- |
| **React + React DOM** | `^19.2.8` | UI runtime |
| **TypeScript** | `~6.0.2` | Compile-time contract enforcement (`tsc -b` gates `npm run build`) |
| **Vite** | `^8.2.2` | Dev server + bundler; proxies `/api` → `http://localhost:8000` |
| **TanStack Query** | `^5.102.8` | Server-state layer: keyed caches (`['stock', id]`, `['fibra', modulo]`…) and post-mutation invalidation |
| **axios** | `^1.20.0` | Single HTTP client (`src/services/api.ts`), injects the `X-Actor` identity header |
| **Zod** | `^4.6.5` | Client-side form validation (`src/schemas/*`) before submission |
| **Tailwind CSS** | `^4.3.3` | Styling via the `@tailwindcss/vite` plugin (no `tailwind.config` — v4 CSS-first setup) |
| **lucide-react** | `^1.40.0` | Icon system |
| **Vitest + Testing Library** | `^5.0.0` / `^16` | 45 component/interaction tests in `jsdom` |
| **ESLint (flat config)** | `^10.9.0` | Lint gate (`react-hooks`, `react-refresh`, `typescript-eslint`) |

Architecture: `pages/` (6 screens) → `components/` (21) → `hooks/` (13, typed Query wrappers) → `services/` (9, one file per domain documenting the real HTTP contract) → `types.ts` (shared DTOs). Toast-based error surfacing; the UI never interprets an API error as stock = 0 (fail-closed).

### 2.3 Data, tooling and governance assets

| Asset | Role |
| --- | --- |
| `openspec/openspec.yaml` | Canonical architecture/API contract consumed by every change package |
| `docs/constitution.md` | Non-negotiable engineering constitution (invariants, zero-trust, DoD) |
| `docs/flujo_operacional.md` | Mandatory Spec-Driven workflow, phases 0–13 |
| `.opencode/agents/` | 11 specialized review/implementation agents (see [Governance](#9-governance--spec-driven-development)) |
| `backend/scripts/seed_catalogo_oficial.py` | Idempotent seeding of the 53-item official catalog |
| `backend/scripts/dev-db.sh` | Boots a disposable local PostgreSQL 18 cluster |
| `data/*.xlsm` | Source DMS spreadsheets (official catalog lineage) |

---

## 3. Evolutionary context and business needs (the "why")

### 3.1 How the system is allowed to evolve

P2 is developed with **Spec-Driven Development (SDD)**. No state-changing code, schema change or UI component exists without an approved OpenSpec change set:

```text
Business report (docs/nis_report.md, docs/fo_report*.md)
        │
        ▼
proposal.md ──► EARS.md  [REQ-<DOMAIN>-<N>] ──► tasks.md
        │                                              │
        │              Constitution (L1)              │
        │              flujo_operacional (L2)          │
        │              active package (L3)             │
        ▼                                              ▼
  Architecture / DB / Security sign-off  ──►  implementation (L5)
        │                                              │
        ▼                                              ▼
  Zero-drift QA (backend contract first)  ──►  human acceptance
        │
        ▼
  Archive (openspec/changes/archive/) + git consolidation
```

Authority is layered in five levels (`.agents.md`): **L1** `docs/constitution.md` (supreme) → **L2** operational workflow + `.agents.md` → **L3** active OpenSpec package → **L4** constitution-impact + tasks → **L5** code. Two delivery rules dominate: **Backend-First** (the frontend stays blocked until the backend contract is signed off) and **Zero-Drift** (implementation must match the approved contract exactly).

### 3.2 Evolution timeline

| Date | Milestone | Why it was needed |
| --- | --- | --- |
| 2026-09-02 | Inter-site warehouse stock transfer model | Establish atomic transfers, RBAC by site and idempotency (`2026-09-02-warehouse-inter-site-stock-transfer`) |
| 2026-09-04 | First WMS inventory dashboard (React + Tailwind) | Operators needed visibility: KPIs, filters, detail drawer, fleet and fiber modules (`2026-09-04-wms-inventory-dashboard`) |
| 2026-09-11 | Manual stock correction + **official 53-item catalog** | Replace demo SKUs with the real DMS catalog; allow justified manual corrections with ledger entries |
| 2026-09-14 | Professional README v1.0.0 + MIT license | Public-facing project baseline |
| 2026-09-23 | **Repository consolidation into a single root** | Merge legacy sub-repositories into one linear history (`docs/adr-2026-09-23-consolidacion-repositorio.md`) |
| 2026-09-24 | Operational flow + agent governance refresh | Codify phases 0–13 and the 11-agent responsibility matrix |
| 2026-09-25 | **Frontend–backend alignment** (129 tests) | Kill phantom materials, hide `ID Lista`, isolate inventories per crew/FO, readable audit, admin RBAC (`2026-09-22-frontend-backend-alignment`) |
| 2026-09-28 | **Crew & deployment management** (Fases 1–12) | Category/U.M. administration, FO as a valid transfer endpoint, per-crew local config, `DESPLIEGUE` lifecycle + CSV reports |
| 2026-09-28 | **NIS operational feedback fixes** *(package complete, pending archival)* | Dynamic U.M. validation and FO routing for initial loads/transfers (`docs/nis_report.md`) |
| 2026-09-29 | **FO CRUD autonomy** | Fiber modules could only be mutated through transfers; added view / edit / adjust / delete with mandatory reason (`docs/fo_report.md`) |
| 2026-09-29 | **FO `DELETE` HTTP 500 fix + official catalog seeding** *(package complete, pending archival)* | See [§4](#4-recent-consolidation--technical-milestones) |

Seven change packages are archived under `openspec/changes/archive/`; two are implemented and awaiting archival.

### 3.3 Architectural decisions that shaped the current system

| Decision | Rationale |
| --- | --- |
| **Transactional delegation to PL/pgSQL** | Race-free stock math in one place; Python never computes balances |
| **Append-only ledger + counter-adjustments** | Constitution 2.4: history is never mutated; discrepancies are corrected by referencing the target event |
| **Sparse inventory model** | `inventario_equipos` holds only rows with real movements — no phantom zero rows |
| **Immutable `id_lista`** | Catalog identity is never renumbered, so foreign keys and history stay stable |
| **Isolated inventories** (migrations `0012`, `0015`) | Warehouse / fleet / FO stock are physically separate tables; no cross-module leakage |
| **RBAC via `X-Actor` scopes + `administradores`** (migration `0012`) | Default-deny, resource-scoped authorization without an external IdP (see [§10](#10-known-limitations--technical-debt)) |
| **Soft-delete for catalog entities** | Keeps referential integrity and ledger intact while removing items from active use |

---

## 4. Recent consolidation & technical milestones

### 4.1 Critical fix — FO module `DELETE` returning HTTP 500

**Symptom** (`docs/fo_report_1.md`): deleting a material from Fibra Óptica, in both `PAQUETE` and `EN_USO`, returned `HTTP 500 Internal Server Error`; the operator only saw a generic *"Ocurrió un error"*. The frontend was validated as correct — it built the URL and the mandatory `motivo` query parameter properly.

**Diagnosis:**

| # | Finding |
| --- | --- |
| 1 | **Root cause:** the production database `p2` was still on Alembic revision **0014** — migration **0015** (`fn_eliminar_inventario_fibra`) had never been applied. Every `DELETE` executed a non-existent function → `SQLSTATE 42883 (undefined_function)` → unmapped `DBAPIError` → **HTTP 500** in both modules |
| 2 | **Secondary finding:** a foreign-key violation raised *inside* a stored function is reported by PostgreSQL as `SQLSTATE 23001 (restrict_violation)`, not `23503` — the classic INSERT/UPDATE code |
| 3 | The integrity rejection (material with movement history) had **no domain mapping**, so it escaped as a 500 through both the statement-time and the commit-time vector (`session.begin()`) |

**Solution** (backend only — zero frontend changes):

1. **`alembic upgrade head` applied (0014 → 0015)** so `fn_eliminar_inventario_fibra` exists in the real deployment.
2. **`backend/app/services/transaccional.py`** — new `mapear_error_delete_fibra(exc, *, modulo, material_id)`:

   | SQLSTATE | Mapped response |
   | --- | --- |
   | `23503` / `23001` (FK) | `409` `FO_DELETE_INTEGRITY_CONFLICT` — *"No se puede eliminar porque existen movimientos o transferencias asociadas"*, with coordinates `{modulo, material_id}` |
   | `42883` (function not applied) | `409` `FO_DELETE_UNAVAILABLE` |
   | any other DB error | `409` (fail-closed — a 500 is never propagated) |
3. **`backend/app/api/v1/fibra.py`** — the endpoint captures `DBAPIError` around `async with session.begin()` (commit-time vector) and translates it through the same mapper. The generic `SEC-012` mapping for every other flow remains untouched.

**Verification (5 new regression tests in `tests/test_fibra.py`):** unit mappings for `23503`, `23001` and `42883`; an integration test proving a `DELETE` against a material with history returns 409 with a clear message, leaves the row intact and writes **zero** `ELIMINACION_FO` events; and a parameter-resolution test (`REQ-DEL-FIX-001`) locking path/query unpacking. Happy-path `204`, `422` (missing motivo) and `404` tests stayed green — **zero UI regression**, `TEAMS`/`DEVOL`, the general catalog, and FO `GET`/`PATCH` untouched.

Tracked as OpenSpec package `2026-09-29-fo-delete-fix` (requirements `REQ-DEL-FIX-001…007`).

### 4.2 Bulk catalog seeding — 53 official materials

`backend/scripts/seed_catalogo_oficial.py` loads the official DMS catalog into the **Inventario General** warehouse (the first active `GENERAL` section, `almacen_id` ascending):

| Property | Value |
| --- | --- |
| Materials | **53**, 53 unique codes |
| Categories | **7** — Cables y Carretes · Cierres y Cajas NAP · Conectividad y Conectores · Empalmes y Consumibles · Equipos · Herrajes, Herramientas y Sujeción · Red Pasiva y Splitters |
| Units of measure (master `ums`) | **8** — `PZ`, `LT`, `ROLLO`, `EQUIPO`, `BOLSA (500 PZ)`, `PAQUETE (100 PZ)`, `CARRETE (1 KM)`, `CARRETE (5 KM)` |
| Mechanism | Single transaction: `ON CONFLICT` UPSERTs for categories, U.M. (reactivating `LT`) and materials (partial unique index `uq_catalogo_codigo_active`) |
| Initial stock | Per material, `fn_cargar_stock_inicial(...)` **only when no `inventario_almacen` row exists** — re-runs never alter already-loaded stock |
| Audit | Each load emits the immutable **`STOCK_INICIAL`** event from PostgreSQL (Invariant 5: zero stock arithmetic and zero direct inventory writes from Python) |
| Integrity check | Hard assertion at the end: active count of the 53 codes `== 53`, otherwise the script fails |

**Idempotent, re-runnable and self-auditing.** Run it from `backend/` so `app.config` picks up `.env`:

```bash
cd backend
.venv/bin/python scripts/seed_catalogo_oficial.py
```

### 4.3 Quality assurance — verified results (2026-09-30)

| Gate | Command | Result |
| --- | --- | --- |
| Backend suite | `.venv/bin/python -m pytest tests/ -q` | **209 passed in 23.94 s** |
| Frontend suite | `npm test` (`vitest run`) | **45 passed / 10 files in 7.42 s** |
| Type checking | `.venv/bin/python -m mypy app/ tests/` | **Success: no issues found in 68 source files** |
| Type + bundle build | `npm run build` (`tsc -b && vite build`) | **✓ built in 667 ms** (2077 modules; 488.62 kB JS / 22.93 kB CSS) |
| Lint | `npm run lint` (`eslint .`) | **✓ clean, zero findings** |

How the backend suite stays trustworthy: it runs **exclusively against an isolated `p2_test` database** — created and migrated to `alembic upgrade head` (0001 → 0015) at collection time, then `TRUNCATE … RESTART IDENTITY CASCADE` over the 16 domain tables plus a deterministic re-seed **before every test**. The development database `p2` is never touched. Each test asserts both the HTTP contract and the resulting database/ledger state, and is traceable to an EARS requirement ID.

Details and repro instructions: [§8 Quality Assurance](#8-quality-assurance).

### 4.4 Adjacent iterations consolidated in the same window

* **NIS catalog fixes** (`2026-09-28-nis-catalog-fixes`, `docs/nis_report.md`):
  * Initial-load target section now offers **Fibra Óptica – Paquete / En Uso** and routes stock to `inventario_fibra` via `fn_cargar_stock_inicial_fibra`.
  * Unit-of-measure validation is **dynamic against the `ums` table** (the static Pydantic enum was removed) so admin-created/renamed U.M. are accepted.
  * `Transferencias` now reads FO origins from `GET /fibra/{modulo}` when a fiber root is selected, fixing an empty-cart latent defect.
* **FO CRUD autonomy** (`2026-09-29-fo-crud-management`, `docs/fo_report.md`): view detail, edit catalog fields and delete with mandatory reason — audited as `ELIMINACION_FO` / `AJUSTE_INVENTARIO_FO`, isolated per module, without altering `TEAMS`/`DEVOL`. Delivered **204 backend tests / 45 frontend tests** at sign-off.

---

## 5. Repository structure

```text
P2/
├── backend/
│   ├── alembic/versions/      # 15 migrations: 0001_initial … 0015_fo_crud_management
│   ├── app/
│   │   ├── api/v1/            # 10 routers (catalogo, inventario, movimientos, …)
│   │   ├── schemas/           # Pydantic V2 contracts (extra="forbid")
│   │   ├── services/          # Domain services; transaccional.py = DB delegation
│   │   ├── models/            # SQLAlchemy models (reads)
│   │   └── {main,config,db,errors,security,telemetry}.py
│   ├── db/ddl.sql             # Canonical DDL (stored functions, triggers, ledger)
│   ├── scripts/               # seed_catalogo_oficial.py · dev-db.sh
│   ├── tests/                 # 19 files · 209 tests · isolated p2_test
│   ├── pyproject.toml         # Dependencies + pytest config
│   └── .env.example
├── frontend/
│   └── src/
│       ├── pages/             # 6 screens
│       ├── components/        # 21 components (+ __tests__/ · 10 files)
│       ├── hooks/ services/ schemas/ utils/
│       ├── layouts/ types.ts
│       └── test/setup.ts
├── openspec/
│   ├── openspec.yaml          # Canonical architecture/API contract
│   ├── changes/               # Active packages + archive/ (7 archived)
│   └── specs/                 # Synced master specs (currently empty — see §10)
├── docs/                      # Constitution, operational flow, ADRs, NIS/FO reports, economic valuation
├── data/                      # Source DMS spreadsheets (catalog lineage)
├── .opencode/                 # 11 SDD agents, OpenSpec commands/skills
├── .agents.md                 # Agent governance & directives (L2)
└── README.md · LICENSE
```

---

## 6. API surface

All routers are mounted under `/api/v1`. Interactive documentation is served at `/docs` (Swagger) and `/redoc`.

| Domain | Routes | Purpose |
| --- | --- | --- |
| **Catalog** | `GET/POST /catalogo` · `GET/PATCH/DELETE /catalogo/{id_lista}` | Materials (SKUs), soft-delete included |
| | `GET/POST/PUT/DELETE /catalogo/categorias[/{id}]` | Category administration (admin) |
| | `GET/POST/PUT/DELETE /catalogo/um[/{id}]` | Unit-of-measure administration (admin) |
| **Inventory** | `GET /inventario/secciones` · `GET /inventario/secciones/{almacen_id}` | Section/warehouse listings |
| | `GET /inventario/secciones/transferibles` | Transferable origins/destinations (incl. FO roots) |
| **Movements** | `POST /movimientos` · `GET /movimientos` · `GET/PATCH/DELETE /movimientos/{id}` | Movement lifecycle |
| | `POST /movimientos/procesar` | Execute `TEAMS`/`DEVOL` via `fn_procesar_movimiento` |
| | `POST /movimientos/{id}/cancelar` | Atomic reversal via `fn_cancelar_movimiento` |
| **Adjustments** | `POST /ajustes/carga-inicial` | Idempotent first load via `fn_cargar_stock_inicial` |
| | `POST /ajustes/stock-almacen` | Justified differential via `fn_ajustar_stock_almacen` |
| **Fleet** | `GET/POST /equipos` · `GET/PATCH/DELETE /equipos/{id}` | Crew management |
| | `GET /equipos/{id}/inventario` · `PATCH /equipos/{id}/inventario/{material_id}` | Crew-scoped inventory |
| **Deployments** | `POST/GET /equipos/{id}/despliegues` · `GET …/{despliegue_id}` · `POST …/{despliegue_id}/cerrar` | `DESPLIEGUE` lifecycle |
| **Fiber optics** | `GET /fibra/{modulo}` · `POST /fibra/carga-inicial` · `POST /fibra/ajuste` | FO stock, initial load, adjustment |
| | `PATCH /fibra/{modulo}/materiales/{id}` · `DELETE /fibra/{modulo}/materiales/{id}?motivo=` | FO CRUD (see §4.1) |
| **Audit** | `GET /auditoria` | Immutable, human-readable ledger |
| **Reports** | `GET /reportes/despliegues` | Deployment reporting (CSV in the UI) |

Error contract: every failure returns `{"error": {"code", "message", …}}` (`backend/app/errors.py`), mapped centrally by four exception handlers in `app/main.py` — `403` authorization, `404` not found, `409` state conflict, `422` business rule (unless overridden, e.g. FO delete → `409`).

---

## 7. Getting started

### 7.1 Prerequisites

* Python **3.12+**, Node **20+** (verified on Node 24.20.0 / npm 11.19.0), PostgreSQL **18**.

### 7.2 Environment

Create `backend/.env` (see `backend/.env.example`):

```env
# Application database (also used as the source for QA URLs)
P2_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/p2

# Credentials exported in the shell for the QA suite (see §8)
# P2_ADMIN_DATABASE_URL=postgresql://USER:PASSWORD@127.0.0.1:5432/p2
# P2_TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/p2_test
```

Optional operational knobs read by `app/config.py`: `P2_TRANSFER_APPROVAL_THRESHOLD` (100), `P2_MFA_ENCRYPTION_KEY`, `P2_MFA_ELEVATION_TTL_SECONDS` (300), `P2_TOTP_MAX_ATTEMPTS` (5), `P2_TOTP_WINDOW_SECONDS` (600), `P2_TOTP_LOCKOUT_SECONDS` (900).

**Never commit real credentials.**

### 7.3 Database

```bash
# Option A: disposable local cluster (trust auth, port 5432, data in /tmp/opencode)
bash backend/scripts/dev-db.sh

# Option B: your own PostgreSQL 18 instance, then:
cd backend
alembic upgrade head            # 0001 → 0015
.venv/bin/python scripts/seed_catalogo_oficial.py   # optional: 53-item catalog
```

### 7.4 Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"         # dependencies live in pyproject.toml (no requirements.txt)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 7.5 Frontend

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api → :8000
```

---

## 8. Quality assurance

### 8.1 Backend (pytest)

```bash
cd backend
export P2_ADMIN_DATABASE_URL="postgresql://USER:PASSWORD@127.0.0.1:5432/p2"
export P2_TEST_DATABASE_URL="postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/p2_test"

.venv/bin/python -m pytest tests/ -v      # full suite
.venv/bin/python -m pytest -m critical    # business-critical smoke subset
.venv/bin/python -m mypy app/ tests/      # static typing
```

> `tests/conftest.py` falls back to a **password-less** URL if `P2_ADMIN_DATABASE_URL` / `P2_TEST_DATABASE_URL` are not exported. If your cluster requires authentication, export both (as above) before running pytest.

**Isolation model:** `p2_test` is created and migrated automatically at collection (`alembic upgrade head`); each test is preceded by `TRUNCATE … RESTART IDENTITY CASCADE` on the 16 domain tables plus a deterministic re-seed (section *Inventario General*, 10 master U.M., QA actor scopes). The development database `p2` is never written to.

**Current state: 209 tests / 19 files, all green.**

### 8.2 Frontend (Vitest + ESLint + tsc)

```bash
cd frontend
npm test          # vitest run — 45 tests / 10 files
npm run lint      # eslint flat config
npm run build     # tsc -b && vite build
```

### 8.3 Definition of Done (Constitution §7)

A change set may not be merged, deployed or archived unless: all mapped automated tests pass at **100%**, builds compile with **zero type errors and zero warnings**, `openspec validate --specs --strict` reports **0 violations**, and every domain invariant remains provably unviolated.

---

## 9. Governance — Spec-Driven Development

* **Contract:** `openspec/openspec.yaml` — declares `domain_rules` (immutable `id_lista`, sparse model, mandatory stored functions, classification schema) and the response semantics of every public path.
* **Workflow:** `docs/flujo_operacional.md` — phases **0–13**, from domain validation and architecture sign-off through database design, backend implementation, testing, contract freeze, frontend implementation, zero-drift QA, human acceptance, security audit, evidence and archival.
* **Constitution:** `docs/constitution.md` — 8 non-negotiable sections (specification supremacy, domain invariants, zero-trust security, atomicity/idempotency, API governance, telemetry/audit, QA gates, amendment procedure).
* **Agents:** 11 specialists in `.opencode/agents/` — `@arq-reviewer`, `@auditor`, `@dba-guard`, `@sec-ops`, `@coder`, `@tester`, `@qa-agent`, `@ui-agent`, `@ux-agent`, `@form-agent`, `@state-agent`, with a defined responsibility matrix per phase.
* **Change packages:** active in `openspec/changes/`, completed ones in `openspec/changes/archive/` (7 archived).
* **Operational reports:** business/field findings enter as documents (`docs/nis_report.md`, `docs/fo_report.md`, `docs/fo_report_1.md`) and are converted into proposals — this is the documented bridge between operations and engineering.

---

## 10. Known limitations & technical debt

Tracked explicitly so that no document overstates the current state:

1. **Authentication / authorization.** There is no external identity provider. The acting user arrives in the `X-Actor` header (the frontend sends a fixed `demo-operador`), and authorization is enforced exclusively server-side via warehouse scopes (`actor_almacen_scopes`) plus the `administradores` table. MFA/TOTP primitives (`pyotp`, `cryptography`) are wired but not user-facing. **OAuth2/JWT integration is planned.**
2. **Mypy runs with default configuration.** There is no `[tool.mypy] strict = true`; the green result means *zero findings under default settings*, not strict mode.
3. **`openspec/specs/` is empty.** Master specs have not been synchronized from the change packages (`opsx-sync` pending).
4. **Two packages are implemented but not yet archived:** `2026-09-28-nis-catalog-fixes` and `2026-09-29-fo-delete-fix` (Fase 13 pending).
5. **Seeding script has no automated test coverage.** `seed_catalogo_oficial.py` is exercised manually; its guarantees rely on UPSERT semantics and the final `== 53` assertion.
6. **Unused / orphaned frontend assets.** `recharts` is declared in `package.json` but imported nowhere; `src/App.css` (Vite template residue) is not imported by any module.
7. **No client-side router.** Navigation is application state (`useState` in `layouts/MainLayout.tsx`); there are no deep-linkable URLs.
8. **FO audit attribution inconsistency (pre-existing).** `fn_ajustar_stock_fibra` / `fn_cargar_stock_inicial_fibra` attribute events to `CURRENT_USER` while `fn_eliminar_inventario_fibra` uses the correct `app.actor` session setting.
9. **Scope enforcement on `/fibra/*` (pre-existing).** Warehouse-scope checks (`SEC-002`) are not applied to the fiber-optic routes — recorded as debt in the FO CRUD sign-off.
10. **`PATCH` with explicit `descripcion: null`** surfaces as an integrity error instead of a `422` (mirrors the general flow; the UI prevents it via `required`).

---

## 11. Project economics

Estimated value of the delivered system, measured 2026-09-30. Full model, assumptions, sensitivity matrix and sources: **[`docs/valoracion-economica.md`](docs/valoracion-economica.md)**.

| Approach | Interpretation | Range (USD) |
| --- | --- | --- |
| Cost of production | What it cost to make, AI-leveraged (1–1.5 FTE-months) | **$12k – $30k** |
| **Replacement / market value** | **What acquiring this scope would cost today** — *headline figure* | **$75k – $200k** |
| Value in use | 5-year economic benefit versus licensing a commercial WMS | **$50k – $200k** |
| Product value | 3-year commercial contract if productized (gated on §10.1) | **$92k – $185k** |

Delivered scope is priced against 2026 market bands for a single-site custom WMS of $64k–$150k (Rorix) / $80k–$300k (Stfalcon), adjusted down for the absent ERP, carrier, hardware and mobile integrations and up for the QA and governance evidence (209 + 45 tests, 14 stored functions, immutable audit ledger). Illustrative conversion at 18 MXN/USD: **≈ $1.35M – $3.6M MXN**.

> **These are estimates, not a formal appraisal.** They rest on stated assumptions (single tenant, no ERP/hardware integration, published vendor rate bands) and should be re-validated before any external or contractual use.

---

## License

MIT — see [`LICENSE`](LICENSE).
