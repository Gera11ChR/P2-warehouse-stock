import { useMemo } from 'react'
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import {
  crearReferencia,
  eliminarReferencia,
  listarReferencia,
  modificarReferencia,
} from '../services/referencia'
import { listFibraStock } from '../services/fibra'
import { listSecciones, stockSeccion } from '../services/inventory'
import type {
  ReferenciaCreatePayload,
  ReferenciaUpdatePayload,
} from '../types'
import { mensajeErrorApi } from '../utils/errorMensaje'
import { queryKeys } from './queryKeys'
import { useToast } from './useToasts'

// ============================================================================
// REFERENCIA DE MATERIALES POR UNIDAD — capa de estado (T8, @state-agent)
// Contrato CONGELADO en T7 (openapi.snapshot.json; paquete
// 2026-10-referencia-materiales-unidades). Ver services/referencia.ts.
//
// Reglas de esta capa (REQ-REF-005/013/014/017):
//  - FAIL-CLOSED: un error de lectura o de origen se expone tal cual
//    (isError/error); NUNCA se reinterpreta como Referencia vacía, origen
//    vacío ni stock 0 (C-10).
//  - Sin agregación ni recálculo en el cliente: el frontend refleja lo que
//    devuelve el backend; el stock de las opciones se copia TAL CUAL de la
//    fila (nunca se suma, nunca se deduce; Q5/P-8).
//  - Invalidación ACOTADA (REQ-REF-017): tras una mutación exitosa SOLO se
//    invalida `queryKeys.referencia(equipoId)`. Jamás inventarios, catálogo,
//    reportes, actividades ni auditoría.
//  - Conservar la entrada ante rechazo: estos hooks NO resetean ningún
//    estado local (el formulario es de T9); ante un error la mutación queda
//    fallida y expone el error crudo.
// ============================================================================

/**
 * GET /equipos/{equipoId}/referencia — líneas de la Unidad (REQ-REF-005).
 *
 * `enabled` guard: no dispara hasta que haya Unidad seleccionada.
 * FAIL-CLOSED: 403/404/422 se exponen tal cual (isError/error); un error
 * NUNCA se reinterpreta como Referencia vacía. Sin agregar ni recalcular
 * nada: el orden, la U.M. efectiva y el `total` los decide el backend.
 */
export function useReferencia(equipoId: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.referencia(equipoId),
    queryFn: () => listarReferencia(equipoId),
    enabled,
  })
}

/**
 * POST /equipos/{equipoId}/referencia — alta masiva todo-o-nada (201).
 *
 * Tras el éxito: toast y recarga SOLO de la Referencia de la Unidad
 * (REQ-REF-017: ninguna otra clave se invalida). Ante un rechazo se muestra
 * el error canónico (`mensajeErrorApi`) y NO se toca ningún estado del
 * formulario (la entrada se conserva; T9).
 *
 * El error crudo queda expuesto en `error` (patrón error-agnostic del repo)
 * para que la UI distinga los casos de negocio con `extraerRespuestaError`
 * de `utils/operadorErrores` (`{status, cuerpo}` → `cuerpo.error.code`):
 *  - 409 `REFERENCIA_DUPLICADA`   → el material ya está en la Referencia
 *  - 404 `MATERIAL_NO_ENCONTRADO` → material inexistente o inactivo
 */
export function useCrearReferencia(equipoId: number) {
  const queryClient = useQueryClient()
  const { pushToast, pushError } = useToast()
  return useMutation({
    mutationFn: (payload: ReferenciaCreatePayload) =>
      crearReferencia(equipoId, payload),
    onSuccess: () => {
      pushToast('Materiales agregados a la Referencia de la Unidad')
      return queryClient.invalidateQueries({
        queryKey: queryKeys.referencia(equipoId),
      })
    },
    onError: (error) =>
      pushError(
        mensajeErrorApi(error, 'No se pudo agregar a la Referencia de la Unidad'),
      ),
  })
}

/**
 * PATCH /equipos/{equipoId}/referencia/{materialId} — cambia SOLO la
 * Cantidad Semanal (200). Tras el éxito: toast y recarga SOLO de la
 * Referencia de la Unidad (REQ-REF-017). Ante un rechazo el error se
 * muestra y se expone crudo en `error`; con `extraerRespuestaError`
 * la UI distingue `404 REFERENCIA_NO_ENCONTRADA` (la línea ya no existe:
 * corresponde refrescar la tabla; REQ-REF-014). No se resetea nada aquí.
 */
