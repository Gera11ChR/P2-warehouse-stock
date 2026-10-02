"""Actas de Entrega y Consumo: registro, snapshot jsonb y eventos (T1.6)

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-02

Fase 1 (Base de Datos) del cambio 2026-10-01-reportes-consumo-management
(REQ-P2-CON-005, REQ-P2-REP-003/004). Persistencia de los DOS hitos:

1) `actas_reportes` — registro persistente de actas (append-only por
   convención de dominio). Cada fila guarda un SNAPSHOT jsonb del estado
   EN EL MOMENTO DEL EVENTO; el XLSX (Fase 2) se genera bajo demanda a
   partir de ese snapshot, nunca del stock mutable actual:
     * tipo 'ENTREGA'  -> movimiento_id (TEAMS confirmado).
     * tipo 'CONSUMO'  -> seguimiento_id (seguimiento cerrado).
   CK ck_actas_extremos garantiza exactamente una referencia según el tipo.

2) `fn_cerrar_seguimiento` EXTENDIDO (sustituye a la versión 0016):
   tras cerrar la cabecera persiste el Acta de Consumo en la MISMA
   transacción SQL del cierre:
     * cantidad_consumida = cantidad_tomada - cantidad_sobrante calculada
       en SQL (la columna GENERATED de seguimiento_items ya la
       materializa; el snapshot la toma de ahí).
     * snapshot jsonb con cabecera (equipo, fechas, usuario,
       observaciones) y líneas completas (material, código, descripción,
       U.M., categoría, tomada, sobrante, consumida).
     * evento de auditoría `ACTA_CONSUMO_GENERADA`.
   Los eventos por línea `SEGUIMIENTO_CERRADO` se conservan (granularidad
   histórica del ledger) y la semántica de stock del cierre es IDÉNTICA a
   la versión 0016 (descuento de consumido sobre inventario_equipos bajo
   FOR UPDATE, rollback total ante cualquier fallo).

3) Acta de Entrega (REQ-P2-REP-003): trigger `tg_acta_entrega` sobre
   `movimientos_cabecera` — AFTER UPDATE OF estado, transición a
   'CONFIRMADO' con tipo TEAMS. El registro del acta ocurre en la MISMA
   TRANSACCIÓN SQL de la confirmación (fn_procesar_movimiento), NUNCA
   como paso HTTP posterior en FastAPI:
     * ESTADO TRANSACCIONAL REAL (verificado en T1.1 sobre el esquema de
       PostgreSQL 18.6): la máquina de estados de movimientos_cabecera es
       BORRADOR -> CONFIRMADO -> CANCELADO (CK ck_movimientos_cabecera_estado).
       'COMPLETED' NO EXISTE en el esquema real; el trigger usa
       'CONFIRMADO'. El contrato maestro se alinea a este nombre (Fase 2).
     * snapshot jsonb: cabecera (usuario, observaciones, fechas), origen
       (sección), equipo destino e items con catálogo (código,
       descripción, U.M., categoría, cantidad).
     * evento de auditoría `ACTA_ENTREGA_GENERADA`.
     * Los movimientos DEVOL no generan acta (solo TEAMS).
     * La cancelación posterior del movimiento NO elimina la acta: el
       snapshot permanece como registro histórico inmutable del evento de
       entrega.

Taxonomía verificada en T1.1: los nuevos tipos de evento
(SUMA_CANTIDAD, MOVIMIENTO_INVENTARIO, AGREGAR_TODO,
ACTA_ENTREGA_GENERADA, ACTA_CONSUMO_GENERADA, SEGUIMIENTO_CREADO,
SEGUIMIENTO_CERRADO) no colisionan con los 17 tipos existentes.

downgrade() — reverso exacto 0020 -> 0019: DROP del trigger y de la
función del trigger, restauración VERBATIM de fn_cerrar_seguimiento a la
versión 0016 (sin acta) y DROP de actas_reportes (los snapshots se
pierden al degradar; los eventos de auditoría emitidos permanecen en el
ledger como evidencia histórica).
"""

