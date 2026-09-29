# DMS-TELECOM Backend Development Operating Model

## Specification-Driven Development (SDD) with OpenSpec

**Effective Date:** September 2026

**Project Context:** P2 → DMS-TELECOM Transition

**Repository Structure:** Consolidated Monorepo (`~/P2`)

**Primary Objective:** Deliver backend changes required by the current Issue Breakdown while preserving architectural integrity, constitutional invariants, traceability, and long-term maintainability.

---

# 1. Purpose

This document defines the official backend development workflow for DMS-TELECOM.

The workflow exists to ensure that:

* Business requirements are translated into formal specifications before implementation.
* Domain-level changes are identified before code is written.
* Constitutional invariants remain protected.
* Database, API, and security concerns are designed intentionally.
* Every implemented requirement is verifiable through automated tests.
* Technical debt is controlled through structured auditing and refactoring.
* All agents operate under a single authoritative document hierarchy.

---

# 2. Repository Governance Structure

```text
~/P2
│
├── .opencode/
│   └── agents/
│
├── backend/
├── frontend/
│
├── docs/
│   ├── constitution.md
│   ├── flujo_operacional.md
│   └── archive/
│
├── openspec/
│   ├── changes/
│   │   └── 2026-09-22-frontend-backend-alignment/
│   │       ├── proposal.md
│   │       ├── EARS.md
│   │       ├── issues-breakdown.md
│   │       ├── constitution-impact.md
│   │       └── tasks.md
│   │
│   └── specs/
│
├── .agents.md
└── README.md
```

---

# 3. Document Authority Hierarchy

All agents MUST follow the document hierarchy below.

## Level 1 — Supreme Authority

```text
docs/constitution.md
```

Defines:

* Business invariants
* Security invariants
* Architectural invariants
* Non-negotiable rules

---

## Level 2 — Operational Governance

```text
docs/flujo_operacional.md
.agents.md
```

Defines:

* Workflow execution
* Agent responsibilities
* Approval flow
* Development governance

---

## Level 3 — Active Change Package (Udoc2)

```text
openspec/changes/2026-09-22-frontend-backend-alignment/

proposal.md
EARS.md
issues-breakdown.md
```

These three documents collectively form:

```text
Udoc2
```

Udoc2 is the operational source of truth for the active initiative.

---

## Level 4 — Derived Execution Documents

```text
constitution-impact.md
tasks.md
```

These documents translate Udoc2 into executable implementation work.

---

## Level 5 — Implementation Artifacts

```text
backend/
frontend/
tests/
```

Code must conform to all higher-level documents.

---

# 4. Current Development Priority

The active initiative is:

## Frontend-Backend Contract Alignment & Domain Adjustments

Based on Udoc2, the highest-priority backend concerns are:

### Priority A — Inventory Domain Alignment

1. Team Inventory Isolation
2. Fiber Optic Inventory Isolation
3. Elimination of Global Catalog Coupling

### Priority B — Data Integrity

4. Category Persistence
5. Ghost Record Elimination
6. Active Inventory Filtering

### Priority C — Administrative Operations

7. Editable SKU
8. Editable Stock Through Audited Adjustments
9. Human-Readable Audit Records

No work outside these priorities may be introduced without a new OpenSpec change package.

---

# 5. Core Operating Principles

## Principle 1 — Specification Before Implementation

No backend code shall be created or modified before:

* Proposal approval
* Requirement definition
* Task decomposition

Workflow:

```text
Issue
 ↓
Proposal
 ↓
EARS Requirements
 ↓
Tasks
 ↓
Implementation
 ↓
Testing
 ↓
Integration
```

---

## Principle 2 — Domain Change Is Not a Bug

The following changes must be treated as potential domain modifications:

* Inventory isolation
* Catalog ownership changes
* Inventory lifecycle changes
* Warehouse model changes
* Material identity changes

These changes require architectural validation before implementation.

---

## Principle 3 — Constitution Supremacy

