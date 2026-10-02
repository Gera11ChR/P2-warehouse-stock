"""Reportes oficiales de Entrega y Consumo (actas) — SOLO LECTURA.

Reemplaza al reporte legacy de despliegues/CSV (descartado). Fuente única:
la tabla append-only `actas_reportes`, cuyo SNAPSHOT jsonb escribe
PostgreSQL EN LA MISMA TRANSACCIÓN del evento (REQ-P2-REP-003/004):
  * 'ENTREGA' -> trigger `tg_acta_entrega` al confirmar TEAMS (CONFIRMADO).
  * 'CONSUMO' -> `fn_cerrar_seguimiento` al cerrar el seguimiento.
El payload JSON y el XLSX se derivan SIEMPRE de ese snapshot y nunca del
stock mutable actual. Las cantidades (incl. `cantidad_consumida`) ya vienen
calculadas por SQL: aquí solo se transportan (cero aritmética de stock).
"""

from datetime import date, datetime

from sqlalchemy import Date, Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ActaReporte
from app.schemas.reporte import ActaItemOut, ActaOut
from app.services.plantilla_reporte import LineaActa

# Límite defensivo de líneas por documento XLSX (B-1, dictamen sec-ops):
# evita workbooks gigantes y el coste O(n) de la inserción de filas.
MAX_LINEAS_XLSX = 1000

# Equipo de un acta: ENTREGA -> snapshot.destino_equipo.equipo_id;
# CONSUMO -> snapshot.equipo_id (los tipos se filtran antes de consultar).
_EQUIPO_ID = cast(
    func.coalesce(
        ActaReporte.snapshot["destino_equipo"]["equipo_id"].astext,
        ActaReporte.snapshot["equipo_id"].astext,
    ),
    Integer,
)


def _a_acta_out(acta: ActaReporte) -> ActaOut:
    """Convierte la fila persistida (snapshot jsonb) en el DTO de lectura."""
    snap = acta.snapshot or {}
    equipo = snap.get("destino_equipo") or {}
    es_entrega = acta.tipo == "ENTREGA"
    items = []
    for it in snap.get("items", []):
        items.append(
            ActaItemOut(
                material_id=it["material_id"],
                codigo=it.get("codigo"),
                descripcion=it.get("descripcion") or "",
                categoria=it.get("categoria"),
                u_m=it.get("u_m"),
                cantidad=it.get("cantidad") if es_entrega else None,
                cantidad_tomada=None if es_entrega else it.get("cantidad_tomada"),
                cantidad_sobrante=None if es_entrega else it.get("cantidad_sobrante"),
                cantidad_consumida=(
                    None if es_entrega else it.get("cantidad_consumida")
                ),
            )
        )
    return ActaOut(
        acta_id=acta.id,
        tipo=acta.tipo,
        movimiento_id=acta.movimiento_id,
        seguimiento_id=acta.seguimiento_id,
        equipo_id=equipo.get("equipo_id") if es_entrega else snap.get("equipo_id"),
        equipo_nombre=equipo.get("nombre") if es_entrega else snap.get("equipo_nombre"),
        usuario=snap.get("usuario"),
        observaciones=snap.get("observaciones"),
        fecha=acta.created_at,
        items=items,
    )


async def consultar_actas(
    session: AsyncSession,
    *,
    tipo: str,
    acta_id: int | None = None,
    equipo_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    solo_equipos: set[int] | None = None,
) -> list[ActaOut]:
    """Actas del `tipo` indicado, más reciente primero. `solo_equipos`
    restringe la lectura a los equipos visibles del actor (aislamiento por
    integrante); None = todos (administrador). Las actas sin equipo
    asociado (p. ej. TEAMS hacia un módulo FO) solo las ve el
    administrador. `desde`/`hasta` filtran sobre la fecha del evento
    (`actas_reportes.created_at`)."""
    stmt = select(ActaReporte).where(ActaReporte.tipo == tipo)
    if acta_id is not None:
        stmt = stmt.where(ActaReporte.id == acta_id)
    if equipo_id is not None:
        stmt = stmt.where(_EQUIPO_ID == equipo_id)
    if solo_equipos is not None:
        stmt = stmt.where(_EQUIPO_ID.in_(solo_equipos))
    if desde is not None:
        stmt = stmt.where(cast(ActaReporte.created_at, Date) >= desde)
    if hasta is not None:
        stmt = stmt.where(cast(ActaReporte.created_at, Date) <= hasta)
    stmt = stmt.order_by(ActaReporte.created_at.desc(), ActaReporte.id.desc())
    filas = (await session.execute(stmt)).scalars().all()
    return [_a_acta_out(a) for a in filas]


def fecha_documento(actas: list[ActaOut]) -> date:
    """Fecha del documento XLSX: la del evento más reciente del conjunto
    (para un acta individual, la fecha de su evento)."""
    reciente: datetime = max(a.fecha for a in actas)
    return reciente.date()


def lineas_para_xlsx(tipo: str, actas: list[ActaOut]) -> list[LineaActa]:
    """Líneas (CANT., DESCRIPCIÓN, U.M.) del documento, concatenando las
    actas en el orden recibido, SIN agregar ni recalcular cantidades.

    * ENTREGA: CANT. = cantidad entregada.
    * CONSUMO: CANT. = cantidad consumida (calculada en SQL, columna
      GENERATED); las líneas sin consumo (consumida = 0) se omiten porque
      no certifican ningún consumo."""
    lineas: list[LineaActa] = []
    for acta in actas:
        for it in acta.items:
            cantidad = it.cantidad if tipo == "ENTREGA" else it.cantidad_consumida
            if not cantidad:
                continue
            lineas.append(
                LineaActa(cantidad=cantidad, descripcion=it.descripcion, u_m=it.u_m)
            )
    return lineas
