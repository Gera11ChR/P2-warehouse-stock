# Reporte de Necesidades Operativas: Autonomía CRUD para Fibra Óptica

## 1. Contexto Actual y Limitación del Sistema
Actualmente, los apartados de "Fibra Óptica - Paquete" y "Fibra Óptica - En Uso" operan bajo un contrato restrictivo donde su inventario (`inventario_fibra` consumido vía `/fibra/<modulo>`) solo puede ser alterado mediante el módulo de Transferencias (operaciones TEAMS/DEVOL). 

A diferencia de la Sección General, el área de Fibra Óptica carece de la capacidad de interactuar directamente con sus registros. No es posible seleccionar un material para visualizar sus detalles, modificar sus propiedades de catálogo, alterar su stock manualmente ni eliminarlo.

## 2. Objetivo de Negocio
Dotar a las secciones de Fibra Óptica (Paquete y En Uso) del mismo comportamiento flexible, autónomo e independiente que posee el Inventario General. Cada apartado de fibra debe operar como un inventario de gestión completa (CRUD) sin perder su compatibilidad con el ruteo de transferencias existente.

## 3. Requerimientos Funcionales

### 3.1. Interfaz de Usuario y Acciones de Tabla
Al seleccionar un material en las tablas de "Fibra Óptica - Paquete" o "Fibra Óptica - En Uso", el sistema debe desplegar las siguientes opciones:
- **Ver Detalle del material*.
- **Modificar material**.
- **Eliminar material**.

### 3.2. Edición de Propiedades del Catálogo
El modal de "Modificar Material" para Fibra Óptica debe permitir la edición directa de los siguientes campos:
- Descripción.
- Código (SKU).
- Clasificación / Categoría.
- Unidad de Medida (U.M.).
- Stock Mínimo.

### 3.3. Gestión Manual de Stock y Auditoría
Al igual que en el inventario general, si el operador modifica manualmente el campo **STOCK ACTUAL** dentro del modal de edición en una sección de fibra, el sistema debe:
1. Exigir obligatoriamente un motivo o justificación de la modificación.
2. Calcular automáticamente el diferencial en el backend (stock nuevo vs stock anterior).
3. Registrar el evento de ajuste en el módulo de Auditoría del sistema.

## 4. Invariantes del Sistema
- La implementación de estas capacidades CRUD en el frontend y backend para Fibra Óptica **no debe romper ni alterar** el funcionamiento del módulo de Transferencias (TEAMS/DEVOL).
- Cada módulo de fibra (Paquete y En Uso) debe mantener el aislamiento de sus datos (operando de forma independiente sobre `inventario_fibra` según su módulo correspondiente).