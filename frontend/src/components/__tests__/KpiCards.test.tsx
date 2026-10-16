import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import KpiCards from '../KpiCards'
import { getResumenGeneral } from '../../services/inventory'
import { invalidarResumenGeneral, queryKeys } from '../../hooks/queryKeys'
import type { SeccionStockRow } from '../../types'

// RF-5 / REQ-VALOR-004: el indicador Valor Total es la SEGUNDA tarjeta
// (Total Materiales, Valor Total, Stock Total, Alertas Stock, Transferencias
// Hoy), muestra la cifra de la API con `MXN` a la derecha, nunca la recalcula
// y expone estados explícitos de carga/error.

vi.mock('../../services/inventory', () => ({
  getResumenGeneral: vi.fn(),
}))

const STOCK: SeccionStockRow[] = [
  {
    material_id: 1,
    codigo: 'A',
    descripcion: 'Material A',
    u_m: 'PZ',
    stock_minimo: 1,
    stock_actual: 4,
    valor_unitario: 2.5,
    alerta_stock: false,
  },
  {
    material_id: 2,
    codigo: 'B',
    descripcion: 'Material B',
    u_m: 'PZ',
    stock_minimo: 1,
    stock_actual: 10,
    valor_unitario: 1.25,
    alerta_stock: true,
  },
]

function renderKpis(client?: QueryClient) {
  const queryClient =
    client ??
    new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <KpiCards stock={STOCK} />
    </QueryClientProvider>,
  )
  return { ...utils, queryClient }
}

beforeEach(() => {
  vi.mocked(getResumenGeneral).mockReset()
})

describe('KpiCards — Valor Total (RF-5)', () => {
  it('RF-5: el orden de tarjetas es Total Materiales, Valor Total, Stock Total, Alertas Stock, Transferencias Hoy', async () => {
    vi.mocked(getResumenGeneral).mockResolvedValue({ valor_total: 22.5, moneda: 'MXN' })
    renderKpis()

    await screen.findByTestId('valor-total')
    const etiquetas = screen
      .getAllByText(
        /^(Total Materiales|Valor Total|Stock Total|Alertas Stock|Transferencias Hoy)$/,
      )
      .map((el) => el.textContent)
    expect(etiquetas).toEqual([
      'Total Materiales',
      'Valor Total',
      'Stock Total',
      'Alertas Stock',
      'Transferencias Hoy',
    ])
  })

  it('RF-5: muestra la cifra de la API con 2-3 decimales y la etiqueta MXN a su derecha, sin recalcular', async () => {
    // La API devuelve 22.5 aunque el stock visible daría otro resultado: el
    // cliente muestra lo del servidor.
    vi.mocked(getResumenGeneral).mockResolvedValue({ valor_total: 22.5, moneda: 'MXN' })
    renderKpis()

    const valor = await screen.findByTestId('valor-total')
    expect(valor).toHaveTextContent('22.50')
    expect(valor).toHaveTextContent('MXN')
    // cifra a la izquierda, MXN a la derecha
    expect(valor.textContent?.indexOf('22.50')).toBeLessThan(
      valor.textContent?.indexOf('MXN') ?? -1,
    )
    expect(getResumenGeneral).toHaveBeenCalledTimes(1)
  })

  it('RF-5: conserva hasta 3 decimales (12.345 → 12.345 MXN)', async () => {
    vi.mocked(getResumenGeneral).mockResolvedValue({ valor_total: 12.345, moneda: 'MXN' })
    renderKpis()
    expect(await screen.findByTestId('valor-total')).toHaveTextContent('12.345')
  })

  it('RF-5: inventario vacío muestra 0.00 MXN (nunca nulo ni error)', async () => {
    vi.mocked(getResumenGeneral).mockResolvedValue({ valor_total: 0, moneda: 'MXN' })
    renderKpis()
    expect(await screen.findByTestId('valor-total')).toHaveTextContent('0.00')
  })

  it('RF-5: mientras carga muestra un estado de carga explícito y ningún valor inventado', async () => {
    vi.mocked(getResumenGeneral).mockReturnValue(new Promise(() => undefined))
    renderKpis()

    const estado = screen.getByRole('status')
    expect(estado).toHaveTextContent(/cargando valor/i)
    expect(estado).toHaveAttribute('aria-busy', 'true')
    expect(screen.queryByTestId('valor-total')).not.toBeInTheDocument()
  })

  it('RF-5: si la consulta falla muestra un error explícito (no 0) con opción de reintentar', async () => {
    vi.mocked(getResumenGeneral).mockRejectedValueOnce(new Error('boom'))
    vi.mocked(getResumenGeneral).mockResolvedValueOnce({ valor_total: 5, moneda: 'MXN' })
    const user = userEvent.setup()
    renderKpis()

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent(/no se pudo obtener el valor total/i)
    expect(screen.queryByTestId('valor-total')).not.toBeInTheDocument()

    await user.click(within(alerta).getByRole('button', { name: /reintentar/i }))
    expect(await screen.findByTestId('valor-total')).toHaveTextContent('5.00')
  })

  it('RF-5: tras una mutación (invalidación de resumen-general) el indicador se refresca con el valor persistido', async () => {
    vi.mocked(getResumenGeneral)
      .mockResolvedValueOnce({ valor_total: 10, moneda: 'MXN' })
      .mockResolvedValueOnce({ valor_total: 17.5, moneda: 'MXN' })
    const { queryClient } = renderKpis()

    expect(await screen.findByTestId('valor-total')).toHaveTextContent('10.00')

    await invalidarResumenGeneral(queryClient)

    await waitFor(() =>
      expect(screen.getByTestId('valor-total')).toHaveTextContent('17.50'),
    )
    expect(getResumenGeneral).toHaveBeenCalledTimes(2)
    expect(queryKeys.resumenGeneral()).toEqual(['inventario', 'resumen-general'])
  })

  it('las otras cuatro tarjetas no cambian (agregaciones visuales del stock de la sección)', async () => {
    vi.mocked(getResumenGeneral).mockResolvedValue({ valor_total: 22.5, moneda: 'MXN' })
    renderKpis()
    await screen.findByTestId('valor-total')

    const tarjeta = (etiqueta: string) =>
      screen.getByText(etiqueta).parentElement as HTMLElement
    expect(tarjeta('Total Materiales')).toHaveTextContent('2')
    expect(tarjeta('Stock Total')).toHaveTextContent('14')
    expect(tarjeta('Alertas Stock')).toHaveTextContent('1')
  })
})
