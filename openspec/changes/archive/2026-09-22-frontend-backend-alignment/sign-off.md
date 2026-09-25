# Arquitectura Sign-Off — Cierre de Backend (Fase 5)
**Change:** `2026-09-22-frontend-backend-alignment`
**Agents:** @arq-reviewer (veredicto: APPROVED WITH CONDITIONS) · @auditor (dictamen: CONFORME CON OBSERVACIONES)
**Fecha:** 2026-09-25
**Branch origen:** `feat/backend-logistics-fixes`

## 1. Declaración formal de aprobación

El paquete `2026-09-22-frontend-backend-alignment` (Udoc2) queda formalmente **aprobado en su alcance de backend** por la gobernanza (@arq-reviewer / @auditor). Se verificó contra el código en `feat/backend-logistics-fixes`: los 22 requisitos EARS v1.1 poseen implementación y artefacto de verificación (matriz de trazabilidad 22/22, cotejada 43/43 contra la colección real de 129 tests), la suite pasa 129/129, `mypy` reporta 0 errores en `app` y `tests`, y `openspec validate --strict` es válido.

Las invariantes constitucionales quedan probadamente intactas: el stock solo muta mediante stored functions PostgreSQL (`fn_ajustar_stock_almacen`, `fn_ajustar_stock_fibra`, `fn_ajustar_stock_general`, `fn_procesar_movimiento`) con `motivo` obligatorio, CHECK no-negativos a nivel de base, `FOR UPDATE` para serialización y ledger de auditoría append-only; no existe ninguna escritura ORM directa de inventario en `backend/app/`.

## 2. Levantamiento del bloqueo Backend-First

Se declara cumplida la regla Backend-First (SDD v7.1): las Fases 1–5 del backend están completas y aprobadas. En consecuencia, **queda formalmente levantado el bloqueo del frontend** (Tasks F.1–F.7). El frontend deberá consumir exclusivamente los contratos aprobados y no podrá redefinir comportamiento backend:

* `GET /api/v1/catalogo` con `desde_numero_lista`/`hasta_numero_lista`/`desde_descripcion`/`hasta_descripcion` y `start_index`
* `PATCH /api/v1/catalogo/{id_lista}` con `stock_actual` + `motivo` (alcance Inventario General)
* `GET /api/v1/equipos/{id}/inventario` (inventario autónomo, clave `material_id`, cero fantasmas)
* `GET /api/v1/fibra/{modulo}`, `POST /api/v1/fibra/carga-inicial`, `POST /api/v1/fibra/ajuste`
* `GET /api/v1/auditoria` con `descripcion`/`codigo`/`categoria`/`estado_activo` (ledger inmutable)

## 3. Interpretación ratificada del modelo de autorización (condición C2)

La gobernanza ratifica como postura aceptada el modelo implementado: **identidad autenticada con al menos un alcance asignado (`assert_authenticated`) + rol administrador permisivo con acceso transversal (`administradores`, pase directo en `assert_authenticated`/`assert_scope`), con la rigidez de integridad delegada íntegramente a PostgreSQL** (CHECK no-negativos, `motivo` obligatorio, ledger append-only, `FOR UPDATE`). Esto satisface Constitution 3.1 (default-deny para actores sin identidad/alcance) y la directriz operativa ratificada en Fase 2, aun cuando la granularidad por recurso de 3.2 (`assert_scope` por sección) no se invoque por ruta en esta iteración. El endurecimiento de 3.2 por recurso y el MFA de elevación (3.3) quedan registrados como paquete OpenSpec de seguimiento.

## 4. Checklist de cierre (DoD §10)

* [x] Udoc2 backend implementado (15/15 REQ backend; 7 REQ-UI mapeados a Tasks F.1–F.7, desbloqueados por este documento)
* [x] constitution-impact.md satisfecho (§2.1–2.6 verificadas en código)
* [x] tasks.md completado (backend, Tasks 2.1–3.10; checkboxes marcados)
* [x] Matriz de trazabilidad completa (22/22 REQ, Constitution 7.1)
* [x] pytest 129/129 passed
* [x] mypy 0 errores (app y tests)
* [x] Sin regresiones TEAMS/DEVOL (REQ-API-009)
* [x] `openspec validate --strict` válido
* [x] Arquitectura Sign-Off aprobado
* [x] Paquete archivado en `openspec/changes/archive/`
* [x] Integración git completada (merge `feat/backend-logistics-fixes` → `main`)

## 5. Backlog heredado (condición C3 — paquetes OpenSpec de seguimiento)

Ninguno viola invariantes; ninguno bloquea este cierre:

1. **`HistorialImportacion` huérfano:** modelo ORM sin endpoint de ingesta que lo escriba. Decidir: implementar ingesta masiva (Constitution 5.2/5.3) o deprecar la tabla.
2. **Rutas legacy del buscador:** params `desde_id_lista`/`hasta_id_lista`/`desde_sku`/`hasta_sku` y rama `id_lista.cast(String).ilike` en `buscar` — deprecar vía paquete propio una vez el frontend migre a REQ-API-006/007.
3. **CHECK legacy `secciones.tipo` (`FO_PAQUETE`/`FO_EN_USO`):** conservado por historia; limpiar cuando se deprecen las secciones FO soft-inactivas.
4. **Granularidad de autorización 3.2 + MFA 3.3:** endurecimiento por recurso y elevación MFA si la operación lo exige.
5. **Ops:** provisionar `P2_MFA_ENCRYPTION_KEY` en despliegue (hoy el fallback genera clave efímera por proceso).

## 6. Resoluciones clave del pipeline

* **DEFECT-1 cerrado:** `catalogo.listar` aplica `LIMIT = Y` con `desde` implícito = 1 (REQ-API-006); test `test_solo_hasta_numero_lista_limita` verde.
* **Migración de presentación sparse → contrato autónomo** conforme a la Nota de Ejecución de Task 3.10 (sin filas fantasma, clave `material_id`).
* **Migraciones 0012/0013:** aislamiento de inventarios (Equipos/FO), RBAC admin, trazabilidad `ultimo_movimiento_id` y auditoría de cambios SKU (Constitution 6.2), con reversibilidad 0013↔0012↔0011 verificada.
* **Refactor Fase 3.5:** `sparse_inventory.py` → `inventario.py` (git mv), baja de `models/vistas.py` y de `fiber_variants`/`team_inventory` (auditadas).
