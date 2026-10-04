"""Ergonomía `justificacion_opcional` — cambio
2026-10-04-ergonomia-justificacion-opcional.

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-04

Elimina la obligatoriedad del motivo en los ajustes manuales de inventario
(REQ-ERG-003/004/005). Las stored functions `fn_ajustar_stock_almacen` y
`fn_ajustar_stock_fibra` dejan de lanzar RAISE EXCEPTION cuando
`p_motivo` es NULL o vacío: el ajuste se procesa y el evento de auditoría
('AJUSTE_INVENTARIO' / 'AJUSTE_INVENTARIO_FO') registra el motivo tal como
llega (NULL permitido). El ledger inmutable (Constitution 2.4) permanece
intacto: la mutación de stock sigue auditada siempre.

La cancelación de movimientos y los borradores TEAMS/DEVOL ya toleraban
motivo/observaciones nulos; no requieren DDL adicional.

downgrade() — reverso exacto 0023 -> 0022: restaura las dos funciones con
la validación de motivo obligatorio original.
"""

from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    -- Ergonomía `justificacion_opcional` (REQ-ERG-004/005): el motivo es
    -- OPCIONAL — null o vacío se acepta y se audita tal como llega.

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
"""
        )
    )


def downgrade() -> None:
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
