# OpenSpec Change Proposal

## Change ID
`2026-09-29-fo-delete-fix`

## Summary
Corregir el error 500 (Internal Server Error) que rechaza la eliminación de
materiales exclusivamente en las secciones de Fibra Óptica — módulos
`PAQUETE` y `EN_USO` — según `docs/fo_report_1.md`, sin tocar el frontend:

1. Auditar el endpoint `DELETE /fibra/{modulo}/materiales/{material_id}` de
   FastAPI (`backend/app/api/v1/fibra.py`) y la stored function
   `fn_eliminar_inventario_fibra`, verificando la resolución del path
   parameter (ID del material) y del query parameter (`motivo`).
2. Capturar en el backend el rechazo de PostgreSQL por integridad
   referencial (`IntegrityError`, SQLSTATE 23503 — el material posee
   historial de movimientos/transferencias) y retornar un **HTTP 409
   controlado** con mensaje claro ("No se puede eliminar porque existen
   movimientos o transferencias asociadas"), en lugar de colapsar con un
   HTTP 500.
3. Preservar intacto el ecosistema FO: lógica transaccional TEAMS/DEVOL,
   estructura del catálogo general y los endpoints de Ver Detalle y
   Modificar implementados recientemente (paquete archivado
   `2026-09-29-fo-crud-management`).

## Business Problem
- **Eliminación FO rota:** el operador recibe la alerta genérica "Ocurrió
  un error" al eliminar un material desde Fibra Óptica; la petición
  `DELETE /api/v1/fibra/{PAQUETE|EN_USO}/materiales/{id}?motivo=...`
  retorna **HTTP 500** en ambos módulos (fo_report_1.md §2).
- **Frontend validado (cero defectos):** el formulario recopila el motivo
  obligatorio, construye la URL y emite la petición correctamente
  (`frontend/src/services/fibra.ts:81-89`, `pages/FibraOptica.tsx`); el
  fallo reside 100 % en cómo el backend procesa la ruta.
- **Excepción de integridad sin mapeo de dominio:** cuando PostgreSQL
  rechaza la eliminación porque el material tiene historial de
  movimientos, el `IntegrityError` no se traduce a un error de negocio
  controlado y escapa como 500 (vector statement-time sin mapeo específico
  y vector commit-time de `session.begin()` sin captura en el endpoint).

## Proposed Changes
1. **Backend `app/services/transaccional.py`:** mapeo específico del flujo
   DELETE FO para SQLSTATE 23503 (violación de Foreign Key) → `BusinessRuleError`
   con mensaje de dominio claro y `status_code=409`, incluyendo coordenadas
   `{modulo, material_id}`. El mapeo genérico SEC-012 permanece para el resto
   de los flujos.
2. **Backend `app/api/v1/fibra.py`:** capturar `sqlalchemy.exc.IntegrityError`
   alrededor del bloque `async with session.begin()` en
   `eliminar_material_fibra` (vector commit-time) → mismo `BusinessRuleError`
   409 con el mensaje de dominio. Cualquier otro error de base de datos del
   flujo DELETE FO jamás se propaga como 500.
3. **Verificación de parámetros:** confirmar (y fijar con tests de regresión)
   que la firma del endpoint desempaqueta correctamente el path parameter
   `material_id: int` y el query parameter `motivo: str | None`.

## Impact Assessment
- **Backend:** `app/services/transaccional.py`, `app/api/v1/fibra.py`.
- **Tests:** `tests/test_fibra.py` (nuevos casos de rechazo por integridad →
  409 con mensaje; happy path 204 intacto; resolución de params).
- **Sin cambios en:** frontend React, `fn_procesar_movimiento` /
  `fn_cancelar_movimiento` (TEAMS/DEVOL), catálogo general, PATCH
  (Modificar) y GET (Ver Detalle) de fibra, ni en `ddl.sql`.

## Out of Scope
- Cualquier modificación a componentes o servicios del frontend (la petición
  DELETE y sus parámetros se construyen y envían correctamente).
- Cambios en la lógica transaccional TEAMS/DEVOL del backend.
- Alteraciones del catálogo general, de Ver Detalle o de Modificar.
- Migraciones de esquema (no se requiere DDL nuevo).
