import { useState } from 'react'
import type { FormEvent } from 'react'
import { configLocalSchema } from '../schemas/configLocal'
import type {
  Categoria,
  EquipoConfigLocalPayload,
  InventarioEquipoRow,
  Ums,
} from '../types'

// ============================================================================
// FORMULARIO — CONFIGURACIÓN LOCAL DEL INVENTARIO DE EQUIPO (FASE 7)
//
// Captura SOLO la intención del usuario: el payload se valida con
// `configLocalSchema` (feedback UX) y el backend sigue siendo la autoridad
// del contrato (422 si el payload llega vacío). Los campos no editados se
// OMITEN del payload (nunca se envían null numéricos — contrato PATCH).
// El bloque de código/descripción/stock actual es SOLO LECTURA
// (REQ-TEAM-001/002): el inventario autónomo no se modifica aquí.
//
// Contrato de props (wave 2b — página InventarioPorEquipos):
//   { material, categorias, ums, onSubmit, onCancel }
// ============================================================================

interface ConfigLocalFormProps {
  material: InventarioEquipoRow
  categorias: Categoria[]
  ums: Ums[]
  onSubmit: (payload: EquipoConfigLocalPayload) => void
  onCancel: () => void
}

/** Traduce los issues de Zod a mensajes deterministas para la UI. */
function formatearErrores(error: { issues: { message: string; path: PropertyKey[] }[] }): string[] {
  return error.issues.map((issue) => {
    if (issue.message.includes('al menos un campo')) {
      return issue.message
    }
    const campo = issue.path[0]
    if (campo === 'stock_minimo_local') {
      return 'El stock mínimo local debe ser un entero mayor o igual a 0.'
    }
    if (campo === 'categoria_local_id') {
      return 'Seleccione una categoría válida.'
    }
    if (campo === 'um_local_id') {
      return 'Seleccione una U.M. válida.'
    }
    return issue.message
  })
}

export default function ConfigLocalForm({
  material,
  categorias,
  ums,
  onSubmit,
  onCancel,
}: ConfigLocalFormProps) {
  // '' / null = campo NO editado (se omite del payload)
  const [stockMinimoLocal, setStockMinimoLocal] = useState('')
  const [categoriaLocalId, setCategoriaLocalId] = useState<number | null>(null)
  const [umLocalId, setUmLocalId] = useState<number | null>(null)
  const [errores, setErrores] = useState<string[]>([])

  const categoriasActivas = categorias
    .filter((c) => c.is_active)
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
  const umsActivas = ums
    .filter((u) => u.is_active)
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    // Campos vacíos → OMITIDOS del payload (contrato: un campo omitido
    // conserva su valor previo; null numérico NO es parte del contrato).
    const payload: EquipoConfigLocalPayload = {}
    if (stockMinimoLocal.trim() !== '') {
      payload.stock_minimo_local = Number(stockMinimoLocal)
    }
    if (categoriaLocalId !== null) {
      payload.categoria_local_id = categoriaLocalId
    }
    if (umLocalId !== null) {
      payload.um_local_id = umLocalId
    }

    const resultado = configLocalSchema.safeParse(payload)
    if (!resultado.success) {
      setErrores(formatearErrores(resultado.error))
      return
    }

    setErrores([])
    onSubmit(resultado.data)
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      {/* ── Bloque SOLO LECTURA (REQ-TEAM-001/002) ───────────────────────── */}
      <div className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Material (solo lectura)
        </p>
        <div>
          <p className="text-xs text-slate-500">Código (SKU)</p>
          <p className="font-mono text-sm text-slate-700">
            {material.codigo ?? '—'}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Descripción</p>
          <p className="text-sm text-slate-700">{material.descripcion}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Stock Actual</p>
          <p className="text-sm font-medium text-slate-700">
            {material.stock_actual.toLocaleString('es-MX')} {material.u_m ?? ''}
          </p>
        </div>
      </div>

      <div>
        <label
          htmlFor="config-local-stock-minimo"
          className="text-xs font-semibold uppercase tracking-wide text-slate-400"
        >
          Stock Mínimo Local
        </label>
        <input
          id="config-local-stock-minimo"
          type="number"
          min={0}
          step={1}
          value={stockMinimoLocal}
          onChange={(event) => {
            setStockMinimoLocal(event.target.value)
            setErrores([])
          }}
          placeholder={
            material.stock_minimo != null
              ? String(material.stock_minimo)
              : undefined
          }
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <p className="mt-1 text-xs text-slate-500">
          {material.stock_minimo != null
            ? `Stock mínimo del catálogo (heredado): ${material.stock_minimo}. Déjalo vacío para heredar.`
            : 'Déjalo vacío para heredar el stock mínimo del catálogo.'}
        </p>
      </div>

      <div>
        <label
          htmlFor="config-local-categoria"
          className="text-xs font-semibold uppercase tracking-wide text-slate-400"
        >
          Categoría Local
        </label>
        <select
          id="config-local-categoria"
          value={categoriaLocalId ?? ''}
          onChange={(event) => {
            setCategoriaLocalId(
              event.target.value === '' ? null : Number(event.target.value),
            )
            setErrores([])
          }}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Heredar del catálogo</option>
          {categoriasActivas.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label
          htmlFor="config-local-um"
          className="text-xs font-semibold uppercase tracking-wide text-slate-400"
        >
          U.M. Local
        </label>
        <select
          id="config-local-um"
          value={umLocalId ?? ''}
          onChange={(event) => {
            setUmLocalId(
              event.target.value === '' ? null : Number(event.target.value),
            )
            setErrores([])
          }}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">Heredar del catálogo</option>
          {umsActivas.map((u) => (
            <option key={u.id} value={u.id}>
              {u.nombre}
            </option>
          ))}
        </select>
      </div>

      {errores.length > 0 && (
        <div className="space-y-1 rounded-md border border-red-200 bg-red-50 p-3">
          {errores.map((mensaje, index) => (
            <p
              key={index}
              className="text-xs font-medium text-red-600"
              role="alert"
            >
              {mensaje}
            </p>
          ))}
        </div>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          Cancelar
        </button>
        <button
          type="submit"
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Guardar
        </button>
      </div>
    </form>
  )
}
