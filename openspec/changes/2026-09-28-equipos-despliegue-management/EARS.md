# EARS Requirements Specification

## Domain: Operational Catalog Management
- **REQ-CATALOG-001:** WHEN an administrator selects the "Modificar" button in the Category or U.M. section, THE SYSTEM SHALL display a dedicated interface to edit existing entries.
- **REQ-CATALOG-002:** WHEN an administrator selects the "Eliminar" button in the Category or U.M. section, THE SYSTEM SHALL allow the removal of existing entries, including entries without associated materials, at the administrator's discretion (keep for future use OR remove).
- **REQ-CATALOG-003:** WHEN a category or U.M. entry is modified or removed, THE SYSTEM SHALL emit an immutable audit event capturing the actor and the change context.

## Domain: Fiber Optic Warehouses
- **REQ-FO-001:** THE SYSTEM SHALL explicitly include "Fibra Óptica - Paquete" and "Fibra Óptica - En Uso" as recognized warehouse options within the transfer functionality.
- **REQ-FO-002:** WHEN materials are transferred from or to Fiber Optic sections, THE SYSTEM SHALL apply the same transfer logic and uniform behavior used for the General Inventory.

## Domain: Team Inventory Autonomy
- **REQ-TEAM-001:** THE SYSTEM SHALL preserve the material code and description as immutable data within the team's autonomous inventory to guarantee traceability.
- **REQ-TEAM-002:** THE SYSTEM SHALL NOT allow manual modification of a team's current stock ("stock actual") through any workflow; current stock derives exclusively from operational inventory movements (transfers or deployments).
- **REQ-TEAM-003:** WHEN a user configures a team's inventory, THE SYSTEM SHALL allow the independent modification of team-specific stock minimum, category, and unit of measure parameters.
- **REQ-TEAM-004:** WHEN a team's operational parameters are modified locally, THE SYSTEM SHALL NOT affect the General Inventory's master data.

## Domain: Deployment Operations (DESPLIEGUE)
- **REQ-DEPLOY-001:** THE SYSTEM SHALL provide a "DESPLIEGUE" function, acting as an extension of the transfer flow, applied internally and independently to each team.
- **REQ-DEPLOY-002:** WHEN a deployment list is generated, THE SYSTEM SHALL record the selected materials and the quantities taken for field use.
- **REQ-DEPLOY-003:** THE SYSTEM SHALL record the operational observations entered during the deployment.
- **REQ-DEPLOY-004:** WHEN the workday concludes, THE SYSTEM SHALL allow the registration of remaining or unused material within the deployment list.
- **REQ-DEPLOY-005:** WHEN remaining materials are registered, THE SYSTEM SHALL automatically adjust the team's current stock and preserve the traceability of the consumed materials.
- **REQ-DEPLOY-006:** WHEN a deployment is created or closed, THE SYSTEM SHALL emit immutable audit events capturing the actor, team, materials, quantities and resulting stock adjustments.

## Domain: Safe Team Access
- **REQ-VIEW-001:** THE SYSTEM SHALL provide a dedicated view to consult the team's internal inventory without the risk of altering data.

## Domain: Operational Reporting
- **REQ-REPORT-001:** THE SYSTEM SHALL restrict the Reports section to generate information centered exclusively on the DESPLIEGUE function and its associated team inventory.
- **REQ-REPORT-002:** WHEN a report is generated, THE SYSTEM SHALL export the used-materials data as a CSV document.
