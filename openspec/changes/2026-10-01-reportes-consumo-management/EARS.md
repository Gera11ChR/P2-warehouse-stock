# EARS: Reportes de Consumo & Management

Requisitos del cambio `2026-10-01-reportes-consumo-management` expresados en notación EARS
(Ubiquitous / State-driven / Event-driven / Unwanted / Optional). Clasificación de severidad:
**CRÍTICO** (constitucional) · **ALTO** · **MEDIO**.

> Convenciones: "usuario autorizado" = administrador/rol con permisos de inventario y reportes.
> "seguimiento" = entidad antes denominada "despliegue" (renombrada a CONSUMO).

## 1. Nomenclatura y flujo CONSUMO

- **REQ-P2-CON-001 (Ubiquitous / CRÍTICO).** El sistema **deberá** referirse al flujo
  anteriormente denominado DESPLIEGUE como **CONSUMO** en toda la interfaz, la API y el esquema
  de datos, mediante renombre físico completo y **sin** referencias legacy visibles en la UI.
- **REQ-P2-CON-002 (Ubiquitous / ALTO).** La interfaz **deberá** renombrar el botón
  "Crear Despliegue" a **"Crear Seguimiento"**, en coherencia con el seguimiento del consumo
  de materiales por el equipo.
- **REQ-P2-CON-003 (State-driven / ALTO).** **Cuando** un usuario autorizado pulse
  **"Agregar todo"** en la interfaz de Inventario por Equipos de un seguimiento de CONSUMO
  en estado ABIERTA, **el sistema deberá** cargar en el detalle del seguimiento la totalidad
  de las líneas del inventario propio e independiente del equipo, incluyendo todas las
  cantidades existentes, de forma atómica vía `fn_agregar_todo_seguimiento`.
- **REQ-P2-CON-004 (Unwanted / ALTO).** El sistema **no deberá** permitir ejecutar
  "Agregar todo" sobre un seguimiento de CONSUMO que no se encuentre en estado ABIERTA.
- **REQ-P2-CON-005 (State-driven / CRÍTICO).** **Cuando** un usuario autorizado confirme el
  cierre de un seguimiento de CONSUMO registrando los materiales sobrantes y sus cantidades,
  **el sistema deberá** cerrar el seguimiento vía `fn_cerrar_seguimiento` y **generar el
  Acta de Consumo** correspondiente.

## 2. Reportes oficiales (XLSX sobre plantillas corporativas)

- **REQ-P2-REP-001 (Unwanted / CRÍTICO).** El backend **no deberá** generar workbooks de Excel
  desde cero ni volver a producir reportes en CSV (formato legacy **descartado**).
- **REQ-P2-REP-002 (Ubiquitous / CRÍTICO).** El backend **deberá** cargar las plantillas
  corporativas `1 ACTA DE REPORTE NORMAL.xlsx` o `2 ACTA DE REPORTE EXTENSO.xlsx` y utilizar
  **OpenPyXL** para **inyectar** los datos del reporte, **conservando** estilos, celdas
  combinadas y la imagen `company_logobrand.png` embebida.
- **REQ-P2-REP-003 (Event-driven / CRÍTICO).** **Cuando** el estado de un movimiento TEAMS en la
  tabla transaccional pase a **COMPLETED** tras confirmar la entrega, **el sistema deberá**
  disparar automáticamente la generación del **Acta de Entrega** (registro persistido;
  archivo XLSX generado bajo demanda).
- **REQ-P2-REP-004 (State-driven / CRÍTICO).** **Cuando** se exporte un Acta de Consumo,
  **el sistema deberá** emitir en la columna `CANT.` la **cantidad consumida**
  (tomada − sobrante, calculada en SQL) y ajustar el título del acta a
  **"ACTA DE CONSUMO"**.
- **REQ-P2-REP-005 (Ubiquitous / ALTO).** La sección **REPORTES deberá** ofrecer dos
  subsecciones —**Entrega** y **Consumo**—, cada una con las opciones **Formato Normal**
  y **Formato Extenso**.
- **REQ-P2-REP-006 (State-driven / ALTO).** **Cuando** el número de ítems del reporte supere
  las filas de datos disponibles de la plantilla (Normal: filas 10–25; Extenso: filas 9–28),
  **el sistema deberá** insertar filas adicionales copiando el estilo de las filas de datos
  y desplazar los bloques de firma, preservando el diseño corporativo.
- **REQ-P2-REP-007 (Ubiquitous / ALTO).** El sistema **deberá** sanitizar los nombres de
  archivo generados y neutralizar la inyección de fórmulas en celdas (prefijar `=`, `+`, `-`,
  `@` al inicio de valores textuales).
