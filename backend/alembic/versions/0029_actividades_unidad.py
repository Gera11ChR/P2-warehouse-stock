"""Actividades por Unidad (Etapa 1, paquete 2026-10-actividades-unidad, T2,
plan §2).

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-19

Registro documental inmutable de actividades de la jornada: 1 actividad = 1
seguimiento CERRADA (UNIQUE). Folio global correlativo sin huecos entre
transacciones confirmadas (pg_advisory_xact_lock + MAX+1; la secuencia
común deja huecos ante rollback), fecha = now() (timestamptz) y snapshot de
materiales consumidos con valor_unitario congelado, derivado íntegramente en
PostgreSQL (REQ-ACT-008/009/010/011/012/015; spec §4-5, plan D-1..D-5).

No modifica tablas existentes. auditoria_eventos.tipo_accion es varchar(50)
sin CHECK de enumeración (verificado en T1), así que el nuevo evento
ACTIVIDAD_CONFIRMADA no requiere ampliación.

upgrade(): tabla + CHECKs + UNIQUEs + FKs RESTRICT + índice + trigger de
inmutabilidad (reutiliza fn_bloquear_mutacion_ledger, sin modificarla) +
fn_crear_actividad (VOLATILE) + fn_actividad_pendiente (STABLE, solo
lectura) + verificaciones de esquema.

downgrade(): solo esquema (funciones, trigger, índice, tabla). Los eventos
ACTIVIDAD_CONFIRMADA ya escritos en auditoria_eventos NO se eliminan
(append-only, Constitución §2.4); no se recrean filas.
"""

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

# Clave fija del advisory lock de folio (bigint, dominio privado 29-000000001).
_ADVISORY_FOLIO = 2900000001

_FN_CREAR_ACTIVIDAD = f"""
CREATE OR REPLACE FUNCTION fn_crear_actividad(
    p_equipo_id integer,
    p_seguimiento_id integer,
    p_vehiculo text,
    p_clientes text,
    p_direcciones text,
    p_actividades jsonb,
    p_comentarios text,
    p_usuario text
) RETURNS integer
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
        v_item_texto := v_item #>> '{{}}';
        IF btrim(v_item_texto) = '' OR length(v_item_texto) > 500 THEN
            RAISE EXCEPTION 'Cada actividad debe ser un texto de 1 a 500 caracteres.'
                USING ERRCODE = 'P0001';
        END IF;
    END LOOP;

    -- 4. Folio global correlativo sin huecos (REQ-ACT-008): el advisory lock
    --    serializa a los escritores de actividades; el UNIQUE es la red de
    --    seguridad. Un rollback posterior no consume número.
    PERFORM pg_advisory_xact_lock({_ADVISORY_FOLIO});
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
"""

_FN_ACTIVIDAD_PENDIENTE = """
CREATE OR REPLACE FUNCTION fn_actividad_pendiente(p_equipo_id integer)
RETURNS TABLE(
    seguimiento_id integer,
    fecha_cierre timestamp with time zone,
    materiales jsonb
)
    LANGUAGE sql
    STABLE
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
"""


def _scalar(bind: Any, query: str) -> Any:
    return bind.execute(sa.text(query)).scalar_one()


