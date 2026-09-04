"""Idempotent seed for the WMS inventory dashboard.

Loads warehouses, 53 general materials, and 5 fiber-optic materials with their
initial warehouse balances recorded as RECEIPT stock movements (append-only
ledger invariant, spec 001 REQ-STOCK-003). Re-runs skip existing SKUs.

Run:  python -m app.seed
"""

import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Sku, StockMovement, UserWarehouseScope, Warehouse, WarehouseInventory

SEED_ACTOR = "seed"
DEMO_ACTOR = "demo-operador"

WAREHOUSES = [
    ("CENTRAL", "Almacén Central"),
    ("NORTE", "Almacén Norte"),
    ("SUR", "Almacén Sur"),
]

GENERAL_MATERIALS = [
    # Cables
    {"sku": "CBL-FO-001", "descripcion": "Cable fibra óptica monomodo 12 hilos", "categoria": "Cables", "um": "CARRETE (1 KM)", "min_stock": 5, "stock": 40},
    {"sku": "CBL-FO-002", "descripcion": "Cable fibra óptica monomodo 24 hilos", "categoria": "Cables", "um": "CARRETE (1 KM)", "min_stock": 5, "stock": 32},
    {"sku": "CBL-FO-003", "descripcion": "Cable fibra óptica monomodo 48 hilos", "categoria": "Cables", "um": "CARRETE (5 KM)", "min_stock": 3, "stock": 18},
    {"sku": "CBL-FO-004", "descripcion": "Cable fibra óptica multimodo OM3 24 hilos", "categoria": "Cables", "um": "CARRETE (1 KM)", "min_stock": 4, "stock": 22},
    {"sku": "CBL-FO-005", "descripcion": "Cable fibra óptica multimodo OM4 12 hilos", "categoria": "Cables", "um": "CARRETE (1 KM)", "min_stock": 4, "stock": 25},
    {"sku": "CBL-DROP-001", "descripcion": "Cable drop plano FTTH 1 fibra", "categoria": "Cables", "um": "ROLLO", "min_stock": 10, "stock": 60},
    {"sku": "CBL-DROP-002", "descripcion": "Cable drop figura 8 FTTH 2 fibras", "categoria": "Cables", "um": "ROLLO", "min_stock": 10, "stock": 55},
    {"sku": "CBL-CORD-001", "descripcion": "Cordón óptico dúplex LC-LC 3m", "categoria": "Cables", "um": "PZ", "min_stock": 20, "stock": 120},
    # Conectores
    {"sku": "CON-LC-001", "descripcion": "Conector LC monomodo UPC", "categoria": "Conectores", "um": "BOLSA (500 PZ)", "min_stock": 5, "stock": 30},
    {"sku": "CON-LC-002", "descripcion": "Conector LC monomodo APC", "categoria": "Conectores", "um": "BOLSA (500 PZ)", "min_stock": 5, "stock": 28},
    {"sku": "CON-SC-001", "descripcion": "Conector SC monomodo UPC", "categoria": "Conectores", "um": "BOLSA (500 PZ)", "min_stock": 5, "stock": 35},
    {"sku": "CON-SC-002", "descripcion": "Conector SC monomodo APC", "categoria": "Conectores", "um": "PAQUETE (100 PZ)", "min_stock": 8, "stock": 40},
    {"sku": "CON-ST-001", "descripcion": "Conector ST multimodo", "categoria": "Conectores", "um": "PAQUETE (100 PZ)", "min_stock": 6, "stock": 30},
    {"sku": "CON-FC-001", "descripcion": "Conector FC monomodo APC", "categoria": "Conectores", "um": "PAQUETE (100 PZ)", "min_stock": 5, "stock": 25},
    {"sku": "CON-ADAPT-001", "descripcion": "Adaptador LC-LC dúplex", "categoria": "Conectores", "um": "PZ", "min_stock": 30, "stock": 200},
    {"sku": "CON-ADAPT-002", "descripcion": "Adaptador SC-SC simplex", "categoria": "Conectores", "um": "PZ", "min_stock": 30, "stock": 180},
    {"sku": "CON-PIGTAIL-001", "descripcion": "Pigtail monomodo LC 1.5m", "categoria": "Conectores", "um": "PZ", "min_stock": 50, "stock": 300},
    {"sku": "CON-PIGTAIL-002", "descripcion": "Pigtail multimodo LC 1.5m", "categoria": "Conectores", "um": "PZ", "min_stock": 40, "stock": 250},
    # Empalmes y cierres
    {"sku": "EMP-CIERRE-001", "descripcion": "Cierre de empalme tipo domo 24 fibras", "categoria": "Empalmes", "um": "PZ", "min_stock": 8, "stock": 45},
    {"sku": "EMP-CIERRE-002", "descripcion": "Cierre de empalme tipo bandeja 48 fibras", "categoria": "Empalmes", "um": "PZ", "min_stock": 6, "stock": 30},
    {"sku": "EMP-BANDEJA-001", "descripcion": "Bandeja de empalme 12 fibras", "categoria": "Empalmes", "um": "PZ", "min_stock": 20, "stock": 120},
    {"sku": "EMP-MANGUITO-001", "descripcion": "Manguito de protección de empalme 60mm", "categoria": "Empalmes", "um": "PAQUETE (100 PZ)", "min_stock": 10, "stock": 80},
    {"sku": "EMP-FUSION-001", "descripcion": "Empalmadora de fusión de núcleo alineado", "categoria": "Empalmes", "um": "EQUIPO", "min_stock": 1, "stock": 6},
    {"sku": "EMP-ROSA-001", "descripcion": "Roseta óptica FTTH 1 puerto", "categoria": "Empalmes", "um": "PZ", "min_stock": 40, "stock": 220},
    {"sku": "EMP-ROSA-002", "descripcion": "Roseta óptica FTTH 2 puertos", "categoria": "Empalmes", "um": "PZ", "min_stock": 30, "stock": 180},
    {"sku": "EMP-CAJA-001", "descripcion": "Caja de distribución óptica 16 puertos", "categoria": "Empalmes", "um": "PZ", "min_stock": 10, "stock": 50},
    # Herramientas
    {"sku": "HER-CORTADORA-001", "descripcion": "Cortadora de precisión de fibra", "categoria": "Herramientas", "um": "EQUIPO", "min_stock": 2, "stock": 12},
    {"sku": "HER-PELADORA-001", "descripcion": "Peladora de fibra óptica de 3 agujeros", "categoria": "Herramientas", "um": "UNIDAD", "min_stock": 5, "stock": 30},
    {"sku": "HER-VFL-001", "descripcion": "Localizador visual de fallas VFL", "categoria": "Herramientas", "um": "UNIDAD", "min_stock": 5, "stock": 25},
    {"sku": "HER-MEDIDOR-001", "descripcion": "Medidor de potencia óptica", "categoria": "Herramientas", "um": "EQUIPO", "min_stock": 3, "stock": 15},
    {"sku": "HER-ALCOHOL-001", "descripcion": "Alcohol isopropílico 99% para limpieza", "categoria": "Herramientas", "um": "LT", "min_stock": 10, "stock": 60},
    {"sku": "HER-KIT-001", "descripcion": "Kit de limpieza para conectores", "categoria": "Herramientas", "um": "PZ", "min_stock": 15, "stock": 90},
    # Equipos
    {"sku": "EQU-OTDR-001", "descripcion": "OTDR reflectómetro óptico", "categoria": "Equipos", "um": "EQUIPO", "min_stock": 1, "stock": 4},
    {"sku": "EQU-ONU-001", "descripcion": "ONU GPON 1 puerto", "categoria": "Equipos", "um": "EQUIPO", "min_stock": 20, "stock": 150},
    {"sku": "EQU-OLT-001", "descripcion": "OLT GPON 8 puertos", "categoria": "Equipos", "um": "EQUIPO", "min_stock": 2, "stock": 8},
    {"sku": "EQU-SFP-001", "descripcion": "Transceptor SFP monomodo 10km", "categoria": "Equipos", "um": "PZ", "min_stock": 25, "stock": 160},
    {"sku": "EQU-SFP-002", "descripcion": "Transceptor SFP+ monomodo 40km", "categoria": "Equipos", "um": "PZ", "min_stock": 15, "stock": 80},
    # Protección y accesorios
    {"sku": "PRO-TUBO-001", "descripcion": "Tubo termocontráctil para empalme", "categoria": "Protección", "um": "PAQUETE (100 PZ)", "min_stock": 12, "stock": 100},
    {"sku": "PRO-CINTA-001", "descripcion": "Cinta aislante autosoldable", "categoria": "Protección", "um": "ROLLO", "min_stock": 20, "stock": 140},
    {"sku": "PRO-VELCRO-001", "descripcion": "Cinta velcro para organizar cableado", "categoria": "Protección", "um": "ROLLO", "min_stock": 20, "stock": 130},
    {"sku": "PRO-BANDEJA-001", "descripcion": "Bandeja porta-fusión modular", "categoria": "Protección", "um": "PZ", "min_stock": 15, "stock": 80},
    {"sku": "PRO-ETIQUETA-001", "descripcion": "Etiquetas autolaminables para fibra", "categoria": "Protección", "um": "PAQUETE (100 PZ)", "min_stock": 10, "stock": 90},
    {"sku": "PRO-SUJETADOR-001", "descripcion": "Sujetador de cable con tornillo", "categoria": "Protección", "um": "BOLSA (500 PZ)", "min_stock": 8, "stock": 60},
    # Consumibles
    {"sku": "CONS-TOALLA-001", "descripcion": "Toallitas limpiadoras sin pelusa", "categoria": "Consumibles", "um": "PAQUETE (100 PZ)", "min_stock": 15, "stock": 120},
    {"sku": "CONS-GEL-001", "descripcion": "Gel de limpieza óptica", "categoria": "Consumibles", "um": "LT", "min_stock": 10, "stock": 50},
    {"sku": "CONS-AIRE-001", "descripcion": "Aire comprimido enlatado", "categoria": "Consumibles", "um": "UNIDAD", "min_stock": 20, "stock": 100},
    {"sku": "CONS-GUANTES-001", "descripcion": "Guantes antiestáticos desechables", "categoria": "Consumibles", "um": "BOLSA (500 PZ)", "min_stock": 5, "stock": 40},
    {"sku": "CONS-BOLSA-001", "descripcion": "Bolsas antiestáticas para componentes", "categoria": "Consumibles", "um": "PAQUETE (100 PZ)", "min_stock": 12, "stock": 70},
    # Varios
    {"sku": "VAR-PATCH-001", "descripcion": "Patch panel fibra óptica 24 puertos", "categoria": "Varios", "um": "PZ", "min_stock": 5, "stock": 25},
    {"sku": "VAR-CASETE-001", "descripcion": "Casete óptico modular 12 fibras", "categoria": "Varios", "um": "PZ", "min_stock": 10, "stock": 60},
    {"sku": "VAR-ATENUADOR-001", "descripcion": "Atenuador óptico fijo 5dB LC", "categoria": "Varios", "um": "PZ", "min_stock": 30, "stock": 200},
    {"sku": "VAR-DIVISOR-001", "descripcion": "Divisor óptico PLC 1x8", "categoria": "Varios", "um": "PZ", "min_stock": 15, "stock": 90},
    {"sku": "VAR-ACOPLE-001", "descripcion": "Acoplador híbrido de adaptación", "categoria": "Varios", "um": "PZ", "min_stock": 20, "stock": 110},
]

