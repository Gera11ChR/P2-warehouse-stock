"""Nomenclatura Equipo -> Unidad — cambio 2026-10-12-equipo-a-unidad.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-12

Solo TEXTO (REQ-UNI-007): sustituye "equipo" por "unidad" en los literales
de RAISE EXCEPTION de las stored functions. No modifica tablas, columnas,
firmas, lógica ni aritmética de stock (Constitución 2.1/2.3/2.4/4.1).

Mecanismo: cada función se lee con `pg_get_functiondef(oid)` (la definición
VIVA, hoy repartida entre 0014/0016/0020/0021), se sustituyen únicamente los
literales listados y se re-crea con `CREATE OR REPLACE`. Si un literal
esperado no existe en la función, la migración ABORTA (jamás una migración
silenciosamente vacía).

El mapeo de errores de la API (`services/transaccional.py`) acepta ambas
variantes de texto, de modo que los códigos HTTP (404/400/409) no cambian.

downgrade() — reverso exacto 0024 -> 0023: restaura los literales previos.
"""

from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

# (función, literal anterior, literal nuevo)
SUSTITUCIONES: list[tuple[str, str, str]] = [
    (
        "fn_procesar_movimiento",
        "El equipo ID % no cuenta con stock suficiente",
        "La unidad ID % no cuenta con stock suficiente",
    ),
    (
        "fn_cancelar_movimiento",
        "Stock insuficiente en el Equipo destino (ID %)",
        "Stock insuficiente en la Unidad destino (ID %)",
    ),
    (
        "fn_crear_seguimiento",
        "El equipo ID % no existe o se encuentra inactivo.",
        "La unidad ID % no existe o se encuentra inactiva.",
    ),
    (
        "fn_crear_seguimiento",
        "El equipo ID % ya posee un seguimiento abierto.",
        "La unidad ID % ya posee un seguimiento abierto.",
    ),
    (
        "fn_cerrar_seguimiento",
        "Stock insuficiente en el Equipo ID %",
        "Stock insuficiente en la Unidad ID %",
    ),
    (
        "fn_agregar_todo_seguimiento",
        "no pertenece al equipo ID %",
        "no pertenece a la unidad ID %",
    ),
]


def _aplicar(sustituciones: list[tuple[str, str, str]]) -> None:
    """Re-crea cada función con los literales sustituidos (viejo -> nuevo)."""
    bind = op.get_bind()
    # Agrupa por función para leer/crear cada definición una sola vez.
    por_funcion: dict[str, list[tuple[str, str]]] = {}
    for funcion, viejo, nuevo in sustituciones:
        por_funcion.setdefault(funcion, []).append((viejo, nuevo))

    for funcion, pares in por_funcion.items():
        definiciones = [
            fila[0]
            for fila in bind.execute(
                sa.text(
                    "SELECT pg_get_functiondef(p.oid) FROM pg_proc p "
                    "JOIN pg_namespace n ON n.oid = p.pronamespace "
                    "WHERE n.nspname = 'public' AND p.proname = :nombre "
                    "AND p.prokind = 'f'"
                ),
                {"nombre": funcion},
            )
        ]
        if not definiciones:
            raise RuntimeError(f"Función {funcion} no encontrada en la BD.")
        for definicion in definiciones:
            nueva = definicion
            for viejo, nuevo in pares:
                if viejo not in nueva:
                    raise RuntimeError(
                        f"Literal esperado ausente en {funcion}: {viejo!r}"
                    )
                nueva = nueva.replace(viejo, nuevo)
            # exec_driver_sql: el cuerpo contiene '%' y ':' que no deben
            # interpretarse como parámetros.
            bind.exec_driver_sql(nueva.replace("%", "%%"))


def upgrade() -> None:
    _aplicar(SUSTITUCIONES)


def downgrade() -> None:
    _aplicar([(f, nuevo, viejo) for f, viejo, nuevo in SUSTITUCIONES])
