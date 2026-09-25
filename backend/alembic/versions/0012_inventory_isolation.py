"""inventory isolation: equipos autónomos, FO independiente y ajustes FO

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-25

Fase 2 (Data, Schemas & Security) del pipeline SDD — implementa las Tasks
2.3, 2.4 y 2.5 del paquete 2026-09-22-frontend-backend-alignment.

Task 2.3 — Inventario autónomo de Equipos (REQ-DOMAIN-001/002):
  * DROP de la vista sparse vw_inventario_equipo_completo (abandono del
    Modelo Sparse: el catálogo global deja de heredarse por equipos).
  * Columna inventario_equipos.ultimo_movimiento_id (INT NULL): trazabilidad
    del movimiento de origen de cada entrada (REQ-DOMAIN-002). Se escribe
    EXCLUSIVAMENTE desde fn_procesar_movimiento. Sin FK declarativa a
    movimientos_cabecera por decisión de contrato: el ledger de movimientos es
    append-only (jamás se borran físicamente), por lo que el puntero lógico
    aporta la misma trazabilidad sin acoplar el inventario al ciclo de vida
    del movimiento. Las filas preexistentes quedan en NULL (sin atribución
    fabricada: el stock acumulado puede provenir de varios movimientos).
  * fn_procesar_movimiento: CAMBIO ADITIVO (REQ-API-009). Firmas, flujo,
    estados y eventos de auditoría INTACTOS. Rama TEAMS: el INSERT ... ON
    CONFLICT DO UPDATE registra ultimo_movimiento_id = p_movimiento_id tanto
    en la inserción de fila nueva como en el UPDATE de acumulación. Rama
    DEVOL: el UPDATE de inventario_equipos también setea
    ultimo_movimiento_id = p_movimiento_id.

Task 2.4 — Fibra Óptica independiente (REQ-DOMAIN-003/004/005/006):
  * Tabla inventario_fibra: PK (modulo, material_id), CHECK nombrados
    (ck_inventario_fibra_modulo, ck_inventario_fibra_non_negative), FK
    RESTRICT a catalogo_materiales(id_lista) e índice ix_inventario_fibra_material.
  * Migración de datos 100% auditada (tipo_accion 'MIGRACION_FO', detalles
    jsonb con stock y origen):
      1) Secciones FO_PAQUETE/FO_EN_USO -> inventario_fibra
         (PAQUETE/EN_USO): INSERT con acumulación ON CONFLICT, auditoría de
         cada fila y retiro de la fila fuente en inventario_almacen
         (movimiento real; cero duplicación de stock y cero pérdida, todo
         trazado en el ledger).
      2) Legacy fiber_variants: join skus.sku = catalogo_materiales.codigo;
         warehouses.name ILIKE '%paquete%' -> PAQUETE, ILIKE '%en uso%' ->
         EN_USO, resto -> PAQUETE; solo inserta si la fila destino no existe
         (no se pisa stock ya migrado desde secciones); auditado. Sin filas
         legacy no ocurre nada (guardas to_regclass + DO plpgsql seguro).
  * Soft-remove de secciones FO: is_active = FALSE. Sin DELETE físico
    (historia y FKs RESTRICT). El CHECK ck_secciones_tipo se conserva por
    compatibilidad histórica: las secciones FO quedan inactivas y sin stock.
  * DROP TABLE IF EXISTS fiber_variants (legacy ya migrada y auditada).
  * DROP TABLE IF EXISTS team_inventory (legacy 0008, sin uso en el contrato
    0010). Evaluación de riesgo verificada contra el esquema activo: cero FKs
    entrantes, cero vistas y cero funciones dependientes. ADVERTENCIA
    documentada: el downgrade profundo por debajo de 0008 queda afectado
    (0008.downgrade usa op.drop_table sin IF EXISTS); el contrato aprobado
    exige reversibilidad 0012 <-> 0011, que está garantizada.

Task 2.5 — Funciones FO y helper de ajuste general (REQ-API-002/003):
  * fn_cargar_stock_inicial_fibra: valida cantidad >= 0 y módulo válido;
    RAISE si la fila ya existe (remite a fn_ajustar_stock_fibra); audita
    'STOCK_INICIAL_FO'.
  * fn_ajustar_stock_fibra: motivo obligatorio, nuevo stock no negativo,
    SELECT ... FOR UPDATE (cero condiciones de carrera), RAISE si no hay
    fila, diferencial calculado en PostgreSQL y auditoría
    'AJUSTE_INVENTARIO_FO' con detalles jsonb completos.
  * fn_ajustar_stock_general: localiza la fila de inventario_almacen del
    material en la sección ACTIVA de tipo GENERAL (RAISE si no existe o si
    hay más de una) y delega en fn_ajustar_stock_almacen.
  * Tabla administradores (actor_id PK): directriz RBAC permisiva de
    sec-ops; la gestión de altas/bajas la realiza la operación; sin seeds
    automáticos.

downgrade() — reverso completo del contrato 0012 -> 0011:
  * DROP de las funciones nuevas, DROP TABLE inventario_fibra, recreación de
    la vista sparse con su SQL original (0010), DROP COLUMN
    ultimo_movimiento_id, DROP TABLE administradores y restauración de
    fn_procesar_movimiento original (sin el nuevo campo, SQL de ddl.sql).
  * NOTA de contrato: la migración de datos FO no se revierte (los saldos
    migrados permanecen reconstruibles en auditoria_eventos vía
    'MIGRACION_FO') y las secciones FO permanecen soft-inactivas tras el
    downgrade. Estabilidad upgrade -> downgrade -> upgrade garantizada.
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # A) INVENTARIO AUTÓNOMO DE EQUIPOS (Task 2.3, REQ-DOMAIN-001/002)
    # ================================================================

    # Abandono del Modelo Sparse: la vista de catálogo completo por equipo
    # desaparece; inventario_equipos pasa a ser la fuente física autónoma.
    op.execute(sa.text("DROP VIEW IF EXISTS vw_inventario_equipo_completo"))

    # Trazabilidad del movimiento de origen de cada entrada (REQ-DOMAIN-002).
    # Sin FK declarativa (ver docstring del módulo).
    op.execute(
        sa.text(
            "ALTER TABLE inventario_equipos "
            "ADD COLUMN IF NOT EXISTS ultimo_movimiento_id INT"
        )
    )

    # fn_procesar_movimiento: cambio aditivo REQ-API-009 (firmas, flujo,
    # estados y eventos de auditoría intactos). Se registra el movimiento de
    # origen en ambas ramas.
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

    # ================================================================
    # B) FIBRA ÓPTICA INDEPENDIENTE (Task 2.4, REQ-DOMAIN-003/004/005/006)
    # ================================================================

    op.execute(
        sa.text(
            """
