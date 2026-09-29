"""FO CRUD management: eliminación física auditada de inventario_fibra

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-29

Fase 2 (Data, Schemas & Security) del pipeline SDD — implementa la Task 2.2
del paquete 2026-09-29-fo-crud-management (propuesta aprobada):

  fn_eliminar_inventario_fibra(p_modulo, p_material_id, p_motivo):
  eliminación FÍSICA de la fila (modulo, material_id) de inventario_fibra
  (REQ-DEL-001/002/003/004):

  1) Valida p_modulo IN ('PAQUETE','EN_USO') → RAISE EXCEPTION en otro caso.
  2) SELECT stock_actual ... FOR UPDATE (cero condiciones de carrera); si
     la fila no existe → RAISE EXCEPTION 'No se encuentra registro de
     inventario para el material ID % en el módulo FO %...' (el mapeo
     existente de transaccional._mapear_raise_exception lo traduce a 404).
  3) REQ-DEL-004: si stock_actual > 0 el motivo es obligatorio y no vacío
     (RAISE → 422 vía el mapeo "motivo"); con stock 0 es opcional.
  4) DELETE de ÚNICAMENTE la fila del módulo: catalogo_materiales, el
     inventario del otro módulo FO y el Inventario General permanecen
     intactos (aislamiento por módulo, REQ-DEL-003).
  5) Auditoría 'ELIMINACION_FO' con snapshot completo jsonb (modulo,
     material_id, stock_eliminado, motivo, usuario, fecha): el stock
     eliminado queda reconstruible en el ledger inmutable (Constitution
     6.2). Atribución del actor vía set_config('app.actor', ...) — patrón
     _set_actor de services/catalogo.py — con fallback a CURRENT_USER.

CERO aritmética de stock en Python y CERO escritura directa de
inventario_fibra desde el backend (Invariantes 2 y 5): la función es la
única vía de eliminación. La reintroducción de stock requiere una nueva
carga inicial FO (fn_cargar_stock_inicial_fibra) o el UPSERT preexistente
de fn_procesar_movimiento en una devolución DEVOL (REQ-TRF-INV-003).

downgrade() — reverso exacto 0015 -> 0014: DROP de la función
fn_eliminar_inventario_fibra(TEXT, INT, TEXT). No hay datos migrados ni
objetos adicionales: cero pérdida de información (las filas eliminadas
durante el uso quedan trazadas en auditoria_eventos como 'ELIMINACION_FO').
"""

from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # A) FN_ELIMINAR_INVENTARIO_FIBRA — eliminación física por módulo
    #    (REQ-DEL-001/002/003/004), 100 % PostgreSQL
    # ================================================================

    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_eliminar_inventario_fibra (
    p_modulo TEXT,
    p_material_id INT,
    p_motivo TEXT DEFAULT NULL
)
RETURNS VOID AS $$
DECLARE
    v_stock_anterior INT;
BEGIN
    IF p_modulo IS NULL OR p_modulo NOT IN ('PAQUETE','EN_USO') THEN
        RAISE EXCEPTION 'El módulo de Fibra Óptica debe ser PAQUETE o EN_USO (recibido: %).', p_modulo;
    END IF;

    -- Bloqueo FOR UPDATE: cero condiciones de carrera sobre inventario_fibra.
    SELECT stock_actual INTO v_stock_anterior
    FROM inventario_fibra
    WHERE modulo = p_modulo AND material_id = p_material_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el módulo FO %. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
            p_material_id, p_modulo;
    END IF;

    -- REQ-DEL-004: con existencias, el motivo es obligatorio y no vacío
    -- (RAISE -> 422 vía el mapeo "motivo" de transaccional).
    IF v_stock_anterior > 0 AND (p_motivo IS NULL OR TRIM(p_motivo) = '') THEN
        RAISE EXCEPTION 'Es obligatorio proporcionar un motivo para eliminar inventario FO con existencias (material ID %, módulo %, stock %).',
            p_material_id, p_modulo, v_stock_anterior;
    END IF;

    -- Eliminación física SOLO de la fila del módulo indicado
    -- (REQ-DEL-003: aislamiento por módulo; catálogo e Inventario General intactos).
    DELETE FROM inventario_fibra
    WHERE modulo = p_modulo AND material_id = p_material_id;

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
            'modulo', p_modulo,
            'material_id', p_material_id,
            'stock_eliminado', v_stock_anterior,
            'motivo', p_motivo,
            'usuario', COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER),
            'fecha', CURRENT_TIMESTAMP
        )
    );
END;
$$ LANGUAGE plpgsql;
"""
        )
    )


def downgrade() -> None:
    # Reverso exacto 0015 -> 0014 (ver docstring del módulo): la función es
    # el único objeto creado por esta migración.
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS fn_eliminar_inventario_fibra(TEXT, INT, TEXT)"
        )
    )
