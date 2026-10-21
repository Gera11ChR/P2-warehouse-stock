# Propuesta — ETAPA 3/3: REFERENCIA DE MATERIALES POR UNIDAD

**Paquete:** `2026-10-referencia-materiales-unidades` · **Fase SDD:** 3 (Especificación) · **Estado:** redactada, pendiente de aprobación del humano.
**Fuente de requisitos:** `docs/2 Unities Functions.docx`, sección «Referencia» (texto y las 4 capturas `Refer_Interfaz_Consl`, `Refer_Conslt`, `Refer_Conf` y `Refer_Interfaz_Conf`). Gobernanza: `docs/constitution.md` (L1), `.agents.md` (L2). Etapas previas ya promovidas a `openspec/specs/003_inventory_dashboard` (`REQ-ACT-*`, `REQ-REP-*`); se consultan solo como puntos de integración.

## 1. Motivación

Hoy el administrador no tiene una forma de dejar anotado, **por Unidad**, qué materiales y qué cantidad semanal maneja cada cuadrilla. La anotación se hace a mano en cada material. La Etapa 3 incorpora la **Referencia**: una lista visual por Unidad, sin efecto contable, que se arma una vez eligiendo materiales ya existentes (nomenclatura oficial) y se consulta cuando se necesita.

## 2. Qué dice el negocio (y qué NO dice)

El documento define, textualmente o en capturas:

- La Referencia es «solo un aspecto visual de referencia para demarcar la cantidad de manejo semanal de materiales que lleva a cabo cada unidad»; es **independiente para cada Unidad**.
- Botón **«Referencia»** en la parte superior derecha del Inventario por Unidad, tanto en **Consulta** (solo despliega la tabla) como en **Configuración** (permite añadir, modificar y eliminar líneas).
- Tabla **«Materiales Referencia»** con las columnas **Descripción**, **U.M.** y **Cantidad Semanal**.
- En Configuración: botón verde **«+ Agregar»** con un menú de origen (**Inventario General** o **Inventario Fibra Óptica**) y un **selector dependiente de Material** que muestra el stock entre paréntesis; cada línea captura MATERIAL y CANTIDAD, con papelera por línea y botón «+ Agregar línea». «La cantidad no afecta el inventario, los materiales y cantidad son un aspecto visual».
- Al seleccionar un material de la tabla se puede **Eliminar** o **Modificar**.
- Los materiales de la Referencia «no afectan en ningún momento los inventarios» ni la base de datos de inventarios y materiales existentes.

El documento **no** define unidades de medida nuevas, equivalencias ni conversiones. El humano confirmó que la Etapa 3 cubre **solo la Referencia por Unidad** (las «Unidades» del título son las Unidades operativas); cualquier conversión de U.M. queda fuera de alcance y requeriría un paquete propio con sus reglas de negocio.

## 3. Alcance

**Dentro:**
- Persistencia por Unidad en una **tabla propia de PostgreSQL** (migración `0030`) con auditoría por trigger.
- API REST de lectura y escritura bajo `/api/v1/equipos/{equipo_id}/referencia`.
- Interfaz: botón «Referencia», tabla «Materiales Referencia», panel de alta con selección dependiente (origen → material), modificar y eliminar.
- Pruebas de migración, `sql_tests`, API (`pytest`), frontend (`vitest`) y verificación visual con Playwright Chromium.

**Fuera (no objetivos):**
- Unidades de medida nuevas, equivalencias y conversiones.
- Cualquier efecto sobre stock, movimientos, seguimientos, actividades, actas, reportes o catálogo.
- Validación de la cantidad semanal contra el stock; alertas, metas o comparaciones de consumo.
- Exportación de la Referencia (XLSX/CSV) y reportes sobre ella.
- Autenticación real, cambios a los permisos existentes y rediseño de Inventario por Unidad.

## 4. Arquitectura de integración

```
Inventario por Unidad (InventarioPorEquipos.tsx)
 ├─ Consulta ──┐
 ├─ Configuración ─┼─ botón «Referencia» ─► panel «Materiales Referencia»
 ├─ CONSUMO       │      Consulta: solo lectura · Configuración: Agregar / Modificar / Eliminar
 └─ ACTIVIDADES   │
                  ▼
   hooks (React Query) ─► /api/v1/equipos/{equipo_id}/referencia  (GET · POST · PATCH · DELETE)
                  ▼
   router delgado ─► servicio (ORM tipado) ─► tabla referencia_materiales ─► trigger de auditoría
                                                │
                                                └─ FK RESTRICT → equipos, catalogo_materiales (solo lectura del catálogo)
   Datos de selección (sin cambios de contrato): GET /inventario/secciones/{id} (General) y GET /fibra (Inventario FO)
```

- **Aislamiento total:** la Referencia no usa Stored Functions de stock ni toca `inventario_*`, `catalogo_materiales`, `equipo_material_config`, `movimientos_*`, `seguimientos`, `actividades_reportes` ni `actas_reportes`.
- **Descripción y U.M. en vivo:** se obtienen del catálogo por JOIN en cada consulta; la Referencia solo guarda `(equipo_id, material_id, cantidad_semanal)`.
- **Datos para el selector dependiente:** el frontend reutiliza los endpoints de lectura existentes (Inventario General e Inventario FO); no se modifican sus contratos.
- **Backend-First:** DB → servicio → router → pruebas → congelación del contrato (T7) → frontend (T8-T10).

