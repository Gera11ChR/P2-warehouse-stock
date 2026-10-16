import { describe, expect, it } from 'vitest'
import { TIPOS_ACCION_AUDITORIA } from '../../types'

// REQ-P2-CON-001: mapeo en lectura de eventos legacy (ledger inmutable) y
// etiquetas de los eventos nuevos del cambio.
describe('Etiquetas de auditoría', () => {
  it('etiqueta los eventos nuevos del cambio', () => {
    for (const tipo of [
      'SUMA_CANTIDAD',
      'MOVIMIENTO_INVENTARIO',
      'AGREGAR_TODO',
      'SEGUIMIENTO_CREADO',
      'SEGUIMIENTO_CERRADO',
      'ACTA_ENTREGA_GENERADA',
      'ACTA_CONSUMO_GENERADA',
    ]) {
      expect(TIPOS_ACCION_AUDITORIA[tipo]).toBeTruthy()
    }
  })

  it('etiqueta la purga del legado FO (PURGA_LEGACY_FO) y el cambio de Valor Unitario (MATERIAL_MODIFICADO) con la nomenclatura oficial', () => {
    expect(TIPOS_ACCION_AUDITORIA.PURGA_LEGACY_FO).toBe('Purga del legado FO')
    expect(TIPOS_ACCION_AUDITORIA.MATERIAL_MODIFICADO).toBe('Material modificado')
    for (const etiqueta of [
      TIPOS_ACCION_AUDITORIA.PURGA_LEGACY_FO,
      TIPOS_ACCION_AUDITORIA.MATERIAL_MODIFICADO,
    ]) {
      expect(etiqueta).not.toMatch(/paquete|en uso/i)
    }
  })

  it('mapea en lectura los eventos DESPLIEGUE_* históricos sin mostrar la nomenclatura legacy', () => {
    expect(TIPOS_ACCION_AUDITORIA.DESPLIEGUE_CREADO).toBe('Seguimiento creado (histórico)')
    expect(TIPOS_ACCION_AUDITORIA.DESPLIEGUE_CERRADO).toBe('Seguimiento cerrado (histórico)')
    for (const label of Object.values(TIPOS_ACCION_AUDITORIA)) {
      expect(label).not.toMatch(/despliegue/i)
    }
  })
})