- **REQ-P2-REP-008 (Optional / MEDIO).** La exportación **podrá** admitir filtros por equipo
  y rango de fechas, manteniendo el comportamiento de búsqueda actual de la sección REPORTES.

## 3. Operadores rápidos de inventario

- **REQ-P2-INV-001 (State-driven / CRÍTICO).** **Cuando** un usuario autorizado invoque
  **`+Cantidad`** sobre un material del Inventario General o de los módulos de Fibra Óptica
  con una cantidad entera mayor que cero, **el sistema deberá** delegar la operación a
  `fn_sumar_cantidad`, que sumará la cantidad al stock actual e insertará el movimiento
  **inmutable** en `auditoria_eventos` dentro de una única transacción atómica.
- **REQ-P2-INV-002 (Ubiquitous / CRÍTICO — regla constitucional).** FastAPI/Python **no deberá**
  realizar aritmética de stock. Toda actualización de existencias **deberá** ejecutarse en
  PostgreSQL 18 mediante Stored Procedures / PL/pgSQL.
- **REQ-P2-INV-003 (State-driven / CRÍTICO).** **Cuando** un usuario autorizado invoque
  **`Mover`** seleccionando un inventario destino distinto del origen y una cantidad parcial
  (por defecto el stock completo) menor o igual al stock disponible, **el sistema deberá**
  delegar a `fn_mover_material`, que descontará del origen, acreditará en el destino y
  registrará la auditoría inmutable de forma atómica.
- **REQ-P2-INV-004 (Unwanted / CRÍTICO).** El sistema **no deberá** permitir `Mover` con
  destino igual al origen, ni con cantidad menor o igual a cero, ni con cantidad mayor al
  stock del origen. Si la operación falla, **ningún** inventario (origen ni destino) deberá
  quedar modificado.
- **REQ-P2-INV-005 (Ubiquitous / ALTO).** La interfaz **deberá** mostrar las opciones
  **`+Cantidad`** y **`Mover`** junto a "Modificar" y "Eliminar" en el panel de detalle del
  material. **`Mover`** presentará un **select box** con los inventarios de destino válidos
  (Inventario General y módulos FO) y un campo de cantidad.
- **REQ-P2-INV-006 (Ubiquitous / ALTO).** Todo movimiento generado por `+Cantidad` o `Mover`
  **deberá** quedar registrado de forma **inmutable** en `auditoria_eventos` con snapshot
  completo (jsonb), conservando la Garantía de Atomicidad.

## 4. Branding

- **REQ-P2-UI-001 (Ubiquitous / MEDIO).** La interfaz general **deberá** mostrar el logo
  corporativo `company_logobrand.png` en la **esquina superior izquierda**.

## 5. Contrato maestro

- **REQ-P2-CTR-001 (Ubiquitous / CRÍTICO).** El contrato `openspec/openspec.yaml` **deberá**
  actualizarse en este cambio para reflejar:
  - `mandatory_functions` ampliado: `fn_procesar_movimiento`, `fn_cancelar_movimiento`,
    `fn_cargar_stock_inicial`, `fn_ajustar_stock_almacen`, `fn_ajustar_stock_fibra`,
    `fn_eliminar_inventario_fibra`, `fn_crear_seguimiento`, `fn_cerrar_seguimiento`,
    `fn_sumar_cantidad`, `fn_mover_material`, `fn_agregar_todo_seguimiento`.
  - Rutas renombradas de seguimientos (`/equipos/{id}/seguimientos*`) y reportes XLSX
    (`/reportes/entrega`, `/reportes/consumo`, con `formato=normal|extenso`); eliminación
    del enum `csv` en reportes.
  - Endpoints de operadores rápidos con descripción de respuestas 200/400/409/422 coherente
    con los Stored Procedures.
- **REQ-P2-CTR-002 (Ubiquitous / CRÍTICO).** Ninguna implementación **deberá** desviarse del
  contrato certificado (Zero-Drift); `@qa-agent` audita que la implementación y el contrato
  coincidan antes de cada cierre de fase.

## Preguntas abiertas (a resolver en fase de BD por `@dba-guard`)

1. Nombre exacto del estado transaccional de entrega TEAMS: ¿`COMPLETED` o `CONFIRMADO`?
   El contrato maestro actual menciona "CONFIRMADO"; el contexto indica `COMPLETED`.
   La implementación usará el nombre real existente en el esquema.
2. Estructura precisa de las tablas de inventario FO y del detalle del seguimiento para
   el diseño de `fn_mover_material` y `fn_agregar_todo_seguimiento`.
