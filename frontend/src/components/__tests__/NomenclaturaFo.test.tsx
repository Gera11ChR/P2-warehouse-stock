import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import Sidebar from '../Sidebar'
import { etiquetaSeccion, etiquetaSeccionPorId } from '../../utils/seccionLabel'

// RF-10 / REQ-FO-003: la locación única de fibra óptica se llama «Inventario
// FO» en toda superficie visible. Los nombres «Paquete», «En Uso», «FO
// Paquete» y «FO En Uso» como nombre de inventario hacen fallar el barrido;
// los comentarios y la U.M. «PAQUETE (100 PZ)» quedan exentos.

const fuentes = import.meta.glob('../../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

const NOMBRE_DEPRECADO = /\bFO\s+(Paquete|En Uso)\b|\b(Paquete|En Uso)\b|Fibra Óptica\s*[-—]\s*(Paquete|En Uso)/

function sinComentarios(src: string): string {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:'"`\\])\/\/.*$/gm, '$1')
}

function candidatos(src: string): string[] {
  const limpio = sinComentarios(src)
  const out: string[] = []
  for (const m of limpio.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)) {
    out.push(m[1] ?? m[2] ?? m[3] ?? '')
  }
  for (const m of limpio.matchAll(/>([^<>{}\n][^<>{}]*)</g)) out.push(m[1])
  for (const m of limpio.matchAll(/^\s+([A-Za-zÁÉÍÓÚÑáéíóúñ¿¡][^\n]*)$/gm)) {
    if (/^(if|const|let|return|for|while|else|await|throw|set\w*)\b/.test(m[1])) continue
    if (!/[=;{}<>|&:[\]]|,$/.test(m[1])) out.push(m[1])
  }
  return out
}

/** ¿El texto usa un nombre deprecado de inventario? (excepciones: U.M.
 *  «PAQUETE (100 PZ)», que es una unidad de medida y no un inventario). */
function esNombreDeprecado(valor: string): boolean {
  const v = valor.replace(/\$\{[^}]*\}/g, '').trim()
  if (/^PAQUETE \(100 PZ\)$/.test(v)) return false
  return NOMBRE_DEPRECADO.test(v)
}

describe('Nomenclatura oficial: Inventario FO (RF-10)', () => {
  it('el barrido encuentra el código fuente de la aplicación', () => {
    const rutas = Object.keys(fuentes)
    expect(rutas.some((r) => r.endsWith('pages/FibraOptica.tsx'))).toBe(true)
    expect(rutas.some((r) => r.endsWith('Sidebar.tsx') && !r.includes('.test.'))).toBe(true)
  })

  it('ningún texto visible usa «Paquete», «En Uso», «FO Paquete» ni «FO En Uso» como nombre de inventario', () => {
    const ofensores: string[] = []
    for (const [ruta, src] of Object.entries(fuentes)) {
      if (/__tests__|\.test\.|\/test\//.test(ruta)) continue
      for (const c of candidatos(src)) {
        if (esNombreDeprecado(c)) ofensores.push(`${ruta}: ${c.trim()}`)
      }
    }
    expect(ofensores).toEqual([])
  })

  it('el detector reconoce los nombres deprecados y respeta las excepciones', () => {
    // Casos positivos: el detector DEBE disparar.
    for (const texto of [
      'Paquete',
      'En Uso',
      'FO Paquete',
      'FO En Uso',
      'Fibra Óptica - Paquete',
      'Fibra Óptica - En Uso',
      'Inventario FO En Uso',
    ]) {
      expect(esNombreDeprecado(texto)).toBe(true)
    }
    // Excepciones: U.M., nombre oficial y frase común.
    for (const texto of [
      'PAQUETE (100 PZ)',
      'Inventario FO',
      'clave de operación en uso por otro usuario',
    ]) {
      expect(esNombreDeprecado(texto)).toBe(false)
    }
  })
})

describe('Navegación: una sola entrada «Inventario FO» sin subentradas (RF-1, RF-10)', () => {
  it('el Sidebar ofrece «Inventario FO» y ningún «Paquete»/«En Uso»', () => {
    render(<Sidebar current={{ page: 'seccion-general' }} onNavigate={vi.fn()} />)

    const nav = screen.getByRole('navigation')
    const entradas = within(nav).getAllByRole('button')
    const etiquetas = entradas.map((b) => b.textContent?.trim())

    expect(etiquetas.filter((t) => t === 'Inventario FO')).toHaveLength(1)
    expect(within(nav).queryByText(/paquete/i)).not.toBeInTheDocument()
    expect(within(nav).queryByText(/en uso/i)).not.toBeInTheDocument()
    expect(within(nav).queryByText(/fibra óptica/i)).not.toBeInTheDocument()
  })

  it('«Inventario FO» navega a la página fibra-optica sin `sub`', () => {
    const onNavigate = vi.fn()
    render(<Sidebar current={{ page: 'seccion-general' }} onNavigate={onNavigate} />)

    screen.getByRole('button', { name: 'Inventario FO' }).click()
    expect(onNavigate).toHaveBeenCalledWith({ page: 'fibra-optica', sub: undefined })
  })
})

describe('Etiquetas de secciones (RF-5)', () => {
  it('la sección FO se muestra como «Inventario FO»; GENERAL con el nombre del almacén', () => {
    expect(etiquetaSeccion({ tipo: 'FO', nombre: 'Inventario FO' })).toBe('Inventario FO')
    expect(etiquetaSeccion({ tipo: 'GENERAL', nombre: 'Almacén Central' })).toBe('Almacén Central')
  })

  it('un id de sección desconocido se rotula «Sección #id», nunca «Inventario FO»', () => {
    const secciones = [
      { almacen_id: 1, tipo: 'GENERAL', nombre: 'Almacén Central' },
      { almacen_id: 2, tipo: 'FO', nombre: 'Inventario FO' },
    ]
    expect(etiquetaSeccionPorId(1, secciones)).toBe('Almacén Central')
    expect(etiquetaSeccionPorId(2, secciones)).toBe('Inventario FO')
    expect(etiquetaSeccionPorId(99, secciones)).toBe('Sección #99')
    expect(etiquetaSeccionPorId(null, secciones)).toBe('—')
  })
})
