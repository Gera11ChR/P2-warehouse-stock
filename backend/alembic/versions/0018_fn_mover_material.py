"""fn_mover_material (Mover) entre Inventario General y módulos FO (T1.4)

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-02

Fase 1 (Base de Datos) del cambio 2026-10-01-reportes-consumo-management
(REQ-P2-INV-003/004/006/007). Operador rápido `Mover`: transferencia
directa entre el Inventario General y los módulos FO (PAQUETE/EN_USO),
con cantidad parcial (por defecto el stock completo lo envía el endpoint),
sin flujos TEAMS/DEVOL.

`fn_mover_material(p_origen, p_origen_modulo, p_destino, p_destino_modulo,
p_material_id, p_cantidad, p_usuario, p_clave_idempotencia) RETURNS JSONB`
({stock_origen, stock_destino} posteriores al movimiento):

* Validaciones (todas RAISE, todo dentro de UNA transacción):
  - origen/destino IN ('GENERAL','FO'); módulos FO válidos cuando aplica.
  - destino != origen (GENERAL->GENERAL y FO modulo->mismo módulo
    rechazados; PAQUETE<->EN_USO es un movimiento válido entre módulos).
  - cantidad > 0 (cero y negativos rechazados).
  - material activo en catalogo_materiales.
  - cantidad <= stock del origen ('Stock insuficiente en Origen...').
* Concurrencia: bloqueo FOR UPDATE con ORDEN DETERMINISTA — primero la
  fila GENERAL (si participa) y después las filas FO ordenadas por modulo
  ascendente. Dos movimientos opuestos sobre el mismo material (p.ej.
  GENERAL->FO y FO->GENERAL) serializan sin deadlock. Cero condiciones de
  carrera sobre el stock.
* Evento de auditoría inmutable `MOVIMIENTO_INVENTARIO` con snapshot
  completo jsonb (origen/destino, stocks antes/después, usuario, clave).
* Guarda de idempotencia (REQ-P2-INV-007) en operaciones_idempotencia
  (creada en 0017): doble ejecución con la misma clave no duplica efectos.

DECISIÓN DE SEMÁNTICA DISPERSA (sparse_equipment_model, documentada como
exige REQ-P2-INV-003):

  1. Fila destino: se crea SOLO con stock > 0. Como p_cantidad > 0 es
     obligatorio, toda fila de destino creada por este SP nace con stock
     positivo; si ya existe, el UPSERT acumula. Nunca se crean filas de
     inventario con stock 0.
  2. Fila origen con stock 0 tras el movimiento: SE CONSERVA (no se
     elimina). Razones:
     a) Consistencia con el comportamiento existente del dominio:
        fn_cerrar_despliegue/fn_cerrar_seguimiento descuentan el inventario
        del equipo "SIN eliminar filas que lleguen a 0" (0014) y
        fn_procesar_movimiento conserva las filas de inventario_equipos en
        0 tras una DEVOL completa.
     b) El modelo disperso exige filas "con existencias o movimientos
        reales": una fila llevada a 0 TIENE historial real de movimientos;
        conservarla mantiene el rastro (ultimo estado, auditoría por
        material) sin inventar una semántica de baja.
     c) Eliminar la fila mezclaría este operador con la semántica de
        ELIMINACION_FO (fn_eliminar_inventario_fibra, con reglas propias
        de motivo obligatorio): un `Mover` completo NO es una baja de
        inventario y no debe auditarse como tal.
     d) Evita operaciones destructivas: el ledger y las lecturas por
        material siguen resolviendo la fila (stock 0) en lugar de perderla.
  3. Coherencia U.M./catálogo entre origen y destino: GARANTIZADA POR
     CONSTRUCCIÓN — ambos extremos referencian el MISMO
     catalogo_materiales.id_lista; `u_m` es un atributo escalar de la fila
     de catálogo (no del inventario), de modo que no puede divergir. La
     validación defensiva de material activo (paso 1) cubre además el caso
     de catálogo inactivo en el momento del movimiento.

CERO aritmética de stock en Python (Invariante 2): descuento, acreditación
y auditoría viven íntegros en PL/pgSQL.

downgrade() — reverso exacto 0018 -> 0017: DROP de la función. No hay
tablas ni datos migrados (el movimiento queda trazado en
auditoria_eventos como MOVIMIENTO_INVENTARIO).
"""

from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # A) FN_MOVER_MATERIAL — transferencia directa General <-> FO
    # ================================================================
    op.execute(
        sa.text(
            """
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
        )
    )


def downgrade() -> None:
    # Reverso exacto 0018 -> 0017 (ver docstring del módulo).
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS fn_mover_material(TEXT, TEXT, TEXT, TEXT, INT, INT, TEXT, TEXT)"
        )
    )
