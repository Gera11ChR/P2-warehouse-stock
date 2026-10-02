# Proposal: Reportes de Consumo & Management

- **ID del cambio:** `2026-10-01-reportes-consumo-management`
- **Rama de trabajo:** `feat/reportes-consumo-management`
- **Estado:** Borrador presentado para aprobación (Spec-Driven Development)
- **Fuente de contexto:** `docs/reportes-implementacion/p2_implementations_context.md` (y sus imágenes `.png`), plantillas corporativas en `backend/app/templates/`, contrato maestro `openspec/openspec.yaml`

## 1. Por qué

1. Los reportes actuales se exportan en **CSV** con un formato legacy que **no es oficial** para la empresa; el administrador requiere formatos corporativos formales.
2. El administrador realiza **aritmética manual** para añadir stock (`+Cantidad`) porque no existe una operación directa de adición sobre el stock existente.
3. **No es posible mover materiales** directamente entre el Inventario General y los inventarios de los módulos de Fibra Óptica; crear un flujo estilo TEAMS/DEVOL para esto es sobredimensionado para la necesidad operativa real.
4. La nomenclatura **DESPLIEGUE** no refleja la operación real (seguimiento del consumo de materiales por equipo) y debe transicionar a **CONSUMO**.
5. Falta branding corporativo: el logo de la empresa debe aparecer en la esquina superior izquierda de la interfaz.

## 2. Qué cambia

### 2.1 Transición de flujo DESPLIEGUE → CONSUMO (renombre físico completo)

- Renombre sistemático en **Frontend y Backend** (sin alias legacy):
  - Funciones SQL: `fn_crear_despliegue` → `fn_crear_seguimiento`; `fn_cerrar_despliegue` → `fn_cerrar_seguimiento`.
  - Endpoints: `/api/v1/equipos/{equipo_id}/despliegues` → `/api/v1/equipos/{equipo_id}/seguimientos` (y sus subrutas).
  - Tablas, columnas y textos de UI: toda referencia a "despliegue" pasa a "seguimiento"/"consumo".
  - En la UI, **"Crear Despliegue"** pasa a **"Crear Seguimiento"**.
- Nuevo botón **"Agregar todo"** en la interfaz de **Inventario por Equipos** del flujo CONSUMO: carga la totalidad del inventario propio e independiente del equipo, con todas sus cantidades existentes, al seguimiento de consumo activo (delegado a `fn_agregar_todo_seguimiento`).

### 2.2 Reportes oficiales basados en plantillas corporativas (XLSX)

- El formato legacy en **CSV se descarta** definitivamente.
- El backend **NO genera Excels desde cero**. Utiliza **OpenPyXL** para **inyectar datos** sobre las plantillas corporativas:
  - `1 ACTA DE REPORTE NORMAL.xlsx` → **Formato Normal** (filas de datos 10–25).
  - `2 ACTA DE REPORTE EXTENSO.xlsx` → **Formato Extenso** (filas de datos 9–28, sección COLABORADORES).
- Se conservan estilos, celdas combinadas e imagen `company_logobrand.png` ya embebida en las plantillas.
- Si los ítems superan las filas disponibles de la plantilla, se **insertan filas copiando el estilo** y se desplazan los bloques de firma.
- La sección **REPORTES** tendrá dos subsecciones —**Entrega** y **Consumo**—, cada una con opción **Formato Normal** y **Formato Extenso**.

### 2.3 Generación de dos hitos (actas)

- **(A) Acta de Entrega:** se dispara automáticamente cuando el estado en la tabla transaccional de un movimiento TEAMS pasa a **COMPLETED** tras confirmar (botón "Confirmar TEAMS"). El registro del acta se persiste; el XLSX se genera bajo demanda.
- **(B) Acta de Consumo:** se genera al **cerrar el seguimiento de CONSUMO** (cierre con registro de sobrantes). `CANT.` = **cantidad consumida** (tomada − sobrante, calculada en SQL). El título del acta se ajusta a **"ACTA DE CONSUMO"** (la plantilla base dice "ACTA DE ENTREGA DE …").

### 2.4 Operadores rápidos de inventario: `+Cantidad` y `Mover`