export function useModificarReferencia(equipoId: number) {
  const queryClient = useQueryClient()
  const { pushToast, pushError } = useToast()
  return useMutation({
    mutationFn: ({
      materialId,
      payload,
    }: {
      materialId: number
      payload: ReferenciaUpdatePayload
    }) => modificarReferencia(equipoId, materialId, payload),
    onSuccess: () => {
      pushToast('Cantidad Semanal actualizada en la Referencia de la Unidad')
      return queryClient.invalidateQueries({
        queryKey: queryKeys.referencia(equipoId),
      })
    },
    onError: (error) =>
      pushError(
        mensajeErrorApi(
          error,
          'No se pudo modificar la línea de la Referencia de la Unidad',
        ),
      ),
  })
}

/**
 * DELETE /equipos/{equipoId}/referencia/{materialId} — borrado físico de la
 * línea (204). Tras el éxito: toast y recarga SOLO de la Referencia de la
 * Unidad (REQ-REF-017). Ante un rechazo el error se muestra y se expone
 * crudo en `error`; con `extraerRespuestaError` la UI distingue
 * `404 REFERENCIA_NO_ENCONTRADA` (la línea ya no existe: corresponde
 * refrescar la tabla; REQ-REF-014). No se resetea nada aquí.
 */
export function useEliminarReferencia(equipoId: number) {
  const queryClient = useQueryClient()
  const { pushToast, pushError } = useToast()
  return useMutation({
    mutationFn: (materialId: number) => eliminarReferencia(equipoId, materialId),
    onSuccess: () => {
      pushToast('Línea eliminada de la Referencia de la Unidad')
      return queryClient.invalidateQueries({
        queryKey: queryKeys.referencia(equipoId),
      })
    },
    onError: (error) =>
      pushError(
        mensajeErrorApi(
          error,
          'No se pudo eliminar la línea de la Referencia de la Unidad',
        ),
      ),
  })
}

// ============================================================================
// ORIGEN DEL SELECTOR DEPENDIENTE (P-8 / Q5) — SOLO LECTURA
//
// «Inventario General» = secciones GENERAL ACTIVAS (listSecciones) + su
// stock por sección (stockSeccion, UNA petición por sección). Un material
// presente en varias secciones aparece como UNA OPCIÓN POR SECCIÓN
// (sufijo de sección en la UI, todas mapean al mismo `material_id`): NO se
// suma stock ni se deduplica en el cliente (Q5).
//
// «Inventario FO» = listFibraStock (inventario único por material).
//
// FAIL-CLOSED (C-10): si una carga falla, el error se expone con reintento
// manual; NUNCA se presenta un origen vacío ni stock 0 como válidos.
//
// Las claves reutilizan las existentes (['secciones'], ['stock', id],
// ['fibra']) para compartir caché con las pantallas de inventario. Los
// hooks de Referencia NO invalidan estas claves (REQ-REF-017).
// ============================================================================

/** Opción del origen «Inventario General»: una por (sección GENERAL activa,
 *  material). El stock se copia TAL CUAL de la fila de la sección: ayuda
 *  visual de solo lectura, sin sumas ni deducciones en el cliente. */
export interface OpcionOrigenGeneral {
  origen: 'general'
  almacen_id: number
  nombre_seccion: string
  material_id: number
  descripcion: string
  u_m: string | null
  stock_actual: number
}

/** Opción del origen «Inventario FO»: una por fila física del Inventario FO.
 *  El stock se copia TAL CUAL de la fila (solo lectura). */
export interface OpcionOrigenFo {
  origen: 'fo'
  material_id: number
  descripcion: string
  u_m: string | null
  stock_actual: number
}

/** Estado fail-closed de un origen del selector dependiente: `options` solo
 *  se entrega cuando TODAS las consultas del origen terminaron sin error;
 *  mientras carga o ante un error es `undefined` (jamás `[]` como síntoma
 *  de error). `refetch` reintenta todas las consultas del origen. */
