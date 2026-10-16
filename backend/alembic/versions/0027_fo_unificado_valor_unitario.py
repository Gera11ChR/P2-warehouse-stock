"""Inventario FO unificado + Valor Unitario + Valor Total — cambio
2026-10-fo-unificado-valor-unitario.

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-15

Fase 5/7 (Backend-First) — implementa RF-1..RF-10 del plan §1:

1. `catalogo_materiales.valor_unitario NUMERIC(12,3) NOT NULL DEFAULT
   1.000` con CHECK `ck_catalogo_valor_unitario_non_negative
   (valor_unitario >= 0)` (RF-2/RF-3). El DEFAULT rellena el catálogo
   existente sin UPDATE sobre datos previos.
2. Tipos decimales (RF-6): `stock_actual`/`cantidad`/`cantidad_tomada`/
   `cantidad_consumida` de inventarios, movimientos y seguimientos pasan a
   NUMERIC(12,3). `auditoria_eventos.cantidad` usa cast explícito
   `USING cantidad::NUMERIC(12,3)` (condición L2 del dictamen de
   @arq-reviewer): el ALTER TYPE no dispara triggers de fila
   (`tg_ledger_auditoria_inmutable` es BEFORE UPDATE/DELETE) y no cambia
   valores — el ledger inmutable conserva conteo y contenido (§2.4). Los
   CHECK existentes (`>= 0`, `> 0`, `consumida <= tomada`) se conservan y
   `DEFAULT 0` se re-declara como `0`.
3. Fusión del Inventario FO (RF-1/RF-7): un evento `FO_UNIFICADO` por
   material (INSERT permitido; ledger append-only), agregación en tabla
   temporal, reemplazo de la PK por `(material_id)`, eliminación de
   `modulo`, de su CHECK `ck_inventario_fibra_modulo` y del índice
   redundante `ix_inventario_fibra_material`. Verificación interna
   `SUM(stock_actual)` antes == después; si difiere, RAISE EXCEPTION y la
   transacción completa revierte (Constitución §4.1/§4.3).
4. Sección de ruteo única `('Inventario FO','FO',FALSE)` (INSERT
   idempotente por `nombre` único) y CHECK `ck_secciones_tipo` ampliado
   con 'FO'. `FO_PAQUETE`/`FO_EN_USO` se conservan (referenciadas por
   movimientos históricos; jamás se borran).
4b. Continuidad de permisos (decisión D-2, T7; visto bueno @sec-ops y
   @arq-reviewer): cada actor con scope sobre `FO_PAQUETE` o `FO_EN_USO`
   recibe scope sobre la sección `FO` (`INSERT ... ON CONFLICT DO NOTHING`,
   idempotente). Es una EXPANSIÓN DE PRIVILEGIO intencional e inevitable al
   unificar el inventario: quien solo operaba «En Uso» pasa a operar todo el
   Inventario FO. Los scopes legacy se conservan (RF-9: movimientos
   históricos). Nunca se otorga scope a actores sin scope legacy.
5. Stored functions re-publicadas (plan §1.4): variables y parámetros
   decimales, sin `p_modulo`/`p_origen_modulo`/`p_destino_modulo`, ramas
   FO por `material_id`, aceptación de secciones legacy 'FO_PAQUETE'/
   'FO_EN_USO' (RF-9: BORRADOR y confirmados históricos siguen
   procesables/cancelables), validación de escala como defensa en
   profundidad (RF-6) y `DROP FUNCTION` de las firmas anteriores para
   evitar sobrecargas ambiguas.
6. `fn_auditar_modificacion_material` + `tg_auditar_modificacion_material`
   extendidos con `valor_unitario` (RF-7).
7. `fn_valor_total_inventario()` (RF-4): aritmética NUMERIC exacta sin
   tope intermedio, ROUND(...,3) final, LANGUAGE sql STABLE.

downgrade() — reverso 0027 -> 0026 (secuencia L5 del plan §1.7):
* ABORTA si existe cualquier valor fraccionario (`<> TRUNC(x)`) en
  `stock_actual`/`cantidad`/`cantidad_tomada`/`cantidad_consumida`/
  `auditoria_eventos.cantidad` (E14: cero pérdida silenciosa).
* Retira PRIMERO los scopes sobre la sección `FO` que el upgrade copió (D-2:
  actores que además tienen scope sobre `FO_PAQUETE`/`FO_EN_USO`); luego
  ABORTA si `movimientos_cabecera`/`movimientos_detalle`/
  `inventario_almacen`/`actor_almacen_scopes` aún referencian la sección
  `Inventario FO` (p. ej. un scope concedido directamente a FO por un actor
  SIN scope legacy). Caso límite documentado: un actor con scope legacy Y un
  scope FO concedido directamente pierde este último en el downgrade (no se
  distingue de uno derivado; la sección FO deja de existir en 0026 y su
  permiso efectivo previo —los scopes legacy— se conserva).
* Restaura `modulo` en `inventario_fibra` con PK `(modulo, material_id)`,
  CHECK `ck_inventario_fibra_modulo` e índice `ix_inventario_fibra_material`;
  la existencia total se coloca en `modulo='PAQUETE'`. La partición
  original NO se reconstruye (reversión con pérdida de la partición, no de
  la cantidad).
* Devuelve las columnas a INTEGER (`auditoria_eventos.cantidad` con
  `USING cantidad::INTEGER`, garantizado entero por el abort previo).
* Restaura `ck_secciones_tipo` sin 'FO', elimina la fila de la sección FO,
  elimina `valor_unitario`, su CHECK y `fn_valor_total_inventario`.
* AL FINAL (L5) restaura las funciones verbatim de sus migraciones base
  (constantes `FN_*_ANTERIOR` con el SQL original) y el trigger/función de
  auditoría previos (0013), de modo que ninguna función restaurada quede
  referenciando la columna `modulo` inexistente en pasos intermedios.
 * Los eventos `FO_UNIFICADO` ya emitidos permanecen (ledger inmutable).

CORRECCIÓN POST-T5 (Drift T5-1, @tester) — aplicada IN-PLACE sobre esta
migración (sin revisión nueva): la versión original re-publicó
`fn_crear_seguimiento` (base 0016) y `fn_agregar_todo_seguimiento` (base
0021) con cuerpos PRE-0024, perdiendo la nomenclatura oficial "Unidad"
introducida por `0024_unidad_textos_raise.py` (cláusula de override de
nomenclatura oficial `.agents.md` §3 — innegociable). Se restauran los
literales POST-0024 EXACTOS de la 0024 en ambos cuerpos (NUEVA y
ANTERIOR; el ANTERIOR restaura el estado real de 0026, que ya incluía la
nomenclatura 0024, y sin ello el downgrade encadenado hacia 0024
abortaría por literal ausente):

* `fn_crear_seguimiento` (FN_CREAR_SEGUIMIENTO_NUEVA/_ANTERIOR):
  - "El equipo ID % no existe o se encuentra inactivo." ->
    "La unidad ID % no existe o se encuentra inactiva."
  - "El equipo ID % ya posee un seguimiento abierto." ->
    "La unidad ID % ya posee un seguimiento abierto."
* `fn_agregar_todo_seguimiento` (FN_AGREGAR_TODO_NUEVA/_ANTERIOR):
  - "no pertenece al equipo ID %" -> "no pertenece a la unidad ID %"

Las funciones re-publicadas desde bases POST-0024 conservaban ya los
textos oficiales y NO se tocaron: `fn_procesar_movimiento` y
`fn_cancelar_movimiento` (base 0026) y `fn_cerrar_seguimiento` (base
0025). Verificación en BD: pg_get_functiondef sobre `p2_test` tras
`downgrade 0026 && upgrade head`.
"""

from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

# ================================================================
# §1.5 — auditoría de valor_unitario (RF-7), base 0013
# ================================================================

FN_AUDITAR_MATERIAL_NUEVA = """
CREATE OR REPLACE FUNCTION fn_auditar_modificacion_material()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.codigo IS DISTINCT FROM NEW.codigo OR
        OLD.descripcion IS DISTINCT FROM NEW.descripcion OR
        OLD.categoria_id IS DISTINCT FROM NEW.categoria_id OR
        OLD.u_m IS DISTINCT FROM NEW.u_m OR
        OLD.stock_minimo IS DISTINCT FROM NEW.stock_minimo OR
        OLD.is_active IS DISTINCT FROM NEW.is_active OR
        OLD.valor_unitario IS DISTINCT FROM NEW.valor_unitario) THEN

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, resultado, detalles
        ) VALUES (
            -- RF-7 (Drift T7 H-1): el evento atribuye al ACTOR de la API
            -- (`app.actor`, fijado por el servicio), con fallback al rol de BD.
            COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER),
            'MATERIAL_MODIFICADO', NEW.id_lista, 'EXITO',
            jsonb_build_object(
                'modulo', 'CATALOGO', 'accion', 'MODIFICAR',
                'valores_anteriores', jsonb_build_object(
                    'codigo', OLD.codigo, 'descripcion', OLD.descripcion,
                    'categoria_id', OLD.categoria_id, 'u_m', OLD.u_m,
                    'stock_minimo', OLD.stock_minimo, 'is_active', OLD.is_active,
                    'valor_unitario', OLD.valor_unitario
                ),
                'valores_nuevos', jsonb_build_object(
                    'codigo', NEW.codigo, 'descripcion', NEW.descripcion,
                    'categoria_id', NEW.categoria_id, 'u_m', NEW.u_m,
                    'stock_minimo', NEW.stock_minimo, 'is_active', NEW.is_active,
                    'valor_unitario', NEW.valor_unitario
                )
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_auditar_modificacion_material ON catalogo_materiales;
CREATE TRIGGER tg_auditar_modificacion_material
AFTER UPDATE ON catalogo_materiales
FOR EACH ROW EXECUTE FUNCTION fn_auditar_modificacion_material();
"""

# ================================================================
# §1.6 — fn_valor_total_inventario (RF-4), SQL EXACTO del plan
# ================================================================

FN_VALOR_TOTAL_INVENTARIO = """
CREATE OR REPLACE FUNCTION fn_valor_total_inventario()
RETURNS NUMERIC AS $$
    SELECT ROUND(
        COALESCE((SELECT SUM(ia.stock_actual * cm.valor_unitario)
                  FROM inventario_almacen ia
                  JOIN secciones s ON s.almacen_id = ia.almacen_id
                                  AND s.tipo = 'GENERAL' AND s.is_active
                  JOIN catalogo_materiales cm ON cm.id_lista = ia.material_id AND cm.is_active), 0)
      + COALESCE((SELECT SUM(f.stock_actual * cm.valor_unitario)
                  FROM inventario_fibra f
                  JOIN catalogo_materiales cm ON cm.id_lista = f.material_id AND cm.is_active), 0)
    , 3);
$$ LANGUAGE sql STABLE;
"""

# ================================================================
# §1.4 — stored functions re-publicadas (base: cuerpo vigente)
# ================================================================

FN_PROCESAR_NUEVA = """
CREATE OR REPLACE FUNCTION fn_procesar_movimiento (p_movimiento_id INT)
RETURNS VOID AS $$
DECLARE
    v_rec RECORD;
    v_cabecera RECORD;
    v_stock_disponible NUMERIC(12,3);
    v_stock_minimo INT;
    v_alerta_stock BOOLEAN := FALSE;
    v_nuevo_stock_origen NUMERIC(12,3);
    v_origen_id INT;
    v_origen_tipo TEXT;
    v_destino_tipo TEXT;
BEGIN
    SELECT * INTO v_cabecera
    FROM movimientos_cabecera
    WHERE id = p_movimiento_id AND estado = 'BORRADOR'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El movimiento ID % no existe o no se encuentra en estado BORRADOR.', p_movimiento_id;
    END IF;

    -- El tipo de sección DESTINO se resuelve una vez (DEVOL). El ORIGEN se
    -- resuelve POR LÍNEA (0026): una transferencia puede combinar líneas de
    -- Inventario General y de Fibra Óptica (secciones FO/FO_* = manejadores
    -- de ruteo hacia el inventario_fibra unificado de 0027).
    SELECT tipo INTO v_destino_tipo
    FROM secciones
    WHERE almacen_id = v_cabecera.destino_almacen_id;

    -- Orden DETERMINISTA de bloqueo (origen, material): dos confirmaciones
    -- concurrentes con las mismas líneas nunca se interbloquean (§2.3).
    FOR v_rec IN SELECT md.*, cm.stock_minimo,
                        COALESCE(md.origen_almacen_id, v_cabecera.origen_almacen_id) AS origen_efectivo
                 FROM movimientos_detalle md
                 JOIN catalogo_materiales cm ON cm.id_lista = md.material_id
                 WHERE md.movimiento_id = p_movimiento_id
                 ORDER BY COALESCE(md.origen_almacen_id, v_cabecera.origen_almacen_id), md.material_id LOOP

        v_stock_minimo := v_rec.stock_minimo;
        v_alerta_stock := FALSE;
        v_origen_id := v_rec.origen_efectivo;

        IF v_cabecera.tipo_movimiento = 'TEAMS' THEN
            IF v_origen_id IS NULL THEN
                RAISE EXCEPTION 'La línea del material ID LISTA % no tiene sección de origen.', v_rec.material_id;
            END IF;

            SELECT tipo INTO v_origen_tipo
            FROM secciones
            WHERE almacen_id = v_origen_id;

            IF v_origen_tipo = 'GENERAL' THEN
                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_almacen
                WHERE almacen_id = v_origen_id AND material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en Origen (Sección ID %) para el material ID LISTA %. Disponible: %, Solicitado: %',
                        v_origen_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                v_nuevo_stock_origen := v_stock_disponible - v_rec.cantidad;

                IF v_nuevo_stock_origen <= v_stock_minimo THEN
                    v_alerta_stock := TRUE;
                END IF;

                UPDATE inventario_almacen
                SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_origen_id AND material_id = v_rec.material_id;

            ELSIF v_origen_tipo IN ('FO','FO_PAQUETE','FO_EN_USO') THEN
                -- Inventario FO unificado (0027): la sección 'FO' y los tipos
                -- legacy FO_PAQUETE/FO_EN_USO enrutan al mismo inventario_fibra,
                -- resuelto por material_id SIN modulo (RF-9).

                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_fibra
                WHERE material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en Origen (Inventario FO) para el material ID LISTA %. Disponible: %, Solicitado: %',
                        v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                v_nuevo_stock_origen := v_stock_disponible - v_rec.cantidad;

                IF v_nuevo_stock_origen <= v_stock_minimo THEN
                    v_alerta_stock := TRUE;
                END IF;

                UPDATE inventario_fibra
                SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
                WHERE material_id = v_rec.material_id;

            ELSE
                RAISE EXCEPTION 'La sección ID % no es un origen válido para movimientos TEAMS.', v_origen_id;
            END IF;

            INSERT INTO inventario_equipos (equipo_id, material_id, stock_actual, ultimo_movimiento_id)
            VALUES (v_cabecera.destino_equipo_id, v_rec.material_id, v_rec.cantidad, p_movimiento_id)
            ON CONFLICT (equipo_id, material_id)
            DO UPDATE SET stock_actual = inventario_equipos.stock_actual + EXCLUDED.stock_actual,
                          ultimo_movimiento_id = p_movimiento_id,
                          updated_at = CURRENT_TIMESTAMP;

        ELSIF v_cabecera.tipo_movimiento = 'DEVOL' THEN
            SELECT stock_actual INTO v_stock_disponible
            FROM inventario_equipos
            WHERE equipo_id = v_cabecera.origen_equipo_id AND material_id = v_rec.material_id
            FOR UPDATE;

            IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                RAISE EXCEPTION 'La unidad ID % no cuenta con stock suficiente del material ID LISTA % para devolver.',
                    v_cabecera.origen_equipo_id, v_rec.material_id;
            END IF;

            v_nuevo_stock_origen := v_stock_disponible - v_rec.cantidad;

            UPDATE inventario_equipos
            SET stock_actual = v_nuevo_stock_origen,
                ultimo_movimiento_id = p_movimiento_id,
                updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.origen_equipo_id AND material_id = v_rec.material_id;

            IF v_destino_tipo = 'GENERAL' THEN
                INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual)
                VALUES (v_cabecera.destino_almacen_id, v_rec.material_id, v_rec.cantidad)
                ON CONFLICT (almacen_id, material_id)
                DO UPDATE SET stock_actual = inventario_almacen.stock_actual + EXCLUDED.stock_actual, updated_at = CURRENT_TIMESTAMP;

            ELSIF v_destino_tipo IN ('FO','FO_PAQUETE','FO_EN_USO') THEN
                INSERT INTO inventario_fibra (material_id, stock_actual)
                VALUES (v_rec.material_id, v_rec.cantidad)
                ON CONFLICT (material_id)
                DO UPDATE SET stock_actual = inventario_fibra.stock_actual + EXCLUDED.stock_actual, updated_at = CURRENT_TIMESTAMP;

            ELSE
                RAISE EXCEPTION 'La sección ID % no es un destino válido para movimientos DEVOL.', v_cabecera.destino_almacen_id;
            END IF;
        END IF;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, equipo_origen_id, equipo_destino_id, almacen_origen_id, almacen_destino_id, cantidad, resultado, detalles
        ) VALUES (
            v_cabecera.usuario,
            CASE WHEN v_cabecera.tipo_movimiento = 'TEAMS' THEN 'TEAMS_TRANSFERENCIA' ELSE 'DEVOL_DEVOLUCION' END,
            v_rec.material_id, v_cabecera.origen_equipo_id, v_cabecera.destino_equipo_id, v_origen_id, v_cabecera.destino_almacen_id, v_rec.cantidad,
            'EXITO',
            jsonb_build_object(
                'movimiento_id', p_movimiento_id,
                'observaciones', v_cabecera.observaciones,
                'alerta_stock_minimo', v_alerta_stock,
                'stock_remanente_origen', v_nuevo_stock_origen,
                'stock_minimo_configurado', v_stock_minimo
            )
        );
    END LOOP;

    UPDATE movimientos_cabecera SET estado = 'CONFIRMADO' WHERE id = p_movimiento_id;
END;
$$ LANGUAGE plpgsql;
"""

