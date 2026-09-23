-- Software Design Document (SDD) - DMS - TELECOM
-- Contrato de Base de Datos (PostgreSQL DDL 10/10)

BEGIN;

-- =========================================================================
-- 1. TRIGGER DE AUDITORÍA AUTOMÁTICA PARA MODIFICACIONES DE MATERIALES
-- =========================================================================

CREATE OR REPLACE FUNCTION fn_auditar_modificacion_material()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.descripcion IS DISTINCT FROM NEW.descripcion OR 
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

-- =========================================================================
-- 2. FUNCIÓN TRANSACCIONAL MEJORADA (TEAMS, DEVOL Y STOCK MÍNIMO)
-- =========================================================================

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

            INSERT INTO inventario_equipos (equipo_id, material_id, stock_actual)
            VALUES (v_cabecera.destino_equipo_id, v_rec.material_id, v_rec.cantidad)
            ON CONFLICT (equipo_id, material_id)
            DO UPDATE SET stock_actual = inventario_equipos.stock_actual + EXCLUDED.stock_actual, updated_at = CURRENT_TIMESTAMP;

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
            SET stock_actual = v_nuevo_stock_origen, updated_at = CURRENT_TIMESTAMP
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

-- =========================================================================
-- 3. FUNCIÓN DE CANCELACIÓN Y REVERSIÓN DE MOVIMIENTOS (BLINDADA)
-- =========================================================================

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
    -- 1. Bloquear cabecera
    SELECT * INTO v_cabecera
    FROM movimientos_cabecera
    WHERE id = p_movimiento_id AND estado = 'CONFIRMADO'
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El movimiento ID % no existe o no se encuentra en estado CONFIRMADO.', p_movimiento_id;
    END IF;

    FOR v_rec IN SELECT * FROM movimientos_detalle WHERE movimiento_id = p_movimiento_id LOOP
        
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

            -- C. Sumar a almacén origen
            UPDATE inventario_almacen
            SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
            WHERE almacen_id = v_cabecera.origen_almacen_id AND material_id = v_rec.material_id;

        -- REVERSIÓN DEVOL (Devuelve el stock del almacén destino al equipo origen)
        ELSIF v_cabecera.tipo_movimiento = 'DEVOL' THEN
            
            -- A. Validar y bloquear stock en el almacén destino
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
            )
        );
    END LOOP;

    -- 3. Actualizar estado de cabecera
    UPDATE movimientos_cabecera SET estado = 'CANCELADO' WHERE id = p_movimiento_id;
END;
$$ LANGUAGE plpgsql;

-- =========================================================================
-- 4. FUNCIÓN DE CARGA INICIAL DE INVENTARIO (UNICA E IDEMPOTENTE)
-- =========================================================================

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

    -- Validar si el registro de inventario ya existe en el almacén
    SELECT EXISTS (
        SELECT 1 
        FROM inventario_almacen 
        WHERE almacen_id = p_almacen_id AND material_id = p_material_id
    ) INTO v_existe;

    IF v_existe THEN
        RAISE EXCEPTION 'El material ID % ya posee un registro de inventario activo en el almacén ID %. Para ajustar existencias use fn_ajustar_stock_almacen.',
            p_material_id, p_almacen_id;
    END IF;

    -- Inserción estricta de primera vez
    INSERT INTO inventario_almacen (almacen_id, material_id, stock_actual)
    VALUES (p_almacen_id, p_material_id, p_cantidad);

    -- Auditoría forense de alta inicial
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

-- =========================================================================
-- 5. FUNCIÓN DE AJUSTE ADMINISTRATIVO Y CONCILIACIÓN DE INVENTARIO
-- =========================================================================

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

    IF p_motivo IS NULL OR TRIM(p_motivo) = '' THEN
        RAISE EXCEPTION 'Es obligatorio proporcionar un motivo justificado para realizar un ajuste manual de inventario.';
    END IF;

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

COMMIT;