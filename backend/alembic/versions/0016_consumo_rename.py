"""Renombre físico DESPLIEGUE -> CONSUMO/seguimiento (T1.2)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-02

Fase 1 (Base de Datos) del cambio 2026-10-01-reportes-consumo-management
(propuesta aprobada, REQ-P2-CON-001). Renombre físico COMPLETO de la
nomenclatura DESPLIEGUE hacia el dominio CONSUMO (entidad de BD/API:
"seguimiento"), cubriendo TODOS los objetos dependientes identificados en
la inspección T1.1 del esquema real (PostgreSQL 18.6):

  * Tablas:      despliegues -> seguimientos;
                 despliegue_items -> seguimiento_items.
  * Columnas:    despliegue_items.despliegue_id -> seguimiento_items.seguimiento_id.
  * Secuencias:  despliegues_id_seq -> seguimientos_id_seq;
                 despliegue_items_id_seq -> seguimiento_items_id_seq.
  * FKs:         fk_despliegues_equipo -> fk_seguimientos_equipo;
                 fk_despliegue_items_despliegue -> fk_seguimiento_items_seguimiento;
                 fk_despliegue_items_material -> fk_seguimiento_items_material.
  * Constraints: PKs despliegues_pkey / despliegue_items_pkey ->
                   seguimientos_pkey / seguimiento_items_pkey;
                 ck_despliegues_estado -> ck_seguimientos_estado;
                 ck_despliegue_items_tomada -> ck_seguimiento_items_tomada;
                 ck_despliegue_items_sobrante -> ck_seguimiento_items_sobrante;
                 uq_despliegue_items_material -> uq_seguimiento_items_material.
  * Indices:     ix_despliegues_equipo -> ix_seguimientos_equipo;
                 ix_despliegues_fecha -> ix_seguimientos_fecha;
                 uq_despliegues_equipo_abierta -> uq_seguimientos_equipo_abierta;
                 ix_despliegue_items_material -> ix_seguimiento_items_material.
  * Funciones:   fn_crear_despliegue -> fn_crear_seguimiento;
                 fn_cerrar_despliegue -> fn_cerrar_seguimiento
                 (cuerpos idénticos a 0014 con nomenclatura nueva).
  * Eventos de auditoría EMITIDOS por las funciones (nuevos eventos):
                 DESPLIEGUE_CREADO -> SEGUIMIENTO_CREADO;
                 DESPLIEGUE_CERRADO -> SEGUIMIENTO_CERRADO.

INMUTABILIDAD DEL LEDGER (REQ-P2-CON-001): CERO UPDATE/DELETE sobre
`auditoria_eventos`. Los 28+ eventos históricos DESPLIEGUE_CREADO /
DESPLIEGUE_CERRADO del inventario existente conservan sus valores legacy;
los eventos nuevos usan la nomenclatura nueva. El mapeo legacy<->nuevo se
resuelve SOLO en lectura (Fase 2, reportes).

Cero pérdida de datos: ALTER ... RENAME son operaciones de catálogo; las
filas de despliegues/despliegue_items (10 cabeceras / 19 items en la BD de
desarrollo) se conservan 1:1. La columna GENERADA cantidad_consumida no
referencia la columna renombrada ni el nombre de la tabla -> permanece
válida sin reescritura. No se confía en Alembic autogenerate: cada objeto
se renombra explícitamente.

downgrade() — reverso exacto 0016 -> 0015: restauración VERBATIM de
fn_crear_despliegue / fn_cerrar_despliegue (cuerpos canónicos de 0014) y
renombres inversos de tablas, secuencias, constraints e índices. Cero
pérdida de datos en ambos sentidos.
"""

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # A) TABLAS Y SECUENCIAS
    # ================================================================
    op.execute(sa.text("ALTER TABLE despliegues RENAME TO seguimientos"))
    op.execute(sa.text("ALTER TABLE despliegue_items RENAME TO seguimiento_items"))
    op.execute(sa.text("ALTER SEQUENCE despliegues_id_seq RENAME TO seguimientos_id_seq"))
    op.execute(
        sa.text("ALTER SEQUENCE despliegue_items_id_seq RENAME TO seguimiento_items_id_seq")
    )

    # ================================================================
    # B) COLUMNAS
    # ================================================================
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME COLUMN despliegue_id TO seguimiento_id"
        )
    )

    # ================================================================
    # C) CLAVES PRIMARIAS Y FORANEAS
    # ================================================================
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT despliegues_pkey "
            "TO seguimientos_pkey"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT despliegue_items_pkey "
            "TO seguimiento_items_pkey"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT fk_despliegues_equipo "
            "TO fk_seguimientos_equipo"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "fk_despliegue_items_despliegue TO fk_seguimiento_items_seguimiento"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "fk_despliegue_items_material TO fk_seguimiento_items_material"
        )
    )

    # ================================================================
    # D) CONSTRAINTS (CHECK / UNIQUE)
    # ================================================================
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT ck_despliegues_estado "
            "TO ck_seguimientos_estado"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "ck_despliegue_items_tomada TO ck_seguimiento_items_tomada"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "ck_despliegue_items_sobrante TO ck_seguimiento_items_sobrante"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "uq_despliegue_items_material TO uq_seguimiento_items_material"
        )
    )

    # ================================================================
    # D.2) CONSTRAINTS NOT NULL (nombres auto-generados
    #      <tabla>_<columna>_not_null: parte de la nomenclatura física)
    # ================================================================
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT despliegues_id_not_null "
            "TO seguimientos_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT despliegues_equipo_id_not_null "
            "TO seguimientos_equipo_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT despliegues_fecha_not_null "
            "TO seguimientos_fecha_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT despliegues_usuario_not_null "
            "TO seguimientos_usuario_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT despliegues_estado_not_null "
            "TO seguimientos_estado_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT despliegues_created_at_not_null "
            "TO seguimientos_created_at_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT despliegues_updated_at_not_null "
            "TO seguimientos_updated_at_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT despliegue_items_id_not_null "
            "TO seguimiento_items_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "despliegue_items_despliegue_id_not_null TO seguimiento_items_seguimiento_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "despliegue_items_material_id_not_null TO seguimiento_items_material_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "despliegue_items_cantidad_tomada_not_null TO seguimiento_items_cantidad_tomada_not_null"
        )
    )

    # ================================================================
    # E) INDICES
    # ================================================================
    op.execute(
        sa.text("ALTER INDEX ix_despliegues_equipo RENAME TO ix_seguimientos_equipo")
    )
    op.execute(
        sa.text("ALTER INDEX ix_despliegues_fecha RENAME TO ix_seguimientos_fecha")
    )
    op.execute(
        sa.text(
            "ALTER INDEX uq_despliegues_equipo_abierta "
            "RENAME TO uq_seguimientos_equipo_abierta"
        )
    )
    op.execute(
        sa.text(
            "ALTER INDEX ix_despliegue_items_material "
            "RENAME TO ix_seguimiento_items_material"
        )
    )

    # ================================================================
    # F) FN_CREAR_SEGUIMIENTO — apertura (100 % PostgreSQL)
    #    Cuerpo de fn_crear_despliegue (0014) con nomenclatura nueva.
    # ================================================================
    op.execute(
        sa.text(
            """
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
        RAISE EXCEPTION 'El equipo ID % no existe o se encuentra inactivo.', p_equipo_id;
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
        RAISE EXCEPTION 'El equipo ID % ya posee un seguimiento abierto.', p_equipo_id;
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
        )
    )

    # ================================================================
    # G) FN_CERRAR_SEGUIMIENTO — cierre con sobrantes (100 % PostgreSQL)
    #    Cuerpo de fn_cerrar_despliegue (0014) con nomenclatura nueva.
    #    (La persistencia del Acta de Consumo se agrega en 0020, T1.6.)
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
END;
$$ LANGUAGE plpgsql;
"""
        )
    )

    # ================================================================
    # H) ELIMINACIÓN DE LOS ALIAS LEGACY (sin retrocompatibilidad:
    #    cero referencias a las funciones antiguas tras esta migración).
    # ================================================================
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS fn_crear_despliegue(INT, TEXT, JSONB, TEXT)")
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS fn_cerrar_despliegue(INT, JSONB, TEXT, TEXT)")
    )


