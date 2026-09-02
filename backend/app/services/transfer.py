from dataclasses import dataclass
from datetime import datetime, timezone
import re
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TRANSFER_APPROVAL_THRESHOLD
from app.errors import (
    BusinessRuleError,
    TransferIdempotencyConflictError,
    TransferNotFoundError,
    TransferStateConflictError,
)
from app.services.audit import make_audit
from app.models import (
    AuditLog,
    Sku,
    StockMovement,
    StockTransfer,
    TransferLineItem,
    Warehouse,
)
from app.services.locking import lock_inventory_rows, lock_transfer_row

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class ReceiveLine:
    line_id: int
    received_quantity: int


@dataclass(frozen=True)
class CreateLine:
    sku: str
    quantity: int


class TransferService:
    @staticmethod
    async def create(
        session: AsyncSession,
        *,
        source_warehouse_id: str,
        destination_warehouse_id: str,
        lines: list[CreateLine],
        actor: str,
        idempotency_key: str,
    ) -> tuple[StockTransfer, bool]:
        if source_warehouse_id == destination_warehouse_id:
            raise BusinessRuleError(
                "Source and destination warehouses must differ",
                coordinates=[{"warehouse_id": source_warehouse_id}],
            )

        if not IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key):
            raise BusinessRuleError(
                "Idempotency key must be 1-64 chars of [A-Za-z0-9_-]",
                coordinates=[{"idempotency_key": idempotency_key}],
            )

        existing = (
            await session.execute(
                select(StockTransfer).where(
                    StockTransfer.actor_id == actor,
                    StockTransfer.idempotency_key == idempotency_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing, False

        other_actor = (
            await session.execute(
                select(StockTransfer.actor_id)
                .where(StockTransfer.idempotency_key == idempotency_key)
                .limit(1)
            )
        ).scalar_one_or_none()
        if other_actor is not None:
            raise TransferIdempotencyConflictError(idempotency_key)

        for warehouse_id in (source_warehouse_id, destination_warehouse_id):
            if await session.get(Warehouse, warehouse_id) is None:
                raise BusinessRuleError(
                    "Warehouse not found",
                    coordinates=[{"warehouse_id": warehouse_id}],
                )

        if len({line.sku for line in lines}) != len(lines):
            raise BusinessRuleError(
                "Duplicate SKU in transfer lines",
                coordinates=[
                    {"line_index": index, "sku": line.sku}
                    for index, line in enumerate(lines)
                ],
            )

        skus = {line.sku for line in lines}
        found = set(
            (
                await session.execute(select(Sku.sku).where(Sku.sku.in_(skus)))
            ).scalars()
        )
        missing = skus - found
        if missing:
            raise BusinessRuleError(
                "Unknown SKU",
                coordinates=[{"sku": sku} for sku in sorted(missing)],
            )

        total = sum(line.quantity for line in lines)
        status = (
            "PENDING_APPROVAL"
            if total > TRANSFER_APPROVAL_THRESHOLD
            else "APPROVED"
        )

        insert_stmt = (
            pg_insert(StockTransfer)
            .values(
                idempotency_key=idempotency_key,
                actor_id=actor,
                source_warehouse_id=source_warehouse_id,
                destination_warehouse_id=destination_warehouse_id,
                status=status,
                requested_by=actor,
            )
            .on_conflict_do_nothing(
                constraint="uq_stock_transfers_actor_idempotency"
            )
            .returning(StockTransfer.transfer_id)
        )
        transfer_id = (await session.execute(insert_stmt)).scalar_one_or_none()
        if transfer_id is None:
            winner = (
                await session.execute(
                    select(StockTransfer).where(
                        StockTransfer.actor_id == actor,
                        StockTransfer.idempotency_key == idempotency_key,
                    )
                )
            ).scalar_one()
            return winner, False

        transfer = await session.get(StockTransfer, transfer_id)
        assert transfer is not None

        for line in lines:
            session.add(
                TransferLineItem(
                    transfer_id=transfer.transfer_id,
                    sku=line.sku,
                    dispatched_quantity=line.quantity,
                )
            )

        session.add(
            make_audit(
                action="TRANSFER_CREATE",
                actor=actor,
                details={
                    "transfer_id": str(transfer.transfer_id),
                    "source_warehouse_id": source_warehouse_id,
                    "destination_warehouse_id": destination_warehouse_id,
                    "lines": [
                        {"sku": line.sku, "quantity": line.quantity}
                        for line in lines
                    ],
                },
            )
        )
        return transfer, True

    @staticmethod
    async def approve(
        session: AsyncSession, *, transfer_id: UUID, actor: str
    ) -> StockTransfer:
        transfer = await lock_transfer_row(session, transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        if transfer.status != "PENDING_APPROVAL":
            raise TransferStateConflictError(
                transfer_id,
                current_status=transfer.status,
                attempted="APPROVE",
            )
        transfer.status = "APPROVED"
        transfer.approved_by = actor
        session.add(
            make_audit(
                action="TRANSFER_APPROVE",
                actor=actor,
                details={"transfer_id": str(transfer_id)},
            )
        )
        return transfer

    @staticmethod
    async def reject(
        session: AsyncSession, *, transfer_id: UUID, actor: str
    ) -> StockTransfer:
        transfer = await lock_transfer_row(session, transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        if transfer.status != "PENDING_APPROVAL":
            raise TransferStateConflictError(
                transfer_id,
                current_status=transfer.status,
                attempted="REJECT",
            )
        transfer.status = "REJECTED"
        session.add(
            make_audit(
                action="TRANSFER_REJECT",
                actor=actor,
                details={"transfer_id": str(transfer_id)},
            )
        )
        return transfer

    @staticmethod
    async def cancel(
        session: AsyncSession, *, transfer_id: UUID, actor: str
    ) -> StockTransfer:
        transfer = await lock_transfer_row(session, transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        if transfer.status not in ("PENDING_APPROVAL", "APPROVED"):
            raise TransferStateConflictError(
                transfer_id,
                current_status=transfer.status,
                attempted="CANCEL",
            )
        transfer.status = "CANCELLED"
        session.add(
            make_audit(
                action="TRANSFER_CANCEL",
                actor=actor,
                details={"transfer_id": str(transfer_id)},
            )
        )
        return transfer

    @staticmethod
    async def dispatch(
        session: AsyncSession, *, transfer_id: UUID, actor: str
    ) -> StockTransfer:
        transfer = await lock_transfer_row(session, transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        if transfer.status != "APPROVED":
            raise TransferStateConflictError(
                transfer_id,
                current_status=transfer.status,
                attempted="DISPATCH",
            )

        lines = (
            (
                await session.execute(
                    select(TransferLineItem).where(
                        TransferLineItem.transfer_id == transfer_id
                    )
                )
            )
            .scalars()
            .all()
        )
        if not lines:
            raise BusinessRuleError(
                "Transfer has no line items",
                coordinates=[{"transfer_id": str(transfer_id)}],
            )

        rows = await lock_inventory_rows(
            session, [(transfer.source_warehouse_id, line.sku) for line in lines]
        )

        errors: list[dict] = []
        for line in lines:
            row = rows.get((transfer.source_warehouse_id, line.sku))
            on_hand = row.on_hand_quantity if row is not None else 0
            if on_hand < line.dispatched_quantity:
                errors.append(
                    {
                        "transfer_id": str(transfer_id),
                        "sku": line.sku,
                        "warehouse_id": transfer.source_warehouse_id,
                        "on_hand": on_hand,
                        "dispatched_quantity": line.dispatched_quantity,
                    }
                )
        if errors:
            raise BusinessRuleError(
                "Insufficient stock for dispatch", coordinates=errors
            )

        for line in lines:
            row = rows[(transfer.source_warehouse_id, line.sku)]
            row.on_hand_quantity -= line.dispatched_quantity
            session.add(
                StockMovement(
                    transfer_id=transfer_id,
                    warehouse_id=transfer.source_warehouse_id,
                    sku=line.sku,
                    quantity_change=-line.dispatched_quantity,
                    movement_type="TRANSFER_OUT",
                    actor_id=actor,
                )
            )

        transfer.status = "IN_TRANSIT"
        transfer.dispatched_at = datetime.now(timezone.utc)

        session.add(
            make_audit(
                action="TRANSFER_DISPATCH",
                actor=actor,
                details={
                    "transfer_id": str(transfer_id),
                    "source_warehouse_id": transfer.source_warehouse_id,
                    "destination_warehouse_id": transfer.destination_warehouse_id,
                    "lines": [
                        {"sku": line.sku, "dispatched_quantity": line.dispatched_quantity}
                        for line in lines
                    ],
                },
            )
        )
        return transfer

    @staticmethod
    async def receive(
        session: AsyncSession,
        *,
        transfer_id: UUID,
        lines: list[ReceiveLine],
        actor: str,
    ) -> StockTransfer:
        transfer = await lock_transfer_row(session, transfer_id)
        if transfer is None:
            raise TransferNotFoundError(transfer_id)
        if transfer.status != "IN_TRANSIT":
            raise TransferStateConflictError(
                transfer_id,
                current_status=transfer.status,
                attempted="RECEIVE",
            )

        if not lines:
            raise BusinessRuleError(
                "Receive payload must not be empty",
                coordinates=[{"transfer_id": str(transfer_id)}],
            )

        db_lines = (
            (
                await session.execute(
                    select(TransferLineItem).where(
                        TransferLineItem.transfer_id == transfer_id
                    )
                )
            )
            .scalars()
            .all()
        )
        by_id = {db_line.line_id: db_line for db_line in db_lines}

        errors: list[dict] = []
        seen: set[int] = set()
        for index, received in enumerate(lines):
            coordinate = {"line_index": index, "line_id": received.line_id}
            if received.line_id in seen:
                errors.append(
                    {
                        **coordinate,
                        "field": "line_id",
                        "message": "duplicate line in receive payload",
                    }
                )
                continue
            seen.add(received.line_id)
            db_line = by_id.get(received.line_id)
            if db_line is None:
                errors.append(
                    {
                        **coordinate,
                        "field": "line_id",
                        "message": "line does not belong to this transfer",
                    }
                )
                continue
            if not (0 <= received.received_quantity <= db_line.dispatched_quantity):
                errors.append(
                    {
                        **coordinate,
                        "field": "received_quantity",
                        "message": (
                            "received quantity outside "
                            "[0, dispatched_quantity]"
                        ),
                        "received_quantity": received.received_quantity,
                        "dispatched_quantity": db_line.dispatched_quantity,
                    }
                )

        payload_ids = set(seen)
        for db_line in db_lines:
            if db_line.line_id not in payload_ids:
                errors.append(
                    {
                        "field": "line_id",
                        "message": "line missing from receive payload",
                        "line_id": db_line.line_id,
                    }
                )

        if errors:
            raise BusinessRuleError("Receive payload invalid", coordinates=errors)

        keys = [
            (transfer.destination_warehouse_id, db_line.sku)
            for db_line in db_lines
        ]
        await lock_inventory_rows(session, keys)
        for warehouse_id, sku in keys:
            await session.execute(
                text(
                    "INSERT INTO warehouse_inventory "
                    "(warehouse_id, sku, on_hand_quantity) "
                    "VALUES (:warehouse_id, :sku, 0) "
                    "ON CONFLICT (warehouse_id, sku) DO NOTHING"
                ),
                {"warehouse_id": warehouse_id, "sku": sku},
            )
        rows = await lock_inventory_rows(session, keys)

        for received in lines:
            db_line = by_id[received.line_id]
            row = rows[(transfer.destination_warehouse_id, db_line.sku)]
            row.on_hand_quantity += db_line.dispatched_quantity
            db_line.received_quantity = received.received_quantity

            credit_movement = StockMovement(
                transfer_id=transfer_id,
                warehouse_id=transfer.destination_warehouse_id,
                sku=db_line.sku,
                quantity_change=db_line.dispatched_quantity,
                movement_type="TRANSFER_IN",
                actor_id=actor,
            )
            session.add(credit_movement)
            await session.flush()

            if received.received_quantity < db_line.dispatched_quantity:
                shortfall = db_line.dispatched_quantity - received.received_quantity
                row.on_hand_quantity -= shortfall
                session.add(
                    StockMovement(
                        transfer_id=transfer_id,
                        warehouse_id=transfer.destination_warehouse_id,
                        sku=db_line.sku,
                        quantity_change=-shortfall,
                        movement_type="ADJUSTMENT",
                        actor_id=actor,
                        references_movement_id=credit_movement.movement_id,
                    )
                )

        transfer.status = "RECEIVED"
        transfer.received_at = datetime.now(timezone.utc)

        session.add(
            make_audit(
                action="TRANSFER_RECEIVE",
                actor=actor,
                details={
                    "transfer_id": str(transfer_id),
                    "source_warehouse_id": transfer.source_warehouse_id,
                    "destination_warehouse_id": transfer.destination_warehouse_id,
                    "lines": [
                        {
                            "line_id": received.line_id,
                            "sku": by_id[received.line_id].sku,
                            "received_quantity": received.received_quantity,
                        }
                        for received in lines
                    ],
                },
            )
        )
        return transfer
