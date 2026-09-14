from sqlalchemy import Boolean, Column, Integer, String, Table

from app.db import Base

vw_inventario_equipo_completo = Table(
    "vw_inventario_equipo_completo",
    Base.metadata,
    Column("equipo_id", Integer),
    Column("id_lista", Integer),
    Column("codigo", String(50)),
    Column("descripcion", String(255)),
    Column("u_m", String(50)),
    Column("stock_minimo", Integer),
    Column("stock_actual", Integer),
    Column("alerta_stock", Boolean),
    info={"is_view": True},
)