def upgrade() -> None:
    op.create_table(
        "actividades_reportes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("folio_num", sa.Integer, nullable=False),
        sa.Column("seguimiento_id", sa.Integer, nullable=False),
        sa.Column("equipo_id", sa.Integer, nullable=False),
        sa.Column("vehiculo", sa.String(100), nullable=False),
        sa.Column("clientes", sa.String(500), nullable=False),
        sa.Column("direcciones", sa.String(500), nullable=False),
        sa.Column("actividades", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("comentarios", sa.String(2000), nullable=True),
        sa.Column("materiales", sa.dialects.postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("usuario", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("folio_num > 0", name="ck_actividades_folio_positivo"),
        sa.CheckConstraint(
            "btrim(vehiculo) <> ''", name="ck_actividades_vehiculo_no_vacio"
        ),
        sa.CheckConstraint(
            "btrim(clientes) <> ''", name="ck_actividades_clientes_no_vacio"
        ),
        sa.CheckConstraint(
            "btrim(direcciones) <> ''", name="ck_actividades_direcciones_no_vacio"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(actividades) = 'array' AND jsonb_array_length(actividades) BETWEEN 1 AND 30",
            name="ck_actividades_actividades_rango",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(materiales) = 'array'", name="ck_actividades_materiales_array"
        ),
        sa.UniqueConstraint("folio_num", name="uq_actividades_folio"),
        sa.UniqueConstraint("seguimiento_id", name="uq_actividades_seguimiento"),
        sa.ForeignKeyConstraint(
            ["seguimiento_id"],
            ["seguimientos.id"],
            name="fk_actividades_seguimiento",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["equipo_id"],
            ["equipos.equipo_id"],
            name="fk_actividades_equipo",
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_actividades_equipo_created",
        "actividades_reportes",
        ["equipo_id", sa.text("created_at DESC")],
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER tg_ledger_actividades_inmutable "
            "BEFORE UPDATE OR DELETE ON actividades_reportes "
            "FOR EACH ROW EXECUTE FUNCTION fn_bloquear_mutacion_ledger()"
        )
    )
    op.execute(sa.text(_FN_CREAR_ACTIVIDAD))
    op.execute(sa.text(_FN_ACTIVIDAD_PENDIENTE))

    # ---- Verificaciones de esquema (abortan con rollback) ----------------
    if not _scalar(
        op.get_bind(),
        "SELECT count(*) FROM pg_class WHERE relname = 'actividades_reportes'",
    ):
        raise RuntimeError("0029: la tabla actividades_reportes no existe.")
    for nombre in (
        "ck_actividades_folio_positivo",
        "ck_actividades_vehiculo_no_vacio",
        "ck_actividades_clientes_no_vacio",
        "ck_actividades_direcciones_no_vacio",
        "ck_actividades_actividades_rango",
        "ck_actividades_materiales_array",
        "uq_actividades_folio",
        "uq_actividades_seguimiento",
        "fk_actividades_seguimiento",
        "fk_actividades_equipo",
    ):
        if not _scalar(
            op.get_bind(),
            f"SELECT count(*) FROM pg_constraint WHERE conname = '{nombre}'",
        ):
            raise RuntimeError(f"0029: falta la restricción {nombre}.")
    if _scalar(
        op.get_bind(),
        "SELECT tgenabled FROM pg_trigger WHERE tgname = 'tg_ledger_actividades_inmutable'",
    ) != "O":
        raise RuntimeError("0029: el trigger tg_ledger_actividades_inmutable no está habilitado.")
    if not _scalar(
        op.get_bind(),
        "SELECT count(*) FROM pg_proc WHERE proname = 'fn_crear_actividad' "
        "AND pronamespace = 'public'::regnamespace",
    ) or not _scalar(
        op.get_bind(),
        "SELECT count(*) FROM pg_proc WHERE proname = 'fn_actividad_pendiente' "
        "AND pronamespace = 'public'::regnamespace",
    ):
        raise RuntimeError("0029: falta alguna de las funciones fn_crear_actividad/fn_actividad_pendiente.")


def downgrade() -> None:
    """Solo esquema: funciones, trigger, índice y tabla. No toca los eventos
    ACTIVIDAD_CONFIRMADA ya escritos (append-only) ni recrea filas."""
    op.execute(sa.text("DROP FUNCTION IF EXISTS fn_actividad_pendiente(integer)"))
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS fn_crear_actividad("
            "integer, integer, text, text, text, jsonb, text, text)"
        )
    )
    op.execute(
        sa.text("DROP TRIGGER IF EXISTS tg_ledger_actividades_inmutable ON actividades_reportes")
    )
    op.drop_index("ix_actividades_equipo_created", table_name="actividades_reportes")
    op.drop_table("actividades_reportes")
