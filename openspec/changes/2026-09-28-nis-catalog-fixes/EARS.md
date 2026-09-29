# EARS Requirements Specification

## Domain: Carga Inicial — Sección Destino
- **REQ-CARGA-001:** WHEN un operador declara `stock_inicial` en el alta de material, THE SYSTEM SHALL ofrecer "Fibra Óptica - Paquete" y "Fibra Óptica - En Uso" como destinos válidos junto a "Inventario General".
- **REQ-CARGA-002:** WHEN la sección destino es `FO_PAQUETE` o `FO_EN_USO`, THE SYSTEM SHALL rutear la carga inicial a `inventario_fibra` (módulo PAQUETE/EN_USO) vía `fn_cargar_stock_inicial_fibra`; la sección `GENERAL` continuará por `fn_cargar_stock_inicial`.
- **REQ-CARGA-003:** THE SYSTEM SHALL preservar la atomicidad y auditoría (`STOCK_INICIAL_FO`) idénticas al flujo general en toda carga inicial a Fibra Óptica.

## Domain: Unidades de Medida dinámicas
- **REQ-UM-001:** WHEN un material se crea o edita con un valor `u_m`, THE SYSTEM SHALL validarlo dinámicamente contra la tabla `ums` activa, aceptando cualquier U.M. creada o renombrada por el administrador.
- **REQ-UM-002:** IF el valor `u_m` no existe en la tabla `ums` activa, THEN THE SYSTEM SHALL rechazar la operación con un error determinístico 422.

## Domain: Invariante de inventario FO en Transferencias
- **REQ-TRF-001:** WHEN "Fibra Óptica - Paquete" o "Fibra Óptica - En Uso" se selecciona como origen en TEAMS, THE SYSTEM SHALL direccionar la consulta de inventario de origen a `inventario_fibra` (módulo correspondiente) y mantener íntegro el flujo transaccional TEAMS/DEVOL (bloqueo, validación de stock y auditoría sin rupturas). En DEVOL, el inventario de origen sigue siendo el del equipo; la raíz FO participa únicamente como destino válido.
- **REQ-TRF-002:** WHEN una raíz FO participa como origen TEAMS o destino DEVOL en un movimiento procesado o cancelado, THE SYSTEM SHALL invalidar la vista de inventario FO correspondiente (`['fibra', modulo]`) para evitar stock obsoleto en la UI.
