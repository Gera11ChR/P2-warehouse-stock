import type { QueryClient } from '@tanstack/react-query'
import type { ReporteParams, TipoMovimiento } from '../types'
import type { ReporteTipo } from '../utils/reporteExport'
import type {
  MoverMaterialPayload,
  SumarCantidadPayload,
} from '../utils/operadorPayload'

// ============================================================================
// CLAVES DE QUERY E INVALIDACIONES (capa de estado — State-Agent)
//
// Única fuente de las claves nuevas del cambio reportes-consumo-management y
// de las reglas de invalidación tras mutaciones. Regla:
//
//   Mutación → HTTP success → invalidateQueries() → GET del estado persistido
//   → React renderiza lo que devuelve el servidor.
//
// NUNCA se parchea el cache con stock calculado en el cliente. Las claves
// preexistentes (['stock', id], ['fibra'], ['equipo', id], ['movimientos'],
// ['secciones'], ['auditoria']) se conservan. `['fibra']` es el Inventario FO
// único (RF-1): ya no existe la clave por módulo.
//
// Valor Total (RF-4/RF-5): TODA mutación que cambie existencias o Valor
// Unitario invalida además ['inventario', 'resumen-general'] mediante
// `invalidarResumenGeneral`. React nunca calcula el total.
// ============================================================================

export const queryKeys = {
  /** Valor Total del inventario (GET /inventario/resumen-general). */
  resumenGeneral: () => ['inventario', 'resumen-general'] as const,
  /** Lista de seguimientos de un equipo (+ detalle anidado bajo el prefijo). */
  seguimientos: (equipoId: number | null) =>
    ['seguimientos', equipoId] as const,
  seguimiento: (equipoId: number | null, seguimientoId: number | null) =>
    ['seguimientos', equipoId, 'detalle', seguimientoId] as const,
  /** Actividad pendiente de la Unidad (GET .../actividades/pendiente). */
  actividadPendiente: (equipoId: number | null) =>
    ['actividades', equipoId, 'pendiente'] as const,
  /** Historial de actividades confirmadas de la Unidad (GET .../actividades). */
  actividades: (equipoId: number | null) =>
    ['actividades', equipoId] as const,
  /** Inventario autónomo del equipo (hook useEquipoInventario). */
  equipo: (equipoId: number | null) => ['equipo', equipoId] as const,
  /** Prefijo de TODAS las actas (Entrega y Consumo). */
  reportes: () => ['reportes'] as const,
  /** Prefijo de las actas de un tipo; con `params` es la clave del listado. */
  actas: (tipo: ReporteTipo, params?: ReporteParams) =>
    params === undefined
      ? (['reportes', 'actas', tipo] as const)
      : (['reportes', 'actas', tipo, params] as const),
}

/** Valor Total (RF-4/RF-5): recarga el estado persistido tras una mutación
 *  que cambió existencias o Valor Unitario. */
export function invalidarResumenGeneral(
  queryClient: QueryClient,
): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: queryKeys.resumenGeneral() })
}

/** Seguimientos del equipo (lista y detalles) + su inventario. Por regla de
 *  plan §4.1 toda mutación de seguimientos refresca además el Valor Total
 *  (el backend es quien decide si cambió). */
export function invalidarSeguimientoEquipo(
  queryClient: QueryClient,
  equipoId: number,
): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.seguimientos(equipoId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.equipo(equipoId) }),
    invalidarResumenGeneral(queryClient),
  ]).then(() => undefined)
}

/** Actas de un tipo (el listado de Reportes se recarga si está montado; si no,
 *  queda obsoleto y se refetcha al abrir la pantalla pese al staleTime). */
export function invalidarActas(
  queryClient: QueryClient,
  tipo: ReporteTipo,
): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: queryKeys.actas(tipo) })
}

/** Actividades de la Unidad: tras confirmar se recargan pendiente, historial
 *  y auditoría; React re-renderiza el estado PERSISTIDO (folio y fecha los
 *  asigna PostgreSQL). NUNCA se parchea el cache con datos del cliente. */
export function invalidarActividadesEquipo(
  queryClient: QueryClient,
  equipoId: number,
): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({
      queryKey: queryKeys.actividadPendiente(equipoId),
    }),
    queryClient.invalidateQueries({ queryKey: queryKeys.actividades(equipoId) }),
    invalidarAuditoria(queryClient),
  ]).then(() => undefined)
}

/** Auditoría (ledger): toda operación de stock agrega eventos. */
export function invalidarAuditoria(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: ['auditoria'] })
}

/** Inventarios afectados por una operación rápida (+Cantidad / Mover):
 *  GENERAL → ['stock'] (cualquier sección GENERAL); FO → ['fibra'] (único).
 *  Se deduplican; origen Y destino se recargan, además de auditoría y Valor
 *  Total. */
export function invalidarInventariosRapidos(
  queryClient: QueryClient,
  extremos: { inventario: SumarCantidadPayload['destino'] }[],
): Promise<void> {
  const claves = new Map<string, readonly unknown[]>()
  for (const { inventario } of extremos) {
    claves.set(inventario === 'GENERAL' ? 'stock' : 'fibra', [
      inventario === 'GENERAL' ? 'stock' : 'fibra',
    ])
  }
  return Promise.all([
    ...[...claves.values()].map((queryKey) =>
      queryClient.invalidateQueries({ queryKey }),
    ),
    invalidarAuditoria(queryClient),
    invalidarResumenGeneral(queryClient),
  ]).then(() => undefined)
}

export function invalidarTrasSumar(
  queryClient: QueryClient,
  payload: SumarCantidadPayload,
): Promise<void> {
  return invalidarInventariosRapidos(queryClient, [
    { inventario: payload.destino },
  ])
}

export function invalidarTrasMover(
  queryClient: QueryClient,
  payload: MoverMaterialPayload,
): Promise<void> {
  return invalidarInventariosRapidos(queryClient, [
    { inventario: payload.origen },
    { inventario: payload.destino },
  ])
}

/** Tras una confirmación (procesar) de un movimiento: movimientos, secciones,
 *  stocks (General y FO), inventario de equipos, auditoría y Valor Total; si
 *  es TEAMS, las actas de Entrega (el trigger de PostgreSQL ya la registró en la misma
 *  transacción: aquí solo se recarga lo persistido). */
export function invalidarTrasConfirmarMovimiento(
  queryClient: QueryClient,
  tipo: TipoMovimiento | null,
): Promise<void> {
  const trabajos: Promise<void>[] = [
    queryClient.invalidateQueries({ queryKey: ['movimientos'] }),
    queryClient.invalidateQueries({ queryKey: ['secciones'] }),
    queryClient.invalidateQueries({ queryKey: ['stock'] }),
    queryClient.invalidateQueries({ queryKey: ['fibra'] }),
    queryClient.invalidateQueries({ queryKey: ['equipo'] }),
    invalidarAuditoria(queryClient),
    invalidarResumenGeneral(queryClient),
  ]
  // Sin tipo conocido (p. ej. borrador procesado desde el historial antes de
  // cargar la lista) se recarga por precaución: invalidar es barato y un acta
  // obsoleta no.
  if (tipo === 'TEAMS' || tipo === null) {
    trabajos.push(invalidarActas(queryClient, 'entrega'))
  }
  return Promise.all(trabajos).then(() => undefined)
}
