# EARS Requirements Specification

## Domain: Resolución de parámetros del DELETE FO
- **REQ-DEL-FIX-001:** WHEN una petición `DELETE /fibra/{modulo}/materiales/{material_id}` llega al endpoint de FastAPI, THE SYSTEM SHALL desempaquetar correctamente el path parameter `material_id` (entero, ID del material) y el query parameter `motivo` (string opcional), enrutándolos a `fn_eliminar_inventario_fibra` con los tipos exactos (INT para el ID, TEXT para módulo y motivo).

## Domain: Manejo controlado de integridad referencial
- **REQ-DEL-FIX-002:** IF PostgreSQL rechaza la eliminación por integridad referencial (el material posee historial de movimientos o transferencias asociadas), THEN THE SYSTEM SHALL capturar la excepción (`IntegrityError`, SQLSTATE 23503) — tanto en la ejecución de la stored function como en el commit de `session.begin()` — y retornar un **HTTP 409** controlado con un mensaje claro ("No se puede eliminar porque existen movimientos o transferencias asociadas"), en lugar de colapsar con un HTTP 500.
- **REQ-DEL-FIX-003:** THE SYSTEM SHALL incluir en el cuerpo del error controlado las coordenadas `{modulo, material_id}` para que el frontend pueda interpretar y mostrar el rechazo.

## Domain: Eliminación exitosa preservada
- **REQ-DEL-FIX-004:** WHEN la eliminación es aceptada por PostgreSQL, THE SYSTEM SHALL mantener el comportamiento actual — HTTP 204, eliminación física SOLO de la fila del módulo indicado de `inventario_fibra`, auditoría `ELIMINACION_FO` con snapshot jsonb completo y aislamiento por módulo (REQ-DEL-001/002/003/004 intactos).

## Domain: Foco estricto en el backend
- **REQ-DEL-FIX-005:** THE SYSTEM SHALL prohibir estrictamente cualquier modificación a los componentes React o servicios del frontend: la petición (DELETE) y sus parámetros (motivo) ya se construyen y envían de forma correcta (`frontend/src/services/fibra.ts`, `frontend/src/pages/FibraOptica.tsx`).

## Domain: Preservación del ecosistema FO
- **REQ-DEL-FIX-006:** THE SYSTEM SHALL preservar intacta la lógica de las transferencias (TEAMS/DEVOL vía `fn_procesar_movimiento` / `fn_cancelar_movimiento`), la estructura del catálogo general y los endpoints de Ver Detalle (`GET /fibra/{modulo}`) y Modificar (`PATCH /fibra/{modulo}/materiales/{material_id}`) implementados en el paquete `2026-09-29-fo-crud-management`.

## Domain: Criterio de aceptación global
- **REQ-DEL-FIX-007:** THE SYSTEM SHALL garantizar que ninguna petición DELETE sobre las rutas de Fibra Óptica retorne HTTP 500: la operación finaliza con un DELETE exitoso (204) o un error controlado (4xx) interpretable por el frontend.
