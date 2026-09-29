import { useState } from 'react'
import type { FormEvent } from 'react'
import type {
  Categoria,
  FibraMaterialRowEditable,
  FibraMaterialUpdatePayload,
  Ums,
} from '../types'
import { UNIDADES } from '../types'
import { MATERIAL_FIELD_LABELS } from '../utils/materialFields'

interface FibraMaterialFormProps {
  /** Fila FO seleccionada con categoría resuelta (join de presentación). */
  initial: FibraMaterialRowEditable
  /** Stock registrado del módulo FO: base de la proyección del diferencial. */
  stockActual: number
  alertaStock: boolean
  categorias: Categoria[]
  /**
   * Unidades de medida del catálogo (GET /api/v1/catalogo/um). El select
   * U.M. usa SOLO las activas ordenadas por nombre; si el arreglo llega
   * vacío se conserva el fallback `UNIDADES` (constante del dominio).
   */
  ums: Ums[]
  onSubmit: (payload: FibraMaterialUpdatePayload) => void
  onCancel: () => void
}

/**
 * Formulario de edición para las secciones de Fibra Óptica
 * (REQ-CATFO-001, REQ-STOCK-001): modo SOLO edición — espejo simplificado
 * del MaterialForm de Inventario General. Edita Descripción, STOCK ACTUAL
 * (con proyección visual del diferencial), Stock Mínimo, U.M., Código/SKU
 * y Categoría (selector dual). Si el operador cambia el STOCK ACTUAL, el
 * motivo es OBLIGATORIO: el frontend envía SOLO stock_actual + motivo
 * (NUNCA el delta) y el backend calcula el diferencial en PostgreSQL con
 * auditoría 'AJUSTE_INVENTARIO_FO'.
 */