The Constitution remains the highest authority.

Allowed:

```text
Adjustment Event
      +
Audit Record
      +
Ledger Entry
```

Forbidden:

```text
Direct Inventory Mutation
      Without
Audit
Ledger
Authorization
Transaction Boundaries
```

---

## Principle 4 — Backend Is the Source of Truth

The frontend may:

* Validate inputs
* Improve usability
* Format information

The backend remains responsible for:

* Inventory calculations
* Business rules
* State transitions
* Authorization decisions
* Audit generation

---

## Principle 5 — Requirement-Based Verification

Tests verify requirements.

Not implementation details.

Example:

```text
REQ-CAT-001
      ↓
test_category_persistence()

REQ-STOCK-004
      ↓
test_stock_adjustment_generates_audit_event()
```

---

## Principle 6 — Backend-First Rule

For the current initiative:

Frontend implementation is blocked until:

1. Domain validation is completed.
2. Backend specifications are approved.
3. Database design is approved.
4. API contracts are finalized.

Frontend may only consume approved backend contracts.

Frontend SHALL NOT redefine backend behavior.

---

# 6. Pre-Phase Validation Gate (Udoc2)

Before any implementation work begins, the following documents MUST exist:

```text
proposal.md
EARS.md
issues-breakdown.md
```

These documents collectively form:

```text
Udoc2
```

Agents MUST verify:

1. Every Issue appears in the Proposal.
2. Every Proposal item maps to one or more EARS requirements.
3. Every EARS requirement traces back to an originating Issue.

Implementation is blocked if traceability is incomplete.

---

# 7. Traceability Matrix Requirement

The following chain MUST exist before coding:

```text
Issue
 ↓
Proposal Item
 ↓
EARS Requirement
 ↓
Task
 ↓
Implementation
 ↓
Test
```

Missing links invalidate the change package.

---

# 8. SDD Execution Pipeline

---

# Phase 0 — Domain & Architecture Validation

## Purpose

Determine whether requested changes fit the current domain model or require domain evolution.

## Agents

* arq-reviewer
* auditor

## Inputs

### Governance

```text
docs/constitution.md
docs/flujo_operacional.md
.agents.md
```

### Udoc2

```text
proposal.md
EARS.md
issues-breakdown.md
```

### Existing Architecture

```text
openspec/specs/
backend/
```

## Activities

Classify each issue as:

* Bug Fix
* Functional Enhancement
* Domain Change

Identify:

* New entities
* New relationships
* Deprecated assumptions
* Inventory ownership impacts
* Catalog ownership impacts

## Deliverable

```text
Domain Validation Report
```

## Exit Criteria

Every issue classified and architectural direction approved.

---

# Phase 1 — Specification & Constitutional Impact Review

## Purpose

Create the formal implementation contract.

## Agents

* arq-reviewer
* auditor

## Inputs

Approved Domain Validation Report

## Deliverables

Inside:

```text
openspec/changes/<change-name>/
```

### proposal.md

Business justification and scope.

### EARS.md

Formal requirements.

### tasks.md

Implementation breakdown.

### constitution-impact.md

Mandatory analysis documenting:

* Immutable Ledger
* Non-Negative Inventory
* Transaction Atomicity
* Audit Preservation
* Authorization Boundaries

## Constitutional Review Gate

Phase 2 is blocked until:

```text
constitution-impact.md
```

is approved.

## Exit Criteria

OpenSpec package approved and internally consistent.

---

# Phase 2 — Data, Schemas & Security Design

## Purpose

Prepare database structures and API contracts before implementation.

## Agents

* dba-guard
* sec-ops

## Inputs

Approved OpenSpec package.

## Activities

### Database

* Schema review
* DDL changes
* Migration strategy
* Index validation

### API Contracts

* Pydantic models
* DTO validation
* Error contracts

### Security

* RBAC review
* Authorization boundaries
* Payload validation

## Deliverables

