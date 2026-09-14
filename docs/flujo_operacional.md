# Flujo Operacional Consolidado (DMS - TELECOM SDD v10/10)

## Arquitectura del Flujo (Pipeline de 5 Fases)

### FASE 1: CONTRATO & DISEÑO
`OpenSpec (openspec.yaml)` + `DDL SQL PostgreSQL 10/10` -> `@arq-reviewer`
*(Resultado: Contrato Aprobado)*

### FASE 2: IMPLEMENTACIÓN BACKEND
Sub-agente `@coder` genera Schemas Pydantic V2, ORM y rutas FastAPI.

### FASE 3: AUDITORÍA DE DOMINIO Y ESPECIALIDAD
- `@dba-guard`: Bloqueos `FOR UPDATE`, Stored Functions e Inmutabilidad.
- `@sec-ops`: RBAC, `extra="forbid"` y Parsers CSV/XLSX/XML.
- `@auditor`: Verificación de Drift vs Contrato OpenSpec.

### FASE 4: LOOP DE RETROALIMENTACIÓN || FASE 5: QA & AUTOMACIÓN
- *(Si hay Hallazgos)*: Drift Report -> `@coder` refactoriza bloque.
- *(Sin Hallazgos / Aprobado)*: `@tester` ejecuta Pytest. -> **[PRODUCCIÓN READY]**

---

## Detalle Operacional Fase por Fase

### Fase 1: Gobernanza de Contrato y Arquitectura
1. **Carga de Fuente Única de Verdad**: Se deposita en la raíz/rutas designadas los archivos `openspec.yaml` y el script DDL SQL.
2. **Validación de Invariantes (`@arq-reviewer`)**: Verifica que la especificación cumpla con las reglas no negociables del dominio:
   - `id_lista` visible, permanente e inmutable (sin re-numeración).
   - Modelo disperso (*Sparse Model*) para catálogo por equipos.
   - Uso exclusivo de `inventario_almacen` (eliminando la ambigüedad de almacenes).
   - Eliminación definitiva del campo `TIPO` por el selector dual de categorías.

### Fase 2: Codificación Restringida (`@coder`)
1. **Generación de DTOs y Controladores**: Coder construye las estructuras en FastAPI y Pydantic V2.
2. **Delegación Transaccional Obligatoria**: Toda modificación de inventario (TEAMS, DEVOL o Reversión) se delega a la base de datos mediante la invocación directa de `fn_procesar_movimiento` y `fn_cancelar_movimiento`. Se prohíbe reescribir lógica de cálculo de stock en Python.[cite: 1]

### Fase 3: Triada de Fiscalización Especializada
1. **Auditoría SQL (`@dba-guard`)**: Revisa que las consultas lean la vista `vw_inventario_equipo_completo` y que no existan escrituras directas sobre las tablas de inventario sin pasar por las Stored Functions.
2. **Auditoría de Seguridad (`@sec-ops`)**: Exige que todos los esquemas Pydantic incluyan `model_config = ConfigDict(extra="forbid")` para bloquear la inyección de atributos no declarados, y verifica la sanitización en la carga masiva registrada en `historial_importaciones`.
3. **Auditoría de Conformidad (`@auditor`)**: Emite el reporte de desvíos (*Drift Report*).

### Protocolo de Retroalimentación y Remediación (Feedback Loop)
Cuando Auditor, `@dba-guard` o `@sec-ops` emiten un estado **RECHAZADO**, se ejecuta el siguiente ciclo automático de resolución
`[ARCHIVO RECHAZADO]` -> `[REPORTE DE HALLAZGOS]` -> `[REFACTORIZACIÓN EN CODER]` -> `[RE-EVALUACIÓN]`

1. **Aislamiento del Punto de Fallo**: El sub-agente fiscalizador genera un ticket estructurado en formato markdown conteniendo:
   - Archivo y líneas afectadas (Ej. `app/routers/teams.py:45`).
   - Regla Violada (Ej. Intento de actualización directa de stock en Python en lugar de invocar `fn_procesar_movimiento`).
   - Acción Correctora Requerida (Especificación exacta de la firma SQL a consumir).
2. **Refactorización Enfocada (`Coder`)**: Coder recibe el reporte, aplica el ajuste únicamente sobre el bloque observado sin alterar otros componentes del sistema, y notifica la corrección.
3. **Control de Ciclos**: Se establece un límite máximo de 3 re-intentos de refactorización. Si en el tercer intento persiste el desvío, la tarea escala a revisión humana.

### Protocolo de Versionado del Contrato OpenSpec
- **Cambios Menores (Non-breaking)**: Adición de campos opcionales en respuestas JSON o nuevos reportes exportables incrementan la versión minor del contrato (`v1.1.0`). No requieren ajustes en esquemas de BD existentes.
- **Cambios Mayores (Breaking Changes)**: Alteraciones en firmas de Stored Functions, nuevos estados en `movimientos_cabecera` o ajustes en el DDL incrementan la versión major (`v2.0.0`).
  - *Regla de Ejecución*: Ante un cambio major, el flujo obliga a re-ejecutar en secuencia estricta a `@arq-reviewer` para validar retrocompatibilidad antes de permitir que Coder toque el código fuente.

### Fase 5: Testing Automático e Integración Continua (`@tester`)
Una vez obtenida la aprobación de compliance (`Auditor: APROBADO`), el sub-agente `@tester` ejecuta la suite automatizada en Pytest:
1. **Prueba de Atomicidad TEAMS**: Valida que una transferencia descuente stock en la sección origen e incremente en el equipo dentro de la misma transacción.
2. **Prueba de Límite TEAMS**: Intenta transferir una cantidad superior al stock disponible y verifica el lanzamiento de error HTTP 400/422.
3. **Prueba Upsert DEVOL**: Verifica que la devolución de un material cree automáticamente el registro en la sección central si este no existía previamente (`ON CONFLICT DO UPDATE`).
4. **Prueba Alerta Stock Mínimo**: Confirma la presencia de la bandera `alerta_stock_minimo: true` en los detalles JSONB de auditoría cuando el remanente cae por debajo del umbral configurado.
5. **Prueba de Reversión**: Ejecuta `fn_cancelar_movimiento` y comprueba la restitution matemática exacta de inventarios.
6. **Prueba de Importación Masiva**: Procesa un archivo CSV corrupto y verifica la inserción de métricas y log de errores en `historial_importaciones`.