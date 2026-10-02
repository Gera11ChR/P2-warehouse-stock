"""fn_agregar_todo_seguimiento (Agregar todo) (T1.5)

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-02

Fase 1 (Base de Datos) del cambio 2026-10-01-reportes-consumo-management
(REQ-P2-CON-003/004, REQ-P2-INV-006/007). Botón "Agregar todo" del flujo
CONSUMO: carga la totalidad de las líneas con stock del inventario propio
e independiente del equipo en el seguimiento ABIERTA activo.

`fn_agregar_todo_seguimiento(p_seguimiento_id, p_equipo_id, p_usuario,
p_clave_idempotencia) RETURNS INT (líneas agregadas)`:

* Validaciones: el seguimiento debe existir (RAISE 'Seguimiento ID % no
  encontrado.'), pertenecer al equipo indicado (RAISE 'El seguimiento ID %
  no pertenece al equipo ID %.') y estar en estado ABIERTA (RAISE 'El
  seguimiento ID % no se encuentra en estado ABIERTA.').
* Concurrencia: bloqueo FOR UPDATE de la cabecera del seguimiento
  (serializa con fn_cerrar_seguimiento y con dobles invocaciones
  concurrentes) y de las líneas de inventario_equipos del equipo en orden
  determinista por material_id (mismo orden de bloqueo que
  fn_cerrar_seguimiento: cero deadlocks). El stock se lee BAJO bloqueo.
* IDEMPOTENCIA (REQ-P2-CON-004): inserción con ON CONFLICT
  (seguimiento_id, material_id) DO NOTHING — una doble invocación NO
  duplica líneas y NO altera las líneas ya presentes (ni las creadas en
  fn_crear_seguimiento ni las agregadas por una invocación previa). Las
  líneas del inventario con stock 0 se omiten (ck_seguimiento_items_tomada
  exige cantidad_tomada > 0; el modelo disperso solo aporta existencias
  reales).
* Evento de auditoría `AGREGAR_TODO` SOLO cuando se agrega al menos una
  línea nueva (un reenvío no duplica eventos en el ledger inmutable).
* Guarda de idempotencia por clave en operaciones_idempotencia
  (REQ-P2-INV-007, tabla de 0017), opcional y dentro de la misma
  transacción.

CERO aritmética de stock en Python y CERO escritura directa de
seguimiento_items/inventario_equipos desde el backend: todo vive en
PL/pgSQL.

downgrade() — reverso exacto 0019 -> 0018: DROP de la función. No hay
tablas ni datos migrados (el evento AGREGAR_TODO queda en el ledger).
"""

from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # A) FN_AGREGAR_TODO_SEGUIMIENTO — carga total del inventario del
    #    equipo al seguimiento ABIERTA (idempotente)
    # ================================================================
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_agregar_todo_seguimiento (
    p_seguimiento_id INT,
    p_equipo_id INT,
    p_usuario TEXT,
    p_clave_idempotencia TEXT DEFAULT NULL
)
RETURNS INT AS $$
DECLARE
    v_actor TEXT;
    v_guard TEXT;
    v_seguimiento RECORD;
    v_inv RECORD;
    v_agregadas INT := 0;
    v_unidades INT := 0;
BEGIN
    v_actor := COALESCE(NULLIF(p_usuario, ''),
                        NULLIF(current_setting('app.actor', true), ''),
                        CURRENT_USER);

    -- 0. Guarda de idempotencia (REQ-P2-INV-007), misma transacción.
    IF p_clave_idempotencia IS NOT NULL THEN
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave)
        VALUES ('AGREGAR_TODO', p_clave_idempotencia)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            RAISE EXCEPTION 'La operación AGREGAR_TODO con clave % ya fue ejecutada; no se aplicaron cambios (idempotencia).',
                p_clave_idempotencia;
        END IF;
    END IF;

    -- 1. Cabecera: existencia, pertenencia al equipo y estado ABIERTA.
    --    FOR UPDATE serializa con fn_cerrar_seguimiento y con dobles
    --    invocaciones concurrentes (REQ-P2-CON-004).
    SELECT * INTO v_seguimiento
    FROM seguimientos
    WHERE id = p_seguimiento_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Seguimiento ID % no encontrado.', p_seguimiento_id;
    END IF;

    IF v_seguimiento.equipo_id <> p_equipo_id THEN
        RAISE EXCEPTION 'El seguimiento ID % no pertenece al equipo ID %.',
            p_seguimiento_id, p_equipo_id;
    END IF;

    IF v_seguimiento.estado <> 'ABIERTA' THEN
        RAISE EXCEPTION 'El seguimiento ID % no se encuentra en estado ABIERTA.',
            p_seguimiento_id;
    END IF;

    -- 2. Líneas del inventario del equipo con existencias reales, leídas
    --    BAJO bloqueo FOR UPDATE en orden determinista por material_id
    --    (cero condiciones de carrera con fn_cerrar_seguimiento y
    --    fn_procesar_movimiento, que bloquean en el mismo orden).
    FOR v_inv IN
        SELECT material_id, stock_actual
        FROM inventario_equipos
        WHERE equipo_id = p_equipo_id AND stock_actual > 0
        ORDER BY material_id
        FOR UPDATE
    LOOP
        -- 3. Inserción idempotente: ON CONFLICT DO NOTHING — una doble
        --    invocación no duplica líneas ni altera las ya presentes.
        INSERT INTO seguimiento_items (seguimiento_id, material_id, cantidad_tomada)
        VALUES (p_seguimiento_id, v_inv.material_id, v_inv.stock_actual)
        ON CONFLICT (seguimiento_id, material_id) DO NOTHING;

        IF FOUND THEN
            v_agregadas := v_agregadas + 1;
            v_unidades := v_unidades + v_inv.stock_actual;
        END IF;
    END LOOP;

    -- 4. Evento de auditoría SOLO si hubo líneas nuevas: el ledger no
    --    duplica eventos en una segunda invocación (REQ-P2-CON-004).
    IF v_agregadas > 0 THEN
        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, equipo_destino_id, resultado, detalles
        ) VALUES (
            v_actor,
            'AGREGAR_TODO',
            p_equipo_id,
            'EXITO',
            jsonb_build_object(
                'seguimiento_id', p_seguimiento_id,
                'equipo_id', p_equipo_id,
                'lineas_agregadas', v_agregadas,
                'unidades_agregadas', v_unidades,
                'usuario', v_actor,
                'clave_idempotencia', p_clave_idempotencia,
                'fecha', CURRENT_TIMESTAMP
            )
        );
    END IF;

    -- 5. Persistir el resultado para retornos de reenvío (REQ-P2-INV-007).
    IF p_clave_idempotencia IS NOT NULL THEN
        UPDATE operaciones_idempotencia
        SET resultado = jsonb_build_object(
            'lineas_agregadas', v_agregadas,
            'seguimiento_id', p_seguimiento_id
        )
        WHERE tipo_operacion = 'AGREGAR_TODO' AND clave = p_clave_idempotencia;
    END IF;

    RETURN v_agregadas;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )


def downgrade() -> None:
    # Reverso exacto 0019 -> 0018 (ver docstring del módulo).
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS fn_agregar_todo_seguimiento(INT, INT, TEXT, TEXT)"
        )
    )