FN_CANCELAR_NUEVA = """
CREATE OR REPLACE FUNCTION fn_cancelar_movimiento (
    p_movimiento_id INT,
    p_motivo TEXT DEFAULT 'Reversión manual por cancelación'
)
RETURNS VOID AS $$
DECLARE
    v_rec RECORD;
    v_cabecera RECORD;
    v_stock_disponible NUMERIC(12,3);
    v_origen_tipo TEXT;
    v_destino_tipo TEXT;
BEGIN
    -- 1. Bloquear cabecera
    SELECT * INTO v_cabecera
    FROM movimientos_cabecera
    WHERE id = p_movimiento_id AND estado = 'CONFIRMADO'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El movimiento ID % no existe o no se encuentra en estado CONFIRMADO.', p_movimiento_id;
    END IF;

    -- Destino (DEVOL): una vez. Origen (TEAMS): POR LÍNEA (0026).
    SELECT tipo INTO v_destino_tipo
    FROM secciones
    WHERE almacen_id = v_cabecera.destino_almacen_id;

    FOR v_rec IN SELECT md.*,
                        COALESCE(md.origen_almacen_id, v_cabecera.origen_almacen_id) AS origen_efectivo
                 FROM movimientos_detalle md
                 WHERE md.movimiento_id = p_movimiento_id
                 ORDER BY COALESCE(md.origen_almacen_id, v_cabecera.origen_almacen_id), md.material_id LOOP

        -- REVERSIÓN TEAMS (Devuelve el stock de la unidad al origen de CADA línea)
        IF v_cabecera.tipo_movimiento = 'TEAMS' THEN

            SELECT tipo INTO v_origen_tipo
            FROM secciones
            WHERE almacen_id = v_rec.origen_efectivo;

            -- A. Validar y bloquear stock en la unidad destino
            SELECT stock_actual INTO v_stock_disponible
            FROM inventario_equipos
            WHERE equipo_id = v_cabecera.destino_equipo_id AND material_id = v_rec.material_id
            FOR UPDATE;

            IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                RAISE EXCEPTION 'Stock insuficiente en la Unidad destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                    v_cabecera.destino_equipo_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
            END IF;

            -- B. Descontar de la unidad destino
            UPDATE inventario_equipos
            SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.destino_equipo_id AND material_id = v_rec.material_id;

            -- C. Sumar al origen de la línea (GENERAL -> inventario_almacen;
            --    FO/FO_PAQUETE/FO_EN_USO -> inventario_fibra unificado, RF-9)
            IF v_origen_tipo = 'GENERAL' THEN
                UPDATE inventario_almacen
                SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_rec.origen_efectivo AND material_id = v_rec.material_id;

            ELSIF v_origen_tipo IN ('FO','FO_PAQUETE','FO_EN_USO') THEN
                UPDATE inventario_fibra
                SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE material_id = v_rec.material_id;
            END IF;

        -- REVERSIÓN DEVOL (Devuelve el stock del almacén destino a la unidad origen)
        ELSIF v_cabecera.tipo_movimiento = 'DEVOL' THEN

            IF v_destino_tipo = 'GENERAL' THEN
                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_almacen
                WHERE almacen_id = v_cabecera.destino_almacen_id AND material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en el Almacén destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                        v_cabecera.destino_almacen_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                UPDATE inventario_almacen
                SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_cabecera.destino_almacen_id AND material_id = v_rec.material_id;

            ELSIF v_destino_tipo IN ('FO','FO_PAQUETE','FO_EN_USO') THEN
                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_fibra
                WHERE material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en el Almacén destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                        v_cabecera.destino_almacen_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                UPDATE inventario_fibra
                SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE material_id = v_rec.material_id;
            END IF;

            UPDATE inventario_equipos
            SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.origen_equipo_id AND material_id = v_rec.material_id;
        END IF;

        -- 2. Registrar evento de cancelación con metadatos forenses
        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, equipo_origen_id, equipo_destino_id, almacen_origen_id, almacen_destino_id, cantidad, resultado, detalles
        ) VALUES (
            CURRENT_USER,
            'MOVIMIENTO_CANCELADO',
            v_rec.material_id, v_cabecera.origen_equipo_id, v_cabecera.destino_equipo_id, v_rec.origen_efectivo, v_cabecera.destino_almacen_id, v_rec.cantidad,
            'EXITO',
            jsonb_build_object(
                'movimiento_id', p_movimiento_id,
                'motivo_cancelacion', p_motivo,
                'fecha_cancelacion', CURRENT_TIMESTAMP,
                'usuario_autoriza', CURRENT_USER
            )
        );
    END LOOP;

    -- 3. Actualizar estado de cabecera
    UPDATE movimientos_cabecera SET estado = 'CANCELADO' WHERE id = p_movimiento_id;
END;
$$ LANGUAGE plpgsql;
"""

FN_CARGAR_STOCK_INICIAL_NUEVA = """
CREATE OR REPLACE FUNCTION fn_cargar_stock_inicial (
    p_almacen_id INT,
    p_material_id INT,
    p_cantidad NUMERIC(12,3),
    p_motivo TEXT DEFAULT 'Carga inicial de inventario en alta de catálogo'
)
RETURNS VOID AS $$
DECLARE
    v_existe BOOLEAN;
BEGIN
    -- Defensa en profundidad de escala (RF-6): sin redondeo silencioso.
    IF p_cantidad <> ROUND(p_cantidad, 3) THEN
        RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
    END IF;

    IF p_cantidad < 0 THEN
        RAISE EXCEPTION 'La cantidad para carga inicial no puede ser negativa (%).', p_cantidad;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM inventario_almacen
        WHERE almacen_id = p_almacen_id AND material_id = p_material_id
    ) INTO v_existe;

    IF v_existe THEN
        RAISE EXCEPTION 'El material ID % ya posee un registro de inventario activo en el almacén ID %. Para ajustar existencias use fn_ajustar_stock_almacen.',
            p_material_id, p_almacen_id;
    END IF;

    INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual)
    VALUES (p_almacen_id, p_material_id, p_cantidad);

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, almacen_destino_id, cantidad, resultado, detalles
    ) VALUES (
        CURRENT_USER,
        'STOCK_INICIAL',
        p_material_id,
        p_almacen_id,
        p_cantidad,
        'EXITO',
        jsonb_build_object(
            'motivo', p_motivo,
            'fecha', CURRENT_TIMESTAMP,
            'operacion', 'CARGA_INICIAL_ALTA'
        )
    );
END;
$$ LANGUAGE plpgsql;
"""

FN_CARGAR_STOCK_INICIAL_FIBRA_NUEVA = """
CREATE OR REPLACE FUNCTION fn_cargar_stock_inicial_fibra (
    p_material_id INT,
    p_cantidad NUMERIC(12,3),
    p_motivo TEXT DEFAULT 'Carga inicial de inventario FO'
)
RETURNS VOID AS $$
DECLARE
    v_existe BOOLEAN;
BEGIN
    -- Defensa en profundidad de escala (RF-6): sin redondeo silencioso.
    IF p_cantidad <> ROUND(p_cantidad, 3) THEN
        RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
    END IF;

    IF p_cantidad < 0 THEN
        RAISE EXCEPTION 'La cantidad para carga inicial no puede ser negativa (%).', p_cantidad;
    END IF;

    -- Inventario FO unificado (0027): la PK deja de ser (modulo, material_id),
    -- por lo que el duplicado se valida explícitamente por material.
    SELECT EXISTS (
        SELECT 1
        FROM inventario_fibra
        WHERE material_id = p_material_id
    ) INTO v_existe;

    IF v_existe THEN
        RAISE EXCEPTION 'El material ID % ya posee un registro de inventario activo en Inventario FO. Para ajustar existencias use fn_ajustar_stock_fibra.',
            p_material_id;
    END IF;

    INSERT INTO inventario_fibra (material_id, stock_actual)
    VALUES (p_material_id, p_cantidad);

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, cantidad, resultado, detalles
    ) VALUES (
        CURRENT_USER,
        'STOCK_INICIAL_FO',
        p_material_id,
        p_cantidad,
        'EXITO',
        jsonb_build_object(
            'motivo', p_motivo,
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;
"""

FN_AJUSTAR_STOCK_ALMACEN_NUEVA = """
CREATE OR REPLACE FUNCTION fn_ajustar_stock_almacen (
    p_almacen_id INT,
    p_material_id INT,
    p_nuevo_stock NUMERIC(12,3),
    p_motivo TEXT
)
RETURNS VOID AS $$
DECLARE
    v_stock_anterior NUMERIC(12,3);
    v_diferencia NUMERIC(12,3);
BEGIN
    -- Defensa en profundidad de escala (RF-6): sin redondeo silencioso.
    IF p_nuevo_stock <> ROUND(p_nuevo_stock, 3) THEN
        RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
    END IF;

    IF p_nuevo_stock < 0 THEN
        RAISE EXCEPTION 'El stock final ajustado no puede ser negativo (%).', p_nuevo_stock;
    END IF;

    -- Ergonomía `justificacion_opcional` (REQ-ERG-003/005): el motivo es
    -- OPCIONAL — null o vacío se acepta y se audita tal como llega.

    -- Bloqueo FOR UPDATE para prevenir condiciones de carrera durante la lectura del stock actual
    SELECT stock_actual INTO v_stock_anterior
    FROM inventario_almacen
    WHERE almacen_id = p_almacen_id AND material_id = p_material_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el almacén ID %. Realice primero la carga inicial.',
            p_material_id, p_almacen_id;
    END IF;

    v_diferencia := p_nuevo_stock - v_stock_anterior;

    -- Actualización de inventario
    UPDATE inventario_almacen
    SET stock_actual = p_nuevo_stock, updated_at = CURRENT_TIMESTAMP
    WHERE almacen_id = p_almacen_id AND material_id = p_material_id;

    -- Auditoría del ajuste con diferencial calculado
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, almacen_destino_id, cantidad, resultado, detalles
    ) VALUES (
        CURRENT_USER,
        'AJUSTE_INVENTARIO',
        p_material_id,
        p_almacen_id,
        p_nuevo_stock,
        'EXITO',
        jsonb_build_object(
            'stock_anterior', v_stock_anterior,
            'stock_nuevo', p_nuevo_stock,
            'diferencial', v_diferencia,
            'motivo', p_motivo,
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;
"""

FN_AJUSTAR_STOCK_FIBRA_NUEVA = """
CREATE OR REPLACE FUNCTION fn_ajustar_stock_fibra (
    p_material_id INT,
    p_nuevo_stock NUMERIC(12,3),
    p_motivo TEXT
)
RETURNS VOID AS $$
DECLARE
    v_stock_anterior NUMERIC(12,3);
    v_diferencia NUMERIC(12,3);
BEGIN
    -- Defensa en profundidad de escala (RF-6): sin redondeo silencioso.
    IF p_nuevo_stock <> ROUND(p_nuevo_stock, 3) THEN
        RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
    END IF;

    -- Ergonomía `justificacion_opcional` (REQ-ERG-004/005): el motivo es
    -- OPCIONAL — null o vacío se acepta y se audita tal como llega.

    IF p_nuevo_stock < 0 THEN
        RAISE EXCEPTION 'El stock final ajustado no puede ser negativo (%).', p_nuevo_stock;
    END IF;

    -- Bloqueo FOR UPDATE: cero condiciones de carrera sobre inventario_fibra.
    -- Inventario FO unificado (0027): resolución por material_id SIN modulo.
    SELECT stock_actual INTO v_stock_anterior
    FROM inventario_fibra
    WHERE material_id = p_material_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en Inventario FO. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
            p_material_id;
    END IF;

    v_diferencia := p_nuevo_stock - v_stock_anterior;

    UPDATE inventario_fibra
    SET stock_actual = p_nuevo_stock, updated_at = CURRENT_TIMESTAMP
    WHERE material_id = p_material_id;

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, cantidad, resultado, detalles
    ) VALUES (
        CURRENT_USER,
        'AJUSTE_INVENTARIO_FO',
        p_material_id,
        p_nuevo_stock,
        'EXITO',
        jsonb_build_object(
            'stock_anterior', v_stock_anterior,
            'stock_nuevo', p_nuevo_stock,
            'diferencial', v_diferencia,
            'motivo', p_motivo,
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;
"""

FN_AJUSTAR_STOCK_GENERAL_NUEVA = """
CREATE OR REPLACE FUNCTION fn_ajustar_stock_general (
    p_material_id INT,
    p_nuevo_stock NUMERIC(12,3),
    p_motivo TEXT
)
RETURNS VOID AS $$
DECLARE
    v_almacen_id INT;
    v_conteo INT;
BEGIN
    -- Defensa en profundidad de escala (RF-6): sin redondeo silencioso.
    IF p_nuevo_stock <> ROUND(p_nuevo_stock, 3) THEN
        RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
    END IF;

    -- Localiza la fila de inventario_almacen del material en la sección
    -- ACTIVA de tipo GENERAL (contrato REQ-API-002/003: edición de stock
    -- desde Inventario General).
    SELECT COUNT(*) INTO v_conteo
    FROM inventario_almacen ia
    JOIN secciones s ON s.almacen_id = ia.almacen_id
    WHERE ia.material_id = p_material_id
      AND s.tipo = 'GENERAL'
      AND s.is_active = TRUE;

    IF v_conteo = 0 THEN
        RAISE EXCEPTION 'No se encontró inventario del material ID % en la sección activa de Inventario General. Realice primero la carga inicial.',
            p_material_id;
    END IF;

    IF v_conteo > 1 THEN
        RAISE EXCEPTION 'Existen % filas de inventario del material ID % en secciones activas de tipo GENERAL; no es posible determinar un destino único para el ajuste.',
            v_conteo, p_material_id;
    END IF;

    SELECT ia.almacen_id INTO v_almacen_id
    FROM inventario_almacen ia
    JOIN secciones s ON s.almacen_id = ia.almacen_id
    WHERE ia.material_id = p_material_id
      AND s.tipo = 'GENERAL'
      AND s.is_active = TRUE
    LIMIT 1
    FOR UPDATE OF ia;

    -- Delegación completa: validación de motivo, no-negatividad, bloqueo
    -- FOR UPDATE, diferencial y auditoría viven en fn_ajustar_stock_almacen.
    PERFORM fn_ajustar_stock_almacen(v_almacen_id, p_material_id, p_nuevo_stock, p_motivo);
END;
$$ LANGUAGE plpgsql;
"""

FN_ELIMINAR_INVENTARIO_FIBRA_NUEVA = """
CREATE OR REPLACE FUNCTION fn_eliminar_inventario_fibra (
    p_material_id INT,
    p_motivo TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_stock_anterior NUMERIC(12,3);
BEGIN
    -- Bloqueo FOR UPDATE: cero condiciones de carrera sobre inventario_fibra.
    -- Inventario FO unificado (0027): resolución por material_id SIN modulo.
    SELECT stock_actual INTO v_stock_anterior
    FROM inventario_fibra
    WHERE material_id = p_material_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en Inventario FO. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
            p_material_id;
    END IF;

    -- REQ-DEL-004: con existencias, el motivo es obligatorio y no vacío
    -- (RAISE -> 422 vía el mapeo "motivo" de transaccional).
    IF v_stock_anterior > 0 AND (p_motivo IS NULL OR TRIM(p_motivo) = '') THEN
        RAISE EXCEPTION 'Es obligatorio proporcionar un motivo para eliminar inventario FO con existencias (material ID %, stock %).',
            p_material_id, v_stock_anterior;
    END IF;

    -- Eliminación física de la fila del material (REQ-DEL-003:
    -- catálogo e Inventario General intactos).
    DELETE FROM inventario_fibra
    WHERE material_id = p_material_id;

    -- Auditoría forense con snapshot completo (Constitution 6.2):
    -- el stock eliminado queda reconstruible en el ledger inmutable.
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, cantidad, resultado, detalles
    ) VALUES (
        COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER),
        'ELIMINACION_FO',
        p_material_id,
        v_stock_anterior,
        'EXITO',
        jsonb_build_object(
            'material_id', p_material_id,
            'stock_eliminado', v_stock_anterior,
            'motivo', p_motivo,
            'usuario', COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER),
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;
"""

FN_SUMAR_CANTIDAD_NUEVA = """
CREATE OR REPLACE FUNCTION fn_sumar_cantidad (
    p_destino TEXT,
    p_material_id INT,
    p_cantidad NUMERIC(12,3),
    p_usuario TEXT,
    p_clave_idempotencia TEXT DEFAULT NULL
)
RETURNS NUMERIC(12,3) AS $$
DECLARE
    v_actor TEXT;
    v_guard TEXT;
    v_guard_actor TEXT;
    v_almacen_id INT;
    v_conteo INT;
    v_stock_anterior NUMERIC(12,3);
    v_nuevo_stock NUMERIC(12,3);
BEGIN
    v_actor := COALESCE(NULLIF(p_usuario, ''),
                        NULLIF(current_setting('app.actor', true), ''),
                        CURRENT_USER);

    -- 0. Guarda de idempotencia (REQ-P2-INV-007): la fila vive en la MISMA
    --    transacción; un fallo posterior la elimina con el rollback.
    IF p_clave_idempotencia IS NOT NULL THEN
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave, actor)
        VALUES ('SUMA_CANTIDAD', p_clave_idempotencia, v_actor)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            SELECT actor INTO v_guard_actor
            FROM operaciones_idempotencia
            WHERE tipo_operacion = 'SUMA_CANTIDAD' AND clave = p_clave_idempotencia;

            IF v_guard_actor IS DISTINCT FROM v_actor THEN
                RAISE EXCEPTION 'La clave de idempotencia ya fue utilizada por otro actor.';
            END IF;

            RAISE EXCEPTION 'La operación SUMA_CANTIDAD ya fue ejecutada para esta clave de idempotencia.';
        END IF;
    END IF;

    -- Defensa en profundidad de escala (RF-6): sin redondeo silencioso.
    IF p_cantidad <> ROUND(p_cantidad, 3) THEN
        RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
    END IF;

    -- 1. Validaciones de dominio (REQ-P2-INV-001).
    IF p_destino IS NULL OR p_destino NOT IN ('GENERAL','FO') THEN
        RAISE EXCEPTION 'El destino de +Cantidad debe ser GENERAL o FO (recibido: %).', p_destino;
    END IF;

    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        RAISE EXCEPTION 'La cantidad a sumar debe ser mayor que cero (recibida: %).', p_cantidad;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM catalogo_materiales
        WHERE id_lista = p_material_id AND is_active = TRUE
    ) THEN
        RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', p_material_id;
    END IF;

    -- 2. Mutación atómica con bloqueo FOR UPDATE + auditoría inmutable.
    IF p_destino = 'GENERAL' THEN
        -- Resolución de la sección GENERAL activa (espejo de
        -- fn_ajustar_stock_general): 0 filas -> 404; >1 -> conflicto.
        SELECT COUNT(*) INTO v_conteo
        FROM inventario_almacen ia
        JOIN secciones s ON s.almacen_id = ia.almacen_id
        WHERE ia.material_id = p_material_id
          AND s.tipo = 'GENERAL' AND s.is_active = TRUE;

        IF v_conteo = 0 THEN
            RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en la sección GENERAL activa. Realice primero la carga inicial.',
                p_material_id;
        END IF;

        IF v_conteo > 1 THEN
            RAISE EXCEPTION 'Existen % filas de inventario del material ID % en secciones GENERAL activas; no es posible determinar un destino único.',
                v_conteo, p_material_id;
        END IF;

        SELECT ia.almacen_id, ia.stock_actual INTO v_almacen_id, v_stock_anterior
        FROM inventario_almacen ia
        JOIN secciones s ON s.almacen_id = ia.almacen_id
        WHERE ia.material_id = p_material_id
          AND s.tipo = 'GENERAL' AND s.is_active = TRUE
        LIMIT 1
        FOR UPDATE OF ia;

        v_nuevo_stock := v_stock_anterior + p_cantidad;

        UPDATE inventario_almacen
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE almacen_id = v_almacen_id AND material_id = p_material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, almacen_destino_id, cantidad, resultado, detalles
        ) VALUES (
            v_actor,
            'SUMA_CANTIDAD',
            p_material_id,
            v_almacen_id,
            p_cantidad,
            'EXITO',
            jsonb_build_object(
                'destino', 'GENERAL',
                'almacen_id', v_almacen_id,
                'stock_anterior', v_stock_anterior,
                'stock_nuevo', v_nuevo_stock,
                'diferencial', p_cantidad,
                'usuario', v_actor,                'fecha', CURRENT_TIMESTAMP
            )
        );

    ELSE -- p_destino = 'FO'
        -- Inventario FO unificado (0027): resolución por material_id SIN modulo.
        SELECT stock_actual INTO v_stock_anterior
        FROM inventario_fibra
        WHERE material_id = p_material_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en Inventario FO. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
                p_material_id;
        END IF;

        v_nuevo_stock := v_stock_anterior + p_cantidad;

        UPDATE inventario_fibra
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE material_id = p_material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, cantidad, resultado, detalles
        ) VALUES (
            v_actor,
            'SUMA_CANTIDAD',
            p_material_id,
            p_cantidad,
            'EXITO',
            jsonb_build_object(
                'destino', 'FO',
                'stock_anterior', v_stock_anterior,
                'stock_nuevo', v_nuevo_stock,
                'diferencial', p_cantidad,
                'usuario', v_actor,                'fecha', CURRENT_TIMESTAMP
            )
        );
    END IF;

    -- 3. Persistir el resultado para retornos de reenvío (REQ-P2-INV-007).
    IF p_clave_idempotencia IS NOT NULL THEN
        UPDATE operaciones_idempotencia
        SET resultado = jsonb_build_object(
            'stock_nuevo', v_nuevo_stock,
            'destino', p_destino
        )
        WHERE tipo_operacion = 'SUMA_CANTIDAD' AND clave = p_clave_idempotencia;
    END IF;

    RETURN v_nuevo_stock;
END;
$$ LANGUAGE plpgsql;
"""

