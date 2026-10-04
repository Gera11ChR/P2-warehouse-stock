# EARS: Eliminación del Buscador a granel (frontend)

Requisitos del cambio `2026-10-04-eliminar-buscador-a-granel` en notación
EARS (Ubiquitous / Event-driven / State-driven / Option-driven / Unwanted).
Clasificación de severidad: **CRÍTICO** (constitucional) · **ALTO** · **MEDIO**.

> Convenciones: "Inventario General" = vista `SeccionGeneral` del frontend.
> "Buscador principal" = búsqueda unificada por SKU/código, nombre
> (descripción), categoría o término directo con paginación.

## 1. Simplificación de la interfaz

- **REQ-SIMPL-001 (Ubiquitous / ALTO).** El sistema **deberá** renderizar la
  vista de Inventario General SIN la pestaña "2 Buscador a granel" ni
  ninguna barra de pestañas: la tabla del buscador principal y su paginación
  **deberán** mostrarse directamente como única vista de la pantalla.
- **REQ-SIMPL-002 (Ubiquitous / ALTO).** La vista **deberá** carecer de los
  campos de rango "Desde número de lista", "Hasta número de lista",
  "Desde descripción", "Hasta descripción" y del botón "Buscar" asociado a
  la modalidad a granel.

## 2. Depuración de código muerto

- **REQ-SIMPL-003 (Ubiquitous / ALTO).** El frontend **deberá** quedar sin
  código muerto del buscador a granel: sin componente `BulkSearch`, sin
  estado `tab`, sin handlers de rango, y sin los campos de filtrado bulk
  (`desde_numero_lista`, `hasta_numero_lista`, `desde_descripcion`,
  `hasta_descripcion`) en el servicio de catálogo.

## 3. Preservación del buscador principal

- **REQ-SIMPL-004 (State-driven / ALTO).** **Cuando** un usuario autorizado
  abra Inventario General, **el sistema deberá** conservar intacto y fluido
  el buscador general por SKU, nombre, categoría o término directo, con sus
  filtros de U.M., categoría y almacén, paginación y operadores
  (+Cantidad / Mover / edición / eliminación) operando como antes.

## 4. Zero-drift e invariantes

- **REQ-SIMPL-005 (Unwanted / CRÍTICO).** La eliminación **no deberá**
  producir efectos colaterales: el backend, el contrato
  `openspec/openspec.yaml`, el ledger inmutable (Constitution 2.4) y los
  flujos de ingesta por lotes (Constitution 5.2/5.3) **deberán** permanecer
  inalterados; las suites backend (pytest) **deberán** seguir al 100 %.
- **REQ-SIMPL-006 (Ubiquitous / ALTO).** El cambio **deberá** contar con al
  menos una prueba automatizada (vitest) que verifique que la pestaña
  "Buscador a granel" no se renderiza y que la vista principal se muestra
  (Constitution 7.1).
