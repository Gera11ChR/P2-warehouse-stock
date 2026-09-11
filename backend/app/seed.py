"""Idempotent seed for the official 53-item material catalog.

Loads warehouses, the official catalog (5 fiber-optic CF-* SKUs + 48 general
SKUs per the DMS master template), and zero-balance CENTRAL custody rows.
Legacy non-official SKUs with transaction history are soft-deactivated
(`is_active = false`) and never physically deleted, preserving foreign keys
and the append-only ledger (Constitution 2.4, spec 001 REQ-STOCK-003).
Re-runs are idempotent: upserts only, no duplicates, no errors.

Run:  python -m app.seed
"""

import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Sku, UserWarehouseScope, Warehouse, WarehouseInventory

SEED_ACTOR = "seed"
DEMO_ACTOR = "demo-operador"

PRIMARY_WAREHOUSE = "CENTRAL"

WAREHOUSES = [
    ("CENTRAL", "Almacén Central"),
    ("NORTE", "Almacén Norte"),
    ("SUR", "Almacén Sur"),
]

# Catálogo oficial de 53 ítems (plantilla DMS):
# 5 módulo Fibra Óptica (tipo FIBRA) + 48 generales (tipo GENERAL).
# STOCK ACTUAL 0 / STOCK MÍNIMO 0 según la plantilla oficial ("SIN STOCK").
OFFICIAL_CATALOG = [
    # Módulo Fibra Óptica
    {"sku": "CF-DROP", "descripcion": "CARRETE FIBRA DROP", "categoria": "Fibra Óptica", "um": "CARRETE (1 KM)", "tipo": "FIBRA"},
    {"sku": "CF-6H-BRND", "descripcion": "CARRETES GRANDES FO 6H *BRAND", "categoria": "Fibra Óptica", "um": "CARRETE (5 KM)", "tipo": "FIBRA"},
    {"sku": "CF-12H-BRND", "descripcion": "CARRETES GRANDES FO 12H *BRAND", "categoria": "Fibra Óptica", "um": "CARRETE (5 KM)", "tipo": "FIBRA"},
    {"sku": "CF-24H-BRND", "descripcion": "CARRETES GRANDES FO 24H *BRAND", "categoria": "Fibra Óptica", "um": "CARRETE (5 KM)", "tipo": "FIBRA"},
    {"sku": "CF-48H-BRND", "descripcion": "CARRETES GRANDES FO 48H *BRAND", "categoria": "Fibra Óptica", "um": "CARRETE (5 KM)", "tipo": "FIBRA"},
    # Herrajes, Soporte y Planta Externa
    {"sku": "AC-001", "descripcion": "ACOPLADORES", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "ALC-1LT", "descripcion": "ALCOHOL ISOPROPÍLICO 1LT", "categoria": "Herrajes, Soporte y Planta Externa", "um": "LT", "tipo": "GENERAL"},
    {"sku": "BS-1M", "descripcion": "BRAZOS DE SOPORTE 1M", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "BS-45", "descripcion": "BRAZOS DE SOPORTE 45CM", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "BS-60", "descripcion": "BRAZOS DE SOPORTE 60CM", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "CJ-NAP-1X16", "descripcion": "CAJAS NAP SANDWICH 1*16", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "CJ-NAP-1X8", "descripcion": "CAJAS NAP SANDWICH 1*8", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "CE-48H", "descripcion": "CIERRES DE EMPALME DE 48H", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "CE-96H", "descripcion": "CIERRES DE EMPALME DE 96H", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "CN-VAR", "descripcion": "CINCHOS (VARIAS MEDIDAS: 5 HASTA 30)", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PAQUETE (100 PZ)", "tipo": "GENERAL"},
    {"sku": "CT-AIS-AM", "descripcion": "CINTA AISLANTE AMARILLA", "categoria": "Herrajes, Soporte y Planta Externa", "um": "ROLLO", "tipo": "GENERAL"},
    {"sku": "CN-MEC", "descripcion": "CONECTORES MECÁNICOS", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "FL-34", "descripcion": 'FLEJE DE ACERO INOXIDABLE "3/4"', "categoria": "Herrajes, Soporte y Planta Externa", "um": "ROLLO", "tipo": "GENERAL"},
    {"sku": "FS-FO", "descripcion": "FUSIONADORES DE FIBRA ÓPTICA", "categoria": "Herrajes, Soporte y Planta Externa", "um": "EQUIPO", "tipo": "GENERAL"},
    {"sku": "GP-3MM", "descripcion": "GRAPAS 3MM", "categoria": "Herrajes, Soporte y Planta Externa", "um": "BOLSA (500 PZ)", "tipo": "GENERAL"},
    {"sku": "HB-58", "descripcion": 'HEBILLAS PARA FLEJE "5/8"', "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "HR-DC-CCH", "descripcion": "HERRAJES TIPO D CHICO CON CHAVETA", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "HR-DC-SCH", "descripcion": "HERRAJES TIPO D CHICO SIN CHAVETA", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "HR-TJ", "descripcion": "HERRAJES TIPO J", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "HR-MLC", "descripcion": "MALICOS (HERRAJE / TENSOR DE REMATADO)", "categoria": "Herrajes, Soporte y Planta Externa", "um": "PZ", "tipo": "GENERAL"},
    # Conectividad y Consumibles
    {"sku": "JM-SCAPC-SMP", "descripcion": "JUMPERS SC/APC - SC/APC AMARILLO SIMPLEX", "categoria": "Conectividad y Consumibles", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "JM-ACP", "descripcion": "JUMPERS ACP", "categoria": "Conectividad y Consumibles", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "JM-UCP", "descripcion": "JUMPERS UCP", "categoria": "Conectividad y Consumibles", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "MG-6010", "descripcion": "MANGAS DE FUSIÓN (60MM / 10MM)", "categoria": "Conectividad y Consumibles", "um": "PAQUETE (100 PZ)", "tipo": "GENERAL"},
    {"sku": "MG-6012", "descripcion": "MANGAS DE FUSIÓN (60MM / 12MM)", "categoria": "Conectividad y Consumibles", "um": "PAQUETE (100 PZ)", "tipo": "GENERAL"},
    {"sku": "MG-6015", "descripcion": "MANGAS DE FUSIÓN (60MM / 15MM)", "categoria": "Conectividad y Consumibles", "um": "PAQUETE (100 PZ)", "tipo": "GENERAL"},
    {"sku": "MD-001", "descripcion": "MODEMS", "categoria": "Conectividad y Consumibles", "um": "UNIDAD", "tipo": "GENERAL"},
    {"sku": "RT-1011-NG", "descripcion": "RETENCIÓN PREFORMADO 10.11MM (NEGRO) (100PZ)", "categoria": "Conectividad y Consumibles", "um": "PAQUETE (100 PZ)", "tipo": "GENERAL"},
    {"sku": "RT-1112-RJ", "descripcion": "RETENCIÓN PREFORMADO 11.12MM (ROJO)", "categoria": "Conectividad y Consumibles", "um": "PAQUETE (100 PZ)", "tipo": "GENERAL"},
    {"sku": "RT-67-AM", "descripcion": "RETENCIÓN PREFORMADO 6.7MM (AMARILLO)", "categoria": "Conectividad y Consumibles", "um": "PAQUETE (100 PZ)", "tipo": "GENERAL"},
    {"sku": "TN-DROP", "descripcion": "TENSORES PARA FIBRA DROP", "categoria": "Conectividad y Consumibles", "um": "PZ", "tipo": "GENERAL"},
    # Splitters Desbalanceados
    {"sku": "SP-DES-298", "descripcion": "SPLITTERS DESBALANCEADOS 2/98", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-595", "descripcion": "SPLITTERS DESBALANCEADOS 5/95", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-1090", "descripcion": "SPLITTERS DESBALANCEADOS 10/90", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-1585", "descripcion": "SPLITTERS DESBALANCEADOS 15/85", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-2080", "descripcion": "SPLITTERS DESBALANCEADOS 20/80", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-2575", "descripcion": "SPLITTERS DESBALANCEADOS 25/75", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-3070", "descripcion": "SPLITTERS DESBALANCEADOS 30/70", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-3575", "descripcion": "SPLITTERS DESBALANCEADOS 35/75", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-4060", "descripcion": "SPLITTERS DESBALANCEADOS 40/60", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-4555", "descripcion": "SPLITTERS DESBALANCEADOS 45/55", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-DES-5050", "descripcion": "SPLITTERS DESBALANCEADOS 50/50", "categoria": "Splitters Desbalanceados", "um": "PZ", "tipo": "GENERAL"},
    # Splitters PLC
    {"sku": "SP-PLC-1X2", "descripcion": "SPLITTERS PLC 1*2 SIN CONECTORES", "categoria": "Splitters PLC", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-PLC-1X4", "descripcion": "SPLITTERS PLC 1*4 SIN CONECTORES", "categoria": "Splitters PLC", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-PLC-1X8", "descripcion": "SPLITTERS PLC 1*8 SIN CONECTORES", "categoria": "Splitters PLC", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-PLC-1X8-SCAPC", "descripcion": "SPLITTERS PLC 1*8 CONECTORES SC/APC", "categoria": "Splitters PLC", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-PLC-1X16", "descripcion": "SPLITTERS PLC 1*16 SIN CONECTORES", "categoria": "Splitters PLC", "um": "PZ", "tipo": "GENERAL"},
    {"sku": "SP-PLC-1X16-SCAPC", "descripcion": "SPLITTERS PLC 1*16 CONECTORES SC/APC", "categoria": "Splitters PLC", "um": "PZ", "tipo": "GENERAL"},
]

OFFICIAL_SKUS = [m["sku"] for m in OFFICIAL_CATALOG]


async def seed() -> None:
    async with SessionLocal() as session:
        async with session.begin():
            for warehouse_id, name in WAREHOUSES:
                existing = await session.get(Warehouse, warehouse_id)
                if existing is None:
                    session.add(Warehouse(warehouse_id=warehouse_id, name=name))
                elif existing.name != name:
                    existing.name = name

            for warehouse_id, _ in WAREHOUSES:
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

            created = 0
            for m in OFFICIAL_CATALOG:
                existing = await session.get(Sku, m["sku"])
                if existing is None:
                    session.add(
                        Sku(
                            sku=m["sku"],
                            description=m["descripcion"],
                            unit_of_measure=m["um"],
                            min_stock=0,
                            categoria=m["categoria"],
                            tipo=m["tipo"],
                            is_active=True,
                        )
                    )
                    created += 1
                else:
                    existing.description = m["descripcion"]
                    existing.unit_of_measure = m["um"]
                    existing.categoria = m["categoria"]
                    existing.tipo = m["tipo"]
                    if existing.min_stock is None:
                        existing.min_stock = 0
                    existing.is_active = True

                custody = await session.get(
                    WarehouseInventory, (PRIMARY_WAREHOUSE, m["sku"])
                )
                if custody is None:
                    session.add(
                        WarehouseInventory(
                            warehouse_id=PRIMARY_WAREHOUSE,
                            sku=m["sku"],
                            on_hand_quantity=0,
                        )
                    )

            # Depuración no destructiva: los SKUs ajenos al catálogo oficial
            # se desactivan (nunca se eliminan) para preservar sus FKs e historial.
            legacy = (
                (
                    await session.execute(
                        select(Sku).where(Sku.sku.not_in(OFFICIAL_SKUS))
                    )
                )
                .scalars()
                .all()
            )
            deactivated = 0
            for sku in legacy:
                if sku.is_active:
                    sku.is_active = False
                    deactivated += 1

            total_skus = (
                await session.execute(select(Sku).order_by(Sku.sku))
            ).scalars().all()
            active = sum(1 for s in total_skus if s.is_active)
            print(
                f"Seed complete: {created} nuevos materiales oficiales, "
                f"{deactivated} legacy desactivados "
                f"({active} activos / {len(total_skus)} totales en catálogo)"
            )


if __name__ == "__main__":
    asyncio.run(seed())
