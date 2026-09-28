# P2 → DMS-TELECOM

# Operational Flow: Spec-Driven Development (SDD)

**Repository:** `P2/`
**Methodology:** OpenSpec + Specification-Driven Development
**Backend Authority:** FastAPI + PostgreSQL + Alembic
**Frontend:** React + Vite + Tailwind
**Active Package:** `openspec/changes/2026-09-28-equipos-despliegue-management/`

---

# 1. Purpose

This document defines the mandatory operational workflow for implementing OpenSpec change packages in the P2 → DMS-TELECOM project.

The workflow establishes strict traceability between:

```text
DApp Operational Context
        ↓
OpenSpec Proposal
        ↓
EARS Requirements
        ↓
Tasks
        ↓
Architecture
        ↓
Database
        ↓
Backend
        ↓
API Contract
        ↓
Frontend
        ↓
Tests
        ↓
Evidence
        ↓
Human Acceptance
        ↓
Archive
```

The Backend is the authoritative source for transactional state, inventory state, persistence, and business rules.

The Frontend is a consumer of Backend contracts and must not become an independent source of business authority.

---

# 2. Repository Structure and Authority

The repository is organized as follows:

```text
P2/
├── .agents/
├── backend/
├── frontend/
├── docs/
└── openspec/
```

## 2.1 `.agents/`

```text
P2/.agents/
```

Contains the definitions and operational instructions for OpenCode/Cline sub-agents.

Examples include:

* `@coder`
* `@dba-guard`
* `@sec-ops`
* `@arq-reviewer`
* `@tester`
* `@qa-agent`
* `@auditor`
* Frontend-specific agents

Agents MUST follow both their individual instructions and this operational workflow.

---

# 3. Governance and Documentation

## 3.1 Constitution

```text
P2/docs/constitution.md
```

This document defines the project's constitutional invariants.

It is a governance authority and MUST be read before implementation.

The Constitution MUST NOT be modified as part of an ordinary OpenSpec change unless an explicitly authorized constitutional change is being processed.

The active change package must conform to the Constitution.

---

## 3.2 Operational Workflow

```text
P2/docs/flujo_operacional.md
```

This document defines the execution process for OpenSpec implementation.

It does not replace the Constitution.

The hierarchy is:

```text
Constitution
    ↓
OpenSpec Specifications
    ↓
OpenSpec Change Package
    ↓
Implementation
    ↓
Tests / Evidence
```

---

# 4. OpenSpec Change Package

The active package is:

```text
P2/openspec/changes/2026-09-28-equipos-despliegue-management/
```

Its mandatory artifacts are:

```text
proposal.md
EARS.md
dapp-context.md
tasks.md
```

## 4.1 `proposal.md`

Defines:

* change scope
* architectural intent
* affected domain
* expected behavior
* implementation boundaries

Location:

```text
P2/openspec/changes/2026-09-28-equipos-despliegue-management/proposal.md
```

---

## 4.2 `EARS.md`

Defines the formal requirements.

Location:

```text
P2/openspec/changes/2026-09-28-equipos-despliegue-management/EARS.md
```

Every implementation requirement MUST be traceable to an EARS identifier.

---

## 4.3 `dapp-context.md`

Defines the operational context derived from the DApp.

Location:

```text
P2/openspec/changes/2026-09-28-equipos-despliegue-management/dapp-context.md
```

This document establishes the operational behavior that the software must represent.

It MUST be used to validate that the implementation corresponds to the real operational model rather than merely satisfying isolated technical requirements.

---

## 4.4 `tasks.md`

Defines the implementation tasks.

Location:

```text
P2/openspec/changes/2026-09-28-equipos-despliegue-management/tasks.md
```

Every implementation task MUST map to one or more EARS requirements or explicitly documented architectural work.

---

# 5. Mandatory Reading Order

Before starting implementation, agents MUST establish the following context:

```text
1. P2/docs/constitution.md
2. P2/docs/flujo_operacional.md
3. Active proposal.md
4. Active EARS.md
5. Active dapp-context.md
6. Active tasks.md
7. Relevant OpenSpec specifications
8. Relevant existing backend/frontend implementation
```

