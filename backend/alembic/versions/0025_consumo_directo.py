"""Inversión de la lógica de consumo — cambio 2026-10-12-inversion-consumo.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-12

El cierre de un seguimiento registra lo CONSUMIDO (no el sobrante):

* `seguimiento_items.cantidad_consumida` pasa de columna GENERADA
  (`tomada - sobrante`) a columna REAL con CHECK 0 <= consumida <= tomada;
  `cantidad_sobrante` y `ck_seguimiento_items_sobrante` se eliminan.
  Backfill: los seguimientos cerrados conservan su consumido
  (`tomada - sobrante`); los ABIERTOS quedan en NULL.
* `fn_cerrar_seguimiento(p_seguimiento_id, p_sobrantes, ...)` se reemplaza
  (DROP + CREATE: cambia el nombre del parámetro) por
  `fn_cerrar_seguimiento(p_seguimiento_id, p_consumidos, ...)`: descuenta
  DIRECTAMENTE lo consumido, exige una línea por material y valida todo
  antes de tocar el inventario. El remanente no se mueve.

El ledger inmutable (`auditoria_eventos`, `actas_reportes`; Constitución
2.4) NO se modifica: los registros históricos conservan su clave antigua.

downgrade() — reverso exacto 0025 -> 0024: restaura la columna sobrante
(`tomada - consumida`), la columna generada, el CHECK original y la función
de 0024 (verbatim).
"""

from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


FN_CERRAR_NUEVA = """
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

FN_CERRAR_0024 = """
CREATE OR REPLACE FUNCTION public.fn_cerrar_seguimiento(p_seguimiento_id integer, p_sobrantes jsonb, p_usuario text, p_observaciones_cierre text DEFAULT NULL::text)
 RETURNS void
 LANGUAGE plpgsql
