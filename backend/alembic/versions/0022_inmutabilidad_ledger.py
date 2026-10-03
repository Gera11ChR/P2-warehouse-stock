"""Endurecimiento de la inmutabilidad del ledger (Fase 5, recomendación
D-4 de la auditoría final) — cambio 2026-10-01-reportes-consumo-management.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-02

`auditoria_eventos` y `actas_reportes` eran inmutables solo por convención
de dominio (ningún UPDATE/DELETE en `app/` ni en migraciones). Los `REVOKE`
no detienen al OWNER de la tabla (el rol de la aplicación es dueño), por lo
que el endurecimiento se implementa con triggers que lanzan RAISE EXCEPTION
ante cualquier UPDATE o DELETE de fila, en ambas tablas:

  * tg_ledger_auditoria_inmutable — BEFORE UPDATE OR DELETE ON auditoria_eventos
  * tg_ledger_actas_inmutable    — BEFORE UPDATE OR DELETE ON actas_reportes

Nota deliberada: NO se bloquea TRUNCATE, porque los fixtures de pytest
(TRUNCATE + resiembra sobre p2_test) dependen de él y la operación exige
privilegio de TRUNCATE que solo el dueño posee.

downgrade() — reverso exacto 0022 -> 0021: DROP de los dos triggers y de la
función.
"""

from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_bloquear_mutacion_ledger()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'La tabla % es append-only (ledger inmutable): UPDATE y DELETE están prohibidos.',
        TG_TABLE_NAME
        USING ERRCODE = 'P0001';
END;
$$ LANGUAGE plpgsql;
"""
        )
    )
    op.execute(
        sa.text(
            """
CREATE TRIGGER tg_ledger_auditoria_inmutable
BEFORE UPDATE OR DELETE ON auditoria_eventos
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_mutacion_ledger();
"""
        )
    )
    op.execute(
        sa.text(
            """
CREATE TRIGGER tg_ledger_actas_inmutable
BEFORE UPDATE OR DELETE ON actas_reportes
FOR EACH ROW EXECUTE FUNCTION fn_bloquear_mutacion_ledger();
"""
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DROP TRIGGER IF EXISTS tg_ledger_auditoria_inmutable ON auditoria_eventos")
    )
    op.execute(
        sa.text("DROP TRIGGER IF EXISTS tg_ledger_actas_inmutable ON actas_reportes")
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_bloquear_mutacion_ledger()"))
