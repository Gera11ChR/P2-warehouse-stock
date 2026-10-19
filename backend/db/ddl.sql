-- Software Design Document (SDD) - DMS - TELECOM
-- Snapshot SCHEMA-ONLY del esquema vigente (cabeza Alembic 0029).
--
-- >>> REFERENCIA, NO EJECUTABLE sobre bases reales: la fuente de verdad del
-- >>> esquema son las migraciones Alembic (`backend/alembic/versions/`).
-- >>> Este archivo es una instantánea de lectura (tablas, restricciones,
-- >>> funciones y triggers); se regenera y se verifica con
-- >>> `backend/scripts/generar_ddl.py`.
--
-- Generado: 2026-10-19 con pg_dump (PostgreSQL) 18.6 (Ubuntu 18.6-0ubuntu0.26.04.1)
-- Comando : pg_dump --schema-only --no-owner --no-privileges  (base de pruebas
--           llevada a la cabeza 0029; sin host, rol ni credenciales)
-- ===== FIN DE CABECERA (contenido generado por pg_dump) =====

--
-- PostgreSQL database dump
--

--
-- Name: fn_actividad_pendiente(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_actividad_pendiente(p_equipo_id integer) RETURNS TABLE(seguimiento_id integer, fecha_cierre timestamp with time zone, materiales jsonb)
    LANGUAGE sql STABLE
    AS $$
SELECT s.id,
       s.closed_at,
       COALESCE(
           (SELECT jsonb_agg(
               jsonb_build_object(
                   'material_id', si.material_id,
                   'codigo', cm.codigo,
                   'descripcion', cm.descripcion,
                   'u_m', cm.u_m,
                   'cantidad_consumida', si.cantidad_consumida,
                   'valor_unitario', cm.valor_unitario
               ) ORDER BY si.material_id
            )
              FROM seguimiento_items si
              JOIN catalogo_materiales cm ON cm.id_lista = si.material_id
             WHERE si.seguimiento_id = s.id
               AND si.cantidad_consumida > 0),
           '[]'::jsonb)
  FROM seguimientos s
 WHERE s.equipo_id = p_equipo_id
   AND s.estado = 'CERRADA'
   AND NOT EXISTS (SELECT 1 FROM actividades_reportes a WHERE a.seguimiento_id = s.id)
 ORDER BY s.closed_at DESC, s.id DESC
 LIMIT 1;
$$;

--
-- Name: fn_agregar_todo_seguimiento(integer, integer, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_agregar_todo_seguimiento(p_seguimiento_id integer, p_equipo_id integer, p_usuario text, p_clave_idempotencia text DEFAULT NULL::text) RETURNS integer
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_ajustar_stock_almacen(integer, integer, numeric, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_ajustar_stock_almacen(p_almacen_id integer, p_material_id integer, p_nuevo_stock numeric, p_motivo text) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_ajustar_stock_fibra(integer, numeric, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_ajustar_stock_fibra(p_material_id integer, p_nuevo_stock numeric, p_motivo text) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_ajustar_stock_general(integer, numeric, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_ajustar_stock_general(p_material_id integer, p_nuevo_stock numeric, p_motivo text) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_auditar_categoria(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_auditar_categoria() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_auditar_equipo_material_config(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_auditar_equipo_material_config() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_auditar_modificacion_material(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_auditar_modificacion_material() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_auditar_um(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_auditar_um() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_bloquear_mutacion_ledger(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_bloquear_mutacion_ledger() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % es append-only (ledger inmutable): UPDATE y DELETE están prohibidos.',
        TG_TABLE_NAME
        USING ERRCODE = 'P0001';
END;
$$;

--
-- Name: fn_cancelar_movimiento(integer, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_cancelar_movimiento(p_movimiento_id integer, p_motivo text DEFAULT 'Reversión manual por cancelación'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
            --    FO -> inventario_fibra unificado)
            IF v_origen_tipo = 'GENERAL' THEN
                UPDATE inventario_almacen
                SET stock_actual = stock_actual + v_rec.cantidad, updated_at = CURRENT_TIMESTAMP
                WHERE almacen_id = v_rec.origen_efectivo AND material_id = v_rec.material_id;

            ELSIF v_origen_tipo = 'FO' THEN
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

            ELSIF v_destino_tipo = 'FO' THEN
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
$$;

--
-- Name: fn_cargar_stock_inicial(integer, integer, numeric, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_cargar_stock_inicial(p_almacen_id integer, p_material_id integer, p_cantidad numeric, p_motivo text DEFAULT 'Carga inicial de inventario en alta de catálogo'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_cargar_stock_inicial_fibra(integer, numeric, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_cargar_stock_inicial_fibra(p_material_id integer, p_cantidad numeric, p_motivo text DEFAULT 'Carga inicial de inventario FO'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_cerrar_seguimiento(integer, jsonb, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_cerrar_seguimiento(p_seguimiento_id integer, p_consumidos jsonb, p_usuario text, p_observaciones_cierre text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_crear_actividad(integer, integer, text, text, text, jsonb, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_crear_actividad(p_equipo_id integer, p_seguimiento_id integer, p_vehiculo text, p_clientes text, p_direcciones text, p_actividades jsonb, p_comentarios text, p_usuario text) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_seguimiento seguimientos%ROWTYPE;
    v_folio integer;
    v_materiales jsonb;
    v_id integer;
    v_item jsonb;
    v_item_texto text;
    v_veces integer;
BEGIN
    -- 1. Bloquear el seguimiento (serializa con cualquier otro cierre de
    --    actividad sobre el mismo registro; REQ-ACT-011).
    SELECT * INTO v_seguimiento
      FROM seguimientos
     WHERE id = p_seguimiento_id
     FOR UPDATE;

    IF NOT FOUND OR v_seguimiento.equipo_id <> p_equipo_id THEN
        RAISE EXCEPTION 'Seguimiento inexistente para la Unidad.'
            USING ERRCODE = 'P0001';
    END IF;

    -- 2. Solo seguimientos cerrados; uno por actividad (REQ-ACT-003).
    IF v_seguimiento.estado <> 'CERRADA' THEN
        RAISE EXCEPTION 'El seguimiento debe estar cerrado para registrar la actividad.'
            USING ERRCODE = 'P0001';
    END IF;

    IF EXISTS (SELECT 1 FROM actividades_reportes WHERE seguimiento_id = p_seguimiento_id) THEN
        RAISE EXCEPTION 'El seguimiento ya tiene una actividad confirmada.'
            USING ERRCODE = 'P0001';
    END IF;

    -- 3. Defensa en profundidad de los campos manuales (Pydantic ya valida;
    --    la función jamás deja pasar a los CHECK/22001).
    IF btrim(p_vehiculo) = '' OR length(p_vehiculo) > 100 THEN
        RAISE EXCEPTION 'El vehículo es obligatorio y no puede exceder 100 caracteres.'
            USING ERRCODE = 'P0001';
    END IF;
    IF btrim(p_clientes) = '' OR length(p_clientes) > 500 THEN
        RAISE EXCEPTION 'El cliente es obligatorio y no puede exceder 500 caracteres.'
            USING ERRCODE = 'P0001';
    END IF;
    IF btrim(p_direcciones) = '' OR length(p_direcciones) > 500 THEN
        RAISE EXCEPTION 'La dirección es obligatoria y no puede exceder 500 caracteres.'
            USING ERRCODE = 'P0001';
    END IF;
    IF p_comentarios IS NOT NULL AND length(p_comentarios) > 2000 THEN
        RAISE EXCEPTION 'Los comentarios no pueden exceder 2000 caracteres.'
            USING ERRCODE = 'P0001';
    END IF;
    IF jsonb_typeof(p_actividades) <> 'array'
       OR jsonb_array_length(p_actividades) < 1
       OR jsonb_array_length(p_actividades) > 30 THEN
        RAISE EXCEPTION 'Las actividades deben contener entre 1 y 30 celdas.'
            USING ERRCODE = 'P0001';
    END IF;
    FOR v_veces IN 0..jsonb_array_length(p_actividades) - 1 LOOP
        v_item := p_actividades -> v_veces;
        IF jsonb_typeof(v_item) <> 'string' THEN
            RAISE EXCEPTION 'Cada actividad debe ser un texto de 1 a 500 caracteres.'
                USING ERRCODE = 'P0001';
        END IF;
        v_item_texto := v_item #>> '{}';
        IF btrim(v_item_texto) = '' OR length(v_item_texto) > 500 THEN
            RAISE EXCEPTION 'Cada actividad debe ser un texto de 1 a 500 caracteres.'
                USING ERRCODE = 'P0001';
        END IF;
    END LOOP;

    -- 4. Folio global correlativo sin huecos (REQ-ACT-008): el advisory lock
    --    serializa a los escritores de actividades; el UNIQUE es la red de
    --    seguridad. Un rollback posterior no consume número.
    PERFORM pg_advisory_xact_lock(2900000001);
    SELECT COALESCE(MAX(folio_num), 0) + 1 INTO v_folio FROM actividades_reportes;

    -- 5. Snapshot de materiales consumidos con valor_unitario congelado
    --    (REQ-ACT-010). Misma fuente y convención que el acta de consumo
    --    (cm.id_lista = si.material_id, orden por material_id).
    SELECT COALESCE(jsonb_agg(
        jsonb_build_object(
            'material_id', si.material_id,
            'codigo', cm.codigo,
            'descripcion', cm.descripcion,
            'u_m', cm.u_m,
            'cantidad_consumida', si.cantidad_consumida,
            'valor_unitario', cm.valor_unitario
        ) ORDER BY si.material_id
    ), '[]'::jsonb) INTO v_materiales
      FROM seguimiento_items si
      JOIN catalogo_materiales cm ON cm.id_lista = si.material_id
     WHERE si.seguimiento_id = p_seguimiento_id
       AND si.cantidad_consumida > 0;

    -- 6. Registro documental (fecha = now(); REQ-ACT-009, REQ-ACT-015).
    INSERT INTO actividades_reportes (
        folio_num, seguimiento_id, equipo_id, vehiculo, clientes, direcciones,
        actividades, comentarios, materiales, usuario
    ) VALUES (
        v_folio, p_seguimiento_id, p_equipo_id, p_vehiculo, p_clientes,
        p_direcciones, p_actividades, p_comentarios, v_materiales, p_usuario
    ) RETURNING id INTO v_id;

    -- 7. Auditoría (convención de ACTA_CONSUMO_GENERADA: equipo_origen_id y
    --    detalles plano; REQ-ACT-012).
    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, equipo_origen_id, resultado, detalles
    ) VALUES (
        p_usuario, 'ACTIVIDAD_CONFIRMADA', p_equipo_id, 'EXITO',
        jsonb_build_object(
            'actividad_id', v_id,
            -- lpad TRUNCA si el texto excede el largo: se amplía a GREATEST(4, n)
            -- para que R10000 no se registre como R1000 (REQ-ACT-008).
            'folio', 'R' || lpad(v_folio::text, GREATEST(4, length(v_folio::text)), '0'),
            'seguimiento_id', p_seguimiento_id,
            'equipo_id', p_equipo_id
        )
    );

    RETURN v_id;
END;
$$;

--
-- Name: fn_crear_seguimiento(integer, text, jsonb, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_crear_seguimiento(p_equipo_id integer, p_observaciones text, p_items jsonb, p_usuario text) RETURNS integer
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_eliminar_inventario_fibra(integer, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_eliminar_inventario_fibra(p_material_id integer, p_motivo text DEFAULT NULL::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_generar_acta_entrega(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_generar_acta_entrega() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_mover_material(text, text, integer, numeric, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_mover_material(p_origen text, p_destino text, p_material_id integer, p_cantidad numeric, p_usuario text, p_clave_idempotencia text DEFAULT NULL::text) RETURNS jsonb
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_procesar_movimiento(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_procesar_movimiento(p_movimiento_id integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
    -- Inventario General y de Fibra Óptica (la sección FO enruta hacia el
    -- inventario_fibra unificado).
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

            ELSIF v_origen_tipo = 'FO' THEN
                -- Inventario FO unificado: inventario_fibra se resuelve por
                -- material_id.

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

            ELSIF v_destino_tipo = 'FO' THEN
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
$$;

--
-- Name: fn_sumar_cantidad(text, integer, numeric, text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_sumar_cantidad(p_destino text, p_material_id integer, p_cantidad numeric, p_usuario text, p_clave_idempotencia text DEFAULT NULL::text) RETURNS numeric
    LANGUAGE plpgsql
    AS $$
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
$$;

--
-- Name: fn_valor_total_inventario(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fn_valor_total_inventario() RETURNS numeric
    LANGUAGE sql STABLE
    AS $$
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
$$;

--
-- Name: actas_reportes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actas_reportes (
    id integer NOT NULL,
    tipo character varying(20) NOT NULL,
    movimiento_id integer,
    seguimiento_id integer,
    snapshot jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_actas_reportes_extremos CHECK (((((tipo)::text = 'ENTREGA'::text) AND (movimiento_id IS NOT NULL) AND (seguimiento_id IS NULL)) OR (((tipo)::text = 'CONSUMO'::text) AND (seguimiento_id IS NOT NULL) AND (movimiento_id IS NULL)))),
    CONSTRAINT ck_actas_reportes_tipo CHECK (((tipo)::text = ANY ((ARRAY['ENTREGA'::character varying, 'CONSUMO'::character varying])::text[])))
);

--
-- Name: actas_reportes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.actas_reportes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: actas_reportes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.actas_reportes_id_seq OWNED BY public.actas_reportes.id;

--
-- Name: actividades_reportes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actividades_reportes (
    id integer NOT NULL,
    folio_num integer NOT NULL,
    seguimiento_id integer NOT NULL,
    equipo_id integer NOT NULL,
    vehiculo character varying(100) NOT NULL,
    clientes character varying(500) NOT NULL,
    direcciones character varying(500) NOT NULL,
    actividades jsonb NOT NULL,
    comentarios character varying(2000),
    materiales jsonb NOT NULL,
    usuario character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_actividades_actividades_rango CHECK (((jsonb_typeof(actividades) = 'array'::text) AND ((jsonb_array_length(actividades) >= 1) AND (jsonb_array_length(actividades) <= 30)))),
    CONSTRAINT ck_actividades_clientes_no_vacio CHECK ((btrim((clientes)::text) <> ''::text)),
    CONSTRAINT ck_actividades_direcciones_no_vacio CHECK ((btrim((direcciones)::text) <> ''::text)),
    CONSTRAINT ck_actividades_folio_positivo CHECK ((folio_num > 0)),
    CONSTRAINT ck_actividades_materiales_array CHECK ((jsonb_typeof(materiales) = 'array'::text)),
    CONSTRAINT ck_actividades_vehiculo_no_vacio CHECK ((btrim((vehiculo)::text) <> ''::text))
);

--
-- Name: actividades_reportes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.actividades_reportes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: actividades_reportes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.actividades_reportes_id_seq OWNED BY public.actividades_reportes.id;

--
-- Name: actor_almacen_scopes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.actor_almacen_scopes (
    actor_id character varying(100) NOT NULL,
    almacen_id integer NOT NULL
);

--
-- Name: administradores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administradores (
    actor_id character varying(100) NOT NULL
);

--
-- Name: TABLE administradores; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.administradores IS 'Directriz RBAC permisiva (sec-ops): actores con rol administrador. La gestión de altas y bajas la realiza la operación; sin seeds automáticos.';

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_logs (
    log_id integer NOT NULL,
    action character varying(100) NOT NULL,
    actor character varying(100) NOT NULL,
    details jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: audit_logs_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_logs_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: audit_logs_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_logs_log_id_seq OWNED BY public.audit_logs.log_id;

--
-- Name: auditoria_eventos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auditoria_eventos (
    id bigint NOT NULL,
    usuario character varying(100),
    tipo_accion character varying(50) NOT NULL,
    material_id integer,
    equipo_origen_id integer,
    equipo_destino_id integer,
    almacen_origen_id integer,
    almacen_destino_id integer,
    cantidad numeric(12,3),
    resultado character varying(20),
    detalles json,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: auditoria_eventos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auditoria_eventos_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: auditoria_eventos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auditoria_eventos_id_seq OWNED BY public.auditoria_eventos.id;

--
-- Name: catalogo_materiales; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.catalogo_materiales (
    id_lista integer NOT NULL,
    codigo character varying(50),
    descripcion character varying(255) NOT NULL,
    categoria_id integer,
    u_m character varying(50),
    stock_minimo integer,
    is_active boolean DEFAULT true NOT NULL,
    valor_unitario numeric(12,3) DEFAULT 1.000 NOT NULL,
    CONSTRAINT ck_catalogo_stock_minimo_non_negative CHECK (((stock_minimo IS NULL) OR (stock_minimo >= 0))),
    CONSTRAINT ck_catalogo_valor_unitario_non_negative CHECK ((valor_unitario >= (0)::numeric))
);

--
-- Name: catalogo_materiales_id_lista_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.catalogo_materiales_id_lista_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: catalogo_materiales_id_lista_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.catalogo_materiales_id_lista_seq OWNED BY public.catalogo_materiales.id_lista;

--
-- Name: categorias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categorias (
    id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

--
-- Name: categorias_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.categorias_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: categorias_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.categorias_id_seq OWNED BY public.categorias.id;

--
-- Name: skus; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skus (
    sku character varying(50) NOT NULL,
    description text,
    unit_of_measure character varying(50),
    min_stock integer,
    categoria character varying(100),
    tipo character varying(20) DEFAULT 'GENERAL'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_skus_tipo CHECK (((tipo)::text = ANY ((ARRAY['GENERAL'::character varying, 'FIBRA'::character varying])::text[])))
);

--
-- Name: warehouse_inventory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.warehouse_inventory (
    warehouse_id character varying(50) NOT NULL,
    sku character varying(50) NOT NULL,
    on_hand_quantity integer DEFAULT 0 NOT NULL,
    CONSTRAINT ck_warehouse_inventory_non_negative CHECK ((on_hand_quantity >= 0))
);

--
-- Name: current_stock_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.current_stock_view AS
 SELECT s.sku,
    COALESCE(sum(wi.on_hand_quantity), (0)::bigint) AS current_stock
   FROM (public.skus s
     LEFT JOIN public.warehouse_inventory wi ON (((wi.sku)::text = (s.sku)::text)))
  GROUP BY s.sku;

--
-- Name: equipo_material_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipo_material_config (
    equipo_id integer NOT NULL,
    material_id integer NOT NULL,
    stock_minimo_local integer,
    categoria_local_id integer,
    um_local_id integer,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_equipo_material_config_stock_minimo CHECK (((stock_minimo_local IS NULL) OR (stock_minimo_local >= 0)))
);

--
-- Name: equipos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipos (
    equipo_id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    descripcion text,
    is_active boolean DEFAULT true NOT NULL
);

--
-- Name: equipos_equipo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.equipos_equipo_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: equipos_equipo_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.equipos_equipo_id_seq OWNED BY public.equipos.equipo_id;

--
-- Name: equipos_integrantes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.equipos_integrantes (
    id integer NOT NULL,
    equipo_id integer NOT NULL,
    usuario character varying(100) NOT NULL
);

--
-- Name: equipos_integrantes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.equipos_integrantes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: equipos_integrantes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.equipos_integrantes_id_seq OWNED BY public.equipos_integrantes.id;

--
-- Name: fleet_allocations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fleet_allocations (
    allocation_id integer NOT NULL,
    vehicle_id character varying(50) NOT NULL,
    warehouse_id character varying(50) NOT NULL,
    sku character varying(50) NOT NULL,
    allocated_quantity integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_fleet_allocations_positive CHECK ((allocated_quantity > 0))
);

--
-- Name: fleet_allocations_allocation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fleet_allocations_allocation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: fleet_allocations_allocation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fleet_allocations_allocation_id_seq OWNED BY public.fleet_allocations.allocation_id;

--
-- Name: historial_importaciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.historial_importaciones (
    id integer NOT NULL,
    archivo character varying(255) NOT NULL,
    formato character varying(10) NOT NULL,
    estado character varying(20) NOT NULL,
    total_registros integer DEFAULT 0 NOT NULL,
    registros_ok integer DEFAULT 0 NOT NULL,
    registros_error integer DEFAULT 0 NOT NULL,
    errores json,
    usuario character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_importaciones_estado CHECK (((estado)::text = ANY ((ARRAY['COMPLETO'::character varying, 'PARCIAL'::character varying, 'FALLIDO'::character varying])::text[]))),
    CONSTRAINT ck_importaciones_formato CHECK (((formato)::text = ANY ((ARRAY['CSV'::character varying, 'XLSX'::character varying, 'XML'::character varying])::text[])))
);

--
-- Name: historial_importaciones_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.historial_importaciones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: historial_importaciones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.historial_importaciones_id_seq OWNED BY public.historial_importaciones.id;

--
-- Name: inventario_almacen; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventario_almacen (
    almacen_id integer NOT NULL,
    material_id integer NOT NULL,
    stock_actual numeric(12,3) DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_inventario_almacen_non_negative CHECK ((stock_actual >= (0)::numeric))
);

--
-- Name: inventario_equipos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventario_equipos (
    equipo_id integer NOT NULL,
    material_id integer NOT NULL,
    stock_actual numeric(12,3) DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    ultimo_movimiento_id integer,
    CONSTRAINT ck_inventario_equipos_non_negative CHECK ((stock_actual >= (0)::numeric))
);

--
-- Name: inventario_fibra; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.inventario_fibra (
    material_id integer NOT NULL,
    stock_actual numeric(12,3) DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT ck_inventario_fibra_non_negative CHECK ((stock_actual >= (0)::numeric))
);

--
-- Name: legacy_stock_quarantine; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.legacy_stock_quarantine (
    quarantine_id integer NOT NULL,
    sku character varying(50) NOT NULL,
    current_stock integer NOT NULL,
    reason character varying(100) NOT NULL,
    quarantined_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: legacy_stock_quarantine_quarantine_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.legacy_stock_quarantine_quarantine_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: legacy_stock_quarantine_quarantine_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.legacy_stock_quarantine_quarantine_id_seq OWNED BY public.legacy_stock_quarantine.quarantine_id;

--
-- Name: mfa_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mfa_attempts (
    attempt_id bigint NOT NULL,
    actor_id character varying(100) NOT NULL,
    success boolean NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: mfa_attempts_attempt_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.mfa_attempts_attempt_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: mfa_attempts_attempt_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.mfa_attempts_attempt_id_seq OWNED BY public.mfa_attempts.attempt_id;

--
-- Name: mfa_elevations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.mfa_elevations (
    elevation_id uuid DEFAULT gen_random_uuid() NOT NULL,
    actor_id character varying(100) NOT NULL,
    transfer_id uuid NOT NULL,
    action character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    used_at timestamp with time zone
);

--
-- Name: movimientos_cabecera; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movimientos_cabecera (
    id integer NOT NULL,
    tipo_movimiento character varying(20) NOT NULL,
    estado character varying(20) DEFAULT 'BORRADOR'::character varying NOT NULL,
    usuario character varying(100) NOT NULL,
    origen_almacen_id integer,
    destino_almacen_id integer,
    origen_equipo_id integer,
    destino_equipo_id integer,
    observaciones text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_movimientos_cabecera_estado CHECK (((estado)::text = ANY ((ARRAY['BORRADOR'::character varying, 'CONFIRMADO'::character varying, 'CANCELADO'::character varying])::text[]))),
    CONSTRAINT ck_movimientos_cabecera_extremos CHECK (((((tipo_movimiento)::text = 'TEAMS'::text) AND (destino_equipo_id IS NOT NULL)) OR (((tipo_movimiento)::text = 'DEVOL'::text) AND (origen_equipo_id IS NOT NULL) AND (destino_almacen_id IS NOT NULL)))),
    CONSTRAINT ck_movimientos_cabecera_tipo CHECK (((tipo_movimiento)::text = ANY ((ARRAY['TEAMS'::character varying, 'DEVOL'::character varying])::text[])))
);

--
-- Name: movimientos_cabecera_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.movimientos_cabecera_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: movimientos_cabecera_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.movimientos_cabecera_id_seq OWNED BY public.movimientos_cabecera.id;

--
-- Name: movimientos_detalle; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.movimientos_detalle (
    movimiento_id integer NOT NULL,
    material_id integer NOT NULL,
    cantidad numeric(12,3) NOT NULL,
    origen_almacen_id integer,
    CONSTRAINT ck_movimientos_detalle_cantidad CHECK ((cantidad > (0)::numeric))
);

--
-- Name: operaciones_idempotencia; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operaciones_idempotencia (
    tipo_operacion character varying(50) NOT NULL,
    clave text NOT NULL,
    resultado jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    actor text
);

--
-- Name: secciones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.secciones (
    almacen_id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    tipo character varying(20) DEFAULT 'GENERAL'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_secciones_tipo CHECK (((tipo)::text = ANY ((ARRAY['GENERAL'::character varying, 'FO'::character varying])::text[])))
);

--
-- Name: secciones_almacen_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.secciones_almacen_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: secciones_almacen_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.secciones_almacen_id_seq OWNED BY public.secciones.almacen_id;

--
-- Name: seguimiento_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seguimiento_items (
    id integer NOT NULL,
    seguimiento_id integer NOT NULL,
    material_id integer NOT NULL,
    cantidad_tomada numeric(12,3) NOT NULL,
    cantidad_consumida numeric(12,3),
    CONSTRAINT ck_seguimiento_items_consumida CHECK (((cantidad_consumida IS NULL) OR ((cantidad_consumida >= (0)::numeric) AND ((cantidad_consumida)::numeric <= cantidad_tomada)))),
    CONSTRAINT ck_seguimiento_items_tomada CHECK ((cantidad_tomada > (0)::numeric))
);

--
-- Name: seguimiento_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seguimiento_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: seguimiento_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.seguimiento_items_id_seq OWNED BY public.seguimiento_items.id;

--
-- Name: seguimientos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seguimientos (
    id integer NOT NULL,
    equipo_id integer NOT NULL,
    fecha date DEFAULT CURRENT_DATE NOT NULL,
    observaciones text,
    usuario character varying(100) NOT NULL,
    estado character varying(20) DEFAULT 'ABIERTA'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    closed_at timestamp with time zone,
    CONSTRAINT ck_seguimientos_estado CHECK (((estado)::text = ANY ((ARRAY['ABIERTA'::character varying, 'CERRADA'::character varying])::text[])))
);

--
-- Name: seguimientos_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seguimientos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: seguimientos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.seguimientos_id_seq OWNED BY public.seguimientos.id;

--
-- Name: stock_movements; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_movements (
    movement_id bigint NOT NULL,
    transfer_id uuid,
    references_movement_id bigint,
    warehouse_id character varying(50) NOT NULL,
    sku character varying(50) NOT NULL,
    quantity_change integer NOT NULL,
    movement_type character varying(20) NOT NULL,
    actor_id character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_stock_movements_nonzero CHECK ((quantity_change <> 0)),
    CONSTRAINT ck_stock_movements_type CHECK (((movement_type)::text = ANY ((ARRAY['TRANSFER_OUT'::character varying, 'TRANSFER_IN'::character varying, 'ADJUSTMENT'::character varying, 'RECEIPT'::character varying, 'DISPATCH'::character varying])::text[])))
);

--
-- Name: stock_movements_movement_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.stock_movements_movement_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: stock_movements_movement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.stock_movements_movement_id_seq OWNED BY public.stock_movements.movement_id;

--
-- Name: stock_transfers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.stock_transfers (
    transfer_id uuid DEFAULT gen_random_uuid() NOT NULL,
    idempotency_key character varying(64) NOT NULL,
    actor_id character varying(100) NOT NULL,
    source_warehouse_id character varying(50) NOT NULL,
    destination_warehouse_id character varying(50) NOT NULL,
    status character varying(20) DEFAULT 'PENDING_APPROVAL'::character varying NOT NULL,
    requested_by character varying(100) NOT NULL,
    approved_by character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    dispatched_at timestamp with time zone,
    received_at timestamp with time zone,
    CONSTRAINT ck_stock_transfers_distinct_warehouses CHECK (((source_warehouse_id)::text <> (destination_warehouse_id)::text)),
    CONSTRAINT ck_stock_transfers_status CHECK (((status)::text = ANY ((ARRAY['PENDING_APPROVAL'::character varying, 'APPROVED'::character varying, 'IN_TRANSIT'::character varying, 'RECEIVED'::character varying, 'REJECTED'::character varying, 'CANCELLED'::character varying])::text[])))
);

--
-- Name: transfer_line_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transfer_line_items (
    line_id integer NOT NULL,
    transfer_id uuid NOT NULL,
    sku character varying(50) NOT NULL,
    dispatched_quantity integer NOT NULL,
    received_quantity integer,
    CONSTRAINT ck_transfer_line_items_dispatch_positive CHECK ((dispatched_quantity > 0)),
    CONSTRAINT ck_transfer_line_items_receive_range CHECK (((received_quantity IS NULL) OR ((received_quantity >= 0) AND (received_quantity <= dispatched_quantity))))
);

--
-- Name: transfer_line_items_line_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transfer_line_items_line_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: transfer_line_items_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transfer_line_items_line_id_seq OWNED BY public.transfer_line_items.line_id;

--
-- Name: ums; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ums (
    id integer NOT NULL,
    nombre character varying(50) NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

--
-- Name: ums_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ums_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

--
-- Name: ums_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ums_id_seq OWNED BY public.ums.id;

--
-- Name: user_mfa_seeds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_mfa_seeds (
    actor_id character varying(100) NOT NULL,
    encrypted_seed text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: user_warehouse_scopes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_warehouse_scopes (
    actor_id character varying(100) NOT NULL,
    warehouse_id character varying(50) NOT NULL,
    granted_by character varying(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

--
-- Name: vehicles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vehicles (
    vehicle_id character varying(50) NOT NULL,
    plate_or_designation character varying(50),
    assigned_crew jsonb
);

--
-- Name: warehouses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.warehouses (
    warehouse_id character varying(50) NOT NULL,
    name character varying(100) NOT NULL,
    is_active boolean DEFAULT true NOT NULL
);

--
-- Name: actas_reportes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actas_reportes ALTER COLUMN id SET DEFAULT nextval('public.actas_reportes_id_seq'::regclass);

--
-- Name: actividades_reportes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades_reportes ALTER COLUMN id SET DEFAULT nextval('public.actividades_reportes_id_seq'::regclass);

--
-- Name: audit_logs log_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs ALTER COLUMN log_id SET DEFAULT nextval('public.audit_logs_log_id_seq'::regclass);

--
-- Name: auditoria_eventos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_eventos ALTER COLUMN id SET DEFAULT nextval('public.auditoria_eventos_id_seq'::regclass);

--
-- Name: catalogo_materiales id_lista; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogo_materiales ALTER COLUMN id_lista SET DEFAULT nextval('public.catalogo_materiales_id_lista_seq'::regclass);

--
-- Name: categorias id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorias ALTER COLUMN id SET DEFAULT nextval('public.categorias_id_seq'::regclass);

--
-- Name: equipos equipo_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipos ALTER COLUMN equipo_id SET DEFAULT nextval('public.equipos_equipo_id_seq'::regclass);

--
-- Name: equipos_integrantes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipos_integrantes ALTER COLUMN id SET DEFAULT nextval('public.equipos_integrantes_id_seq'::regclass);

--
-- Name: fleet_allocations allocation_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fleet_allocations ALTER COLUMN allocation_id SET DEFAULT nextval('public.fleet_allocations_allocation_id_seq'::regclass);

--
-- Name: historial_importaciones id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_importaciones ALTER COLUMN id SET DEFAULT nextval('public.historial_importaciones_id_seq'::regclass);

--
-- Name: legacy_stock_quarantine quarantine_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_stock_quarantine ALTER COLUMN quarantine_id SET DEFAULT nextval('public.legacy_stock_quarantine_quarantine_id_seq'::regclass);

--
-- Name: mfa_attempts attempt_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mfa_attempts ALTER COLUMN attempt_id SET DEFAULT nextval('public.mfa_attempts_attempt_id_seq'::regclass);

--
-- Name: movimientos_cabecera id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_cabecera ALTER COLUMN id SET DEFAULT nextval('public.movimientos_cabecera_id_seq'::regclass);

--
-- Name: secciones almacen_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secciones ALTER COLUMN almacen_id SET DEFAULT nextval('public.secciones_almacen_id_seq'::regclass);

--
-- Name: seguimiento_items id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seguimiento_items ALTER COLUMN id SET DEFAULT nextval('public.seguimiento_items_id_seq'::regclass);

--
-- Name: seguimientos id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seguimientos ALTER COLUMN id SET DEFAULT nextval('public.seguimientos_id_seq'::regclass);

--
-- Name: stock_movements movement_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements ALTER COLUMN movement_id SET DEFAULT nextval('public.stock_movements_movement_id_seq'::regclass);

--
-- Name: transfer_line_items line_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_line_items ALTER COLUMN line_id SET DEFAULT nextval('public.transfer_line_items_line_id_seq'::regclass);

--
-- Name: ums id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ums ALTER COLUMN id SET DEFAULT nextval('public.ums_id_seq'::regclass);

--
-- Name: actas_reportes actas_reportes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actas_reportes
    ADD CONSTRAINT actas_reportes_pkey PRIMARY KEY (id);

--
-- Name: actividades_reportes actividades_reportes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades_reportes
    ADD CONSTRAINT actividades_reportes_pkey PRIMARY KEY (id);

--
-- Name: actor_almacen_scopes actor_almacen_scopes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actor_almacen_scopes
    ADD CONSTRAINT actor_almacen_scopes_pkey PRIMARY KEY (actor_id, almacen_id);

--
-- Name: administradores administradores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administradores
    ADD CONSTRAINT administradores_pkey PRIMARY KEY (actor_id);

--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);

--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (log_id);

--
-- Name: auditoria_eventos auditoria_eventos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria_eventos
    ADD CONSTRAINT auditoria_eventos_pkey PRIMARY KEY (id);

--
-- Name: catalogo_materiales catalogo_materiales_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogo_materiales
    ADD CONSTRAINT catalogo_materiales_pkey PRIMARY KEY (id_lista);

--
-- Name: categorias categorias_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorias
    ADD CONSTRAINT categorias_nombre_key UNIQUE (nombre);

--
-- Name: categorias categorias_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categorias
    ADD CONSTRAINT categorias_pkey PRIMARY KEY (id);

--
-- Name: equipo_material_config equipo_material_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipo_material_config
    ADD CONSTRAINT equipo_material_config_pkey PRIMARY KEY (equipo_id, material_id);

--
-- Name: equipos_integrantes equipos_integrantes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipos_integrantes
    ADD CONSTRAINT equipos_integrantes_pkey PRIMARY KEY (id);

--
-- Name: equipos equipos_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipos
    ADD CONSTRAINT equipos_nombre_key UNIQUE (nombre);

--
-- Name: equipos equipos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipos
    ADD CONSTRAINT equipos_pkey PRIMARY KEY (equipo_id);

--
-- Name: fleet_allocations fleet_allocations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fleet_allocations
    ADD CONSTRAINT fleet_allocations_pkey PRIMARY KEY (allocation_id);

--
-- Name: historial_importaciones historial_importaciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.historial_importaciones
    ADD CONSTRAINT historial_importaciones_pkey PRIMARY KEY (id);

--
-- Name: inventario_almacen inventario_almacen_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventario_almacen
    ADD CONSTRAINT inventario_almacen_pkey PRIMARY KEY (almacen_id, material_id);

--
-- Name: inventario_equipos inventario_equipos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventario_equipos
    ADD CONSTRAINT inventario_equipos_pkey PRIMARY KEY (equipo_id, material_id);

--
-- Name: inventario_fibra inventario_fibra_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventario_fibra
    ADD CONSTRAINT inventario_fibra_pkey PRIMARY KEY (material_id);

--
-- Name: legacy_stock_quarantine legacy_stock_quarantine_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_stock_quarantine
    ADD CONSTRAINT legacy_stock_quarantine_pkey PRIMARY KEY (quarantine_id);

--
-- Name: mfa_attempts mfa_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mfa_attempts
    ADD CONSTRAINT mfa_attempts_pkey PRIMARY KEY (attempt_id);

--
-- Name: mfa_elevations mfa_elevations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mfa_elevations
    ADD CONSTRAINT mfa_elevations_pkey PRIMARY KEY (elevation_id);

--
-- Name: movimientos_cabecera movimientos_cabecera_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_cabecera
    ADD CONSTRAINT movimientos_cabecera_pkey PRIMARY KEY (id);

--
-- Name: movimientos_detalle movimientos_detalle_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_detalle
    ADD CONSTRAINT movimientos_detalle_pkey PRIMARY KEY (movimiento_id, material_id);

--
-- Name: operaciones_idempotencia operaciones_idempotencia_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operaciones_idempotencia
    ADD CONSTRAINT operaciones_idempotencia_pkey PRIMARY KEY (tipo_operacion, clave);

--
-- Name: secciones secciones_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secciones
    ADD CONSTRAINT secciones_nombre_key UNIQUE (nombre);

--
-- Name: secciones secciones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.secciones
    ADD CONSTRAINT secciones_pkey PRIMARY KEY (almacen_id);

--
-- Name: seguimiento_items seguimiento_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seguimiento_items
    ADD CONSTRAINT seguimiento_items_pkey PRIMARY KEY (id);

--
-- Name: seguimientos seguimientos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seguimientos
    ADD CONSTRAINT seguimientos_pkey PRIMARY KEY (id);

--
-- Name: skus skus_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skus
    ADD CONSTRAINT skus_pkey PRIMARY KEY (sku);

--
-- Name: stock_movements stock_movements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_pkey PRIMARY KEY (movement_id);

--
-- Name: stock_transfers stock_transfers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_transfers
    ADD CONSTRAINT stock_transfers_pkey PRIMARY KEY (transfer_id);

--
-- Name: transfer_line_items transfer_line_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_line_items
    ADD CONSTRAINT transfer_line_items_pkey PRIMARY KEY (line_id);

--
-- Name: ums ums_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ums
    ADD CONSTRAINT ums_nombre_key UNIQUE (nombre);

--
-- Name: ums ums_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ums
    ADD CONSTRAINT ums_pkey PRIMARY KEY (id);

--
-- Name: actividades_reportes uq_actividades_folio; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades_reportes
    ADD CONSTRAINT uq_actividades_folio UNIQUE (folio_num);

--
-- Name: actividades_reportes uq_actividades_seguimiento; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades_reportes
    ADD CONSTRAINT uq_actividades_seguimiento UNIQUE (seguimiento_id);

--
-- Name: equipos_integrantes uq_equipos_integrantes_usuario; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipos_integrantes
    ADD CONSTRAINT uq_equipos_integrantes_usuario UNIQUE (equipo_id, usuario);

--
-- Name: legacy_stock_quarantine uq_legacy_stock_quarantine_sku; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_stock_quarantine
    ADD CONSTRAINT uq_legacy_stock_quarantine_sku UNIQUE (sku);

--
-- Name: seguimiento_items uq_seguimiento_items_material; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seguimiento_items
    ADD CONSTRAINT uq_seguimiento_items_material UNIQUE (seguimiento_id, material_id);

--
-- Name: stock_transfers uq_stock_transfers_actor_idempotency; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_transfers
    ADD CONSTRAINT uq_stock_transfers_actor_idempotency UNIQUE (actor_id, idempotency_key);

--
-- Name: transfer_line_items uq_transfer_line_items_transfer_sku; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_line_items
    ADD CONSTRAINT uq_transfer_line_items_transfer_sku UNIQUE (transfer_id, sku);

--
-- Name: user_mfa_seeds user_mfa_seeds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_mfa_seeds
    ADD CONSTRAINT user_mfa_seeds_pkey PRIMARY KEY (actor_id);

--
-- Name: user_warehouse_scopes user_warehouse_scopes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_warehouse_scopes
    ADD CONSTRAINT user_warehouse_scopes_pkey PRIMARY KEY (actor_id, warehouse_id);

--
-- Name: vehicles vehicles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vehicles
    ADD CONSTRAINT vehicles_pkey PRIMARY KEY (vehicle_id);

--
-- Name: warehouse_inventory warehouse_inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warehouse_inventory
    ADD CONSTRAINT warehouse_inventory_pkey PRIMARY KEY (warehouse_id, sku);

--
-- Name: warehouses warehouses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warehouses
    ADD CONSTRAINT warehouses_pkey PRIMARY KEY (warehouse_id);

--
-- Name: ix_actas_reportes_seguimiento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actas_reportes_seguimiento ON public.actas_reportes USING btree (seguimiento_id);

--
-- Name: ix_actas_reportes_tipo_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actas_reportes_tipo_created ON public.actas_reportes USING btree (tipo, created_at);

--
-- Name: ix_actividades_equipo_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actividades_equipo_created ON public.actividades_reportes USING btree (equipo_id, created_at DESC);

--
-- Name: ix_equipo_material_config_material; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_equipo_material_config_material ON public.equipo_material_config USING btree (material_id);

--
-- Name: ix_inventario_almacen_material; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventario_almacen_material ON public.inventario_almacen USING btree (material_id);

--
-- Name: ix_inventario_equipos_material; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_inventario_equipos_material ON public.inventario_equipos USING btree (material_id);

--
-- Name: ix_mfa_attempts_actor_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mfa_attempts_actor_created ON public.mfa_attempts USING btree (actor_id, created_at);

--
-- Name: ix_mfa_elevations_actor_transfer_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_mfa_elevations_actor_transfer_action ON public.mfa_elevations USING btree (actor_id, transfer_id, action);

--
-- Name: ix_movimientos_detalle_origen; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_movimientos_detalle_origen ON public.movimientos_detalle USING btree (origen_almacen_id);

--
-- Name: ix_seguimiento_items_material; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seguimiento_items_material ON public.seguimiento_items USING btree (material_id);

--
-- Name: ix_seguimientos_equipo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seguimientos_equipo ON public.seguimientos USING btree (equipo_id);

--
-- Name: ix_seguimientos_fecha; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seguimientos_fecha ON public.seguimientos USING btree (fecha);

--
-- Name: ix_stock_movements_warehouse_sku; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_stock_movements_warehouse_sku ON public.stock_movements USING btree (warehouse_id, sku);

--
-- Name: ix_warehouse_inventory_sku; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_warehouse_inventory_sku ON public.warehouse_inventory USING btree (sku);

--
-- Name: uq_catalogo_codigo_active; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_catalogo_codigo_active ON public.catalogo_materiales USING btree (codigo) WHERE (codigo IS NOT NULL);

--
-- Name: uq_seguimientos_equipo_abierta; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_seguimientos_equipo_abierta ON public.seguimientos USING btree (equipo_id) WHERE ((estado)::text = 'ABIERTA'::text);

--
-- Name: movimientos_cabecera tg_acta_entrega; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_acta_entrega AFTER UPDATE OF estado ON public.movimientos_cabecera FOR EACH ROW WHEN ((((new.estado)::text = 'CONFIRMADO'::text) AND ((new.tipo_movimiento)::text = 'TEAMS'::text) AND ((old.estado)::text IS DISTINCT FROM (new.estado)::text))) EXECUTE FUNCTION public.fn_generar_acta_entrega();

--
-- Name: categorias tg_auditar_categoria; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_auditar_categoria AFTER DELETE OR UPDATE ON public.categorias FOR EACH ROW EXECUTE FUNCTION public.fn_auditar_categoria();

--
-- Name: equipo_material_config tg_auditar_equipo_material_config; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_auditar_equipo_material_config AFTER INSERT OR UPDATE ON public.equipo_material_config FOR EACH ROW EXECUTE FUNCTION public.fn_auditar_equipo_material_config();

--
-- Name: catalogo_materiales tg_auditar_modificacion_material; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_auditar_modificacion_material AFTER UPDATE ON public.catalogo_materiales FOR EACH ROW EXECUTE FUNCTION public.fn_auditar_modificacion_material();

--
-- Name: ums tg_auditar_um; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_auditar_um AFTER DELETE OR UPDATE ON public.ums FOR EACH ROW EXECUTE FUNCTION public.fn_auditar_um();

--
-- Name: actas_reportes tg_ledger_actas_inmutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_ledger_actas_inmutable BEFORE DELETE OR UPDATE ON public.actas_reportes FOR EACH ROW EXECUTE FUNCTION public.fn_bloquear_mutacion_ledger();

--
-- Name: actividades_reportes tg_ledger_actividades_inmutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_ledger_actividades_inmutable BEFORE DELETE OR UPDATE ON public.actividades_reportes FOR EACH ROW EXECUTE FUNCTION public.fn_bloquear_mutacion_ledger();

--
-- Name: auditoria_eventos tg_ledger_auditoria_inmutable; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_ledger_auditoria_inmutable BEFORE DELETE OR UPDATE ON public.auditoria_eventos FOR EACH ROW EXECUTE FUNCTION public.fn_bloquear_mutacion_ledger();

--
-- Name: actor_almacen_scopes actor_almacen_scopes_almacen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actor_almacen_scopes
    ADD CONSTRAINT actor_almacen_scopes_almacen_id_fkey FOREIGN KEY (almacen_id) REFERENCES public.secciones(almacen_id) ON DELETE RESTRICT;

--
-- Name: catalogo_materiales catalogo_materiales_categoria_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogo_materiales
    ADD CONSTRAINT catalogo_materiales_categoria_id_fkey FOREIGN KEY (categoria_id) REFERENCES public.categorias(id) ON DELETE RESTRICT;

--
-- Name: equipos_integrantes equipos_integrantes_equipo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipos_integrantes
    ADD CONSTRAINT equipos_integrantes_equipo_id_fkey FOREIGN KEY (equipo_id) REFERENCES public.equipos(equipo_id) ON DELETE RESTRICT;

--
-- Name: actas_reportes fk_actas_reportes_movimiento; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actas_reportes
    ADD CONSTRAINT fk_actas_reportes_movimiento FOREIGN KEY (movimiento_id) REFERENCES public.movimientos_cabecera(id) ON DELETE RESTRICT;

--
-- Name: actas_reportes fk_actas_reportes_seguimiento; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actas_reportes
    ADD CONSTRAINT fk_actas_reportes_seguimiento FOREIGN KEY (seguimiento_id) REFERENCES public.seguimientos(id) ON DELETE RESTRICT;

--
-- Name: actividades_reportes fk_actividades_equipo; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades_reportes
    ADD CONSTRAINT fk_actividades_equipo FOREIGN KEY (equipo_id) REFERENCES public.equipos(equipo_id) ON DELETE RESTRICT;

--
-- Name: actividades_reportes fk_actividades_seguimiento; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actividades_reportes
    ADD CONSTRAINT fk_actividades_seguimiento FOREIGN KEY (seguimiento_id) REFERENCES public.seguimientos(id) ON DELETE RESTRICT;

--
-- Name: equipo_material_config fk_equipo_material_config_categoria; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipo_material_config
    ADD CONSTRAINT fk_equipo_material_config_categoria FOREIGN KEY (categoria_local_id) REFERENCES public.categorias(id) ON DELETE RESTRICT;

--
-- Name: equipo_material_config fk_equipo_material_config_equipo; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipo_material_config
    ADD CONSTRAINT fk_equipo_material_config_equipo FOREIGN KEY (equipo_id) REFERENCES public.equipos(equipo_id) ON DELETE RESTRICT;

--
-- Name: equipo_material_config fk_equipo_material_config_material; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipo_material_config
    ADD CONSTRAINT fk_equipo_material_config_material FOREIGN KEY (material_id) REFERENCES public.catalogo_materiales(id_lista) ON DELETE RESTRICT;

--
-- Name: equipo_material_config fk_equipo_material_config_um; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.equipo_material_config
    ADD CONSTRAINT fk_equipo_material_config_um FOREIGN KEY (um_local_id) REFERENCES public.ums(id) ON DELETE RESTRICT;

--
-- Name: inventario_fibra fk_inventario_fibra_material; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventario_fibra
    ADD CONSTRAINT fk_inventario_fibra_material FOREIGN KEY (material_id) REFERENCES public.catalogo_materiales(id_lista) ON DELETE RESTRICT;

--
-- Name: movimientos_detalle fk_movimientos_detalle_origen; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_detalle
    ADD CONSTRAINT fk_movimientos_detalle_origen FOREIGN KEY (origen_almacen_id) REFERENCES public.secciones(almacen_id) ON DELETE RESTRICT;

--
-- Name: seguimiento_items fk_seguimiento_items_material; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seguimiento_items
    ADD CONSTRAINT fk_seguimiento_items_material FOREIGN KEY (material_id) REFERENCES public.catalogo_materiales(id_lista) ON DELETE RESTRICT;

--
-- Name: seguimiento_items fk_seguimiento_items_seguimiento; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seguimiento_items
    ADD CONSTRAINT fk_seguimiento_items_seguimiento FOREIGN KEY (seguimiento_id) REFERENCES public.seguimientos(id) ON DELETE RESTRICT;

--
-- Name: seguimientos fk_seguimientos_equipo; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seguimientos
    ADD CONSTRAINT fk_seguimientos_equipo FOREIGN KEY (equipo_id) REFERENCES public.equipos(equipo_id) ON DELETE RESTRICT;

--
-- Name: fleet_allocations fleet_allocations_sku_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fleet_allocations
    ADD CONSTRAINT fleet_allocations_sku_fkey FOREIGN KEY (sku) REFERENCES public.skus(sku) ON DELETE RESTRICT;

--
-- Name: fleet_allocations fleet_allocations_vehicle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fleet_allocations
    ADD CONSTRAINT fleet_allocations_vehicle_id_fkey FOREIGN KEY (vehicle_id) REFERENCES public.vehicles(vehicle_id) ON DELETE RESTRICT;

--
-- Name: fleet_allocations fleet_allocations_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fleet_allocations
    ADD CONSTRAINT fleet_allocations_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(warehouse_id) ON DELETE RESTRICT;

--
-- Name: inventario_almacen inventario_almacen_almacen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventario_almacen
    ADD CONSTRAINT inventario_almacen_almacen_id_fkey FOREIGN KEY (almacen_id) REFERENCES public.secciones(almacen_id) ON DELETE RESTRICT;

--
-- Name: inventario_almacen inventario_almacen_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventario_almacen
    ADD CONSTRAINT inventario_almacen_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.catalogo_materiales(id_lista) ON DELETE RESTRICT;

--
-- Name: inventario_equipos inventario_equipos_equipo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventario_equipos
    ADD CONSTRAINT inventario_equipos_equipo_id_fkey FOREIGN KEY (equipo_id) REFERENCES public.equipos(equipo_id) ON DELETE RESTRICT;

--
-- Name: inventario_equipos inventario_equipos_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.inventario_equipos
    ADD CONSTRAINT inventario_equipos_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.catalogo_materiales(id_lista) ON DELETE RESTRICT;

--
-- Name: legacy_stock_quarantine legacy_stock_quarantine_sku_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.legacy_stock_quarantine
    ADD CONSTRAINT legacy_stock_quarantine_sku_fkey FOREIGN KEY (sku) REFERENCES public.skus(sku) ON DELETE RESTRICT;

--
-- Name: mfa_elevations mfa_elevations_transfer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.mfa_elevations
    ADD CONSTRAINT mfa_elevations_transfer_id_fkey FOREIGN KEY (transfer_id) REFERENCES public.stock_transfers(transfer_id) ON DELETE RESTRICT;

--
-- Name: movimientos_cabecera movimientos_cabecera_destino_almacen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_cabecera
    ADD CONSTRAINT movimientos_cabecera_destino_almacen_id_fkey FOREIGN KEY (destino_almacen_id) REFERENCES public.secciones(almacen_id) ON DELETE RESTRICT;

--
-- Name: movimientos_cabecera movimientos_cabecera_destino_equipo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_cabecera
    ADD CONSTRAINT movimientos_cabecera_destino_equipo_id_fkey FOREIGN KEY (destino_equipo_id) REFERENCES public.equipos(equipo_id) ON DELETE RESTRICT;

--
-- Name: movimientos_cabecera movimientos_cabecera_origen_almacen_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_cabecera
    ADD CONSTRAINT movimientos_cabecera_origen_almacen_id_fkey FOREIGN KEY (origen_almacen_id) REFERENCES public.secciones(almacen_id) ON DELETE RESTRICT;

--
-- Name: movimientos_cabecera movimientos_cabecera_origen_equipo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_cabecera
    ADD CONSTRAINT movimientos_cabecera_origen_equipo_id_fkey FOREIGN KEY (origen_equipo_id) REFERENCES public.equipos(equipo_id) ON DELETE RESTRICT;

--
-- Name: movimientos_detalle movimientos_detalle_material_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_detalle
    ADD CONSTRAINT movimientos_detalle_material_id_fkey FOREIGN KEY (material_id) REFERENCES public.catalogo_materiales(id_lista) ON DELETE RESTRICT;

--
-- Name: movimientos_detalle movimientos_detalle_movimiento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.movimientos_detalle
    ADD CONSTRAINT movimientos_detalle_movimiento_id_fkey FOREIGN KEY (movimiento_id) REFERENCES public.movimientos_cabecera(id) ON DELETE RESTRICT;

--
-- Name: stock_movements stock_movements_references_movement_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_references_movement_id_fkey FOREIGN KEY (references_movement_id) REFERENCES public.stock_movements(movement_id) ON DELETE RESTRICT;

--
-- Name: stock_movements stock_movements_sku_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_sku_fkey FOREIGN KEY (sku) REFERENCES public.skus(sku) ON DELETE RESTRICT;

--
-- Name: stock_movements stock_movements_transfer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_transfer_id_fkey FOREIGN KEY (transfer_id) REFERENCES public.stock_transfers(transfer_id) ON DELETE RESTRICT;

--
-- Name: stock_movements stock_movements_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_movements
    ADD CONSTRAINT stock_movements_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(warehouse_id) ON DELETE RESTRICT;

--
-- Name: stock_transfers stock_transfers_destination_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_transfers
    ADD CONSTRAINT stock_transfers_destination_warehouse_id_fkey FOREIGN KEY (destination_warehouse_id) REFERENCES public.warehouses(warehouse_id) ON DELETE RESTRICT;

--
-- Name: stock_transfers stock_transfers_source_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.stock_transfers
    ADD CONSTRAINT stock_transfers_source_warehouse_id_fkey FOREIGN KEY (source_warehouse_id) REFERENCES public.warehouses(warehouse_id) ON DELETE RESTRICT;

--
-- Name: transfer_line_items transfer_line_items_sku_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_line_items
    ADD CONSTRAINT transfer_line_items_sku_fkey FOREIGN KEY (sku) REFERENCES public.skus(sku) ON DELETE RESTRICT;

--
-- Name: transfer_line_items transfer_line_items_transfer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transfer_line_items
    ADD CONSTRAINT transfer_line_items_transfer_id_fkey FOREIGN KEY (transfer_id) REFERENCES public.stock_transfers(transfer_id) ON DELETE RESTRICT;

--
-- Name: user_warehouse_scopes user_warehouse_scopes_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_warehouse_scopes
    ADD CONSTRAINT user_warehouse_scopes_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(warehouse_id) ON DELETE RESTRICT;

--
-- Name: warehouse_inventory warehouse_inventory_sku_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warehouse_inventory
    ADD CONSTRAINT warehouse_inventory_sku_fkey FOREIGN KEY (sku) REFERENCES public.skus(sku) ON DELETE RESTRICT;

--
-- Name: warehouse_inventory warehouse_inventory_warehouse_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.warehouse_inventory
    ADD CONSTRAINT warehouse_inventory_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES public.warehouses(warehouse_id) ON DELETE RESTRICT;

--
-- PostgreSQL database dump complete
--