```text
backend/alembic/versions/
backend/db/ddl.sql
backend/app/schemas/
```

## Exit Criteria

Schema, contracts, and security model approved.

---

# Phase 3 — Backend Implementation

## Purpose

Implement approved functionality.

## Agent

* coder

## Inputs

* tasks.md
* EARS.md
* Approved migrations
* Approved schemas

## Activities

### API

```text
backend/app/api/v1/
```

### Services

```text
backend/app/services/
```

### Models

```text
backend/app/models/
```

### Business Rules

* Inventory filtering
* Category persistence
* Audit generation
* Stock adjustment workflows
* Catalog isolation
* Inventory isolation

## Exit Criteria

All approved tasks completed with no specification deviations.

---

# Phase 3.5 — Refactor & Dead Code Audit

## Purpose

Remove obsolete artifacts separately from feature implementation.

## Agent

* auditor

## Activities

* Remove deprecated endpoints
* Remove dead services
* Remove unused imports
* Simplify redundant modules
* Identify legacy code paths

## Deliverable

```text
Refactoring Report
```

## Exit Criteria

No obsolete implementation remains related to replaced behavior.

---

# Phase 4 — Requirement-Based Testing & QA

## Purpose

Verify compliance with specifications.

## Agents

* tester
* qa-agent

## Inputs

* Implemented code
* EARS requirements
* tasks.md

## Activities

### Automated Tests

```text
backend/tests/
```

### Traceability Matrix

Generate:

```text
REQ-ID
   ↓
Test Artifact
```

### Validation

* pytest
* mypy
* regression testing

## Deliverables

* New automated tests
* Traceability Matrix
* QA Report

## Exit Criteria

* All tests pass
* No regressions detected
* Every requirement mapped to verification

---

# Phase 5 — Integration, Archive & Sign-Off

## Purpose

Finalize and formally close the change.

## Agents

* arq-reviewer
* auditor

## Activities

### Architecture Review

Final compliance validation.

### OpenSpec Closure

Move:

```text
openspec/changes/<change-name>/
```

to:

```text
openspec/changes/archive/
```

### Git Integration

Merge:

```text
feat/backend-logistics-fixes
```

into:

```text
main
```

## Deliverables

* Architecture Sign-Off
* Archived Specification Package
* Merged Branch
* Final Traceability Record

## Exit Criteria

Change fully integrated and archived.

---

# 9. Agent Responsibility Matrix

| Domain                  | Agents                                      | Responsibility                                    |
| ----------------------- | ------------------------------------------- | ------------------------------------------------- |
| Governance              | arq-reviewer, auditor                       | Domain validation, specification review, sign-off |
| Database                | dba-guard                                   | DDL, migrations, schema integrity                 |
| Security                | sec-ops                                     | Authorization, RBAC, payload validation           |
| Backend                 | coder                                       | FastAPI, SQLAlchemy, services, APIs               |
| Refactoring             | auditor                                     | Cleanup and technical debt control                |
| Testing                 | tester, qa-agent                            | Verification and traceability                     |
| Frontend (Future Phase) | ui-agent, ux-agent, form-agent, state-agent | UI adaptation after backend approval              |

---

# 10. Definition of Done (DoD)

A backend change is considered complete only when:

✓ Udoc2 requirements are fully implemented

✓ constitution-impact.md is satisfied

✓ tasks.md is completed

✓ Traceability Matrix is complete

✓ pytest passes

✓ mypy passes

✓ No regression is detected

✓ Architecture Sign-Off is approved

✓ OpenSpec package is archived

✓ Git integration is completed

---

# 11. Immediate Next Action

Execute:

```text
Phase 0 — Domain & Architecture Validation
```

Target Udoc2 Priorities:

1. Team Inventory Isolation
2. Fiber Inventory Isolation
3. Editable Stock Under Immutable Ledger Constraints

Expected Outcome:

A formal determination of whether the current logistics model can support these requirements or whether a domain evolution must occur before specification and implementation proceed.
