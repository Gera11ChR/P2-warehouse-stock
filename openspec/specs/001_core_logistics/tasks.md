# Tasks — Spec 001 (Core Logistics & Ingestion)

- [ ] **Task 1: Initialize Relational Database Schemas (RF-1, RF-3)**
  - Create Async SQLAlchemy models for `skus` (fiber optic hardware), `vehicles`, `fleet_allocations` (relational tracking for two-person field crews), and `audit_logs`.
  - Generate and execute the initial Alembic migration to establish the schema structure.
  - *Done when:* `alembic upgrade head` executes without errors, tables exist in PostgreSQL, and the backend test suite executes with a 100% pass rate.

- [ ] **Task 2: Implement Zero-Trust Security Dependencies (RF-2)**
  - Create FastAPI dependencies to enforce JWT Bearer token validation and strict Role-Based Access Control (RBAC) across all routes.
  - Integrate Multi-Factor Authentication (MFA/TOTP) requirement verification for all administrative endpoints.
  - *Done when:* Pytest suite returns HTTP 403 Forbidden when an Operator token attempts to access an Admin route, and unauthenticated/non-MFA requests are explicitly blocked.

- [ ] **Task 3: Build Atomic Inventory Transactional Logic (RF-3, RF-5)**
  - Implement `InventoryService.adjust_stock` utilizing explicit `SELECT ... FOR UPDATE` row-level database locking to completely eliminate race conditions.
  - Ensure all stock movements automatically insert a traceable, append-only record into `audit_logs` within the exact same atomic transaction.
  - *Done when:* A Pytest concurrency test simulating 10 simultaneous stock adjustments on a single SKU maintains the exact mathematical balance with 0 failures.

- [ ] **Task 4: Bulk Ingestion Endpoint and Validation Schemas (RF-4)**
  - Define `BulkIngestItem` and `BulkIngestPayload` using Pydantic v2 to enforce strict pre-commit schema and logic validation.
  - Create the `POST /api/v1/inventory/bulk` route engineered to roll back the entire batch if a single error (e.g., non-existent SKU) is detected.
  - *Done when:* The endpoint returns an HTTP 422 Unprocessable Entity detailing the exact array indices of failed rows without committing any partial data.

- [ ] **Task 5: Ergonomic React Data-Grid & Excel Parsing (RF-4, RF-5)**
  - Build a React + TypeScript `<InventoryGrid/>` component capable of receiving and staging bulk clipboard data (e.g., from Excel).
  - Implement visual UI handlers to clearly highlight erroneous rows identified by the backend's validation rejection.
  - *Done when:* Copying tabular rows from Excel and pasting them into the UI successfully maps to the JSON payload, and `npm run build` compiles with zero TypeScript or asset errors.