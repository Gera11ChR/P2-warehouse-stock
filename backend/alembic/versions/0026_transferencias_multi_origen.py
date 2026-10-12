"""Transferencias multi-origen — cambio 2026-10-12-transferencias-multi-origen.

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-12

Un movimiento TEAMS puede combinar líneas de Inventario General y de Fibra
Óptica: cada línea conserva su sección de ORIGEN.

* `movimientos_detalle.origen_almacen_id` (FK secciones) con backfill desde
  la cabecera. `movimientos_cabecera.origen_almacen_id` pasa a ser NULL
  cuando el carrito es mixto (CHECK relajado: TEAMS exige solo destino).
* `fn_procesar_movimiento` y `fn_cancelar_movimiento` resuelven el origen
  POR LÍNEA (inventario_almacen o inventario_fibra por módulo) y toman los
  bloqueos FOR UPDATE en orden determinista (origen, material).
* `fn_generar_acta_entrega`: UNA acta (folio único) por operación con el
  origen de cada línea y la lista de orígenes distintos.

El ledger inmutable NO se modifica (§2.4).

downgrade() — reverso exacto 0026 -> 0025: ABORTA si existe un movimiento
TEAMS mixto (cabecera sin origen), que el esquema anterior no puede
representar; si no, restaura las 3 funciones (verbatim de 0025), el CHECK y
elimina la columna.
"""

from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

CK_NUEVO = (
    "(tipo_movimiento = 'TEAMS' AND destino_equipo_id IS NOT NULL) "
    "OR (tipo_movimiento = 'DEVOL' AND origen_equipo_id IS NOT NULL AND destino_almacen_id IS NOT NULL)"
)
CK_VIEJO = (
    "(tipo_movimiento = 'TEAMS' AND origen_almacen_id IS NOT NULL AND destino_equipo_id IS NOT NULL) "
    "OR (tipo_movimiento = 'DEVOL' AND origen_equipo_id IS NOT NULL AND destino_almacen_id IS NOT NULL)"
)

FN_PROCESAR_NUEVA = """
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

FN_CANCELAR_NUEVA = """
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

FN_ACTA_NUEVA = """
CREATE OR REPLACE FUNCTION fn_generar_acta_entrega()
RETURNS TRIGGER AS $$
DECLARE
    v_snapshot JSONB;
    v_acta_id INT;
    v_origenes JSONB;
    v_origen_ids JSONB;
BEGIN
    -- Orígenes DISTINTOS de la operación (0026): una sola acta (folio único)
    -- ampara toda la transferencia, aunque combine General y Fibra Óptica.
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
               'almacen_id', s.almacen_id, 'nombre', s.nombre, 'tipo', s.tipo
           ) ORDER BY s.almacen_id), '[]'::jsonb),
           COALESCE(jsonb_agg(s.almacen_id ORDER BY s.almacen_id), '[]'::jsonb)
    INTO v_origenes, v_origen_ids
    FROM secciones s
    WHERE s.almacen_id IN (
        SELECT DISTINCT COALESCE(md.origen_almacen_id, NEW.origen_almacen_id)
        FROM movimientos_detalle md
        WHERE md.movimiento_id = NEW.id
    );

    -- Snapshot del estado EN ESTE INSTANTE (misma transacción de la
    -- confirmación): cabecera + origen(es) + unidad destino + líneas con
    -- catálogo y origen propio. El XLSX se genera bajo demanda desde este
    -- snapshot; nunca desde el stock mutable actual.
    SELECT jsonb_build_object(
        'acta_tipo', 'ENTREGA',
        'movimiento_id', NEW.id,
        'tipo_movimiento', NEW.tipo_movimiento,
        'usuario', NEW.usuario,
        'observaciones', NEW.observaciones,
        'fecha_confirmacion', CURRENT_TIMESTAMP,
        'fecha_creacion', NEW.created_at,
        'origen', (
            SELECT jsonb_build_object(
                'almacen_id', s.almacen_id,
                'nombre', s.nombre,
                'tipo', s.tipo
            )
            FROM secciones s
            WHERE s.almacen_id = NEW.origen_almacen_id
        ),
        'origenes', v_origenes,
        'destino_equipo', (
            SELECT jsonb_build_object(
                'equipo_id', e.equipo_id,
                'nombre', e.nombre
            )
            FROM equipos e
            WHERE e.equipo_id = NEW.destino_equipo_id
        ),
        'items', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'material_id', md.material_id,
                    'codigo', cm.codigo,
                    'descripcion', cm.descripcion,
                    'u_m', cm.u_m,
                    'categoria', c.nombre,
                    'cantidad', md.cantidad,
                    'origen', (
                        SELECT jsonb_build_object(
                            'almacen_id', so.almacen_id,
                            'nombre', so.nombre,
                            'tipo', so.tipo
                        )
                        FROM secciones so
                        WHERE so.almacen_id = COALESCE(md.origen_almacen_id, NEW.origen_almacen_id)
                    )
                ) ORDER BY md.material_id
            )
            FROM movimientos_detalle md
            JOIN catalogo_materiales cm ON cm.id_lista = md.material_id
            LEFT JOIN categorias c ON c.id = cm.categoria_id
            WHERE md.movimiento_id = NEW.id
        ), '[]'::jsonb)
    ) INTO v_snapshot;

    INSERT INTO actas_reportes (tipo, movimiento_id, snapshot)
    VALUES ('ENTREGA', NEW.id, v_snapshot)
    RETURNING id INTO v_acta_id;

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, equipo_destino_id, almacen_origen_id, resultado, detalles
    ) VALUES (
        COALESCE(NULLIF(current_setting('app.actor', true), ''), NEW.usuario, CURRENT_USER),
        'ACTA_ENTREGA_GENERADA',
        NEW.destino_equipo_id,
        NEW.origen_almacen_id,
        'EXITO',
        jsonb_build_object(
            'acta_id', v_acta_id,
            'movimiento_id', NEW.id,
            'usuario', NEW.usuario,
            'fecha_confirmacion', CURRENT_TIMESTAMP,
            'origen_almacen_ids', v_origen_ids
        )
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

FN_PROCESAR_0025 = """
CREATE OR REPLACE FUNCTION public.fn_procesar_movimiento(p_movimiento_id integer)
 RETURNS void
 LANGUAGE plpgsql
