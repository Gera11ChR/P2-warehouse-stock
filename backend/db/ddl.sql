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

-- 0014 (Fase 2, paquete 2026-09-28-equipos-despliegue-management): ruteo
-- FO aditivo. Las secciones FO_PAQUETE/FO_EN_USO (is_active=FALSE, meros
-- manejadores de ruteo) redirigen origen/destino a
-- inventario_fibra(modulo='PAQUETE'/'EN_USO'). La rama GENERAL permanece
-- idéntica en comportamiento y mensajes.

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

    -- Resolución UNA VEZ de los tipos de sección origen/destino.
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

-- =========================================================================
-- 3. FUNCIÓN DE CANCELACIÓN Y REVERSIÓN DE MOVIMIENTOS (BLINDADA)
-- =========================================================================

-- 0014 (Fase 2): reversión FO aditiva simétrica al ruteo de la sección 2.
-- Los mensajes históricos de RAISE permanecen intactos.

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

    -- Resolución UNA VEZ de los tipos de sección origen/destino.
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
            
            -- A. Validar y bloquear stock en el destino (GENERAL ->
            --    inventario_almacen; FO -> inventario_fibra)
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

-- =========================================================================
-- 10. UNIDADES DE MEDIDA MAESTRAS, CONFIGURACIÓN LOCAL DE EQUIPOS Y
--     DESPLIEGUES (Fase 2 — paquete 2026-09-28-equipos-despliegue-management)
-- =========================================================================

-- Unidades de Medida maestras: fuente única del selector de U.M.
-- Eliminación lógica (is_active=FALSE) auditada por tg_auditar_um.
CREATE TABLE ums (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN NOT NULL DEFAULT true
);

-- Siembra idempotente de las 10 unidades soportadas (SUPPORTED_UNITS,
-- app/schemas/material.py).
INSERT INTO ums (nombre) VALUES
    ('PZ'), ('LT'), ('CARRETE (1 KM)'), ('METRO (M)'), ('CARRETE (5 KM)'),
    ('BOLSA (500 PZ)'), ('PAQUETE (100 PZ)'), ('ROLLO'), ('EQUIPO'), ('UNIDAD')
ON CONFLICT (nombre) DO NOTHING;

-- Parámetros operativos LOCALES por equipo (stock mínimo, categoría, U.M.).
-- Tabla SEPARADA de inventario_equipos: preserva el inventario físico
-- autónomo poblado exclusivamente por movimientos TEAMS/DEVOL. El catálogo
-- maestro (codigo, descripcion, u_m, stock_minimo) permanece inmutable.
CREATE TABLE equipo_material_config (
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
);

CREATE INDEX ix_equipo_material_config_material ON equipo_material_config (material_id);

-- Cabecera del flujo DESPLIEGUE: ciclo ABIERTA -> CERRADA gobernado
-- exclusivamente por fn_crear_despliegue / fn_cerrar_despliegue.
-- UN SOLO despliegue abierto por equipo (índice único parcial).
CREATE TABLE despliegues (
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
);

CREATE INDEX ix_despliegues_equipo ON despliegues (equipo_id);
CREATE INDEX ix_despliegues_fecha ON despliegues (fecha);
CREATE UNIQUE INDEX uq_despliegues_equipo_abierta ON despliegues (equipo_id)
    WHERE estado = 'ABIERTA';

-- Ledger APPEND-ONLY de líneas de despliegue: las filas se crean en
-- fn_crear_despliegue; en fn_cerrar_despliegue solo se rellena
-- cantidad_sobrante. La columna GENERADA materializa el consumo
-- (tomada - sobrante) íntegramente en PostgreSQL. Cero DELETE físicos.
CREATE TABLE despliegue_items (
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
);

CREATE INDEX ix_despliegue_items_material ON despliegue_items (material_id);

-- =========================================================================
-- 11. FN_CREAR_DESPLIEGUE — apertura de despliegue de campo
-- =========================================================================

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

    -- 4. Un solo despliegue abierto por equipo (bloqueo de filas; el índice
    --    único parcial es la red de seguridad).
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

-- =========================================================================
-- 12. FN_CERRAR_DESPLIEGUE — cierre con sobrantes y descuento de stock
-- =========================================================================

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

    -- 2. Cargar items ORDENADOS por material_id (orden de bloqueo
    --    determinista) y recolectar los material_id.
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

    -- 4. Bloqueo de las filas de inventario del equipo (FOR UPDATE, orden
    --    por material_id: cero condiciones de carrera y cero deadlocks).
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

    -- 5. Por cada item: sobrante (default 0), consumido, validación de stock
    --    del equipo, UPDATE del item (materializa la columna GENERATED),
    --    descuento del inventario (SIN eliminar filas que lleguen a 0) y
    --    evento de auditoría por línea.
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

-- =========================================================================
-- 13. TRIGGERS DE AUDITORÍA DE CATÁLOGO (Constitution 6.2)
-- =========================================================================

-- Categorías: modificación/eliminación (física o soft-delete vía
-- is_active=FALSE) emitida como evento inmutable.
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

-- Unidades de Medida: mismo patrón de auditoría.
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

-- Configuración local de equipos: alta y modificación auditadas con los
-- valores anteriores completos (NULL en INSERT: sin historia previa).
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

COMMIT;