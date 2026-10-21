import {
  ArrowRightLeft,
  Boxes,
  Cable,
  FileBarChart,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import logoDms from '../assets/company_logobrand.png'
import type { NavigationTarget } from '../types'

interface NavItem {
  label: string
  page: string
  sub?: string
  icon: typeof Boxes
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Sección General', page: 'seccion-general', icon: Boxes },
  // RF-1/RF-10: una sola entrada, sin subentradas. La ruta interna
  // `fibra-optica` se conserva (identificador técnico, no texto visible).
  { label: 'Inventario FO', page: 'fibra-optica', icon: Cable },
  { label: 'Inventario por Unidad', page: 'inventario-por-equipos', icon: Wrench },
  { label: 'Transferencias', page: 'transferencias', icon: ArrowRightLeft },
  { label: 'Reportes', page: 'reportes', icon: FileBarChart },
  { label: 'Auditoría', page: 'auditoria', icon: ShieldCheck },
]

interface SidebarProps {
  current: NavigationTarget
  onNavigate: (target: NavigationTarget) => void
}

export default function Sidebar({ current, onNavigate }: SidebarProps) {
  const isActive = (item: NavItem) =>
    current.page === item.page && current.sub === (item.sub ?? current.sub)

  return (
    <aside className="flex h-screen w-14 shrink-0 flex-col bg-slate-900 text-slate-200 md:w-64">
      {/* Marca corporativa (REQ-P2-UI-001): logo en la esquina superior izquierda.
          El PNG es transparente con trazos negros: se asienta sobre una ficha
          clara para conservar el contraste en el sidebar oscuro. */}
      <div className="flex h-16 items-center justify-center gap-2 border-b border-slate-700 px-1 md:justify-start md:px-3">
        <span className="flex shrink-0 items-center rounded-md bg-white px-1 py-1 md:px-1.5">
          <img
            src={logoDms}
            alt="Logotipo corporativo DMS Telecom"
            width={1080}
            height={413}
            className="h-5 w-auto md:h-8"
          />
        </span>
        {/* Shell responsivo (T9, Etapa 3): bajo `md` la sidebar es compacta y
            solo muestra iconos; el nombre accesible se conserva con sr-only. */}
        <span className="sr-only text-base font-semibold text-white md:not-sr-only">
          DMS - TELECOM
        </span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-1.5 md:p-3">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item)
          const Icon = item.icon
          return (
            <div key={item.label}>
              <button
                type="button"
                onClick={() => onNavigate({ page: item.page, sub: item.sub })}
                title={item.label}
                className={`flex w-full items-center justify-center gap-3 rounded-md px-2 py-2 text-sm font-medium transition-colors md:justify-start md:px-3 ${
                  active ? 'bg-blue-600 text-white' : 'hover:bg-slate-800'
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="sr-only md:not-sr-only">{item.label}</span>
              </button>
            </div>
          )
        })}
      </nav>
    </aside>
  )
}
