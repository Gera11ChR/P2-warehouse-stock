// Opciones del select de Consulta de Unidad (REQ-UNI-010).
export type ConsultaVista = 'inventario' | 'descripcion' | 'integrantes'

export const CONSULTA_OPCIONES: ReadonlyArray<{
  value: ConsultaVista
  label: string
}> = [
  { value: 'inventario', label: 'Inventario Unidad' },
  { value: 'descripcion', label: 'Descripción' },
  { value: 'integrantes', label: 'Integrantes' },
]
