from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import AuthorizationError, TransferNotFoundError
from app.models import StockTransfer, TransferLineItem
from app.schemas.transfer import (
    MfaElevationOut,
    MfaElevationRequest,
    ReceiveLinePayload,
    TransferCreate,
    TransferLineOut,
    TransferListOut,
    TransferOut,
)
from app.security import ActorContext, assert_scope, get_current_actor
from app.services.mfa import issue_elevation, verify_elevation
from app.services.transfer import CreateLine, ReceiveLine, TransferService

router = APIRouter(prefix="/stock-transfers", tags=["stock-transfers"])

IdempotencyKeyHeader = Annotated[str, Header(alias="Idempotency-Key")]
ElevationHeader = Annotated[UUID | None, Header(alias="X-Elevation-Id")]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
ActorDep = Annotated[ActorContext, Depends(get_current_actor)]


async def _to_out(session: AsyncSession, transfer: StockTransfer) -> TransferOut:
    lines = (
        (
            await session.execute(
                select(TransferLineItem)
                .where(TransferLineItem.transfer_id == transfer.transfer_id)
                .order_by(TransferLineItem.line_id)
            )
        )
        .scalars()
        .all()
    )
    return TransferOut.model_validate(
        {
            "transfer_id": transfer.transfer_id,
            "idempotency_key": transfer.idempotency_key,
            "status": transfer.status,
            "source_warehouse_id": transfer.source_warehouse_id,
            "destination_warehouse_id": transfer.destination_warehouse_id,
            "requested_by": transfer.requested_by,
            "approved_by": transfer.approved_by,
            "created_at": transfer.created_at,
            "dispatched_at": transfer.dispatched_at,
            "received_at": transfer.received_at,
            "lines": [
                TransferLineOut.model_validate(
                    {
                        "line_id": line.line_id,
                        "sku": line.sku,
                        "dispatched_quantity": line.dispatched_quantity,
                        "received_quantity": line.received_quantity,
                    }
                )
                for line in lines
            ],
        }
    )


async def _load_for_scope(
    session: AsyncSession, transfer_id: UUID, actor_ctx: ActorContext
) -> StockTransfer:
    transfer = await session.get(StockTransfer, transfer_id)
    if transfer is None or not (
        set(actor_ctx.scoped_warehouse_ids)
        & {transfer.source_warehouse_id, transfer.destination_warehouse_id}
    ):
        raise TransferNotFoundError(transfer_id)
    return transfer


@router.post("", response_model=TransferOut)
async def create_transfer(
    payload: TransferCreate,
    session: SessionDep,
    actor_ctx: ActorDep,
    idempotency_key: IdempotencyKeyHeader,
    response: Response,
) -> TransferOut:
    assert_scope(
        actor_ctx,
        {payload.source_warehouse_id, payload.destination_warehouse_id},
    )
    async with session.begin():
        transfer, created = await TransferService.create(
            session,
            source_warehouse_id=payload.source_warehouse_id,
            destination_warehouse_id=payload.destination_warehouse_id,
            lines=[CreateLine(sku=l.sku, quantity=l.quantity) for l in payload.lines],
            actor=actor_ctx.actor_id,
            idempotency_key=idempotency_key,
        )
        response.status_code = 201 if created else 200
        return await _to_out(session, transfer)