Relevant specifications are located under the applicable OpenSpec specification paths defined by the repository.

Agents MUST NOT assume that the active package alone describes the entire system.

---

# PHASE 0 — PACKAGE VALIDATION AND IMPACT ANALYSIS

## Objective

Determine whether the active OpenSpec package is internally consistent and identify the existing implementation affected by the change.

## Agents

* `@arq-reviewer`
* `@auditor`
* `@sec-ops`

## Read

```text
P2/docs/constitution.md

P2/openspec/changes/2026-09-28-equipos-despliegue-management/
├── proposal.md
├── EARS.md
├── dapp-context.md
└── tasks.md
```

Also inspect relevant:

```text
P2/backend/
P2/frontend/
P2/openspec/
```

## Actions

Identify:

* requirements affected
* existing specifications affected
* existing database tables
* existing Stored Functions
* existing API endpoints
* existing frontend pages/components/services
* obsolete implementation
* migration requirements
* regression risks
* security implications

## Required Output

Impact analysis covering:

```text
Requirement
→ Existing implementation
→ Required change
→ Legacy implementation
→ Affected files
→ Affected database objects
→ Affected tests
```

No Build work may begin during this phase.

---

# PHASE 1 — ARCHITECTURAL PLAN

## Objective

Define the target architecture before modifying implementation.

## Agents

* `@arq-reviewer`
* `@dba-guard`
* `@coder`
* `@sec-ops`

## Actions

Determine:

* domain entities
* ownership of data
* inventory boundaries
* database relationships
* transactional boundaries
* audit behavior
* editable fields
* immutable fields
* category relationships
* unit-of-measure behavior
* minimum-stock behavior
* legacy structures to remove
* API responsibilities
* security boundaries

The plan MUST explicitly preserve the approved operational separation of inventories.

## Output

Architecture plan containing:

```text
Database objects
Stored Functions
API endpoints
DTOs
Frontend contracts
Affected files
Legacy removal
Tests
Security considerations
```

Human approval is required before Build.

---

# PHASE 2 — DATABASE AND TRANSACTIONAL DESIGN

## Backend Authority

All database work is restricted to:

```text
P2/backend/alembic/
P2/backend/app/models/
```

and the PostgreSQL structures managed by the backend.

## Agents

* `@dba-guard`
* `@arq-reviewer`
* `@auditor`

## Actions

Design:

* tables
* columns
* primary keys
* foreign keys
* constraints
* indexes
* audit structures
* Alembic migrations
* Stored Functions
* transaction boundaries
* row-locking strategy
* migration/data cleanup strategy

Migration files are created under:

```text
P2/backend/alembic/versions/
```

SQLAlchemy mappings are maintained under:

```text
P2/backend/app/models/
```

## Mandatory Rule

Business-critical inventory mutations MUST remain transactionally authoritative in PostgreSQL.

Python MUST NOT become an alternative transactional authority.

---

# PHASE 3 — BACKEND IMPLEMENTATION

## Objective

Implement the authoritative transactional system and API contract.

## Agents

* `@dba-guard`
* `@coder`
* `@sec-ops`

---

## 3.1 Database Implementation

Modify:

```text
P2/backend/alembic/versions/
P2/backend/app/models/
```

Implement:

* migrations
* database structures
* constraints
* indexes
* Stored Functions
* audit mechanisms
* required data transformations
* obsolete database structures

---

## 3.2 API Implementation

Modify:

```text
P2/backend/app/api/
P2/backend/app/schemas/
```

Implement:

* FastAPI routers
* endpoints
* Pydantic V2 DTOs
* request validation
* response contracts
* authorization boundaries
* error handling

The API MUST expose PostgreSQL-backed business operations rather than duplicating their authoritative logic.

---

# PHASE 4 — BACKEND TESTING

## Test Location

```text
P2/backend/tests/
```

## Agents

* `@tester`
* `@qa-agent`
* `@dba-guard`
* `@auditor`

## Tests MUST validate, where applicable:

* inventory non-negativity
* atomicity
* rollback
* concurrency
* row locking
* inventory isolation
* team inventory separation
* fiber inventory separation
* stock adjustments
* transfers
* returns
* audit preservation
* immutable fields
* editable fields
* category validity
* unit-of-measure validity
* minimum stock
* active/inactive behavior
* obsolete record elimination
* Stored Function behavior
* API behavior

