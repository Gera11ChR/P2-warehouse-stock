# DMS-TELECOM — CONTEXTO MAESTRO Udoc

## Base funcional para la construcción del Frontend

---

# 1. PROPÓSITO DE ESTE CONTEXTO

Este documento constituye el **contexto funcional consolidado** que debe ser comprendido antes de ejecutar cualquiera de las fases de construcción del Frontend de DMS-TELECOM.

Su objetivo no es sustituir:

- `openspec/openspec.yaml`
- Las especificaciones activas de `openspec/specs/`
- Los cambios aprobados en `openspec/changes/`
- El contrato OpenAPI real expuesto por FastAPI
- El código existente del Backend

Su objetivo es proporcionar al agente una visión coherente de:

1. Qué capacidad funcional ya existe en el Backend.
2. Cómo debe ser consumida por el Frontend.
3. Qué experiencia operativa se desea construir.
4. Cómo deben encajar las operaciones de inventario, equipos, TEAMS, DEVOL, auditoría, catálogo y fibra óptica.
5. Dónde termina la responsabilidad del Frontend y dónde comienza la autoridad del Backend.

---

# 2. JERARQUÍA DE INTERPRETACIÓN

El agente debe interpretar este contexto mediante la siguiente prioridad:

```text
1. OpenSpec / Contrato aprobado
          ↓
2. Backend real + OpenAPI real
          ↓
3. Udoc: Backend establecido + Observaciones Frontend
          ↓
4. Prompt Maestro de Ejecución Frontend
          ↓
5. Implementación visual / UX
```

El Backend existente es la base funcional sobre la cual se construye el Frontend.

Las observaciones del Frontend no deben interpretarse como autorización para crear nuevas reglas de negocio que no existan en el Backend.

Cuando una idea del Frontend contradiga el contrato real del Backend:

```text
NO adaptar artificialmente el Frontend.
NO inventar comportamiento intermedio.
NO crear lógica de negocio local.

→ Detener esa parte.
→ Identificar la incompatibilidad.
→ Escalar al responsable correspondiente.
```

---

# 3. ESTADO FUNCIONAL ACTUAL DEL BACKEND

DMS-TELECOM es un sistema WMS orientado a la logística de materiales de telecomunicaciones.

El flujo funcional establecido es:

```text
CATÁLOGO MAESTRO
        ↓
CARGA INICIAL
        ↓
INVENTARIO GENERAL / ALMACÉN CENTRAL
        ↓
TEAMS
        ↓
INVENTARIO DEL EQUIPO
        ↓
DEVOL
        ↓
INVENTARIO GENERAL
        ↓
AUDITORÍA INMUTABLE
```

El Backend concentra las operaciones transaccionales y el control de concurrencia en PostgreSQL.

La API funciona como capa de transporte y validación mientras PostgreSQL mantiene la autoridad sobre la mutación del inventario.

```text
INTERFAZ OPERATIVA
        ↓
SOLICITUD HTTP
        ↓
FASTAPI
        ↓
POSTGRESQL
        ↓
RESULTADO REAL PERSISTIDO
        ↓
FRONTEND
```

Nunca:

```text
FRONTEND
 ↓
"calcular"
 ↓
"asumir"
 ↓
"persistir localmente"
```

---

# 4. PRINCIPIO FUNDAMENTAL DE INVENTARIO

El Frontend nunca es la autoridad sobre el stock.

La autoridad real pertenece a:

```text
PostgreSQL
└── Stored Functions
    ├── fn_procesar_movimiento()
    ├── fn_cancelar_movimiento()
    ├── fn_ajustar_stock_inicial()
    └── fn_ajustar_stock_almacen()
```

El Backend utiliza control transaccional y bloqueo para garantizar consistencia.

Por lo tanto, el Frontend:

- Consulta.
- Muestra.
- Filtra.
- Prepara operaciones.
- Solicita mutaciones.
- Muestra el resultado.
- Sincroniza nuevamente el estado.

No puede declarar por sí mismo que una operación tuvo éxito.

---

# 5. MODELO DE CATÁLOGO

Existe un catálogo maestro de materiales.

