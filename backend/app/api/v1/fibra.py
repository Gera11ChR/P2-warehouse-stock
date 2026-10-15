"""Fibra Óptica — Inventario FO unificado (RF-1, migración 0027).

El Inventario FO es UNA sola locación por material (`inventario_fibra` con
PK `material_id`): los antiguos subapartados PAQUETE/EN_USO desaparecen del
dominio vivo (los tipos legacy `FO_PAQUETE`/`FO_EN_USO` solo sobreviven
como valores históricos del ledger, RF-9). Toda mutación de stock se
delega a las stored functions `fn_cargar_stock_inicial_fibra` /
`fn_ajustar_stock_fibra` / `fn_eliminar_inventario_fibra` vía
services.transaccional — CERO aritmética de stock y CERO escritura directa
en Python (Invariantes 2 y 5 del proyecto).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import BusinessRuleError
from app.models import CatalogoMaterial, InventarioFibra
from app.schemas.inventario import (
    FibraAjusteRequest,
    FibraCargaInicialRequest,
    FibraMaterialOut,
    FibraMaterialUpdateRequest,
    FibraOperacionOut,
    FibraStockOut,
)
from app.schemas.material import MaterialUpdate
from app.security import (
    ActorContext,
    assert_authenticated,
    get_current_actor,
    require_admin,
)
from app.services import catalogo as catalogo_svc
from app.services import transaccional

router = APIRouter(prefix="/fibra", tags=["fibra"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


@router.get("", response_model=list[FibraStockOut])
async def stock_fibra(
    session: SessionDep, _actor: ActorDep
) -> list[FibraStockOut]:
    """Stock del Inventario FO unificado (RF-1) con el esquema estándar
    (CÓDIGO, DESCRIPCIÓN, U.M., STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK,
    VALOR UNITARIO por JOIN al catálogo maestro).

    Una sola fila por material; solo filas físicas de `inventario_fibra`
    (registros reales creados por la carga inicial); los materiales
    inactivos del catálogo se omiten (REQ-API-001: cero fantasmas). La
    métrica la gobierna `u_m`."""
    stmt = (
        select(
            InventarioFibra.material_id,
            CatalogoMaterial.codigo,
            CatalogoMaterial.descripcion,
            CatalogoMaterial.u_m,
            CatalogoMaterial.stock_minimo,
            CatalogoMaterial.valor_unitario,
            InventarioFibra.stock_actual,
        )
        .join(
            CatalogoMaterial,
            CatalogoMaterial.id_lista == InventarioFibra.material_id,
        )
        .where(
            CatalogoMaterial.is_active == True,  # noqa: E712
        )
        .order_by(InventarioFibra.material_id.asc())
    )
    filas = (await session.execute(stmt)).all()
    return [
        FibraStockOut(
            material_id=f.material_id,
            codigo=f.codigo,
            descripcion=f.descripcion,
            u_m=f.u_m,
            stock_minimo=f.stock_minimo,
            stock_actual=f.stock_actual,
            valor_unitario=f.valor_unitario,
            alerta_stock=(
                f.stock_actual <= f.stock_minimo
                if f.stock_minimo is not None
                else False
            ),
        )
        for f in filas
    ]


@router.post("/carga-inicial", response_model=FibraOperacionOut)
async def carga_inicial_fibra(
    payload: FibraCargaInicialRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> FibraOperacionOut:
    """Alta única e idempotente del Inventario FO (RF-1).

    Delega a `fn_cargar_stock_inicial_fibra`: rechaza si el material ya
    tiene fila y audita 'STOCK_INICIAL_FO' en PostgreSQL. Cantidad decimal
    con hasta 3 decimales (RF-6); sin `modulo` (enviarlo → 422)."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await transaccional.cargar_stock_inicial_fibra(
            session,
            material_id=payload.material_id,
            cantidad=payload.cantidad,
            motivo=payload.motivo,
        )
    return FibraOperacionOut(material_id=payload.material_id)


