"""dms-telecom contract: tablas, stored functions, trigger y vista sparse

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-14

Materializa el contrato OpenSpec v1.0.0 + DDL 10/10 del proyecto DMS - TELECOM:
  * catalogo_materiales con id_lista INMUTABLE (SERIAL, sin reutilización)
  * secciones + inventario_almacen (erradicación del término legacy almacenes)
  * inventario_equipos como Sparse Model (solo filas con existencias reales)
  * movimientos_cabecera/detalle con estados BORRADOR/CONFIRMADO/CANCELADO
  * auditoria_eventos append-only (Constitution 2.4)
  * fn_procesar_movimiento / fn_cancelar_movimiento / trigger de auditoría
  * vw_inventario_equipo_completo (catálogo completo con stock 0 renderizado)
"""

from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )

    op.create_table(
        "catalogo_materiales",
        sa.Column("id_lista", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("codigo", sa.String(50), nullable=True),
        sa.Column("descripcion", sa.String(255), nullable=False),
        sa.Column(
            "categoria_id",
            sa.Integer(),
            sa.ForeignKey("categorias.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("u_m", sa.String(50), nullable=True),
        sa.Column("stock_minimo", sa.Integer(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.CheckConstraint(
            "stock_minimo IS NULL OR stock_minimo >= 0",
            name="ck_catalogo_stock_minimo_non_negative",
        ),
    )
    op.create_index(
        "uq_catalogo_codigo_active",
        "catalogo_materiales",
        ["codigo"],
        unique=True,
        postgresql_where=sa.text("codigo IS NOT NULL"),
    )

    op.create_table(
        "secciones",
        sa.Column("almacen_id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "tipo",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'GENERAL'"),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.CheckConstraint(
            "tipo IN ('GENERAL','FO_PAQUETE','FO_EN_USO')",
            name="ck_secciones_tipo",
        ),
    )

    op.create_table(
        "equipos",
        sa.Column("equipo_id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("nombre", sa.String(100), nullable=False, unique=True),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
    )

    op.create_table(
        "equipos_integrantes",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "equipo_id",
            sa.Integer(),
            sa.ForeignKey("equipos.equipo_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("usuario", sa.String(100), nullable=False),
        sa.UniqueConstraint(
            "equipo_id", "usuario", name="uq_equipos_integrantes_usuario"
        ),
    )

    op.create_table(
        "inventario_almacen",
        sa.Column(
            "almacen_id",
            sa.Integer(),
            sa.ForeignKey("secciones.almacen_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "material_id",
            sa.Integer(),
            sa.ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("stock_actual", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "stock_actual >= 0", name="ck_inventario_almacen_non_negative"
        ),
    )
    op.create_index(
        "ix_inventario_almacen_material", "inventario_almacen", ["material_id"]
    )

    op.create_table(
        "inventario_equipos",
        sa.Column(
            "equipo_id",
            sa.Integer(),
            sa.ForeignKey("equipos.equipo_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "material_id",
            sa.Integer(),
            sa.ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("stock_actual", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "stock_actual >= 0", name="ck_inventario_equipos_non_negative"
        ),
    )
    op.create_index(
        "ix_inventario_equipos_material", "inventario_equipos", ["material_id"]
    )

    op.create_table(
        "movimientos_cabecera",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("tipo_movimiento", sa.String(20), nullable=False),
        sa.Column(
            "estado",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'BORRADOR'"),
        ),
        sa.Column("usuario", sa.String(100), nullable=False),
        sa.Column(
            "origen_almacen_id",
            sa.Integer(),
            sa.ForeignKey("secciones.almacen_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "destino_almacen_id",
            sa.Integer(),
            sa.ForeignKey("secciones.almacen_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "origen_equipo_id",
            sa.Integer(),
            sa.ForeignKey("equipos.equipo_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "destino_equipo_id",
            sa.Integer(),
            sa.ForeignKey("equipos.equipo_id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("observaciones", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "tipo_movimiento IN ('TEAMS','DEVOL')",
            name="ck_movimientos_cabecera_tipo",
        ),
        sa.CheckConstraint(
            "estado IN ('BORRADOR','CONFIRMADO','CANCELADO')",
            name="ck_movimientos_cabecera_estado",
        ),
        sa.CheckConstraint(
            "(tipo_movimiento = 'TEAMS' AND origen_almacen_id IS NOT NULL AND destino_equipo_id IS NOT NULL) "
            "OR (tipo_movimiento = 'DEVOL' AND origen_equipo_id IS NOT NULL AND destino_almacen_id IS NOT NULL)",
            name="ck_movimientos_cabecera_extremos",
        ),
    )

    op.create_table(
        "movimientos_detalle",
        sa.Column(
            "movimiento_id",
            sa.Integer(),
            sa.ForeignKey("movimientos_cabecera.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "material_id",
            sa.Integer(),
            sa.ForeignKey("catalogo_materiales.id_lista", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "cantidad > 0", name="ck_movimientos_detalle_cantidad"
        ),
    )

    op.create_table(
        "auditoria_eventos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("usuario", sa.String(100), nullable=True),
        sa.Column("tipo_accion", sa.String(50), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=True),
        sa.Column("equipo_origen_id", sa.Integer(), nullable=True),
        sa.Column("equipo_destino_id", sa.Integer(), nullable=True),
        sa.Column("almacen_origen_id", sa.Integer(), nullable=True),
        sa.Column("almacen_destino_id", sa.Integer(), nullable=True),
        sa.Column("cantidad", sa.Integer(), nullable=True),
        sa.Column("resultado", sa.String(20), nullable=True),
        sa.Column("detalles", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "historial_importaciones",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("archivo", sa.String(255), nullable=False),
        sa.Column("formato", sa.String(10), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False),
        sa.Column("total_registros", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("registros_ok", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("registros_error", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errores", sa.JSON(), nullable=True),
        sa.Column("usuario", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "formato IN ('CSV','XLSX','XML')", name="ck_importaciones_formato"
        ),
        sa.CheckConstraint(
            "estado IN ('COMPLETO','PARCIAL','FALLIDO')",
            name="ck_importaciones_estado",
        ),
    )

    op.create_table(
        "actor_almacen_scopes",
        sa.Column("actor_id", sa.String(100), primary_key=True),
        sa.Column(
            "almacen_id",
            sa.Integer(),
            sa.ForeignKey("secciones.almacen_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )

    # Secciones semilla del SDD (inventarios origen permitidos)
    op.execute(
        sa.text(
            "INSERT INTO secciones (nombre, tipo) VALUES "
            "('Inventario General', 'GENERAL'), "
            "('Fibra Optica - Paquete', 'FO_PAQUETE'), "
            "('Fibra Optica - En Uso', 'FO_EN_USO')"
        )
    )

    # Trigger de auditoría de modificaciones de catálogo
    op.execute(
        sa.text(
            """
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
"""
        )
    )

    # Función transaccional TEAMS/DEVOL (bloqueos FOR UPDATE + auditoría)
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

    # Función de cancelación y reversión (blindada, CONFIRMADO -> CANCELADO)
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

    # Vista sparse: catálogo completo por equipo con stock 0 renderizado
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


def downgrade() -> None:
    op.execute(sa.text("DROP VIEW IF EXISTS vw_inventario_equipo_completo"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cancelar_movimiento(INT, TEXT)"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_procesar_movimiento(INT)"))
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS tg_auditar_modificacion_material ON catalogo_materiales"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_auditar_modificacion_material()"))
    op.drop_table("actor_almacen_scopes")
    op.drop_table("historial_importaciones")
    op.drop_table("auditoria_eventos")
    op.drop_table("movimientos_detalle")
    op.drop_table("movimientos_cabecera")
    op.drop_table("inventario_equipos")
    op.drop_table("inventario_almacen")
    op.drop_table("equipos_integrantes")
    op.drop_table("equipos")
    op.drop_table("secciones")
    op.drop_table("catalogo_materiales")
    op.drop_table("categorias")
