"""CRUD de catálogo. SOLO muta catalogo_materiales y categorias.

NUNCA toca inventario_almacen / inventario_equipos: la carga de stock inicial
se delega a fn_cargar_stock_inicial vía services.transaccional. El trigger
fn_auditar_modificacion_material registra la auditoría en PostgreSQL.
"""

from sqlalchemy import String, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BusinessRuleError
from app.models import CatalogoMaterial, Categoria
from app.schemas.material import (
    MaterialCreate,
    MaterialOut,
    MaterialUpdate,
)


async def _resolver_categoria(
    session: AsyncSession, *, categoria_id: int | None, nueva_categoria: str | None
) -> int | None:
    if nueva_categoria:
        existente = (
            await session.execute(
                select(Categoria).where(Categoria.nombre == nueva_categoria.strip())
            )
        ).scalar_one_or_none()
        if existente is not None:
            return existente.id
        categoria = Categoria(nombre=nueva_categoria.strip())
        session.add(categoria)
        await session.flush()
        return categoria.id
    return categoria_id


async def _validar_categoria(session: AsyncSession, categoria_id: int) -> None:
    categoria = await session.get(Categoria, categoria_id)
    if categoria is None:
        raise BusinessRuleError(
            "Categoría inexistente", coordinates=[{"categoria_id": categoria_id}]
        )


async def _to_out(session: AsyncSession, material: CatalogoMaterial) -> MaterialOut:
    nombre_categoria: str | None = None
    if material.categoria_id is not None:
        categoria = await session.get(Categoria, material.categoria_id)
        nombre_categoria = categoria.nombre if categoria is not None else None
    return MaterialOut(
        id_lista=material.id_lista,
        codigo=material.codigo,
        descripcion=material.descripcion,
        categoria_id=material.categoria_id,
        categoria=nombre_categoria,
        u_m=material.u_m,
        stock_minimo=material.stock_minimo,
        is_active=material.is_active,
    )


async def listar(
    session: AsyncSession,
    *,
    buscar: str | None = None,
    categoria_id: int | None = None,
    desde_id_lista: int | None = None,
    hasta_id_lista: int | None = None,
    desde_sku: str | None = None,
    hasta_sku: str | None = None,
    desde_numero_lista: int | None = None,
    hasta_numero_lista: int | None = None,
    desde_descripcion: str | None = None,
    hasta_descripcion: str | None = None,
) -> tuple[list[MaterialOut], int]:
    """Listado del catálogo activo con posicionamiento ordinal opcional.

    Orden de aplicación (REQ-API-006/007): primero se filtran los criterios
    de negocio — buscar, categoria_id, rangos id_lista/SKU y rangos de
    descripción — y DESPUÉS se aplica el OFFSET/LIMIT ordinal
    (determinista: ORDER BY descripcion ASC, id_lista ASC,
    OFFSET = desde_numero_lista - 1, LIMIT = hasta - desde + 1,
    start_index = desde_numero_lista or 1). Sin parámetros ordinales se
    conserva el comportamiento histórico (ORDER BY id_lista ASC,
    start_index = 1). Prohibido descargar el catálogo completo al cliente.
    """
    stmt = select(CatalogoMaterial).where(CatalogoMaterial.is_active == True)  # noqa: E712
    if buscar:
        patron = f"%{buscar}%"
        stmt = stmt.where(
            or_(
                CatalogoMaterial.codigo.ilike(patron),
                CatalogoMaterial.descripcion.ilike(patron),
                CatalogoMaterial.id_lista.cast(String).ilike(patron),
            )
        )
    if categoria_id is not None:
        stmt = stmt.where(CatalogoMaterial.categoria_id == categoria_id)
    if desde_id_lista is not None:
        stmt = stmt.where(CatalogoMaterial.id_lista >= desde_id_lista)
    if hasta_id_lista is not None:
        stmt = stmt.where(CatalogoMaterial.id_lista <= hasta_id_lista)
    if desde_sku is not None:
        stmt = stmt.where(CatalogoMaterial.codigo >= desde_sku)
    if hasta_sku is not None:
        stmt = stmt.where(CatalogoMaterial.codigo <= hasta_sku)
    # Rangos por descripción (REQ-API-007): filtros deterministas que
    # aplican junto con el resto de criterios ANTES del posicionamiento.
    if desde_descripcion:
        stmt = stmt.where(CatalogoMaterial.descripcion >= desde_descripcion)
    if hasta_descripcion:
        stmt = stmt.where(CatalogoMaterial.descripcion <= hasta_descripcion)

    # Posicionamiento ordinal determinista (REQ-API-006).
    if desde_numero_lista is not None or hasta_numero_lista is not None:
        stmt = stmt.order_by(
            CatalogoMaterial.descripcion.asc(),
            CatalogoMaterial.id_lista.asc(),
        )
        offset = (desde_numero_lista - 1) if desde_numero_lista is not None else 0
        stmt = stmt.offset(offset)
        if desde_numero_lista is not None and hasta_numero_lista is not None:
            stmt = stmt.limit(hasta_numero_lista - desde_numero_lista + 1)
        elif hasta_numero_lista is not None:
            # Desde implícito = 1 (REQ-API-006): LIMIT = Y.
            stmt = stmt.limit(hasta_numero_lista)
        start_index = desde_numero_lista or 1
    else:
        stmt = stmt.order_by(CatalogoMaterial.id_lista.asc())
        start_index = 1

    materiales = (await session.execute(stmt)).scalars().all()
    return [await _to_out(session, m) for m in materiales], start_index


