"""Correcciones de seguridad T3.2 (dictamen @sec-ops) — cambio
2026-10-01-reportes-consumo-management.

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-02

Hallazgos corregidos (Fase 3, T3.2):
  * [M-1] El registro de idempotencia queda LIGADO AL ACTOR: nueva columna
    `operaciones_idempotencia.actor` y los tres SP la escriben (v_actor).
    Un reenvío con la clave de OTRO actor se rechaza con 409
    ("ya fue utilizada por otro actor") sin divulgar el resultado original.
  * [A-2] La clave de idempotencia se REDACTa de los `detalles` de
    `auditoria_eventos` (ya no se persiste en el ledger cosechable).
  * [B-3] Los RAISE de idempotencia ya no reflejan el valor de la clave en
    el mensaje de error.

downgrade() — reverso exacto 0021 -> 0020: restauración VERBATIM de los
tres SP a su versión 0017/0018/0019 y DROP de la columna `actor` (las
filas históricas de operaciones_idempotencia pierden su actor al degradar;
sin pérdida de datos de negocio).
"""

from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def _sql(sql: str) -> None:
    op.execute(sa.text(sql))


# Versiones ORIGINALES (verbatim) de los tres SP tal como los crearon las
# migraciones 0017/0018/0019. El downgrade() las restaura (reverso exacto
# 0021 -> 0020) antes de DROP de la columna `actor`.
SQL_ORIG_SUMAR = """
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
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave)
        VALUES ('SUMA_CANTIDAD', p_clave_idempotencia)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            RAISE EXCEPTION 'La operación SUMA_CANTIDAD con clave % ya fue ejecutada; no se aplicaron cambios (idempotencia).',
                p_clave_idempotencia;
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
                'usuario', v_actor,
                'clave_idempotencia', p_clave_idempotencia,
                'fecha', CURRENT_TIMESTAMP
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
                'usuario', v_actor,
                'clave_idempotencia', p_clave_idempotencia,
                'fecha', CURRENT_TIMESTAMP
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
"""

SQL_ORIG_MOVER = """
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
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave)
        VALUES ('MOVIMIENTO_INVENTARIO', p_clave_idempotencia)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            RAISE EXCEPTION 'La operación MOVIMIENTO_INVENTARIO con clave % ya fue ejecutada; no se aplicaron cambios (idempotencia).',
                p_clave_idempotencia;
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
            'usuario', v_actor,
            'clave_idempotencia', p_clave_idempotencia,
            'fecha', CURRENT_TIMESTAMP
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

SQL_ORIG_AGREGAR = """
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
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave)
        VALUES ('AGREGAR_TODO', p_clave_idempotencia)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            RAISE EXCEPTION 'La operación AGREGAR_TODO con clave % ya fue ejecutada; no se aplicaron cambios (idempotencia).',
                p_clave_idempotencia;
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
        RAISE EXCEPTION 'El seguimiento ID % no pertenece al equipo ID %.',
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
                'usuario', v_actor,
                'clave_idempotencia', p_clave_idempotencia,
                'fecha', CURRENT_TIMESTAMP
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


def upgrade() -> None:
    # A) Columna actor (nullable: las claves pre-0021 no tienen actor).
    op.execute(
        sa.text(
            "ALTER TABLE operaciones_idempotencia "
            "ADD COLUMN IF NOT EXISTS actor TEXT"
        )
    )
    # B) SP v2: actor en la guarda, clave redactada de auditoría.
    _sql("""
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
""")
    _sql("""
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
""")
    _sql("""
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
        RAISE EXCEPTION 'El seguimiento ID % no pertenece al equipo ID %.',
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
""")


def downgrade() -> None:
    _sql(SQL_ORIG_SUMAR)
    _sql(SQL_ORIG_MOVER)
    _sql(SQL_ORIG_AGREGAR)
    op.execute(
        sa.text(
            "ALTER TABLE operaciones_idempotencia DROP COLUMN IF EXISTS actor"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS "
            "fn_sumar_cantidad(TEXT, TEXT, INT, INT, TEXT, TEXT)"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS "
            "fn_mover_material(TEXT, TEXT, TEXT, TEXT, INT, INT, TEXT, TEXT)"
        )
    )
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS "
            "fn_agregar_todo_seguimiento(INT, INT, TEXT, TEXT)"
        )
    )
