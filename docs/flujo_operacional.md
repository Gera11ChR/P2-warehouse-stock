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

---

# 2. Current Development Priority

The current initiative is:

## Backend Logistics Alignment

Based on the approved Issue Breakdown, the highest-priority backend concerns are:

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

These priorities drive all planning and implementation activities until completion.

---

# 3. Core Operating Principles

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

Examples:

### Allowed

Frontend stock editing that produces:

```text
Adjustment Event
   +
Audit Record
   +
Ledger Entry
```

### Forbidden

Direct inventory mutation that bypasses:

```text
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

Tests exist to verify requirements.

Not code.

Every implemented requirement must be traceable to at least one automated verification artifact.

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

# 4. SDD Execution Pipeline

---

# Phase 0 — Domain & Architecture Validation

## Purpose

Determine whether the requested changes fit the existing domain model or require structural evolution.

## Agents

* arq-reviewer
* auditor

## Inputs

* Issue Breakdown
* Proposal Draft
* Existing OpenSpec Documentation

## Activities

* Classify each issue:

  * Bug Fix
  * Functional Enhancement
  * Domain Change

* Identify:

  * New entities
  * New relationships
  * Deprecated assumptions
  * Inventory ownership impacts

## Deliverable

Domain Validation Report

## Exit Criteria

Every issue is classified and architectural direction is approved.

---

# Phase 1 — Specification & Constitutional Impact Review

## Purpose

Create the formal contract governing implementation.

## Agents

* arq-reviewer
* auditor

## Inputs

* Approved Domain Validation Report

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

* Affected invariants
* Risks
* Mitigation strategy

Examples:

* Immutable Ledger
* Non-Negative Inventory
* Transaction Atomicity
* Audit Preservation

## Exit Criteria

OpenSpec package approved and internally consistent.

---

# Phase 2 — Data, Schemas & Security Design

## Purpose

Prepare the database and API contracts before implementation.

## Agents

* dba-guard
* sec-ops

## Inputs

Approved specifications.

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

* Tasks
* Migrations
* Schemas

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

## Exit Criteria

All tasks completed without deviations from specifications.

---

# Phase 3.5 — Refactor & Dead Code Audit

## Purpose

Remove obsolete artifacts without mixing cleanup and feature development.

## Agent

* auditor

## Activities

* Remove deprecated endpoints
* Remove dead services
* Remove unused imports
* Simplify redundant modules
* Identify legacy code paths

## Deliverable

Refactoring Report

## Exit Criteria

No unused implementation remains related to replaced behavior.

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

Move completed change:

```text
openspec/changes/<change-name>
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
* Archived Specification
* Merged Branch

## Exit Criteria

Change fully integrated and archived.

---

# 5. Agent Responsibility Matrix

| Domain      | Agents                | Responsibility                                    |
| ----------- | --------------------- | ------------------------------------------------- |
| Governance  | arq-reviewer, auditor | Domain validation, specification review, sign-off |
| Database    | dba-guard             | DDL, migrations, schema integrity                 |
| Security    | sec-ops               | Authorization, RBAC, payload validation           |
| Backend     | coder                 | FastAPI, SQLAlchemy, services, APIs               |
| Refactoring | auditor               | Cleanup and technical debt control                |
| Testing     | tester, qa-agent      | Verification and traceability                     |

---

# 6. Immediate Next Action

Execute:

```text
Phase 0 — Domain & Architecture Validation
```

Target Issues:

1. Team Inventory Isolation
2. Fiber Optic Inventory Isolation
3. Stock Editing Under Immutable Ledger Constraints

Expected Outcome:

A formal determination of whether these requirements can be implemented within the current logistics model or require a domain evolution before entering specification and implementation phases.
