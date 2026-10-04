# EARS: Eliminación del prefijo "Dashboard /" en la cabecera (frontend)

Requisitos del cambio `2026-10-04-eliminar-breadcrumb-dashboard` en notación
EARS (Ubiquitous / Event-driven / State-driven / Option-driven / Unwanted).
Clasificación de severidad: **CRÍTICO** (constitucional) · **ALTO** · **MEDIO**.

> Convenciones: "Cabecera" = componente global `Header` del frontend.
> "Ruta limpia" = etiqueta de la sección activa sin prefijo raíz
> (ej. "Sección General", "Fibra Óptica / Paquete").

## 1. Limpieza visual de la cabecera

- **REQ-BREAD-001 (Ubiquitous / ALTO).** La cabecera **deberá** renderizar
  la miga de pan SIN el texto "Dashboard" ni el separador "/" que lo
  antepone: el nodo raíz "Dashboard /" **deberá** desaparecer de todas las
  vistas.
- **REQ-BREAD-002 (Ubiquitous / ALTO).** La cabecera **deberá** mostrar
  únicamente la ruta limpia de la sección activa, incluidas las subvistas
  compuestas (ej. "Fibra Óptica / Paquete", "Reportes / Consumo").

## 2. Preservación funcional

- **REQ-BREAD-003 (State-driven / ALTO).** **Cuando** un usuario navegue por
  el Sidebar, **el sistema deberá** conservar la navegación 100 % funcional,
  con las rutas/URLs reales y el `NavigationContext` intactos; solo cambia la
  representación visual del breadcrumb.
- **REQ-BREAD-004 (Ubiquitous / MEDIO).** El buscador global de la cabecera
  **deberá** permanecer operativo: placeholder "Buscar materiales, SKU o
  descripción...", atajo Ctrl + K y callback `onSearch` sin alteraciones.

## 3. Zero-drift e invariantes

- **REQ-BREAD-005 (Unwanted / CRÍTICO).** La eliminación **no deberá**
  producir efectos colaterales: backend, contrato `openspec/openspec.yaml`,
  ledger inmutable y etiquetas de sección (`LABELS`/`SUB_LABELS`) **deberán**
  permanecer inalterados; las suites backend (pytest) y frontend (vitest)
  **deberán** seguir al 100 %.
- **REQ-BREAD-006 (Ubiquitous / ALTO).** El cambio **deberá** contar con al
  menos una prueba automatizada (vitest) que verifique que "Dashboard" no se
  renderiza en la cabecera y que la ruta limpia sí se muestra
  (Constitution 7.1).
