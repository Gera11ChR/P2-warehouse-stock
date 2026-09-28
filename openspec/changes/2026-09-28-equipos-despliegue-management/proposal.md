# OpenSpec Change Proposal

## Change ID
`2026-09-28-equipos-despliegue-management`

## Summary
Extender el modelo operativo de DMS-TELECOM para habilitar:
1. Administración flexible (modificar/eliminar) de Categorías y Unidades de Medida (U.M.) en la Sección General[cite: 7].
2. Integración de los inventarios secundarios de Fibra Óptica (Paquete y En Uso) al mismo nivel que el inventario general en transferencias[cite: 7].
3. Configuración operativa autónoma por equipo (stock mínimo, categoría, U.M.) preservando la inmutabilidad del catálogo y del stock actual[cite: 7].
4. Nueva función "DESPLIEGUE" independiente por equipo para registrar materiales tomados para uso en campo, sobrantes devueltos y actualización automática de existencias[cite: 7].
5. Vista dedicada de consulta para equipos (evitando accesos accidentales a flujos de modificación)[cite: 7].
6. Reorientación de la sección Reportes de forma exclusiva a la función DESPLIEGUE y exportación CSV[cite: 7].

## Business Problem
- **Catálogos Inflexibles:** No existe forma de eliminar o modificar categorías y U.M. creadas. Si un material se elimina, su categoría sigue existiendo sin opción a que el administrador la quite o mantenga a discreción[cite: 7].
- **Transferencias Limitadas:** Los inventarios de Fibra Óptica no aparecen como opciones válidas de almacén, impidiendo transferir material desde esas secciones a los equipos[cite: 7].
- **Falta de Autonomía en Equipos:** Los equipos no pueden definir su propio conteo de necesidad (stock mínimo) ni clasificar sus materiales (categoría/U.M.) de forma aislada[cite: 7].
- **Puntos Ciegos en Campo:** No hay control de lo que un equipo toma para una jornada vs. lo que realmente sobra y devuelve, generando brechas en la trazabilidad[cite: 7].
- **Riesgo Operativo:** Consultar el inventario de un equipo requiere abrir ventanas de modificación, arriesgando alteraciones no deseadas de datos[cite: 7].
- **Reportes Desenfocados:** Se requieren informes centrados específicamente en la trazabilidad de la nueva función DESPLIEGUE[cite: 7].

## Proposed Changes
1. **Modales de Catálogo:** Habilitar botones en el apartado general para desplegar interfaces de eliminación o modificación de Categorías y U.M. existentes[cite: 7].
2. **Selector Multi-Almacén:** Incorporar explícitamente "Fibra Óptica - Paquete" y "Fibra Óptica - En Uso" a la lista de almacenes disponibles en TEAMS/DEVOL[cite: 7].
3. **Parámetros de Equipo Locales:** Habilitar la edición de stock mínimo, categoría y U.M. exclusivamente dentro de la vista del equipo, bloqueando la edición del stock actual[cite: 7].
4. **Flujo DESPLIEGUE:** Crear una lista de despliegue donde el equipo registre materiales seleccionados, ingrese sobrantes al final de la jornada y el sistema ajuste automáticamente el inventario del equipo[cite: 7].
5. **Separación de Vistas:** Implementar una vista dedicada para consulta segura de equipos, separada de la opción "Modificar Equipo"[cite: 7].
6. **Módulo de Reportes CSV:** Ajustar la pantalla de Reportes para designar informes sobre las listas de despliegue y los materiales usados, exportables en CSV[cite: 7].

## Impact Assessment
- **Backend/DB:** Nuevos servicios CRUD para catálogos, ampliación del servicio de transferencias, nuevas tablas para soportar el flujo de "Lista de Despliegue" y endpoints de reportes CSV.
- **Frontend:** Implementación de modales de configuración, actualización del formulario de transferencias, interfaces interactivas para "DESPLIEGUE", vista de solo lectura de equipos y refactorización de la UI de Reportes.
- **Auditoría:** Se mantiene la política actual; los ajustes de inventario derivados de "DESPLIEGUE" deben registrarse con la misma coherencia que TEAMS/DEVOL[cite: 7].

## Out of Scope
- Alteración manual o directa del stock actual desde la vista de configuración del equipo (su cambio indirecto seguirá dado por transferencias o despliegues)[cite: 7].
- Modificación del código y descripción del material dentro del equipo (datos inmutables)[cite: 7].