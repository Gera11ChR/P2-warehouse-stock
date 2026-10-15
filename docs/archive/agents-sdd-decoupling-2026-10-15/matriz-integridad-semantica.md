# Matriz de Integridad Semántica por Subagente

Directiva maestra: Desacoplamiento de Dominio, Gobernanza SDD y Agnosticismo para Subagentes.
Fecha: 2026-10-15 · Commit base: `4ffb7d1` · Evidencia: `before/` (estado previo) vs. `after/` (estado resultante).

Comparación cruzada semántica (no literal) con las 6 dimensiones exigidas. Estado final: `[VALIDADO / REQUIERE CORRECCIÓN]`.

---

## 1. @arq-reviewer

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/arq-reviewer.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Checklist de auditoría: clasificación Dominio vs. Bug (Fase 0); alineación de invariantes constitucionales (stock no negativo, ledger append-only, mutaciones auditadas, prohibición de `UPDATE` directo); separación de preocupaciones (EARS vs tasks/DDL); confiabilidad e idempotencia (atomicidad vía Stored Functions). Rol gatekeeper Fases 0/1 y Sign-Off Fase 5. |
| **3. Mapeo de Ubicación (Antes → Después)** | "CURRENT DOMAIN STATUS" (cabecera) → reemplazado por bloques de Jerarquía Normativa y Agnosticismo (cabecera). Checklist §1-4 conservado en "AUDIT CHECKLIST" con misma numeración y orden. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. Los 4 items del checklist mantienen significado, rigor y obligatoriedad; los nombres concretos de tablas/funciones se sustituyeron por referencia a los artefactos normativos (DDL aprobado, `domain_rules`), sin debilitar la regla. |
| **5. Desacoplamiento de Dominio** | ELIMINADO el bloque de patrones P2 v1.0 y los nombres de entidades hardcodeados (`secciones_inventario`, `inventario_equipos`, `auditoria_eventos`, `historial_importaciones`, `fn_procesar_movimiento`). Se conservaron las referencias estructurales `docs/constitution.md`, `openspec/changes/`, `openspec/specs/`. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica detectada. Ninguna diferencia no autorizada. |
| **Estado final** | **[VALIDADO]** |

---

## 2. @auditor

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/auditor.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Golden Rule (prohibido código de feature; solo Drift Report en Compliance; solo eliminaciones en 3.5); 4 vectores de auditoría (Entity/Logic/Exception/Traceability Drift); soft-delete; delegación a Stored Functions; prohibición de `UPDATE` directo; mapeo de errores SQL a 400/422; payload JSONB estandarizado; estructura estricta del Drift Report; responsabilidades por fase SDD (0, 1, 3, 3.5, 5) |
| **3. Mapeo de Ubicación (Antes → Después)** | "CURRENT DOMAIN STATUS" → bloques normativos en cabecera. "GOLDEN RULE", "MANDATORY AUDIT VECTORS" (§1-4) y "DELIVERABLE STRUCTURE: DRIFT REPORT" conservados con estructura idéntica. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. Los 4 vectores conservan su función de auditoría; los nombres de funciones (`fn_procesar_movimiento`, `fn_cancelar_movimiento`, `fn_ajustar_stock_almacen`) quedaron como ejemplo etiquetado y la regla de delegación apunta a `domain_rules.transaction_delegation` (fuente normativa vigente que además lista más funciones). Estructura del Drift Report intacta. |
| **5. Desacoplamiento de Dominio** | ELIMINADOS nombres de tablas/funciones/archivos hardcodeados como normativos (`secciones_inventario`, `inventario_equipos`, `auditoria_eventos`, `historial_importaciones`, `src/routers/teams.py`). Ejemplos remanentes etiquetados `[Ejemplo Puramente Ilustrativo - Sujeto a Especificación Normativa]`. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. El ejemplo de finding conserva severidad/archivo/regla/código/acción. |
| **Estado final** | **[VALIDADO]** |

---