CREATE TABLE IF NOT EXISTS inventario_fibra (
    modulo VARCHAR(20) NOT NULL,
    material_id INT NOT NULL,
    stock_actual INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT inventario_fibra_pkey PRIMARY KEY (modulo, material_id),
    CONSTRAINT ck_inventario_fibra_modulo CHECK (modulo IN ('PAQUETE','EN_USO')),
    CONSTRAINT ck_inventario_fibra_non_negative CHECK (stock_actual >= 0),
    CONSTRAINT fk_inventario_fibra_material FOREIGN KEY (material_id)
        REFERENCES catalogo_materiales(id_lista) ON DELETE RESTRICT
)
"""
        )
    )
    op.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_inventario_fibra_material "
            "ON inventario_fibra (material_id)"
        )
    )

    # Migración (1): secciones FO_PAQUETE/FO_EN_USO -> inventario_fibra.
    # Cada fila movida se audita (MIGRACION_FO) y se retira de su origen.
    op.execute(
        sa.text(
            """
DO $$
DECLARE
    v_fila RECORD;
    v_modulo TEXT;
BEGIN
    FOR v_fila IN
        SELECT s.almacen_id, s.tipo, ia.material_id, ia.stock_actual
        FROM secciones s
        JOIN inventario_almacen ia ON ia.almacen_id = s.almacen_id
        WHERE s.tipo IN ('FO_PAQUETE','FO_EN_USO')
    LOOP
        v_modulo := CASE WHEN v_fila.tipo = 'FO_PAQUETE' THEN 'PAQUETE' ELSE 'EN_USO' END;

        INSERT INTO inventario_fibra (modulo, material_id, stock_actual)
        VALUES (v_modulo, v_fila.material_id, v_fila.stock_actual)
        ON CONFLICT (modulo, material_id) DO UPDATE
        SET stock_actual = inventario_fibra.stock_actual + EXCLUDED.stock_actual,
            updated_at = CURRENT_TIMESTAMP;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, almacen_origen_id, cantidad, resultado, detalles
        ) VALUES (
            CURRENT_USER,
            'MIGRACION_FO',
            v_fila.material_id,
            v_fila.almacen_id,
            v_fila.stock_actual,
            'EXITO',
            jsonb_build_object(
                'modulo', v_modulo,
                'stock', v_fila.stock_actual,
                'origen', jsonb_build_object(
                    'tipo', 'seccion',
                    'seccion_id', v_fila.almacen_id,
                    'seccion_tipo', v_fila.tipo
                ),
                'fecha', CURRENT_TIMESTAMP
            )
        );

        DELETE FROM inventario_almacen
        WHERE almacen_id = v_fila.almacen_id AND material_id = v_fila.material_id;
    END LOOP;
