import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Categoria, Material, SeccionTransferible, Ums } from '../types'
import { UNIDADES } from '../types'
import type {
  MaterialCreatePayload,
  MaterialUpdatePayload,
} from '../services/catalog'
import { MATERIAL_FIELD_LABELS } from '../utils/materialFields'

interface MaterialFormProps {
  mode: 'create' | 'edit'
  initial?: Material
  stockActual?: number
  alertaStock?: boolean
  categorias: Categoria[]
  /**
   * Secciones destino de la Carga Inicial
   * (GET /api/v1/inventario/secciones/transferibles): Inventario General
   * activo + raíces FO con etiquetas operativas. El select NO filtra por
   * `is_active` (las raíces FO son soft-inactivas por dominio).
   */
  seccionesDestino?: SeccionTransferible[]
  /**
   * Unidades de medida del catálogo (GET /api/v1/catalogo/um). El select
   * U.M. usa SOLO las activas ordenadas por nombre; si el arreglo llega
   * vacío se conserva el fallback `UNIDADES` (constante del dominio).
   */
  ums?: Ums[]
  onSubmit: (
    payload: MaterialCreatePayload | MaterialUpdatePayload,
  ) => void | Promise<void>
  onCancel: () => void
}

export default function MaterialForm({
  mode,
  initial,
  stockActual = 0,
  alertaStock = false,
  categorias,
  seccionesDestino = [],
  ums = [],
  onSubmit,
  onCancel,
}: MaterialFormProps) {
  const [descripcion, setDescripcion] = useState(initial?.descripcion ?? '')
  const [stockMinimo, setStockMinimo] = useState(
    initial?.stock_minimo != null ? String(initial.stock_minimo) : '',
  )
  const [u_m, setUm] = useState(initial?.u_m ?? '')
  const [codigo, setCodigo] = useState(initial?.codigo ?? '')

  // Selector dual: categoria_id XOR nueva_categoria
  const [categoriaMode, setCategoriaMode] = useState<'selector' | 'nueva'>(
    'selector',
  )
  const [categoriaId, setCategoriaId] = useState<number | null>(
    initial?.categoria_id ?? null,
  )
  const [nuevaCategoria, setNuevaCategoria] = useState('')

  // Carga inicial (solo create)
  const [stockInicial, setStockInicial] = useState('')
  const [seccionId, setSeccionId] = useState<number | null>(null)

  // Edición de STOCK ACTUAL (REQ-UI-004, alcance Inventario General):
  // el input arranca con el valor registrado; SOLO si el usuario lo cambia
  // se incluye stock_actual en el payload, y entonces el motivo es obligatorio.
  const [stockActualEditado, setStockActualEditado] = useState(
    String(stockActual),
  )
  const [motivo, setMotivo] = useState('')
  const [motivoError, setMotivoError] = useState<string | null>(null)
  const [stockError, setStockError] = useState<string | null>(null)

  // Proyección UX (simulación visual previa al commit). El diferencial NO se
  // envía: el backend recalcula el delta y audita vía fn_ajustar_stock_general.
  const stockEditadoNum =
    stockActualEditado === '' ? null : Number(stockActualEditado)
  const stockModificado =
    mode === 'edit' &&
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

  // Etiqueta operativa de una sección destino de Carga Inicial
  // (REQ-CARGA-001): las raíces FO se muestran con nombre propio;
  // GENERAL conserva el nombre del almacén.
  const labelSeccionDestino = (s: SeccionTransferible): string => {
    if (s.tipo === 'FO_PAQUETE') return 'Fibra Óptica - Paquete'
    if (s.tipo === 'FO_EN_USO') return 'Fibra Óptica - En Uso'
    return s.nombre
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()

    if (mode === 'create') {
      const payload: MaterialCreatePayload = {
        descripcion: descripcion || '',
        codigo: codigo || null,
        categoria_id: categoriaMode === 'selector' ? categoriaId : null,
        nueva_categoria: categoriaMode === 'nueva' ? nuevaCategoria || null : null,
        u_m: u_m || null,
        stock_minimo: stockMinimo === '' ? null : Number(stockMinimo),
        stock_inicial:
          stockInicial === '' ? null : Number(stockInicial),
        seccion_id: stockInicial === '' ? null : seccionId,
      }
      onSubmit(payload)
      return
    }

    // ── Edición (Inventario General) ──────────────────────────────────────
    const payload: MaterialUpdatePayload = {
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
      // Contrato REQ-API-002/003: el backend calcula el delta y lo enruta a
      // fn_ajustar_stock_general → fn_ajustar_stock_almacen. El frontend NO
      // envía el diferencial: solo stock_actual + motivo.
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

      {mode === 'edit' ? (
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
      ) : (
        <div>
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            {MATERIAL_FIELD_LABELS.stock_actual}
          </label>
          <div className="mt-1 rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700">
            {stockActual.toLocaleString('es-MX')}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Solo lectura. El stock se define en la sección «Carga Inicial» al
            guardar.
          </p>
        </div>
      )}

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

      {mode === 'create' && (
        <div className="space-y-3 border-t border-slate-200 pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Carga Inicial (opcional)
          </p>

          <div>
            <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Stock Inicial
            </label>
            <input
              type="number"
              min={0}
              value={stockInicial}
              onChange={(event) => setStockInicial(event.target.value)}
              className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
          </div>

          {stockInicial !== '' && Number(stockInicial) > 0 && (
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Sección destino *
              </label>
              <select
                value={seccionId ?? ''}
                onChange={(event) =>
                  setSeccionId(
                    event.target.value === ''
                      ? null
                      : Number(event.target.value),
                  )
                }
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                required
              >
                <option value="">— Seleccione sección —</option>
                {seccionesDestino.map((s) => (
                  <option key={s.almacen_id} value={s.almacen_id}>
                    {labelSeccionDestino(s)}
                  </option>
                ))}
              </select>
            </div>
          )}
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
          {mode === 'create' ? 'Agregar' : 'Guardar'}
        </button>
      </div>
    </form>
  )
}