## 3. @coder

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/coder.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Pydantic V2 (DTOs); SQLAlchemy alineado a DDL; FastAPI; PostgreSQL 14+; restricciones SDD 1-4 (aislamiento Fase 3, supremacía de especificación, invarianza de firmas/tipos, CERO lógica transaccional en Python); delegación a Stored Functions (`fn_procesar_movimiento`, `fn_cancelar_movimiento`, `fn_cargar_stock_inicial`, `fn_ajustar_stock_almacen`); estándar de salida (typing, 400/422, async, docstrings) |
| **3. Mapeo de Ubicación (Antes → Después)** | "CURRENT DOMAIN STATUS" → bloques normativos en cabecera. "ROLES AND RESPONSIBILITIES", "STRICT SDD RESTRICTIONS" (§1-4), "DOMAIN ALIGNMENT" y "CODE OUTPUT STANDARD" conservados con misma estructura. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. Las 4 restricciones SDD mantienen su carácter obligatorio; la prohibición de lógica transaccional en Python y la delegación a Stored Functions permanecen como regla normativa, ahora referenciada a `domain_rules.transaction_delegation` (fuente vigente). Enums españoles y nombres de tablas fijados dejaron de ser lista cerrada en el prompt. |
| **5. Desacoplamiento de Dominio** | ELIMINADOS como normativos: enums (`GENERAL`, `FO_PAQUETE`, `FO_EN_USO`, `TEAMS`, `DEVOL`) y nombres de tablas (`id_lista`, `secciones_inventario`, `catalogo_materiales`). Nombres de funciones conservados únicamente como ejemplo etiquetado. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. "CURRENT_USER in PostgreSQL" generalizado a "approved session/authorization mechanism in PostgreSQL" (equivalente). |
| **Estado final** | **[VALIDADO]** |

---

## 4. @dba-guard

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/dba-guard.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Checklist de 4 puntos: migración de aislamiento con cero pérdida de datos y FKs; control de concurrencia con `FOR UPDATE` en transacción atómica o vía Stored Functions; seguridad de migraciones Alembic (`alembic/versions/`, `def downgrade()`); inmutabilidad de ledger (cero UPDATE/DELETE) |
| **3. Mapeo de Ubicación (Antes → Después)** | "CURRENT DOMAIN STATUS" → bloques normativos en cabecera. "CORE MANDATE", "ACTIVATION TRIGGERS" y "AUDIT CHECKLIST" (§1-4) conservados con misma numeración y orden. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. `FOR UPDATE` permanece como control normativo obligatorio (sin etiqueta ilustrativa); `alembic/versions/` y `def downgrade()` intactos como referencias estructurales. |
| **5. Desacoplamiento de Dominio** | ELIMINADOS nombres de tablas/funciones hardcodeados (`auditoria_eventos`, `historial_importaciones`, `fn_*`); la referencia a Stored Functions apunta a `domain_rules.transaction_delegation`. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. |
| **Estado final** | **[VALIDADO]** |

---

## 5. @form-agent

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/form-agent.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Regla constitucional (formulario captura intención; backend valida; PostgreSQL decide); workflows de carritos (temporalidad, no mutar inventario visual); proyecciones UX permitidas vs. stock persistido prohibido; carga inicial vía contrato oficial; ajuste diferencial (incremento/decremento); workflow de importación; React Hook Form + Zod para validación preliminar; restricciones absolutas (no SQL, no inventar endpoints, no ejecutar reglas transaccionales); criterio de éxito (inicio, captura, revisión, confirmación, resultado, recuperación) |
| **3. Mapeo de Ubicación (Antes → Después)** | Bloques normativos insertados en cabecera. Las 15 secciones originales conservadas: §3/§4/§5/§11 (dominio) purgadas y convertidas en referencias a artefactos; §6/§7 workflows conservados ("Carrito de Transferencia"/"Carrito de Devolución" con nomenclatura genérica oficial); §8-§15 intactas. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. La metodología de captura de intención, los workflows por pasos, la prohibición de decidir stock y React Hook Form + Zod mantienen su alcance. El listado fijo de campos `cantidad_*` pasó a "dictado por los DTO del contrato vigente" (misma obligación: no introducir variantes). |
| **5. Desacoplamiento de Dominio** | ELIMINADOS como normativos: lista de dominio obligatorio, vocabulario oficial fijo (`cantidad_inicial`, `cantidad_transferir`, `cantidad_devolver`, `cantidad_integrantes`, `cantidad_diferencial`), reglas concretas de catálogo (`TIPO`, `id_lista`), extensiones fijas (`.csv/.xlsx/.xml`, `.doc/.docx`). Todo vocabulario de negocio remanente etiquetado como ilustrativo. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. Secciones TEAMS→"Transferencia" y DEVOL→"Devolución" mantienen el mismo workflow. |
| **Estado final** | **[VALIDADO]** |

