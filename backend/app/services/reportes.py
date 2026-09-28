"""Reportes de despliegues (0014) — SOLO LECTURA.

Consulta plana despliegues → despliegue_items → catalogo_materiales con los
nombres de catálogo resueltos (categoría y U.M.) y el nombre del equipo.
Incluye TODOS los estados (ABIERTA y CERRADA); el reporte se centra en el
cierre pero el historial abierto queda visible para operaciones.

La exportación CSV aplica sanitización anti-inyección de fórmulas (OWASP):
toda celda cuyo texto inicia con `=`, `+`, `-` o `@` se prefija con una
comilla simple.
"""

import csv
import io
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CatalogoMaterial,
    Categoria,
    Despliegue,
    DespliegueItem,
    Equipo,
    Ums,
)
from app.schemas.reporte import (
    ReporteDespliegueItemOut,
    ReporteDespliegueOut,
)


async def consultar_reportes_despliegues(
    session: AsyncSession,
    *,
    equipo_id: int | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    solo_equipos: set[int] | None = None,
) -> list[ReporteDespliegueOut]:
    """Reporte plano de despliegues con filtros de equipo y rango de fechas
    (sobre despliegues.fecha). `solo_equipos` restringe la lectura a los
    equipos visibles del actor (aislamiento por integrante); None = todos
    (administrador)."""
    stmt = (
        select(
            Despliegue.id,
            Despliegue.equipo_id,
            Despliegue.fecha,
            Despliegue.estado,
            Despliegue.usuario,
            Despliegue.observaciones,
            Despliegue.created_at,
            Despliegue.closed_at,
            Equipo.nombre.label("equipo_nombre"),
            DespliegueItem.material_id,
            CatalogoMaterial.codigo,
            CatalogoMaterial.descripcion,
            Categoria.nombre.label("categoria_nombre"),
            Ums.nombre.label("um_nombre"),
            DespliegueItem.cantidad_tomada,
            DespliegueItem.cantidad_sobrante,
            DespliegueItem.cantidad_consumida,
        )
        .join(Equipo, Equipo.equipo_id == Despliegue.equipo_id)
        .join(DespliegueItem, DespliegueItem.despliegue_id == Despliegue.id)
        .join(
            CatalogoMaterial,
            CatalogoMaterial.id_lista == DespliegueItem.material_id,
        )
        .outerjoin(Categoria, Categoria.id == CatalogoMaterial.categoria_id)
        .outerjoin(Ums, Ums.nombre == CatalogoMaterial.u_m)
    )
    if equipo_id is not None:
        stmt = stmt.where(Despliegue.equipo_id == equipo_id)
    if solo_equipos is not None:
        stmt = stmt.where(Despliegue.equipo_id.in_(solo_equipos))
    if desde is not None:
        stmt = stmt.where(Despliegue.fecha >= desde)
    if hasta is not None:
        stmt = stmt.where(Despliegue.fecha <= hasta)
    stmt = stmt.order_by(
        Despliegue.fecha.desc(),
        Despliegue.id.desc(),
        DespliegueItem.material_id.asc(),
    )
    filas = (await session.execute(stmt)).all()

    reportes: dict[int, ReporteDespliegueOut] = {}
    for fila in filas:
        reporte = reportes.get(fila.id)
        if reporte is None:
            reporte = ReporteDespliegueOut(
                despliegue_id=fila.id,
                equipo_id=fila.equipo_id,
                equipo_nombre=fila.equipo_nombre,
                fecha=fila.fecha,
                estado=fila.estado,
                usuario=fila.usuario,
                observaciones=fila.observaciones,
                created_at=fila.created_at,
                closed_at=fila.closed_at,
                items=[],
            )
            reportes[fila.id] = reporte
        reporte.items.append(
            ReporteDespliegueItemOut(
                material_id=fila.material_id,
                codigo=fila.codigo,
                descripcion=fila.descripcion,
                categoria=fila.categoria_nombre,
                um=fila.um_nombre,
                cantidad_tomada=fila.cantidad_tomada,
                cantidad_sobrante=fila.cantidad_sobrante,
                cantidad_consumida=fila.cantidad_consumida,
            )
        )
    return list(reportes.values())


def _sanitizar_celda(valor) -> str:
    """OWASP CSV Injection: neutraliza celdas que inician con =, +, -, @.

    V5 (sec-ops): el chequeo se aplica sobre el texto SIN espacios líderes —
    `"  =CMD()"` también queda neutralizado."""
    texto = "" if valor is None else str(valor)
    if texto.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + texto
    return texto


def generar_csv(rows: list[ReporteDespliegueOut]) -> str:
    """Serializa el reporte a CSV (UTF-8, QUOTE_MINIMAL) con todas las
    celdas sanitizadas contra inyección de fórmulas."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(
        [
            "despliegue_id",
            "equipo_id",
            "equipo_nombre",
            "fecha",
            "estado",
            "usuario",
            "observaciones",
            "material_id",
            "codigo",
            "descripcion",
            "categoria",
            "um",
            "cantidad_tomada",
            "cantidad_sobrante",
            "cantidad_consumida",
            "created_at",
            "closed_at",
        ]
    )
    for reporte in rows:
        for item in reporte.items:
            writer.writerow(
                [
                    _sanitizar_celda(reporte.despliegue_id),
                    _sanitizar_celda(reporte.equipo_id),
                    _sanitizar_celda(reporte.equipo_nombre),
                    _sanitizar_celda(reporte.fecha),
                    _sanitizar_celda(reporte.estado),
                    _sanitizar_celda(reporte.usuario),
                    _sanitizar_celda(reporte.observaciones),
                    _sanitizar_celda(item.material_id),
                    _sanitizar_celda(item.codigo),
                    _sanitizar_celda(item.descripcion),
                    _sanitizar_celda(item.categoria),
                    _sanitizar_celda(item.um),
                    _sanitizar_celda(item.cantidad_tomada),
                    _sanitizar_celda(item.cantidad_sobrante),
                    _sanitizar_celda(item.cantidad_consumida),
                    _sanitizar_celda(reporte.created_at),
                    _sanitizar_celda(reporte.closed_at),
                ]
            )
    return buffer.getvalue()
