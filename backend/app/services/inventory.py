from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BusinessRuleError
from app.services.audit import make_audit
from app.models import AuditLog, FleetAllocation, StockMovement, Vehicle
from app.services.locking import lock_inventory_rows


@dataclass(frozen=True)
class AdjustmentItem:
    warehouse_id: str
    sku: str
    quantity_change: int


class InventoryService:
    @staticmethod
    async def adjust_stock(
        session: AsyncSession,
        *,
        warehouse_id: str,
        sku: str,
        quantity_change: int,
        actor: str,
        movement_type: str = "ADJUSTMENT",
        action: str = "STOCK_ADJUST",
        references_movement_id: int | None = None,
    ) -> StockMovement:
        if quantity_change == 0:
            raise BusinessRuleError(
                "Quantity change must be non-zero",
                coordinates=[{"warehouse_id": warehouse_id, "sku": sku}],
            )

        rows = await lock_inventory_rows(session, [(warehouse_id, sku)])
        row = rows.get((warehouse_id, sku))
        if row is None:
            raise BusinessRuleError(
                "Warehouse inventory row not found",
                coordinates=[{"warehouse_id": warehouse_id, "sku": sku}],
            )

        new_quantity = row.on_hand_quantity + quantity_change
        if new_quantity < 0:
            raise BusinessRuleError(
                "Insufficient stock",
                coordinates=[
                    {
                        "warehouse_id": warehouse_id,
                        "sku": sku,
                        "on_hand": row.on_hand_quantity,
                        "requested_change": quantity_change,
                    }
                ],
            )

        row.on_hand_quantity = new_quantity
        movement = StockMovement(
            warehouse_id=warehouse_id,
            sku=sku,
            quantity_change=quantity_change,
            movement_type=movement_type,
            actor_id=actor,
            references_movement_id=references_movement_id,
        )
        session.add(movement)
        await session.flush()

        session.add(
            make_audit(
                action=action,
                actor=actor,
                details={
                    "warehouse_id": warehouse_id,
                    "sku": sku,
                    "quantity_change": quantity_change,
                    "movement_type": movement_type,
                    "movement_id": movement.movement_id,
                },
            )
        )
        return movement

    @staticmethod
    async def adjust_stock_bulk(
        session: AsyncSession,
        items: list[AdjustmentItem],
        *,
        actor: str,
        movement_type: str = "ADJUSTMENT",
        action: str = "STOCK_ADJUST_BULK",
    ) -> list[StockMovement]:
        if not items:
            raise BusinessRuleError("Bulk payload must not be empty", coordinates=[])

        rows = await lock_inventory_rows(
            session, [(item.warehouse_id, item.sku) for item in items]
        )

        errors: list[dict] = []
        for index, item in enumerate(items):
            row = rows.get((item.warehouse_id, item.sku))
            if row is None:
                errors.append(
                    {
                        "line_index": index,
                        "field": "sku",
                        "message": "warehouse inventory row not found",
                        "warehouse_id": item.warehouse_id,
                        "sku": item.sku,
                    }
                )
                continue
            if item.quantity_change == 0:
                errors.append(
                    {
                        "line_index": index,
                        "field": "quantity_change",
                        "message": "quantity change must be non-zero",
                        "warehouse_id": item.warehouse_id,
                        "sku": item.sku,
                    }
                )
                continue
            if row.on_hand_quantity + item.quantity_change < 0:
                errors.append(
                    {
                        "line_index": index,
                        "field": "quantity_change",
                        "message": "insufficient stock",
                        "warehouse_id": item.warehouse_id,
                        "sku": item.sku,
                        "on_hand": row.on_hand_quantity,
                    }
                )

        if errors:
            raise BusinessRuleError(
                "Bulk adjustment rejected", coordinates=errors
            )

        movements: list[StockMovement] = []
        for item in items:
            row = rows[(item.warehouse_id, item.sku)]
            row.on_hand_quantity += item.quantity_change
            movement = StockMovement(
                warehouse_id=item.warehouse_id,
                sku=item.sku,
                quantity_change=item.quantity_change,
                movement_type=movement_type,
                actor_id=actor,
            )
            session.add(movement)
            movements.append(movement)

        await session.flush()
        session.add(
            make_audit(
                action=action,
                actor=actor,
                details={
                    "lines": [
                        {
                            "warehouse_id": item.warehouse_id,
                            "sku": item.sku,
                            "quantity_change": item.quantity_change,
                        }
                        for item in items
                    ],
                    "movement_type": movement_type,
                },
            )
        )
        return movements

    @staticmethod
    async def allocate_to_vehicle(
        session: AsyncSession,
        *,
        vehicle_id: str,
        warehouse_id: str,
        sku: str,
        quantity: int,
        actor: str,
    ) -> FleetAllocation:
        if quantity <= 0:
            raise BusinessRuleError(
                "Allocated quantity must be positive",
                coordinates=[{"vehicle_id": vehicle_id, "warehouse_id": warehouse_id, "sku": sku}],
            )

        vehicle = await session.get(Vehicle, vehicle_id)
        if vehicle is None:
            raise BusinessRuleError(
                "Vehicle not found",
                coordinates=[{"vehicle_id": vehicle_id}],
            )

        rows = await lock_inventory_rows(session, [(warehouse_id, sku)])
        row = rows.get((warehouse_id, sku))
        if row is None:
            raise BusinessRuleError(
                "Warehouse inventory row not found",
                coordinates=[{"warehouse_id": warehouse_id, "sku": sku}],
            )
        if row.on_hand_quantity - quantity < 0:
            raise BusinessRuleError(
                "Insufficient stock for fleet allocation",
                coordinates=[
                    {
                        "warehouse_id": warehouse_id,
                        "sku": sku,
                        "on_hand": row.on_hand_quantity,
                        "requested": quantity,
                    }
                ],
            )

        row.on_hand_quantity -= quantity
        movement = StockMovement(
            warehouse_id=warehouse_id,
            sku=sku,
            quantity_change=-quantity,
            movement_type="DISPATCH",
            actor_id=actor,
        )
        session.add(movement)
        await session.flush()

        allocation = FleetAllocation(
            vehicle_id=vehicle_id,
            warehouse_id=warehouse_id,
            sku=sku,
            allocated_quantity=quantity,
        )
        session.add(allocation)
        await session.flush()

        session.add(
            make_audit(
                action="FLEET_ALLOCATION",
                actor=actor,
                details={
                    "vehicle_id": vehicle_id,
                    "warehouse_id": warehouse_id,
                    "sku": sku,
                    "allocated_quantity": quantity,
                    "allocation_id": allocation.allocation_id,
                    "movement_id": movement.movement_id,
                },
            )
        )
        return allocation