Every requirement-specific test MUST reference its corresponding EARS identifier.

---

# PHASE 5 — BACKEND VERIFICATION AND CONTRACT FREEZE

## Agents

* `@arq-reviewer`
* `@auditor`
* `@tester`

Before Frontend development begins, verify:

```text
Database
   ↓
Stored Functions
   ↓
SQLAlchemy
   ↓
Pydantic
   ↓
FastAPI
   ↓
OpenAPI
```

The Backend contract is considered frozen only after:

* backend tests pass
* API contract is reviewed
* EARS coverage is verified
* security checks pass
* architectural review passes

The resulting API contract becomes the authoritative contract for Frontend development.

---

# PHASE 6 — FRONTEND PLAN

## Frontend Authority

Frontend implementation is restricted to:

```text
P2/frontend/src/
```

## Agents

* `@state-agent`
* `@ui-agent`
* `@ux-agent`
* `@form-agent`

## Read

The frozen Backend API contract.

## Actions

Design:

```text
frontend/src/services/
frontend/src/hooks/
frontend/src/components/
frontend/src/pages/
```

as applicable.

Define:

* TypeScript interfaces
* API services
* TanStack Query hooks
* routes
* components
* forms
* Zod schemas
* loading states
* empty states
* error states
* confirmation flows
* operational feedback

The Frontend design MUST correspond to the DApp operational model.

---

# PHASE 7 — FRONTEND IMPLEMENTATION

## Agents

* `@ui-agent`
* `@state-agent`
* `@form-agent`

Implement under:

```text
P2/frontend/src/
```

including:

```text
components/
pages/
services/
hooks/
```

as applicable.

The Frontend MUST consume the frozen Backend contract.

It MUST NOT:

* calculate authoritative inventory
* persist inventory directly
* bypass API contracts
* reproduce PostgreSQL transactional logic
* create alternative sources of truth
* rely on stale local state as authoritative inventory state

Frontend validation is limited to input/presentation concerns.

---

# PHASE 8 — INTEGRATION AND ZERO-DRIFT QA

## Agents

* `@qa-agent`
* `@tester`
* `@auditor`

## Environment

Frontend MUST be tested against the actual local Backend/API environment.

Backend:

```text
P2/backend/
```

Frontend:

```text
P2/frontend/
```

## Validate

* API compatibility
* TypeScript compatibility
* real database behavior
* inventory isolation
* team operations
* fiber operations
* stock adjustments
* transfers
* returns
* category behavior
* unit-of-measure behavior
* minimum-stock behavior
* audit visibility
* active/inactive filtering
* error handling

The QA objective is **Zero-Drift** between:

```text
DApp
↕
Backend
↕
API Contract
↕
Frontend
```

---

# PHASE 9 — DApp OPERATIONAL ACCEPTANCE

## Objective

Verify that the implementation actually represents the operational behavior documented by the DApp.

## Agents

* `@qa-agent`
* `@auditor`
* `@arq-reviewer`

For every DApp-derived requirement:

```text
DApp Requirement
        ↓
EARS ID
        ↓
Task
        ↓
Backend Implementation
        ↓
Frontend Implementation
        ↓
Automated Test
        ↓
Evidence
```

The implementation is not accepted merely because:

* the code compiles
* migrations execute
* API endpoints respond
* frontend builds

It must also reproduce the intended operational workflow.

---

# PHASE 10 — SECURITY AND ARCHITECTURE AUDIT

## Agents

* `@sec-ops`
* `@auditor`
* `@arq-reviewer`

Inspect:

```text
P2/backend/
P2/frontend/
P2/openspec/
P2/docs/
```

Validate:

* authorization
* input validation
* direct-write risks
* unauthorized mutation paths
* transaction boundaries
* audit integrity
* legacy paths
* architectural consistency
* Constitution compliance
* OpenSpec compliance

---

# PHASE 11 — FINAL EVIDENCE

Evidence MUST establish:

