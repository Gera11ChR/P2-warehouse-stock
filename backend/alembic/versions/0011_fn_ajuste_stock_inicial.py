"""ajuste inicial: fn_cargar_stock_inicial y fn_ajustar_stock_almacen

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-14

Cambio minor (non-breaking) v1.1.0 del contrato OpenSpec:
  * fn_cargar_stock_inicial: alta única e idempotente de inventario
    (usada por el alta de material con stock inicial).
  * fn_ajustar_stock_almacen: ajuste administrativo con motivo obligatorio,
    diferencial y auditoría calculados íntegramente en PostgreSQL.
"""

from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
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
$$ LANGUAGE plpgsql;
"""
        )
    )

    op.execute(
        sa.text(
            """
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

    SELECT stock_actual INTO v_stock_anterior
    FROM inventario_almacen
    WHERE almacen_id = p_almacen_id AND material_id = p_material_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el almacén ID %. Realice primero la carga inicial.',
            p_material_id, p_almacen_id;
    END IF;

    v_diferencia := p_nuevo_stock - v_stock_anterior;

    UPDATE inventario_almacen
    SET stock_actual = p_nuevo_stock, updated_at = CURRENT_TIMESTAMP
    WHERE almacen_id = p_almacen_id AND material_id = p_material_id;

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
"""
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_ajustar_stock_almacen(INT, INT, INT, TEXT)"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_cargar_stock_inicial(INT, INT, INT, TEXT)"))
