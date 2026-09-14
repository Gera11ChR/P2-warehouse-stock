"""Gestión de BORRADORES de movimientos (TEAMS/DEVOL).

Este servicio crea/edita/elimina cabeceras en estado BORRADOR y sus detalles.
La validación de stock disponible, el descuento/incremento de inventario y la
auditoría crítica se ejecutan EXCLUSIVAMENTE en PostgreSQL vía
fn_procesar_movimiento / fn_cancelar_movimiento (ver services.transaccional).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import BusinessRuleError, MovimientoNotFoundError, MovimientoStateError
from app.models import (
    CatalogoMaterial,
    Equipo,
    MovimientoCabecera,
    MovimientoDetalle,
    Seccion,
)
from app.schemas.movimiento import (
    MovimientoBorradorCreate,
    MovimientoBorradorUpdate,
    MovimientoOut,
)


async def _validar_referencias(
    session: AsyncSession, payload: MovimientoBorradorCreate
) -> None:
    material_ids = {line.material_id for line in payload.detalle}
    activos = set(
        (
            await session.execute(
                select(CatalogoMaterial.id_lista).where(
                    CatalogoMaterial.id_lista.in_(material_ids),
                    CatalogoMaterial.is_active == True,  # noqa: E712
                )
            )
        ).scalars()
    )
    inexistentes = material_ids - activos
    if inexistentes:
        raise BusinessRuleError(
            "Material no encontrado en el catálogo activo",
            coordinates=[
                {"material_id": m} for m in sorted(inexistentes)
            ],
        )

    if payload.tipo_movimiento == "TEAMS":
        seccion = await session.get(Seccion, payload.origen_almacen_id)
        if seccion is None:
            raise BusinessRuleError(
                "Sección origen inexistente",
                coordinates=[{"origen_almacen_id": payload.origen_almacen_id}],
            )
        equipo = await session.get(Equipo, payload.destino_equipo_id)
        if equipo is None:
            raise BusinessRuleError(
                "Equipo destino inexistente",
                coordinates=[{"destino_equipo_id": payload.destino_equipo_id}],
            )
    else:
        equipo = await session.get(Equipo, payload.origen_equipo_id)
        if equipo is None:
            raise BusinessRuleError(
                "Equipo origen inexistente",
                coordinates=[{"origen_equipo_id": payload.origen_equipo_id}],
            )
        seccion = await session.get(Seccion, payload.destino_almacen_id)
        if seccion is None:
            raise BusinessRuleError(
                "Sección destino inexistente",
                coordinates=[{"destino_almacen_id": payload.destino_almacen_id}],
            )


def _aplicar_campos(
    cabecera: MovimientoCabecera, payload: MovimientoBorradorCreate
) -> None:
    cabecera.tipo_movimiento = payload.tipo_movimiento
    cabecera.origen_almacen_id = payload.origen_almacen_id
    cabecera.destino_almacen_id = payload.destino_almacen_id
    cabecera.origen_equipo_id = payload.origen_equipo_id
    cabecera.destino_equipo_id = payload.destino_equipo_id
    cabecera.observaciones = payload.observaciones
    cabecera.detalle = [
        MovimientoDetalle(material_id=line.material_id, cantidad=line.cantidad)
        for line in payload.detalle
    ]


async def _to_out(
    session: AsyncSession, cabecera: MovimientoCabecera
) -> MovimientoOut:
    await session.refresh(cabecera, attribute_names=["detalle"])
    return MovimientoOut.model_validate(cabecera, from_attributes=True)


async def _obtener(
    session: AsyncSession, movimiento_id: int
) -> MovimientoCabecera:
    cabecera = (
        await session.execute(
            select(MovimientoCabecera)
            .options(selectinload(MovimientoCabecera.detalle))
            .where(MovimientoCabecera.id == movimiento_id)
        )
    ).scalar_one_or_none()
    if cabecera is None:
        raise MovimientoNotFoundError(movimiento_id)
    return cabecera


async def crear_borrador(
    session: AsyncSession, payload: MovimientoBorradorCreate, *, actor: str
) -> MovimientoOut:
    await _validar_referencias(session, payload)
    cabecera = MovimientoCabecera(usuario=actor, estado="BORRADOR")
    _aplicar_campos(cabecera, payload)
    session.add(cabecera)
    await session.flush()
    return await _to_out(session, cabecera)


async def listar(
    session: AsyncSession,
    *,
    estado: str | None = None,
    tipo_movimiento: str | None = None,
) -> list[MovimientoOut]:
    stmt = select(MovimientoCabecera).options(
        selectinload(MovimientoCabecera.detalle)
    )
    if estado:
        stmt = stmt.where(MovimientoCabecera.estado == estado)
    if tipo_movimiento:
        stmt = stmt.where(MovimientoCabecera.tipo_movimiento == tipo_movimiento)
    stmt = stmt.order_by(MovimientoCabecera.id.desc())
    cabeceras = (await session.execute(stmt)).scalars().all()
    return [await _to_out(session, c) for c in cabeceras]


async def obtener(session: AsyncSession, movimiento_id: int) -> MovimientoOut:
    return await _to_out(session, await _obtener(session, movimiento_id))


async def actualizar_borrador(
    session: AsyncSession,
    movimiento_id: int,
    payload: MovimientoBorradorUpdate,
    *,
    actor: str,
) -> MovimientoOut:
    cabecera = await _obtener(session, movimiento_id)
    if cabecera.estado != "BORRADOR":
        raise MovimientoStateError(
            movimiento_id, estado=cabecera.estado, operacion="editar"
        )
    if payload.observaciones is not None:
        cabecera.observaciones = payload.observaciones
    if payload.detalle is not None:
        material_ids = {line.material_id for line in payload.detalle}
        activos = set(
            (
                await session.execute(
                    select(CatalogoMaterial.id_lista).where(
                        CatalogoMaterial.id_lista.in_(material_ids),
                        CatalogoMaterial.is_active == True,  # noqa: E712
                    )
                )
            ).scalars()
        )
        inexistentes = material_ids - activos
        if inexistentes:
            raise BusinessRuleError(
                "Material no encontrado en el catálogo activo",
                coordinates=[
                    {"material_id": m} for m in sorted(inexistentes)
                ],
            )
        cabecera.detalle = [
            MovimientoDetalle(material_id=line.material_id, cantidad=line.cantidad)
            for line in payload.detalle
        ]
    await session.flush()
    return await _to_out(session, cabecera)


async def eliminar_borrador(
    session: AsyncSession, movimiento_id: int, *, actor: str
) -> None:
    cabecera = await _obtener(session, movimiento_id)
    if cabecera.estado != "BORRADOR":
        raise MovimientoStateError(
            movimiento_id, estado=cabecera.estado, operacion="eliminar"
        )
    await session.delete(cabecera)
    await session.flush()