AS $$
DECLARE
    v_seguimiento RECORD;
    v_item RECORD;
    v_linea RECORD;
    v_fila_inv RECORD;
    v_visto_sobrantes INT[] := '{}';
    v_material_ids INT[] := '{}';
    v_tomadas_map JSONB := '{}'::jsonb;
    v_sobrantes_map JSONB := '{}'::jsonb;
    v_sobrante INT;
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

    -- 2. Cargar items del seguimiento ORDENADOS por material_id (orden de
    --    bloqueo determinista) y recolectar los material_id.
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

    -- 3. Validar el payload de sobrantes (arreglo JSON). Las líneas omitidas
    --    se cierran con cantidad_sobrante = 0.
    IF p_sobrantes IS NOT NULL THEN
        IF jsonb_typeof(p_sobrantes) <> 'array' THEN
            RAISE EXCEPTION 'El payload de sobrantes debe ser un arreglo JSON.';
        END IF;

        FOR v_linea IN
            SELECT (elem->>'material_id')::INT AS material_id,
                   (elem->>'cantidad_sobrante')::INT AS cantidad_sobrante
            FROM jsonb_array_elements(p_sobrantes) AS elem
        LOOP
            IF v_linea.material_id = ANY(v_visto_sobrantes) THEN
                RAISE EXCEPTION 'Material ID LISTA % duplicado en la lista de sobrantes.', v_linea.material_id;
            END IF;
            v_visto_sobrantes := array_append(v_visto_sobrantes, v_linea.material_id);

            IF v_linea.material_id IS NULL OR NOT (v_tomadas_map ? v_linea.material_id::text) THEN
                RAISE EXCEPTION 'Material ID LISTA % no pertenece a este seguimiento.', v_linea.material_id;
            END IF;

            v_tomada := (v_tomadas_map->>v_linea.material_id::text)::INT;

            IF v_linea.cantidad_sobrante IS NULL OR v_linea.cantidad_sobrante < 0
               OR v_linea.cantidad_sobrante > v_tomada THEN
                RAISE EXCEPTION 'Sobrante inválido para el material ID LISTA % (máximo %).',
                    v_linea.material_id, v_tomada;
            END IF;

            v_sobrantes_map := v_sobrantes_map || jsonb_build_object(
                v_linea.material_id::text, v_linea.cantidad_sobrante
            );
        END LOOP;
    END IF;

    -- 4. Bloqueo de las filas de inventario del equipo (FOR UPDATE,
    --    orden por material_id: cero condiciones de carrera y cero
    --    deadlocks con fn_procesar_movimiento).
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

    -- 5. Por cada item: sobrante (default 0), consumido, validación de
    --    stock del equipo, UPDATE del item (materializa la columna
    --    GENERATED), descuento del inventario (SIN eliminar filas que
    --    lleguen a 0) y evento de auditoría por línea.
    FOR v_item IN
        SELECT si.id, si.material_id, si.cantidad_tomada
        FROM seguimiento_items si
        WHERE si.seguimiento_id = p_seguimiento_id
        ORDER BY si.material_id
        FOR UPDATE
    LOOP
        v_sobrante := COALESCE((v_sobrantes_map->>v_item.material_id::text)::INT, 0);
        v_consumido := v_item.cantidad_tomada - v_sobrante;

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
        SET cantidad_sobrante = v_sobrante
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
                'cantidad_sobrante', v_sobrante,
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

    -- 7. ACTA DE CONSUMO (REQ-P2-CON-005, REQ-P2-REP-004): snapshot jsonb
    --    persistido en la MISMA transacción del cierre. CANT. = cantidad
    --    consumida (tomada - sobrante), calculada en SQL (la columna
    --    GENERATED la materializa y el snapshot la lee de ahí).
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
                    'cantidad_sobrante', COALESCE(si.cantidad_sobrante, 0),
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
$$
"""


def upgrade() -> None:
    op.execute(sa.text("ALTER TABLE seguimiento_items ADD COLUMN cantidad_consumida_n INT"))
    op.execute(
        sa.text(
            "UPDATE seguimiento_items "
            "SET cantidad_consumida_n = cantidad_tomada - cantidad_sobrante "
            "WHERE cantidad_sobrante IS NOT NULL"
        )
    )
    op.execute(sa.text("ALTER TABLE seguimiento_items DROP CONSTRAINT ck_seguimiento_items_sobrante"))
    op.execute(sa.text("ALTER TABLE seguimiento_items DROP COLUMN cantidad_consumida"))
    op.execute(sa.text("ALTER TABLE seguimiento_items DROP COLUMN cantidad_sobrante"))
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items "
            "RENAME COLUMN cantidad_consumida_n TO cantidad_consumida"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items ADD CONSTRAINT ck_seguimiento_items_consumida "
            "CHECK (cantidad_consumida IS NULL OR "
            "(cantidad_consumida >= 0 AND cantidad_consumida <= cantidad_tomada))"
        )
    )
    op.execute(sa.text("DROP FUNCTION fn_cerrar_seguimiento(INT, JSONB, TEXT, TEXT)"))
    op.execute(sa.text(FN_CERRAR_NUEVA))


def downgrade() -> None:
    op.execute(sa.text("DROP FUNCTION fn_cerrar_seguimiento(INT, JSONB, TEXT, TEXT)"))
    op.execute(sa.text("ALTER TABLE seguimiento_items ADD COLUMN cantidad_sobrante INT"))
    op.execute(
        sa.text(
            "UPDATE seguimiento_items "
            "SET cantidad_sobrante = cantidad_tomada - cantidad_consumida "
            "WHERE cantidad_consumida IS NOT NULL"
        )
    )
    op.execute(sa.text("ALTER TABLE seguimiento_items DROP CONSTRAINT ck_seguimiento_items_consumida"))
    op.execute(sa.text("ALTER TABLE seguimiento_items DROP COLUMN cantidad_consumida"))
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items ADD COLUMN cantidad_consumida INT "
            "GENERATED ALWAYS AS (cantidad_tomada - cantidad_sobrante) STORED"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items ADD CONSTRAINT ck_seguimiento_items_sobrante "
            "CHECK (cantidad_sobrante IS NULL OR "
            "(cantidad_sobrante >= 0 AND cantidad_sobrante <= cantidad_tomada))"
        )
    )
    op.execute(sa.text(FN_CERRAR_0024))
