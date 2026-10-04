# OpenSpec Change Proposal

## Change ID
`2026-10-04-eliminar-breadcrumb-dashboard`

## Summary
Eliminación definitiva del elemento visual "Dashboard /" (prefijo/raíz de las
migas de pan o breadcrumbs) de la cabecera global de la aplicación. La
cabecera pasa a mostrar únicamente el nombre o ruta limpia de la sección
activa:

1. **Antes**: `Dashboard / Sección General`, `Dashboard / Fibra Óptica / Paquete`.
2. **Después**: `Sección General`, `Fibra Óptica / Paquete`.

Como el breadcrumb se renderiza en un único componente global
(`components/Header.tsx`), la eliminación del nodo raíz cubre TODAS las
secciones y subsecciones (Sección General, Fibra Óptica, Inventario por
Equipos, Transferencias, Reportes, Auditoría y sus subvistas) sin tocar
páginas individuales.

## Business Problem
- **Ruido visual sin valor informativo**: el prefijo "Dashboard" es un rótulo
  técnico que no describe la sección activa; duplica el contexto que ya
  aportan el logo de marca (DMS - TELECOM) y el menú lateral.
- **Contaminación semántica de las migas de pan**: un breadcrumb raíz debe
  identificar un nodo navegable real del sistema; "Dashboard" no es una ruta
  ni una sección del menú.

## Proposed Changes
1. **`frontend/src/components/Header.tsx`**: eliminar el `<span>Dashboard</span>`
   y el separador `<span className="mx-2 text-slate-300">/</span>` del `<nav>`.
   El breadcrumb limpio (prop ya generada por `MainLayout.tsx`) se renderiza
   directamente con su estilo actual (`font-medium text-slate-800`).
2. **Tests**: nuevo `components/__tests__/Header.test.tsx` (vitest) que
   verifica que "Dashboard" ya no se renderiza en la cabecera, que la ruta
   limpia de la sección sí se muestra y que el buscador global (placeholder,
   atajo Ctrl + K y callback `onSearch`) sigue operativo.

## Impact Assessment
- **Frontend**: `components/Header.tsx` (4 líneas removidas), nuevo
  `components/__tests__/Header.test.tsx`. Sin cambios en `MainLayout.tsx`,
  `Sidebar.tsx`, páginas, rutas ni URLs.
- **Backend**: ninguno.
- **Contrato OpenSpec**: ninguno (`openspec/openspec.yaml` no documenta el
  breadcrumb; `openspec/specs/` está vacío; cambio de UI puro con
  `skip_specs: true`, precedente: `2026-10-04-eliminar-buscador-a-granel`).

## Out of Scope
- Renombrados o cambios de etiquetas de sección (`LABELS`/`SUB_LABELS` en
  `MainLayout.tsx` se conservan intactos).
- Navegación: el Sidebar, las rutas/URLs reales y el `NavigationContext`
  permanecen 100 % funcionales.
- Cualquier cambio de backend, esquemas, migraciones o reglas de dominio de
  la Constitución (`openspec/openspec.yaml`).