```text
EARS requirement
        ↓
Implementation
        ↓
Test
        ↓
Result
```

Evidence must cover, as applicable:

* database tests
* API tests
* frontend tests
* integration tests
* E2E tests
* DApp acceptance
* security checks
* migration validation
* regression validation
* architecture validation

---

# PHASE 12 — HUMAN ACCEPTANCE

The active package cannot be considered complete until:

* all required EARS requirements have evidence
* backend tests pass
* frontend tests pass
* integration tests pass
* DApp operational acceptance passes
* security review passes
* architecture review passes
* regression validation passes
* no critical unresolved finding remains
* no unauthorized legacy path remains

Human approval is required before final consolidation.

---

# PHASE 13 — GIT AND OPENSPEC CONSOLIDATION

## Agent

* `@auditor`

## Actions

Review the final repository state:

```text
P2/
├── backend/
├── frontend/
├── docs/
└── openspec/
```

Verify that:

* only authorized files changed
* implementation matches the approved package
* all EARS requirements have evidence
* no unauthorized code remains
* backend/frontend contracts remain aligned
* tests pass
* audit is complete

After final approval:

1. Commit the completed implementation.
2. Merge according to repository governance.
3. Preserve the final commit as implementation evidence.
4. Move the completed package:

```text
P2/openspec/changes/2026-09-28-equipos-despliegue-management/
```

to:

```text
P2/openspec/changes/archive/2026-09-28-equipos-despliegue-management/
```

The package MUST NOT be archived before final acceptance.

---

# 14. Active Package Boundary

During implementation of the current change, the primary working package is:

```text
P2/openspec/changes/2026-09-28-equipos-despliegue-management/
```

Agents MUST NOT arbitrarily modify archived packages:

```text
P2/openspec/changes/archive/
```

Archived packages are historical implementation records unless the current change explicitly requires historical analysis.

---

# 15. Mandatory Traceability Matrix

The implementation MUST maintain the following conceptual traceability:

| Layer               | Location                                                                       |
| ------------------- | ------------------------------------------------------------------------------ |
| Constitution        | `P2/docs/constitution.md`                                                      |
| Operational Flow    | `P2/docs/flujo_operacional.md`                                                 |
| Proposal            | `P2/openspec/changes/2026-09-28-equipos-despliegue-management/proposal.md`     |
| Requirements        | `P2/openspec/changes/2026-09-28-equipos-despliegue-management/EARS.md`         |
| DApp Context        | `P2/openspec/changes/2026-09-28-equipos-despliegue-management/dapp-context.md` |
| Tasks               | `P2/openspec/changes/2026-09-28-equipos-despliegue-management/tasks.md`        |
| DB migrations       | `P2/backend/alembic/versions/`                                                 |
| DB models           | `P2/backend/app/models/`                                                       |
| API                 | `P2/backend/app/api/`                                                          |
| DTOs                | `P2/backend/app/schemas/`                                                      |
| Backend tests       | `P2/backend/tests/`                                                            |
| Frontend components | `P2/frontend/src/components/`                                                  |
| Frontend pages      | `P2/frontend/src/pages/`                                                       |
| Frontend services   | `P2/frontend/src/services/`                                                    |
| Frontend hooks      | `P2/frontend/src/hooks/`                                                       |
| Completed package   | `P2/openspec/changes/archive/`                                                 |

---

# 16. Completion Gate

The package is COMPLETE only when:

```text
[ ] Constitution reviewed
[ ] OpenSpec package validated
[ ] DApp context validated
[ ] Issues/requirements traced
[ ] Architecture approved
[ ] Database design approved
[ ] Stored Functions implemented
[ ] Alembic migrations implemented
[ ] Backend implemented
[ ] Backend tests pass
[ ] API contract verified
[ ] API contract frozen
[ ] Frontend planned from contract
[ ] Frontend implemented
[ ] Zero-Drift QA passes
[ ] DApp operational acceptance passes
[ ] Security audit passes
[ ] Regression validation passes
[ ] Evidence complete
[ ] Human acceptance obtained
[ ] Git consolidation completed
[ ] OpenSpec package archived
```

Only after all applicable gates are satisfied is the OpenSpec change considered successfully implemented.
