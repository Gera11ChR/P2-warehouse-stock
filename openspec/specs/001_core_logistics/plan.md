# Plan técnico — Spec 001 (Core Fiber Optic Logistics & Fleet Inventory)

## Estructura de módulos

* `backend/app/models/` → Modelos SQLAlchemy asíncronos para SKUs, almacenes, vehículos y registros de auditoría (RF-1..5)
* `backend/app/schemas/` → Esquemas Pydantic v2 para validación estricta de payloads, lotes e ingesta masiva (RF-6..7)
* `backend/app/api/v1/` → Routers de FastAPI para Autenticación (JWT/MFA/RBAC), Catálogo, Inventario y Asignación de Flota (RF-8..12)
* `backend/app/services/` → Lógica de negocio transaccional con bloqueo a nivel de fila `FOR UPDATE` (RF-13)
* `frontend/src/components/` → Componentes React + TypeScript con data-grids avanzados para pegado desde Excel y validación por lotes (RF-14..15)
* `tests/` → Suite de pruebas con Pytest cubriendo concurrencia atómica, permisos RBAC y validación de esquemas (RF-1..15)

---

## Modelo de datos (PostgreSQL)

```json
{
  "version": 1,
  "tables": {
    "skus": {
      "sku": "VARCHAR(50) PRIMARY KEY",
      "description": "TEXT",
      "unit_of_measure": "VARCHAR(20)",
      "current_stock": "INTEGER",
      "min_stock": "INTEGER",
      "stock_status": "VARCHAR(20)"
    },
    "vehicles": {
      "vehicle_id": "VARCHAR(50) PRIMARY KEY",
      "plate_or_name": "VARCHAR(50)",
      "assigned_crew": "JSON"
    },
    "fleet_allocations": {
      "allocation_id": "SERIAL PRIMARY KEY",
      "vehicle_id": "VARCHAR(50) REFERENCES vehicles(vehicle_id)",
      "sku": "VARCHAR(50) REFERENCES skus(sku)",
      "allocated_quantity": "INTEGER",
      "timestamp": "TIMESTAMP WITH TIME ZONE"
    },
    "audit_logs": {
      "log_id": "SERIAL PRIMARY KEY",
      "action": "VARCHAR(50)",
      "actor": "VARCHAR(100)",
      "details": "JSON",
      "created_at": "TIMESTAMP WITH TIME ZONE"
    }
  }
}

```

* **Restricciones:** Claves foráneas estrictas, campos monetarios y de inventario no negativos, marcas de tiempo automáticas con zona horaria.

---

## Algoritmo de Transacción Atómica y Bloqueo de Stock (RF-13)

1. Iniciar transacción asíncrona en base de datos (`async with session.begin():`).
2. Ejecutar consulta con bloqueo exclusivo: `SELECT * FROM skus WHERE sku = :sku FOR UPDATE`.
3. Validar si `current_stock >= requested_quantity`. Si no es suficiente, lanzar excepción HTTP 400 (Stock Insufficient) provocando `ROLLBACK` automático.
4. Actualizar el stock en la tabla `skus` e insertar el movimiento correspondiente en la tabla append-only `audit_logs`.
5. Confirmar la transacción (`COMMIT`).

---

## Algoritmo de Ingesta Masiva y Validación por Lotes (RF-14)

1. **Captura:** El componente React intercepta el evento de pegado de portapapeles (`paste`) desde Excel en el data-grid.
2. **Normalización:** Se parsean las filas tabulares en una estructura JSON intermedia en el cliente.
3. **Pre-validación por lotes:** Se envía el lote completo al endpoint de FastAPI; Pydantic v2 valida esquemas fila por fila.
4. **Verificación atómica:** Si se detecta un error de formato o SKU inexistente en alguna fila, **todo el lote se rechaza** sin realizar commits parciales, devolviendo un reporte detallado con las filas erróneas para corrección visual en la interfaz.

---

## Decisiones técnicas

* **Backend Asíncrono:** Uso de Python 3.12+ con FastAPI y SQLAlchemy Async para maximizar el rendimiento bajo concurrencia en operaciones de inventario.
* **Seguridad Cero-Trust:** Endpoints protegidos mediante tokens JWT Bearer, verificación obligatoria de MFA (TOTP) para roles administrativos y aislamiento estricto por RBAC.
* **Interfaz de Alta Productividad:** React con TypeScript y Vite, omitiendo formularios lentos de registro unitario en favor de grillas tabulares masivas compatibles con Excel.