export interface EstadoOrigenOpciones<T> {
  options: T[] | undefined
  isLoading: boolean
  isError: boolean
  error: unknown
  refetch: () => void
}

/**
 * Opciones de SOLO LECTURA del selector dependiente del formulario de alta
 * (REQ-REF-013): «Inventario General» (una opción por sección GENERAL
 * activa, sin sumar stock ni deduplicar) y «Inventario FO» (una opción por
 * fila). Fail-closed en ambos orígenes (C-10).
 *
 * `enabled` guard: no dispara hasta que el formulario esté abierto.
 */
export function useOpcionesOrigenReferencia(enabled = true): {
  general: EstadoOrigenOpciones<OpcionOrigenGeneral>
  fo: EstadoOrigenOpciones<OpcionOrigenFo>
} {
  const seccionesQuery = useQuery({
    queryKey: ['secciones'],
    queryFn: listSecciones,
    enabled,
  })

  // Secciones GENERAL activas: únicas candidatas del origen «Inventario
  // General» (P-8).
  const seccionesGenerales = useMemo(
    () =>
      (seccionesQuery.data ?? []).filter(
        (seccion) => seccion.tipo === 'GENERAL' && seccion.is_active,
      ),
    [seccionesQuery.data],
  )

  // Una petición de stock POR SECCIÓN (P-8). Misma clave ['stock', id] que
  // la pantalla de Inventario General (caché compartida).
  const stocksGenerales = useQueries({
    queries: seccionesGenerales.map((seccion) => ({
      queryKey: ['stock', seccion.almacen_id],
      queryFn: () => stockSeccion(seccion.almacen_id),
      enabled,
    })),
  })

  const opcionesGenerales = useMemo<OpcionOrigenGeneral[] | undefined>(() => {
    // Fail-closed: si falló secciones o CUALQUIER consulta de stock no hay
    // opciones; jamás se presenta un origen vacío ante un error (C-10).
    if (seccionesQuery.isError) return undefined
    if (
      stocksGenerales.some((resultado) => resultado.isError || !resultado.data)
    ) {
      return undefined
    }
    const opciones: OpcionOrigenGeneral[] = []
    seccionesGenerales.forEach((seccion, indice) => {
      const filas = stocksGenerales[indice]?.data
      if (!filas) return
      for (const fila of filas) {
        // Una opción por sección (Q5): NO se suma stock ni se deduplica el
        // material; el stock se copia TAL CUAL de la fila.
        opciones.push({
          origen: 'general',
          almacen_id: seccion.almacen_id,
          nombre_seccion: seccion.nombre,
          material_id: fila.material_id,
          descripcion: fila.descripcion,
          u_m: fila.u_m,
          stock_actual: fila.stock_actual,
        })
      }
    })
    return opciones
  }, [seccionesGenerales, stocksGenerales, seccionesQuery.isError])

  const foQuery = useQuery({
    queryKey: ['fibra'],
    queryFn: listFibraStock,
    enabled,
  })

  const opcionesFo = useMemo<OpcionOrigenFo[] | undefined>(() => {
    // Fail-closed: pendiente o error → undefined; jamás `[]` por error.
    if (!foQuery.data) return undefined
    return foQuery.data.map((fila) => ({
      origen: 'fo' as const,
      material_id: fila.material_id,
      descripcion: fila.descripcion,
      u_m: fila.u_m,
      stock_actual: fila.stock_actual,
    }))
  }, [foQuery.data])

  return {
    general: {
      options: opcionesGenerales,
      isLoading:
        seccionesQuery.isPending ||
        stocksGenerales.some((resultado) => resultado.isPending),
      isError:
        seccionesQuery.isError ||
        stocksGenerales.some((resultado) => resultado.isError),
      error:
        seccionesQuery.error ??
        stocksGenerales.find((resultado) => resultado.isError)?.error ??
        null,
      refetch: () => {
        void seccionesQuery.refetch()
        for (const resultado of stocksGenerales) void resultado.refetch()
      },
    },
    fo: {
      options: opcionesFo,
      isLoading: foQuery.isPending,
      isError: foQuery.isError,
      error: foQuery.error,
      refetch: () => {
        void foQuery.refetch()
      },
    },
  }
}