El Frontend debe tratarlo como la fuente funcional para:

- Código / SKU
- Descripción
- Unidad de medida
- Categoría
- Stock mínimo
- Atributos del material
- Identificación del material

La creación de nuevos materiales debe representar un registro real y persistente.

No se debe permitir el estado:

```text
contador de materiales aumenta
        +
registro no aparece en inventario
        +
registro no puede utilizarse posteriormente
```

Cuando un material es creado correctamente:

```text
Crear material
      ↓
Persistencia Backend
      ↓
Respuesta exitosa
      ↓
invalidateQueries(...)
      ↓
Nueva consulta
      ↓
material visible en catálogo/inventario
```

---

# 6. ID LISTA

La identificación visual `ID LISTA` debe seguir el contrato establecido por el Backend.

Regla:

```text
id_lista = inmutable
```

No debe renumerarse al eliminar materiales.

Ejemplo:

```text
1
2
3
...
53
54
55
```

Si se elimina el 54:

```text
1
2
3
...
53
55
```

Nunca:

```text
55 → 54
```

La numeración debe servir para trazabilidad y consistencia.

---

# 7. INVENTARIO GENERAL

El inventario general representa las existencias físicas pertenecientes al almacén.

Debe permitir:

```text
Visualizar
Buscar
Filtrar
Consultar detalle
Modificar mediante operación autorizada
Agregar material
Transferir material
Consultar estado
```

Los filtros pueden utilizar:

- Descripción
- Categoría
- Unidad de medida
- Almacén
- ID LISTA
- SKU
- Rangos compatibles

El Frontend no debe reconstruir el stock mediante cálculos locales.

---

# 8. MODELO SPARSE PARA INVENTARIO POR EQUIPO

El sistema utiliza un catálogo único de materiales.

No debe crearse físicamente una réplica de los materiales para cada equipo.

Modelo conceptual:

```text
CATÁLOGO MAESTRO
      │
      ├── Material 1
      ├── Material 2
      ├── ...
      └── Material N
             │
             ├── Equipo A → sólo registros necesarios
             ├── Equipo B → sólo registros necesarios
             ├── Equipo C → sólo registros necesarios
             └── ...
```

La interfaz puede presentar el catálogo completo para facilitar la operación.

```text
VISUALIZACIÓN
= catálogo completo + existencias resueltas por Backend
```

Nunca:

```text
VISUALIZACIÓN
= catálogo reconstruido artificialmente por React
```

---

# 9. EQUIPOS

Los equipos representan cuadrillas operativas.

El Frontend debe permitir:

```text
Crear equipo
Editar equipo
Eliminar equipo
Consultar equipo
Consultar inventario del equipo
Transferir material al equipo
Devolver material desde el equipo
```

Datos funcionales:

```text
Nombre del equipo
Cantidad de integrantes
Nombres de integrantes
```

---

# 10. TEAMS — ALMACÉN GENERAL → EQUIPO

TEAMS representa la transferencia de materiales desde el inventario general hacia un equipo.

Flujo:

```text
TEAMS
 ↓
Seleccionar equipo destino
 ↓
Abrir contexto del equipo
 ↓
Buscar materiales
 ↓
Filtrar materiales
 ↓
Seleccionar materiales
 ↓
Agregar cantidades
 ↓
Carrito temporal
 ↓
Revisar
 ↓
Confirmar transferencia
 ↓
Backend
 ↓
PostgreSQL
 ↓
Respuesta
 ↓
Actualizar inventario origen y destino
```

Filtros previstos:

```text
Buscar por descripción
Categoría
U.M.
Almacén
```

El carrito es exclusivamente temporal.

No representa inventario persistido.

---

# 11. DEVOL — EQUIPO → INVENTARIO GENERAL

DEVOL representa el movimiento:

```text
EQUIPO
   ↓
DEVOL
   ↓
INVENTARIO GENERAL
```

Flujo:

