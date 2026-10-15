# Spec: Inventario FO unificado, Valor Unitario y Valor Total

**Change ID:** `2026-10-fo-unificado-valor-unitario`
**Identificadores:** `RF-1`..`RF-10` (primarios, usados en `tasks.md` y en `test_RF_<n>_...`) con alias constitucional `[REQ-<DOMINIO>-<NNN>]` (Constitución §1.5).
**Alcance de esta especificación:** *qué* debe hacer el sistema (Constitución §1.2). El *cómo* (tipos SQL, DDL, rutas) vive en `plan.md`.
**Terminología oficial (`.agents.md` §3):** `Inventario FO`, `Unidad`, `TRANSF`, `Confirmar Devolución`. Los términos `FO Paquete`/`FO En Uso`/`Paquete`/`En Uso` quedan deprecados en toda superficie visible.

Convención de precisión (usada por varios RF): una **cantidad decimal** es un número no negativo con **hasta 3 decimales** y **hasta 12 dígitos en total** (9 enteros + 3 decimales; máximo `999 999 999.999`). Los identificadores (`id_lista`, `material_id`, `almacen_id`, `equipo_id`, `movimiento_id`, ...) son enteros sin decimales.

---

## 1. Historias de Usuario

- **HU-1.** Como operador de logística quiero ver y operar todo el material de fibra óptica en un único **Inventario FO**, para no tener que decidir entre "Paquete" y "En Uso" antes de cada operación.
- **HU-2.** Como administrador quiero asignar a cada material un **Valor Unitario** en MXN con decimales, para conocer el valor económico de mi inventario.
- **HU-3.** Como responsable del almacén quiero ver el **Valor Total** del inventario (General + Inventario FO) junto a los demás indicadores, para valuar la existencia de un vistazo.
- **HU-4.** Como operador quiero registrar existencias y movimientos con fracciones (p. ej. 2.5), para reflejar materiales que no se cuentan por piezas enteras.
- **HU-5.** Como auditor quiero que todo cambio de valor unitario y toda fusión de inventario FO quede en el ledger de auditoría, y que los movimientos históricos sigan siendo consultables y cancelables.

---

## 2. Requisitos Funcionales

### Requirement: RF-1 [REQ-FO-001] Inventario FO unificado

- **(Ubiquitous)** El sistema **deberá** mantener una única existencia de fibra óptica por material (una sola locación general **Inventario FO**), sin subapartados, módulos ni secciones intermedias, en la interfaz, en la API y en la base de datos.
- **(Event-driven)** **Cuando** se aplique la migración de unificación, el sistema **deberá** sumar en una única existencia las cantidades de un mismo material que estuvieran registradas en los antiguos inventarios Paquete y En Uso, sin pérdida ni creación de cantidad, y **deberá** registrar un evento de auditoría por cada material fusionado con las cantidades anteriores y la resultante.
- **(Unwanted behavior)** **Si** un cliente envía un identificador de módulo (`modulo`, `origen_modulo`, `destino_modulo`) en una operación de Inventario FO, **entonces** el sistema **deberá** rechazar la solicitud con HTTP 422 sin efectos secundarios.

#### Scenario: Una sola existencia por material tras la migración
- **WHEN** un material tenía 10 en Paquete y 5 en En Uso antes de la migración
- **THEN** el Inventario FO muestra una única fila de ese material con 15 y existe un evento de auditoría con 10, 5 y 15

#### Scenario: Sin subapartados en la interfaz
- **WHEN** el operador abre el Inventario FO
- **THEN** la navegación no ofrece "Paquete" ni "En Uso" y se muestra una sola tabla de materiales FO

#### Scenario: Módulo rechazado
- **WHEN** se envía `{"modulo": "PAQUETE"}` a una operación de Inventario FO
- **THEN** la respuesta es 422 y no cambia ninguna existencia

### Requirement: RF-2 [REQ-VALOR-001] Atributo Valor Unitario

- **(Ubiquitous)** El sistema **deberá** asociar a cada material un **Valor Unitario** expresado en MXN como cantidad decimal no negativa (hasta 3 decimales, máximo `999 999 999.999`), compartido por el Inventario General, el Inventario FO y el Inventario por Unidad.
- **(Unwanted behavior)** **Si** se intenta asignar un Valor Unitario negativo, con más de 3 decimales o que exceda el máximo, **entonces** el sistema **deberá** rechazar la operación sin modificar el material y devolver un error de validación (HTTP 422) que identifique el campo.

