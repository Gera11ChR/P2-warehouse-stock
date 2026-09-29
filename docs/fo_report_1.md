# Reporte de Incidente: Fallo en Eliminación de Inventario (Fibra Óptica)
**ID de Reporte:** `fo_report_1`
**Estado:** Abierto
**Prioridad:** Alta (Bloquea funcionalidad CRUD específica)

## 1. Contexto General
El sistema general de DMS-TELECOM está operando correctamente en su totalidad, a excepción de un único detalle localizado: **No es posible eliminar materiales exclusivamente desde las secciones del inventario de Fibra Óptica** (tanto en el módulo `PAQUETE` como en `EN_USO`).

El resto del programa, incluyendo transferencias y el inventario general, funciona sin inconvenientes. El formulario del frontend recopila correctamente los datos (incluyendo el motivo obligatorio) y emite la petición, pero el servidor la rechaza.

## 2. Descripción Técnica del Problema (Síntomas)
Al intentar eliminar un material desde la interfaz de Fibra Óptica, el usuario recibe una alerta visual genérica ("Ocurrió un error")[cite: 8]. 

El análisis de la consola de red del navegador revela lo siguiente:
* **Fallo exacto:** La petición HTTP `DELETE` retorna un código de estado **500 (Internal Server Error)**[cite: 9, 10].
* **Módulos afectados:** Ocurre indistintamente en ambas categorías de fibra:
  * Ruta afectada 1: `/api/v1/fibra/EN_USO/materiales/{id}?motivo=...`.
  * Ruta afectada 2: `/api/v1/fibra/PAQUETE/materiales/{id}?motivo=...`[cite: 10].
* **Frontend validado:** El frontend está construyendo bien la URL y pasando el query parameter `motivo` correctamente (ej. `?motivo=No+deja+eliminar`)[cite: 9, 10]. El fallo reside 100% en cómo el backend procesa esta ruta.

## 3. Puntos de Investigación y Resolución Requeridos (Directivas para el Agente)
El problema es un error no controlado (500) en el backend (FastAPI). Para solucionar esto sin ambigüedades, el agente debe:

1. **Auditar el endpoint de FastAPI:** Revisar la función que maneja el método `DELETE` en el enrutador de Fibra Óptica (probablemente en `backend/app/api/v1/fibra.py`). Verificar si hay un error tipográfico en la inyección de dependencias, parámetros esperados (path parameters vs query parameters), o fallos al desempaquetar el objeto.
2. **Auditar la capa de Base de Datos (Servicio / Repositorio):** Revisar la ejecución del stored procedure o función PostgreSQL (`fn_eliminar_inventario_fibra`). 
   - ¿Se están pasando correctamente los tipos de datos (entero para el ID, string para el módulo y motivo)?
   - ¿Existe un problema de *Foreign Key Constraints* (claves foráneas) al intentar borrar un material que tiene stock (ej. 4,300 M) que no está siendo capturado (try/catch) adecuadamente por Python para retornar un HTTP 400 explicativo en lugar de un HTTP 500?
3. **Reparación esperada:**
   - Corregir el bug lógico en el backend que causa la excepción 500.
   - Si la eliminación es rechazada por integridad referencial (el material tiene un historial que no puede borrarse), el backend debe capturar el `IntegrityError` y devolver un HTTP 400/409 con un mensaje claro (ej. "No se puede eliminar porque existen movimientos asociados"), para que el frontend lo muestre y no truene.

## 4. Criterio de Aceptación
El bug se considerará resuelto cuando se pueda realizar un `DELETE` exitoso (retornando HTTP 200 o 204) o, en su defecto, un error controlado (HTTP 400) que el frontend pueda interpretar, eliminando por completo los errores 500 (Internal Server Error) en las rutas de Fibra Óptica.