@router.post("/ajuste", response_model=FibraOperacionOut)
async def ajuste_fibra(
    payload: FibraAjusteRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> FibraOperacionOut:
    """Ajuste administrativo de stock del Inventario FO (RF-1).

    Ergonomía `justificacion_opcional` (REQ-ERG-005): motivo opcional; el
    diferencial, el bloqueo FOR UPDATE y la auditoría
    ('AJUSTE_INVENTARIO_FO') se calculan en PostgreSQL vía
    `fn_ajustar_stock_fibra` (Constitution 2.4: ledger inmutable).
    `nuevo_stock` decimal (RF-6); sin `modulo`."""
    assert_authenticated(actor_ctx)
    async with session.begin():
        await transaccional.ajustar_stock_fibra(
            session,
            material_id=payload.material_id,
            nuevo_stock=payload.nuevo_stock,
            motivo=payload.motivo,
        )
    return FibraOperacionOut(material_id=payload.material_id)


@router.patch("/materiales/{material_id}", response_model=FibraMaterialOut)
async def actualizar_material_fibra(
    material_id: int,
    payload: FibraMaterialUpdateRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> FibraMaterialOut:
    """Edición de material desde el Inventario FO unificado
    (REQ-CATFO-001/002).

    RBAC (RF-8, dictamen @sec-ops): la PRESENCIA de `valor_unitario` en el
    payload exige rol administrador (403); el gate se evalúa al inicio,
    antes de construir el payload de catálogo. Los demás campos conservan
    `assert_authenticated`.

    El stock JAMÁS se actualiza por ORM: `stock_actual`/`motivo` nunca
    entran al payload de catálogo (Invariante 5). Si `stock_actual` viene
    en el payload, el ajuste se enruta a `fn_ajustar_stock_fibra` dentro
    del MISMO `session.begin()` (REQ-STOCK-003): el diferencial, el bloqueo
    FOR UPDATE y la auditoría ('AJUSTE_INVENTARIO_FO') viven en PostgreSQL
    y, si el ajuste falla, la edición del material también revierte.
    La U.M. se valida dinámicamente contra el maestro `ums` (422
    determinístico, REQ-CATFO-002) y la modificación de catálogo queda
    auditada por el trigger tg_auditar_modificacion_material (RF-7)."""
    assert_authenticated(actor_ctx)
    if "valor_unitario" in payload.model_fields_set:
        require_admin(actor_ctx)
    async with session.begin():
        # Pre-chequeo: la fila física del material debe existir en
        # inventario_fibra — 404 temprana con coordenadas (REQ-CATFO-001).
        fila = (
            await session.execute(
                select(InventarioFibra).where(
                    InventarioFibra.material_id == material_id,
                )
            )
        ).scalar_one_or_none()
        if fila is None:
            raise BusinessRuleError(
                "Material no encontrado en Inventario FO",
                coordinates=[{"material_id": material_id}],
                status_code=404,
            )

        # Payload de SOLO catálogo: stock_actual/motivo jamás pasan por
        # setattr del ORM (espejo del exclude de catalogo_svc.actualizar).
        # `exclude_unset` preserva la semántica PATCH: solo los campos
        # realmente enviados por el cliente llegan a la edición (un payload
        # de solo-ajuste de stock NO anula descripción/código/U.M.).
        payload_catalogo = MaterialUpdate(
            **{
                campo: valor
                for campo, valor in payload.model_dump(exclude_unset=True).items()
                if campo not in ("stock_actual", "motivo")
            }
        )
        material = await catalogo_svc.actualizar(
            session, material_id, payload_catalogo, actor=actor_ctx.actor_id
        )
        if material is None:
            raise BusinessRuleError(
                "Material no encontrado",
                coordinates=[{"material_id": material_id}],
                status_code=404,
            )

        if payload.stock_actual is not None:
            # Ergonomía `justificacion_opcional` (REQ-ERG-004): motivo
            # opcional — puede venir None/vacío y el evento
            # AJUSTE_INVENTARIO_FO lo registra tal como llega.
            await transaccional.ajustar_stock_fibra(
                session,
                material_id=material_id,
                nuevo_stock=payload.stock_actual,
                motivo=payload.motivo,
            )

        # Re-lectura de la fila tras el ajuste: el UPDATE lo ejecutó la
        # stored function por SQL crudo, así que se refresca el objeto ORM
        # para materializar el stock final dentro de la MISMA transacción.
        await session.refresh(fila)
        return FibraMaterialOut(
            material_id=material_id,
            codigo=material.codigo,
            descripcion=material.descripcion,
            u_m=material.u_m,
            stock_minimo=material.stock_minimo,
            stock_actual=fila.stock_actual,
            valor_unitario=material.valor_unitario,
            alerta_stock=(
                fila.stock_actual <= material.stock_minimo
                if material.stock_minimo is not None
                else False
            ),
            categoria=material.categoria,
            categoria_id=material.categoria_id,
        )


@router.delete("/materiales/{material_id}", status_code=204)
async def eliminar_material_fibra(
    material_id: int,
    session: SessionDep,
    actor_ctx: ActorDep,
    response: Response,
    motivo: str | None = None,
) -> Response:
    """Eliminación FÍSICA de la fila del material de `inventario_fibra`
    (REQ-DEL-001/002/003/004, RF-1).

    Solo se elimina la fila del Inventario FO: `catalogo_materiales` y el
    Inventario General permanecen intactos (REQ-DEL-003). El evento
    'ELIMINACION_FO' con snapshot completo jsonb (material_id,
    stock_eliminado, motivo, usuario, fecha) lo inserta
    `fn_eliminar_inventario_fibra` en PostgreSQL (Constitution 6.2).

    `motivo` viaja como QUERY PARAM (204 sin body): obligatorio y no vacío
    SOLO si la fila tiene stock_actual > 0 — la validación autoritativa
    vive en PostgreSQL (RAISE → 422, REQ-DEL-004); con stock 0 es opcional
    (REQ-DEL-001). El cliente fibra.ts lo envía como query string.

    REQ-DEL-FIX-002 (fo_report_1.md): los errores de integridad que
    emergen en el COMMIT de `session.begin()` (p.ej. un IntegrityError por
    restricción de clave foránea diferida a commit) se traducen al mismo
    409 controlado con mensaje de dominio — jamás un 500."""
    assert_authenticated(actor_ctx)
    try:
        async with session.begin():
            await transaccional.eliminar_inventario_fibra(
                session,
                material_id=material_id,
                motivo=motivo,
                actor=actor_ctx.actor_id,
            )
    except DBAPIError as exc:
        raise await transaccional.mapear_error_delete_fibra(
            exc, material_id=material_id
        ) from exc
    response.status_code = 204
    return response