END $$;
"""
        )
    )

    # Migración (2): legacy fiber_variants -> inventario_fibra vía
    # skus.sku = catalogo_materiales.codigo. Solo inserta si la fila destino
    # no existe. Sin filas legacy no ocurre nada (guardas to_regclass).
    op.execute(
        sa.text(
            """
DO $$
DECLARE
    v_fila RECORD;
    v_modulo TEXT;
    v_material_id INT;
    v_existe BOOLEAN;
BEGIN
    IF to_regclass('public.fiber_variants') IS NOT NULL
       AND to_regclass('public.skus') IS NOT NULL
       AND to_regclass('public.warehouses') IS NOT NULL THEN

        FOR v_fila IN
            SELECT fv.sku, fv.cantidad, w.name AS warehouse_name
            FROM fiber_variants fv
            JOIN skus s ON s.sku = fv.sku
            LEFT JOIN warehouses w ON w.warehouse_id = fv.warehouse_id
        LOOP
            SELECT cm.id_lista INTO v_material_id
            FROM catalogo_materiales cm
            WHERE cm.codigo = v_fila.sku
            LIMIT 1;

            IF v_material_id IS NULL THEN
                CONTINUE; -- sin correspondencia en el catálogo oficial: nada que migrar
            END IF;

            v_modulo := CASE
                WHEN v_fila.warehouse_name ILIKE '%paquete%' THEN 'PAQUETE'
                WHEN v_fila.warehouse_name ILIKE '%en uso%' THEN 'EN_USO'
                ELSE 'PAQUETE'
            END;

            SELECT EXISTS (
                SELECT 1 FROM inventario_fibra
                WHERE modulo = v_modulo AND material_id = v_material_id
            ) INTO v_existe;

            IF NOT v_existe THEN
                INSERT INTO inventario_fibra (modulo, material_id, stock_actual)
                VALUES (v_modulo, v_material_id, v_fila.cantidad);

                INSERT INTO auditoria_eventos (
                    usuario, tipo_accion, material_id, cantidad, resultado, detalles
                ) VALUES (
                    CURRENT_USER,
                    'MIGRACION_FO',
                    v_material_id,
                    v_fila.cantidad,
                    'EXITO',
                    jsonb_build_object(
                        'modulo', v_modulo,
                        'stock', v_fila.cantidad,
                        'origen', jsonb_build_object(
                            'tipo', 'fiber_variants',
                            'sku', v_fila.sku,
                            'warehouse', v_fila.warehouse_name
                        ),
                        'fecha', CURRENT_TIMESTAMP
                    )
                );
            END IF;
        END LOOP;
    END IF;