#### Scenario: Valor con decimales
- **WHEN** se asigna `12.345` a un material
- **THEN** el valor persistido y devuelto por la API es exactamente `12.345`

#### Scenario: Valor fuera de rango
- **WHEN** se asigna `-1`, `1.2345` o `1000000000`
- **THEN** la respuesta es 422 y el Valor Unitario previo no cambia

### Requirement: RF-3 [REQ-VALOR-002] Valor inicial, visualización y edición

- **(Ubiquitous)** El sistema **deberá** asignar `1.000` MXN como Valor Unitario inicial a todo el catálogo existente y a todo material nuevo que no declare otro valor.
- **(Ubiquitous)** El sistema **deberá** mostrar la columna **VALOR UNITARIO** en las tablas del Inventario General, del Inventario FO y del Inventario por Unidad, con la cifra a la izquierda y la etiqueta `MXN` a su derecha (p. ej. `1.00 MXN`; hasta 3 decimales, mínimo 2).
- **(Event-driven)** **Cuando** un administrador abra la opción de modificar un material (Inventario General o Inventario FO), el sistema **deberá** presentar el campo Valor Unitario precargado con el valor actual y **deberá** permitir guardarlo con decimales.
- **(Option-driven)** **Donde** la opción de modificar se ejecute en el Inventario por Unidad, el sistema **deberá** mostrar el Valor Unitario en modo solo lectura (el valor pertenece al catálogo).

#### Scenario: Valor por defecto
- **WHEN** se aplica la migración sobre un catálogo existente
- **THEN** todos los materiales tienen Valor Unitario `1.000`

#### Scenario: Edición con decimales
- **WHEN** el administrador guarda `2.5` en Modificar Material
- **THEN** las tres tablas muestran `2.50 MXN` para ese material tras refrescar

### Requirement: RF-4 [REQ-VALOR-003] Cálculo transaccional del Valor Total

- **(Ubiquitous)** El sistema **deberá** calcular el **Valor Total** como la suma, sobre todos los materiales activos con existencia en secciones activas del Inventario General y en el Inventario FO, del producto `Stock Actual × Valor Unitario`, calculado por PostgreSQL con aritmética exacta y redondeado a 3 decimales (mitad hacia arriba) únicamente al final.
- **(Ubiquitous)** El sistema **deberá** exponerlo en `GET /api/v1/inventario/resumen-general` junto con la moneda `MXN`.
- **(Event-driven)** **Cuando** cambie cualquier existencia (carga, ajuste, +Cantidad, Mover, TRANSF, devolución, cancelación, eliminación) o cualquier Valor Unitario, el siguiente cálculo **deberá** reflejar el estado persistido (sin caché ni cálculo en el cliente).
- **(Unwanted behavior)** **Si** no existen existencias, **entonces** el Valor Total **deberá** ser `0` (nunca nulo ni error).

La fórmula es:

$$\text{Valor Total} = \sum_{i} (\text{Stock Actual}_i \times \text{Valor Unitario}_i)$$

#### Scenario: Consolidación General + FO
- **WHEN** el material A (General) tiene stock 4 y valor 2.5, y el material B (FO) tiene stock 10 y valor 1.25
- **THEN** el Valor Total es `22.500`

#### Scenario: Inventario vacío
- **WHEN** no existe ninguna fila de inventario
- **THEN** el Valor Total es `0`

#### Scenario: Material inactivo
- **WHEN** un material con stock pasa a inactivo
- **THEN** su valor deja de contar en el Valor Total

### Requirement: RF-5 [REQ-VALOR-004] Posición del indicador Valor Total

- **(Ubiquitous)** La sección general **deberá** mostrar el indicador **Valor Total** inmediatamente después de **Total Materiales** y antes de **Stock Total**, resultando el orden: `Total Materiales`, `Valor Total`, `Stock Total`, `Alertas Stock`, `Transferencias Hoy`.
- **(Ubiquitous)** El indicador **deberá** mostrar la cifra con la etiqueta `MXN` a su derecha, usando el valor devuelto por la API sin recalcularlo en el cliente.
- **(Event-driven)** **Cuando** una mutación (ajuste, edición de Valor Unitario, movimiento, etc.) concluya con éxito, el indicador **deberá** refrescarse con el valor persistido.
- **(State-driven)** **Mientras** la consulta esté cargando o haya fallado, el indicador **deberá** mostrar un estado de carga o de error explícito y nunca un valor inventado.