FN_MOVER_MATERIAL_NUEVA = """
CREATE OR REPLACE FUNCTION fn_mover_material (
    p_origen TEXT,
    p_destino TEXT,
    p_material_id INT,
    p_cantidad NUMERIC(12,3),
    p_usuario TEXT,
    p_clave_idempotencia TEXT DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_actor TEXT;
    v_guard TEXT;
    v_guard_actor TEXT;
    v_conteo INT;
    v_almacen_general INT;
    v_stock_origen_anterior NUMERIC(12,3);  -- NULL = fila no leída / aún sin bloquear
    v_stock_destino_anterior NUMERIC(12,3); -- NULL = fila destino inexistente (modelo disperso)
    v_nuevo_stock_origen NUMERIC(12,3);
    v_nuevo_stock_destino NUMERIC(12,3);
    v_stock_fibra NUMERIC(12,3);
BEGIN
    v_actor := COALESCE(NULLIF(p_usuario, ''),
                        NULLIF(current_setting('app.actor', true), ''),
                        CURRENT_USER);

    -- 0. Guarda de idempotencia (REQ-P2-INV-007), misma transacción.
    IF p_clave_idempotencia IS NOT NULL THEN
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave, actor)
        VALUES ('MOVIMIENTO_INVENTARIO', p_clave_idempotencia, v_actor)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            SELECT actor INTO v_guard_actor
            FROM operaciones_idempotencia
            WHERE tipo_operacion = 'MOVIMIENTO_INVENTARIO' AND clave = p_clave_idempotencia;

            IF v_guard_actor IS DISTINCT FROM v_actor THEN
                RAISE EXCEPTION 'La clave de idempotencia ya fue utilizada por otro actor.';
            END IF;

            RAISE EXCEPTION 'La operación MOVIMIENTO_INVENTARIO ya fue ejecutada para esta clave de idempotencia.';
        END IF;
    END IF;

    -- Defensa en profundidad de escala (RF-6): sin redondeo silencioso.
    IF p_cantidad <> ROUND(p_cantidad, 3) THEN
        RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
    END IF;

    -- 1. Validaciones de parámetros.
    IF p_origen IS NULL OR p_origen NOT IN ('GENERAL','FO') THEN
        RAISE EXCEPTION 'El origen del movimiento debe ser GENERAL o FO (recibido: %).', p_origen;
    END IF;

    IF p_destino IS NULL OR p_destino NOT IN ('GENERAL','FO') THEN
        RAISE EXCEPTION 'El destino del movimiento debe ser GENERAL o FO (recibido: %).', p_destino;
    END IF;

    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        RAISE EXCEPTION 'La cantidad a mover debe ser mayor que cero (recibida: %).', p_cantidad;
    END IF;

    -- 2. REQ-P2-INV-004: destino igual al origen (0027: comparación por
    --    tipo de inventario, ya sin módulos FO).
    IF p_origen = p_destino THEN
        RAISE EXCEPTION 'El destino del movimiento no puede ser igual al origen (%).', p_origen;
    END IF;

    -- 3. Material activo. Coherencia de U.M./catálogo entre extremos:
    --    GARANTIZADA POR CONSTRUCCIÓN (mismo id_lista en ambos
    --    inventarios; u_m es atributo del catálogo, no del inventario).
    IF NOT EXISTS (
        SELECT 1 FROM catalogo_materiales
        WHERE id_lista = p_material_id AND is_active = TRUE
    ) THEN
        RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', p_material_id;
    END IF;

    -- 4. Bloqueo DETERMINISTA (cero deadlocks): primero la fila GENERAL
    --    (si participa) y después la fila FO (única por material desde
    --    0027). Movimientos opuestos concurrentes sobre el mismo material
    --    serializan en este mismo orden.

    -- 4.a Lado GENERAL (origen o destino): resolución de la sección
    --     GENERAL activa independiente del material.
    IF p_origen = 'GENERAL' OR p_destino = 'GENERAL' THEN
        SELECT COUNT(*) INTO v_conteo
        FROM secciones
        WHERE tipo = 'GENERAL' AND is_active = TRUE;

        IF v_conteo = 0 THEN
            RAISE EXCEPTION 'No existe una sección GENERAL activa para el movimiento de inventario.';
        END IF;

        IF v_conteo > 1 THEN
            RAISE EXCEPTION 'Existen % secciones GENERAL activas; no es posible determinar un destino único para el movimiento.',
                v_conteo;
        END IF;

        SELECT almacen_id INTO v_almacen_general
        FROM secciones
        WHERE tipo = 'GENERAL' AND is_active = TRUE
        ORDER BY almacen_id
        LIMIT 1;

        IF p_origen = 'GENERAL' THEN
            SELECT stock_actual INTO v_stock_origen_anterior
            FROM inventario_almacen
            WHERE almacen_id = v_almacen_general AND material_id = p_material_id
            FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en la sección GENERAL activa. Realice primero la carga inicial.',
                    p_material_id;
            END IF;
        ELSE
            -- GENERAL es destino: la fila puede no existir aún (modelo
            -- disperso); se crea en el UPSERT solo con stock > 0.
            SELECT stock_actual INTO v_stock_destino_anterior
            FROM inventario_almacen
            WHERE almacen_id = v_almacen_general AND material_id = p_material_id
            FOR UPDATE;
        END IF;
    END IF;

    -- 4.b Lado FO (origen o destino): bloqueo de la fila única del
    --     material (0027: sin modulo).
    IF p_origen = 'FO' OR p_destino = 'FO' THEN
        SELECT stock_actual INTO v_stock_fibra
        FROM inventario_fibra
        WHERE material_id = p_material_id
        FOR UPDATE;

        IF p_origen = 'FO' THEN
            IF v_stock_fibra IS NULL THEN
                RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en Inventario FO. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
                    p_material_id;
            END IF;
            v_stock_origen_anterior := v_stock_fibra;
        ELSE
            -- FO es destino: la fila puede no existir aún (modelo disperso).
            v_stock_destino_anterior := COALESCE(v_stock_fibra, 0);
        END IF;
    END IF;

    -- 5. Validación de stock del origen (REQ-P2-INV-004).
    IF COALESCE(v_stock_origen_anterior, 0) < p_cantidad THEN
        RAISE EXCEPTION 'Stock insuficiente en Origen (%) para el material ID LISTA %. Disponible: %, Solicitado: %',
            p_origen, p_material_id, COALESCE(v_stock_origen_anterior, 0), p_cantidad;
    END IF;

    v_nuevo_stock_origen := COALESCE(v_stock_origen_anterior, 0) - p_cantidad;
    v_nuevo_stock_destino := COALESCE(v_stock_destino_anterior, 0) + p_cantidad;

    -- 6. Descuento del origen (la fila SE CONSERVA aunque llegue a 0:
    --    decisión de semántica dispersa documentada en el docstring).
    IF p_origen = 'GENERAL' THEN
        UPDATE inventario_almacen
        SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
        WHERE almacen_id = v_almacen_general AND material_id = p_material_id;
    ELSE
        UPDATE inventario_fibra
        SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
        WHERE material_id = p_material_id;
    END IF;

    -- 7. Acreditación del destino: la fila se crea SOLO con stock > 0
    --    (p_cantidad > 0 garantizado); si existe, el UPSERT acumula.
    --    El stock del destino se RELEE tras el UPSERT (fila bloqueada por
    --    nuestra propia escritura) para que el snapshot de auditoría y el
    --    retorno sean exactos bajo concurrencia.
    IF p_destino = 'GENERAL' THEN
        INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual)
        VALUES (v_almacen_general, p_material_id, p_cantidad)
        ON CONFLICT (almacen_id, material_id)
        DO UPDATE SET stock_actual = inventario_almacen.stock_actual + EXCLUDED.stock_actual,
                      updated_at = CURRENT_TIMESTAMP;

        SELECT stock_actual INTO v_nuevo_stock_destino
        FROM inventario_almacen
        WHERE almacen_id = v_almacen_general AND material_id = p_material_id;
    ELSE
        INSERT INTO inventario_fibra (material_id, stock_actual)
        VALUES (p_material_id, p_cantidad)
        ON CONFLICT (material_id)
        DO UPDATE SET stock_actual = inventario_fibra.stock_actual + EXCLUDED.stock_actual,
                      updated_at = CURRENT_TIMESTAMP;

        SELECT stock_actual INTO v_nuevo_stock_destino
        FROM inventario_fibra
        WHERE material_id = p_material_id;
    END IF;

    -- 8. Auditoría inmutable con snapshot completo (REQ-P2-INV-006).
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, cantidad, resultado, detalles
    ) VALUES (
        v_actor,
        'MOVIMIENTO_INVENTARIO',
        p_material_id,
        p_cantidad,
        'EXITO',
        jsonb_build_object(
            'origen', jsonb_build_object(
                'tipo', p_origen,
                'almacen_id', CASE WHEN p_origen = 'GENERAL' THEN v_almacen_general ELSE NULL END
            ),
            'destino', jsonb_build_object(
                'tipo', p_destino,
                'almacen_id', CASE WHEN p_destino = 'GENERAL' THEN v_almacen_general ELSE NULL END
            ),
            'stock_origen_anterior', COALESCE(v_stock_origen_anterior, 0),
            'stock_origen_despues', v_nuevo_stock_origen,
            'stock_destino_anterior', COALESCE(v_stock_destino_anterior, 0),
            'stock_destino_despues', v_nuevo_stock_destino,
            'usuario', v_actor,            'fecha', CURRENT_TIMESTAMP
        )
    );

    -- 9. Persistir el resultado para retornos de reenvío (REQ-P2-INV-007).
    IF p_clave_idempotencia IS NOT NULL THEN
        UPDATE operaciones_idempotencia
        SET resultado = jsonb_build_object(
            'stock_origen', v_nuevo_stock_origen,
            'stock_destino', v_nuevo_stock_destino,
            'origen', p_origen,
            'destino', p_destino
        )
        WHERE tipo_operacion = 'MOVIMIENTO_INVENTARIO' AND clave = p_clave_idempotencia;
    END IF;

    RETURN jsonb_build_object(
        'stock_origen', v_nuevo_stock_origen,
        'stock_destino', v_nuevo_stock_destino
    );
END;
$$ LANGUAGE plpgsql;
"""

FN_AGREGAR_TODO_NUEVA = """
CREATE OR REPLACE FUNCTION fn_agregar_todo_seguimiento (
    p_seguimiento_id INT,
    p_equipo_id INT,
    p_usuario TEXT,
    p_clave_idempotencia TEXT DEFAULT NULL
)
RETURNS INT AS $$
DECLARE
    v_actor TEXT;
    v_guard TEXT;
    v_guard_actor TEXT;
    v_seguimiento RECORD;
    v_inv RECORD;
    v_agregadas INT := 0;
    v_unidades NUMERIC(12,3) := 0;
BEGIN
    v_actor := COALESCE(NULLIF(p_usuario, ''),
                        NULLIF(current_setting('app.actor', true), ''),
                        CURRENT_USER);

    -- 0. Guarda de idempotencia (REQ-P2-INV-007), misma transacción.
    IF p_clave_idempotencia IS NOT NULL THEN
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave, actor)
        VALUES ('AGREGAR_TODO', p_clave_idempotencia, v_actor)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            SELECT actor INTO v_guard_actor
            FROM operaciones_idempotencia
            WHERE tipo_operacion = 'AGREGAR_TODO' AND clave = p_clave_idempotencia;

            IF v_guard_actor IS DISTINCT FROM v_actor THEN
                RAISE EXCEPTION 'La clave de idempotencia ya fue utilizada por otro actor.';
            END IF;

            RAISE EXCEPTION 'La operación AGREGAR_TODO ya fue ejecutada para esta clave de idempotencia.';
        END IF;
    END IF;

    -- 1. Cabecera: existencia, pertenencia al equipo y estado ABIERTA.
    --    FOR UPDATE serializa con fn_cerrar_seguimiento y con dobles
    --    invocaciones concurrentes (REQ-P2-CON-004).
    SELECT * INTO v_seguimiento
    FROM seguimientos
    WHERE id = p_seguimiento_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Seguimiento ID % no encontrado.', p_seguimiento_id;
    END IF;

    IF v_seguimiento.equipo_id <> p_equipo_id THEN
        RAISE EXCEPTION 'El seguimiento ID % no pertenece a la unidad ID %.',
            p_seguimiento_id, p_equipo_id;
    END IF;

    IF v_seguimiento.estado <> 'ABIERTA' THEN
        RAISE EXCEPTION 'El seguimiento ID % no se encuentra en estado ABIERTA.',
            p_seguimiento_id;
    END IF;

    -- 2. Líneas del inventario del equipo con existencias reales, leídas
    --    BAJO bloqueo FOR UPDATE en orden determinista por material_id
    --    (cero condiciones de carrera con fn_cerrar_seguimiento y
    --    fn_procesar_movimiento, que bloquean en el mismo orden).
    FOR v_inv IN
        SELECT material_id, stock_actual
        FROM inventario_equipos
        WHERE equipo_id = p_equipo_id AND stock_actual > 0
        ORDER BY material_id
        FOR UPDATE
    LOOP
        -- 3. Inserción idempotente: ON CONFLICT DO NOTHING — una doble
        --    invocación no duplica líneas ni altera las ya presentes.
        INSERT INTO seguimiento_items (seguimiento_id, material_id, cantidad_tomada)
        VALUES (p_seguimiento_id, v_inv.material_id, v_inv.stock_actual)
        ON CONFLICT (seguimiento_id, material_id) DO NOTHING;

        IF FOUND THEN
            v_agregadas := v_agregadas + 1;
            v_unidades := v_unidades + v_inv.stock_actual;
        END IF;
    END LOOP;

    -- 4. Evento de auditoría SOLO si hubo líneas nuevas: el ledger no
    --    duplica eventos en una segunda invocación (REQ-P2-CON-004).
    IF v_agregadas > 0 THEN
        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, equipo_destino_id, resultado, detalles
        ) VALUES (
            v_actor,
            'AGREGAR_TODO',
            p_equipo_id,
            'EXITO',
            jsonb_build_object(
                'seguimiento_id', p_seguimiento_id,
                'equipo_id', p_equipo_id,
                'lineas_agregadas', v_agregadas,
                'unidades_agregadas', v_unidades,
                'usuario', v_actor,                'fecha', CURRENT_TIMESTAMP
            )
        );
    END IF;

    -- 5. Persistir el resultado para retornos de reenvío (REQ-P2-INV-007).
    IF p_clave_idempotencia IS NOT NULL THEN
        UPDATE operaciones_idempotencia
        SET resultado = jsonb_build_object(
            'lineas_agregadas', v_agregadas,
            'seguimiento_id', p_seguimiento_id
        )
        WHERE tipo_operacion = 'AGREGAR_TODO' AND clave = p_clave_idempotencia;
    END IF;

    RETURN v_agregadas;
END;
$$ LANGUAGE plpgsql;
"""

