"""Referencia de materiales por Unidad (Etapa 3, paquete
2026-10-referencia-materiales-unidades, T2, plan §3).

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-21

Configuración visual por Unidad: (equipo_id, material_id, cantidad_semanal)
con PK compuesta, FKs ON DELETE RESTRICT hacia equipos y el catálogo, y
CHECK de cantidad positiva (REQ-REF-011/012/018; spec §5, plan §3.1-§3.2,
D-5/D-9/P-2/P-4). cantidad_semanal NO es un saldo (RN-7): no aplican
Stored Functions de stock; toda mutación se audita por trigger en la misma
transacción (Constitución §6.2). Sin DDL sobre tablas existentes: ni una
Unidad ni un material con Referencia pueden borrarse físicamente.

No modifica tablas existentes. auditoria_eventos.tipo_accion es
varchar(50) sin CHECK de enumeración, así que los nuevos eventos
REFERENCIA_LINEA_* no requieren ampliación. El actor llega por el GUC
app.actor (fijado por el backend con set_config); NULLIF evita un actor
vacío si el GUC ya fue fijado en la sesión.

upgrade(): tabla + CHECK + PK + FKs RESTRICT + fn_auditar_referencia_materiales
(PL/pgSQL, INSERT/UPDATE/DELETE; un UPDATE que no cambia la cantidad no
emite evento) + tg_auditar_referencia_materiales + verificaciones de
esquema.

downgrade(): solo los objetos del paquete (trigger, función, tabla), sin
tocar nada preexistente. Los eventos REFERENCIA_LINEA_* ya escritos en
auditoria_eventos NO se eliminan (append-only, Constitución §2.4/§6.2).
"""

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

_FN_AUDITAR_REFERENCIA = """
CREATE OR REPLACE FUNCTION fn_auditar_referencia_materiales()
RETURNS TRIGGER
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Un UPDATE que no cambia la cantidad no emite evento (REQ-REF-012;
    -- no se usa WHEN (OLD…) porque el trigger cubre también INSERT y
    -- DELETE). La cantidad puede repetirse en un UPDATE de otros campos.
    IF TG_OP = 'UPDATE' AND OLD.cantidad_semanal IS NOT DISTINCT FROM NEW.cantidad_semanal THEN
        RETURN NEW;
    END IF;

    INSERT INTO auditoria_eventos (
        usuario, tipo_accion, material_id, resultado, detalles
    ) VALUES (
        COALESCE(NULLIF(current_setting('app.actor', true), ''), CURRENT_USER),
        CASE TG_OP
            WHEN 'INSERT' THEN 'REFERENCIA_LINEA_CREADA'
            WHEN 'UPDATE' THEN 'REFERENCIA_LINEA_MODIFICADA'
            ELSE 'REFERENCIA_LINEA_ELIMINADA'
        END,
        CASE WHEN TG_OP = 'DELETE' THEN OLD.material_id ELSE NEW.material_id END,
        'EXITO',
        jsonb_build_object(
            'equipo_id', CASE WHEN TG_OP = 'DELETE' THEN OLD.equipo_id ELSE NEW.equipo_id END,
            'modulo', 'REFERENCIA',
            'accion', CASE TG_OP
                WHEN 'INSERT' THEN 'CREAR'
                WHEN 'UPDATE' THEN 'MODIFICAR'
                ELSE 'ELIMINAR'
            END,
            'valores_anteriores', CASE WHEN TG_OP = 'INSERT' THEN NULL::jsonb
                                       ELSE jsonb_build_object('cantidad_semanal', OLD.cantidad_semanal) END,
            'valores_nuevos', CASE WHEN TG_OP = 'DELETE' THEN NULL::jsonb
                                   ELSE jsonb_build_object('cantidad_semanal', NEW.cantidad_semanal) END
        )
    );

    -- La función retorna OLD en DELETE y NEW en los demás casos.
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;
"""


def _scalar(bind: Any, query: str) -> Any:
    return bind.execute(sa.text(query)).scalar_one()


def upgrade() -> None:
    op.create_table(
        "referencia_materiales",
        sa.Column("equipo_id", sa.Integer, nullable=False),
        sa.Column("material_id", sa.Integer, nullable=False),
        sa.Column("cantidad_semanal", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "equipo_id", "material_id", name="pk_referencia_materiales"
        ),
        sa.CheckConstraint(
            "cantidad_semanal > 0", name="ck_referencia_cantidad_positiva"
        ),
        sa.ForeignKeyConstraint(
            ["equipo_id"],
            ["equipos.equipo_id"],
            name="fk_referencia_equipo",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"],
            ["catalogo_materiales.id_lista"],
            name="fk_referencia_material",
            ondelete="RESTRICT",
        ),
    )
    op.execute(sa.text(_FN_AUDITAR_REFERENCIA))
    op.execute(
        sa.text(
            "CREATE TRIGGER tg_auditar_referencia_materiales "
            "AFTER INSERT OR UPDATE OR DELETE ON referencia_materiales "
            "FOR EACH ROW EXECUTE FUNCTION fn_auditar_referencia_materiales()"
        )
    )

    # ---- Verificaciones de esquema (abortan con rollback) ----------------
    if not _scalar(
        op.get_bind(),
        "SELECT count(*) FROM pg_class WHERE relname = 'referencia_materiales'",
    ):
        raise RuntimeError("0030: la tabla referencia_materiales no existe.")
    for nombre in (
        "pk_referencia_materiales",
        "ck_referencia_cantidad_positiva",
        "fk_referencia_equipo",
        "fk_referencia_material",
    ):
        if not _scalar(
            op.get_bind(),
            f"SELECT count(*) FROM pg_constraint WHERE conname = '{nombre}'",
        ):
            raise RuntimeError(f"0030: falta la restricción {nombre}.")
    if _scalar(
        op.get_bind(),
        "SELECT tgenabled FROM pg_trigger "
        "WHERE tgname = 'tg_auditar_referencia_materiales'",
    ) != "O":
        raise RuntimeError("0030: el trigger tg_auditar_referencia_materiales no está habilitado.")
    if not _scalar(
        op.get_bind(),
        "SELECT count(*) FROM pg_proc WHERE proname = 'fn_auditar_referencia_materiales' "
        "AND pronamespace = 'public'::regnamespace",
    ):
        raise RuntimeError("0030: falta la función fn_auditar_referencia_materiales.")


def downgrade() -> None:
    """Solo los objetos del paquete, en orden inverso de dependencias:
    trigger, función y tabla. No toca nada preexistente. Los eventos
    REFERENCIA_LINEA_* ya escritos en auditoria_eventos NO se eliminan
    (append-only, Constitución §2.4/§6.2)."""
    op.execute(
        sa.text(
            "DROP TRIGGER IF EXISTS tg_auditar_referencia_materiales "
            "ON referencia_materiales"
        )
    )
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_auditar_referencia_materiales()"))
    op.drop_table("referencia_materiales")