async def obtener(session: AsyncSession, id_lista: int) -> MaterialOut | None:
    material = await session.get(CatalogoMaterial, id_lista)
    if material is None or not material.is_active:
        return None
    return await _to_out(session, material)


async def crear(
    session: AsyncSession, payload: MaterialCreate, *, actor: str
) -> MaterialOut:
    if payload.categoria_id is not None:
        await _validar_categoria(session, payload.categoria_id)

    categoria_id = await _resolver_categoria(
        session,
        categoria_id=payload.categoria_id,
        nueva_categoria=payload.nueva_categoria,
    )

    material = CatalogoMaterial(
        codigo=payload.codigo,
        descripcion=payload.descripcion,
        categoria_id=categoria_id,
        u_m=payload.u_m,
        stock_minimo=payload.stock_minimo,
    )
    session.add(material)
    await session.flush()
    return await _to_out(session, material)


async def actualizar(
    session: AsyncSession,
    id_lista: int,
    payload: MaterialUpdate,
    *,
    actor: str,
) -> MaterialOut | None:
    material = await session.get(CatalogoMaterial, id_lista)
    if material is None or not material.is_active:
        return None

    if payload.categoria_id is not None:
        await _validar_categoria(session, payload.categoria_id)

    categoria_id: int | None = None
    if payload.nueva_categoria:
        categoria_id = await _resolver_categoria(
            session, categoria_id=None, nueva_categoria=payload.nueva_categoria
        )
    elif payload.categoria_id is not None:
        categoria_id = payload.categoria_id

    update = payload.model_dump(
        exclude_unset=True,
        # stock_actual/motivo jamás pasan por setattr: el stock se ajusta
        # exclusivamente vía fn_ajustar_stock_general → fn_ajustar_stock_almacen
        # (Task 3.4); incluirlos aquí rompería el flush del ORM.
        exclude={"categoria_id", "nueva_categoria", "stock_actual", "motivo"},
    )
    for field, value in update.items():
        setattr(material, field, value)
    if categoria_id is not None:
        material.categoria_id = categoria_id

    await session.flush()
    return await _to_out(session, material)


async def eliminar(
    session: AsyncSession, id_lista: int, *, actor: str
) -> bool:
    """Eliminación controlada: soft-delete. `id_lista` NO se reutiliza jamás."""
    material = await session.get(CatalogoMaterial, id_lista)
    if material is None or not material.is_active:
        return False
    material.is_active = False
    await session.flush()
    return True