FN_CREAR_SEGUIMIENTO_NUEVA = """
CREATE OR REPLACE FUNCTION fn_crear_seguimiento (
    p_equipo_id INT,
    p_observaciones TEXT,
    p_items JSONB,
    p_usuario TEXT
)
RETURNS INT AS $$
DECLARE
    v_id INT;
    v_existe BOOLEAN;
    v_item RECORD;
    v_visto INT[] := '{}';
BEGIN
    -- 1. El equipo debe existir y estar activo.
    SELECT EXISTS (
        SELECT 1 FROM equipos WHERE equipo_id = p_equipo_id AND is_active = TRUE
    ) INTO v_existe;

    IF NOT v_existe THEN
        RAISE EXCEPTION 'La unidad ID % no existe o se encuentra inactiva.', p_equipo_id;
    END IF;

    -- 2. La lista del seguimiento debe ser un arreglo JSON no vacío.
    IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
        RAISE EXCEPTION 'La lista de seguimiento debe contener al menos un material.';
    END IF;

    -- 3. Validación de cada línea: material activo, cantidad positiva y
    --    cero duplicados dentro del payload. 0027: cantidades decimales
    --    NUMERIC(12,3); sobre-precisión -> RAISE (RF-6, sin redondeo
    --    silencioso).
    FOR v_item IN
        SELECT (elem->>'material_id')::INT AS material_id,
               (elem->>'cantidad_tomada')::NUMERIC AS cantidad_tomada
        FROM jsonb_array_elements(p_items) AS elem
    LOOP
        IF v_item.material_id IS NULL THEN
            RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', v_item.material_id;
        END IF;

        IF v_item.material_id = ANY(v_visto) THEN
            RAISE EXCEPTION 'Material ID LISTA % duplicado en la lista de seguimiento.', v_item.material_id;
        END IF;
        v_visto := array_append(v_visto, v_item.material_id);

        IF v_item.cantidad_tomada <> ROUND(v_item.cantidad_tomada, 3) THEN
            RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
        END IF;

        IF v_item.cantidad_tomada IS NULL OR v_item.cantidad_tomada <= 0 THEN
            RAISE EXCEPTION 'Cantidad tomada inválida para el material ID LISTA % (debe ser mayor a 0).', v_item.material_id;
        END IF;

        SELECT EXISTS (
            SELECT 1 FROM catalogo_materiales
            WHERE id_lista = v_item.material_id AND is_active = TRUE
        ) INTO v_existe;

        IF NOT v_existe THEN
            RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', v_item.material_id;
        END IF;
    END LOOP;

    -- 4. Un solo seguimiento abierto por equipo (bloqueo de filas sobre la
    --    ventana del equipo; el índice único parcial es la red de seguridad).
    PERFORM 1
    FROM seguimientos
    WHERE equipo_id = p_equipo_id AND estado = 'ABIERTA'
    FOR UPDATE;

    IF FOUND THEN
        RAISE EXCEPTION 'La unidad ID % ya posee un seguimiento abierto.', p_equipo_id;
    END IF;

    -- 5. Cabecera (estado por defecto ABIERTA) e items.
    INSERT INTO seguimientos (equipo_id, fecha, observaciones, usuario)
    VALUES (p_equipo_id, CURRENT_DATE, p_observaciones, p_usuario)
    RETURNING id INTO v_id;

    FOR v_item IN
        SELECT (elem->>'material_id')::INT AS material_id,
               (elem->>'cantidad_tomada')::NUMERIC AS cantidad_tomada
        FROM jsonb_array_elements(p_items) AS elem
    LOOP
        INSERT INTO seguimiento_items (seguimiento_id, material_id, cantidad_tomada)
        VALUES (v_id, v_item.material_id, v_item.cantidad_tomada);
    END LOOP;

    -- 6. Evento de auditoría de apertura (nomenclatura nueva).
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, equipo_destino_id, resultado, detalles
    ) VALUES (
        p_usuario,
        'SEGUIMIENTO_CREADO',
        p_equipo_id,
        'EXITO',
        jsonb_build_object(
            'seguimiento_id', v_id,
            'fecha', CURRENT_DATE,
            'cantidad_items', jsonb_array_length(p_items),
            'observaciones', p_observaciones
        )
    );

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;
"""

FN_CERRAR_SEGUIMIENTO_NUEVA = """
CREATE OR REPLACE FUNCTION fn_cerrar_seguimiento (
    p_seguimiento_id INT,
    p_consumidos JSONB,
    p_usuario TEXT,
    p_observaciones_cierre TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_seguimiento RECORD;
    v_item RECORD;
    v_linea RECORD;
    v_fila_inv RECORD;
    v_vistos INT[] := '{}';
    v_material_ids INT[] := '{}';
    v_tomadas_map JSONB := '{}'::jsonb;
    v_consumidos_map JSONB := '{}'::jsonb;
    v_tomada NUMERIC(12,3);
    v_consumido NUMERIC(12,3);
    v_stock_actual NUMERIC(12,3);
    v_nuevo_stock NUMERIC(12,3);
    v_snapshot_acta JSONB;
    v_acta_id INT;
BEGIN
    -- 1. Bloquear la cabecera SOLO si está ABIERTA.
    SELECT * INTO v_seguimiento
    FROM seguimientos
    WHERE id = p_seguimiento_id AND estado = 'ABIERTA'
    FOR UPDATE;

    IF NOT FOUND THEN
        IF EXISTS (SELECT 1 FROM seguimientos WHERE id = p_seguimiento_id) THEN
            RAISE EXCEPTION 'El seguimiento ID % no se encuentra en estado ABIERTA.', p_seguimiento_id;
        ELSE
            RAISE EXCEPTION 'Seguimiento ID % no encontrado.', p_seguimiento_id;
        END IF;
    END IF;

    -- 2. Items del seguimiento ORDENADOS por material_id (orden de bloqueo
    --    determinista).
    FOR v_item IN
        SELECT si.id, si.material_id, si.cantidad_tomada
        FROM seguimiento_items si
        WHERE si.seguimiento_id = p_seguimiento_id
        ORDER BY si.material_id
        FOR UPDATE
    LOOP
        v_material_ids := array_append(v_material_ids, v_item.material_id);
        v_tomadas_map := v_tomadas_map || jsonb_build_object(
            v_item.material_id::text, v_item.cantidad_tomada
        );
    END LOOP;

    -- 3. Validar el payload de consumidos (arreglo JSON obligatorio).
    IF p_consumidos IS NULL OR jsonb_typeof(p_consumidos) <> 'array' THEN
        RAISE EXCEPTION 'El payload de consumidos debe ser un arreglo JSON.';
    END IF;

    FOR v_linea IN
        SELECT (elem->>'material_id')::INT AS material_id,
               (elem->>'cantidad_consumida')::NUMERIC AS cantidad_consumida
        FROM jsonb_array_elements(p_consumidos) AS elem
    LOOP
        IF v_linea.material_id = ANY(v_vistos) THEN
            RAISE EXCEPTION 'Material ID LISTA % duplicado en la lista de consumidos.', v_linea.material_id;
        END IF;
        v_vistos := array_append(v_vistos, v_linea.material_id);

        IF v_linea.material_id IS NULL OR NOT (v_tomadas_map ? v_linea.material_id::text) THEN
            RAISE EXCEPTION 'Material ID LISTA % no pertenece a este seguimiento.', v_linea.material_id;
        END IF;

        v_tomada := (v_tomadas_map->>v_linea.material_id::text)::NUMERIC;

        -- 0027: sobre-precisión -> RAISE (RF-6, sin redondeo silencioso).
        IF v_linea.cantidad_consumida <> ROUND(v_linea.cantidad_consumida, 3) THEN
            RAISE EXCEPTION 'La cantidad admite máximo 3 decimales.';
        END IF;

        IF v_linea.cantidad_consumida IS NULL OR v_linea.cantidad_consumida < 0
           OR v_linea.cantidad_consumida > v_tomada THEN
            RAISE EXCEPTION 'Consumo inválido para el material ID LISTA % (máximo %).',
                v_linea.material_id, v_tomada;
        END IF;

        v_consumidos_map := v_consumidos_map || jsonb_build_object(
            v_linea.material_id::text, v_linea.cantidad_consumida
        );
    END LOOP;

    -- 3b. Completitud: TODO material del seguimiento debe reportar su
    --     consumo (sin valores implícitos). Se valida ANTES de tocar el
    --     inventario.
    FOR v_item IN
        SELECT si.material_id FROM seguimiento_items si
        WHERE si.seguimiento_id = p_seguimiento_id
        ORDER BY si.material_id
    LOOP
        IF NOT (v_consumidos_map ? v_item.material_id::text) THEN
            RAISE EXCEPTION 'Falta la cantidad consumida del material ID LISTA %.', v_item.material_id;
        END IF;
    END LOOP;

    -- 4. Bloqueo de las filas de inventario de la unidad (FOR UPDATE, orden
    --    por material_id: cero carreras y cero deadlocks con
    --    fn_procesar_movimiento).
    FOR v_fila_inv IN
        SELECT ie.material_id, ie.stock_actual
        FROM inventario_equipos ie
        WHERE ie.equipo_id = v_seguimiento.equipo_id
          AND ie.material_id = ANY(v_material_ids)
        ORDER BY ie.material_id
        FOR UPDATE
    LOOP
        NULL; -- el bloqueo ya quedó tomado; la lectura ocurre en el paso 5
    END LOOP;

    -- 5. Por cada item: validación de stock, registro del consumido,
    --    descuento DIRECTO del consumido (el remanente no se mueve; SIN
    --    eliminar filas que lleguen a 0) y evento de auditoría por línea.
    FOR v_item IN
        SELECT si.id, si.material_id, si.cantidad_tomada
        FROM seguimiento_items si
        WHERE si.seguimiento_id = p_seguimiento_id
        ORDER BY si.material_id
        FOR UPDATE
    LOOP
        v_consumido := (v_consumidos_map->>v_item.material_id::text)::NUMERIC;

        SELECT stock_actual INTO v_stock_actual
        FROM inventario_equipos
        WHERE equipo_id = v_seguimiento.equipo_id AND material_id = v_item.material_id
        FOR UPDATE;

        IF COALESCE(v_stock_actual, 0) < v_consumido THEN
            RAISE EXCEPTION 'Stock insuficiente en la Unidad ID % para el material ID LISTA %. Disponible: %, Consumido: %',
                v_seguimiento.equipo_id, v_item.material_id, COALESCE(v_stock_actual, 0), v_consumido;
        END IF;

        v_nuevo_stock := COALESCE(v_stock_actual, 0) - v_consumido;

        UPDATE seguimiento_items
        SET cantidad_consumida = v_consumido
        WHERE id = v_item.id;

        UPDATE inventario_equipos
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE equipo_id = v_seguimiento.equipo_id AND material_id = v_item.material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, equipo_origen_id, cantidad, resultado, detalles
        ) VALUES (
            p_usuario,
            'SEGUIMIENTO_CERRADO',
            v_item.material_id,
            v_seguimiento.equipo_id,
            v_consumido,
            'EXITO',
            jsonb_build_object(
                'seguimiento_id', p_seguimiento_id,
                'cantidad_tomada', v_item.cantidad_tomada,
                'cantidad_consumida', v_consumido,
                'stock_remanente_equipo', v_nuevo_stock,
                'fecha_cierre', CURRENT_TIMESTAMP,
                'observaciones_cierre', p_observaciones_cierre
            )
        );
    END LOOP;

    -- 6. Cerrar la cabecera.
    UPDATE seguimientos
    SET estado = 'CERRADA', closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    WHERE id = p_seguimiento_id;

    -- 7. ACTA DE CONSUMO: snapshot jsonb persistido en la MISMA transacción.
    SELECT jsonb_build_object(
        'acta_tipo', 'CONSUMO',
        'seguimiento_id', p_seguimiento_id,
        'equipo_id', v_seguimiento.equipo_id,
        'equipo_nombre', (SELECT nombre FROM equipos WHERE equipo_id = v_seguimiento.equipo_id),
        'fecha_apertura', v_seguimiento.fecha,
        'fecha_cierre', CURRENT_TIMESTAMP,
        'usuario', p_usuario,
        'observaciones', v_seguimiento.observaciones,
        'observaciones_cierre', p_observaciones_cierre,
        'items', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'material_id', si.material_id,
                    'codigo', cm.codigo,
                    'descripcion', cm.descripcion,
                    'u_m', cm.u_m,
                    'categoria', c.nombre,
                    'cantidad_tomada', si.cantidad_tomada,
                    'cantidad_consumida', si.cantidad_consumida
                ) ORDER BY si.material_id
            )
            FROM seguimiento_items si
            JOIN catalogo_materiales cm ON cm.id_lista = si.material_id
            LEFT JOIN categorias c ON c.id = cm.categoria_id
            WHERE si.seguimiento_id = p_seguimiento_id
        ), '[]'::jsonb)
    ) INTO v_snapshot_acta;

    INSERT INTO actas_reportes (tipo, seguimiento_id, snapshot)
    VALUES ('CONSUMO', p_seguimiento_id, v_snapshot_acta)
    RETURNING id INTO v_acta_id;

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, equipo_origen_id, resultado, detalles
    ) VALUES (
        p_usuario,
        'ACTA_CONSUMO_GENERADA',
        v_seguimiento.equipo_id,
        'EXITO',
        jsonb_build_object(
            'acta_id', v_acta_id,
            'seguimiento_id', p_seguimiento_id,
            'equipo_id', v_seguimiento.equipo_id,
            'fecha_cierre', CURRENT_TIMESTAMP,
            'observaciones_cierre', p_observaciones_cierre
        )
    );
END;
$$ LANGUAGE plpgsql;
"""

# ================================================================
# downgrade(): SQL VERBATIM de las funciones vigentes en 0026
# (copias literales extraídas de sus migraciones base)
# ================================================================

FN_PROCESAR_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_procesar_movimiento (p_movimiento_id INT)
RETURNS VOID AS $$
DECLARE
    v_rec RECORD;
    v_cabecera RECORD;
    v_stock_disponible INT;
    v_stock_minimo INT;
    v_alerta_stock BOOLEAN := FALSE;
    v_nuevo_stock_origen INT;
    v_origen_id INT;
    v_origen_tipo TEXT;
    v_destino_tipo TEXT;
    v_modulo TEXT;
BEGIN
    SELECT * INTO v_cabecera
    FROM movimientos_cabecera
    WHERE id = p_movimiento_id AND estado = 'BORRADOR'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El movimiento ID % no existe o no se encuentra en estado BORRADOR.', p_movimiento_id;
    END IF;

    -- El tipo de sección DESTINO se resuelve una vez (DEVOL). El ORIGEN se
    -- resuelve POR LÍNEA (0026): una transferencia puede combinar líneas de
    -- Inventario General y de Fibra Óptica (secciones FO_* = manejadores de
    -- ruteo hacia inventario_fibra).
    SELECT tipo INTO v_destino_tipo
    FROM secciones
    WHERE almacen_id = v_cabecera.destino_almacen_id;

    -- Orden DETERMINISTA de bloqueo (origen, material): dos confirmaciones
    -- concurrentes con las mismas líneas nunca se interbloquean (§2.3).
    FOR v_rec IN SELECT md.*, cm.stock_minimo,
                        COALESCE(md.origen_almacen_id, v_cabecera.origen_almacen_id) AS origen_efectivo
                 FROM movimientos_detalle md
                 JOIN catalogo_materiales cm ON cm.id_lista = md.material_id
                 WHERE md.movimiento_id = p_movimiento_id
                 ORDER BY COALESCE(md.origen_almacen_id, v_cabecera.origen_almacen_id), md.material_id LOOP

        v_stock_minimo := v_rec.stock_minimo;
        v_alerta_stock := FALSE;
        v_modulo := NULL;
        v_origen_id := v_rec.origen_efectivo;

        IF v_cabecera.tipo_movimiento = 'TEAMS' THEN
            IF v_origen_id IS NULL THEN
                RAISE EXCEPTION 'La línea del material ID LISTA % no tiene sección de origen.', v_rec.material_id;
            END IF;

            SELECT tipo INTO v_origen_tipo
            FROM secciones
            WHERE almacen_id = v_origen_id;

            IF v_origen_tipo = 'GENERAL' THEN
                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_almacen
                WHERE almacen_id = v_origen_id AND material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en Origen (Sección ID %) para el material ID LISTA %. Disponible: %, Solicitado: %',
                        v_origen_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                v_nuevo_stock_origen := v_stock_disponible - v_rec.cantidad;

                IF v_nuevo_stock_origen <= v_stock_minimo THEN
                    v_alerta_stock := TRUE;
                END IF;

                UPDATE inventario_almacen
                SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_origen_id AND material_id = v_rec.material_id;

            ELSIF v_origen_tipo IN ('FO_PAQUETE','FO_EN_USO') THEN
                v_modulo := CASE WHEN v_origen_tipo = 'FO_PAQUETE' THEN 'PAQUETE' ELSE 'EN_USO' END;

                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_fibra
                WHERE modulo = v_modulo AND material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en Origen (Módulo FO %) para el material ID LISTA %. Disponible: %, Solicitado: %',
                        v_modulo, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                v_nuevo_stock_origen := v_stock_disponible - v_rec.cantidad;

                IF v_nuevo_stock_origen <= v_stock_minimo THEN
                    v_alerta_stock := TRUE;
                END IF;

                UPDATE inventario_fibra
                SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
                WHERE modulo = v_modulo AND material_id = v_rec.material_id;

            ELSE
                RAISE EXCEPTION 'La sección ID % no es un origen válido para movimientos TEAMS.', v_origen_id;
            END IF;

            INSERT INTO inventario_equipos (equipo_id, material_id, stock_actual, ultimo_movimiento_id)
            VALUES (v_cabecera.destino_equipo_id, v_rec.material_id, v_rec.cantidad, p_movimiento_id)
            ON CONFLICT (equipo_id, material_id)
            DO UPDATE SET stock_actual = inventario_equipos.stock_actual + EXCLUDED.stock_actual,
                          ultimo_movimiento_id = p_movimiento_id,
                          updated_at = CURRENT_TIMESTAMP;

        ELSIF v_cabecera.tipo_movimiento = 'DEVOL' THEN
            SELECT stock_actual INTO v_stock_disponible
            FROM inventario_equipos
            WHERE equipo_id = v_cabecera.origen_equipo_id AND material_id = v_rec.material_id
            FOR UPDATE;

            IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                RAISE EXCEPTION 'La unidad ID % no cuenta con stock suficiente del material ID LISTA % para devolver.',
                    v_cabecera.origen_equipo_id, v_rec.material_id;
            END IF;

            v_nuevo_stock_origen := v_stock_disponible - v_rec.cantidad;

            UPDATE inventario_equipos
            SET stock_actual = v_nuevo_stock_origen,
                ultimo_movimiento_id = p_movimiento_id,
                updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.origen_equipo_id AND material_id = v_rec.material_id;

            IF v_destino_tipo = 'GENERAL' THEN
                INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual)
                VALUES (v_cabecera.destino_almacen_id, v_rec.material_id, v_rec.cantidad)
                ON CONFLICT (almacen_id, material_id)
                DO UPDATE SET stock_actual = inventario_almacen.stock_actual + EXCLUDED.stock_actual, updated_at = CURRENT_TIMESTAMP;

            ELSIF v_destino_tipo IN ('FO_PAQUETE','FO_EN_USO') THEN
                v_modulo := CASE WHEN v_destino_tipo = 'FO_PAQUETE' THEN 'PAQUETE' ELSE 'EN_USO' END;

                INSERT INTO inventario_fibra (modulo, material_id, stock_actual)
                VALUES (v_modulo, v_rec.material_id, v_rec.cantidad)
                ON CONFLICT (modulo, material_id)
                DO UPDATE SET stock_actual = inventario_fibra.stock_actual + EXCLUDED.stock_actual, updated_at = CURRENT_TIMESTAMP;

            ELSE
                RAISE EXCEPTION 'La sección ID % no es un destino válido para movimientos DEVOL.', v_cabecera.destino_almacen_id;
            END IF;
        END IF;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, equipo_origen_id, equipo_destino_id, almacen_origen_id, almacen_destino_id, cantidad, resultado, detalles
        ) VALUES (
            v_cabecera.usuario,
            CASE WHEN v_cabecera.tipo_movimiento = 'TEAMS' THEN 'TEAMS_TRANSFERENCIA' ELSE 'DEVOL_DEVOLUCION' END,
            v_rec.material_id, v_cabecera.origen_equipo_id, v_cabecera.destino_equipo_id, v_origen_id, v_cabecera.destino_almacen_id, v_rec.cantidad,
            'EXITO',
            jsonb_build_object(
                'movimiento_id', p_movimiento_id,
                'observaciones', v_cabecera.observaciones,
                'alerta_stock_minimo', v_alerta_stock,
                'stock_remanente_origen', v_nuevo_stock_origen,
                'stock_minimo_configurado', v_stock_minimo
            ) || CASE WHEN v_modulo IS NOT NULL
                      THEN jsonb_build_object('modulo_fo', v_modulo)
                      ELSE '{}'::jsonb END
        );
    END LOOP;

    UPDATE movimientos_cabecera SET estado = 'CONFIRMADO' WHERE id = p_movimiento_id;