#### Scenario: Orden de tarjetas
- **WHEN** se renderiza la sección general
- **THEN** las tarjetas aparecen en el orden indicado y `Valor Total` es la segunda

#### Scenario: Refresco tras editar el valor
- **WHEN** el administrador cambia un Valor Unitario con éxito
- **THEN** el indicador muestra el nuevo Valor Total proveniente de la API

### Requirement: RF-6 [REQ-DEC-001] Existencias y cantidades decimales

- **(Ubiquitous)** El sistema **deberá** representar como cantidad decimal: la existencia de los inventarios General, FO y por Unidad; la cantidad de cada línea de movimiento (TRANSF y devolución); las cantidades tomadas y consumidas de los seguimientos; el parámetro de cantidad/stock de toda operación transaccional (carga inicial, ajuste, +Cantidad, Mover, TRANSF, cancelación, cierre de seguimiento); y la cantidad registrada en el ledger de auditoría.
- **(Ubiquitous)** El sistema **deberá** conservar el invariante de saldo no negativo y la regla de cantidad de movimiento mayor que cero con valores decimales.
- **(Event-driven)** **Cuando** se cancele un movimiento confirmado con cantidades decimales, el sistema **deberá** revertir exactamente las cantidades originales.
- **(Unwanted behavior)** **Si** una cantidad tiene más de 3 decimales, es negativa donde no se permite, o excede el máximo, **entonces** el sistema **deberá** rechazarla (HTTP 400/422) sin redondeo silencioso y sin alterar existencias.
- **(Ubiquitous)** Los identificadores **deberán** permanecer enteros sin decimales; el `stock_minimo` permanece entero.

#### Scenario: Ajuste fraccionario
- **WHEN** se ajusta el stock de un material a `7.250`
- **THEN** la API y la base de datos devuelven `7.250` y el evento de auditoría registra el diferencial decimal

#### Scenario: Transferencia fraccionaria y cancelación
- **WHEN** se transfiere `2.5` a una Unidad y luego se cancela el movimiento
- **THEN** el origen vuelve exactamente a su cantidad original y la Unidad a la suya

#### Scenario: Sobre-precisión
- **WHEN** se envía una cantidad `1.0005`
- **THEN** la respuesta es 422 y ninguna existencia cambia

#### Scenario: Concurrencia con decimales
- **WHEN** dos TRANSF simultáneas intentan consumir `8` y `7` de un stock de `10`
- **THEN** una concluye, la otra se rechaza (400/422) y el stock nunca es negativo

### Requirement: RF-7 [REQ-VALOR-005] Auditoría de Valor Unitario y de la unificación

- **(Event-driven)** **Cuando** cambie el Valor Unitario de un material, el sistema **deberá** emitir un evento de auditoría inmutable con actor, marca de tiempo, material y valores anterior y nuevo del Valor Unitario.
- **(Ubiquitous)** El sistema **deberá** conservar íntegros (sin actualizar ni borrar) todos los eventos históricos del ledger, incluidos los que contienen `modulo`.
- **(Unwanted behavior)** **Si** una edición no modifica el Valor Unitario, **entonces** el sistema **no deberá** emitir evento de valor.

#### Scenario: Evento de cambio de valor
- **WHEN** el Valor Unitario pasa de `1.000` a `2.500`
- **THEN** existe un evento con valor anterior `1.000` y nuevo `2.500`, actor y fecha

#### Scenario: Ledger intacto
- **WHEN** se aplica la migración
- **THEN** el número y contenido de los eventos previos coinciden con los de antes de migrar

### Requirement: RF-8 [REQ-VALOR-006] Contrato API y seguridad

- **(Ubiquitous)** Todas las entradas de la API que reciban Valor Unitario, existencias o cantidades **deberán** validarse con esquemas estrictos de tipo decimal (límites de RF-2/RF-6) y **deberán** rechazar propiedades no declaradas (HTTP 422).
- **(Ubiquitous)** Las respuestas **deberán** representar Valor Unitario, existencias, cantidades y Valor Total como números JSON, sin pérdida de precisión.
- **(Event-driven)** **Cuando** una solicitud incluya `valor_unitario`, el sistema **deberá** exigir rol administrador (HTTP 403 en caso contrario) sin afectar el resto de campos editables por actores autenticados.
- **(Unwanted behavior)** **Si** una regla de negocio de PostgreSQL rechaza una operación, **entonces** la API **deberá** responder 400 o 422 con el error canónico, nunca 500 ni excepciones SQL nativas.
- **(Ubiquitous)** `GET /api/v1/inventario/resumen-general` **deberá** exigir un actor autenticado (default-deny).

