from app.models.acta import ActaReporte
from app.models.actividad import ActividadReporte
from app.models.auditoria import AuditoriaEvento
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
from app.models.seguimiento import (
    EquipoMaterialConfig,
    Seguimiento,
    SeguimientoItem,
)

__all__ = [
    "ActaReporte",
    "ActividadReporte",
    "ActorAlmacenScope",
    "AuditoriaEvento",
    "CatalogoMaterial",
    "Categoria",
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
    "Seguimiento",
    "SeguimientoItem",
    "Ums",
]