END;
$$ LANGUAGE plpgsql;

"""

FN_CANCELAR_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_cancelar_movimiento (
    p_movimiento_id INT,
    p_motivo TEXT DEFAULT 'Reversión manual por cancelación'
)
RETURNS VOID AS $$
DECLARE
    v_rec RECORD;
    v_cabecera RECORD;
    v_stock_disponible INT;
    v_origen_tipo TEXT;
    v_destino_tipo TEXT;
    v_modulo TEXT;
BEGIN
    -- 1. Bloquear cabecera
    SELECT * INTO v_cabecera
    FROM movimientos_cabecera
    WHERE id = p_movimiento_id AND estado = 'CONFIRMADO'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El movimiento ID % no existe o no se encuentra en estado CONFIRMADO.', p_movimiento_id;
    END IF;

    -- Destino (DEVOL): una vez. Origen (TEAMS): POR LÍNEA (0026).
    SELECT tipo INTO v_destino_tipo
    FROM secciones
    WHERE almacen_id = v_cabecera.destino_almacen_id;

    FOR v_rec IN SELECT md.*,
                        COALESCE(md.origen_almacen_id, v_cabecera.origen_almacen_id) AS origen_efectivo
                 FROM movimientos_detalle md
                 WHERE md.movimiento_id = p_movimiento_id
                 ORDER BY COALESCE(md.origen_almacen_id, v_cabecera.origen_almacen_id), md.material_id LOOP

        v_modulo := NULL;

        -- REVERSIÓN TEAMS (Devuelve el stock de la unidad al origen de CADA línea)
        IF v_cabecera.tipo_movimiento = 'TEAMS' THEN

            SELECT tipo INTO v_origen_tipo
            FROM secciones
            WHERE almacen_id = v_rec.origen_efectivo;

            -- A. Validar y bloquear stock en la unidad destino
            SELECT stock_actual INTO v_stock_disponible
            FROM inventario_equipos
            WHERE equipo_id = v_cabecera.destino_equipo_id AND material_id = v_rec.material_id
            FOR UPDATE;

            IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                RAISE EXCEPTION 'Stock insuficiente en la Unidad destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                    v_cabecera.destino_equipo_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
            END IF;

            -- B. Descontar de la unidad destino
            UPDATE inventario_equipos
            SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.destino_equipo_id AND material_id = v_rec.material_id;

            -- C. Sumar al origen de la línea (GENERAL -> inventario_almacen; FO -> inventario_fibra)
            IF v_origen_tipo = 'GENERAL' THEN
                UPDATE inventario_almacen
                SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_rec.origen_efectivo AND material_id = v_rec.material_id;

            ELSIF v_origen_tipo IN ('FO_PAQUETE','FO_EN_USO') THEN
                v_modulo := CASE WHEN v_origen_tipo = 'FO_PAQUETE' THEN 'PAQUETE' ELSE 'EN_USO' END;

                UPDATE inventario_fibra
                SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE modulo = v_modulo AND material_id = v_rec.material_id;
            END IF;

        -- REVERSIÓN DEVOL (Devuelve el stock del almacén destino a la unidad origen)
        ELSIF v_cabecera.tipo_movimiento = 'DEVOL' THEN

            IF v_destino_tipo = 'GENERAL' THEN
                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_almacen
                WHERE almacen_id = v_cabecera.destino_almacen_id AND material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en el Almacén destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                        v_cabecera.destino_almacen_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                UPDATE inventario_almacen
                SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_cabecera.destino_almacen_id AND material_id = v_rec.material_id;

            ELSIF v_destino_tipo IN ('FO_PAQUETE','FO_EN_USO') THEN
                v_modulo := CASE WHEN v_destino_tipo = 'FO_PAQUETE' THEN 'PAQUETE' ELSE 'EN_USO' END;

                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_fibra
                WHERE modulo = v_modulo AND material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en el Almacén destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                        v_cabecera.destino_almacen_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                UPDATE inventario_fibra
                SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE modulo = v_modulo AND material_id = v_rec.material_id;
            END IF;

            UPDATE inventario_equipos
            SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.origen_equipo_id AND material_id = v_rec.material_id;
        END IF;

        -- 2. Registrar evento de cancelación con metadatos forenses
        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, equipo_origen_id, equipo_destino_id, almacen_origen_id, almacen_destino_id, cantidad, resultado, detalles
        ) VALUES (
            CURRENT_USER,
            'MOVIMIENTO_CANCELADO',
            v_rec.material_id, v_cabecera.origen_equipo_id, v_cabecera.destino_equipo_id, v_rec.origen_efectivo, v_cabecera.destino_almacen_id, v_rec.cantidad,
            'EXITO',
            jsonb_build_object(
                'movimiento_id', p_movimiento_id,
                'motivo_cancelacion', p_motivo,
                'fecha_cancelacion', CURRENT_TIMESTAMP,
                'usuario_autoriza', CURRENT_USER
            ) || CASE WHEN v_modulo IS NOT NULL
                      THEN jsonb_build_object('modulo_fo', v_modulo)
                      ELSE '{}'::jsonb END
        );
    END LOOP;

    -- 3. Actualizar estado de cabecera
    UPDATE movimientos_cabecera SET estado = 'CANCELADO' WHERE id = p_movimiento_id;
END;
$$ LANGUAGE plpgsql;

"""

FN_CARGAR_INICIAL_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_cargar_stock_inicial (
    p_almacen_id INT,
    p_material_id INT,
    p_cantidad INT,
    p_motivo TEXT DEFAULT 'Carga inicial de inventario en alta de catálogo'
)
RETURNS VOID AS $$
DECLARE
    v_existe BOOLEAN;
BEGIN
    IF p_cantidad < 0 THEN
        RAISE EXCEPTION 'La cantidad para carga inicial no puede ser negativa (%).', p_cantidad;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM inventario_almacen
        WHERE almacen_id = p_almacen_id AND material_id = p_material_id
    ) INTO v_existe;

    IF v_existe THEN
        RAISE EXCEPTION 'El material ID % ya posee un registro de inventario activo en el almacén ID %. Para ajustar existencias use fn_ajustar_stock_almacen.',
            p_material_id, p_almacen_id;
    END IF;

    INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual)
    VALUES (p_almacen_id, p_material_id, p_cantidad);

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, almacen_destino_id, cantidad, resultado, detalles
    ) VALUES (
        CURRENT_USER,
        'STOCK_INICIAL',
        p_material_id,
        p_almacen_id,
        p_cantidad,
        'EXITO',
        jsonb_build_object(
            'motivo', p_motivo,
            'fecha', CURRENT_TIMESTAMP,
            'operacion', 'CARGA_INICIAL_ALTA'
        )
    );
END;
$$ LANGUAGE plpgsql;

"""

FN_CARGAR_INICIAL_FIBRA_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_cargar_stock_inicial_fibra (
    p_modulo TEXT,
    p_material_id INT,
    p_cantidad INT,
    p_motivo TEXT DEFAULT 'Carga inicial de inventario FO'
)
RETURNS VOID AS $$
DECLARE
    v_existe BOOLEAN;
BEGIN
    IF p_cantidad < 0 THEN
        RAISE EXCEPTION 'La cantidad para carga inicial no puede ser negativa (%).', p_cantidad;
    END IF;

    IF p_modulo IS NULL OR p_modulo NOT IN ('PAQUETE','EN_USO') THEN
        RAISE EXCEPTION 'El módulo de Fibra Óptica debe ser PAQUETE o EN_USO (recibido: %).', p_modulo;
    END IF;

    SELECT EXISTS (
        SELECT 1
        FROM inventario_fibra
        WHERE modulo = p_modulo AND material_id = p_material_id
    ) INTO v_existe;

    IF v_existe THEN
        RAISE EXCEPTION 'El material ID % ya posee un registro de inventario activo en el módulo FO %. Para ajustar existencias use fn_ajustar_stock_fibra.',
            p_material_id, p_modulo;
    END IF;

    INSERT INTO inventario_fibra (modulo, material_id, stock_actual)
    VALUES (p_modulo, p_material_id, p_cantidad);

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, cantidad, resultado, detalles
    ) VALUES (
        CURRENT_USER,
        'STOCK_INICIAL_FO',
        p_material_id,
        p_cantidad,
        'EXITO',
        jsonb_build_object(
            'modulo', p_modulo,
            'motivo', p_motivo,
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;

"""

FN_AJUSTAR_GENERAL_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_ajustar_stock_general (
    p_material_id INT,
    p_nuevo_stock INT,
    p_motivo TEXT
)
RETURNS VOID AS $$
DECLARE
    v_almacen_id INT;
    v_conteo INT;
BEGIN
    -- Localiza la fila de inventario_almacen del material en la sección
    -- ACTIVA de tipo GENERAL (contrato REQ-API-002/003: edición de stock
    -- desde Inventario General).
    SELECT COUNT(*) INTO v_conteo
    FROM inventario_almacen ia
    JOIN secciones s ON s.almacen_id = ia.almacen_id
    WHERE ia.material_id = p_material_id
      AND s.tipo = 'GENERAL'
      AND s.is_active = TRUE;

    IF v_conteo = 0 THEN
        RAISE EXCEPTION 'No se encontró inventario del material ID % en la sección activa de Inventario General. Realice primero la carga inicial.',
            p_material_id;
    END IF;

    IF v_conteo > 1 THEN
        RAISE EXCEPTION 'Existen % filas de inventario del material ID % en secciones activas de tipo GENERAL; no es posible determinar un destino único para el ajuste.',
            v_conteo, p_material_id;
    END IF;

    SELECT ia.almacen_id INTO v_almacen_id
    FROM inventario_almacen ia
    JOIN secciones s ON s.almacen_id = ia.almacen_id
    WHERE ia.material_id = p_material_id
      AND s.tipo = 'GENERAL'
      AND s.is_active = TRUE
    LIMIT 1
    FOR UPDATE OF ia;

    -- Delegación completa: validación de motivo, no-negatividad, bloqueo
    -- FOR UPDATE, diferencial y auditoría viven en fn_ajustar_stock_almacen.
    PERFORM fn_ajustar_stock_almacen(v_almacen_id, p_material_id, p_nuevo_stock, p_motivo);
END;
$$ LANGUAGE plpgsql;

"""

FN_AJUSTAR_ALMACEN_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_ajustar_stock_almacen (
    p_almacen_id INT,
    p_material_id INT,
    p_nuevo_stock INT,
    p_motivo TEXT
)
RETURNS VOID AS $$
DECLARE
    v_stock_anterior INT;
    v_diferencia INT;
BEGIN
    IF p_nuevo_stock < 0 THEN
        RAISE EXCEPTION 'El stock final ajustado no puede ser negativo (%).', p_nuevo_stock;
    END IF;

    -- Ergonomía `justificacion_opcional` (REQ-ERG-003/005): el motivo es
    -- OPCIONAL — null o vacío se acepta y se audita tal como llega.

    -- Bloqueo FOR UPDATE para prevenir condiciones de carrera durante la lectura del stock actual
    SELECT stock_actual INTO v_stock_anterior
    FROM inventario_almacen
    WHERE almacen_id = p_almacen_id AND material_id = p_material_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el almacén ID %. Realice primero la carga inicial.',
            p_material_id, p_almacen_id;
    END IF;

    v_diferencia := p_nuevo_stock - v_stock_anterior;

    -- Actualización de inventario
    UPDATE inventario_almacen
    SET stock_actual = p_nuevo_stock, updated_at = CURRENT_TIMESTAMP
    WHERE almacen_id = p_almacen_id AND material_id = p_material_id;

    -- Auditoría del ajuste con diferencial calculado
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, almacen_destino_id, cantidad, resultado, detalles
    ) VALUES (
        CURRENT_USER,
        'AJUSTE_INVENTARIO',
        p_material_id,
        p_almacen_id,
        p_nuevo_stock,
        'EXITO',
        jsonb_build_object(
            'stock_anterior', v_stock_anterior,
            'stock_nuevo', p_nuevo_stock,
            'diferencial', v_diferencia,
            'motivo', p_motivo,
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;

"""

FN_AJUSTAR_FIBRA_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_ajustar_stock_fibra (
    p_modulo TEXT,
    p_material_id INT,
    p_nuevo_stock INT,
    p_motivo TEXT
)
RETURNS VOID AS $$
DECLARE
    v_stock_anterior INT;
    v_diferencia INT;
BEGIN
    -- Ergonomía `justificacion_opcional` (REQ-ERG-004/005): el motivo es
    -- OPCIONAL — null o vacío se acepta y se audita tal como llega.

    IF p_nuevo_stock < 0 THEN
        RAISE EXCEPTION 'El stock final ajustado no puede ser negativo (%).', p_nuevo_stock;
    END IF;

    -- Bloqueo FOR UPDATE: cero condiciones de carrera sobre inventario_fibra
    SELECT stock_actual INTO v_stock_anterior
    FROM inventario_fibra
    WHERE modulo = p_modulo AND material_id = p_material_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el módulo FO %. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
            p_material_id, p_modulo;
    END IF;

    v_diferencia := p_nuevo_stock - v_stock_anterior;

    UPDATE inventario_fibra
    SET stock_actual = p_nuevo_stock, updated_at = CURRENT_TIMESTAMP
    WHERE modulo = p_modulo AND material_id = p_material_id;

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, cantidad, resultado, detalles
    ) VALUES (
        CURRENT_USER,
        'AJUSTE_INVENTARIO_FO',
        p_material_id,
        p_nuevo_stock,
        'EXITO',
        jsonb_build_object(
            'stock_anterior', v_stock_anterior,
            'stock_nuevo', p_nuevo_stock,
            'diferencial', v_diferencia,
            'motivo', p_motivo,
            'modulo', p_modulo,
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;

"""

FN_ELIMINAR_FIBRA_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_eliminar_inventario_fibra (
    p_modulo TEXT,
    p_material_id INT,
    p_motivo TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_stock_anterior INT;
BEGIN
    IF p_modulo IS NULL OR p_modulo NOT IN ('PAQUETE','EN_USO') THEN
        RAISE EXCEPTION 'El módulo de Fibra Óptica debe ser PAQUETE o EN_USO (recibido: %).', p_modulo;
    END IF;

    -- Bloqueo FOR UPDATE: cero condiciones de carrera sobre inventario_fibra.
    SELECT stock_actual INTO v_stock_anterior
    FROM inventario_fibra
    WHERE modulo = p_modulo AND material_id = p_material_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el módulo FO %. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
            p_material_id, p_modulo;
    END IF;

    -- REQ-DEL-004: con existencias, el motivo es obligatorio y no vacío
    -- (RAISE -> 422 vía el mapeo "motivo" de transaccional).
    IF v_stock_anterior > 0 AND (p_motivo IS NULL OR TRIM(p_motivo) = '') THEN
        RAISE EXCEPTION 'Es obligatorio proporcionar un motivo para eliminar inventario FO con existencias (material ID %, módulo %, stock %).',
            p_material_id, p_modulo, v_stock_anterior;
    END IF;

    -- Eliminación física SOLO de la fila del módulo indicado
    -- (REQ-DEL-003: aislamiento por módulo; catálogo e Inventario General intactos).
    DELETE FROM inventario_fibra
    WHERE modulo = p_modulo AND material_id = p_material_id;

    -- Auditoría forense con snapshot completo (Constitution 6.2):
    -- el stock eliminado queda reconstruible en el ledger inmutable.
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, cantidad, resultado, detalles
    ) VALUES (
        COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER),
        'ELIMINACION_FO',
        p_material_id,
        v_stock_anterior,
        'EXITO',
        jsonb_build_object(
            'modulo', p_modulo,
            'material_id', p_material_id,
            'stock_eliminado', v_stock_anterior,
            'motivo', p_motivo,
            'usuario', COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER),
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;

"""

FN_SUMAR_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_sumar_cantidad (
    p_destino TEXT,
    p_modulo TEXT,
    p_material_id INT,
    p_cantidad INT,
    p_usuario TEXT,
    p_clave_idempotencia TEXT DEFAULT NULL
)
RETURNS INT AS $$
DECLARE
    v_actor TEXT;
    v_guard TEXT;
    v_guard_actor TEXT;
    v_almacen_id INT;
    v_conteo INT;
    v_stock_anterior INT;
    v_nuevo_stock INT;
BEGIN
    v_actor := COALESCE(NULLIF(p_usuario, ''),
                        NULLIF(current_setting('app.actor', true), ''),
                        CURRENT_USER);

    -- 0. Guarda de idempotencia (REQ-P2-INV-007): la fila vive en la MISMA
    --    transacción; un fallo posterior la elimina con el rollback.
    IF p_clave_idempotencia IS NOT NULL THEN
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave, actor)
        VALUES ('SUMA_CANTIDAD', p_clave_idempotencia, v_actor)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            SELECT actor INTO v_guard_actor
            FROM operaciones_idempotencia
            WHERE tipo_operacion = 'SUMA_CANTIDAD' AND clave = p_clave_idempotencia;

            IF v_guard_actor IS DISTINCT FROM v_actor THEN
                RAISE EXCEPTION 'La clave de idempotencia ya fue utilizada por otro actor.';
            END IF;

            RAISE EXCEPTION 'La operación SUMA_CANTIDAD ya fue ejecutada para esta clave de idempotencia.';
        END IF;
    END IF;

    -- 1. Validaciones de dominio (REQ-P2-INV-001).
    IF p_destino IS NULL OR p_destino NOT IN ('GENERAL','FO') THEN
        RAISE EXCEPTION 'El destino de +Cantidad debe ser GENERAL o FO (recibido: %).', p_destino;
    END IF;

    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        RAISE EXCEPTION 'La cantidad a sumar debe ser mayor que cero (recibida: %).', p_cantidad;
    END IF;

    IF p_destino = 'FO' AND (p_modulo IS NULL OR p_modulo NOT IN ('PAQUETE','EN_USO')) THEN
        RAISE EXCEPTION 'El módulo de Fibra Óptica debe ser PAQUETE o EN_USO (recibido: %).', p_modulo;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM catalogo_materiales
        WHERE id_lista = p_material_id AND is_active = TRUE
    ) THEN
        RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', p_material_id;
    END IF;

    -- 2. Mutación atómica con bloqueo FOR UPDATE + auditoría inmutable.
    IF p_destino = 'GENERAL' THEN
        -- Resolución de la sección GENERAL activa (espejo de
        -- fn_ajustar_stock_general): 0 filas -> 404; >1 -> conflicto.
        SELECT COUNT(*) INTO v_conteo
        FROM inventario_almacen ia
        JOIN secciones s ON s.almacen_id = ia.almacen_id
        WHERE ia.material_id = p_material_id
          AND s.tipo = 'GENERAL' AND s.is_active = TRUE;

        IF v_conteo = 0 THEN
            RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en la sección GENERAL activa. Realice primero la carga inicial.',
                p_material_id;
        END IF;

        IF v_conteo > 1 THEN
            RAISE EXCEPTION 'Existen % filas de inventario del material ID % en secciones GENERAL activas; no es posible determinar un destino único.',
                v_conteo, p_material_id;
        END IF;

        SELECT ia.almacen_id, ia.stock_actual INTO v_almacen_id, v_stock_anterior
        FROM inventario_almacen ia
        JOIN secciones s ON s.almacen_id = ia.almacen_id
        WHERE ia.material_id = p_material_id
          AND s.tipo = 'GENERAL' AND s.is_active = TRUE
        LIMIT 1
        FOR UPDATE OF ia;

        v_nuevo_stock := v_stock_anterior + p_cantidad;

        UPDATE inventario_almacen
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE almacen_id = v_almacen_id AND material_id = p_material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, almacen_destino_id, cantidad, resultado, detalles
        ) VALUES (
            v_actor,
            'SUMA_CANTIDAD',
            p_material_id,
            v_almacen_id,
            p_cantidad,
            'EXITO',
            jsonb_build_object(
                'destino', 'GENERAL',
                'almacen_id', v_almacen_id,
                'stock_anterior', v_stock_anterior,
                'stock_nuevo', v_nuevo_stock,
                'diferencial', p_cantidad,
                'usuario', v_actor,                'fecha', CURRENT_TIMESTAMP
            )
        );

    ELSE -- p_destino = 'FO'
        SELECT stock_actual INTO v_stock_anterior
        FROM inventario_fibra
        WHERE modulo = p_modulo AND material_id = p_material_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el módulo FO %. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
                p_material_id, p_modulo;
        END IF;

        v_nuevo_stock := v_stock_anterior + p_cantidad;

        UPDATE inventario_fibra
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE modulo = p_modulo AND material_id = p_material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, cantidad, resultado, detalles
        ) VALUES (
            v_actor,
            'SUMA_CANTIDAD',
            p_material_id,
            p_cantidad,
            'EXITO',
            jsonb_build_object(
                'destino', 'FO',
                'modulo', p_modulo,
                'stock_anterior', v_stock_anterior,
                'stock_nuevo', v_nuevo_stock,
                'diferencial', p_cantidad,
                'usuario', v_actor,                'fecha', CURRENT_TIMESTAMP
            )
        );
    END IF;

    -- 3. Persistir el resultado para retornos de reenvío (REQ-P2-INV-007).
    IF p_clave_idempotencia IS NOT NULL THEN
        UPDATE operaciones_idempotencia
        SET resultado = jsonb_build_object(
            'stock_nuevo', v_nuevo_stock,
            'destino', p_destino,
            'modulo', p_modulo
        )
        WHERE tipo_operacion = 'SUMA_CANTIDAD' AND clave = p_clave_idempotencia;
    END IF;

    RETURN v_nuevo_stock;