from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # A) REGISTRO DE ACTAS (Entrega / Consumo) con snapshot jsonb
    # ================================================================
    op.execute(
        sa.text(
            """
CREATE TABLE IF NOT EXISTS actas_reportes (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(20) NOT NULL,
    movimiento_id INT,
    seguimiento_id INT,
    snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_actas_reportes_tipo CHECK (tipo IN ('ENTREGA','CONSUMO')),
    CONSTRAINT ck_actas_reportes_extremos CHECK (
        (tipo = 'ENTREGA' AND movimiento_id IS NOT NULL AND seguimiento_id IS NULL)
        OR
        (tipo = 'CONSUMO' AND seguimiento_id IS NOT NULL AND movimiento_id IS NULL)
    ),
    CONSTRAINT fk_actas_reportes_movimiento FOREIGN KEY (movimiento_id)
        REFERENCES movimientos_cabecera(id) ON DELETE RESTRICT,
    CONSTRAINT fk_actas_reportes_seguimiento FOREIGN KEY (seguimiento_id)
        REFERENCES seguimientos(id) ON DELETE RESTRICT
)
"""
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_actas_reportes_tipo_created "
            "ON actas_reportes (tipo, created_at)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_actas_reportes_seguimiento "
            "ON actas_reportes (seguimiento_id)"
        )
    )

    # ================================================================
    # B) FN_CERRAR_SEGUIMIENTO EXTENDIDO — cierre + Acta de Consumo
    #    (REQ-P2-CON-005, REQ-P2-REP-004)
    # ================================================================
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_cerrar_seguimiento (
    p_seguimiento_id INT,
    p_sobrantes JSONB,
    p_usuario TEXT,
    p_observaciones_cierre TEXT DEFAULT NULL
)
RETURNS VOID AS $$
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
            RAISE EXCEPTION 'Stock insuficiente en el Equipo ID % para el material ID LISTA %. Disponible: %, Consumido: %',
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
$$ LANGUAGE plpgsql;
"""
        )
    )

    # ================================================================
    # C) ACTA DE ENTREGA — trigger en la MISMA transacción SQL de la
    #    confirmación TEAMS (REQ-P2-REP-003)
    # ================================================================
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_generar_acta_entrega()
RETURNS TRIGGER AS $$
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
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_acta_entrega ON movimientos_cabecera;
CREATE TRIGGER tg_acta_entrega
AFTER UPDATE OF estado ON movimientos_cabecera
FOR EACH ROW
WHEN (
    NEW.estado = 'CONFIRMADO'
    AND NEW.tipo_movimiento = 'TEAMS'
    AND OLD.estado IS DISTINCT FROM NEW.estado
)
EXECUTE FUNCTION fn_generar_acta_entrega();
"""
        )
    )


def downgrade() -> None:
    # Reverso exacto 0020 -> 0019 (ver docstring del módulo).

    # 1. Trigger y función del Acta de Entrega (orden inverso de
    #    dependencias).
    op.execute(sa.text("DROP TRIGGER IF EXISTS tg_acta_entrega ON movimientos_cabecera"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_generar_acta_entrega()"))

    # 2. Restauración VERBATIM de fn_cerrar_seguimiento a la versión 0016
    #    (sin persistencia de acta).
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_cerrar_seguimiento (
    p_seguimiento_id INT,
    p_sobrantes JSONB,
    p_usuario TEXT,
    p_observaciones_cierre TEXT DEFAULT NULL
)
RETURNS VOID AS $$
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
BEGIN
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

    FOR v_fila_inv IN
        SELECT ie.material_id, ie.stock_actual
        FROM inventario_equipos ie
        WHERE ie.equipo_id = v_seguimiento.equipo_id
          AND ie.material_id = ANY(v_material_ids)
        ORDER BY ie.material_id
        FOR UPDATE
    LOOP
        NULL;
    END LOOP;

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
            RAISE EXCEPTION 'Stock insuficiente en el Equipo ID % para el material ID LISTA %. Disponible: %, Consumido: %',
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

    UPDATE seguimientos
    SET estado = 'CERRADA', closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    WHERE id = p_seguimiento_id;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )

    # 3. Registro de actas (los eventos de auditoría emitidos permanecen
    #    en el ledger como evidencia histórica).
    op.execute(sa.text("DROP TABLE IF EXISTS actas_reportes"))