#### Scenario: Propiedad extra
- **WHEN** se envía un campo no declarado al `PATCH` de un material
- **THEN** la respuesta es 422

#### Scenario: Actor sin privilegios
- **WHEN** un actor no administrador envía `valor_unitario`
- **THEN** la respuesta es 403 y el valor no cambia

#### Scenario: Representación numérica
- **WHEN** se consulta un material con valor `12.345`
- **THEN** el JSON contiene el número `12.345` (no la cadena `"12.345"`)

### Requirement: RF-9 [REQ-FO-002] Compatibilidad con movimientos históricos

- **(Ubiquitous)** El sistema **deberá** conservar consultables, con sus datos originales, los movimientos y eventos previos que referencian los antiguos orígenes/destinos FO Paquete y FO En Uso.
- **(Event-driven)** **Cuando** se cancele un movimiento confirmado cuyo origen o destino fuese el antiguo Paquete o En Uso, el sistema **deberá** revertirlo contra el Inventario FO unificado, restaurando exactamente las cantidades originales.
- **(Ubiquitous)** Todo movimiento nuevo que involucre fibra óptica **deberá** referenciar el Inventario FO unificado; los antiguos orígenes **no deberán** ofrecerse como opciones seleccionables.
- **(Ubiquitous)** Las etiquetas visibles de movimientos históricos con origen/destino FO antiguo **deberán** mostrarse como "Inventario FO".

#### Scenario: Cancelación de un movimiento legacy
- **WHEN** se cancela un TRANSF confirmado antes de la migración cuyo origen era FO En Uso (cantidad 3)
- **THEN** el Inventario FO del material aumenta exactamente 3 y el movimiento queda cancelado

#### Scenario: Orígenes antiguos no seleccionables
- **WHEN** el operador abre el selector de origen/destino de TRANSF
- **THEN** solo aparece "Inventario FO" y no "Paquete"/"En Uso"

### Requirement: RF-10 [REQ-FO-003] Nomenclatura oficial Inventario FO

- **(Ubiquitous)** La interfaz **deberá** denominar **Inventario FO** a la locación única de fibra óptica en navegación lateral, título de página, selectores de TRANSF/Mover/+Cantidad, reportes, auditoría y mensajes.
- **(Unwanted behavior)** **Si** un texto visible contiene "Paquete", "En Uso", "FO Paquete" o "FO En Uso" como nombre de inventario, **entonces** una prueba de barrido **deberá** fallar (valores técnicos históricos y comentarios exentos).
- **(Ubiquitous)** La navegación **deberá** presentar una única entrada de Fibra Óptica sin subentradas.

#### Scenario: Barrido de nomenclatura
- **WHEN** corre la prueba de barrido sobre los textos visibles
- **THEN** no hay coincidencias fuera de las excepciones declaradas

---

## 3. Casos Límite (Edge Cases) y Clarificaciones

### 3.1 Casos límite

| # | Caso | Comportamiento exigido |
| :-- | :-- | :-- |
| E1 | Ajustar stock a `0` | Permitido; la fila se conserva con `0`; aporta `0` al Valor Total; se audita. |
| E2 | Valor Unitario `0` | Permitido (`>= 0`); aporta `0`. |
| E3 | Valor con más de 3 decimales (`1.2345`) | 422; sin redondeo silencioso. |
| E4 | Desbordamiento (`> 999 999 999.999`) | 422 en API; la BD también lo rechaza (defensa en profundidad). |
| E5 | Decimales largos expresados en notación científica (`1e-4`) | Rechazado por sobre-precisión. |
| E6 | Material FO con filas en Paquete y En Uso | Se suman; evento de fusión por material (RF-1). |
| E7 | Material FO solo en una de las dos particiones | Se conserva la cantidad; fila única. |
| E8 | Movimiento histórico en curso (BORRADOR) con origen FO antiguo | Debe poder confirmarse o cancelarse contra el Inventario FO. |
| E9 | Suma de productos que excede 12 dígitos | El Valor Total no se trunca ni falla (aritmética `NUMERIC` exacta); solo se redondea al final. |
| E10 | Dos ediciones concurrentes del mismo Valor Unitario | Última escritura válida prevalece; ambas generan evento si hay cambio. |
| E11 | Cantidad decimal en U.M. de piezas (`PZ`) | Permitida (sin regla por U.M.; ver C-5). |
| E12 | Eliminación física de un material FO con stock | Conserva las reglas vigentes (motivo y auditoría), sin `modulo`. |
| E13 | Migración repetida / reintento | Idempotente a nivel de Alembic (revisión única); sin duplicar eventos. |
| E14 | `downgrade()` con stock fraccional | Aborta con error explícito (sin pérdida silenciosa). |
| E15 | `valor_unitario: null` explícito en PATCH | No-op: sin escritura, sin evento de auditoría y sin error 500 (la columna es `NOT NULL`; el null explícito no es un valor válido y se ignora). |

