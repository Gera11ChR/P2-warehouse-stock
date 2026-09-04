import { useState } from 'react'
import Sidebar from '../components/Sidebar'
import Header from '../components/Header'
import SeccionGeneral from '../pages/SeccionGeneral'
import FibraOptica from '../pages/FibraOptica'
import InventarioPorEquipos from '../pages/InventarioPorEquipos'
import Transferencias from '../pages/Transferencias'
import Reportes from '../pages/Reportes'
import Auditoria from '../pages/Auditoria'
import type { NavigationTarget } from '../types'

const LABELS: Record<string, string> = {
  'seccion-general': 'Sección General',
  'fibra-optica': 'Fibra Óptica',
  'inventario-por-equipos': 'Inventario por Equipos',
  transferencias: 'Transferencias',
  reportes: 'Reportes',
  auditoria: 'Auditoría',
}

export default function MainLayout() {
  const [route, setRoute] = useState<NavigationTarget>({
    page: 'seccion-general',
  })
  const [globalSearch, setGlobalSearch] = useState('')

  const handleSearch = (term: string) => {
    setGlobalSearch(term)
    setRoute({ page: 'seccion-general' })
  }

  const breadcrumb = route.sub
    ? `${LABELS[route.page] ?? ''} / ${route.sub === 'paquete' ? 'Paquete' : 'En Uso'}`
    : LABELS[route.page] ?? ''

  return (
    <div className="flex h-screen overflow-hidden bg-slate-100">
      <Sidebar current={route} onNavigate={setRoute} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Header breadcrumb={breadcrumb} onSearch={handleSearch} />
        <main className="flex-1 overflow-y-auto p-6">
          {route.page === 'seccion-general' && (
            <SeccionGeneral globalSearch={globalSearch} />
          )}
          {route.page === 'fibra-optica' && (
            <FibraOptica sub={route.sub ?? 'paquete'} />
          )}
          {route.page === 'inventario-por-equipos' && <InventarioPorEquipos />}
          {route.page === 'transferencias' && <Transferencias />}
          {route.page === 'reportes' && <Reportes />}
          {route.page === 'auditoria' && <Auditoria />}
        </main>
      </div>
    </div>
  )
}
