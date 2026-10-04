# OpenSpec Change Proposal

## Change ID
`2026-10-04-eliminar-buscador-a-granel`

## Summary
Eliminación definitiva del componente "Buscador a granel" de la interfaz
gráfica y del flujo de frontend del Inventario General, simplificando la
vista para que el operador trabaje directamente con el buscador principal
(SKU, nombre, categoría o término directo):

1. **UI**: remover la pestaña "2 Buscador a granel" (y con ella la barra de
   pestañas completa, que queda con una sola vista útil) junto con los
   campos de rango "DESDE NÚMERO DE LISTA", "HASTA NÚMERO DE LISTA",
   "DESDE DESCRIPCIÓN", "HASTA DESCRIPCIÓN" y su botón "Buscar".
2. **Código muerto React**: eliminar el componente `BulkSearch.tsx`, el
   estado `tab`, el render condicional y los campos de filtrado bulk del
   servicio `catalog.ts` que únicamente daban soporte a esta modalidad.
3. **Backend intacto**: cero cambios de API, esquemas, migraciones o
   funciones SQL. El backend conserva los parámetros de rango de
   `GET /api/v1/catalogo` (REQ-API-006/007) por compatibilidad; solo el
   frontend deja de consumirlos.

## Business Problem
- **Componente inoperativo/duplicado**: el "Buscador a granel" replica una
  capacidad de consulta que el buscador principal ya cubre con mejor
  ergonomía; su presencia añade una pestaña y 4 campos de rango que generan
  fricción sin valor operativo.
- **Código muerto**: estado, handlers y funciones de filtrado exclusivos de
  la modalidad a granel se mantienen vivos solo para renderizar una vista
  que se va a retirar.

## Proposed Changes
1. **`frontend/src/components/BulkSearch.tsx`**: eliminado (archivo completo).
2. **`frontend/src/pages/SeccionGeneral.tsx`**: eliminar import, estado
   `tab`, barra de pestañas y render condicional; `InventoryTable` +
   paginación se renderizan directamente; comentario de invalidación
   actualizado (sin referencia al Buscador a granel).
3. **`frontend/src/services/catalog.ts`**: eliminar de `CatalogFilters` los
   campos `desde_numero_lista`, `hasta_numero_lista`, `desde_descripcion`,
   `hasta_descripcion` y su doc-block REQ-API-006. Los campos
   `@deprecated` legacy se conservan (compat backend, fuera de alcance).
4. **`frontend/src/types.ts`**: conservar `MaterialList.start_index`
   (respuesta real del contrato); solo actualizar el comentario que decía
   que el frontend numera filas continuas.
5. **Tests**: nuevo `SeccionGeneral.test.tsx` (vitest) que verifica que la
   pestaña/sección "Buscador a granel" ya no se renderiza y que el buscador
   principal sigue operativo.

## Impact Assessment
- **Frontend**: `components/BulkSearch.tsx` (borrado),
  `pages/SeccionGeneral.tsx`, `services/catalog.ts`, `types.ts` (comentario),
  nuevo `components/__tests__/SeccionGeneral.test.tsx`.
- **Backend**: ninguno.
- **Contrato OpenSpec**: ninguno (`openspec.yaml` no documenta rangos de
  `GET /catalogo`).

## Out of Scope
- `GET /api/v1/catalogo` y sus parámetros de rango en el backend
  (REQ-API-006/007 conservados por compatibilidad).
- Campos `@deprecated` legacy de `CatalogFilters`.
- Cualquier otra vista (Fibra Óptica, Equipos, Transferencias, Reportes).
- Constitution §5.2/5.3 (bulk ingestion): no aplica — el buscador a granel
  era consulta, no ingesta por lotes.
