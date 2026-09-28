"""equipos y despliegue: UMs, configuración local de equipos y flujo DESPLIEGUE

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-28

Fase 2 (Data, Schemas & Security) del pipeline SDD — implementa las Tasks
del paquete 2026-09-28-equipos-despliegue-management (propuesta aprobada):

  1) Tabla `ums` (Unidades de Medida maestras): fuente única del selector
     de U.M. (alta/modificación de material y configuración local de
     equipos). Siembra de las 10 unidades del tuple SUPPORTED_UNITS de
     app/schemas/material.py. Eliminación lógica (is_active=FALSE) con
     auditoría por trigger.

  2) Tabla `equipo_material_config`: parámetros operativos LOCALES por
     equipo (stock mínimo, categoría, U.M.). Tabla SEPARADA (no columnas
     sobre inventario_equipos) para preservar el modelo de inventario de
     equipos como registro físico autónomo: las filas de inventario solo
     las crean los movimientos TEAMS/DEVOL y las funciones de stock.
     Auditoría completa por trigger (INSERT/UPDATE).

  3) Tablas `despliegues` + `despliegue_items`: flujo DESPLIEGUE de campo.
     `despliegues` con estado ABIERTA/CERRADA y índice único parcial que
     garantiza UN SOLO despliegue abierto por equipo.
     `despliegue_items` es un LEDGER APPEND-ONLY: las filas se crean en
     fn_crear_despliegue y en fn_cerrar_despliegue solo se rellena
     cantidad_sobrante (la columna GENERATED cantidad_consumida se
     materializa). Cero DELETE físicos (FOREIGN KEY RESTRICT).

  4) fn_crear_despliegue / fn_cerrar_despliegue: TODA la aritmética de
     stock del despliegue corre en PostgreSQL (cero condiciones de carrera:
     FOR UPDATE sobre cabecera, items e inventario del equipo). La
     insuficiencia de stock hace RAISE y revierte la transacción completa.

  5) Enrutamiento FO en fn_procesar_movimiento / fn_cancelar_movimiento
     (cambio ADITIVO, tarea 2 del paquete): las secciones
     FO_PAQUETE/FO_EN_USO (is_active=FALSE, meros manejadores de ruteo)
     redirigen a inventario_fibra(modulo='PAQUETE'/'EN_USO'). La rama
     GENERAL permanece byte-idéntica en comportamiento y mensajes.

  6) Triggers de auditoría de catálogo (Constitution 6.2):
     fn_auditar_categoria / fn_auditar_um (UPDATE O DELETE, con
     soft-delete detectado como ELIMINADA) y
     fn_auditar_equipo_material_config (INSERT O UPDATE).

downgrade() — reverso exacto 0014 -> 0013: DROP de triggers/funciones
nuevas, restauración VERBATIM de fn_procesar_movimiento y
fn_cancelar_movimiento a sus cuerpos pre-0014 (canónicos de ddl.sql) y
DROP de las cuatro tablas nuevas en orden de dependencias. Cero pérdida
de datos de los objetos preexistentes (las tablas nuevas no tienen datos
migrados; el stock no se toca).
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # A) UNIDADES DE MEDIDA MAESTRAS (ums)
    # ================================================================

    op.execute(
        sa.text(
            """
CREATE TABLE IF NOT EXISTS ums (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT true
)
"""
        )
    )

    # Siembra de las 10 unidades soportadas (SUPPORTED_UNITS,
    # app/schemas/material.py). ON CONFLICT: idempotente frente a
    # resiembras posteriores (conftest TRUNCATE + resiembra).
    op.execute(
        sa.text(
            """
INSERT INTO ums (nombre) VALUES
    ('PZ'), ('LT'), ('CARRETE (1 KM)'), ('METRO (M)'), ('CARRETE (5 KM)'),
    ('BOLSA (500 PZ)'), ('PAQUETE (100 PZ)'), ('ROLLO'), ('EQUIPO'), ('UNIDAD')