AS $$
DECLARE
    v_rec RECORD;
    v_cabecera RECORD;
    v_stock_disponible INT;
    v_stock_minimo INT;
    v_alerta_stock BOOLEAN := FALSE;
    v_nuevo_stock_origen INT;
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

    -- Resolución UNA VEZ de los tipos de sección origen/destino (ruteo
    -- aditivo FO: las secciones FO_PAQUETE/FO_EN_USO redirigen a
    -- inventario_fibra; son manejadores de ruteo, no inventario físico).
    SELECT tipo INTO v_origen_tipo
    FROM secciones
    WHERE almacen_id = v_cabecera.origen_almacen_id;

    SELECT tipo INTO v_destino_tipo
    FROM secciones
    WHERE almacen_id = v_cabecera.destino_almacen_id;

    FOR v_rec IN SELECT md.*, cm.stock_minimo
                 FROM movimientos_detalle md
                 JOIN catalogo_materiales cm ON cm.id_lista = md.material_id
                 WHERE md.movimiento_id = p_movimiento_id LOOP

        v_stock_minimo := v_rec.stock_minimo;
        v_alerta_stock := FALSE;
        v_modulo := NULL;

        IF v_cabecera.tipo_movimiento = 'TEAMS' THEN
            IF v_origen_tipo = 'GENERAL' THEN
                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_almacen
                WHERE almacen_id = v_cabecera.origen_almacen_id AND material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en Origen (Sección ID %) para el material ID LISTA %. Disponible: %, Solicitado: %',
                        v_cabecera.origen_almacen_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                v_nuevo_stock_origen := v_stock_disponible - v_rec.cantidad;

                IF v_nuevo_stock_origen <= v_stock_minimo THEN
                    v_alerta_stock := TRUE;
                END IF;

                UPDATE inventario_almacen
                SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_cabecera.origen_almacen_id AND material_id = v_rec.material_id;

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
                RAISE EXCEPTION 'La sección ID % no es un origen válido para movimientos TEAMS.', v_cabecera.origen_almacen_id;
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
            v_rec.material_id, v_cabecera.origen_equipo_id, v_cabecera.destino_equipo_id, v_cabecera.origen_almacen_id, v_cabecera.destino_almacen_id, v_rec.cantidad,
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
$$
"""

FN_CANCELAR_0025 = """
CREATE OR REPLACE FUNCTION public.fn_cancelar_movimiento(p_movimiento_id integer, p_motivo text DEFAULT 'Reversión manual por cancelación'::text)
 RETURNS void
 LANGUAGE plpgsql
