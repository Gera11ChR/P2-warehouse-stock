from app.models.auditoria import AuditoriaEvento
from app.models.despliegue import Despliegue, DespliegueItem, EquipoMaterialConfig
from app.models.equipo import Equipo, EquipoIntegrante
from app.models.importacion import HistorialImportacion
from app.models.inventario import (
    InventarioAlmacen,
    InventarioEquipo,
    InventarioFibra,
    Seccion,
)
from app.models.material import CatalogoMaterial, Categoria, Ums
from app.models.movimiento import MovimientoCabecera, MovimientoDetalle
from app.models.scope import ActorAlmacenScope

__all__ = [
    "ActorAlmacenScope",
    "AuditoriaEvento",
    "CatalogoMaterial",
    "Categoria",
    "Despliegue",
    "DespliegueItem",
    "Equipo",
    "EquipoIntegrante",
    "EquipoMaterialConfig",
    "HistorialImportacion",
    "InventarioAlmacen",
    "InventarioEquipo",
    "InventarioFibra",
    "MovimientoCabecera",
    "MovimientoDetalle",
    "Seccion",
    "Ums",
]
