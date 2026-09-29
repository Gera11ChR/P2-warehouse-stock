# Operational Feedback and Pending Fixes (Nis Report)

## Overview
This document details the current operational issues and verified functionalities based on the recent system implementation. The objective is to resolve discrepancies in the catalog management and material creation workflows.

## 1. Missing Target Sections in Initial Load ("Carga Inicial")
* **Current Problem:** In the "Sección General", when an operator uses the "Agregar Material" form, the "SECCIÓN DESTINO" dropdown within the "CARGA INICIAL" section only displays "Inventario General"[cite: 34]. The system fails to display the Fiber Optic warehouses ("Fibra Óptica - Paquete" and "Fibra Óptica - En Uso") as valid destination options. 
* **Operational Need:** The "SECCIÓN DESTINO" selector must accurately reflect all available warehouses. Operators need the ability to assign initial stock directly to "Fibra Óptica - Paquete" or "Fibra Óptica - En Uso" during the material creation process.

## 2. Validation Error with Dynamic Units of Measure ("U.M.")
* **Current Problem:** When an administrator attempts to save a material using a newly created or renamed "U.M." (e.g., "METRO (M)"), the system rejects the action and displays a red "Ocurrió un error X" notification. The system only accepts the operation if the "U.M." is reverted to its original, pre-existing base nomenclature.
* **Operational Need:** The "U.M." selector in the material forms must accept the dynamically managed catalog entries. The backend validation must allow administrators to use any actively created or modified "U.M." without triggering an "Ocurrió un error X" state, ensuring full catalog flexibility.

## 3. Verified Functionality: Transfers ("Transferencias")
* **Status:** The "Transferencias" module is functioning exactly as intended.
* **Details:** Both "Fibra Óptica - Paquete" and "Fibra Óptica - En Uso" successfully appear as selectable options for the "Equipo Origen" and "Sección Destino" fields during "TEAMS" and "DEVOL" operations. 
* **Conclusion:** Aside from the two issues mentioned above, the rest of the implementation fully meets the operational needs of the company.  