- **`+Cantidad`:** adición aritmética directa al stock actual del material (Inventario General y módulos FO), **sin pasar por el flujo de transferencia**. Ej.: stock 3 + 50 = 53.
- **`Mover`:** transferencia directa entre Inventario General y módulos FO mediante un **select box de destino**. Soporta **cantidad parcial** (valor por defecto: stock completo). Sin lógica compleja de TEAMS/DEVOL.
- **Garantía de Atomicidad:** los endpoints en FastAPI **DELEGAN** la actualización del stock y la inserción del movimiento **inmutable en `auditoria_eventos`** directamente a **PostgreSQL 18** vía **Stored Procedures / PL/pgSQL**:
  - `fn_sumar_cantidad(...)` para `+Cantidad`.
  - `fn_mover_material(...)` para `Mover`.
- **Regla constitucional:** **cero aritmética de stock en Python**.

### 2.5 Branding

- Inserción del **logo corporativo** (`company_logobrand.png`) en la **esquina superior izquierda** de la interfaz general.

## 3. Impacto

- **Base de Datos:** nuevas migraciones Alembic (renombres, `fn_sumar_cantidad`, `fn_mover_material`, `fn_agregar_todo_seguimiento`, nuevos tipos de evento de auditoría). Verificación del nombre real del estado transaccional (`COMPLETED` vs `CONFIRMADO`) a cargo de `@dba-guard`.
- **Backend:** nuevas dependencias `openpyxl` y `Pillow` (conservación de imágenes en plantillas); servicio de inyección de plantillas; nuevos endpoints de reportes (`/reportes/entrega`, `/reportes/consumo` con `formato=normal|extenso`) y de operadores rápidos; disparo del Acta de Entrega al confirmar TEAMS.
- **Contrato maestro:** `openspec/openspec.yaml` se actualiza:
  - `mandatory_functions` pasa a incluir: `fn_procesar_movimiento`, `fn_cancelar_movimiento`, `fn_cargar_stock_inicial`, `fn_ajustar_stock_almacen`, `fn_ajustar_stock_fibra`, `fn_eliminar_inventario_fibra`, `fn_crear_seguimiento`, `fn_cerrar_seguimiento`, `fn_sumar_cantidad`, `fn_mover_material`, `fn_agregar_todo_seguimiento`.
  - `paths`: renombre de rutas de despliegues; sustitución de `/reportes/despliegues` (enum `csv` eliminado) por rutas de reportes XLSX; nuevos endpoints de operadores rápidos.
- **Frontend (React 19):** renombres de UI, botón "Agregar todo", operadores `+Cantidad` y `Mover` en el panel de detalle del material, subsecciones de Reportes con exportación XLSX (Normal/Extenso), logo corporativo.

## 4. Fuera de alcance

- Flujos robustos tipo TEAMS o DEVOL para mover materiales (la necesidad es un movimiento directo).
- Reimpresión de actas históricas en formatos antiguos.
- Migración/retrocompatibilidad del CSV legacy (se descarta por completo).

## 5. Decisiones de diseño ya resueltas

1. Renombre físico completo en BD/API/UI, sin alias legacy.
2. `Mover` soporta cantidad parcial; por defecto mueve todo el stock.
3. Acta de Consumo: `CANT.` = cantidad consumida; título ajustado.
4. Actas generadas bajo demanda desde datos persistidos; inserción de filas con copia de estilo en caso de desborde.

## 6. Gobernanza multi-agente (SDD)

- `@arq-reviewer` valida el impacto arquitectónico antes de codificar.
- `@dba-guard` diseña y certifica el esquema SQL y los Stored Procedures.
- `@coder` implementa Python/FastAPI; `@sec-ops` audita la seguridad.
- `@tester` (pytest) y `@qa-agent` (auditoría de contrato) aseguran Zero-Drift.
- Fase Frontend: `@ui-agent`, `@ux-agent`, `@form-agent`, `@state-agent`.
- **Ejecución estrictamente secuencial** (sin subagentes en paralelo; sin pruebas concurrentes) para evitar deadlocks en PostgreSQL.
- **Certificación del contrato Backend es gate obligatorio** antes de tocar el Frontend.
- Commits únicamente en `feat/reportes-consumo-management`. **Merge prohibido** (lo hará el administrador).