---

## 6. @qa-agent

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/qa-agent.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Autoridad Zero-Drift con validación Backend-First; principio de independencia; contract testing por capas (OpenSpec→OpenAPI→Pydantic→TS→React); Matriz de Trazabilidad (REQ-ID con test que pasa y asevera HTTP+BD); pruebas E2E; prueba de cancelación con transiciones de estado; invariantes (stock negativo, reversión exacta); auditoría JSONB; concurrencia con garantía `FOR UPDATE` desde PostgreSQL; Zero-Drift Scan; regresión; formato PASS/FAIL con estructura Finding→Severity→File/Line→Rule→Evidence→Correction; restricciones; criterios de éxito; principio final |
| **3. Mapeo de Ubicación (Antes → Después)** | "CURRENT DOMAIN STATUS" → bloques normativos en cabecera. Las 17 secciones originales conservadas en el mismo orden; §3, §7, §9 y §10 purgadas de vocabulario fijo y etiquetadas. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. Backend-First, trazabilidad, PASS/FAIL estricto, `FOR UPDATE`, Zero-Drift Scan y restricciones intactos. Transiciones CONFIRMADO→CANCELADO y campos de auditoría (actor, timestamp, action…) permanecen como ejemplo etiquetado, con remisión a los estados/campos dictados por el paquete activo y el DDL. |
| **5. Desacoplamiento de Dominio** | ELIMINADOS como normativos: TEAMS/DEVOL, `FO_PAQUETE`/`FO_EN_USO`, `id_lista` y reglas de aislamiento hardcodeadas. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. |
| **Estado final** | **[VALIDADO]** |

---

## 7. @sec-ops

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/sec-ops.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Default-deny; RBAC con alcance por recurso; defensa contra mass assignment con `extra = "forbid"` en Pydantic v2; aislamiento de secretos; triggers de activación (Fase 2, rutas, dependencias FastAPI, autenticación, parsing masivo) |
| **3. Mapeo de Ubicación (Antes → Después)** | "CURRENT DOMAIN STATUS" → bloques normativos en cabecera. "CORE MANDATE", "ACTIVATION TRIGGERS" y "AUDIT CHECKLIST" (§1-3) conservados. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. `extra = "forbid"` permanece como contrato de seguridad normativo sin etiqueta ilustrativa (per regla 3 de la directiva). |
| **5. Desacoplamiento de Dominio** | ELIMINADA la enumeración fija de formatos de ingesta (CSV/Excel/XML) como lista cerrada; sustituida por "formatos dictados por el contrato activo" con etiqueta ilustrativa. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. |
| **Estado final** | **[VALIDADO]** |

---

## 8. @state-agent

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/state-agent.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Jerarquía de autoridad (constitution→AGENTS→OpenSpec→FastAPI→TS→React); verificación completa de contrato API antes de consumir; fidelidad de interfaces TypeScript; gestión TanStack Query; regla de invalidación post-mutación; delimitación de estado local permitido; regla RFC (detener y proponer RFC, nunca parche silencioso); RBAC visual; restricciones (prohibida aritmética de stock como verdad, persistir inventario local, inventar DTOs/endpoints, duplicar lógica backend); criterio de éxito OpenSpec=FastAPI=TS=React |
| **3. Mapeo de Ubicación (Antes → Después)** | Bloques normativos insertados en cabecera. Las 14 secciones conservadas: §2 jerarquía alineada a los niveles L1-L5 oficiales de `.agents.md` §2; §3/§5/§6/§9 purgadas y etiquetadas; §4, §7, §8, §10-§14 intactas. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. Verificación de contrato, type safety, TanStack Query, invalidación, RFC y RBAC visual mantienen rigor. El ejemplo `MovimientoProcesarDTO` quedó etiquetado como ilustrativo conservando la regla "no introducir campos no declarados por el backend". Los hooks oficiales fijos se sustituyeron por "derivados de los contratos vigentes". |
| **5. Desacoplamiento de Dominio** | ELIMINADOS como normativos: catálogo de 53 materiales, `id_lista`, Sparse Model, `COALESCE`, TEAMS, DEVOL, hooks fijos (`useCatalogo`, `useEquipos`, `useMovimientos`, `useAuditoria`, `useReportes`) y ejemplo JSON concreto. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. |
| **Estado final** | **[VALIDADO]** |

