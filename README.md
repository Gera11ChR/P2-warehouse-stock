# DMS - TELECOM | Warehouse Management System (WMS)

[![Status](https://img.shields.io/badge/Status-Estable_v1.0.0-blue.svg)](#)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-Pydantic_V2-009688.svg)](#)
[![Database](https://img.shields.io/badge/PostgreSQL-18_PL%2FpgSQL-336791.svg)](#)
[![QA Suite](https://img.shields.io/badge/Pytest-93%2F93_Passed-success.svg)](#)
[![Type Checking](https://img.shields.io/badge/Mypy-Strict_0_Errors-blue.svg)](#)

Sistema de gestión de inventarios y logística para operaciones de telecomunicaciones basado en **FastAPI** y **PostgreSQL**. Diseñado bajo principios de atomicidad transaccional, trazabilidad inmutable y gobernanza estricta mediante contratos de especificación.

---

## 📋 Flujo del Negocio

El sistema resuelve el problema logístico de asignación y retorno de materiales críticos (herrajes, bobinas de fibra, ONTs) en despliegues de red:

```text
[ Catálogo Maestro / SKUs ]
           │
           ▼
[ Carga Inicial de Stock ] ──► (Almacén Central)
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
[ Transferencia a Cuadrillas (TEAMS) ]                 [ Ajustes e Inventario ]
            │                                                     │
            ▼                                                     ▼
[ Devolución de Material (DEVOL) ]                      [ Auditoría Inmutable ]

```

---

## ✨ Características Principales

* **Gestión de catálogo de materiales**: Control de SKUs, unidades de medida y niveles mínimos.
* **Control de inventario por almacén**: Monitorización en tiempo real de existencias.
* **Transferencias TEAMS**: Asignación de stock a cuadrillas operativas.
* **Devoluciones DEVOL**: Retorno de materiales y equipos al almacén central.
* **Ajustes controlados de inventario**: Correcciones justificadas y auditadas de diferenciales.
* **Auditoría transaccional (*Append-Only*)**: Registro inmutable de toda operación de impacto.
* **Soft-delete para entidades operativas**: Preservación del historial manteniendo la integridad referencial.
* **API REST documentada**: Endpoints validados con esquemas estrictos de FastAPI/Pydantic.

---

## 📐 Arquitectura del Sistema

La arquitectura sigue el patrón **Zero-Legacy**: la capa API opera exclusivamente como transporte y validación estricta, delegando el control de concurrencia y la mutación de estado al motor de base de datos relacional.

```text
┌─────────────────────────────────────────────────────────────────┐
│              React / Vite Frontend (Tailwind CSS)               │
└─────────────────────────────────────────────────────────────────┘
                                │ (HTTP / JSON)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              FastAPI Backend (Pydantic V2 Extra=Forbid)         │
└─────────────────────────────────────────────────────────────────┘
                                │ (SQLAlchemy Async / Psycopg3)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL 18 Engine                          │
│  ├── fn_procesar_movimiento()   [FOR UPDATE / Locking]          │
│  ├── fn_cancelar_movimiento()   [Reversión transaccional]       │
│  ├── fn_ajustar_stock_inicial() [Alta idempotente]              │
│  └── fn_ajustar_stock_almacen() [Control de diferenciales]      │
└─────────────────────────────────────────────────────────────────┘

```

---

## 🔒 Invariantes del Dominio

* **Invariante 1 (`id_lista` Inmutable)**: Campo de lista autogenerado en catálogos, bloqueado ante mutaciones vía API.
* **Invariante 2 (Sparse Model)**: Consulta unificada de existencias aplicando `COALESCE(stock_actual, 0)` en vistas SQL.
* **Invariante 3 (Nomenclatura Única)**: Almacenamiento exclusivo en la entidad `inventario_almacen` para stock físico.
* **Invariante 4 (Selector Dual)**: Clasificación de materiales mediante `categoria_id` (existente) o `nueva_categoria` sin redundancia.
* **Invariante 5 (Delegación Transaccional)**: Mutación de inventario restringida únicamente a Stored Functions de `PL/pgSQL`.

---

## 🔄 Operaciones de Inventario

El ciclo de vida del almacén está gobernado por cinco operaciones fundamentales:

1. **Carga Inicial**: Alta primera de stock en un almacén para un material (idempotente).
2. **Transferencias (TEAMS)**: Movimiento negativo del almacén y positivo hacia la cuadrilla técnica.
3. **Devoluciones (DEVOL)**: Movimiento negativo desde la cuadrilla y positivo hacia el almacén central.
4. **Ajustes**: Corrección directa de existencias (+/-) con código de justificación (ej. mermas, robos, auditorías físicas).
5. **Cancelaciones**: Reversión exacta de un movimiento (TEAMS/DEVOL) previo, restaurando atómicamente el estado del inventario.

---

## 📜 Gobernanza OpenSpec (SDD)

El proyecto evoluciona mediante **Spec-Driven Development (SDD)**. Toda modificación funcional se rige por:

1. **Contrato OpenSpec**: Especificación previa de endpoints en `openspec/openspec.yaml`.
2. **Validación de Agentes**: Revisión arquitectónica, de base de datos y de seguridad (`.opencode/agents/`).
3. **Zero-Drift**: Implementación estricta y sin desviaciones sobre el contrato aprobado.

---

## 📂 Estructura del Repositorio

```text
P2-warehouse-stock/
├── backend/
│   ├── alembic/              # Migraciones DDL de base de datos
│   ├── app/                  # Código fuente de FastAPI (Routers, Core, Models, Services)
│   ├── db/                   # Contrato DDL de base de datos (ddl.sql)
│   └── tests/                # Suite E2E de pruebas aisladas
├── data/                     # Archivos de siembra inicial (Excel DMS)
├── docs/                     # Informes de auditoría y dictámenes
├── frontend/                 # Aplicación SPA cliente (React/Vite)
└── openspec/                 # Especificaciones del contrato API y reglas de negocio

```

---

## 🚀 API (Endpoints Principales)

| Módulo | Ruta | Método | Descripción Operativa |
| --- | --- | --- | --- |
| **Movimientos** | `/api/v1/movimientos/procesar` | `POST` | Transferencias TEAMS/DEVOL vía `fn_procesar_movimiento`. |
| **Movimientos** | `/api/v1/movimientos/{id}/cancelar` | `POST` | Reversión atómica vía `fn_cancelar_movimiento`. |
| **Ajustes** | `/api/v1/ajustes/carga-inicial` | `POST` | Alta de stock vía `fn_ajustar_stock_inicial`. |
| **Ajustes** | `/api/v1/ajustes/stock-almacen` | `POST` | Corrección diferencial vía `fn_ajustar_stock_almacen`. |
| **Catálogo** | `/api/v1/catalogo` | `GET / POST` | Consulta y registro de SKUs activos/inactivos. |
| **Equipos** | `/api/v1/equipos` | `GET / POST` | Administración de cuadrillas operativas. |
| **Auditoría** | `/api/v1/auditoria` | `GET` | Lectura del ledger inmutable de eventos. |

---

## 🖥️ Frontend

Interfaz de usuario responsiva desarrollada con:

* **Framework**: React + Vite (TypeScript)
* **Estilos**: Tailwind CSS
* **Arquitectura de UI**: Layout de 3 columnas (Sidebar de navegación, Workspace de tablas, Drawer de detalles).

---

## ⚙️ Configuración (Variables de Entorno)

Crea un archivo `.env` en el directorio `backend/`. **Utiliza únicamente credenciales de tus entornos locales o de servidor; nunca expongas contraseñas reales en repositorios públicos.**

```env
# Conexión principal de la API
P2_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/p2

# Conexión con privilegios para ejecución DDL / Migraciones Alembic
P2_ADMIN_DATABASE_URL=postgresql://ADMIN_USER:ADMIN_PASSWORD@127.0.0.1:5432/p2

# Base de datos aislada para la suite automatizada de QA
P2_TEST_DATABASE_URL=postgresql+psycopg://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/p2_test

```

---

## 🛠️ Instalación

### Base de Datos

Requiere instancia activa de **PostgreSQL 18**.

```bash
# Ejecutar migraciones DDL hasta la revisión actual
cd backend
alembic upgrade head

```

### Backend (FastAPI)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

```

### Frontend (React)

```bash
cd frontend
npm install
npm run dev

```

---

## 🧪 QA (Validación y Pruebas)

El backend cuenta con una suite automatizada robusta ejecutada contra una base de datos real (aislada vía truncado en cascada).

```bash
cd backend
# Ejecutar suite completa con Pytest
.venv/bin/python -m pytest tests/ -v

# Ejecutar verificación estática de tipos con Mypy
.venv/bin/python -m mypy app/ tests/

```

---

## 📖 Documentación Interactiva

Con el backend en ejecución, accede a los contratos de la API en tiempo real:

* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Contrato Base:** Revisar `openspec/openspec.yaml` para las reglas de negocio puras.

---

## 📌 Estado del Proyecto

**Versión:** v1.0.0

**Estado:** Estable

### Validación Actual

* 93 pruebas E2E automatizadas (100% de cobertura de endpoints base) ejecutadas contra PostgreSQL.
* Entorno de pruebas completamente aislado (`p2_test`).
* Validación estática sin hallazgos (`Mypy Strict`).
* Lógica concurrente transaccional delegada y centralizada exitosamente en Stored Functions.
* Sistema de auditoría (*ledger*) integrado y operativo.

### Alcance Actual

El sistema cubre formalmente el flujo core logístico: Catálogo de materiales, Inventario base de almacén, Asignaciones (TEAMS), Devoluciones (DEVOL), Ajustes de diferencial, Cancelaciones/Reversiones y la Auditoría de dichos movimientos.

### Limitaciones Conocidas

* **Autenticación (AuthN / AuthZ):** Actualmente se gestiona el RBAC mediante el paso de `usuario_id` en headers/payloads (entorno confiable). La integración con un Identity Provider externo (OAuth2/JWT) está planificada para fases futuras.
* **Manejo de Bobinas de Fibra Óptica:** La lógica hiper-especializada de cortes parciales (*metros restantes*) se maneja como stock unificado; el submódulo de rastreo serializado por bobina se encuentra en desarrollo.

---

## 📄 Licencia

Este proyecto está bajo licencia MIT. Consulta el archivo `LICENSE` para más detalles.

```

```