# OpenSpec Change Proposal

## Change ID
`2026-10-fo-unificado-valor-unitario`

## Fuente de insumo (efímera)
`docs/1 Changes.docx` (Parte 1: Solo_FO.png · Parte 2: Valor_Unitario.png). El
documento es únicamente el insumo inicial: toda la especificación oficial
reside en este paquete. Tras el archivado (Fase 8/9) el `.docx` pierde toda
autoridad operativa y NO debe referenciarse desde `.agents.md`.

## Resumen

Dos cambios de dominio acoplados por el mismo módulo de inventario:

1. **Parte 1 — Inventario FO unificado.** Se eliminan los subapartados
   `Inventario Paquete` / `Inventario En Uso` de Fibra Óptica. Todo el material
   de fibra óptica vive en una única locación general: **Inventario FO**.
2. **Parte 2 — Valuación económica.**
   - Nueva variable `valor_unitario` (MXN, con decimales) en el catálogo de
     materiales, visible en todos los inventarios (General, FO, Unidades) y
     editable al modificar un material.
   - Nuevo indicador **Valor Total** (entre `Total Materiales` y `Stock Total`):
     `Σ (stock_actual_i × valor_unitario_i)` sobre Inventario General +
     Inventario FO, calculado por PostgreSQL.
   - Precisión decimal `NUMERIC(12,3)` / `Decimal` / `number` para
     `valor_unitario` **y** para el stock y las cantidades de movimiento
     (alcance ampliado confirmado por el solicitante). Los identificadores
     (PK/FK) permanecen `INTEGER`/`BIGINT`.

## Contexto y Problema

- **Ineficiencia operacional.** Mantener FO dividida en dos inventarios obliga
  a elegir "módulo" antes de cualquier operación (carga, ajuste, +Cantidad,
  Mover, TRANSF, eliminación) y fragmenta la existencia de un mismo material
  en dos filas. El solicitante lo califica de "poco práctico".
- **Sin valuación económica.** El sistema conoce cantidades pero no su valor:
  no existe forma de responder cuánto vale el inventario en tiempo real.
- **Cantidades solo enteras.** `stock_actual`, `cantidad`, `cantidad_tomada` y
  los parámetros de las stored functions son `INT`; no admiten fracciones
  (p. ej. 2.5 m de cable), lo que el solicitante pide resolver en esta misma
  entrega.

## Solución Propuesta

| Eje | Decisión |
| :-- | :-- |
| FO | `inventario_fibra` deja de particionarse por `modulo`: una fila por material. Migración que **suma** las filas PAQUETE y EN_USO existentes (cero pérdida) y deja un evento de auditoría por material fusionado. |
| Secciones FO | Se añade el manejador de ruteo único `FO` (tipo `FO`). `FO_PAQUETE` / `FO_EN_USO` se conservan **solo como referencia histórica** del ledger inmutable (no transferibles, no seleccionables). |
| Valor unitario | `catalogo_materiales.valor_unitario NUMERIC(12,3) NOT NULL DEFAULT 1.000 CHECK (>= 0)`. Una sola fuente para los tres inventarios (se muestra por JOIN al catálogo). Auditado por el trigger existente de materiales. |
| Valor Total | Cálculo en PostgreSQL (nunca en Python ni React) y expuesto en `GET /api/v1/inventario/resumen-general`. |
| Decimales | `ALTER COLUMN ... TYPE NUMERIC(12,3)` en existencias y cantidades; stored functions re-publicadas con parámetros `NUMERIC(12,3)`; DTOs `Decimal` serializados como número JSON. |
| API | `modulo` desaparece del contrato FO (rutas `/fibra`, `/fibra/materiales/{id}`, `sumar-cantidad`, `mover`). Contrato versionado y congelado antes del frontend. |

## Decisiones de diseño aprobadas (resumen)

1. Valor Total calculado en backend; excluye materiales inactivos y no valora
   Unidades.
2. PK de `inventario_fibra` pasa a `material_id`; sección de ruteo `FO` nueva.
3. `Decimal` se serializa como número JSON (TypeScript `number`); entrada con
   más de 3 decimales se **rechaza** (422), nunca se redondea en silencio.
4. `stock_minimo` y `stock_minimo_local` permanecen `INT` (fuera del listado del
   solicitante).
5. `spec.md` expresa *qué* (decimales, límites); `plan.md` expresa *cómo*
   (`NUMERIC(12,3)`, DDL), conforme a Constitución §1.2.
6. Cada requisito es `RF-n` y lleva alias constitucional `[REQ-<DOMINIO>-<NNN>]`
   (Constitución §1.5, prevalece sobre `.agents.md` §6).
7. Pruebas en `backend/tests/` con nombre `test_RF_<n>_...` (estructura real del
   repositorio).

## Prerrequisito P0 (fuera de T1..Tn)

El paquete `openspec/changes/2026-10-04-saneamiento-deuda-tecnica/` (26/26 tareas completadas) **ya fue archivado** en `openspec/changes/archive/` (2026-10-15, verificado) antes de iniciar la Fase 7, dejando un único paquete activo (`.agents.md` §2). P0 queda como comprobación idempotente de inicio: si `openspec/changes/` volviera a contener más de un paquete activo, detenerse y solicitar aclaración humana.

## Mapeo de las 9 Fases Canónicas SDD