### 3.2 Clarificaciones Fase 4 (decisiones por defecto; sujetas a ratificación de `@arq-reviewer`)

| ID | Ambigüedad del insumo | Decisión adoptada |
| :-- | :-- | :-- |
| C-1 | El Valor Total es consolidado, pero las otras tarjetas hoy dependen de la sección seleccionada. | El Valor Total es **global** (General + FO) y **no reacciona** al filtro de sección; las demás tarjetas no cambian. |
| C-2 | "Todos los inventarios" incluye Unidades; "modificar" no se define en Unidades. | La columna aparece en Unidades como solo lectura; se edita únicamente desde el catálogo (General/FO). |
| C-3 | El insumo solo habla de modificar; no del alta de material. | El alta **no** recibe Valor Unitario: nace en `1.000` y se modifica después. |
| C-4 | Quién puede cambiar el valor. | Solo administrador (RF-8); a ratificar por `@sec-ops`. |
| C-5 | Los decimales aplican a "variables de inventario y movimiento" sin distinguir U.M. | Sin restricción por U.M.; cualquier cantidad admite hasta 3 decimales. |
| C-6 | Las Unidades no entran en el Valor Total. | Transferir a una Unidad reduce el Valor Total (el material sale de General/FO); es coherente con el insumo y se documenta. |
| C-7 | Formato de redondeo/visualización. | Cálculo exacto y redondeo a 3 decimales al final; visualización con mínimo 2 y máximo 3 decimales, locale `es-MX`. |

---

## 4. Fuera de Alcance (Out of Scope)

- Multimoneda (USD/EUR), tipo de cambio o conversión.
- Histórico de variaciones de precio, valuación a una fecha pasada o costeo (PEPS/promedio); el Valor Total refleja el estado actual.
- Valuación del Inventario por Unidad dentro del Valor Total.
- `stock_minimo` y `stock_minimo_local` decimales.
- Restricciones de cantidad según U.M. (p. ej. solo enteros para `PZ`).
- Importación masiva de Valor Unitario (CSV/XLSX).
- Nuevos reportes de valuación o exportaciones financieras.
- Renombrar enumeraciones técnicas heredadas del ledger (`FO_PAQUETE`, `FO_EN_USO`, `TEAMS`, `DEVOL`).
- Otros indicadores o filtros del dashboard distintos de `Valor Total`.

---

## 5. Criterios de Finalización (Definition of Done)

1. `RF-1`..`RF-10` cuentan con prueba automatizada (`test_RF_<n>_...`) que asevera respuesta HTTP **y** estado de base de datos (o, en frontend, el comportamiento visible) y pasan al 100 %; la Matriz de Trazabilidad cubre el 100 % (`@tester`, `@qa-agent`).
2. Migración Alembic `0027` aplica y revierte limpiamente sobre `p2_test`; una carga previa de datos conserva sus totales (cero pérdida).
3. Contrato backend congelado y registrado por `@qa-agent` antes de iniciar el frontend; visto bueno de `@arq-reviewer` y `@sec-ops`.
4. Constitución intacta: saldo no negativo, ledger inmutable (conteo y contenido de eventos previos sin cambios), atomicidad, default-deny y `extra="forbid"`.
5. Cero deriva (Zero-Drift): `spec.md` = `plan.md` = `tasks.md` = pruebas = OpenAPI = interfaces TypeScript; sin aritmética de stock ni de valor en Python/React.
6. Nomenclatura oficial (`Inventario FO`, `Unidad`, `TRANSF`, `Confirmar Devolución`) sin desviaciones visibles.
7. Compuertas §7.2: pytest 100 %, `mypy`, `tsc -b` sin errores ni advertencias, eslint, `vite build` y `openspec validate --specs --strict` con 0 violaciones.
8. Drift Report de `@auditor` en estado APPROVED; paquete listo para archivarse en `openspec/changes/archive/` y promover sus requisitos a `openspec/specs/`.