---

## 9. @tester

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/tester.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Pytest + pytest-asyncio + httpx/TestClient; fixtures asíncronos contra PostgreSQL; Rigid Specification Baseline; trazabilidad `test_<REQ_ID>_...`; aislamiento transaccional; aserciones HTTP+BD; 7 suites obligatorias (aislamiento/catálogo, administración, transferencia, devolución, cancelaciones, importaciones/auditoría, concurrencia con `asyncio.gather` y `FOR UPDATE`); estructura de salida (rutas `backend/tests/integration/`, nomenclatura de funciones) |
| **3. Mapeo de Ubicación (Antes → Después)** | "CURRENT DOMAIN STATUS" → bloques normativos en cabecera. "ROLES AND RESPONSIBILITIES", "STRICT SDD RESTRICTIONS" (§1-4), las 7 suites y "TEST CODE OUTPUT STRUCTURE" conservadas con misma estructura y orden. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. Las 4 restricciones SDD, el formato `test_<REQ_ID>_<module>_<scenario>_<expected_result>()`, las bibliotecas y la ruta `backend/tests/integration/` intactos. Las 7 suites conservan su metodología (incluida la prueba de concurrencia con `asyncio.gather` validando el `FOR UPDATE` y el rechazo 400/422); los nombres concretos de entidades/estados se sustituyeron por "dictados por el paquete activo y el DDL aprobado" con etiqueta ilustrativa. |
| **5. Desacoplamiento de Dominio** | ELIMINADOS como normativos: nombres de tablas (`secciones_inventario`, `inventario_equipos`, `auditoria_eventos`, `historial_importaciones`, `catalogo_materiales`), funciones (`fn_procesar_movimiento`, `fn_cancelar_movimiento`, `fn_ajustar_stock_almacen`), estados (`BORRADOR`, `CONFIRMADO`, `CANCELADO`, `COMPLETADO`, `CON_ERRORES`), triggers y nombres de archivos de test concretos. |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. |
| **Estado final** | **[VALIDADO]** |

---

## 10. @ui-agent

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/ui-agent.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Stack React/TypeScript/Vite/Tailwind/React Router; regla constitucional del frontend (PostgreSQL→FastAPI→Frontend; nunca fuente de verdad); Design System (lista de 17 componentes reutilizables); layout Sidebar/Workspace/Drawer; navegación semántica sin duplicados; identidad visual DMS - TELECOM; reglas de tablas; unidades de medida renderizadas desde API sin alteración; restricciones absolutas (sin fetch/axios en componentes presentacionales, sin invalidateQueries en capa visual, sin reglas de negocio, sin renumerar identificadores); flujo de trabajo de 10 pasos; criterios de éxito; anti-patrones; entregable |
| **3. Mapeo de Ubicación (Antes → Después)** | Bloques normativos insertados en cabecera. Las 14 secciones conservadas: §3 (conocimiento de dominio) purgada a reglas genéricas con etiqueta; §5 (rutas), §7 (columnas de tablas) y §8 (unidades) purgadas a referencias con etiqueta; §2, §4, §6, §9-§14 intactas. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. La regla constitucional, la lista de componentes, el layout, las restricciones absolutas, el flujo de 10 pasos, los anti-patrones (`stock = stock - cantidad`, `material.id_lista = nuevoIndice`, `inventarioFake`, `stockLocalPersistente`) y el entregable permanecen idénticos. La regla de identificadores inmutables se conservó referenciando `domain_rules` (fuente normativa vigente `immutable_id_lista`). |
| **5. Desacoplamiento de Dominio** | ELIMINADOS como normativos: lista de ~20 materiales concretos (Acopladores, Cajas NAP, etc.), reglas específicas de `id_lista`, explicaciones de TEAMS/DEVOL/Fibra, rutas fijas (`/general`, `/equipos`, `/fibra/paquete`, ...), lista fija de unidades de medida (PZ, LT, M, CARRETE...) y columnas fijas de tablas (ID LISTA, SKU...). |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. |
| **Estado final** | **[VALIDADO]** |