| Fase | Aplicación a este cambio |
| :-- | :-- |
| **1. Constitución** | Invariantes que el cambio debe preservar: §2.1 saldo no negativo (CHECK `stock_actual >= 0` se conserva con decimales); §2.4 ledger inmutable (los movimientos y eventos históricos con `FO_PAQUETE`/`FO_EN_USO` no se reescriben; la unificación se registra como eventos nuevos); §6.2 auditoría (todo cambio de `valor_unitario` emite evento con valores anterior/nuevo); §4.1 atomicidad (la migración y las funciones operan en una transacción); §2.3 serialización (`FOR UPDATE` en el nuevo esquema FO). Enmienda constitucional: **no requerida**. |
| **2. Contexto Agente** | Rige `.agents.md` (L2): nomenclatura oficial `Inventario FO`/`Unidad`/`TRANSF`; Backend-First; Zero-Drift. Cláusula de efimeridad: este paquete es el único contexto activo; al archivarse pierde autoridad y `.agents.md` no conserva referencias a él ni a `1 Changes.docx`. |
| **3. Especificación** | `spec.md` con `RF-1`..`RF-10` en sintaxis EARS, alias `[REQ-...]`, escenarios y casos límite. Gate: `@arq-reviewer`. |
| **4. Clarificación** | Revisión de ambigüedades (lista en `spec.md` §3.2) y casos límite decimales por `@arq-reviewer` y validación de criterios por `@qa-agent`. Sin ambigüedades abiertas = condición para pasar a Fase 5. |
| **5. Planificación** | `plan.md`: migración Alembic `0027`, stored functions, DTOs Pydantic v2, endpoints FastAPI, punto de Congelación Contractual y capa frontend. Gates: `@arq-reviewer`, `@dba-guard`, `@sec-ops`. |
| **6. Tareas** | `tasks.md` con `T1`..`T7`, agente asignado y "Hecho cuando:". |
| **7. Implementación (Backend-First)** | DB (`@dba-guard`) → API (`@coder`) → pruebas (`@tester`) → **Congelación Contractual** (`@qa-agent`) → Frontend (`@form-agent`/`@state-agent`/`@ui-agent`/`@ux-agent`). Frontend bloqueado hasta la congelación. |
| **8. Validación y Auditoría** | Pytest 100 %, Matriz de Trazabilidad (todo `RF-x` con test que asevera HTTP **y** estado de BD), Drift Report (`@auditor`), `openspec validate --strict`, `mypy`, `tsc -b`, eslint, build. Aprobación múltiple y archivado formal. |
| **9. Evolución** | Promoción de los `RF-n` a `openspec/specs/` (specs maestras `001/003`), archivado del paquete en `openspec/changes/archive/2026-10-fo-unificado-valor-unitario/`, actualización de `openspec/openspec.yaml` (`domain_rules`) e inhabilitación de este contexto de implementación. |

## Impacto

- **Backend:** migración `0027`; modelos SQLAlchemy (`catalogo_materiales`,
  `inventario_*`, `movimientos_detalle`, `seguimiento_items`,
  `auditoria_eventos`); 12+ stored functions; schemas `inventario`, `material`,
  `operadores`, `ajuste`, `movimiento`, `seguimiento`, `reporte`, `auditoria`;
  routers `fibra`, `inventario`, `catalog`; servicio `transaccional`.
- **Frontend:** `FibraOptica.tsx`, `Sidebar.tsx`, `KpiCards.tsx`,
  `MaterialForm.tsx`, `FibraMaterialForm.tsx`, tablas de inventario, `types.ts`,
  `services/fibra.ts`, utilidades de etiquetas, `Transferencias.tsx`.
- **Gobernanza:** `openspec/openspec.yaml` (`domain_rules`) se actualiza en la
  Fase 9 para declarar `FO_PAQUETE`/`FO_EN_USO` como valores históricos del
  ledger y `valor_unitario` como atributo de catálogo auditado.
- **Constitución:** intacta; sin enmienda.

## Riesgos

| # | Riesgo | Mitigación |
| :-- | :-- | :-- |
| R1 | Alcance amplio: el stock decimal toca >10 stored functions y la suite de >300 tests. | Migración única y reversible; `@dba-guard` revisa cada función; Backend-First con congelación. |
| R2 | `auditoria_eventos.cantidad` (ledger append-only) es `INT`; cambiarla a `NUMERIC` altera el tipo de una tabla inmutable. | El `ALTER TYPE` reescribe sin disparar triggers de fila ni mutar valores; requiere visto bueno de `@arq-reviewer` y `@dba-guard` y prueba de que el conteo/valores previos permanecen idénticos. |
| R3 | Movimientos históricos con secciones `FO_PAQUETE`/`FO_EN_USO` deben seguir siendo cancelables tras la unificación. | `fn_cancelar_movimiento` enruta ambos tipos legacy al inventario FO unificado; prueba dedicada (RF-9). |
| R4 | `downgrade()` no es totalmente reversible si ya existe stock fraccional o filas FO ya fusionadas. | `downgrade()` ABORTA con mensaje explícito si existe stock/cantidad con fracción; la fusión PAQUETE+EN_USO no se re-divide: el `downgrade()` restaura la existencia total (cero pérdida de cantidad) en `modulo='PAQUETE'` y lo declara como reversión con pérdida de la partición histórica; documentado en `plan.md` §1.7. |
| R5 | Cualquier consumidor que envíe `modulo` recibirá 422 (`extra="forbid"`). | Cambio de contrato versionado; frontend actualizado tras la congelación; barrido de tests. |
| R6 | Desbordamiento: stock × valor puede exceder 12 dígitos. | `Valor Total` es `NUMERIC` sin tope en el cálculo (se redondea solo al final); columnas individuales acotadas por `NUMERIC(12,3)`. |
