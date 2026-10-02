"""fn_sumar_cantidad (+Cantidad) y tabla de idempotencia (T1.3)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-02

Fase 1 (Base de Datos) del cambio 2026-10-01-reportes-consumo-management
(REQ-P2-INV-001/002/006/007). Operador rápido `+Cantidad`: adición
aritmética directa al stock actual de un material del Inventario General o
de los módulos FO (PAQUETE/EN_USO), SIN pasar por el flujo TEAMS/DEVOL.

1) `operaciones_idempotencia` — registro de claves de idempotencia
   (REQ-P2-INV-007): PK (tipo_operacion, clave). La guarda vive DENTRO de
   cada SP, en la MISMA transacción: si la transacción falla, la fila
   guarda desaparece con el rollback (el reintento es válido); si la
   transacción confirma, cualquier reenvío con la misma clave recibe
   RAISE EXCEPTION sin duplicar efectos sobre stock ni auditoría. El
   endpoint (Fase 2) puede devolver el resultado original leyendo la
   columna `resultado` (jsonb).

2) `fn_sumar_cantidad(p_destino, p_modulo, p_material_id, p_cantidad,
   p_usuario, p_clave_idempotencia)` RETURNS INT (nuevo stock):
   * p_destino = 'GENERAL' resuelve en PostgreSQL la fila del material en
     la sección GENERAL activa (espejo de fn_ajustar_stock_general:
     0 filas -> RAISE 404 vía "No se encuentra registro de inventario";
     >1 filas -> RAISE conflicto "no es posible determinar un destino
     único").
   * p_destino = 'FO' con p_modulo IN ('PAQUETE','EN_USO') opera sobre
     inventario_fibra.
   * Validaciones: cantidad > 0 (cero y negativos rechazados), material
     activo en catalogo_materiales, registro de inventario existente.
   * Mutación 100 % PostgreSQL: SELECT ... FOR UPDATE (cero condiciones
     de carrera), UPDATE stock_actual = stock_actual + p_cantidad e
     INSERT inmutable en auditoria_eventos con evento `SUMA_CANTIDAD`
     (diferenciado semánticamente de AJUSTE_INVENTARIO /
     AJUSTE_INVENTARIO_FO, taxonomía verificada en T1.1: sin colisiones),
     todo en una única transacción atómica.
   * REGLA CONSTITUCIONAL: cero aritmética de stock en Python; el backend
     (Fase 2) solo delega.

downgrade() — reverso exacto 0017 -> 0016: DROP de la función y de la
tabla de idempotencia (la tabla la crea esta migración y la comparten
0018/0019; el downgrade corre en orden inverso, de modo que al ejecutarse
este DROP las funciones 0018/0019 ya no existen). Cero pérdida de datos
de negocio: la tabla solo contiene claves operativas efímeras.
"""

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ================================================================
    # A) REGISTRO DE CLAVES DE IDEMPOTENCIA (REQ-P2-INV-007)
    # ================================================================
    op.execute(
        sa.text(
            """
CREATE TABLE IF NOT EXISTS operaciones_idempotencia (
    tipo_operacion VARCHAR(50) NOT NULL,
    clave TEXT NOT NULL,
    resultado JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT operaciones_idempotencia_pkey PRIMARY KEY (tipo_operacion, clave)
)
"""
        )
    )

    # ================================================================
    # B) FN_SUMAR_CANTIDAD — operador +Cantidad (General y FO)
    # ================================================================
    op.execute(
        sa.text(
            """
CREATE OR REPLACE FUNCTION fn_sumar_cantidad (
    p_destino TEXT,
    p_modulo TEXT,
    p_material_id INT,
    p_cantidad INT,
    p_usuario TEXT,
    p_clave_idempotencia TEXT DEFAULT NULL
)
RETURNS INT AS $$
DECLARE
    v_actor TEXT;
    v_guard TEXT;
    v_almacen_id INT;
    v_conteo INT;
    v_stock_anterior INT;
    v_nuevo_stock INT;
BEGIN
    v_actor := COALESCE(NULLIF(p_usuario, ''),
                        NULLIF(current_setting('app.actor', true), ''),
                        CURRENT_USER);

    -- 0. Guarda de idempotencia (REQ-P2-INV-007): la fila vive en la MISMA
    --    transacción; un fallo posterior la elimina con el rollback.
    IF p_clave_idempotencia IS NOT NULL THEN
        INSERT INTO operaciones_idempotencia (tipo_operacion, clave)
        VALUES ('SUMA_CANTIDAD', p_clave_idempotencia)
        ON CONFLICT (tipo_operacion, clave) DO NOTHING
        RETURNING clave INTO v_guard;

        IF v_guard IS NULL THEN
            RAISE EXCEPTION 'La operación SUMA_CANTIDAD con clave % ya fue ejecutada; no se aplicaron cambios (idempotencia).',
                p_clave_idempotencia;
        END IF;
    END IF;

    -- 1. Validaciones de dominio (REQ-P2-INV-001).
    IF p_destino IS NULL OR p_destino NOT IN ('GENERAL','FO') THEN
        RAISE EXCEPTION 'El destino de +Cantidad debe ser GENERAL o FO (recibido: %).', p_destino;
    END IF;

    IF p_cantidad IS NULL OR p_cantidad <= 0 THEN
        RAISE EXCEPTION 'La cantidad a sumar debe ser mayor que cero (recibida: %).', p_cantidad;
    END IF;

    IF p_destino = 'FO' AND (p_modulo IS NULL OR p_modulo NOT IN ('PAQUETE','EN_USO')) THEN
        RAISE EXCEPTION 'El módulo de Fibra Óptica debe ser PAQUETE o EN_USO (recibido: %).', p_modulo;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM catalogo_materiales
        WHERE id_lista = p_material_id AND is_active = TRUE
    ) THEN
        RAISE EXCEPTION 'Material ID LISTA % no existe o está inactivo.', p_material_id;
    END IF;

    -- 2. Mutación atómica con bloqueo FOR UPDATE + auditoría inmutable.
    IF p_destino = 'GENERAL' THEN
        -- Resolución de la sección GENERAL activa (espejo de
        -- fn_ajustar_stock_general): 0 filas -> 404; >1 -> conflicto.
        SELECT COUNT(*) INTO v_conteo
        FROM inventario_almacen ia
        JOIN secciones s ON s.almacen_id = ia.almacen_id
        WHERE ia.material_id = p_material_id
          AND s.tipo = 'GENERAL' AND s.is_active = TRUE;

        IF v_conteo = 0 THEN
            RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en la sección GENERAL activa. Realice primero la carga inicial.',
                p_material_id;
        END IF;

        IF v_conteo > 1 THEN
            RAISE EXCEPTION 'Existen % filas de inventario del material ID % en secciones GENERAL activas; no es posible determinar un destino único.',
                v_conteo, p_material_id;
        END IF;

        SELECT ia.almacen_id, ia.stock_actual INTO v_almacen_id, v_stock_anterior
        FROM inventario_almacen ia
        JOIN secciones s ON s.almacen_id = ia.almacen_id
        WHERE ia.material_id = p_material_id
          AND s.tipo = 'GENERAL' AND s.is_active = TRUE
        LIMIT 1
        FOR UPDATE OF ia;

        v_nuevo_stock := v_stock_anterior + p_cantidad;

        UPDATE inventario_almacen
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE almacen_id = v_almacen_id AND material_id = p_material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, almacen_destino_id, cantidad, resultado, detalles
        ) VALUES (
            v_actor,
            'SUMA_CANTIDAD',
            p_material_id,
            v_almacen_id,
            p_cantidad,
            'EXITO',
            jsonb_build_object(
                'destino', 'GENERAL',
                'almacen_id', v_almacen_id,
                'stock_anterior', v_stock_anterior,
                'stock_nuevo', v_nuevo_stock,
                'diferencial', p_cantidad,
                'usuario', v_actor,
                'clave_idempotencia', p_clave_idempotencia,
                'fecha', CURRENT_TIMESTAMP
            )
        );

    ELSE -- p_destino = 'FO'
        SELECT stock_actual INTO v_stock_anterior
        FROM inventario_fibra
        WHERE modulo = p_modulo AND material_id = p_material_id
        FOR UPDATE;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'No se encuentra registro de inventario para el material ID % en el módulo FO %. Realice primero la carga inicial con fn_cargar_stock_inicial_fibra.',
                p_material_id, p_modulo;
        END IF;

        v_nuevo_stock := v_stock_anterior + p_cantidad;

        UPDATE inventario_fibra
        SET stock_actual = v_nuevo_stock, updated_at = CURRENT_TIMESTAMP
        WHERE modulo = p_modulo AND material_id = p_material_id;

        INSERT INTO auditoria_eventos (
            usuario, tipo_accion, material_id, cantidad, resultado, detalles
        ) VALUES (
            v_actor,
            'SUMA_CANTIDAD',
            p_material_id,
            p_cantidad,
            'EXITO',
            jsonb_build_object(
                'destino', 'FO',
                'modulo', p_modulo,
                'stock_anterior', v_stock_anterior,
                'stock_nuevo', v_nuevo_stock,
                'diferencial', p_cantidad,
                'usuario', v_actor,
                'clave_idempotencia', p_clave_idempotencia,
                'fecha', CURRENT_TIMESTAMP
            )
        );
    END IF;

    -- 3. Persistir el resultado para retornos de reenvío (REQ-P2-INV-007).
    IF p_clave_idempotencia IS NOT NULL THEN
        UPDATE operaciones_idempotencia
        SET resultado = jsonb_build_object(
            'stock_nuevo', v_nuevo_stock,
            'destino', p_destino,
            'modulo', p_modulo
        )
        WHERE tipo_operacion = 'SUMA_CANTIDAD' AND clave = p_clave_idempotencia;
    END IF;

    RETURN v_nuevo_stock;
END;
$$ LANGUAGE plpgsql;
"""
        )
    )


def downgrade() -> None:
    # Reverso exacto 0017 -> 0016 (ver docstring del módulo).
    op.execute(
        sa.text(
            "DROP FUNCTION IF EXISTS fn_sumar_cantidad(TEXT, TEXT, INT, INT, TEXT, TEXT)"
        )
    )
    op.execute(sa.text("DROP TABLE IF EXISTS operaciones_idempotencia"))
