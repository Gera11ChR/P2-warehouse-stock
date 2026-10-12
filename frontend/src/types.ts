// ============================================================================
// CATÁLOGO Y MATERIALES (contrato real /api/v1/catalogo)
// ============================================================================

export interface Categoria {
  id: number
  nombre: string
  is_active: boolean
}

/** Unidad de medida del catálogo (contrato real /api/v1/catalogo/um). */
export interface Ums {
  id: number
  nombre: string
  is_active: boolean
}

export interface Material {
  id_lista: number
  codigo: string | null
  descripcion: string
  categoria_id: number | null
  categoria: string | null
  u_m: string | null
  stock_minimo: number | null
  is_active: boolean
}

/**
 * Respuesta de GET /api/v1/catalogo (contrato real MaterialListOut).
 * `start_index` es el ordinal 1-indexed de la primera fila del rango
 * (REQ-API-006) devuelto por el backend.
 */
export interface MaterialList {
  start_index: number
  materiales: Material[]
}

// ============================================================================
// INVENTARIO Y SECCIONES (contrato real /api/v1/inventario)
// ============================================================================

export interface Seccion {
  almacen_id: number
  nombre: string
  tipo: string
  is_active: boolean
}

/**
 * Sección candidata a transferencias (contrato real
 * GET /api/v1/inventario/secciones/transferibles). `transferible=false`
 * la excluye como extremo en la UI; la autoridad de la validación sigue
 * siendo el backend.
 */
export interface SeccionTransferible {
  almacen_id: number
  nombre: string
  tipo: 'GENERAL' | 'FO_PAQUETE' | 'FO_EN_USO'
  transferible: boolean
}

export interface SeccionStockRow {
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  stock_actual: number
  alerta_stock: boolean
}

/** Fila de inventario con contexto de sección para la UI */
export interface InventoryRow extends SeccionStockRow {
  almacen_id: number
  almacen: string
}

// ============================================================================
// EQUIPOS (FASE 2 — contrato real /api/v1/equipos)
// ============================================================================

export interface Equipo {
  equipo_id: number
  nombre: string
  descripcion: string | null
  is_active: boolean
  integrantes: string[]
}

/**
 * Fila del inventario AUTÓNOMO del equipo (contrato real
 * GET /api/v1/equipos/{equipo_id}/inventario, InventarioEquipoOut;
 * REQ-DOMAIN-001/002). Reemplaza al modelo sparse deprecado
 * (vw_inventario_equipo_completo, CatalogoEquipoRow): SOLO filas físicas
 * con stock real originado en movimientos TEAMS/DEVOL auditados
 * (cero fantasmas de stock 0). `ultimo_movimiento_id` traza el movimiento
 * de origen. Equipo nuevo → [] (200); 404 solo si el equipo no existe.
 *
 * FASE 7 (configuración local): `*_local` son los valores definidos para
 * ESTE equipo (PATCH /equipos/{equipo_id}/inventario/{material_id}); los
 * `*_efectivo` son el valor RESUELTO por el backend (local si existe,
 * heredado del catálogo en caso contrario). La resolución efectiva es
 * autoridad del backend: el frontend solo la refleja.
 */
export interface InventarioEquipoRow {
  equipo_id: number
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  stock_actual: number
  alerta_stock: boolean
  ultimo_movimiento_id: number | null
  stock_minimo_local: number | null
  categoria_local_id: number | null
  um_local_id: number | null
  stock_minimo_efectivo: number | null
  categoria_efectiva: string | null
  um_efectivo: string | null
}

// ============================================================================
// CONFIGURACIÓN LOCAL DEL INVENTARIO DE EQUIPO
// (contrato real PATCH /api/v1/equipos/{equipo_id}/inventario/{material_id})
// ============================================================================

/**
 * Payload del PATCH de configuración local. Al menos UNO de los tres
 * campos (422 si viene vacío). Un campo omitido conserva su valor previo;
 * enviar `null` para un campo numérico NO es parte del contrato (se usan
 * campos omitidos). La resolución de efectivos (`*_efectivo`) es backend.
 */
export interface EquipoConfigLocalPayload {
  stock_minimo_local?: number
  categoria_local_id?: number
  um_local_id?: number
}

/** Eco del PATCH de configuración local (EquipoConfigLocalOut). */
export interface EquipoConfigLocal {
  equipo_id: number
  material_id: number
  stock_minimo_local: number | null
  categoria_local_id: number | null
  um_local_id: number | null
  updated_at: string
}

// ============================================================================
// SEGUIMIENTOS DE CONSUMO DE EQUIPO (contrato certificado
// /api/v1/equipos/{equipo_id}/seguimientos; openspec.yaml)
// ============================================================================