```text
DEVOL
 ↓
Seleccionar equipo origen
 ↓
Consultar inventario del equipo
 ↓
Buscar / filtrar materiales
 ↓
Seleccionar materiales
 ↓
Definir cantidades
 ↓
Carrito temporal
 ↓
Revisar
 ↓
Confirmar devolución
 ↓
Backend
 ↓
PostgreSQL
 ↓
Resultado persistido
 ↓
Actualizar inventario del equipo
 ↓
Actualizar inventario general
```

---

# 12. CARRITOS TEMPORALES

Los carritos de TEAMS y DEVOL son mecanismos de UX.

```text
Inventario actual
      ↓
selección 1
selección 2
selección 3
      ↓
CARRO TEMPORAL
      ↓
confirmación
      ↓
UNA MUTACIÓN REAL
```

Mientras el carrito no se confirme:

```text
NO existe modificación real de inventario.
```

El Frontend puede mostrar:

```text
Saldo estimado después de la operación: X
```

pero nunca debe interpretarlo como saldo confirmado.

---

# 13. SINCRONIZACIÓN DE ESTADO

Toda mutación exitosa debe provocar una nueva lectura de los datos afectados.

```ts
mutation success
      ↓
invalidateQueries(...)
      ↓
GET nuevamente al Backend
      ↓
renderizar estado persistido
```

Aplicar especialmente a:

```text
Inventario general
Inventario de equipo
Catálogo
Equipos
Movimientos
Auditoría
```

---

# 14. FAIL-CLOSED

El Frontend debe diferenciar:

```text
stock = 0
```

de:

```text
no pude obtener el stock
```

Ejemplo válido:

```text
API responde:
stock_actual = 0

→ mostrar 0
```

Ejemplo inválido:

```text
API falla
→ React asigna 0
```

Regla:

```text
ERROR DE API ≠ STOCK CERO
```

---

# 15. FIBRA ÓPTICA

La interfaz debe contemplar:

```text
Fibra Óptica
├── Paquete
└── En Uso
```

## Paquete

Representa materiales manejados como carretes.

Operaciones:

```text
Agregar
Modificar
Eliminar
Transferir Stock / TEAMS
```

## En Uso

Representa materiales expresados en metros.

Debe seguir exactamente los mismos principios de autoridad y sincronización del Backend.

---

# 16. AUDITORÍA

La auditoría representa la trazabilidad de operaciones que realmente afectan al sistema.

Debe mostrar:

```text
Fecha/hora
Usuario
Acción
Material
Equipo/almacén
Origen
Destino
Resultado
```

No registrar acciones puramente visuales:

```text
Abrir pantalla
Cambiar pestaña
Abrir drawer
Realizar búsqueda
```

---

# 17. CANCELACIONES

Las cancelaciones son reversiones de movimientos previamente confirmados.

```text
mostrar opción de cancelar
        ↓
únicamente cuando el estado sea compatible
        ↓
solicitar cancelación al Backend
        ↓
esperar confirmación
        ↓
actualizar estado
```

Después de una cancelación exitosa:

```text
estado = CANCELADO
```

La interfaz debe impedir una segunda cancelación sobre el mismo movimiento.

---

# 18. REPORTES E IMPORTACIONES

## Reportes

Orientados a:

```text
Consulta
Análisis
Exportación
```

## Importaciones

Flujo:

```text
Archivo
 ↓
Backend
 ↓
Validación
 ↓
Preview
 ↓
Confirmación
 ↓
Transacción
```

Formatos permitidos:

```text
.csv
.xlsx
.xml
```

Formatos bloqueados:

```text
.doc
.docx
```

---

# 19. BÚSQUEDA Y FILTRADO

Criterios:

```text
Descripción
SKU
ID LISTA
Categoría
U.M.
Almacén
```

Buscador a granel:

```text
SKU inicial → SKU final
ID LISTA inicial → ID LISTA final
Descripción inicial → Descripción final
```

---

# 20. RELACIÓN ENTRE UI Y BACKEND

