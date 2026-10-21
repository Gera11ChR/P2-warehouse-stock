"""Servicio de la Referencia de materiales por Unidad (T4, paquete
2026-10-referencia-materiales-unidades; plan §4, P-2/P-3/P-6/P-9).

REGLAS:
  * REQ-REF-005 (C-1/Q2/P-9, C-5): el listado lee `codigo`/`descripcion`
    del catálogo EN VIVO y la U.M. EFECTIVA de la Unidad por
    `COALESCE(ums.nombre, catalogo_materiales.u_m)` (mismo cálculo que
    `um_efectivo` del inventario de la Unidad), ordenado por `descripcion`
    (collation de la BD) y `material_id`; los materiales inactivos se
    conservan pero no se listan (C-4).
  * REQ-REF-006/007 (C-8/P-3): alta masiva todo-o-nada con precedencia de
    errores 422 → 404 → 409, `coordinates` por línea e inserción en orden
    ascendente de `material_id` (evita interbloqueos entre altas
    cruzadas); la carrera de la PK compuesta y un `40P01` residual
    responden 409 `REFERENCIA_DUPLICADA` controlado — jamás 500 ni SQL
    expuesto (H-03).
  * REQ-REF-008 (C-4/C-11, H-04/H-08): PATCH con `SELECT … FOR UPDATE`;
    línea inexistente o con material inactivo → 404
    `REFERENCIA_NO_ENCONTRADA`; la misma cantidad es un no-op sin
    escritura (no toca `updated_at`, no audita).
  * REQ-REF-009 (C-3): DELETE físico; el trigger conserva los valores
    previos en el ledger de auditoría.
  * REQ-REF-011/012: SOLO se escribe `referencia_materiales` (catálogo,
    `equipo_material_config` y `ums` se leen sin escribir); sin Stored
    Functions de stock y sin eventos de auditoría manuales: los emite el
    trigger `tg_auditar_referencia_materiales` en la misma transacción.
  * La transacción la gobierna el router (T5): aquí solo `flush()`, sin
    `commit()`.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, and_, func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BusinessRuleError
from app.models import (
    CatalogoMaterial,
    EquipoMaterialConfig,
    ReferenciaMaterial,
    Ums,
)
from app.schemas.referencia import (
    ReferenciaCreate,
    ReferenciaLineaOut,
    ReferenciaListOut,
    ReferenciaUpdate,
)


def _stmt_lineas(
    equipo_id: int, material_id: int | None = None
) -> Select[int, str | None, str, str, Decimal]:
    """SELECT de líneas de la Referencia con JOIN al catálogo activo y
    LEFT JOIN a `equipo_material_config`/`ums` para la U.M. efectiva
    (P-9/C-1), sin bloqueo — solo lectura (REQ-REF-011)."""
    u_m = func.coalesce(Ums.nombre, CatalogoMaterial.u_m).label("u_m")
    stmt = (
        select(
            ReferenciaMaterial.material_id,
            CatalogoMaterial.codigo,
            CatalogoMaterial.descripcion,
            u_m,
            ReferenciaMaterial.cantidad_semanal,
        )
        .join(
            CatalogoMaterial,
            CatalogoMaterial.id_lista == ReferenciaMaterial.material_id,
        )
        .outerjoin(
            EquipoMaterialConfig,
            and_(
                EquipoMaterialConfig.equipo_id == ReferenciaMaterial.equipo_id,
                EquipoMaterialConfig.material_id
                == ReferenciaMaterial.material_id,
            ),
        )
        .outerjoin(Ums, Ums.id == EquipoMaterialConfig.um_local_id)
        .where(
            ReferenciaMaterial.equipo_id == equipo_id,
            CatalogoMaterial.is_active == True,  # noqa: E712
        )
        .order_by(
            CatalogoMaterial.descripcion.asc(),
            ReferenciaMaterial.material_id.asc(),
        )
    )
    if material_id is not None:
        stmt = stmt.where(ReferenciaMaterial.material_id == material_id)
    return stmt


def _a_linea(fila: Any) -> ReferenciaLineaOut:
    """Mapea una fila del SELECT de líneas al DTO de salida."""
    return ReferenciaLineaOut(
        material_id=fila.material_id,
        codigo=fila.codigo,
        descripcion=fila.descripcion,
        u_m=fila.u_m,
        cantidad_semanal=fila.cantidad_semanal,
    )


def _no_encontrada(equipo_id: int, material_id: int) -> BusinessRuleError:
    """404 canónico de línea inexistente u oculta por material inactivo
    (REQ-REF-008/009, C-4)."""
    return BusinessRuleError(
        "La línea no existe en la Referencia de la Unidad",
        code="REFERENCIA_NO_ENCONTRADA",
        status_code=404,
        coordinates=[{"equipo_id": equipo_id, "material_id": material_id}],
    )


async def listar_referencia(
    session: AsyncSession, equipo_id: int
) -> ReferenciaListOut:
    """Lectura de la Referencia (REQ-REF-005): ítems con datos del catálogo
    en vivo y U.M. efectiva de la Unidad, ordenados por `descripcion`
    ascendente y luego `material_id` ascendente; `total` cuenta solo los
    ítems listados. Solo lectura: cero escrituras y cero eventos de
    auditoría (REQ-REF-011/012)."""
    filas = (await session.execute(_stmt_lineas(equipo_id))).all()
    items = [_a_linea(f) for f in filas]
    return ReferenciaListOut(items=items, total=len(items))


async def crear_referencia(
    session: AsyncSession, equipo_id: int, payload: ReferenciaCreate
) -> ReferenciaListOut:
    """Alta masiva todo-o-nada (REQ-REF-006/007, C-8/P-3) dentro de la
    transacción del router:

    1. Duplicados del payload → 422 `REFERENCIA_LINEA_DUPLICADA` con la
       `coordinates` de la 2.ª aparición (índice cero-basado), SIN tocar la
       BD (P-6).
    2. Materiales inexistentes o inactivos → 404 `MATERIAL_NO_ENCONTRADO`
       (primera línea por índice).
    3. Materiales ya en la Referencia → 409 `REFERENCIA_DUPLICADA`
       (primera línea por índice).
    4. Inserción en orden ascendente de `material_id` (P-3); un
       `IntegrityError` de carrera por la PK compuesta o un interbloqueo
       residual `40P01` responden 409 `REFERENCIA_DUPLICADA` controlado con
       mensaje de reintento — jamás 500 ni SQL expuesto (C-8/H-03).

    Devuelve las líneas creadas re-consultadas con el orden del GET y
    `total` = creadas. Sin `commit()`: la transacción la gobierna T5."""
    lineas = payload.lineas
    vistos: dict[int, int] = {}
    for i, linea in enumerate(lineas):
        if linea.material_id in vistos:
            raise BusinessRuleError(
                "El material se repite dentro de la petición de Referencia",
                code="REFERENCIA_LINEA_DUPLICADA",
                status_code=422,
                coordinates=[{"linea": i, "material_id": linea.material_id}],
            )
        vistos[linea.material_id] = i
    ids = list(vistos)
    activos = set(
        (
            await session.execute(
                select(CatalogoMaterial.id_lista).where(
                    CatalogoMaterial.id_lista.in_(ids),
                    CatalogoMaterial.is_active == True,  # noqa: E712
                )
            )
        ).scalars()
    )
    for i, linea in enumerate(lineas):
        if linea.material_id not in activos:
            raise BusinessRuleError(
                "Material no encontrado",
                code="MATERIAL_NO_ENCONTRADO",
                status_code=404,
                coordinates=[{"linea": i, "material_id": linea.material_id}],
            )
    presentes = set(
        (
            await session.execute(
                select(ReferenciaMaterial.material_id).where(
                    ReferenciaMaterial.equipo_id == equipo_id,
                    ReferenciaMaterial.material_id.in_(ids),
                )
            )
        ).scalars()
    )
    for i, linea in enumerate(lineas):
        if linea.material_id in presentes:
            raise BusinessRuleError(
                "El material ya está en la Referencia de la Unidad",
                code="REFERENCIA_DUPLICADA",
                status_code=409,
                coordinates=[{"linea": i, "material_id": linea.material_id}],
            )
    ordenadas = sorted(lineas, key=lambda l: l.material_id)
    session.add_all(
        ReferenciaMaterial(
            equipo_id=equipo_id,
            material_id=linea.material_id,
            cantidad_semanal=linea.cantidad_semanal,
        )
        for linea in ordenadas
    )
    try:
        await session.flush()
    except IntegrityError:
        # Carrera concurrente: la PK compuesta garantiza una sola línea
        # (REQ-REF-007, §6); el router revierte la transacción.
        raise BusinessRuleError(
            "El material ya está en la Referencia de la Unidad; "
            "reintente la operación",
            code="REFERENCIA_DUPLICADA",
            status_code=409,
            coordinates=[],
        ) from None
    except DBAPIError as exc:
        if getattr(getattr(exc, "orig", None), "sqlstate", None) != "40P01":
            raise
        # Interbloqueo residual entre altas cruzadas en distinto orden
        # (P-3): respuesta controlada de reintento, nunca 500.
        raise BusinessRuleError(
            "Conflicto de concurrencia al crear la Referencia; "
            "reintente la operación",
            code="REFERENCIA_DUPLICADA",
            status_code=409,
            coordinates=[],
        ) from None
    creados = {linea.material_id for linea in ordenadas}
    listado = await listar_referencia(session, equipo_id)
    items = [item for item in listado.items if item.material_id in creados]
    return ReferenciaListOut(items=items, total=len(items))


async def modificar_referencia(
    session: AsyncSession,
    equipo_id: int,
    material_id: int,
    payload: ReferenciaUpdate,
) -> ReferenciaLineaOut:
    """Modifica SOLO la Cantidad Semanal de la línea (REQ-REF-008, C-11/Q4).

    * `SELECT … FOR UPDATE` de la línea con JOIN al catálogo activo: una
      línea con material inactivo se trata como inexistente y se conserva
      (C-4/H-04) → 404 `REFERENCIA_NO_ENCONTRADA`.
    * Misma cantidad → devuelve la línea SIN `UPDATE` (no toca
      `updated_at`, no audita — no-op idempotente, C-11/H-08).
    * Cantidad distinta → actualiza `cantidad_semanal` y
      `updated_at = CURRENT_TIMESTAMP`; el trigger audita
      `REFERENCIA_LINEA_MODIFICADA` con los valores previos y nuevos.

    El `FOR UPDATE` usa JOIN interno porque PostgreSQL prohíbe bloquear el
    lado nullable de un `LEFT JOIN` (verificado en T4); la U.M. efectiva
    se lee con el SELECT de listado (solo lectura) dentro de la misma
    transacción."""
    linea = (
        await session.execute(
            select(ReferenciaMaterial)
            .join(
                CatalogoMaterial,
                CatalogoMaterial.id_lista == ReferenciaMaterial.material_id,
            )
            .where(
                ReferenciaMaterial.equipo_id == equipo_id,
                ReferenciaMaterial.material_id == material_id,
                CatalogoMaterial.is_active == True,  # noqa: E712
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if linea is None:
        raise _no_encontrada(equipo_id, material_id)
    if linea.cantidad_semanal == payload.cantidad_semanal:
        fila = (
            await session.execute(_stmt_lineas(equipo_id, material_id))
        ).one()
        return _a_linea(fila)
    linea.cantidad_semanal = payload.cantidad_semanal
    linea.updated_at = datetime.now(timezone.utc)
    await session.flush()
    fila = (await session.execute(_stmt_lineas(equipo_id, material_id))).one()
    return _a_linea(fila)


async def eliminar_referencia(
    session: AsyncSession, equipo_id: int, material_id: int
) -> None:
    """Eliminación FÍSICA de la línea (REQ-REF-009, C-3/D-9): `SELECT …
    FOR UPDATE` con JOIN al catálogo activo; línea inexistente o con
    material inactivo → 404 `REFERENCIA_NO_ENCONTRADA` (la línea se
    conserva, C-4). El trigger conserva los valores previos en el ledger
    de auditoría; el material y todos los inventarios quedan intactos
    (REQ-REF-011)."""
    linea = (
        await session.execute(
            select(ReferenciaMaterial)
            .join(
                CatalogoMaterial,
                CatalogoMaterial.id_lista == ReferenciaMaterial.material_id,
            )
            .where(
                ReferenciaMaterial.equipo_id == equipo_id,
                ReferenciaMaterial.material_id == material_id,
                CatalogoMaterial.is_active == True,  # noqa: E712
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if linea is None:
        raise _no_encontrada(equipo_id, material_id)
    await session.delete(linea)
