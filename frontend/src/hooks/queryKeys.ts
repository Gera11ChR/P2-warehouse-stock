import type { QueryClient } from '@tanstack/react-query'
import type { FibraModulo, ReporteParams, TipoMovimiento } from '../types'
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
// preexistentes (['stock', id], ['fibra', modulo], ['equipo', id],
// ['movimientos'], ['secciones'], ['auditoria']) se conservan.
// ============================================================================

export const queryKeys = {
  /** Lista de seguimientos de un equipo (+ detalle anidado bajo el prefijo). */
  seguimientos: (equipoId: number | null) =>
    ['seguimientos', equipoId] as const,
  seguimiento: (equipoId: number | null, seguimientoId: number | null) =>
    ['seguimientos', equipoId, 'detalle', seguimientoId] as const,
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

/** Seguimientos del equipo (lista y detalles) + su inventario. */
export function invalidarSeguimientoEquipo(
  queryClient: QueryClient,
  equipoId: number,
): Promise<void> {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: queryKeys.seguimientos(equipoId) }),
    queryClient.invalidateQueries({ queryKey: queryKeys.equipo(equipoId) }),
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

/** Auditoría (ledger): toda operación de stock agrega eventos. */
export function invalidarAuditoria(queryClient: QueryClient): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: ['auditoria'] })
}

/** Inventarios afectados por una operación rápida (+Cantidad / Mover):
 *  GENERAL → ['stock'] (cualquier sección GENERAL); FO → ['fibra', módulo].
 *  Se deduplican; origen Y destino se recargan. */
export function invalidarInventariosRapidos(
  queryClient: QueryClient,
  extremos: {
    inventario: SumarCantidadPayload['destino']
    modulo?: FibraModulo
  }[],
): Promise<void> {
  const claves = new Map<string, readonly unknown[]>()
  for (const { inventario, modulo } of extremos) {
    if (inventario === 'GENERAL') {
      claves.set('stock', ['stock'])
    } else if (modulo !== undefined) {
      claves.set(`fibra:${modulo}`, ['fibra', modulo])
    } else {
      claves.set('fibra', ['fibra'])
    }
  }
  return Promise.all([
    ...[...claves.values()].map((queryKey) =>
      queryClient.invalidateQueries({ queryKey }),
    ),
    invalidarAuditoria(queryClient),
  ]).then(() => undefined)
}

export function invalidarTrasSumar(
  queryClient: QueryClient,
  payload: SumarCantidadPayload,
): Promise<void> {
  return invalidarInventariosRapidos(queryClient, [
    { inventario: payload.destino, modulo: payload.modulo },
  ])
}

export function invalidarTrasMover(
  queryClient: QueryClient,
  payload: MoverMaterialPayload,
): Promise<void> {
  return invalidarInventariosRapidos(queryClient, [
    { inventario: payload.origen, modulo: payload.origen_modulo },
    { inventario: payload.destino, modulo: payload.destino_modulo },
  ])
}

/** Tras una confirmación (procesar) de un movimiento: movimientos, secciones,
 *  stocks (General y FO), inventario de equipos y auditoría; si es TEAMS, las
 *  actas de Entrega (el trigger de PostgreSQL ya la registró en la misma
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
  ]
  // Sin tipo conocido (p. ej. borrador procesado desde el historial antes de
  // cargar la lista) se recarga por precaución: invalidar es barato y un acta
  // obsoleta no.
  if (tipo === 'TEAMS' || tipo === null) {
    trabajos.push(invalidarActas(queryClient, 'entrega'))
  }
  return Promise.all(trabajos).then(() => undefined)
}