ON CONFLICT (nombre) DO NOTHING
"""
        )
    )

    # ================================================================
    # B) CONFIGURACIÓN OPERATIVA LOCAL DE EQUIPOS (equipo_material_config)
    # ================================================================

    op.execute(
        sa.text(
            """
CREATE TABLE IF NOT EXISTS equipo_material_config (
    equipo_id INT NOT NULL,
    material_id INT NOT NULL,
    stock_minimo_local INT,
    categoria_local_id INT,
    um_local_id INT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT equipo_material_config_pkey PRIMARY KEY (equipo_id, material_id),
    CONSTRAINT fk_equipo_material_config_equipo FOREIGN KEY (equipo_id)
        REFERENCES equipos(equipo_id) ON DELETE RESTRICT,
    CONSTRAINT fk_equipo_material_config_material FOREIGN KEY (material_id)
        REFERENCES catalogo_materiales(id_lista) ON DELETE RESTRICT,
    CONSTRAINT fk_equipo_material_config_categoria FOREIGN KEY (categoria_local_id)
        REFERENCES categorias(id) ON DELETE RESTRICT,
    CONSTRAINT fk_equipo_material_config_um FOREIGN KEY (um_local_id)
        REFERENCES ums(id) ON DELETE RESTRICT,
    CONSTRAINT ck_equipo_material_config_stock_minimo
        CHECK (stock_minimo_local IS NULL OR stock_minimo_local >= 0)
)
"""
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_equipo_material_config_material "
            "ON equipo_material_config (material_id)"
        )
    )

    # ================================================================
    # C) DESPLIEGUES (cabecera) Y DESPLIEGUE_ITEMS (ledger append-only)
    # ================================================================

    op.execute(
        sa.text(
            """
CREATE TABLE IF NOT EXISTS despliegues (
    id SERIAL PRIMARY KEY,
    equipo_id INT NOT NULL,
    fecha DATE NOT NULL DEFAULT CURRENT_DATE,
    observaciones TEXT,
    usuario VARCHAR(100) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'ABIERTA',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ,
    CONSTRAINT fk_despliegues_equipo FOREIGN KEY (equipo_id)
        REFERENCES equipos(equipo_id) ON DELETE RESTRICT,
    CONSTRAINT ck_despliegues_estado CHECK (estado IN ('ABIERTA','CERRADA'))
)
"""
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_despliegues_equipo ON despliegues (equipo_id)"
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_despliegues_fecha ON despliegues (fecha)"
        )
    )
    # Invariante de dominio: UN SOLO despliegue ABIERTO por equipo.
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_despliegues_equipo_abierta "
            "ON despliegues (equipo_id) WHERE estado = 'ABIERTA'"
        )
    )

    op.execute(
        sa.text(
            """
