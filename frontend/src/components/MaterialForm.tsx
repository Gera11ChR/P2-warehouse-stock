import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Categoria, Material, SeccionTransferible, Ums } from '../types'
import { UNIDADES } from '../types'
import type {
  MaterialCreatePayload,
  MaterialUpdatePayload,
} from '../services/catalog'
import { MATERIAL_FIELD_LABELS } from '../utils/materialFields'
import {
  formatearCantidad,
  mensajeCantidadInvalida,
  validarCantidad,
} from '../utils/cantidad'
import { validarValorUnitario } from '../schemas/valorUnitario'
import { etiquetaSeccion } from '../utils/seccionLabel'
import CampoCantidad from './CampoCantidad'

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
  /**
   * RBAC VISUAL (RF-8; no es seguridad): `false` deshabilita el campo
   * Valor Unitario y jamás lo envía. La autoridad es el backend: la sola
   * presencia de `valor_unitario` en el PATCH exige rol administrador (403).
   * Por omisión el campo es editable y solo se envía si el usuario lo
   * cambió, de modo que un actor sin privilegios que edita otros campos no
   * dispara el 403.
   */
  esAdmin?: boolean
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
  esAdmin = true,
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
  // se incluye stock_actual en el payload. Ergonomía
  // `justificacion_opcional` (REQ-ERG-003): el motivo es opcional.
  const [stockActualEditado, setStockActualEditado] = useState(
    String(stockActual),
  )
  const [motivo, setMotivo] = useState('')
  // Valor Unitario (RF-3, solo edición; el alta nace en 1.000 — C-3). Se
  // envía SOLO si el administrador lo cambió (presencia = 403 para no admin).
  const [valorUnitario, setValorUnitario] = useState(
    initial?.valor_unitario != null ? String(initial.valor_unitario) : '',
  )
  const [intentado, setIntentado] = useState(false)

  // Validación PRELIMINAR (el backend decide). Decimales hasta 3 (RF-6).
  const stockValidacion = validarCantidad(stockActualEditado, {
    permitirCero: true,
  })
  const stockError: string | null =
    mode === 'edit' && stockActualEditado !== '' && !stockValidacion.ok
      ? mensajeCantidadInvalida(stockValidacion.motivo)
      : null

  // Proyección UX (simulación visual previa al commit). El diferencial NO se
  // envía: el backend recalcula el delta y audita vía fn_ajustar_stock_general.
  const stockEditadoNum = stockValidacion.ok ? stockValidacion.cantidad : null
  const stockModificado =
    mode === 'edit' && stockEditadoNum !== null && stockEditadoNum !== stockActual
  const diferencial =
    stockModificado && stockEditadoNum !== null
      ? stockEditadoNum - stockActual
      : null

  const valorValidacion = validarValorUnitario(valorUnitario)
  const valorModificado =
    mode === 'edit' &&
    esAdmin &&
    valorValidacion.ok &&
    initial?.valor_unitario != null &&
    valorValidacion.valor !== initial.valor_unitario
  const valorError: string | null =
    mode === 'edit' && esAdmin && !valorValidacion.ok
      ? valorUnitario === ''
        ? intentado
          ? 'Ingresa el Valor Unitario (0 o mayor).'
          : null
        : valorValidacion.mensaje
      : null

  // Stock Inicial (alta): decimal ≥ 0; vacío = sin carga inicial.
  const stockInicialValidacion = validarCantidad(stockInicial, {
    permitirCero: true,
  })
  const stockInicialError: string | null =
    mode === 'create' && stockInicial !== '' && !stockInicialValidacion.ok
      ? mensajeCantidadInvalida(stockInicialValidacion.motivo)
      : null

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
    setIntentado(true)

    if (mode === 'create') {
      if (stockInicialError !== null) return
      const payload: MaterialCreatePayload = {
        descripcion: descripcion || '',
        codigo: codigo || null,
        categoria_id: categoriaMode === 'selector' ? categoriaId : null,
        nueva_categoria: categoriaMode === 'nueva' ? nuevaCategoria || null : null,
        u_m: u_m || null,
        stock_minimo: stockMinimo === '' ? null : Number(stockMinimo),
        stock_inicial:
          stockInicial === '' || !stockInicialValidacion.ok
            ? null
            : stockInicialValidacion.cantidad,
        seccion_id: stockInicial === '' ? null : seccionId,
      }
      onSubmit(payload)
      return
    }

    // ── Edición (Inventario General) ──────────────────────────────────────
    // Un valor inválido bloquea el envío con el error en línea (el backend
    // vuelve a validar: 422 por escala/rango; sin redondeo silencioso).
    if (stockError !== null) return
    if (esAdmin && !valorValidacion.ok) return

    const payload: MaterialUpdatePayload = {
      descripcion: descripcion || null,
      codigo: codigo || null,
      categoria_id: categoriaMode === 'selector' ? categoriaId : null,
      nueva_categoria: categoriaMode === 'nueva' ? nuevaCategoria || null : null,
      u_m: u_m || null,
      stock_minimo: stockMinimo === '' ? null : Number(stockMinimo),
    }

    // stock_actual SOLO se incluye si el usuario modificó el valor registrado.
    if (stockModificado && stockEditadoNum !== null) {
      // Contrato REQ-API-002/003: el backend calcula el delta y lo enruta a
      // fn_ajustar_stock_general → fn_ajustar_stock_almacen. El frontend NO
      // envía el diferencial: solo stock_actual + motivo. Ergonomía
      // REQ-ERG-003: el motivo es OPCIONAL — vacío se envía como null.
      payload.stock_actual = stockEditadoNum
      payload.motivo = motivo.trim() || null
    }

    // RF-8: valor_unitario SOLO si el administrador lo cambió.
    if (valorModificado && valorValidacion.ok) {
      payload.valor_unitario = valorValidacion.valor
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
          <CampoCantidad
            id="material-stock-actual"
            label={MATERIAL_FIELD_LABELS.stock_actual}
            value={stockActualEditado}
            onChange={setStockActualEditado}
            error={stockError}
            ayuda="Hasta 3 decimales (por ejemplo 7.250)."
          />
          {!stockModificado && (
            <p className="mt-1 text-xs text-slate-500">
              Si modificas este valor podrás indicar un motivo opcional: el
              backend calcula el diferencial y registra el ajuste en
              Auditoría.
            </p>
          )}
          {stockModificado && diferencial !== null && (
            <p className="mt-1 text-xs text-slate-500">
              Proyección visual — Stock actual registrado:{' '}
              {formatearCantidad(stockActual)} → Nuevo:{' '}
              {formatearCantidad(stockEditadoNum ?? stockActual)} (diferencial{' '}
              {diferencial >= 0 ? '+' : ''}
              {formatearCantidad(diferencial)}). El saldo confirmado lo
              calcula y audita el backend.
            </p>
          )}

          {stockModificado && (
            <div className="mt-3">
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Motivo del ajuste (opcional)
              </label>
              <textarea
                value={motivo}
                onChange={(event) => setMotivo(event.target.value)}
                maxLength={500}
                rows={2}
                placeholder="Ej. Conteo físico, corrección de captura, ajuste administrativo"
                className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <div className="mt-1 flex items-center justify-between">
                <p className="text-xs text-slate-500">
                  Opcional (máx. 500 caracteres). El ajuste queda registrado
                  en Auditoría.
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

      {mode === 'edit' && (
        <div>
          <CampoCantidad
            id="material-valor-unitario"
            label={`${MATERIAL_FIELD_LABELS.valor_unitario} (MXN)`}
            value={valorUnitario}
            onChange={setValorUnitario}
            error={valorError}
            ayuda={
              esAdmin
                ? 'Decimal mayor o igual a 0, hasta 3 decimales. Cada cambio queda registrado en Auditoría.'
                : 'Solo un administrador puede modificar el Valor Unitario.'
            }
            disabled={!esAdmin}
          />
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
            <CampoCantidad
              id="material-stock-inicial"
              label="Stock Inicial"
              value={stockInicial}
              onChange={setStockInicial}
              error={stockInicialError}
              ayuda="Opcional. Hasta 3 decimales (por ejemplo 2.5)."
            />
          </div>

          {stockInicialValidacion.ok && stockInicialValidacion.cantidad > 0 && (
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
                    {etiquetaSeccion(s)}
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
