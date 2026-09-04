# P2 Telecommunications Warehouse Management System (WMS)

A full-stack enterprise inventory and logistics platform engineered for telecommunications warehouse operations, featuring strict domain localization, immutable audit tracking, and multi-warehouse stock management.

## Architecture & Tech Stack

* **Frontend:** React, TypeScript, Tailwind CSS, and Vite, structured around a responsive three-column layout (dark navigation sidebar, light workspace, and white detail drawer) with a real-time toast notification system.
* **Backend:** Python, FastAPI, and Pydantic DTOs, providing strict schema validation, extra-field rejection (`extra="forbid"`), and modular API routers.
* **Database Layer:** PostgreSQL powered by SQLAlchemy ORM, Alembic schema migrations, strict foreign key constraints, and an idempotent seeding script (`seed.py`) pre-configured with 53 general materials and 5 specialized fiber materials.

## Core Business Constraints & Specifications

* **Strict Spanish Domain Localization:** All user interfaces, database entities (*Almacén Central*), API error payloads, and audit logs are fully localized in Spanish.
* **Mandatory Field Ordering:** Enforces a rigid 1-to-6 field sequence across all drawers, forms, and validation rules:
  1. `DESCRIPCIÓN`
  2. `STOCK ACTUAL`
  3. `STOCK MÍNIMO`
  4. `ALERTA STOCK`
  5. `U.M.` (Unit of Measure)
  6. `CÓDIGO` (SKU)
* **Data Integrity & Security:** Protected by deletion guards (`_assert_deletable`) across all relational mapping tables to block unhandled foreign key crashes, alongside header-based actor scope authorizations.

## API Endpoints & Modules

| Router / Module | Purpose |
| :--- | :--- |
| `/api/v1/materials` | SKU catalog management, categories, units, and minimum stock rules. |
| `/api/v1/inventory` | Per-warehouse and per-SKU stock level queries with automated alerts. |
| `/api/v1/team-inventory` | Team-assigned asset tracking linking equipment, users, and quantities. |
| `/api/v1/fiber-optics` | Specialized fiber spool variant tracking (*metros restantes*). |
| `/api/v1/stock-transfers` | Inter-site warehouse stock transfer lifecycle execution. |
| `/api/v1/audit` | Localized system action logs and traceability tracking. |

## Getting Started

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Running Test Suite
```bash
pytest
```