FIBER_MATERIALS = [
    {"sku": "FO-MONO-001", "descripcion": "Fibra óptica monomodo G.652.D", "categoria": "Fibra Óptica", "um": "CARRETE (5 KM)", "min_stock": 3, "stock": 20},
    {"sku": "FO-MONO-002", "descripcion": "Fibra óptica monomodo G.657.A2", "categoria": "Fibra Óptica", "um": "CARRETE (5 KM)", "min_stock": 3, "stock": 16},
    {"sku": "FO-MULTI-001", "descripcion": "Fibra óptica multimodo OM4", "categoria": "Fibra Óptica", "um": "CARRETE (1 KM)", "min_stock": 4, "stock": 24},
    {"sku": "FO-MULTI-002", "descripcion": "Fibra óptica multimodo OM3", "categoria": "Fibra Óptica", "um": "CARRETE (1 KM)", "min_stock": 4, "stock": 20},
    {"sku": "FO-PATCH-001", "descripcion": "Pigtail fibra óptica LC APC", "categoria": "Fibra Óptica", "um": "PZ", "min_stock": 40, "stock": 260},
]


async def seed() -> None:
    async with SessionLocal() as session:
        async with session.begin():
            for warehouse_id, name in WAREHOUSES:
                existing = await session.get(Warehouse, warehouse_id)
                if existing is None:
                    session.add(Warehouse(warehouse_id=warehouse_id, name=name))
                elif existing.name != name:
                    existing.name = name

            warehouse_ids = [wid for wid, _ in WAREHOUSES]

            for warehouse_id in warehouse_ids:
                existing_scope = await session.get(
                    UserWarehouseScope, (DEMO_ACTOR, warehouse_id)
                )
                if existing_scope is None:
                    session.add(
                        UserWarehouseScope(
                            actor_id=DEMO_ACTOR,
                            warehouse_id=warehouse_id,
                            granted_by=SEED_ACTOR,
                        )
                    )

            materials = [
                {**m, "tipo": "GENERAL"} for m in GENERAL_MATERIALS
            ] + [
                {**m, "tipo": "FIBRA"} for m in FIBER_MATERIALS
            ]

            created = 0
            for index, m in enumerate(materials):
                existing = await session.get(Sku, m["sku"])
                if existing is not None:
                    continue
                session.add(
                    Sku(
                        sku=m["sku"],
                        description=m["descripcion"],
                        unit_of_measure=m["um"],
                        min_stock=m["min_stock"],
                        categoria=m["categoria"],
                        tipo=m["tipo"],
                    )
                )
                warehouse_id = warehouse_ids[index % len(warehouse_ids)]
                session.add(
                    WarehouseInventory(
                        warehouse_id=warehouse_id,
                        sku=m["sku"],
                        on_hand_quantity=m["stock"],
                    )
                )
                session.add(
                    StockMovement(
                        warehouse_id=warehouse_id,
                        sku=m["sku"],
                        quantity_change=m["stock"],
                        movement_type="RECEIPT",
                        actor_id=SEED_ACTOR,
                    )
                )
                created += 1

            total_skus = (
                await session.execute(select(Sku).order_by(Sku.sku))
            ).scalars().all()
            print(
                f"Seed complete: {created} nuevos materiales "
                f"({len(total_skus)} totales en catálogo)"
            )


if __name__ == "__main__":
    asyncio.run(seed())
