import {
  ArrowRightLeft,
  Boxes,
  Cable,
  FileBarChart,
  Package,
  ShieldCheck,
  Wrench,
} from 'lucide-react'
import type { NavigationTarget } from '../types'

interface NavItem {
  label: string
  page: string
  sub?: string
  icon: typeof Boxes
  children?: NavItem[]
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Sección General', page: 'seccion-general', icon: Boxes },
  {
    label: 'Fibra Óptica',
    page: 'fibra-optica',
    icon: Cable,
    children: [
      { label: 'Paquete', page: 'fibra-optica', sub: 'paquete', icon: Package },
      { label: 'En Uso', page: 'fibra-optica', sub: 'en-uso', icon: Wrench },
    ],
  },
  { label: 'Inventario por Equipos', page: 'inventario-por-equipos', icon: Wrench },
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
    <aside className="flex h-screen w-64 shrink-0 flex-col bg-slate-900 text-slate-200">
      <div className="flex h-16 items-center gap-2 border-b border-slate-700 px-5">
        <Cable className="h-6 w-6 text-blue-400" />
        <span className="text-lg font-semibold text-white">P2 WMS</span>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {NAV_ITEMS.map((item) => {
          const active = isActive(item)
          const Icon = item.icon
          return (
            <div key={item.label}>
              <button
                type="button"
                onClick={() => onNavigate({ page: item.page, sub: item.sub })}
                className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  active ? 'bg-blue-600 text-white' : 'hover:bg-slate-800'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </button>
              {item.children && (
                <div className="ml-4 mt-1 space-y-1">
                  {item.children.map((child) => {
                    const childActive = isActive(child)
                    const ChildIcon = child.icon
                    return (
                      <button
                        key={child.label}
                        type="button"
                        onClick={() =>
                          onNavigate({ page: child.page, sub: child.sub })
                        }
                        className={`flex w-full items-center gap-3 rounded-md px-3 py-1.5 text-sm transition-colors ${
                          childActive
                            ? 'bg-blue-600 text-white'
                            : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
                        }`}
                      >
                        <ChildIcon className="h-3.5 w-3.5" />
                        <span>{child.label}</span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </nav>
    </aside>
  )
}