END $$;
"""
        )
    )

    # Soft-remove de las secciones FO (sin DELETE físico: historia y FKs
    # RESTRICT). ck_secciones_tipo se conserva por compatibilidad histórica.
    op.execute(
        sa.text(
            "UPDATE secciones SET is_active = FALSE "
            "WHERE tipo IN ('FO_PAQUETE','FO_EN_USO')"
        )
    )

    # Limpieza legacy: fiber_variants (ya migrada y auditada) y team_inventory
    # (0008, sin uso en el contrato 0010; verificado: sin FKs entrantes, sin
    # vistas ni funciones dependientes en el esquema activo).
    op.execute(sa.text("DROP TABLE IF EXISTS fiber_variants"))
    op.execute(sa.text("DROP TABLE IF EXISTS team_inventory"))

    # ================================================================
    # C) FUNCIONES FO + HELPER DE AJUSTE GENERAL (Tasks 2.4/2.5)
    # ================================================================

    op.execute(
        sa.text(
            """
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
"""
        )
    )

    op.execute(
        sa.text(
            """
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
"""
        )
    )

    op.execute(
        sa.text(
            """
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
$$ LANGUAGE plpgsql;
"""
        )
    )

    # ================================================================
    # D) TABLA DE ADMINISTRADORES (Task 2.5 / sec-ops, RBAC permisivo)
    # ================================================================

    op.execute(
        sa.text(
            """
CREATE TABLE IF NOT EXISTS administradores (
    actor_id VARCHAR(100) NOT NULL,
    CONSTRAINT administradores_pkey PRIMARY KEY (actor_id)
)
"""
        )
    )
    op.execute(
        sa.text(
            "COMMENT ON TABLE administradores IS "
            "'Directriz RBAC permisiva (sec-ops): actores con rol administrador. "
            "La gestión de altas y bajas la realiza la operación; sin seeds automáticos.'"
        )
    )


def downgrade() -> None:
    # Reverso completo del contrato 0012 -> 0011 (ver docstring del módulo).

    # 1. Funciones nuevas (en orden inverso de dependencias).
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_general(INT, INT, TEXT)"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_fibra(TEXT, INT, INT, TEXT)"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cargar_stock_inicial_fibra(TEXT, INT, INT, TEXT)"))

    # 2. Tabla inventario_fibra (los saldos migrados permanecen trazados en
    #    auditoria_eventos vía 'MIGRACION_FO').
    op.execute(sa.text("DROP TABLE IF EXISTS inventario_fibra"))

    # 3. Recreación de la vista sparse con su SQL original (0010).
    op.execute(
        sa.text(
            """
CREATE OR REPLACE VIEW vw_inventario_equipo_completo AS
SELECT
    e.equipo_id,
    cm.id_lista,
    cm.codigo,
    cm.descripcion,
    cm.u_m,
    cm.stock_minimo,
    COALESCE(ie.stock_actual, 0) AS stock_actual,
    CASE
        WHEN cm.stock_minimo IS NULL THEN FALSE
        ELSE COALESCE(ie.stock_actual, 0) <= cm.stock_minimo
    END AS alerta_stock
FROM equipos e
CROSS JOIN catalogo_materiales cm
LEFT JOIN inventario_equipos ie
    ON ie.equipo_id = e.equipo_id AND ie.material_id = cm.id_lista
WHERE e.is_active = TRUE AND cm.is_active = TRUE;
"""
        )
    )

    # 4. fn_procesar_movimiento original (sin ultimo_movimiento_id),
    #    usando el SQL canónico de ddl.sql.
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
"""
        )
    )

    # 5. Columna de trazabilidad.
    op.execute(
        sa.text(
            "ALTER TABLE inventario_equipos "
            "DROP COLUMN IF EXISTS ultimo_movimiento_id"
        )
    )

    # 6. Tabla de administradores.
    op.execute(sa.text("DROP TABLE IF EXISTS administradores"))
