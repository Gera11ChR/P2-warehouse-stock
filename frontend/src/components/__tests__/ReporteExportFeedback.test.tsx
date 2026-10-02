import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import ReporteExportFeedback from '../ReporteExportFeedback'
import ReporteSubseccion from '../ReporteSubseccion'
import type { ReporteExportStatus } from '../../utils/reporteExport'

describe('ReporteExportFeedback — estados de la exportación XLSX', () => {
  it('idle: región viva vacía (nada que anunciar)', () => {
    render(<ReporteExportFeedback tipo="entrega" status={{ estado: 'idle' }} />)
    expect(screen.getByRole('status')).toBeEmptyDOMElement()
  })

  it('loading: anuncia qué acta y qué formato se genera', () => {
    render(
      <ReporteExportFeedback
        tipo="consumo"
        status={{ estado: 'loading', formato: 'extenso' }}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent(
      'Generando Acta de Consumo en formato Extenso',
    )
  })

  it('success: indica el archivo y dónde revisarlo', () => {
    render(
      <ReporteExportFeedback
        tipo="entrega"
        status={{ estado: 'success', formato: 'normal', nombreArchivo: 'acta_entrega.xlsx' }}
      />,
    )
    expect(screen.getByRole('status')).toHaveTextContent(
      'Archivo generado: acta_entrega.xlsx. Revisa la descarga de tu navegador.',
    )
  })

  it('error 404: traduce «sin actas para los filtros» y conserva el detalle del servidor', () => {
    render(
      <ReporteExportFeedback
        tipo="entrega"
        status={{
          estado: 'error',
          formato: 'normal',
          httpStatus: 404,
          detalle: 'No hay actas para los filtros indicados',
        }}
      />,
    )
    const alerta = screen.getByRole('alert')
    expect(alerta).toHaveTextContent(
      'No hay actas de Entrega para los filtros seleccionados',
    )
    expect(alerta).toHaveTextContent('Ajusta el equipo o el rango de fechas')
    expect(alerta).toHaveTextContent(
      'Detalle del servidor: No hay actas para los filtros indicados',
    )
  })

  it('error 422 y error genérico tienen mensajes operativos distintos', () => {
    const { rerender } = render(
      <ReporteExportFeedback
        tipo="consumo"
        status={{ estado: 'error', formato: 'normal', httpStatus: 422 }}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(/filtros no son válidos/)

    rerender(
      <ReporteExportFeedback
        tipo="consumo"
        status={{ estado: 'error', formato: 'normal', httpStatus: 500 }}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      /No se pudo generar el archivo del Acta de Consumo/,
    )
    expect(screen.getByRole('alert')).not.toHaveTextContent(/500|IntegrityError/)
  })
})

describe('ReporteSubseccion — exportación', () => {
  function renderSub(status: ReporteExportStatus, motivo?: string) {
    return render(
      <ReporteSubseccion
        tipo="entrega"
        idPrefix="t"
        equipos={[]}
        equipoId={null}
        desde=""
        hasta=""
        onEquipoChange={() => undefined}
        onDesdeChange={() => undefined}
        onHastaChange={() => undefined}
        onExportNormal={() => undefined}
        onExportExtenso={() => undefined}
        exportStatus={status}
        exportDisabledReason={motivo}
      >
        <div />
      </ReporteSubseccion>,
    )
  }

  it('en loading bloquea ambos botones y marca el formato en curso', () => {
    renderSub({ estado: 'loading', formato: 'normal' })
    expect(screen.getByRole('button', { name: 'Exportar XLSX (Normal)' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Exportar XLSX (Normal)' })).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('button', { name: 'Exportar XLSX (Extenso)' })).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent(/Generando Acta de Entrega/)
  })

  it('tras un error los botones quedan habilitados para reintentar', () => {
    renderSub({ estado: 'error', formato: 'normal', httpStatus: 404 })
    expect(screen.getByRole('button', { name: 'Exportar XLSX (Normal)' })).toBeEnabled()
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('el motivo de deshabilitación queda asociado a los botones', () => {
    renderSub({ estado: 'idle' }, 'No hay actas para exportar con los filtros actuales.')
    expect(screen.getByRole('button', { name: 'Exportar XLSX (Extenso)' })).toHaveAccessibleDescription(
      'No hay actas para exportar con los filtros actuales.',
    )
  })
})
