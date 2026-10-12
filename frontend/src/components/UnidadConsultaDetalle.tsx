import type { Equipo } from '../types'
import type { ConsultaVista } from '../utils/consultaUnidad'

// ============================================================================
// DETALLE DE CONSULTA DE UNIDAD — presentacional, solo lectura.
// REQ-UNI-012/013: Descripción (campo opcional: vacío si no existe) e
// Integrantes de la unidad, tomados de la entidad `Equipo` ya cargada
// (GET /equipos). Sin peticiones propias ni escrituras (REQ-UNI-016).
// ============================================================================

interface Props {
  vista: Exclude<ConsultaVista, 'inventario'>
  unidad: Equipo | undefined
}

export default function UnidadConsultaDetalle({ vista, unidad }: Props) {
  if (vista === 'descripcion') {
    const texto = unidad?.descripcion?.trim() ?? ''
    return (
      <section
        aria-label="Descripción de la unidad"
        className="rounded-lg border border-slate-200 bg-white p-4"
      >
        <h3 className="text-sm font-medium text-slate-700">Descripción</h3>
        <p
          data-testid="unidad-descripcion"
          className="mt-2 min-h-6 whitespace-pre-wrap text-sm text-slate-800"
        >
          {texto}
        </p>
      </section>
    )
  }

  const integrantes = unidad?.integrantes ?? []
  return (
    <section
      aria-label="Integrantes de la unidad"
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-slate-700">Integrantes</h3>
        <span className="text-xs text-slate-500">
          Cantidad: {integrantes.length}
        </span>
      </div>
      <ul data-testid="unidad-integrantes" className="mt-2 space-y-1">
        {integrantes.map((nombre) => (
          <li
            key={nombre}
            className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-800"
          >
            {nombre}
          </li>
        ))}
      </ul>
    </section>
  )
}