export type EstadoSeguimiento = 'ABIERTA' | 'CERRADA'

/** Línea de un seguimiento. `cantidad_consumida` la registra el backend al
 *  cierre (NULL mientras está ABIERTA); NUNCA el frontend. */
export interface SeguimientoItem {
  id: number
  material_id: number
  cantidad_tomada: number
  cantidad_consumida: number | null
}

/**
 * Seguimiento (SeguimientoOut: crear/cerrar/detalle). Ciclo de vida
 * ABIERTA → CERRADA: el backend garantiza a lo sumo UNO abierto por equipo.
 */
export interface Seguimiento {
  id: number
  equipo_id: number
  fecha: string
  observaciones: string | null
  usuario: string
  estado: EstadoSeguimiento
  created_at: string
  updated_at: string
  closed_at: string | null
  items: SeguimientoItem[]
}

/** Respuesta de GET /equipos/{equipo_id}/seguimientos (SeguimientoListOut). */
export interface SeguimientoList {
  seguimientos: Seguimiento[]
}

/** POST /equipos/{equipo_id}/seguimientos — apertura (201). */
export interface SeguimientoCreatePayload {
  observaciones?: string
  items: { material_id: number; cantidad_tomada: number }[]
}

/** POST /equipos/{equipo_id}/seguimientos/{seguimiento_id}/cerrar. */
export interface CerrarSeguimientoPayload {
  consumidos: { material_id: number; cantidad_consumida: number }[]
  observaciones_cierre?: string
}

/** POST .../{seguimiento_id}/agregar-todo — body OPCIONAL (AgregarTodoRequest). */
export interface AgregarTodoPayload {
  /** 1..100 caracteres; un reenvío con la misma clave devuelve el resultado
   *  original sin duplicar efectos. */
  clave_idempotencia?: string
}

/** Respuesta de agregar-todo (AgregarTodoOut). `lineas_agregadas` lo calcula
 *  la función SQL (0 en un reenvío idempotente). */
export interface AgregarTodoResultadoOut {
  lineas_agregadas: number
  seguimiento: Seguimiento
}

// ============================================================================
// OPERADORES RÁPIDOS DE INVENTARIO (contrato certificado
// POST /api/v1/inventario/sumar-cantidad y /inventario/mover).
// Los payloads (SumarCantidadPayload / MoverMaterialPayload) viven en
// utils/operadorPayload.ts junto a sus constructores puros.
// El stock resultante lo devuelve el SERVIDOR: el cliente nunca lo calcula.
// ============================================================================

export type InventarioContratoOut = 'GENERAL' | 'FO'
export type ModuloFoOut = 'PAQUETE' | 'EN_USO'

/** Respuesta de POST /inventario/sumar-cantidad (SumarCantidadOut). */
export interface SumarCantidadOut {
  destino: InventarioContratoOut
  modulo: ModuloFoOut | null
  material_id: number
  stock_nuevo: number
  reenvio_idempotente: boolean
}

/** Respuesta de POST /inventario/mover (MoverMaterialOut). */
export interface MoverMaterialOut {
  material_id: number
  origen: InventarioContratoOut
  origen_modulo: ModuloFoOut | null
  destino: InventarioContratoOut
  destino_modulo: ModuloFoOut | null
  stock_origen: number
  stock_destino: number
  reenvio_idempotente: boolean
}

// ============================================================================
// ACTAS DE ENTREGA / CONSUMO (contrato certificado ActaOut de
// /api/v1/reportes/entrega y /api/v1/reportes/consumo, formato=json).
// Los números (incl. `cantidad_consumida`) los calcula PostgreSQL; el
// frontend solo los muestra, sin agregar ni recalcular.
// ============================================================================

export type ActaTipo = 'ENTREGA' | 'CONSUMO'

export interface ActaItem {
  material_id: number
  codigo: string | null
  descripcion: string
  categoria: string | null
  u_m: string | null
  /** ENTREGA: cantidad entregada al equipo. */
  cantidad: number | null
  /** CONSUMO: tomada / consumida. */
  cantidad_tomada: number | null
  cantidad_consumida: number | null
}

export interface Acta {
  acta_id: number
  tipo: ActaTipo
  movimiento_id: number | null
  seguimiento_id: number | null
  equipo_id: number | null
  equipo_nombre: string | null
  usuario: string | null
  observaciones: string | null
  fecha: string
  items: ActaItem[]
}

/** Respuesta JSON de GET /reportes/entrega|consumo (ActaListOut). */
export interface ActaList {
  actas: Acta[]
}

/** Filtros de GET /reportes/entrega|consumo (todos opcionales). El parámetro
 *  `formato` lo fija el servicio (json | normal | extenso). */