AS $$
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

    -- Resolución UNA VEZ de los tipos de sección origen/destino (ruteo
    -- aditivo FO, espejo de fn_procesar_movimiento).
    SELECT tipo INTO v_origen_tipo
    FROM secciones
    WHERE almacen_id = v_cabecera.origen_almacen_id;

    SELECT tipo INTO v_destino_tipo
    FROM secciones
    WHERE almacen_id = v_cabecera.destino_almacen_id;

    FOR v_rec IN SELECT * FROM movimientos_detalle WHERE movimiento_id = p_movimiento_id LOOP

        v_modulo := NULL;

        -- REVERSIÓN TEAMS (Devuelve el stock del equipo al almacén origen)
        IF v_cabecera.tipo_movimiento = 'TEAMS' THEN

            -- A. Validar y bloquear stock en el equipo destino
            SELECT stock_actual INTO v_stock_disponible
            FROM inventario_equipos
            WHERE equipo_id = v_cabecera.destino_equipo_id AND material_id = v_rec.material_id
            FOR UPDATE;

            IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                RAISE EXCEPTION 'Stock insuficiente en la Unidad destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                    v_cabecera.destino_equipo_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
            END IF;

            -- B. Descontar de equipo destino
            UPDATE inventario_equipos
            SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.destino_equipo_id AND material_id = v_rec.material_id;

            -- C. Sumar al origen (GENERAL -> inventario_almacen; FO -> inventario_fibra)
            IF v_origen_tipo = 'GENERAL' THEN
                UPDATE inventario_almacen
                SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_cabecera.origen_almacen_id AND material_id = v_rec.material_id;

            ELSIF v_origen_tipo IN ('FO_PAQUETE','FO_EN_USO') THEN
                v_modulo := CASE WHEN v_origen_tipo = 'FO_PAQUETE' THEN 'PAQUETE' ELSE 'EN_USO' END;

                UPDATE inventario_fibra
                SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE modulo = v_modulo AND material_id = v_rec.material_id;
            END IF;

        -- REVERSIÓN DEVOL (Devuelve el stock del almacén destino al equipo origen)
        ELSIF v_cabecera.tipo_movimiento = 'DEVOL' THEN

            -- A. Validar y bloquear stock en el destino (GENERAL -> inventario_almacen;
            --    FO -> inventario_fibra). Mensaje histórico intacto.
            IF v_destino_tipo = 'GENERAL' THEN
                SELECT stock_actual INTO v_stock_disponible
                FROM inventario_almacen
                WHERE almacen_id = v_cabecera.destino_almacen_id AND material_id = v_rec.material_id
                FOR UPDATE;

                IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                    RAISE EXCEPTION 'Stock insuficiente en el Almacén destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                        v_cabecera.destino_almacen_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
                END IF;

                -- B. Descontar de almacén destino
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

                -- B. Descontar del inventario FO destino
                UPDATE inventario_fibra
                SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE modulo = v_modulo AND material_id = v_rec.material_id;
            END IF;

            -- C. Sumar a equipo origen
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
            v_rec.material_id, v_cabecera.origen_equipo_id, v_cabecera.destino_equipo_id, v_cabecera.origen_almacen_id, v_cabecera.destino_almacen_id, v_rec.cantidad,
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
$$
"""

FN_ACTA_0025 = """
CREATE OR REPLACE FUNCTION public.fn_generar_acta_entrega()
 RETURNS trigger
 LANGUAGE plpgsql
AS $$
DECLARE
    v_snapshot JSONB;
    v_acta_id INT;