def downgrade() -> None:
    # Reverso exacto 0016 -> 0015 (ver docstring del módulo): restauración
    # VERBATIM de las funciones legacy y renombres inversos. Cero pérdida
    # de datos en ambos sentidos; el ledger jamás se toca.

    # 1. Eliminar las funciones con nomenclatura nueva y restaurar las
    #    canónicas de 0014 (cuerpos con nomenclatura DESPLIEGUE).
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS fn_cerrar_seguimiento(INT, JSONB, TEXT, TEXT)")
    )
    op.execute(
        sa.text("DROP FUNCTION IF EXISTS fn_crear_seguimiento(INT, TEXT, JSONB, TEXT)")
    )
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_crear_despliegue (
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
    SELECT EXISTS (
        SELECT 1 FROM equipos WHERE equipo_id = p_equipo_id AND is_active = TRUE
    ) INTO v_existe;

    IF NOT v_existe THEN
        RAISE EXCEPTION 'El equipo ID % no existe o se encuentra inactivo.', p_equipo_id;
    END IF;

    IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
        RAISE EXCEPTION 'La lista de despliegue debe contener al menos un material.';
    END IF;

    FOR v_item IN
        SELECT (elem->>'material_id')::INT AS material_id,
               (elem->>'cantidad_tomada')::INT AS cantidad_tomada
        FROM jsonb_array_elements(p_items) AS elem
    LOOP
        IF v_item.material_id IS NULL THEN
            RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', v_item.material_id;
        END IF;

        IF v_item.material_id = ANY(v_visto) THEN
            RAISE EXCEPTION 'Material ID LISTA % duplicado en la lista de despliegue.', v_item.material_id;
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

    PERFORM 1
    FROM despliegues
    WHERE equipo_id = p_equipo_id AND estado = 'ABIERTA'
    FOR UPDATE;

    IF FOUND THEN
        RAISE EXCEPTION 'El equipo ID % ya posee un despliegue abierto.', p_equipo_id;
    END IF;

    INSERT INTO despliegues (equipo_id, fecha, observaciones, usuario)
    VALUES (p_equipo_id, CURRENT_DATE, p_observaciones, p_usuario)
    RETURNING id INTO v_id;

    FOR v_item IN
        SELECT (elem->>'material_id')::INT AS material_id,
               (elem->>'cantidad_tomada')::INT AS cantidad_tomada
        FROM jsonb_array_elements(p_items) AS elem
    LOOP
        INSERT INTO despliegue_items (despliegue_id, material_id, cantidad_tomada)
        VALUES (v_id, v_item.material_id, v_item.cantidad_tomada);
    END LOOP;

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, equipo_destino_id, resultado, detalles
    ) VALUES (
        p_usuario,
        'DESPLIEGUE_CREADO',
        p_equipo_id,
        'EXITO',
        jsonb_build_object(
            'despliegue_id', v_id,
            'fecha', CURRENT_DATE,
            'cantidad_items', jsonb_array_length(p_items),
            'observaciones', p_observaciones
        )
    );

    RETURN v_id;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_cerrar_despliegue (
    p_despliegue_id INT,
    p_sobrantes JSONB,
    p_usuario TEXT,
    p_observaciones_cierre TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_despliegue RECORD;
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
    SELECT * INTO v_despliegue
    FROM despliegues
    WHERE id = p_despliegue_id AND estado = 'ABIERTA'
    FOR UPDATE;

    IF NOT FOUND THEN
        IF EXISTS (SELECT 1 FROM despliegues WHERE id = p_despliegue_id) THEN
            RAISE EXCEPTION 'El despliegue ID % no se encuentra en estado ABIERTA.', p_despliegue_id;
        ELSE
            RAISE EXCEPTION 'Despliegue ID % no encontrado.', p_despliegue_id;
        END IF;
    END IF;

    FOR v_item IN
        SELECT di.id, di.material_id, di.cantidad_tomada
        FROM despliegue_items di
        WHERE di.despliegue_id = p_despliegue_id
        ORDER BY di.material_id
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
                RAISE EXCEPTION 'Material ID LISTA % no pertenece a este despliegue.', v_linea.material_id;
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
        WHERE ie.equipo_id = v_despliegue.equipo_id
          AND ie.material_id = ANY(v_material_ids)
        ORDER BY ie.material_id
        FOR UPDATE
    LOOP
        NULL;
    END LOOP;

    FOR v_item IN
        SELECT di.id, di.material_id, di.cantidad_tomada
        FROM despliegue_items di
        WHERE di.despliegue_id = p_despliegue_id
        ORDER BY di.material_id
        FOR UPDATE
    LOOP
        v_sobrante := COALESCE((v_sobrantes_map->>v_item.material_id::text)::INT, 0);
        v_consumido := v_item.cantidad_tomada - v_sobrante;

        SELECT stock_actual INTO v_stock_actual
        FROM inventario_equipos
        WHERE equipo_id = v_despliegue.equipo_id AND material_id = v_item.material_id
        FOR UPDATE;

        IF COALESCE(v_stock_actual, 0) < v_consumido THEN
            RAISE EXCEPTION 'Stock insuficiente en el Equipo ID % para el material ID LISTA %. Disponible: %, Consumido: %',
                v_despliegue.equipo_id, v_item.material_id, COALESCE(v_stock_actual, 0), v_consumido;
        END IF;

        v_nuevo_stock := COALESCE(v_stock_actual, 0) - v_consumido;

        UPDATE despliegue_items
        SET cantidad_sobrante = v_sobrante
        WHERE id = v_item.id;

        UPDATE inventario_equipos
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE equipo_id = v_despliegue.equipo_id AND material_id = v_item.material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, equipo_origen_id, cantidad, resultado, detalles
        ) VALUES (
            p_usuario,
            'DESPLIEGUE_CERRADO',
            v_item.material_id,
            v_despliegue.equipo_id,
            v_consumido,
            'EXITO',
            jsonb_build_object(
                'despliegue_id', p_despliegue_id,
                'cantidad_tomada', v_item.cantidad_tomada,
                'cantidad_sobrante', v_sobrante,
                'cantidad_consumida', v_consumido,
                'stock_remanente_equipo', v_nuevo_stock,
                'fecha_cierre', CURRENT_TIMESTAMP,
                'observaciones_cierre', p_observaciones_cierre
            )
        );
    END LOOP;

    UPDATE despliegues
    SET estado = 'CERRADA', closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    WHERE id = p_despliegue_id;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )

    # 2. Renombres inversos de índices, constraints, columna, secuencias y
    #    tablas (orden inverso al upgrade).
    op.execute(
        sa.text(
            "ALTER INDEX ix_seguimiento_items_material "
            "RENAME TO ix_despliegue_items_material"
        )
    )
    op.execute(
        sa.text(
            "ALTER INDEX uq_seguimientos_equipo_abierta "
            "RENAME TO uq_despliegues_equipo_abierta"
        )
    )
    op.execute(
        sa.text("ALTER INDEX ix_seguimientos_fecha RENAME TO ix_despliegues_fecha")
    )
    op.execute(
        sa.text("ALTER INDEX ix_seguimientos_equipo RENAME TO ix_despliegues_equipo")
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "uq_seguimiento_items_material TO uq_despliegue_items_material"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "ck_seguimiento_items_sobrante TO ck_despliegue_items_sobrante"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "ck_seguimiento_items_tomada TO ck_despliegue_items_tomada"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT ck_seguimientos_estado "
            "TO ck_despliegues_estado"
        )
    )
    # NOT NULL (reverso de D.2)
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "seguimiento_items_cantidad_tomada_not_null TO despliegue_items_cantidad_tomada_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "seguimiento_items_material_id_not_null TO despliegue_items_material_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "seguimiento_items_seguimiento_id_not_null TO despliegue_items_despliegue_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT seguimiento_items_id_not_null "
            "TO despliegue_items_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT seguimientos_updated_at_not_null "
            "TO despliegues_updated_at_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT seguimientos_created_at_not_null "
            "TO despliegues_created_at_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT seguimientos_estado_not_null "
            "TO despliegues_estado_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT seguimientos_usuario_not_null "
            "TO despliegues_usuario_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT seguimientos_fecha_not_null "
            "TO despliegues_fecha_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT seguimientos_equipo_id_not_null "
            "TO despliegues_equipo_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT seguimientos_id_not_null "
            "TO despliegues_id_not_null"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "fk_seguimiento_items_material TO fk_despliegue_items_material"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT "
            "fk_seguimiento_items_seguimiento TO fk_despliegue_items_despliegue"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT fk_seguimientos_equipo "
            "TO fk_despliegues_equipo"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME CONSTRAINT seguimiento_items_pkey "
            "TO despliegue_items_pkey"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimientos RENAME CONSTRAINT seguimientos_pkey "
            "TO despliegues_pkey"
        )
    )
    op.execute(
        sa.text(
            "ALTER TABLE seguimiento_items RENAME COLUMN seguimiento_id TO despliegue_id"
        )
    )
    op.execute(
        sa.text(
            "ALTER SEQUENCE seguimiento_items_id_seq RENAME TO despliegue_items_id_seq"
        )
    )
    op.execute(
        sa.text("ALTER SEQUENCE seguimientos_id_seq RENAME TO despliegues_id_seq")
    )
    op.execute(sa.text("ALTER TABLE seguimiento_items RENAME TO despliegue_items"))
    op.execute(sa.text("ALTER TABLE seguimientos RENAME TO despliegues"))
