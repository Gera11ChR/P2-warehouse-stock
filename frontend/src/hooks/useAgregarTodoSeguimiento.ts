import { useMutation, useQueryClient } from '@tanstack/react-query'
import { agregarTodoSeguimiento } from '../services/seguimientos'
import { invalidarAuditoria, invalidarSeguimientoEquipo } from './queryKeys'

/**
 * POST /equipos/{equipoId}/seguimientos/{seguimientoId}/agregar-todo
 * (REQ-P2-CON-003). Variables: `{ seguimientoId, claveIdempotencia? }`.
 *
 * NO está montado en ninguna pantalla: no existe UI para editar un
 * seguimiento ABIERTO (la precarga de «Agregar todo» en
 * SeguimientoNuevaListaForm es LOCAL, decisión UX T4.2). Disponible para
 * cuando se añada esa edición. Quien lo use debe generar la clave con
 * `generarClaveIdempotencia` UNA vez por intento y reutilizarla al reintentar.
 *
 * Tras success se invalidan seguimientos del equipo (las líneas nuevas las
 * decide fn_agregar_todo_seguimiento: el cliente no las calcula), inventario
 * del equipo y auditoría (evento AGREGAR_TODO). Errores: error-agnostic
 * (404 no pertenece al equipo, 409 no está ABIERTA).
 */
export function useAgregarTodoSeguimiento(equipoId: number) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      seguimientoId,
      claveIdempotencia,
    }: {
      seguimientoId: number
      claveIdempotencia?: string
    }) => agregarTodoSeguimiento(equipoId, seguimientoId, claveIdempotencia),
    onSuccess: () =>
      Promise.all([
        invalidarSeguimientoEquipo(queryClient, equipoId),
        invalidarAuditoria(queryClient),
      ]),
  })
}