CREATE TABLE IF NOT EXISTS despliegue_items (
    id SERIAL PRIMARY KEY,
    despliegue_id INT NOT NULL,
    material_id INT NOT NULL,
    cantidad_tomada INT NOT NULL,
    cantidad_sobrante INT,
    cantidad_consumida INT GENERATED ALWAYS AS (cantidad_tomada - cantidad_sobrante) STORED,
    CONSTRAINT fk_despliegue_items_despliegue FOREIGN KEY (despliegue_id)
        REFERENCES despliegues(id) ON DELETE RESTRICT,
    CONSTRAINT fk_despliegue_items_material FOREIGN KEY (material_id)
        REFERENCES catalogo_materiales(id_lista) ON DELETE RESTRICT,
    CONSTRAINT uq_despliegue_items_material UNIQUE (despliegue_id, material_id),
    CONSTRAINT ck_despliegue_items_tomada CHECK (cantidad_tomada > 0),
    CONSTRAINT ck_despliegue_items_sobrante CHECK (
        cantidad_sobrante IS NULL OR
        (cantidad_sobrante >= 0 AND cantidad_sobrante <= cantidad_tomada)
    )
)
"""
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_despliegue_items_material "
            "ON despliegue_items (material_id)"
        )
    )

    # ================================================================
    # D) FN_CREAR_DESPLIEGUE — apertura de despliegue (100% PostgreSQL)
    # ================================================================

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
    -- 1. El equipo debe existir y estar activo.
    SELECT EXISTS (
        SELECT 1 FROM equipos WHERE equipo_id = p_equipo_id AND is_active = TRUE
    ) INTO v_existe;

    IF NOT v_existe THEN
        RAISE EXCEPTION 'El equipo ID % no existe o se encuentra inactivo.', p_equipo_id;
    END IF;

    -- 2. La lista de despliegue debe ser un arreglo JSON no vacío.
    IF p_items IS NULL OR jsonb_typeof(p_items) <> 'array' OR jsonb_array_length(p_items) = 0 THEN
        RAISE EXCEPTION 'La lista de despliegue debe contener al menos un material.';
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

    -- 4. Un solo despliegue abierto por equipo (bloqueo de filas sobre la
    --    ventana del equipo; el índice único parcial es la red de seguridad).
    PERFORM 1
    FROM despliegues
    WHERE equipo_id = p_equipo_id AND estado = 'ABIERTA'
    FOR UPDATE;

    IF FOUND THEN
        RAISE EXCEPTION 'El equipo ID % ya posee un despliegue abierto.', p_equipo_id;
    END IF;

    -- 5. Cabecera (estado por defecto ABIERTA) e items.
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

    -- 6. Evento de auditoría de apertura.
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

    # ================================================================
    # E) FN_CERRAR_DESPLIEGUE — cierre con sobrantes (100% PostgreSQL)
    # ================================================================

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
    -- 1. Bloquear la cabecera SOLO si está ABIERTA.
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

    -- 2. Cargar items del despliegue ORDENADOS por material_id (orden de
    --    bloqueo determinista) y recolectar los material_id.
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

    -- 4. Bloqueo de las filas de inventario del equipo (FOR UPDATE,
    --    orden por material_id: cero condiciones de carrera y cero
    --    deadlocks con fn_procesar_movimiento).
    FOR v_fila_inv IN
        SELECT ie.material_id, ie.stock_actual
        FROM inventario_equipos ie
        WHERE ie.equipo_id = v_despliegue.equipo_id
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

    -- 6. Cerrar la cabecera.
    UPDATE despliegues
    SET estado = 'CERRADA', closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
    WHERE id = p_despliegue_id;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )

    # ================================================================
    # F) FN_PROCESAR_MOVIMIENTO — enrutamiento FO aditivo (REQ aprobado)
    # ================================================================

    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_procesar_movimiento (p_movimiento_id INT)
RETURNS VOID AS $$
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
                RAISE EXCEPTION 'El equipo ID % no cuenta con stock suficiente del material ID LISTA % para devolver.',
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
$$ LANGUAGE plpgsql;
"""
        )
    )

    # ================================================================
    # G) FN_CANCELAR_MOVIMIENTO — reversión FO aditiva simétrica
    # ================================================================

    op.execute(
        sa.text(
            """
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
                RAISE EXCEPTION 'Stock insuficiente en el Equipo destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
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
$$ LANGUAGE plpgsql;
"""
        )
    )

    # ================================================================
    # H) TRIGGERS DE AUDITORÍA DE CATÁLOGO (Constitution 6.2)
    # ================================================================

    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_auditar_categoria()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, resultado, detalles
    ) VALUES (
        COALESCE(current_setting('app.actor', true), CURRENT_USER),
        CASE
            WHEN TG_OP = 'DELETE' THEN 'CATEGORIA_ELIMINADA'
            WHEN NEW.is_active IS DISTINCT FROM OLD.is_active AND NEW.is_active = FALSE THEN 'CATEGORIA_ELIMINADA'
            ELSE 'CATEGORIA_MODIFICADA'
        END,
        'EXITO',
        jsonb_build_object(
            'categoria_id', COALESCE(NEW.id, OLD.id),
            'nombre_anterior', OLD.nombre,
            'nombre_nuevo', CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE NEW.nombre END,
            'is_active_anterior', OLD.is_active,
            'is_active_nuevo', CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE NEW.is_active END
        )
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_auditar_categoria ON categorias;
CREATE TRIGGER tg_auditar_categoria
AFTER UPDATE OR DELETE ON categorias
FOR EACH ROW EXECUTE FUNCTION fn_auditar_categoria();
"""
        )
    )

    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_auditar_um()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, resultado, detalles
    ) VALUES (
        COALESCE(current_setting('app.actor', true), CURRENT_USER),
        CASE
            WHEN TG_OP = 'DELETE' THEN 'UM_ELIMINADA'
            WHEN NEW.is_active IS DISTINCT FROM OLD.is_active AND NEW.is_active = FALSE THEN 'UM_ELIMINADA'
            ELSE 'UM_MODIFICADA'
        END,
        'EXITO',
        jsonb_build_object(
            'um_id', COALESCE(NEW.id, OLD.id),
            'nombre_anterior', OLD.nombre,
            'nombre_nuevo', CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE NEW.nombre END,
            'is_active_anterior', OLD.is_active,
            'is_active_nuevo', CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE NEW.is_active END
        )
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_auditar_um ON ums;
CREATE TRIGGER tg_auditar_um
AFTER UPDATE OR DELETE ON ums
FOR EACH ROW EXECUTE FUNCTION fn_auditar_um();
"""
        )
    )

    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_auditar_equipo_material_config()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, resultado, detalles
    ) VALUES (
        COALESCE(current_setting('app.actor', true), CURRENT_USER),
        'CONFIG_EQUIPO_MODIFICADA',
        NEW.material_id,
        'EXITO',
        jsonb_build_object(
            'equipo_id', NEW.equipo_id,
            'stock_minimo_local', NEW.stock_minimo_local,
            'categoria_local_id', NEW.categoria_local_id,
            'um_local_id', NEW.um_local_id,
            'valores_anteriores', CASE WHEN TG_OP = 'INSERT' THEN NULL::jsonb
                                       ELSE jsonb_build_object(
                                           'stock_minimo_local', OLD.stock_minimo_local,
                                           'categoria_local_id', OLD.categoria_local_id,
                                           'um_local_id', OLD.um_local_id
                                       ) END
        )
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tg_auditar_equipo_material_config ON equipo_material_config;
CREATE TRIGGER tg_auditar_equipo_material_config
AFTER INSERT OR UPDATE ON equipo_material_config
FOR EACH ROW EXECUTE FUNCTION fn_auditar_equipo_material_config();
"""
        )
    )


def downgrade() -> None:
    # Reverso exacto 0014 -> 0013 (ver docstring del módulo).

    # 1. Triggers y funciones de auditoría nuevas (orden inverso de
    #    dependencias: trigger antes que su función).
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS tg_auditar_equipo_material_config ON equipo_material_config"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_auditar_equipo_material_config()"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS tg_auditar_um ON ums"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_auditar_um()"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS tg_auditar_categoria ON categorias"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_auditar_categoria()"))

    # 2. Funciones del flujo DESPLIEGUE.
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cerrar_despliegue(INT, JSONB, TEXT, TEXT)"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_crear_despliegue(INT, TEXT, JSONB, TEXT)"))

    # 3. Restauración VERBATIM de fn_cancelar_movimiento y
    #    fn_procesar_movimiento a sus cuerpos pre-0014 (canónicos de
    #    ddl.sql: sin enrutamiento FO).
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_cancelar_movimiento (
    p_movimiento_id INT,
    p_motivo TEXT DEFAULT 'Reversión manual por cancelación'
)
RETURNS VOID AS $$
DECLARE
    v_rec RECORD;
    v_cabecera RECORD;
    v_stock_disponible INT;
BEGIN
    SELECT * INTO v_cabecera
    FROM movimientos_cabecera
    WHERE id = p_movimiento_id AND estado = 'CONFIRMADO'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El movimiento ID % no existe o no se encuentra en estado CONFIRMADO.', p_movimiento_id;
    END IF;

    FOR v_rec IN SELECT * FROM movimientos_detalle WHERE movimiento_id = p_movimiento_id LOOP

        IF v_cabecera.tipo_movimiento = 'TEAMS' THEN
            SELECT stock_actual INTO v_stock_disponible
            FROM inventario_equipos
            WHERE equipo_id = v_cabecera.destino_equipo_id AND material_id = v_rec.material_id
            FOR UPDATE;

            IF COALESCE(v_stock_disponible, 0) < v_rec.cantidad THEN
                RAISE EXCEPTION 'Stock insuficiente en el Equipo destino (ID %) para revertir el material ID LISTA %. Disponible: %, A revertir: %',
                    v_cabecera.destino_equipo_id, v_rec.material_id, COALESCE(v_stock_disponible, 0), v_rec.cantidad;
            END IF;

            UPDATE inventario_equipos
            SET stock_actual = stock_actual - v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.destino_equipo_id AND material_id = v_rec.material_id;

            UPDATE inventario_almacen
            SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE almacen_id = v_cabecera.origen_almacen_id AND material_id = v_rec.material_id;

        ELSIF v_cabecera.tipo_movimiento = 'DEVOL' THEN
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

            UPDATE inventario_equipos
            SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.origen_equipo_id AND material_id = v_rec.material_id;
        END IF;

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
            )
        );
    END LOOP;

    UPDATE movimientos_cabecera SET estado = 'CANCELADO' WHERE id = p_movimiento_id;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )

    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_procesar_movimiento (p_movimiento_id INT)
RETURNS VOID AS $$
DECLARE
    v_rec RECORD;
    v_cabecera RECORD;
    v_stock_disponible INT;
    v_stock_minimo INT;
    v_alerta_stock BOOLEAN := FALSE;
    v_nuevo_stock_origen INT;
BEGIN
    SELECT * INTO v_cabecera
    FROM movimientos_cabecera
    WHERE id = p_movimiento_id AND estado = 'BORRADOR'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El movimiento ID % no existe o no se encuentra en estado BORRADOR.', p_movimiento_id;
    END IF;

    FOR v_rec IN SELECT md.*, cm.stock_minimo
                 FROM movimientos_detalle md
                 JOIN catalogo_materiales cm ON cm.id_lista = md.material_id
                 WHERE md.movimiento_id = p_movimiento_id LOOP

        v_stock_minimo := v_rec.stock_minimo;
        v_alerta_stock := FALSE;

        IF v_cabecera.tipo_movimiento = 'TEAMS' THEN
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
                RAISE EXCEPTION 'El equipo ID % no cuenta con stock suficiente del material ID LISTA % para devolver.',
                    v_cabecera.origen_equipo_id, v_rec.material_id;
            END IF;

            v_nuevo_stock_origen := v_stock_disponible - v_rec.cantidad;

            UPDATE inventario_equipos
            SET stock_actual = v_nuevo_stock_origen,
                ultimo_movimiento_id = p_movimiento_id,
                updated_at = CURRENT_TIMESTAMP
            WHERE equipo_id = v_cabecera.origen_equipo_id AND material_id = v_rec.material_id;

            INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual)
            VALUES (v_cabecera.destino_almacen_id, v_rec.material_id, v_rec.cantidad)
            ON CONFLICT (almacen_id, material_id)
            DO UPDATE SET stock_actual = inventario_almacen.stock_actual + EXCLUDED.stock_actual, updated_at = CURRENT_TIMESTAMP;
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
            )
        );
    END LOOP;

    UPDATE movimientos_cabecera SET estado = 'CONFIRMADO' WHERE id = p_movimiento_id;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )

    # 4. Tablas nuevas (orden de dependencias: items antes que cabecera;
    #    config antes que ums).
    op.execute(sa.text("DROP TABLE IF EXISTS despliegue_items"))
    op.execute(sa.text("DROP TABLE IF EXISTS despliegues"))
    op.execute(sa.text("DROP TABLE IF EXISTS equipo_material_config"))
    op.execute(sa.text("DROP TABLE IF EXISTS ums"))
