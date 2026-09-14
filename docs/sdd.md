# Software Design Document (SDD) - DMS - TELECOM

## 1. Identidad y Nombre del Sistema
- **Nombre de la Plataforma**: DMS - TELECOM (reemplaza visual e internamente a P2 WMS en toda la interfaz).
- **Catálogo Maestro**: 53 materiales iniciales con `ID LISTA` inmutable.

---

## 2. Inventario General y Catálogo Maestro

### Buscador y Filtros
- **Búsqueda Básica**: Por Código, Descripción e `ID LISTA`.
- **Regla del ID LISTA**: Identificador visible, permanente e inmutable asignado a cada material para búsquedas, reportes y auditorías. Si un material es eliminado, su `ID LISTA` NO se reutiliza ni se renumera.
- **Buscador a Granel**: Filtros por rango:
  - Desde `ID LISTA` -> Hasta `ID LISTA`.
  - Desde `SKU` -> Hasta `SKU`.
  - Desde `Descripción` -> Hasta `Descripción`.

### Campos Visibles en Inventario
- `ID LISTA`
- `Código`
- `Descripción`
- `Categoría`
- `U.M.` (Unidad de Medida)
- `Stock Actual`
- `Stock Mínimo`
- `Alerta Stock`
- `Sección/Almacén`

---

## 3. Clasificación y Gestión de Materiales (CRUD)

### Clasificación Dual
- **Eliminación Definitiva**: Se elimina completamente el campo legacy `TIPO`.
- **Esquema Dual**:
  - `CATEGORÍA`: Desplegable de categorías existentes.
  - `NUEVA CATEGORÍA`: Campo de texto libre. Si se captura una nueva categoría, esta queda disponible para futuros materiales.

### Operaciones CRUD
- **Agregar Material**:
  - Obligatorio: `Descripción`.
  - Opcionales: `Código`, `Categoría`, `U.M.`, `Stock Inicial`, `Stock Mínimo`, `Sección/Almacén`.
  - Persistencia inmediata, visibilidad en tablas y registro en auditoría.
- **Modificar Material**: Permite editar atributos salvo `id_lista`. Dispara trigger de auditoría.
- **Eliminar Material**: Eliminación controlada con confirmación obligatoria y registro en auditoría.

---

## 4. Funcionalidades Transaccionales

### Funcionalidad TEAMS (Transferencia a Equipos)
Mecanismo oficial para transferir materiales desde inventarios origen permitidos (`Inventario General`, `Fibra Óptica - Paquete`, `Fibra Óptica - En Uso`) hacia un equipo.
- **Flujo**: Selección de equipo -> Carrito temporal -> Especificación de cantidades -> Confirmación.
- **Garantía Transaccional**: Descuento en origen, incremento en destino y registro de auditoría ejecutados en una única transacción atómica.

### Funcionalidad DEVOL (Devolución a Inventario General)
Proceso inverso a TEAMS para retornar materiales desde un equipo hacia el Inventario General.
- **Validaciones**: Bloqueo si la cantidad solicitada excede el stock disponible en el equipo. Advertencia de stock mínimo.
- **Operación**: Descuento en equipo, `UPSERT` en inventario central y registro atómico de auditoría.

---

## 5. Inventario por Equipos (Sparse Data Model)
- **Rediseño Completo**: Se elimina la replicación automática de materiales por equipo. Existe un único catálogo maestro de materiales.
- **Base de Datos**: Solo existen registros en `inventario_equipos` cuando un equipo realmente tiene stock o movimientos.
- **Interfaz (UI)**: La vista de un equipo muestra el catálogo completo rindiendo `Stock = 0` para aquellos materiales sin registro en base de datos.

---

## 6. Módulos Adicionales
- **Fibra Óptica**: Manejo de inventarios independientes para `Paquete` (carretes) y `En Uso` (metros).
- **CRUD de Equipos**: Creación, edición y eliminación de equipos con sus integrantes.
- **Importaciones/Exportaciones**:
  - Exportación a PDF, Excel y CSV.
  - Importación en formatos CSV, XLSX y XML con validación previa de estructura y trazabilidad en `historial_importaciones`.[cite: 1, 2]
- **Auditoría**: Registro automático e inmutable de operaciones críticas (`TEAMS`, `DEVOL`, modificaciones, ajustes y borrados) con detalles JSONB.