export interface ReporteParams {
  equipo_id?: number
  desde?: string
  hasta?: string
  /** Exporta/consulta un acta individual. */
  acta_id?: number
}

/** Formatos XLSX descargables (plantillas corporativas Normal / Extenso). */
export type FormatoXlsx = 'normal' | 'extenso'

// ============================================================================
// FIBRA ÓPTICA — inventarios independientes PAQUETE / EN_USO
// (contrato real /api/v1/fibra; REQ-DOMAIN-003/004/005)
// ============================================================================

export type FibraModulo = 'PAQUETE' | 'EN_USO'

/** Fila de stock FO con esquema estándar (CÓDIGO, DESCRIPCIÓN, U.M.,
 *  STOCK ACTUAL, STOCK MÍNIMO, ALERTA STOCK). La métrica la gobierna `u_m`
 *  (el legado carretes/metros de fiber_variants está deprecado). */
export interface FibraStockRow {
  modulo: FibraModulo
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  stock_actual: number
  alerta_stock: boolean
}

/** POST /api/v1/fibra/carga-inicial — alta única e idempotente.
 *  `cantidad` >= 0; `motivo` opcional. */
export interface FibraCargaInicialPayload {
  modulo: FibraModulo
  material_id: number
  cantidad: number
  motivo?: string
}

/** POST /api/v1/fibra/ajuste — ajuste administrativo.
 *  `nuevo_stock` >= 0; `motivo` OPCIONAL (ergonomía `justificacion_opcional`). */
export interface FibraAjustePayload {
  modulo: FibraModulo
  material_id: number
  nuevo_stock: number
  motivo?: string | null
}

/** Eco mínimo de una operación FO (FibraOperacionOut). */
export interface FibraOperacionOut {
  modulo: FibraModulo
  material_id: number
}

/**
 * PATCH /api/v1/fibra/{modulo}/materiales/{material_id} — edición FO
 * (REQ-CATFO-001/002, REQ-STOCK-001/002/003). Espejo de
 * `FibraMaterialUpdateRequest` del backend: `stock_actual` SOLO si el
 * operador cambió el valor registrado. Ergonomía `justificacion_opcional`
 * (REQ-ERG-004): `motivo` es OPCIONAL — vacío se envía como `null`. El
 * frontend NUNCA envía el diferencial: el delta, el bloqueo FOR UPDATE y la
 * auditoría 'AJUSTE_INVENTARIO_FO' los calcula PostgreSQL.
 */
export interface FibraMaterialUpdatePayload {
  descripcion?: string | null
  codigo?: string | null
  categoria_id?: number | null
  nueva_categoria?: string | null
  u_m?: string | null
  stock_minimo?: number | null
  stock_actual?: number
  motivo?: string | null
}

/**
 * Respuesta del PATCH FO (FibraMaterialOut): material materializado tras
 * la edición — join catálogo maestro + `inventario_fibra` con esquema
 * estándar + categoría resuelta.
 */
export interface FibraMaterialOut {
  modulo: FibraModulo
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  stock_actual: number
  alerta_stock: boolean
  categoria: string | null
  categoria_id: number | null
}

/**
 * Fila editable inicial del FibraMaterialForm (REQ-CATFO-001): campos de
 * catálogo de la fila FO seleccionada + categoría resuelta con el join de
 * presentación `['catalogo']` (patrón SeccionGeneral).
 */
export interface FibraMaterialRowEditable {
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_minimo: number | null
  categoria_id: number | null
  categoria: string | null
}

// ============================================================================
// KPIs (sin endpoint /kpis — agregación visual en FASE 1)
// ============================================================================

export interface Kpis {
  total_materiales: number
  stock_total: number
  alertas_stock: number
  transferencias_hoy: number
}

// ============================================================================
// MOVIMIENTOS (FASE 3 — contrato real /api/v1/movimientos)
// ============================================================================

export type TipoMovimiento = 'TEAMS' | 'DEVOL'
export type EstadoMovimiento = 'BORRADOR' | 'CONFIRMADO' | 'CANCELADO'

export interface DetalleMovimiento {
  material_id: number
  cantidad: number
  /** TEAMS multi-origen: sección de origen de la línea (General o FO). La
   *  cabecera trae el origen común o null si el carrito es mixto. */
  origen_almacen_id?: number | null
}

export interface Movimiento {
  id: number
  tipo_movimiento: TipoMovimiento
  estado: EstadoMovimiento
  usuario: string
  origen_almacen_id: number | null
  destino_almacen_id: number | null
  origen_equipo_id: number | null
  destino_equipo_id: number | null
  observaciones: string | null
  detalle: DetalleMovimiento[]
}

