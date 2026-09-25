-- Software Design Document (SDD) - DMS - TELECOM
-- Contrato de Base de Datos (PostgreSQL DDL 10/10)

BEGIN;

-- =========================================================================
-- 1. TRIGGER DE AUDITORÍA AUTOMÁTICA PARA MODIFICACIONES DE MATERIALES
-- =========================================================================

CREATE OR REPLACE FUNCTION fn_auditar_modificacion_material()
RETURNS TRIGGER AS $$
BEGIN
    -- 0013 (Fase 3.5, REQ-UI-004 + Constitution 6.2): codigo (SKU) añadido
    -- a la condición IF para auditar ediciones de solo-SKU.
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

-- =========================================================================
-- 6. INVENTARIO AUTÓNOMO DE EQUIPOS Y FIBRA ÓPTICA INDEPENDIENTE
--    (Fase 2 — paquete 2026-09-22-frontend-backend-alignment, Tasks 2.3/2.4)
-- =========================================================================

-- NOTA: la vista sparse vw_inventario_equipo_completo (Modelo Sparse) queda
-- DEPRECADA. En esquemas existentes debe eliminarse con:
--   DROP VIEW IF EXISTS vw_inventario_equipo_completo;
-- inventario_equipos es ahora el inventario físico autónomo de cada Equipo,
-- poblado exclusivamente por movimientos TEAMS/DEVOL auditados.

-- Trazabilidad del movimiento de origen de cada entrada de inventario de
-- equipo (REQ-DOMAIN-002). Sin FK declarativa: el ledger de movimientos es
-- append-only y el puntero lo escribe exclusivamente fn_procesar_movimiento.
ALTER TABLE inventario_equipos
    ADD COLUMN ultimo_movimiento_id INT;

-- Inventario independiente de Fibra Óptica (REQ-DOMAIN-003/004/005/006):
-- raíces de inventario PAQUETE y EN_USO con esquema estándar gobernado por
-- U.M. El CHECK ck_secciones_tipo de la tabla secciones se conserva por
-- compatibilidad histórica (las secciones FO quedan soft-inactivas).
CREATE TABLE inventario_fibra (
    modulo VARCHAR(20) NOT NULL,
    material_id INT NOT NULL,
    stock_actual INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT inventario_fibra_pkey PRIMARY KEY (modulo, material_id),
    CONSTRAINT ck_inventario_fibra_modulo CHECK (modulo IN ('PAQUETE','EN_USO')),
    CONSTRAINT ck_inventario_fibra_non_negative CHECK (stock_actual >= 0),
    CONSTRAINT fk_inventario_fibra_material FOREIGN KEY (material_id)
        REFERENCES catalogo_materiales(id_lista) ON DELETE RESTRICT
);

CREATE INDEX ix_inventario_fibra_material ON inventario_fibra (material_id);

-- =========================================================================
-- 7. FUNCIONES DE CARGA INICIAL Y AJUSTE DE INVENTARIO DE FIBRA ÓPTICA
-- =========================================================================

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
    IF p_motivo IS NULL OR TRIM(p_motivo) = '' THEN
        RAISE EXCEPTION 'Es obligatorio proporcionar un motivo justificado para realizar un ajuste manual de inventario de Fibra Óptica.';
    END IF;

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

-- =========================================================================
-- 8. HELPER DE AJUSTE DE STOCK DESDE INVENTARIO GENERAL (REQ-API-002/003)
-- =========================================================================

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
    -- ACTIVA de tipo GENERAL; RAISE si no existe o si hay más de una.
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

-- =========================================================================
-- 9. TABLA DE ADMINISTRADORES (RBAC permisivo — sec-ops)
-- =========================================================================

-- Directriz RBAC permisiva: actores con rol administrador. La gestión de
-- altas y bajas la realiza la operación; sin seeds automáticos.
CREATE TABLE administradores (
    actor_id VARCHAR(100) NOT NULL,
    CONSTRAINT administradores_pkey PRIMARY KEY (actor_id)
);

COMMENT ON TABLE administradores IS
'Directriz RBAC permisiva (sec-ops): actores con rol administrador. La gestión de altas y bajas la realiza la operación; sin seeds automáticos.';

COMMIT;