END;
$$ LANGUAGE plpgsql;
-- v2 (0021): actor en idempotencia, clave redactada de auditoría y mensajes.

"""

FN_MOVER_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_mover_material (
    p_origen TEXT,
    p_origen_modulo TEXT,
    p_destino TEXT,
    p_destino_modulo TEXT,
    p_material_id INT,
    p_cantidad INT,
    p_usuario TEXT,
    p_clave_idempotencia TEXT DEFAULT NULL
)
RETURNS JSONB AS $$
DECLARE
    v_actor TEXT;
    v_guard TEXT;
    v_guard_actor TEXT;
    v_conteo INT;
    v_almacen_general INT;
    v_stock_origen_anterior INT;  -- NULL = fila no leída (FO) / aún sin bloquear
    v_stock_destino_anterior INT; -- NULL = fila destino inexistente (modelo disperso)
    v_nuevo_stock_origen INT;
    v_nuevo_stock_destino INT;
    v_fila_fibra RECORD;
BEGIN
    v_actor := COALESCE(NULLIF(p_usuario, ''),
                        NULLIF(current_setting('app.actor', true), ''),
                        CURRENT_USER);

    -- 0. Guarda de idempotencia (REQ-P2-INV-007), misma transacción.
    IF p_clave_idempotencia IS NOT NULL THEN
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave, actor)
        VALUES ('MOVIMIENTO_INVENTARIO', p_clave_idempotencia, v_actor)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            SELECT actor INTO v_guard_actor
            FROM operaciones_idempotencia
            WHERE tipo_operacion = 'MOVIMIENTO_INVENTARIO' AND clave = p_clave_idempotencia;

            IF v_guard_actor IS DISTINCT FROM v_actor THEN
                RAISE EXCEPTION 'La clave de idempotencia ya fue utilizada por otro actor.';
            END IF;

            RAISE EXCEPTION 'La operación MOVIMIENTO_INVENTARIO ya fue ejecutada para esta clave de idempotencia.';
        END IF;
    END IF;

    -- 1. Validaciones de parámetros.
    IF p_origen IS NULL OR p_origen NOT IN ('GENERAL','FO') THEN
        RAISE EXCEPTION 'El origen del movimiento debe ser GENERAL o FO (recibido: %).', p_origen;
    END IF;

    IF p_destino IS NULL OR p_destino NOT IN ('GENERAL','FO') THEN
        RAISE EXCEPTION 'El destino del movimiento debe ser GENERAL o FO (recibido: %).', p_destino;
    END IF;

    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        RAISE EXCEPTION 'La cantidad a mover debe ser mayor que cero (recibida: %).', p_cantidad;
    END IF;

    IF p_origen = 'FO' AND (p_origen_modulo IS NULL OR p_origen_modulo NOT IN ('PAQUETE','EN_USO')) THEN
        RAISE EXCEPTION 'El módulo de origen FO debe ser PAQUETE o EN_USO (recibido: %).', p_origen_modulo;
    END IF;

    IF p_destino = 'FO' AND (p_destino_modulo IS NULL OR p_destino_modulo NOT IN ('PAQUETE','EN_USO')) THEN
        RAISE EXCEPTION 'El módulo de destino FO debe ser PAQUETE o EN_USO (recibido: %).', p_destino_modulo;
    END IF;

    -- 2. REQ-P2-INV-004: destino igual al origen.
    IF (p_origen = 'GENERAL' AND p_destino = 'GENERAL')
       OR (p_origen = 'FO' AND p_destino = 'FO' AND p_origen_modulo = p_destino_modulo) THEN
        RAISE EXCEPTION 'El destino del movimiento no puede ser igual al origen (%).', p_origen;
    END IF;

    -- 3. Material activo. Coherencia de U.M./catálogo entre extremos:
    --    GARANTIZADA POR CONSTRUCCIÓN (mismo id_lista en ambos
    --    inventarios; u_m es atributo del catálogo, no del inventario).
    IF NOT EXISTS (
        SELECT 1 FROM catalogo_materiales
        WHERE id_lista = p_material_id AND is_active = TRUE
    ) THEN
        RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', p_material_id;
    END IF;

    -- 4. Bloqueo DETERMINISTA (cero deadlocks): primero la fila GENERAL
    --    (si participa) y después las filas FO ordenadas por modulo
    --    ascendente. Movimientos opuestos concurrentes sobre el mismo
    --    material serializan en este mismo orden.

    -- 4.a Lado GENERAL (origen o destino): resolución de la sección
    --     GENERAL activa independiente del material.
    IF p_origen = 'GENERAL' OR p_destino = 'GENERAL' THEN
        SELECT COUNT(*) INTO v_conteo
        FROM secciones
        WHERE tipo = 'GENERAL' AND is_active = TRUE;

        IF v_conteo = 0 THEN
            RAISE EXCEPTION 'No existe una sección GENERAL activa para el movimiento de inventario.';
        END IF;

        IF v_conteo > 1 THEN
            RAISE EXCEPTION 'Existen % secciones GENERAL activas; no es posible determinar un destino único para el movimiento.',
                v_conteo;
        END IF;

        SELECT almacen_id INTO v_almacen_general
        FROM secciones
        WHERE tipo = 'GENERAL' AND is_active = TRUE
        ORDER BY almacen_id
        LIMIT 1;

        IF p_origen = 'GENERAL' THEN
            SELECT stock_actual INTO v_stock_origen_anterior
            FROM inventario_almacen
            WHERE almacen_id = v_almacen_general AND material_id = p_material_id
            FOR UPDATE;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en la sección GENERAL activa. Realice primero la carga inicial.',
                    p_material_id;
            END IF;
        ELSE
            -- GENERAL es destino: la fila puede no existir aún (modelo
            -- disperso); se crea en el UPSERT solo con stock > 0.
            SELECT stock_actual INTO v_stock_destino_anterior
            FROM inventario_almacen
            WHERE almacen_id = v_almacen_general AND material_id = p_material_id
            FOR UPDATE;
        END IF;
    END IF;

    -- 4.b Lado FO (origen y/o destino): bloqueo de las filas implicadas
    --     en orden ascendente de modulo.
    IF p_origen = 'FO' OR p_destino = 'FO' THEN
        FOR v_fila_fibra IN
            SELECT modulo, stock_actual
            FROM inventario_fibra
            WHERE material_id = p_material_id
              AND (modulo = p_origen_modulo OR modulo = p_destino_modulo)
            ORDER BY modulo
            FOR UPDATE
        LOOP
            IF p_origen = 'FO' AND v_fila_fibra.modulo = p_origen_modulo THEN
                v_stock_origen_anterior := v_fila_fibra.stock_actual;
            END IF;
            IF p_destino = 'FO' AND v_fila_fibra.modulo = p_destino_modulo THEN
                v_stock_destino_anterior := v_fila_fibra.stock_actual;
            END IF;
        END LOOP;

        IF p_origen = 'FO' AND v_stock_origen_anterior IS NULL THEN
            RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el módulo FO %. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
                p_material_id, p_origen_modulo;
        END IF;
    END IF;

    -- 5. Validación de stock del origen (REQ-P2-INV-004).
    IF COALESCE(v_stock_origen_anterior, 0) < p_cantidad THEN
        RAISE EXCEPTION 'Stock insuficiente en Origen (%) para el material ID LISTA %. Disponible: %, Solicitado: %',
            p_origen, p_material_id, COALESCE(v_stock_origen_anterior, 0), p_cantidad;
    END IF;

    v_nuevo_stock_origen := COALESCE(v_stock_origen_anterior, 0) - p_cantidad;
    v_nuevo_stock_destino := COALESCE(v_stock_destino_anterior, 0) + p_cantidad;

    -- 6. Descuento del origen (la fila SE CONSERVA aunque llegue a 0:
    --    decisión de semántica dispersa documentada en el docstring).
    IF p_origen = 'GENERAL' THEN
        UPDATE inventario_almacen
        SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
        WHERE almacen_id = v_almacen_general AND material_id = p_material_id;
    ELSE
        UPDATE inventario_fibra
        SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
        WHERE modulo = p_origen_modulo AND material_id = p_material_id;
    END IF;

    -- 7. Acreditación del destino: la fila se crea SOLO con stock > 0
    --    (p_cantidad > 0 garantizado); si existe, el UPSERT acumula.
    --    El stock del destino se RELEE tras el UPSERT (fila bloqueada por
    --    nuestra propia escritura) para que el snapshot de auditoría y el
    --    retorno sean exactos bajo concurrencia.
    IF p_destino = 'GENERAL' THEN
        INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual)
        VALUES (v_almacen_general, p_material_id, p_cantidad)
        ON CONFLICT (almacen_id, material_id)
        DO UPDATE SET stock_actual = inventario_almacen.stock_actual + EXCLUDED.stock_actual,
                      updated_at = CURRENT_TIMESTAMP;

        SELECT stock_actual INTO v_nuevo_stock_destino
        FROM inventario_almacen
        WHERE almacen_id = v_almacen_general AND material_id = p_material_id;
    ELSE
        INSERT INTO inventario_fibra (modulo, material_id, stock_actual)
        VALUES (p_destino_modulo, p_material_id, p_cantidad)
        ON CONFLICT (modulo, material_id)
        DO UPDATE SET stock_actual = inventario_fibra.stock_actual + EXCLUDED.stock_actual,
                      updated_at = CURRENT_TIMESTAMP;

        SELECT stock_actual INTO v_nuevo_stock_destino
        FROM inventario_fibra
        WHERE modulo = p_destino_modulo AND material_id = p_material_id;
    END IF;

    -- 8. Auditoría inmutable con snapshot completo (REQ-P2-INV-006).
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, cantidad, resultado, detalles
    ) VALUES (
        v_actor,
        'MOVIMIENTO_INVENTARIO',
        p_material_id,
        p_cantidad,
        'EXITO',
        jsonb_build_object(
            'origen', jsonb_build_object(
                'tipo', p_origen,
                'modulo', p_origen_modulo,
                'almacen_id', CASE WHEN p_origen = 'GENERAL' THEN v_almacen_general ELSE NULL END
            ),
            'destino', jsonb_build_object(
                'tipo', p_destino,
                'modulo', p_destino_modulo,
                'almacen_id', CASE WHEN p_destino = 'GENERAL' THEN v_almacen_general ELSE NULL END
            ),
            'stock_origen_anterior', COALESCE(v_stock_origen_anterior, 0),
            'stock_origen_despues', v_nuevo_stock_origen,
            'stock_destino_anterior', COALESCE(v_stock_destino_anterior, 0),
            'stock_destino_despues', v_nuevo_stock_destino,
            'usuario', v_actor,            'fecha', CURRENT_TIMESTAMP
        )
    );

    -- 9. Persistir el resultado para retornos de reenvío (REQ-P2-INV-007).
    IF p_clave_idempotencia IS NOT NULL THEN
        UPDATE operaciones_idempotencia
        SET resultado = jsonb_build_object(
            'stock_origen', v_nuevo_stock_origen,
            'stock_destino', v_nuevo_stock_destino,
            'origen', p_origen,
            'destino', p_destino
        )
        WHERE tipo_operacion = 'MOVIMIENTO_INVENTARIO' AND clave = p_clave_idempotencia;
    END IF;

    RETURN jsonb_build_object(
        'stock_origen', v_nuevo_stock_origen,
        'stock_destino', v_nuevo_stock_destino
    );
END;
$$ LANGUAGE plpgsql;
-- v2 (0021): actor en idempotencia, clave redactada de auditoría y mensajes.

"""

FN_AGREGAR_TODO_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_agregar_todo_seguimiento (
    p_seguimiento_id INT,
    p_equipo_id INT,
    p_usuario TEXT,
    p_clave_idempotencia TEXT DEFAULT NULL
)
RETURNS INT AS $$
DECLARE
    v_actor TEXT;
    v_guard TEXT;
    v_guard_actor TEXT;
    v_seguimiento RECORD;
    v_inv RECORD;
    v_agregadas INT := 0;
    v_unidades INT := 0;
BEGIN
    v_actor := COALESCE(NULLIF(p_usuario, ''),
                        NULLIF(current_setting('app.actor', true), ''),
                        CURRENT_USER);

    -- 0. Guarda de idempotencia (REQ-P2-INV-007), misma transacción.
    IF p_clave_idempotencia IS NOT NULL THEN
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave, actor)
        VALUES ('AGREGAR_TODO', p_clave_idempotencia, v_actor)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            SELECT actor INTO v_guard_actor
            FROM operaciones_idempotencia
            WHERE tipo_operacion = 'AGREGAR_TODO' AND clave = p_clave_idempotencia;

            IF v_guard_actor IS DISTINCT FROM v_actor THEN
                RAISE EXCEPTION 'La clave de idempotencia ya fue utilizada por otro actor.';
            END IF;

            RAISE EXCEPTION 'La operación AGREGAR_TODO ya fue ejecutada para esta clave de idempotencia.';
        END IF;
    END IF;

    -- 1. Cabecera: existencia, pertenencia al equipo y estado ABIERTA.
    --    FOR UPDATE serializa con fn_cerrar_seguimiento y con dobles
    --    invocaciones concurrentes (REQ-P2-CON-004).
    SELECT * INTO v_seguimiento
    FROM seguimientos
    WHERE id = p_seguimiento_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Seguimiento ID % no encontrado.', p_seguimiento_id;
    END IF;

    IF v_seguimiento.equipo_id <> p_equipo_id THEN
        RAISE EXCEPTION 'El seguimiento ID % no pertenece a la unidad ID %.',
            p_seguimiento_id, p_equipo_id;
    END IF;

    IF v_seguimiento.estado <> 'ABIERTA' THEN
        RAISE EXCEPTION 'El seguimiento ID % no se encuentra en estado ABIERTA.',
            p_seguimiento_id;
    END IF;

    -- 2. Líneas del inventario del equipo con existencias reales, leídas
    --    BAJO bloqueo FOR UPDATE en orden determinista por material_id
    --    (cero condiciones de carrera con fn_cerrar_seguimiento y
    --    fn_procesar_movimiento, que bloquean en el mismo orden).
    FOR v_inv IN
        SELECT material_id, stock_actual
        FROM inventario_equipos
        WHERE equipo_id = p_equipo_id AND stock_actual > 0
        ORDER BY material_id
        FOR UPDATE
    LOOP
        -- 3. Inserción idempotente: ON CONFLICT DO NOTHING — una doble
        --    invocación no duplica líneas ni altera las ya presentes.
        INSERT INTO seguimiento_items (seguimiento_id, material_id, cantidad_tomada)
        VALUES (p_seguimiento_id, v_inv.material_id, v_inv.stock_actual)
        ON CONFLICT (seguimiento_id, material_id) DO NOTHING;

        IF FOUND THEN
            v_agregadas := v_agregadas + 1;
            v_unidades := v_unidades + v_inv.stock_actual;
        END IF;
    END LOOP;

    -- 4. Evento de auditoría SOLO si hubo líneas nuevas: el ledger no
    --    duplica eventos en una segunda invocación (REQ-P2-CON-004).
    IF v_agregadas > 0 THEN
        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, equipo_destino_id, resultado, detalles
        ) VALUES (
            v_actor,
            'AGREGAR_TODO',
            p_equipo_id,
            'EXITO',
            jsonb_build_object(
                'seguimiento_id', p_seguimiento_id,
                'equipo_id', p_equipo_id,
                'lineas_agregadas', v_agregadas,
                'unidades_agregadas', v_unidades,
                'usuario', v_actor,                'fecha', CURRENT_TIMESTAMP
            )
        );
    END IF;

    -- 5. Persistir el resultado para retornos de reenvío (REQ-P2-INV-007).
    IF p_clave_idempotencia IS NOT NULL THEN
        UPDATE operaciones_idempotencia
        SET resultado = jsonb_build_object(
            'lineas_agregadas', v_agregadas,
            'seguimiento_id', p_seguimiento_id
        )
        WHERE tipo_operacion = 'AGREGAR_TODO' AND clave = p_clave_idempotencia;
    END IF;

    RETURN v_agregadas;