@router.post("/{transfer_id}/elevations", response_model=MfaElevationOut, status_code=201)
async def create_elevation(
    transfer_id: UUID,
    payload: MfaElevationRequest,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> MfaElevationOut:
    async with session.begin():
        await _load_for_scope(session, transfer_id, actor_ctx)
        elevation = await issue_elevation(
            session,
            actor=actor_ctx.actor_id,
            transfer_id=transfer_id,
            action=payload.action,
            totp_code=payload.totp_code,
        )
        return MfaElevationOut.model_validate(
            {
                "elevation_id": elevation.elevation_id,
                "action": elevation.action,
                "expires_at": elevation.expires_at,
            }
        )


@router.post("/{transfer_id}/approve", response_model=TransferOut)
async def approve_transfer(
    transfer_id: UUID,
    session: SessionDep,
    actor_ctx: ActorDep,
    elevation_id: ElevationHeader = None,
) -> TransferOut:
    async with session.begin():
        await _load_for_scope(session, transfer_id, actor_ctx)
        if elevation_id is None:
            raise AuthorizationError(
                "MFA elevation required for approval",
                code="MFA_REQUIRED",
                actor=actor_ctx.actor_id,
            )
        await verify_elevation(
            session,
            actor=actor_ctx.actor_id,
            transfer_id=transfer_id,
            action="APPROVE",
            elevation_id=elevation_id,
        )
        transfer = await TransferService.approve(
            session, transfer_id=transfer_id, actor=actor_ctx.actor_id
        )
        return await _to_out(session, transfer)


@router.post("/{transfer_id}/reject", response_model=TransferOut)
async def reject_transfer(
    transfer_id: UUID,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> TransferOut:
    async with session.begin():
        await _load_for_scope(session, transfer_id, actor_ctx)
        transfer = await TransferService.reject(
            session, transfer_id=transfer_id, actor=actor_ctx.actor_id
        )
        return await _to_out(session, transfer)


@router.post("/{transfer_id}/dispatch", response_model=TransferOut)
async def dispatch_transfer(
    transfer_id: UUID,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> TransferOut:
    async with session.begin():
        transfer = await session.get(StockTransfer, transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        assert_scope(actor_ctx, {transfer.source_warehouse_id})
        transfer = await TransferService.dispatch(
            session, transfer_id=transfer_id, actor=actor_ctx.actor_id
        )
        return await _to_out(session, transfer)


@router.post("/{transfer_id}/receive", response_model=TransferOut)
async def receive_transfer(
    transfer_id: UUID,
    lines: list[ReceiveLinePayload],
    session: SessionDep,
    actor_ctx: ActorDep,
) -> TransferOut:
    async with session.begin():
        transfer = await session.get(StockTransfer, transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        assert_scope(actor_ctx, {transfer.destination_warehouse_id})
        transfer = await TransferService.receive(
            session,
            transfer_id=transfer_id,
            lines=[
                ReceiveLine(line_id=l.line_id, received_quantity=l.received_quantity)
                for l in lines
            ],
            actor=actor_ctx.actor_id,
        )
        return await _to_out(session, transfer)


@router.post("/{transfer_id}/cancel", response_model=TransferOut)
async def cancel_transfer(
    transfer_id: UUID,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> TransferOut:
    async with session.begin():
        transfer = await session.get(StockTransfer, transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        is_creator = transfer.actor_id == actor_ctx.actor_id
        is_scoped = bool(
            set(actor_ctx.scoped_warehouse_ids)
            & {transfer.source_warehouse_id, transfer.destination_warehouse_id}
        )
        if not (is_creator or is_scoped):
            raise AuthorizationError(
                "Only the creator or a scoped operator may cancel this transfer",
                actor=actor_ctx.actor_id,
            )
        transfer = await TransferService.cancel(
            session, transfer_id=transfer_id, actor=actor_ctx.actor_id
        )
        return await _to_out(session, transfer)


@router.get("", response_model=TransferListOut)
async def list_transfers(
    session: SessionDep,
    actor_ctx: ActorDep,
) -> TransferListOut:
    scope = set(actor_ctx.scoped_warehouse_ids)
    if not scope:
        return TransferListOut.model_validate({"transfers": []})
    transfers = (
        (
            await session.execute(
                select(StockTransfer)
                .where(
                    or_(
                        StockTransfer.source_warehouse_id.in_(scope),
                        StockTransfer.destination_warehouse_id.in_(scope),
                    )
                )
                .order_by(StockTransfer.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return TransferListOut.model_validate(
        {
            "transfers": [
                await _to_out(session, transfer) for transfer in transfers
            ]
        }
    )


@router.get("/{transfer_id}", response_model=TransferOut)
async def get_transfer(
    transfer_id: UUID,
    session: SessionDep,
    actor_ctx: ActorDep,
) -> TransferOut:
    transfer = await _load_for_scope(session, transfer_id, actor_ctx)
    return await _to_out(session, transfer)