export default function FibraMaterialForm({
  initial,
  stockActual = 0,
  alertaStock = false,
  categorias,
  ums = [],
  onSubmit,
  onCancel,
}: FibraMaterialFormProps) {
  const [descripcion, setDescripcion] = useState(initial.descripcion)
  const [stockMinimo, setStockMinimo] = useState(
    initial.stock_minimo != null ? String(initial.stock_minimo) : '',
  )
  const [u_m, setUm] = useState(initial.u_m ?? '')
  const [codigo, setCodigo] = useState(initial.codigo ?? '')

  // Selector dual: categoria_id XOR nueva_categoria (espejo de MaterialForm).
  const [categoriaMode, setCategoriaMode] = useState<'selector' | 'nueva'>(
    'selector',
  )
  const [categoriaId, setCategoriaId] = useState<number | null>(
    initial.categoria_id,
  )
  const [nuevaCategoria, setNuevaCategoria] = useState('')

  // Edición de STOCK ACTUAL (REQ-STOCK-001): el input arranca con el valor
  // registrado; SOLO si el usuario lo cambia se incluye stock_actual en el
  // payload, y entonces el motivo es obligatorio.
  const [stockActualEditado, setStockActualEditado] = useState(
    String(stockActual),
  )
  const [motivo, setMotivo] = useState('')
  const [motivoError, setMotivoError] = useState<string | null>(null)
  const [stockError, setStockError] = useState<string | null>(null)

  // Proyección UX (simulación visual previa al commit). El diferencial NO se
  // envía: el backend recalcula el delta y audita vía fn_ajustar_stock_fibra.
  const stockEditadoNum =
    stockActualEditado === '' ? null : Number(stockActualEditado)
  const stockModificado =
    stockEditadoNum !== null &&
    Number.isFinite(stockEditadoNum) &&
    stockEditadoNum >= 0 &&
    stockEditadoNum !== stockActual
  const diferencial = stockModificado ? stockEditadoNum - stockActual : null

  // U.M.: catálogo activo ordenado por nombre; fallback a la constante del
  // dominio si la página no provee el catálogo de unidades (ums = []).
  const unidadesDisponibles = (() => {
    const activas = ums
      .filter((u) => u.is_active)
      .map((u) => u.nombre)
      .sort((a, b) => a.localeCompare(b, 'es'))
    return activas.length > 0 ? activas : [...UNIDADES]
  })()

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    // Campos de catálogo: se envían siempre (espejo de MaterialForm) para
    // preservar la semántica del modal "Modificar Material" FO.
    const payload: FibraMaterialUpdatePayload = {
      descripcion: descripcion || null,
      codigo: codigo || null,
      categoria_id: categoriaMode === 'selector' ? categoriaId : null,
      nueva_categoria: categoriaMode === 'nueva' ? nuevaCategoria || null : null,
      u_m: u_m || null,
      stock_minimo: stockMinimo === '' ? null : Number(stockMinimo),
    }

    const stockEditado =
      stockActualEditado === '' ? null : Number(stockActualEditado)

    // stock_actual SOLO se incluye si el usuario modificó el valor registrado.
    if (
      stockEditado !== null &&
      Number.isFinite(stockEditado) &&
      stockEditado !== stockActual
    ) {
      if (stockEditado < 0) {
        setStockError('El Stock Actual no puede ser negativo.')
        return
      }
      const motivoLimpio = motivo.trim()
      if (!motivoLimpio) {
        setMotivoError(
          'El motivo del ajuste es obligatorio al modificar el Stock Actual: todo ajuste queda registrado en Auditoría.',
        )
        return
      }
      // REQ-STOCK-002: el backend calcula el delta y lo enruta a
      // fn_ajustar_stock_fibra. El frontend NO envía el diferencial:
      // solo stock_actual + motivo.
      payload.stock_actual = stockEditado
      payload.motivo = motivoLimpio
    }

    onSubmit(payload)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.descripcion}
        </label>
        <input
          type="text"
          value={descripcion}
          onChange={(event) => setDescripcion(event.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          required
        />
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.stock_actual}
        </label>
        <input
          type="number"
          min={0}
          step={1}
          value={stockActualEditado}
          onChange={(event) => {
            setStockActualEditado(event.target.value)
            setStockError(null)
            setMotivoError(null)
          }}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        {!stockModificado && (
          <p className="mt-1 text-xs text-slate-500">
            Si modificas este valor deberás indicar un motivo: el backend
            calcula el diferencial y registra el ajuste en Auditoría.
          </p>
        )}
        {stockModificado && diferencial !== null && (
          <p className="mt-1 text-xs text-slate-500">
            Proyección visual — Stock actual registrado:{' '}
            {stockActual.toLocaleString('es-MX')} → Nuevo:{' '}
            {stockEditadoNum.toLocaleString('es-MX')} (diferencial{' '}
            {diferencial >= 0 ? '+' : ''}
            {diferencial.toLocaleString('es-MX')}). El saldo confirmado lo
            calcula y audita el backend.
          </p>
        )}
        {stockError && (
          <p className="mt-1 text-xs font-medium text-red-600">{stockError}</p>
        )}

        {stockModificado && (
          <div className="mt-3">
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Motivo del ajuste *
            </label>
            <textarea
              value={motivo}
              onChange={(event) => {
                setMotivo(event.target.value)
                if (motivoError) setMotivoError(null)
              }}
              maxLength={500}
              rows={2}
              placeholder="Ej. Conteo físico, corrección de captura, ajuste administrativo"
              className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${
                motivoError ? 'border-red-400' : 'border-slate-300'
              }`}
            />
            <div className="mt-1 flex items-center justify-between">
              <p
                className={`text-xs ${
                  motivoError ? 'font-medium text-red-600' : 'text-slate-500'
                }`}
              >
                {motivoError ??
                  'Obligatorio al modificar el Stock Actual (máx. 500 caracteres).'}
              </p>
              <span className="text-xs text-slate-400">
                {motivo.length}/500
              </span>
            </div>
          </div>
        )}
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.stock_minimo}
        </label>
        <input
          type="number"
          min={0}
          value={stockMinimo}
          onChange={(event) => setStockMinimo(event.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.alerta_stock}
        </label>
        <div className="mt-1">
          {alertaStock ? (
            <span className="inline-flex rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700">
              Alerta Stock
            </span>
          ) : (
            <span className="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-700">
              Sin alerta
            </span>
          )}
        </div>
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.u_m}
        </label>
        <select
          value={u_m}
          onChange={(event) => setUm(event.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        >
          <option value="">—</option>
          {unidadesDisponibles.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {MATERIAL_FIELD_LABELS.codigo}
        </label>
        <input
          type="text"
          value={codigo}
          onChange={(event) => setCodigo(event.target.value)}
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 font-mono text-sm"
        />
      </div>

      <div className="space-y-3 border-t border-slate-200 pt-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Clasificación
        </p>

        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Categoría
          </label>
          <div className="mt-2 flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                checked={categoriaMode === 'selector'}
                onChange={() => setCategoriaMode('selector')}
              />
              <span>Selector</span>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                checked={categoriaMode === 'nueva'}
                onChange={() => setCategoriaMode('nueva')}
              />
              <span>Nueva categoría</span>
            </label>
          </div>

          {categoriaMode === 'selector' ? (
            <select
              value={categoriaId ?? ''}
              onChange={(event) =>
                setCategoriaId(
                  event.target.value === '' ? null : Number(event.target.value),
                )
              }
              className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">— Sin categoría —</option>
              {categorias
                .filter((c) => c.is_active)
                .map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
            </select>
          ) : (
            <input
              type="text"
              value={nuevaCategoria}
              onChange={(event) => setNuevaCategoria(event.target.value)}
              placeholder="Nombre de la nueva categoría"
              className="mt-2 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          )}
        </div>
      </div>

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
