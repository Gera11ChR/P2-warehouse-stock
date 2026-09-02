# Project P2: System Architecture & Engineering Governance Constitution

## Preamble
This Constitution establishes the non-negotiable legal framework, domain invariants, and system principles for **Project P2 (Enterprise Fiber Optic Logistics & Fleet Inventory System)**. It governs all software behavior, specifications, design decisions, and AI agent execution. Technical implementation details (frameworks, drivers, and tools) are defined in downstream Architecture Specifications and MUST conform to the principles set forth herein.

---

## 1. Specification Supremacy & SDD Governance

* **1.1 Traceable Change Mandate:** No state-changing code, database schema modification, or interface component shall be created or modified without an approved OpenSpec change set (`proposal.md`, `spec.md`, `tasks.md`).
* **1.2 Requirement vs. Design Separation:** Specifications MUST strictly separate *Requirements Specifications* (what the system must do from a domain perspective) from *Design Specifications* (how the architecture and software realize those requirements).
* **1.3 Canonical Source of Truth:** Specifications serve as the authoritative contract for system behavior. Divergences between code and specification MUST be resolved by amending the specification first.
* **1.4 EARS Requirements Syntax:** All functional requirements MUST be authored using formal EARS syntax (*Ubiquitous, Event-Driven, State-Driven, Option-Driven, Unwanted Behavior*). Informal or ambiguous statements are invalid.
* **1.5 Requirement Traceability Identifiers:** Every functional and non-functional requirement MUST possess a unique, immutable identifier formatted as `[REQ-<DOMAIN>-<NUMBER>]` (e.g., `[REQ-STOCK-001]`).

---

## 2. Core Domain Invariants & Data Integrity

* **2.1 Non-Negative Balance Invariant:** Stock balance for any managed asset (reels, drop cables, splices) SHALL NOT drop below zero unless explicitly governed by a documented, approved negative-inventory business rule.
* **2.2 Material Identity & Allocation Invariant:** Deployed fiber optic hardware MUST maintain explicit relational binding to a single physical location, warehouse entity, or assigned field crew vehicle. An asset SHALL NOT simultaneously exist in incompatible states or unassigned loose states.
* **2.3 State Serialization:** All inventory state transitions MUST be strictly serialized such that concurrent operations cannot produce race conditions, double-allocations, or invalid stock quantities.
* **2.4 Immutable Ledger & Counter-Adjustments:** Historical inventory transactions, movements, and audit logs are append-only. Historical records SHALL NOT be mutated or deleted via API operations. Discrepancies MUST be resolved exclusively via traceable, audit-logged counter-adjustments referencing the target event.

---

## 3. Cybersecurity, Zero-Trust & Access Control

* **3.1 Default-Deny Authorization:** Every system endpoint and service boundary MUST enforce explicit authorization using a default-deny posture. Requests lacking verifiable credentials or necessary authority MUST be rejected with explicit authorization failure responses.
* **3.2 Resource-Scoped Authorization:** Access control MUST enforce least privilege at both the role level and resource-scope level (e.g., restricting an operator's write actions to their explicitly assigned warehouse or fleet node).
* **3.3 Privileged Access Protection:** Access to administrative endpoints, systemic configurations, and sensitive operations MUST require Multi-Factor Authentication (MFA) prior to elevated session issuance.
* **3.4 Secret Isolation:** Hardcoding credentials, encryption keys, API secrets, or certificates within source code, version control, or static configuration files is strictly forbidden. All secrets MUST be injected dynamically via secure environment runtime contexts.
* **3.5 Defense Against Payload Injection:** All dynamic incoming payloads MUST undergo strict schema validation and attribute filtering prior to processing to prevent mass-assignment, property injection, and unvalidated data binding.
* **3.6 Credential & Transport Security:** All transmitted data MUST utilize industry-approved, secure encrypted transport channels. Stored credentials MUST be hashed using approved, adaptive, memory-hard key derivation algorithms.

---

## 4. Reliability, Transactional Atomicity & Idempotency

* **4.1 Transactional Atomicity:** Any operation modifying multi-entity state (e.g., deducting warehouse stock while committing a fleet allocation) MUST execute within an atomic transaction boundary. Partial state commits are strictly prohibited.
* **4.2 Operation Idempotency:** Any network-exposed or asynchronous operation capable of being retried MUST be designed idempotently to prevent unintended duplicate state side-effects upon retry.
* **4.3 Recoverability & Crash Safety:** System failures during multi-step batch or bulk operations MUST leave the system in a consistent, uncorrupted state, enabling safe recovery or rollbacks without manual database manipulation.

---

## 5. API Governance & Ergonomic Ingestion

* **5.1 Explicit API Contracts:** All externally exposed interfaces MUST maintain versioned, schema-validated contracts adhering to standard HTTP semantics, deterministic error payloads, and strict property typing.
* **5.2 Bulk Processing Ergonomics:** For high-volume inventory operations, interfaces MUST support ergonomic bulk dataset staging and pre-commit validation.
* **5.3 All-or-Nothing Bulk Validation:** Bulk data ingestions MUST undergo comprehensive schema and business rule checks prior to persistence. If any item within a bulk payload violates a rule, the entire batch transaction MUST be rejected without partial application, identifying the exact error coordinates.

---

## 6. Observability, Metrics & Auditability

* **6.1 Structured Telemetry:** The system MUST produce structured, machine-readable application logs containing correlation/trace IDs across every transaction lifecycle.
* **6.2 Security & Operational Audit Events:** All authentication attempts, privilege elevations, state modifications, and inventory adjustments MUST emit immutable audit events capturing timestamp, actor, target entity, and exact change context.

---

## 7. Quality Assurance, Evidence & Definition of Done

* **7.1 Multi-Modal Verification Mapping:** Every requirement (`[REQ-XXX-000]`) MUST map to at least one documented, automated, or deterministic verification method appropriate to its nature (e.g., unit test, integration test, static security scan, schema validation, or formal acceptance verification).
* **7.2 Definition of Done (Quality Gates):** A change set SHALL NOT be merged, deployed, or archived unless:
  1. All mapped automated test suites pass with a **100% pass rate**.
  2. Production interface builds compile with **zero type errors and zero build warnings**.
  3. OpenSpec validation CLI (`openspec validate --specs --strict`) passes with **0 schema violations**.
  4. All defined domain invariants remain provably unviolated.

---

## 8. Constitutional Governance & Amendments

* **8.1 Amendment Procedure:** This Constitution may only be amended through a formal OpenSpec proposal detailing the rationale, technical impact, and migration plan for existing specifications.
* **8.2 Non-Bypassability:** Neither automated AI sub-agents nor human developers possess authority to bypass constitutional rules without an approved constitutional amendment.