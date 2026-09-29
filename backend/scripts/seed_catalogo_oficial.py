"""Seed idempotente del catálogo oficial de 53 materiales — Inventario General.

Proceso estrictamente repetible (UPSERT por `codigo`, índice parcial
`uq_catalogo_codigo_active`) y 100 % alineado al flujo de alta de material
de la API (`POST /api/v1/catalogo` con `stock_inicial` + `seccion_id`):

  1. Categorías oficiales: `ON CONFLICT (nombre) DO UPDATE SET is_active = TRUE`.
  2. Unidades de Medida maestras usadas por los 53: aseguradas y activas
     (reactiva `LT`, hoy inactiva en el maestro).
  3. Materiales: `ON CONFLICT (codigo) WHERE codigo IS NOT NULL DO UPDATE`
     de descripcion/categoria/u_m/stock_minimo con `is_active = TRUE`.
  4. STOCK ACTUAL 5: carga inicial en la sección GENERAL activa vía
     `fn_cargar_stock_inicial` SOLO si la fila de `inventario_almacen` no
     existe (re-ejecuciones jamás alteran stock ya cargado); la función
     inserta la auditoría `STOCK_INICIAL` en PostgreSQL (Invariante 5:
     cero aritmética y cero escritura directa de inventario desde Python).

Uso (desde `backend/` para que `app.config` cargue `.env`):

    .venv/bin/python scripts/seed_catalogo_oficial.py

o con URL explícita: `P2_DATABASE_URL=... .venv/bin/python scripts/...`
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.db import SessionLocal  # noqa: E402

MOTIVO_SEED = "Seed catálogo oficial de 53 materiales"

# (codigo, categoria, descripcion, u_m, stock_actual, stock_minimo)
MATERIALES: list[tuple[str, str, str, str, int, int]] = [
    ("CON-ACO-001", "Conectividad y Conectores", "ACOPLADORES", "PZ", 5, 1),
    ("EMP-ALC-001", "Empalmes y Consumibles", "ALCOHOL ISOPROPÍLICO 1LT", "LT", 5, 1),
    ("HER-BRA-003", "Herrajes, Herramientas y Sujeción", "BRAZOS DE SOPORTE 1M", "PZ", 5, 1),
    ("HER-BRA-001", "Herrajes, Herramientas y Sujeción", "BRAZOS DE SOPORTE 45CM", "PZ", 5, 1),
    ("HER-BRA-002", "Herrajes, Herramientas y Sujeción", "BRAZOS DE SOPORTE 60CM", "PZ", 5, 1),
    ("CIE-NAP-002", "Cierres y Cajas NAP", "CAJAS NAP SANDWICH 1×16", "PZ", 5, 1),
    ("CIE-NAP-001", "Cierres y Cajas NAP", "CAJAS NAP SANDWICH 1×8", "PZ", 5, 1),
    ("CAB-CAR-002", "Cables y Carretes", "CARRETE FIBRA DROP", "CARRETE (1 KM)", 5, 1),
    ("CAB-CAR-003", "Cables y Carretes", "CARRETES GRANDES FO 12H *BRAND", "CARRETE (5 KM)", 5, 1),
    ("CAB-CAR-004", "Cables y Carretes", "CARRETES GRANDES FO 24H *BRAND", "CARRETE (5 KM)", 5, 1),
    ("CAB-CAR-001", "Cables y Carretes", "CARRETES GRANDES FO 48H *BRAND", "CARRETE (5 KM)", 5, 1),
    ("CIE-CIE-001", "Cierres y Cajas NAP", "CARRETES GRANDES FO 6H *BRAND", "CARRETE (5 KM)", 5, 1),
    ("CIE-CIE-002", "Cierres y Cajas NAP", "CIERRES DE EMPALME DE 48H", "PZ", 5, 1),
    ("EMP-CIN-001", "Empalmes y Consumibles", "CIERRES DE EMPALME DE 96H", "PZ", 5, 1),
    ("EMP-CIN-002", "Empalmes y Consumibles", "CINCHOS (VARIAS MEDIDAS: 5 HASTA 30)", "PAQUETE (100 PZ)", 5, 1),
    ("CON-CON-001", "Conectividad y Conectores", "CINTA AISLANTE AMARILLA", "ROLLO", 5, 1),
    ("CAB-FIB-001", "Cables y Carretes", "CONECTORES MECÁNICOS", "PZ", 5, 1),
    ("HER-FLE-001", "Herrajes, Herramientas y Sujeción", "FLEJE DE ACERO INOXIDABLE 3/4", "ROLLO", 5, 1),
    ("HER-FUS-001", "Herrajes, Herramientas y Sujeción", "FUSIONADORES DE FIBRA ÓPTICA", "EQUIPO", 5, 1),
    ("HER-GRA-001", "Herrajes, Herramientas y Sujeción", "GRAPAS 3MM", "BOLSA (500 PZ)", 5, 1),
    ("HER-HEB-001", "Herrajes, Herramientas y Sujeción", "HEBILLAS PARA FLEJE 5/8", "PZ", 5, 1),
    ("HER-HER-001", "Herrajes, Herramientas y Sujeción", "HERRAJES TIPO D CHICO CON CHAVETA", "PZ", 5, 1),
    ("HER-HER-002", "Herrajes, Herramientas y Sujeción", "HERRAJES TIPO D CHICO SIN CHAVETA", "PZ", 5, 1),
    ("HER-HER-003", "Herrajes, Herramientas y Sujeción", "HERRAJES TIPO J", "PZ", 5, 1),
    ("CON-JUM-002", "Conectividad y Conectores", "JUMPERS SC/APC - SC/APC AMARILLO SIMPLEX", "PZ", 5, 1),
    ("CON-JUM-001", "Conectividad y Conectores", "JUMPERS ACP", "PZ", 5, 1),
    ("CON-JUM-003", "Conectividad y Conectores", "JUMPERS UCP", "PZ", 5, 1),
    ("HER-MAL-001", "Herrajes, Herramientas y Sujeción", "MALICOS (HERRAJE / TENSOR DE REMATADO)", "PZ", 5, 1),
    ("EMP-MAN-001", "Empalmes y Consumibles", "MANGAS DE FUSIÓN (60MM / 10MM)", "PAQUETE (100 PZ)", 5, 1),
    ("EMP-MAN-002", "Empalmes y Consumibles", "MANGAS DE FUSIÓN (60MM / 12MM)", "PAQUETE (100 PZ)", 5, 1),
    ("EMP-MAN-003", "Empalmes y Consumibles", "MANGAS DE FUSIÓN (60MM / 15MM)", "PAQUETE (100 PZ)", 5, 1),
    ("EQU-MOD-001", "Equipos", "MODEMS", "PZ", 5, 1),
    ("HER-RET-001", "Herrajes, Herramientas y Sujeción", "RETENCIÓN PREFORMADO 10.11MM (NEGRO) (100PZ)", "PAQUETE (100 PZ)", 5, 1),
    ("HER-RET-002", "Herrajes, Herramientas y Sujeción", "RETENCIÓN PREFORMADO 11.12MM (ROJO)", "PAQUETE (100 PZ)", 5, 1),
    ("HER-RET-003", "Herrajes, Herramientas y Sujeción", "RETENCIÓN PREFORMADO 6.7MM (AMARILLO)", "PAQUETE (100 PZ)", 5, 1),
    ("RED-SPL-001", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 10/90", "PZ", 5, 1),
    ("RED-SPL-002", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 15/85", "PZ", 5, 1),
    ("RED-SPL-004", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 2/98", "PZ", 5, 1),
    ("RED-SPL-003", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 20/80", "PZ", 5, 1),
    ("RED-SPL-005", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 25/75", "PZ", 5, 1),
    ("RED-SPL-006", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 30/70", "PZ", 5, 1),
    ("RED-SPL-007", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 35/75", "PZ", 5, 1),
    ("RED-SPL-008", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 40/60", "PZ", 5, 1),
    ("RED-SPL-009", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 45/55", "PZ", 5, 1),
    ("RED-SPL-011", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 5/95", "PZ", 5, 1),
    ("RED-SPL-010", "Red Pasiva y Splitters", "SPLITTERS DESBALANCEADOS 50/50", "PZ", 5, 1),
    ("RED-SPL-012", "Red Pasiva y Splitters", "SPLITTERS PLC 1×4 SIN CONECTORES", "PZ", 5, 1),
    ("RED-SPL-013", "Red Pasiva y Splitters", "SPLITTERS PLC 1×16 CONECTORES SC/APC", "PZ", 5, 1),
    ("RED-SPL-014", "Red Pasiva y Splitters", "SPLITTERS PLC 1×16 SIN CONECTORES", "PZ", 5, 1),
    ("RED-SPL-015", "Red Pasiva y Splitters", "SPLITTERS PLC 1×2 SIN CONECTORES", "PZ", 5, 1),
    ("RED-SPL-016", "Red Pasiva y Splitters", "SPLITTERS PLC 1×8 CONECTORES SC/APC", "PZ", 5, 1),
    ("RED-SPL-017", "Red Pasiva y Splitters", "SPLITTERS PLC 1×8 SIN CONECTORES", "PZ", 5, 1),
    ("HER-TEN-001", "Herrajes, Herramientas y Sujeción", "TENSORES PARA FIBRA DROP", "PZ", 5, 1),
]

SQL_UPSERT_CATEGORIA = text(
    "INSERT INTO categorias (nombre, is_active) VALUES (:nombre, TRUE) "
    "ON CONFLICT (nombre) DO UPDATE SET is_active = TRUE "
    "RETURNING id"
)

SQL_UPSERT_UM = text(
    "INSERT INTO ums (nombre, is_active) VALUES (:nombre, TRUE) "
    "ON CONFLICT (nombre) DO UPDATE SET is_active = TRUE "
    "RETURNING id"
)

SQL_UPSERT_MATERIAL = text(
    "INSERT INTO catalogo_materiales "
    "(codigo, descripcion, categoria_id, u_m, stock_minimo, is_active) "
    "VALUES (:codigo, :descripcion, :categoria_id, :u_m, :stock_minimo, TRUE) "
    "ON CONFLICT (codigo) WHERE codigo IS NOT NULL "
    "DO UPDATE SET descripcion = EXCLUDED.descripcion, "
    "              categoria_id = EXCLUDED.categoria_id, "
    "              u_m = EXCLUDED.u_m, "
    "              stock_minimo = EXCLUDED.stock_minimo, "
    "              is_active = TRUE "
    "RETURNING id_lista, (xmax = 0) AS insertado"
)

SQL_EXISTE_INVENTARIO = text(
    "SELECT EXISTS ("
    "SELECT 1 FROM inventario_almacen "
    "WHERE almacen_id = :almacen_id AND material_id = :material_id)"
)

SQL_CARGAR_STOCK = text(
    "SELECT fn_cargar_stock_inicial(:almacen_id, :material_id, :cantidad, :motivo)"
)

SQL_SECCION_GENERAL = text(
    "SELECT almacen_id FROM secciones "
    "WHERE tipo = 'GENERAL' AND is_active = TRUE "
    "ORDER BY almacen_id ASC LIMIT 1"
)

SQL_CONTEO = text(
    "SELECT COUNT(*) FROM catalogo_materiales "
    "WHERE is_active = TRUE AND codigo = ANY(:codigos)"
)


async def main() -> None:
    codigos = [m[0] for m in MATERIALES]
    categorias = sorted({m[1] for m in MATERIALES})
    ums = sorted({m[3] for m in MATERIALES})

    insertados = 0
    actualizados = 0
    cargas_nuevas = 0
    cargas_salteadas = 0

    async with SessionLocal() as session:
        async with session.begin():
            seccion_id = (
                await session.execute(SQL_SECCION_GENERAL)
            ).scalar_one_or_none()
            if seccion_id is None:
                raise RuntimeError(
                    "No existe una sección GENERAL activa en `secciones`; "
                    "el seed requiere Inventario General."
                )

            categoria_ids: dict[str, int] = {}
            for nombre in categorias:
                categoria_ids[nombre] = (
                    await session.execute(
                        SQL_UPSERT_CATEGORIA, {"nombre": nombre}
                    )
                ).scalar_one()

            for nombre in ums:
                await session.execute(SQL_UPSERT_UM, {"nombre": nombre})

            for codigo, categoria, descripcion, u_m, stock, minimo in MATERIALES:
                fila = (
                    await session.execute(
                        SQL_UPSERT_MATERIAL,
                        {
                            "codigo": codigo,
                            "descripcion": descripcion,
                            "categoria_id": categoria_ids[categoria],
                            "u_m": u_m,
                            "stock_minimo": minimo,
                        },
                    )
                ).one()
                id_lista, insertado = fila.id_lista, fila.insertado
                if insertado:
                    insertados += 1
                else:
                    actualizados += 1

                existe = (
                    await session.execute(
                        SQL_EXISTE_INVENTARIO,
                        {"almacen_id": seccion_id, "material_id": id_lista},
                    )
                ).scalar_one()
                if existe:
                    cargas_salteadas += 1
                    continue
                await session.execute(
                    SQL_CARGAR_STOCK,
                    {
                        "almacen_id": seccion_id,
                        "material_id": id_lista,
                        "cantidad": stock,
                        "motivo": MOTIVO_SEED,
                    },
                )
                cargas_nuevas += 1

            total = (
                await session.execute(SQL_CONTEO, {"codigos": codigos})
            ).scalar_one()

    print("=== Seed catálogo oficial (Inventario General) ===")
    print(f"Categorías aseguradas:            {len(categorias)}")
    print(f"U.M. maestras aseguradas:         {len(ums)}")
    print(f"Materiales INSERTADOS:            {insertados}")
    print(f"Materiales ACTUALIZADOS:          {actualizados}")
    print(f"Cargas de stock NUEVAS:           {cargas_nuevas}")
    print(f"Cargas de stock SALTEADAS:        {cargas_salteadas}")
    print(f"Total activos de los 53 códigos:  {total}")
    if total != 53:
        raise RuntimeError(f"Conteo final inesperado: {total} != 53")


if __name__ == "__main__":
    asyncio.run(main())
