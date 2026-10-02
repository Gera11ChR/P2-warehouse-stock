import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ReporteExportButtons from '../ReporteExportButtons'

describe('ReporteExportButtons', () => {
  it('invoca el handler del formato pulsado', async () => {
    const user = userEvent.setup()
    const onExportNormal = vi.fn()
    const onExportExtenso = vi.fn()
    render(
      <ReporteExportButtons
        onExportNormal={onExportNormal}
        onExportExtenso={onExportExtenso}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Exportar XLSX (Normal)' }))
    expect(onExportNormal).toHaveBeenCalledTimes(1)
    expect(onExportExtenso).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Exportar XLSX (Extenso)' }))
    expect(onExportExtenso).toHaveBeenCalledTimes(1)
  })

  it('deshabilita ambos botones con disabled o sin handler', () => {
    const { rerender } = render(
      <ReporteExportButtons
        onExportNormal={vi.fn()}
        onExportExtenso={vi.fn()}
        disabled
      />,
    )
    expect(screen.getByRole('button', { name: 'Exportar XLSX (Normal)' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Exportar XLSX (Extenso)' })).toBeDisabled()

    rerender(<ReporteExportButtons />)
    expect(screen.getByRole('button', { name: 'Exportar XLSX (Normal)' })).toBeDisabled()
  })

  it('con loadingFormato bloquea ambos y marca aria-busy el activo', () => {
    render(
      <ReporteExportButtons
        onExportNormal={vi.fn()}
        onExportExtenso={vi.fn()}
        loadingFormato="extenso"
      />,
    )
    const normal = screen.getByRole('button', { name: 'Exportar XLSX (Normal)' })
    const extenso = screen.getByRole('button', { name: 'Exportar XLSX (Extenso)' })
    expect(normal).toBeDisabled()
    expect(extenso).toBeDisabled()
    expect(extenso).toHaveAttribute('aria-busy', 'true')
    expect(normal).toHaveAttribute('aria-busy', 'false')
  })
})