## 5. Límites defensivos

| Límite | Valor | Respuesta |
| --- | --- | --- |
| Líneas por petición de alta | 1..50 (todo o nada) | 422 |
| `cantidad_semanal` | `> 0`, ≤ 3 decimales, `NUMERIC(12,3)` | 422 |
| Material repetido en la misma petición | no permitido | 422 `REFERENCIA_LINEA_DUPLICADA` |
| Material ya presente en la Referencia de la Unidad | no permitido (usar Modificar) | 409 `REFERENCIA_DUPLICADA` |
| Campos no declarados / `extra` | prohibidos (`extra="forbid"`) | 422 |
| Identificadores fuera de INT4 | rechazados | 400 `NUMERIC_OUT_OF_RANGE` |
| Escritura sobre Unidad inactiva | no permitida | 404 |

## 6. Decisiones de diseño acordadas con el humano

| ID | Decisión | Origen |
| --- | --- | --- |
| D-1 | Alcance: **solo Referencia por Unidad**; sin conversiones de U.M. | Respuesta del humano |
| D-2 | Persistencia en **tabla propia de PostgreSQL** (no `localStorage`), compartida entre usuarios y auditada | Respuesta del humano |
| D-3 | Edición permitida al **administrador y a los integrantes de la Unidad** (`assert_equipo_access`, igual que Configuración); lectura con el mismo criterio | Respuesta del humano |
| D-4 | `openapi.snapshot.json` nace como **borrador** (`frozen: false`) y se congela con `frozen: true` en T7 generado del OpenAPI vivo | Respuesta del humano |

## 7. Decisiones de diseño propuestas (a ratificar en T1, `@arq-reviewer`)

| ID | Propuesta | Razón |
| --- | --- | --- |
| D-5 | Guardar `material_id` (FK `RESTRICT`), no un texto copiado | «Nomenclatura existente» y sin duplicar datos; Descripción/U.M. siempre vigentes |
| D-6 | Mutaciones por ORM tipado + trigger de auditoría (sin Stored Function de stock) | No es una mutación de stock; mismo patrón que la configuración local por Unidad |
| D-7 | Origen «Inventario General / Inventario FO» es solo ayuda de interfaz: el backend valida que el material exista y esté activo en el catálogo | El origen no se persiste ni aporta un invariante propio |
| D-8 | «Modificar» cambia solo `cantidad_semanal`; cambiar de material = eliminar y agregar | El documento no define otra edición |
| D-9 | «Eliminar» borra físicamente la línea; el trigger conserva `valores_anteriores` en el ledger de auditoría | La Referencia es configuración, no ledger ni catálogo (Constitución §2.4 aplica a transacciones) |
| D-10 | Los materiales inactivos del catálogo no se listan; la línea se conserva y reaparece si se reactivan | Cero fantasmas, sin perder la configuración |
| D-11 | Orden del listado: Descripción ascendente y `material_id` ascendente | Determinista y ergonómico; el documento no fija el orden |
| D-12 | El botón «Referencia» va en el extremo derecho de la barra de subsecciones de Inventario por Unidad y alterna (muestra/oculta) el panel en Consulta y Configuración | Posición de las capturas |
| D-13 | Etiqueta de interfaz «Inventario FO» (nomenclatura oficial `.agents.md` §3) donde el documento dice «Inventario Fibra Óptica» | Cláusula de override de nomenclatura |
| D-14 | Lectura permitida con la Unidad dada de baja; escritura solo con Unidad activa | Conserva el historial visible, como las actividades |

## 8. Riesgos

| Riesgo | Mitigación |
| --- | --- |
| No existe combobox/autocompletar de materiales en el frontend | Componente nuevo y acotado en T9, con pruebas y verificación visual |
| Un selector de cientos de materiales degrada la usabilidad móvil | Selector con búsqueda y verificación a 390 px en T9 |
| Confundir la Referencia con stock real | Textos explícitos en la interfaz («no afecta el inventario») y spec `REQ-REF-011` |
| Deriva de nomenclatura (Equipo/Inventario Fibra Óptica) | Barrido existente `nomenclaturaUnidad` cubre `src/**`; D-13 |
| Pruebas de infraestructura con listas de tablas (`TRUNCATE`) | T3 añade la tabla nueva a `backend/tests/conftest.py` y `backend/sql_tests/conftest.py` |

## 9. Reversibilidad

Migración `0030` con `downgrade()` que elimina trigger, función y tabla sin tocar objetos preexistentes. Revertir el paquete consiste en retirar el router, el servicio y los componentes nuevos; los eventos de auditoría ya escritos se conservan (ledger inmutable).

## 10. Impacto constitucional

Sin enmiendas. Se respetan §1 (SDD), §2 (la Referencia no altera saldos ni identidad de materiales), §3 (default-deny y alcance por Unidad, `extra="forbid"`), §4 (cada petición en una transacción atómica; el alta masiva es todo o nada), §5.1 y §5.3 (contratos explícitos y validación todo-o-nada), §6.2 (auditoría inmutable de cada mutación) y §7 (trazabilidad `REQ-REF-*` y cuadro de calidad).
