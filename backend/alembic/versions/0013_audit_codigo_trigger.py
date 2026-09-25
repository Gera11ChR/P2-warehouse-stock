"""audit trigger: incluir codigo (SKU) en la condición de auditoría de materiales

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-25

Fase 3.5 (Refactor & Dead Code Audit) del pipeline SDD — cierra el hallazgo
de auditoría de la Fase 3 sobre el trigger fn_auditar_modificacion_material
(creado en 0010 y presente en backend/db/ddl.sql sección 1).

Motivo (Constitution 6.2 + REQ-UI-004):
  * REQ-UI-004 (Task 3.3) habilita la edición del CÓDIGO (SKU) desde el
    formulario Modificar Material de Inventario General.
  * El trigger auditaba descripcion, categoria_id, u_m, stock_minimo e
    is_active, PERO NO codigo: un UPDATE que cambiara SOLO el SKU no emitía
    el evento MATERIAL_MODIFICADO, violando Constitution 6.2 ("All ... state
    modifications ... MUST emit immutable audit events").
  * Los jsonb valores_anteriores/valores_nuevos del evento YA incluían
    codigo, por lo que el único cambio requerido es la condición IF.

Naturaleza del cambio: ADITIVO.
  * No altera firmas de funciones ni el esquema de eventos existentes.
  * El payload jsonb de MATERIAL_MODIFICADO permanece idéntico.
  * Los eventos ya registrados en auditoria_eventos no se tocan (ledger
    append-only, Constitution 2.4).

upgrade(): CREATE OR REPLACE de fn_auditar_modificacion_material con la
  condición `OLD.codigo IS DISTINCT FROM NEW.codigo` añadida a la cláusula
  IF (resto del cuerpo idéntico al SQL de 0010/ddl.sql) y recreación del
  trigger tg_auditar_modificacion_material.

downgrade(): restaura la función con el SQL original (sin la condición de
  codigo) y recrea el trigger — reverso exacto 0013 -> 0012.
"""

from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CREATE OR REPLACE con la condición `codigo` añadida a la cláusula IF.
    # Cuerpo idéntico al SQL de 0010/ddl.sql salvo por esa única condición.
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_auditar_modificacion_material()
RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.codigo IS DISTINCT FROM NEW.codigo OR
        OLD.descripcion IS DISTINCT FROM NEW.descripcion OR
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


def downgrade() -> None:
    # Restauración exacta del SQL original (0010/ddl.sql, sin la condición
    # de codigo) y recreación del trigger. Reverso 0013 -> 0012.
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
