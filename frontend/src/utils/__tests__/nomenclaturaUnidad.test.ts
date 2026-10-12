import { describe, expect, it } from 'vitest'

// RF-18 / REQ-UNI-021: ningún texto visible del frontend debe contener
// "Equipo"/"Equipos" (nomenclatura oficial: Unidad). El barrido inspecciona
// literales de cadena y texto JSX; ignora comentarios, identificadores,
// rutas de API y la lista blanca de RF-5 / REQ-UNI-005.

const fuentes = import.meta.glob('../../**/*.{ts,tsx}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

/** Lista blanca (REQ-UNI-005): U.M. maestra "EQUIPO" y categoría "Equipos". */
const LISTA_BLANCA = new Set(['EQUIPO', 'Equipos'])

const PALABRA = /\bequipos?\b/i

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
  // Texto JSX multilínea: líneas que no parecen código.
  for (const m of limpio.matchAll(/^\s+([A-Za-zÁÉÍÓÚÑáéíóúñ¿¡][^\n]*)$/gm)) {
    if (/^(if|const|let|return|for|while|else|await|throw|set\w*)\b/.test(m[1])) continue
    if (!/[=;{}<>|&:[\]]|,$/.test(m[1])) out.push(m[1])
  }
  return out
}

function esTextoVisible(valor: string): boolean {
  // Las interpolaciones `${equipo}` son identificadores, no texto.
  const v = valor.replace(/\$\{[^}]*\}/g, '').trim()
  if (!v || LISTA_BLANCA.has(v) || !PALABRA.test(v)) return false
  if (v.includes('/equipos') || v.includes('inventario-por-equipos')) return false
  // Identificadores/ids/keys: una sola palabra en minúscula o con separadores.
  if (!/\s/.test(v) && !/^[A-ZÁÉÍÓÚÑ]/.test(v)) return false
  if (/^[\w./-]+$/.test(v) && /[._/-]/.test(v)) return false
  return true
}

describe('Nomenclatura oficial: Unidad (REQ-UNI-021)', () => {
  it('el barrido encuentra el código fuente de la aplicación', () => {
    const rutas = Object.keys(fuentes)
    expect(rutas.some((r) => r.endsWith('pages/InventarioPorEquipos.tsx'))).toBe(true)
  })

  it('ningún texto visible contiene "Equipo/Equipos" fuera de la lista blanca', () => {
    const ofensores: string[] = []
    for (const [ruta, src] of Object.entries(fuentes)) {
      if (/__tests__|\.test\.|\/test\//.test(ruta)) continue
      for (const c of candidatos(src)) {
        if (esTextoVisible(c)) ofensores.push(`${ruta}: ${c.trim()}`)
      }
    }
    expect(ofensores).toEqual([])
  })

  it('el detector reconoce un texto visible antiguo y respeta la lista blanca', () => {
    expect(esTextoVisible('Crear Equipo')).toBe(true)
    expect(esTextoVisible('Seleccione un equipo')).toBe(true)
    expect(esTextoVisible('EQUIPO')).toBe(false)
    expect(esTextoVisible('Equipos')).toBe(false)
    expect(esTextoVisible('/equipos/5')).toBe(false)
    expect(esTextoVisible('equipo_id')).toBe(false)
  })
})

// RF-14 / REQ-CONSUMO-014: el concepto "Sobrante" no debe quedar en la
// interfaz (texto visible) ni en el código de producción: tipos, esquemas,
// payloads y servicios tampoco usan `sobrante(s)`.
describe('Sin rastro de "sobrante" (REQ-CONSUMO-014)', () => {
  const SOBRANTE = /sobrante/i

  it('ningún texto visible contiene "sobrante"', () => {
    const ofensores: string[] = []
    for (const [ruta, src] of Object.entries(fuentes)) {
      if (/__tests__|\.test\.|\/test\//.test(ruta)) continue
      for (const c of candidatos(src)) {
        if (SOBRANTE.test(c)) ofensores.push(`${ruta}: ${c.trim()}`)
      }
    }
    expect(ofensores).toEqual([])
  })

  it('ni el código de producción (identificadores, tipos, payloads) lo usa', () => {
    const ofensores: string[] = []
    for (const [ruta, src] of Object.entries(fuentes)) {
      if (/__tests__|\.test\.|\/test\//.test(ruta)) continue
      src.split('\n').forEach((linea, i) => {
        if (SOBRANTE.test(linea)) ofensores.push(`${ruta}:${i + 1}: ${linea.trim()}`)
      })
    }
    expect(ofensores).toEqual([])
  })

  it('el detector reconoce un texto visible con "Sobrante"', () => {
    expect(candidatos("const x = 'Sobrante por material'").some((c) => SOBRANTE.test(c))).toBe(true)
  })
})