END;
$$ LANGUAGE plpgsql;
-- v2 (0021): actor en idempotencia, clave redactada de auditoría y mensajes.

"""

FN_CREAR_SEGUIMIENTO_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_crear_seguimiento (
    p_equipo_id INT,
    p_observaciones TEXT,
    p_items JSONB,
    p_usuario TEXT
)
RETURNS INT AS $$
DECLARE
    v_id INT;
    v_existe BOOLEAN;
    v_item RECORD;
    v_visto INT[] := '{}';
BEGIN
    -- 1. El equipo debe existir y estar activo.
    SELECT EXISTS (
        SELECT 1 FROM equipos WHERE equipo_id = p_equipo_id AND is_active = TRUE
    ) INTO v_existe;

    IF NOT v_existe THEN
        RAISE EXCEPTION 'La unidad ID % no existe o se encuentra inactiva.', p_equipo_id;
    END IF;

    -- 2. La lista del seguimiento debe ser un arreglo JSON no vacío.
    IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
        RAISE EXCEPTION 'La lista de seguimiento debe contener al menos un material.';
    END IF;

    -- 3. Validación de cada línea: material activo, cantidad positiva y
    --    cero duplicados dentro del payload.
    FOR v_item IN
        SELECT (elem->>'material_id')::INT AS material_id,
               (elem->>'cantidad_tomada')::INT AS cantidad_tomada
        FROM jsonb_array_elements(p_items) AS elem
    LOOP
        IF v_item.material_id IS NULL THEN
            RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', v_item.material_id;
        END IF;

        IF v_item.material_id = ANY(v_visto) THEN
            RAISE EXCEPTION 'Material ID LISTA % duplicado en la lista de seguimiento.', v_item.material_id;
        END IF;
        v_visto := array_append(v_visto, v_item.material_id);

        IF v_item.cantidad_tomada IS NULL OR v_item.cantidad_tomada <= 0 THEN
            RAISE EXCEPTION 'Cantidad tomada inválida para el material ID LISTA % (debe ser mayor a 0).', v_item.material_id;
        END IF;

        SELECT EXISTS (
            SELECT 1 FROM catalogo_materiales
            WHERE id_lista = v_item.material_id AND is_active = TRUE
        ) INTO v_existe;

        IF NOT v_existe THEN
            RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', v_item.material_id;
        END IF;
    END LOOP;

    -- 4. Un solo seguimiento abierto por equipo (bloqueo de filas sobre la
    --    ventana del equipo; el índice único parcial es la red de seguridad).
    PERFORM 1
    FROM seguimientos
    WHERE equipo_id = p_equipo_id AND estado = 'ABIERTA'
    FOR UPDATE;

    IF FOUND THEN
        RAISE EXCEPTION 'La unidad ID % ya posee un seguimiento abierto.', p_equipo_id;
    END IF;

    -- 5. Cabecera (estado por defecto ABIERTA) e items.
    INSERT INTO seguimientos (equipo_id, fecha, observaciones, usuario)
    VALUES (p_equipo_id, CURRENT_DATE, p_observaciones, p_usuario)
    RETURNING id INTO v_id;

    FOR v_item IN
        SELECT (elem->>'material_id')::INT AS material_id,
               (elem->>'cantidad_tomada')::INT AS cantidad_tomada
        FROM jsonb_array_elements(p_items) AS elem
    LOOP
        INSERT INTO seguimiento_items (seguimiento_id, material_id, cantidad_tomada)
        VALUES (v_id, v_item.material_id, v_item.cantidad_tomada);
    END LOOP;

    -- 6. Evento de auditoría de apertura (nomenclatura nueva).
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, equipo_destino_id, resultado, detalles
    ) VALUES (
        p_usuario,
        'SEGUIMIENTO_CREADO',
        p_equipo_id,
        'EXITO',
        jsonb_build_object(
            'seguimiento_id', v_id,
            'fecha', CURRENT_DATE,
            'cantidad_items', jsonb_array_length(p_items),
            'observaciones', p_observaciones
        )
    );

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;

"""

FN_CERRAR_ANTERIOR = """

CREATE FUNCTION fn_cerrar_seguimiento (
    p_seguimiento_id INT,
    p_consumidos JSONB,
    p_usuario TEXT,
    p_observaciones_cierre TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_seguimiento RECORD;
    v_item RECORD;
    v_linea RECORD;
    v_fila_inv RECORD;
    v_vistos INT[] := '{}';
    v_material_ids INT[] := '{}';
    v_tomadas_map JSONB := '{}'::jsonb;
    v_consumidos_map JSONB := '{}'::jsonb;
    v_tomada INT;
    v_consumido INT;
    v_stock_actual INT;
    v_nuevo_stock INT;
    v_snapshot_acta JSONB;
    v_acta_id INT;
BEGIN
    -- 1. Bloquear la cabecera SOLO si está ABIERTA.
    SELECT * INTO v_seguimiento
    FROM seguimientos
    WHERE id = p_seguimiento_id AND estado = 'ABIERTA'
    FOR UPDATE;

    IF NOT FOUND THEN
        IF EXISTS (SELECT 1 FROM seguimientos WHERE id = p_seguimiento_id) THEN
            RAISE EXCEPTION 'El seguimiento ID % no se encuentra en estado ABIERTA.', p_seguimiento_id;
        ELSE
            RAISE EXCEPTION 'Seguimiento ID % no encontrado.', p_seguimiento_id;
        END IF;
    END IF;

    -- 2. Items del seguimiento ORDENADOS por material_id (orden de bloqueo
    --    determinista).
    FOR v_item IN
        SELECT si.id, si.material_id, si.cantidad_tomada
        FROM seguimiento_items si
        WHERE si.seguimiento_id = p_seguimiento_id
        ORDER BY si.material_id
        FOR UPDATE
    LOOP
        v_material_ids := array_append(v_material_ids, v_item.material_id);
        v_tomadas_map := v_tomadas_map || jsonb_build_object(
            v_item.material_id::text, v_item.cantidad_tomada
        );
    END LOOP;

    -- 3. Validar el payload de consumidos (arreglo JSON obligatorio).
    IF p_consumidos IS NULL OR jsonb_typeof(p_consumidos) <> 'array' THEN
        RAISE EXCEPTION 'El payload de consumidos debe ser un arreglo JSON.';
    END IF;

    FOR v_linea IN
        SELECT (elem->>'material_id')::INT AS material_id,
               (elem->>'cantidad_consumida')::INT AS cantidad_consumida
        FROM jsonb_array_elements(p_consumidos) AS elem
    LOOP
        IF v_linea.material_id = ANY(v_vistos) THEN
            RAISE EXCEPTION 'Material ID LISTA % duplicado en la lista de consumidos.', v_linea.material_id;
        END IF;
        v_vistos := array_append(v_vistos, v_linea.material_id);

        IF v_linea.material_id IS NULL OR NOT (v_tomadas_map ? v_linea.material_id::text) THEN
            RAISE EXCEPTION 'Material ID LISTA % no pertenece a este seguimiento.', v_linea.material_id;
        END IF;

        v_tomada := (v_tomadas_map->>v_linea.material_id::text)::INT;

        IF v_linea.cantidad_consumida IS NULL OR v_linea.cantidad_consumida < 0
           OR v_linea.cantidad_consumida > v_tomada THEN
            RAISE EXCEPTION 'Consumo inválido para el material ID LISTA % (máximo %).',
                v_linea.material_id, v_tomada;
        END IF;

        v_consumidos_map := v_consumidos_map || jsonb_build_object(
            v_linea.material_id::text, v_linea.cantidad_consumida
        );
    END LOOP;

    -- 3b. Completitud: TODO material del seguimiento debe reportar su
    --     consumo (sin valores implícitos). Se valida ANTES de tocar el
    --     inventario.
    FOR v_item IN
        SELECT si.material_id FROM seguimiento_items si
        WHERE si.seguimiento_id = p_seguimiento_id
        ORDER BY si.material_id
    LOOP
        IF NOT (v_consumidos_map ? v_item.material_id::text) THEN
            RAISE EXCEPTION 'Falta la cantidad consumida del material ID LISTA %.', v_item.material_id;
        END IF;
    END LOOP;

    -- 4. Bloqueo de las filas de inventario de la unidad (FOR UPDATE, orden
    --    por material_id: cero carreras y cero deadlocks con
    --    fn_procesar_movimiento).
    FOR v_fila_inv IN
        SELECT ie.material_id, ie.stock_actual
        FROM inventario_equipos ie
        WHERE ie.equipo_id = v_seguimiento.equipo_id
          AND ie.material_id = ANY(v_material_ids)
        ORDER BY ie.material_id
        FOR UPDATE
    LOOP
        NULL; -- el bloqueo ya quedó tomado; la lectura ocurre en el paso 5
    END LOOP;

    -- 5. Por cada item: validación de stock, registro del consumido,
    --    descuento DIRECTO del consumido (el remanente no se mueve; SIN
    --    eliminar filas que lleguen a 0) y evento de auditoría por línea.
    FOR v_item IN
        SELECT si.id, si.material_id, si.cantidad_tomada
        FROM seguimiento_items si
        WHERE si.seguimiento_id = p_seguimiento_id
        ORDER BY si.material_id
        FOR UPDATE
    LOOP
        v_consumido := (v_consumidos_map->>v_item.material_id::text)::INT;

        SELECT stock_actual INTO v_stock_actual
        FROM inventario_equipos
        WHERE equipo_id = v_seguimiento.equipo_id AND material_id = v_item.material_id
        FOR UPDATE;

        IF COALESCE(v_stock_actual, 0) < v_consumido THEN
            RAISE EXCEPTION 'Stock insuficiente en la Unidad ID % para el material ID LISTA %. Disponible: %, Consumido: %',
                v_seguimiento.equipo_id, v_item.material_id, COALESCE(v_stock_actual, 0), v_consumido;
        END IF;

        v_nuevo_stock := COALESCE(v_stock_actual, 0) - v_consumido;

        UPDATE seguimiento_items
        SET cantidad_consumida = v_consumido
        WHERE id = v_item.id;

        UPDATE inventario_equipos
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE equipo_id = v_seguimiento.equipo_id AND material_id = v_item.material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, equipo_origen_id, cantidad, resultado, detalles
        ) VALUES (
            p_usuario,
            'SEGUIMIENTO_CERRADO',
            v_item.material_id,
            v_seguimiento.equipo_id,
            v_consumido,
            'EXITO',
            jsonb_build_object(
                'seguimiento_id', p_seguimiento_id,
                'cantidad_tomada', v_item.cantidad_tomada,
                'cantidad_consumida', v_consumido,
                'stock_remanente_equipo', v_nuevo_stock,
                'fecha_cierre', CURRENT_TIMESTAMP,
                'observaciones_cierre', p_observaciones_cierre
            )
        );
    END LOOP;

    -- 6. Cerrar la cabecera.
    UPDATE seguimientos
    SET estado = 'CERRADA', closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    WHERE id = p_seguimiento_id;

    -- 7. ACTA DE CONSUMO: snapshot jsonb persistido en la MISMA transacción.
    SELECT jsonb_build_object(
        'acta_tipo', 'CONSUMO',
        'seguimiento_id', p_seguimiento_id,
        'equipo_id', v_seguimiento.equipo_id,
        'equipo_nombre', (SELECT nombre FROM equipos WHERE equipo_id = v_seguimiento.equipo_id),
        'fecha_apertura', v_seguimiento.fecha,
        'fecha_cierre', CURRENT_TIMESTAMP,
        'usuario', p_usuario,
        'observaciones', v_seguimiento.observaciones,
        'observaciones_cierre', p_observaciones_cierre,
        'items', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'material_id', si.material_id,
                    'codigo', cm.codigo,
                    'descripcion', cm.descripcion,
                    'u_m', cm.u_m,
                    'categoria', c.nombre,
                    'cantidad_tomada', si.cantidad_tomada,
                    'cantidad_consumida', si.cantidad_consumida
                ) ORDER BY si.material_id
            )
            FROM seguimiento_items si
            JOIN catalogo_materiales cm ON cm.id_lista = si.material_id
            LEFT JOIN categorias c ON c.id = cm.categoria_id
            WHERE si.seguimiento_id = p_seguimiento_id
        ), '[]'::jsonb)
    ) INTO v_snapshot_acta;

    INSERT INTO actas_reportes (tipo, seguimiento_id, snapshot)
    VALUES ('CONSUMO', p_seguimiento_id, v_snapshot_acta)
    RETURNING id INTO v_acta_id;

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, equipo_origen_id, resultado, detalles
    ) VALUES (
        p_usuario,
        'ACTA_CONSUMO_GENERADA',
        v_seguimiento.equipo_id,
        'EXITO',
        jsonb_build_object(
            'acta_id', v_acta_id,
            'seguimiento_id', p_seguimiento_id,
            'equipo_id', v_seguimiento.equipo_id,
            'fecha_cierre', CURRENT_TIMESTAMP,
            'observaciones_cierre', p_observaciones_cierre
        )
    );
END;
$$ LANGUAGE plpgsql;

"""

FN_AUDITAR_MATERIAL_ANTERIOR = """

CREATE OR REPLACE FUNCTION fn_auditar_modificacion_material()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.codigo IS DISTINCT FROM NEW.codigo OR
        OLD.descripcion IS DISTINCT FROM NEW.descripcion OR
        OLD.categoria_id IS DISTINCT FROM NEW.categoria_id OR
        OLD.u_m IS DISTINCT FROM NEW.u_m OR
        OLD.stock_minimo IS DISTINCT FROM NEW.stock_minimo OR
        OLD.is_active IS DISTINCT FROM NEW.is_active) THEN

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, resultado, detalles
        ) VALUES (
            CURRENT_USER, 'MATERIAL_MODIFICADO', NEW.id_lista, 'EXITO',
            jsonb_build_object(
                'modulo', 'CATALOGO', 'accion', 'MODIFICAR',
                'valores_anteriores', jsonb_build_object(
                    'codigo', OLD.codigo, 'descripcion', OLD.descripcion,
                    'categoria_id', OLD.categoria_id, 'u_m', OLD.u_m,
                    'stock_minimo', OLD.stock_minimo, 'is_active', OLD.is_active
                ),
                'valores_nuevos', jsonb_build_object(
                    'codigo', NEW.codigo, 'descripcion', NEW.descripcion,
                    'categoria_id', NEW.categoria_id, 'u_m', NEW.u_m,
                    'stock_minimo', NEW.stock_minimo, 'is_active', NEW.is_active
                )
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_auditar_modificacion_material ON catalogo_materiales;
CREATE TRIGGER tg_auditar_modificacion_material
AFTER UPDATE ON catalogo_materiales
FOR EACH ROW EXECUTE FUNCTION fn_auditar_modificacion_material();

"""

# ================================================================
# upgrade() — pasos 1..7 del plan §1 (transaccional; cada paso asume el anterior)
# ================================================================