export const ESTADOS_MOVIMIENTO: Record<EstadoMovimiento, string> = {
  BORRADOR: 'Borrador',
  CONFIRMADO: 'Confirmado',
  CANCELADO: 'Cancelado',
}

/** Texto VISIBLE de cada tipo de movimiento (nomenclatura oficial). El valor
 *  técnico del contrato (`TEAMS` | `DEVOL`) NO cambia: solo se rotula. */
export const TIPOS_MOVIMIENTO: Record<TipoMovimiento, string> = {
  TEAMS: 'TRANSF',
  DEVOL: 'DEVOL',
}

/** Única fuente del texto visible de un tipo de movimiento. */
export function etiquetaTipoMovimiento(tipo: TipoMovimiento): string {
  return TIPOS_MOVIMIENTO[tipo]
}

/** Línea de carrito temporal (UX). cantidad_transferir/cantidad_devolver
 *  son campos SOLO del carrito; el payload real usa material_id + cantidad. */
export interface CartLine {
  material_id: number
  codigo: string | null
  descripcion: string
  u_m: string | null
  stock_disponible: number
  /** TEAMS: sección desde la que se agregó la línea (su origen real). */
  origen_almacen_id?: number | null
  cantidad_transferir?: number
  cantidad_devolver?: number
}

// ============================================================================
// AUDITORÍA (contrato real /api/v1/auditoria)
// ============================================================================

export interface EventoAuditoria {
  id: number
  usuario: string | null
  tipo_accion: string
  material_id: number | null
  equipo_origen_id: number | null
  equipo_destino_id: number | null
  almacen_origen_id: number | null
  almacen_destino_id: number | null
  cantidad: number | null
  resultado: string | null
  detalles: Record<string, unknown> | null
  created_at: string
  /** LEFT JOIN al catálogo SIN filtro is_active (REQ-API-008):
   *  el historial queda íntegro aunque el material esté inactivo. */
  descripcion: string | null
  codigo: string | null
  categoria: string | null
  estado_activo: boolean | null
}

export const TIPOS_ACCION_AUDITORIA: Record<string, string> = {
  MATERIAL_MODIFICADO: 'Material modificado',
  TEAMS_TRANSFERENCIA: 'TRANSF — transferencia',
  DEVOL_DEVOLUCION: 'DEVOL — devolución',
  MOVIMIENTO_CANCELADO: 'Movimiento cancelado',
  STOCK_INICIAL: 'Carga inicial de stock',
  AJUSTE_INVENTARIO: 'Ajuste de inventario',
  STOCK_INICIAL_FO: 'Carga inicial FO',
  AJUSTE_INVENTARIO_FO: 'Ajuste de inventario FO',
  MIGRACION_FO: 'Migración FO',
  ELIMINACION_FO: 'Eliminación de inventario FO',
  // Cambio 2026-10-01-reportes-consumo-management (REQ-P2-INV-006 / CON-001).
  SUMA_CANTIDAD: '+Cantidad — suma directa',
  MOVIMIENTO_INVENTARIO: 'Mover — movimiento entre inventarios',
  AGREGAR_TODO: 'Seguimiento — agregar todo',
  SEGUIMIENTO_CREADO: 'Seguimiento creado',
  SEGUIMIENTO_CERRADO: 'Seguimiento cerrado',
  ACTA_ENTREGA_GENERADA: 'Acta de Entrega generada',
  ACTA_CONSUMO_GENERADA: 'Acta de Consumo generada',
  // Eventos HISTÓRICOS del flujo anterior. El ledger es inmutable (no se
  // actualizan filas): el mapeo se hace SOLO en lectura para que la UI no
  // muestre la nomenclatura legacy (REQ-P2-CON-001).
  DESPLIEGUE_CREADO: 'Seguimiento creado (histórico)',
  DESPLIEGUE_CERRADO: 'Seguimiento cerrado (histórico)',
}

// ============================================================================
// CONSTANTES DEL DOMINIO
// ============================================================================

/** Unidades de medida soportadas (FASE 1 — coincide con backend SUPPORTED_UNITS) */
export const UNIDADES = [
  'PZ',
  'LT',
  'CARRETE (1 KM)',
  'METRO (M)',
  'CARRETE (5 KM)',
  'BOLSA (500 PZ)',
  'PAQUETE (100 PZ)',
  'ROLLO',
  'EQUIPO',
  'UNIDAD',
] as const

// ============================================================================
// NAVEGACIÓN (UI)
// ============================================================================

export interface NavigationTarget {
  page: string
  sub?: string
  /** Pre-filtro opcional por equipo al abrir Reportes (evita exportar actas
   *  de otro equipo por accidente tras una entrega/cierre). */
  equipoId?: number
}