BEGIN
    -- Snapshot del estado EN ESTE INSTANTE (misma transacción de la
    -- confirmación): cabecera + origen + equipo destino + líneas con
    -- catálogo. El XLSX (Fase 2) se genera bajo demanda desde este
    -- snapshot; nunca desde el stock mutable actual.
    SELECT jsonb_build_object(
        'acta_tipo', 'ENTREGA',
        'movimiento_id', NEW.id,
        'tipo_movimiento', NEW.tipo_movimiento,
        'usuario', NEW.usuario,
        'observaciones', NEW.observaciones,
        'fecha_confirmacion', CURRENT_TIMESTAMP,
        'fecha_creacion', NEW.created_at,
        'origen', (
            SELECT jsonb_build_object(
                'almacen_id', s.almacen_id,
                'nombre', s.nombre,
                'tipo', s.tipo
            )
            FROM secciones s
            WHERE s.almacen_id = NEW.origen_almacen_id
        ),
        'destino_equipo', (
            SELECT jsonb_build_object(
                'equipo_id', e.equipo_id,
                'nombre', e.nombre
            )
            FROM equipos e
            WHERE e.equipo_id = NEW.destino_equipo_id
        ),
        'items', COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'material_id', md.material_id,
                    'codigo', cm.codigo,
                    'descripcion', cm.descripcion,
                    'u_m', cm.u_m,
                    'categoria', c.nombre,
                    'cantidad', md.cantidad
                ) ORDER BY md.material_id
            )
            FROM movimientos_detalle md
            JOIN catalogo_materiales cm ON cm.id_lista = md.material_id
            LEFT JOIN categorias c ON c.id = cm.categoria_id
            WHERE md.movimiento_id = NEW.id
        ), '[]'::jsonb)
    ) INTO v_snapshot;

    INSERT INTO actas_reportes (tipo, movimiento_id, snapshot)
    VALUES ('ENTREGA', NEW.id, v_snapshot)
    RETURNING id INTO v_acta_id;

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, equipo_destino_id, almacen_origen_id, resultado, detalles
    ) VALUES (
        COALESCE(NULLIF(current_setting('app.actor', true), ''), NEW.usuario, CURRENT_USER),
        'ACTA_ENTREGA_GENERADA',
        NEW.destino_equipo_id,
        NEW.origen_almacen_id,
        'EXITO',
        jsonb_build_object(
            'acta_id', v_acta_id,
            'movimiento_id', NEW.id,
            'usuario', NEW.usuario,
            'fecha_confirmacion', CURRENT_TIMESTAMP
        )
    );

    RETURN NEW;
END;
$$
"""


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE movimientos_detalle ADD COLUMN origen_almacen_id INT"))
    op.execute(
        sa.text(
            "ALTER TABLE movimientos_detalle ADD CONSTRAINT fk_movimientos_detalle_origen "
            "FOREIGN KEY (origen_almacen_id) REFERENCES secciones (almacen_id) ON DELETE RESTRICT"
        )
    )
    op.execute(
        sa.text("CREATE INDEX ix_movimientos_detalle_origen ON movimientos_detalle (origen_almacen_id)")
    )
    op.execute(
        sa.text(
            "UPDATE movimientos_detalle d SET origen_almacen_id = c.origen_almacen_id "
            "FROM movimientos_cabecera c "
            "WHERE d.movimiento_id = c.id AND c.tipo_movimiento = 'TEAMS'"
        )
    )
    op.execute(sa.text("ALTER TABLE movimientos_cabecera DROP CONSTRAINT ck_movimientos_cabecera_extremos"))
    op.execute(
        sa.text(
            f"ALTER TABLE movimientos_cabecera ADD CONSTRAINT ck_movimientos_cabecera_extremos CHECK ({CK_NUEVO})"
        )
    )
    op.execute(sa.text(FN_PROCESAR_NUEVA))
    op.execute(sa.text(FN_CANCELAR_NUEVA))
    op.execute(sa.text(FN_ACTA_NUEVA))


def downgrade() -> None:
    mixtos = op.get_bind().execute(
        sa.text(
            "SELECT count(*) FROM movimientos_cabecera "
            "WHERE tipo_movimiento = 'TEAMS' AND origen_almacen_id IS NULL"
        )
    ).scalar_one()
    if mixtos:
        raise RuntimeError(
            f"Downgrade abortado: existen {mixtos} movimiento(s) TEAMS mixto(s) "
            "(cabecera sin origen) que el esquema 0025 no puede representar."
        )
    op.execute(sa.text(FN_PROCESAR_0025))
    op.execute(sa.text(FN_CANCELAR_0025))
    op.execute(sa.text(FN_ACTA_0025))
    op.execute(sa.text("ALTER TABLE movimientos_cabecera DROP CONSTRAINT ck_movimientos_cabecera_extremos"))
    op.execute(
        sa.text(
            f"ALTER TABLE movimientos_cabecera ADD CONSTRAINT ck_movimientos_cabecera_extremos CHECK ({CK_VIEJO})"
        )
    )
    op.execute(sa.text("DROP INDEX ix_movimientos_detalle_origen"))
    op.execute(sa.text("ALTER TABLE movimientos_detalle DROP CONSTRAINT fk_movimientos_detalle_origen"))
    op.execute(sa.text("ALTER TABLE movimientos_detalle DROP COLUMN origen_almacen_id"))