---

## 11. @ux-agent

| Dimensión | Resultado |
| :--- | :--- |
| **1. Subagente / Archivo** | `.opencode/agents/ux-agent.md` (misma ruta antes y después) |
| **2. Directivas Técnicas Previas** | Regla constitucional (proyección UX ≠ autoridad transaccional); prevención de errores (confusión de materiales, módulos, unidades); gestión de riesgo UX (bajo/medio/alto) con contexto antes de confirmar; implementación de estados (Empty/Loading/Skeleton/Error Boundary/Confirm Dialog/Success/Warning/Toast/disabled/feedback); confirmación operativa con contexto completo; accesibilidad (teclado, focus, labels, ARIA, contraste, sin dependencia de color); traducción de errores técnicos a contexto operacional; restricciones (no decidir validez, stock o estados de movimientos); criterio de éxito (6 preguntas del operador) |
| **3. Mapeo de Ubicación (Antes → Después)** | Bloques normativos insertados en cabecera. Las 12 secciones conservadas: §3 (conocimiento de dominio) purgada y etiquetada; §4 (prevención de errores) con ejemplos concretos eliminados; §2, §5-§12 intactas. |
| **4. Integridad Semántica y Alcance** | CONSERVADA al 100%. Clasificación de riesgo, confirmaciones contextuales (con ejemplo etiquetado "¿Confirmar transferencia de 20 unidades..."), accesibilidad, error handling y las 6 preguntas del criterio de éxito permanecen. |
| **5. Desacoplamiento de Dominio** | ELIMINADOS como normativos: lista de dominio obligatorio (53 materiales, `id_lista`, TEAMS, DEVOL, Sparse Model, Fibra Paquete/En Uso) y ejemplos concretos de confusión (Splitter PLC 1x8 vs desbalanceado 20/80). |
| **6. Estado y Diferencias Pendientes** | Sin pérdida semántica. |
| **Estado final** | **[VALIDADO]** |

---

## Resumen global

| Subagente | Estado |
| :--- | :--- |
| @arq-reviewer | VALIDADO |
| @auditor | VALIDADO |
| @coder | VALIDADO |
| @dba-guard | VALIDADO |
| @form-agent | VALIDADO |
| @qa-agent | VALIDADO |
| @sec-ops | VALIDADO |
| @state-agent | VALIDADO |
| @tester | VALIDADO |
| @ui-agent | VALIDADO |
| @ux-agent | VALIDADO |

**Verificaciones de integridad ejecutadas:**
1. Los 3 bloques normativos (Jerarquía Normativa, Cláusula de Agnosticismo, Preservación Inmutable) presentes en los 11 archivos.
2. Controles técnicos normativos sin etiqueta ilustrativa: `FOR UPDATE` (dba-guard, qa-agent, tester), `extra = "forbid"` (sec-ops), formato PASS/FAIL (qa-agent), Golden Rule + Drift Report (auditor), trazabilidad `test_<REQ_ID>` (tester), prohibición de `UPDATE` directo (arq-reviewer, auditor, coder, dba-guard).
3. Vocabulario legacy (TEAMS, DEVOL, `FO_PAQUETE`, `FO_EN_USO`, `id_lista`) solo presente dentro de etiquetas `[Ejemplo Puramente Ilustrativo - Sujeto a Especificación Normativa]` o como anti-patrón prohibido.
4. Referencias estructurales conservadas en todos los archivos: `docs/constitution.md`, `.agents.md`, `openspec/changes/`, `openspec/specs/`, `alembic/versions/`, `backend/tests/integration/`.
