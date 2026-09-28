# DAPP Operational Requirements Context

## Document Purpose

This document consolidates the operational requirements provided by the business stakeholders for the next evolution of the DMS-TELECOM platform.

Its purpose is to serve as contextual input for future OpenSpec artifacts (`proposal.md`, `ears.md`, `tasks.md`) and for subsequent architecture, development, testing, and auditing activities.

This document is not a technical specification and does not prescribe implementation details.

---

# 1. Category and Unit of Measure Management

## Current Situation

The Inventory section contains global actions for:

* Modify
* Delete

These actions currently provide no practical administrative functionality for Categories and Units of Measure.

The Add action already behaves correctly and allows users to:

* Create new materials.
* Create new categories.
* Create new units of measure.

No changes are required to the current creation workflow.

---

## Operational Need

Administrators require the ability to manage existing catalog definitions.

### Categories

Administrators must be able to:

* Modify existing categories.
* Delete existing categories.

### Units of Measure

Administrators must be able to:

* Modify existing units of measure.
* Delete existing units of measure.

---

## Operational Consideration

A category or unit of measure may remain registered even when no materials are associated with it.

Administrators require the flexibility to decide whether to:

* Keep it available for future use.
* Remove it when it is no longer needed.

---

## Scope

This requirement applies exclusively to:

* Categories.
* Units of Measure.

It does not apply to the existing workflows used to modify or delete individual materials.

---

# 2. Fiber Optic Inventory Integration into Transfers

## Current Situation

The system correctly recognizes the General Inventory as a valid source and destination within transfer workflows.

The following inventories currently do not participate in transfer operations:

* Fiber Optic – Package
* Fiber Optic – In Use

---

## Operational Problem

Materials stored in Fiber Optic inventories cannot be directly assigned to teams through the existing transfer mechanisms.

As a result, inventories used daily in field operations remain outside the normal material distribution process.

---

## Operational Need

The following inventories must behave exactly like the General Inventory regarding:

* Material reception.
* Material transfers.
* TEAMS operations.
* DEVOL operations.

Inventories:

* Fiber Optic – Package
* Fiber Optic – In Use

---

## Expected Outcome

Teams must be able to receive materials from:

* General Inventory.
* Fiber Optic – Package.
* Fiber Optic – In Use.

The same inventory integrity, traceability, and operational rules currently applied to transfers must remain in effect.

---

# 3. Autonomous Team Inventory

## Operational Principle

Each team must maintain its own independent inventory.

Teams must not rely on the General Inventory to define their internal operational parameters.

---

## Team-Specific Configurable Parameters

Each team must be able to independently manage:

* Minimum stock.
* Category.
* Unit of measure.

These parameters belong to the team inventory and may differ from the master inventory definition.

---

## Non-Modifiable Fields

The following fields must remain immutable:

* Material code.
* Material description.

---

## Business Rationale

Teams require operational flexibility to adapt inventory control and counting processes without altering the master material definition.

---

## Operational Constraint

The mechanism used to determine current stock must remain unchanged.

Current stock continues to be derived exclusively from operational inventory movements.

Direct modification of current stock is not part of this requirement.

---

# 4. DEPLOYMENT Operations

## Objective

Introduce a new operation named DEPLOYMENT that functions independently for each team.

DEPLOYMENT represents the daily operational use of materials in field activities.

---

## Operating Principle

Each team owns:

* Its own inventory.
* Its own deployment records.

Operations performed by one team must remain independent from those of any other team.

---

## Relationship with TEAMS and DEVOL

DEPLOYMENT follows the same operational philosophy used by TEAMS and DEVOL.

However, DEPLOYMENT operates exclusively within the scope of an individual team.

---

## Expected Operational Flow

### Step 1

The team receives materials through the existing inventory transfer mechanisms.

### Step 2

Materials available within the team inventory can be assigned to a deployment record.

### Step 3

The deployment record captures:

* Materials used in field operations.
* Quantities taken.
* Operational observations.

### Step 4

At the end of the activity, users register:

* Remaining materials.
* Unused materials.

### Step 5

The system automatically updates team inventory balances.

---

## Operational Objectives

DEPLOYMENT must provide the ability to:

* Register materials used in field activities.
* Register remaining materials.
* Maintain inventory control at the team level.
* Preserve complete traceability.
* Reduce accidental modifications.
* Maintain operational isolation between teams.

---

# 5. Safe Team Consultation

## Current Situation

The only available method for viewing a team's internal inventory is through the edit workflow.

---

## Operational Risk

This behavior increases the likelihood of accidental modifications to operational data.

---

## Operational Need

A dedicated consultation view must be available.

This view must allow users to:

* Review inventory information.
* Review assigned materials.
* Review team-specific settings.

Without entering an edit workflow.

---

# 6. Reporting

## Objective

The Reporting section must focus on DEPLOYMENT operations.

---

## Required Information

Reports must allow verification of:

### Team Inventory

* Current inventory status.
* Available materials.

### DEPLOYMENT Activity

* Materials used.
* Materials assigned to deployments.
* Remaining materials.
* Movement traceability.

---

## Export Capability

Report data must be exportable in CSV format.

---

# Derived Operational Principles

The following principles consistently appear throughout the business requirements:

1. Team operational independence.
2. Complete inventory traceability.
3. Inventory integrity preservation.
4. Separation of consultation and editing workflows.
5. Administrative flexibility for catalog management.
6. Full participation of Fiber Optic inventories in transfer operations.
7. Formal registration of field material usage through DEPLOYMENT.
8. Preservation of the existing stock determination model based on inventory movements.

---

# Intended Usage

This document serves as the authoritative business-context reference for future OpenSpec work, including:

* Change Proposals.
* EARS Specifications.
* Architecture Reviews.
* Database Reviews.
* Security Reviews.
* Task Planning.
* Development Activities.
* Validation and Audit Processes.

Implementation decisions must be derived from formal specifications and not directly from this context document.