```text
┌──────────────────────────────────────────┐
│               FRONTEND                   │
│                                          │
│ Navega                                   │
│ Busca                                    │
│ Filtra                                   │
│ Selecciona                               │
│ Captura                                  │
│ Prepara carritos                         │
│ Valida visualmente                       │
│ Muestra estimaciones                     │
│ Muestra errores                          │
│ Muestra resultados                       │
└────────────────────┬─────────────────────┘
                     │ HTTP / JSON
                     ▼
┌──────────────────────────────────────────┐
│                 FASTAPI                  │
│                                          │
│ Transporte                               │
│ Validación                               │
│ Serialización                            │
│ Contratos                                │
└────────────────────┬─────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────┐
│              POSTGRESQL                  │
│                                          │
│ Autoridad del inventario                 │
│ Concurrencia                             │
│ Transacciones                            │
│ Stock                                    │
│ Reversiones                              │
│ Auditoría                                │
└──────────────────────────────────────────┘
```

---

# 21. OBJETIVO FINAL DE LA CONSTRUCCIÓN DEL FRONTEND

El objetivo es convertir las capacidades transaccionales ya existentes del Backend en una experiencia operativa coherente.

```text
CATÁLOGO
   ↓
INVENTARIO GENERAL
   ↓
SELECCIÓN DE EQUIPO
   ↓
TEAMS
   ↓
INVENTARIO DEL EQUIPO
   ↓
DEVOL
   ↓
INVENTARIO GENERAL
   ↓
AUDITORÍA
```

---

# 22. REGLA DE INTEGRACIÓN ENTRE LAS FASES

### Fase 1

```text
Layout
Navegación
Catálogo
Inventario general
Formularios base
ID LISTA
```

### Fase 2

```text
Equipos
Inventario sparse
```

### Fase 3

```text
TEAMS
DEVOL
Carritos
Mutaciones
Sincronización
```

### Fase 4

```text
Cancelaciones
Fibra Óptica
Auditoría
```

### Fase 5

```text
Importaciones
Reportes compatibles
QA integral
```

---

# 23. QUÉ DEBE HACER EL AGENTE ANTES DE IMPLEMENTAR

Preguntas obligatorias:

```text
¿Qué capacidad del Backend estoy consumiendo?
¿Qué endpoint real la expone?
¿Qué DTO real devuelve?
¿Qué entidad representa?
¿Qué mutación real ejecuta?
¿Qué query debe invalidarse después?
¿Qué componente existente puedo reutilizar?
¿Qué parte pertenece al Frontend?
¿Qué parte NO pertenece al Frontend?
```

Debe inspeccionar:

```text
frontend/
backend/
OpenAPI
OpenSpec
hooks
services
types
routes
components
queries
mutations
```

---

# 24. REGLA DE NO INVENCIÓN

La existencia de una funcionalidad visual no implica la existencia de un endpoint.

Ejemplo:

```text
"Transferir materiales"
```

NO implica automáticamente:

```text
POST /api/v1/teams/transfer
```

Primero debe verificarse el contrato real.

---

# 25. CRITERIO DE ÉXITO

```text
La UI representa correctamente el dominio
        +
Las operaciones utilizan contratos reales
        +
No existe autoridad de inventario en React
        +
Las mutaciones llegan al Backend
        +
PostgreSQL determina el resultado
        +
La UI vuelve a consultar el estado persistido
        +
Los errores no se convierten en stock = 0
        +
La auditoría refleja operaciones reales
        +
TEAMS y DEVOL funcionan de forma coherente
        +
El modelo sparse se conserva
        +
Las fases permanecen integradas
```

Resultado esperado:

```text
DMS - TELECOM
= una interfaz operacional sobre un Backend transaccional,
no un segundo sistema de inventario construido dentro del navegador.
```

---

# 26. REGLA FINAL PARA EL AGENTE

Antes de construir cualquier componente:

```text
¿QUÉ QUIERE HACER EL OPERADOR?
        ↓
¿QUÉ CAPACIDAD DEL BACKEND LO HACE POSIBLE?
        ↓
¿QUÉ CONTRATO REAL EXISTE?
        ↓
¿CÓMO DEBE REPRESENTARSE EN LA UI?
        ↓
¿QUÉ ESTADO DEBE INVALIDARSE DESPUÉS?
```

La misión del Frontend es encajar la experiencia operativa deseada sobre las capacidades reales del Backend, sin duplicar, alterar ni sustituir la autoridad transaccional existente.