def upgrade() -> None:
    # ----------------------------------------------------------------
    # Paso 1 — valor_unitario (RF-2/RF-3). DEFAULT 1.000 rellena el
    # catálogo existente (ADD COLUMN con default constante: sin reescritura).
    # ----------------------------------------------------------------
    op.execute(
        sa.text(
            "ALTER TABLE catalogo_materiales "
            "ADD COLUMN valor_unitario NUMERIC(12,3) NOT NULL DEFAULT 1.000"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE catalogo_materiales "
            "ADD CONSTRAINT ck_catalogo_valor_unitario_non_negative "
            "CHECK (valor_unitario >= 0)"
        )
    )

    # ----------------------------------------------------------------
    # Paso 2 — tipos decimales (RF-6). Los CHECK existentes se conservan
    # (PostgreSQL re-coacciona las expresiones de los CHECK al nuevo tipo);
    # DEFAULT 0 se re-declara como 0. auditoria_eventos.cantidad usa cast
    # explícito (condición L2 del dictamen @arq-reviewer; el ALTER TYPE no
    # dispara triggers de fila ni cambia valores — ledger inmutable §2.4).
    # ----------------------------------------------------------------
    op.execute(sa.text("ALTER TABLE inventario_almacen ALTER COLUMN stock_actual TYPE NUMERIC(12,3)"))
    op.execute(sa.text("ALTER TABLE inventario_almacen ALTER COLUMN stock_actual SET DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE inventario_fibra ALTER COLUMN stock_actual TYPE NUMERIC(12,3)"))
    op.execute(sa.text("ALTER TABLE inventario_fibra ALTER COLUMN stock_actual SET DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE inventario_equipos ALTER COLUMN stock_actual TYPE NUMERIC(12,3)"))
    op.execute(sa.text("ALTER TABLE inventario_equipos ALTER COLUMN stock_actual SET DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE movimientos_detalle ALTER COLUMN cantidad TYPE NUMERIC(12,3)"))
    op.execute(sa.text("ALTER TABLE seguimiento_items ALTER COLUMN cantidad_tomada TYPE NUMERIC(12,3)"))
    op.execute(sa.text("ALTER TABLE seguimiento_items ALTER COLUMN cantidad_consumida TYPE NUMERIC(12,3)"))
    op.execute(
        sa.text(
            "ALTER TABLE auditoria_eventos ALTER COLUMN cantidad "
            "TYPE NUMERIC(12,3) USING cantidad::NUMERIC(12,3)"
        )
    )

    # ----------------------------------------------------------------
    # Paso 3 — Fusión del Inventario FO (RF-1/RF-7, plan §1.3).
    # (a) trazabilidad: un evento por material fusionado (INSERT permitido;
    #     el ledger es append-only).
    # ----------------------------------------------------------------
    op.execute(
        sa.text(
            """
INSERT INTO auditoria_eventos (usuario, tipo_accion, material_id, cantidad, resultado, detalles)
SELECT 'migracion-0027', 'FO_UNIFICADO', material_id, SUM(stock_actual), 'OK',
       jsonb_build_object(
         'modulo','Inventario FO',
         'valores_anteriores', jsonb_object_agg(modulo, stock_actual),
         'valores_nuevos', jsonb_build_object('stock_actual', SUM(stock_actual)))
FROM inventario_fibra GROUP BY material_id;
"""
        )
    )

    # (b) agregación y reemplazo de clave
    op.execute(
        sa.text(
            "CREATE TEMP TABLE _fo_agg ON COMMIT DROP AS "
            "SELECT material_id, SUM(stock_actual) AS stock_actual, MAX(updated_at) AS updated_at "
            "FROM inventario_fibra GROUP BY material_id"
        )
    )
    # Suma ANTES de la fusión para la verificación interna (§4.1).
    op.execute(
        sa.text(
            "CREATE TEMP TABLE _fo_antes ON COMMIT DROP AS "
            "SELECT COALESCE(SUM(stock_actual), 0)::NUMERIC AS suma FROM inventario_fibra"
        )
    )
    op.execute(sa.text("DELETE FROM inventario_fibra"))  # tabla de saldo mutable, no ledger
    op.execute(sa.text("ALTER TABLE inventario_fibra DROP CONSTRAINT inventario_fibra_pkey"))
    op.execute(sa.text("ALTER TABLE inventario_fibra DROP CONSTRAINT ck_inventario_fibra_modulo"))
    op.execute(sa.text("ALTER TABLE inventario_fibra DROP COLUMN modulo"))
    op.execute(
        sa.text(
            "ALTER TABLE inventario_fibra ADD CONSTRAINT inventario_fibra_pkey "
            "PRIMARY KEY (material_id)"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO inventario_fibra (material_id, stock_actual, updated_at) "
            "SELECT material_id, stock_actual, updated_at FROM _fo_agg"
        )
    )
    # Índice redundante con la nueva PK (material_id).
    op.execute(sa.text("DROP INDEX ix_inventario_fibra_material"))

    # Verificación interna: SUM antes == SUM después; si difiere, RAISE y la
    # transacción completa revierte (§4.1/§4.3).
    op.execute(
        sa.text(
            """
DO $$
DECLARE
    v_antes NUMERIC;
    v_despues NUMERIC;
BEGIN
    SELECT suma INTO v_antes FROM _fo_antes;
    SELECT COALESCE(SUM(stock_actual), 0) INTO v_despues FROM inventario_fibra;
    IF v_antes <> v_despues THEN
        RAISE EXCEPTION 'Fusión FO 0027 abortada: suma antes (%) <> suma después (%). Transacción completa revertida.', v_antes, v_despues;
    END IF;
END $$;
"""
        )
    )

    # ----------------------------------------------------------------
    # Paso 4 — Sección de ruteo única (RF-1/RF-9). FO_PAQUETE/FO_EN_USO se
    # conservan (referenciadas por movimientos históricos; jamás se borran).
    # ----------------------------------------------------------------
    op.execute(sa.text("ALTER TABLE secciones DROP CONSTRAINT ck_secciones_tipo"))
    op.execute(
        sa.text(
            "ALTER TABLE secciones ADD CONSTRAINT ck_secciones_tipo "
            "CHECK (tipo IN ('GENERAL','FO','FO_PAQUETE','FO_EN_USO'))"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO secciones (nombre, tipo, is_active) "
            "SELECT 'Inventario FO', 'FO', FALSE "
            "WHERE NOT EXISTS (SELECT 1 FROM secciones WHERE nombre = 'Inventario FO')"
        )
    )

    # Paso 4b — continuidad de permisos (D-2): copia los scopes legacy a la
    # sección FO. Idempotente (PK actor_id+almacen_id, ON CONFLICT DO NOTHING).
    op.execute(
        sa.text(
            "INSERT INTO actor_almacen_scopes (actor_id, almacen_id) "
            "SELECT DISTINCT sc.actor_id, fo.almacen_id "
            "FROM actor_almacen_scopes sc "
            "JOIN secciones legacy ON legacy.almacen_id = sc.almacen_id "
            "     AND legacy.tipo IN ('FO_PAQUETE','FO_EN_USO') "
            "CROSS JOIN secciones fo "
            "WHERE fo.tipo = 'FO' AND fo.nombre = 'Inventario FO' "
            "ON CONFLICT DO NOTHING"
        )
    )

    # ----------------------------------------------------------------
    # Paso 5 — stored functions re-publicadas (§1.4) + DROP de firmas
    # anteriores (evita sobrecargas ambiguas).
    # ----------------------------------------------------------------
    op.execute(sa.text(FN_PROCESAR_NUEVA))
    op.execute(sa.text(FN_CANCELAR_NUEVA))
    op.execute(sa.text(FN_CARGAR_STOCK_INICIAL_NUEVA))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cargar_stock_inicial(INT, INT, INT, TEXT)"))
    op.execute(sa.text(FN_CARGAR_STOCK_INICIAL_FIBRA_NUEVA))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cargar_stock_inicial_fibra(TEXT, INT, INT, TEXT)"))
    op.execute(sa.text(FN_AJUSTAR_STOCK_ALMACEN_NUEVA))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_almacen(INT, INT, INT, TEXT)"))
    op.execute(sa.text(FN_AJUSTAR_STOCK_FIBRA_NUEVA))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_fibra(TEXT, INT, INT, TEXT)"))
    op.execute(sa.text(FN_AJUSTAR_STOCK_GENERAL_NUEVA))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_general(INT, INT, TEXT)"))
    op.execute(sa.text(FN_ELIMINAR_INVENTARIO_FIBRA_NUEVA))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_eliminar_inventario_fibra(TEXT, INT, TEXT)"))
    op.execute(sa.text(FN_SUMAR_CANTIDAD_NUEVA))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_sumar_cantidad(TEXT, TEXT, INT, INT, TEXT, TEXT)"))
    op.execute(sa.text(FN_MOVER_MATERIAL_NUEVA))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_mover_material(TEXT, TEXT, TEXT, TEXT, INT, INT, TEXT, TEXT)"))
    op.execute(sa.text(FN_AGREGAR_TODO_NUEVA))
    op.execute(sa.text(FN_CREAR_SEGUIMIENTO_NUEVA))
    op.execute(sa.text(FN_CERRAR_SEGUIMIENTO_NUEVA))
    # fn_generar_acta_entrega NO se re-publica: su snapshot ya serializa
    # md.cantidad vía jsonb_build_object sin cast a entero (sin cambios).

    # ----------------------------------------------------------------
    # Paso 6 — auditoría de valor_unitario (RF-7): función + trigger.
    # ----------------------------------------------------------------
    op.execute(sa.text(FN_AUDITAR_MATERIAL_NUEVA))

    # ----------------------------------------------------------------
    # Paso 7 — fn_valor_total_inventario (RF-4).
    # ----------------------------------------------------------------
    op.execute(sa.text(FN_VALOR_TOTAL_INVENTARIO))


# ================================================================
# downgrade() — reverso 0027 -> 0026 (secuencia L5 del plan §1.7)
# ================================================================

_COLUMNAS_DECIMALES = [
    ("inventario_almacen", "stock_actual"),
    ("inventario_fibra", "stock_actual"),
    ("inventario_equipos", "stock_actual"),
    ("movimientos_detalle", "cantidad"),
    ("seguimiento_items", "cantidad_tomada"),
    ("seguimiento_items", "cantidad_consumida"),
    ("auditoria_eventos", "cantidad"),
]


def downgrade() -> None:
    bind = op.get_bind()

    # 1. ABORTA si existe cualquier valor fraccionario (E14: cero pérdida
    #    silenciosa). ANTES de modificar nada.
    for tabla, columna in _COLUMNAS_DECIMALES:
        hallado = bind.execute(
            sa.text(
                f"SELECT 1 FROM {tabla} "
                f"WHERE {columna} IS NOT NULL AND {columna} <> TRUNC({columna}) "
                f"LIMIT 1"
            )
        ).scalar_one_or_none()
        if hallado is not None:
            raise RuntimeError(
                f"Downgrade 0027 abortado: existen valores fraccionarios en "
                f"{tabla}.{columna}; la reversión a INTEGER perdería decimales "
                "(E14). Corrija los saldos antes de degradar."
            )

    # 1b. ABORTA si movimientos/inventario/scopes referencian la sección
    #     'Inventario FO' (la fila no podría eliminarse sin romper FKs).
    fo_id = bind.execute(
        sa.text("SELECT almacen_id FROM secciones WHERE nombre = 'Inventario FO' AND tipo = 'FO'")
    ).scalar_one_or_none()
    if fo_id is not None:
        # D-2: retira los scopes FO copiados por el upgrade (actores con scope
        # legacy). Un scope concedido directamente a FO sigue bloqueando abajo.
        bind.execute(
            sa.text(
                "DELETE FROM actor_almacen_scopes fo_sc "
                "WHERE fo_sc.almacen_id = :id AND EXISTS ("
                " SELECT 1 FROM actor_almacen_scopes l "
                " JOIN secciones ls ON ls.almacen_id = l.almacen_id "
                "  AND ls.tipo IN ('FO_PAQUETE','FO_EN_USO') "
                " WHERE l.actor_id = fo_sc.actor_id)"
            ),
            {"id": fo_id},
        )
        refs = bind.execute(
            sa.text(
                "SELECT "
                " (SELECT count(*) FROM movimientos_cabecera WHERE origen_almacen_id = :id OR destino_almacen_id = :id)"
                " + (SELECT count(*) FROM movimientos_detalle WHERE origen_almacen_id = :id)"
                " + (SELECT count(*) FROM inventario_almacen WHERE almacen_id = :id)"
                " + (SELECT count(*) FROM actor_almacen_scopes WHERE almacen_id = :id)"
            ),
            {"id": fo_id},
        ).scalar_one()
        if refs:
            raise RuntimeError(
                f"Downgrade 0027 abortado: {refs} referencia(s) a la sección "
                "'Inventario FO' (movimientos/inventario/scopes); el esquema "
                "0026 no puede representarlas."
            )

    # 2. Restaura `modulo` en inventario_fibra con PK (modulo, material_id).
    #    La existencia total se coloca en modulo='PAQUETE'; la partición
    #    original NO se reconstruye (ver docstring).
    op.execute(sa.text("ALTER TABLE inventario_fibra ADD COLUMN modulo VARCHAR(20)"))
    op.execute(sa.text("UPDATE inventario_fibra SET modulo = 'PAQUETE'"))
    op.execute(sa.text("ALTER TABLE inventario_fibra ALTER COLUMN modulo SET NOT NULL"))
    op.execute(sa.text("ALTER TABLE inventario_fibra DROP CONSTRAINT inventario_fibra_pkey"))
    op.execute(
        sa.text(
            "ALTER TABLE inventario_fibra ADD CONSTRAINT ck_inventario_fibra_modulo "
            "CHECK (modulo IN ('PAQUETE','EN_USO'))"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE inventario_fibra ADD CONSTRAINT inventario_fibra_pkey "
            "PRIMARY KEY (modulo, material_id)"
        )
    )
    op.execute(
        sa.text("CREATE INDEX ix_inventario_fibra_material ON inventario_fibra (material_id)")
    )

    # 3. Devuelve las columnas a INTEGER (valores garantizados enteros por el
    #    abort del paso 1). auditoria_eventos con cast explícito.
    op.execute(sa.text("ALTER TABLE inventario_almacen ALTER COLUMN stock_actual TYPE INT"))
    op.execute(sa.text("ALTER TABLE inventario_almacen ALTER COLUMN stock_actual SET DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE inventario_fibra ALTER COLUMN stock_actual TYPE INT"))
    op.execute(sa.text("ALTER TABLE inventario_fibra ALTER COLUMN stock_actual SET DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE inventario_equipos ALTER COLUMN stock_actual TYPE INT"))
    op.execute(sa.text("ALTER TABLE inventario_equipos ALTER COLUMN stock_actual SET DEFAULT 0"))
    op.execute(sa.text("ALTER TABLE movimientos_detalle ALTER COLUMN cantidad TYPE INT"))
    op.execute(sa.text("ALTER TABLE seguimiento_items ALTER COLUMN cantidad_tomada TYPE INT"))
    op.execute(sa.text("ALTER TABLE seguimiento_items ALTER COLUMN cantidad_consumida TYPE INT"))
    op.execute(
        sa.text(
            "ALTER TABLE auditoria_eventos ALTER COLUMN cantidad "
            "TYPE INT USING cantidad::INTEGER"
        )
    )

    # 3b. Re-declaración de los CHECK re-coaccionados por los ALTER TYPE:
    #     PostgreSQL conserva el cast `::numeric` en la expresión tras
    #     devolver la columna a INTEGER; se restaura el texto canónico de
    #     0026 (semántica idéntica, cero deriva de esquema).
    op.execute(sa.text("ALTER TABLE inventario_almacen DROP CONSTRAINT ck_inventario_almacen_non_negative"))
    op.execute(
        sa.text("ALTER TABLE inventario_almacen ADD CONSTRAINT ck_inventario_almacen_non_negative CHECK (stock_actual >= 0)")
    )
    op.execute(sa.text("ALTER TABLE inventario_fibra DROP CONSTRAINT ck_inventario_fibra_non_negative"))
    op.execute(
        sa.text("ALTER TABLE inventario_fibra ADD CONSTRAINT ck_inventario_fibra_non_negative CHECK (stock_actual >= 0)")
    )
    op.execute(sa.text("ALTER TABLE inventario_equipos DROP CONSTRAINT ck_inventario_equipos_non_negative"))
    op.execute(
        sa.text("ALTER TABLE inventario_equipos ADD CONSTRAINT ck_inventario_equipos_non_negative CHECK (stock_actual >= 0)")
    )
    op.execute(sa.text("ALTER TABLE movimientos_detalle DROP CONSTRAINT ck_movimientos_detalle_cantidad"))
    op.execute(
        sa.text("ALTER TABLE movimientos_detalle ADD CONSTRAINT ck_movimientos_detalle_cantidad CHECK (cantidad > 0)")
    )
    op.execute(sa.text("ALTER TABLE seguimiento_items DROP CONSTRAINT ck_seguimiento_items_tomada"))
    op.execute(
        sa.text("ALTER TABLE seguimiento_items ADD CONSTRAINT ck_seguimiento_items_tomada CHECK (cantidad_tomada > 0)")
    )
    op.execute(sa.text("ALTER TABLE seguimiento_items DROP CONSTRAINT ck_seguimiento_items_consumida"))
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items ADD CONSTRAINT ck_seguimiento_items_consumida "
            "CHECK (cantidad_consumida IS NULL OR (cantidad_consumida >= 0 AND cantidad_consumida <= cantidad_tomada))"
        )
    )

    # 4. Restaura ck_secciones_tipo sin 'FO' y elimina la fila de la sección
    #    (referencias ya descartadas en el paso 1b). ORDEN: primero se retira
    #    la fila tipo='FO' y DESPUÉS se añade el CHECK antiguo (la fila lo
    #    violaría si el CHECK se creara antes).
    op.execute(sa.text("ALTER TABLE secciones DROP CONSTRAINT ck_secciones_tipo"))
    op.execute(sa.text("DELETE FROM secciones WHERE nombre = 'Inventario FO' AND tipo = 'FO'"))
    op.execute(
        sa.text(
            "ALTER TABLE secciones ADD CONSTRAINT ck_secciones_tipo "
            "CHECK (tipo IN ('GENERAL','FO_PAQUETE','FO_EN_USO'))"
        )
    )

    # 5. Elimina valor_unitario, su CHECK y fn_valor_total_inventario.
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_valor_total_inventario()"))
    op.execute(
        sa.text(
            "ALTER TABLE catalogo_materiales "
            "DROP CONSTRAINT ck_catalogo_valor_unitario_non_negative"
        )
    )
    op.execute(sa.text("ALTER TABLE catalogo_materiales DROP COLUMN valor_unitario"))

    # 6. AL FINAL (L5): restauración VERBATIM de las funciones vigentes en
    #    0026 (constantes FN_*_ANTERIOR) y del trigger/función de auditoría
    #    previos. La columna `modulo` y los tipos INTEGER ya existen en este
    #    punto, de modo que ninguna función restaurada queda referenciando
    #    objetos inexistentes.
    op.execute(sa.text(FN_PROCESAR_ANTERIOR))
    op.execute(sa.text(FN_CANCELAR_ANTERIOR))
    op.execute(sa.text(FN_CARGAR_INICIAL_ANTERIOR))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cargar_stock_inicial(INT, INT, NUMERIC, TEXT)"))
    op.execute(sa.text(FN_CARGAR_INICIAL_FIBRA_ANTERIOR))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cargar_stock_inicial_fibra(INT, NUMERIC, TEXT)"))
    op.execute(sa.text(FN_AJUSTAR_GENERAL_ANTERIOR))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_general(INT, NUMERIC, TEXT)"))
    op.execute(sa.text(FN_AJUSTAR_ALMACEN_ANTERIOR))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_almacen(INT, INT, NUMERIC, TEXT)"))
    op.execute(sa.text(FN_AJUSTAR_FIBRA_ANTERIOR))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_fibra(INT, NUMERIC, TEXT)"))
    op.execute(sa.text(FN_ELIMINAR_FIBRA_ANTERIOR))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_eliminar_inventario_fibra(INT, TEXT)"))
    op.execute(sa.text(FN_SUMAR_ANTERIOR))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_sumar_cantidad(TEXT, INT, NUMERIC, TEXT, TEXT)"))
    op.execute(sa.text(FN_MOVER_ANTERIOR))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_mover_material(TEXT, TEXT, INT, NUMERIC, TEXT, TEXT)"))
    op.execute(sa.text(FN_AGREGAR_TODO_ANTERIOR))
    op.execute(sa.text(FN_CREAR_SEGUIMIENTO_ANTERIOR))
    # FN_CERRAR_ANTERIOR es la copia literal de 0025 (CREATE FUNCTION plano):
    # como 0025, se DROP la firma vigente antes de recrearla.
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cerrar_seguimiento(INT, JSONB, TEXT, TEXT)"))
    op.execute(sa.text(FN_CERRAR_ANTERIOR))
    op.execute(sa.text(FN_AUDITAR_MATERIAL_ANTERIOR))

    # 7. Los eventos FO_UNIFICADO ya emitidos PERMANECEN (ledger inmutable).
