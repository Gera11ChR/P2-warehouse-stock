import { Suspense, lazy, useState } from 'react'
import Sidebar from '../components/Sidebar'
import Header from '../components/Header'
import { NavigationContext } from '../hooks/navigationContext'
import type { NavigationTarget } from '../types'

// Code-splitting por página (Constitución §7.2.2: `vite build` sin advertencias
// de tamaño de chunk). Cada página se descarga al navegar a ella.
const SeccionGeneral = lazy(() => import('../pages/SeccionGeneral'))
const FibraOptica = lazy(() => import('../pages/FibraOptica'))
const InventarioPorEquipos = lazy(() => import('../pages/InventarioPorEquipos'))
const Transferencias = lazy(() => import('../pages/Transferencias'))
const Reportes = lazy(() => import('../pages/Reportes'))
const Auditoria = lazy(() => import('../pages/Auditoria'))

const LABELS: Record<string, string> = {
  'seccion-general': 'Sección General',
  'fibra-optica': 'Inventario FO',
  'inventario-por-equipos': 'Inventario por Unidad',
  transferencias: 'Transferencias',
  reportes: 'Reportes',
  auditoria: 'Auditoría',
}

const SUB_LABELS: Record<string, string> = {
  entrega: 'Entrega',
  consumo: 'Consumo',
  actividades: 'Actividades',
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
    ? `${LABELS[route.page] ?? ''} / ${SUB_LABELS[route.sub] ?? route.sub}`
    : LABELS[route.page] ?? ''

  return (
    <NavigationContext.Provider value={setRoute}>
      <div className="flex h-screen overflow-hidden bg-slate-100">
        <Sidebar current={route} onNavigate={setRoute} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header breadcrumb={breadcrumb} onSearch={handleSearch} />
          <main className="flex-1 overflow-y-auto p-3 md:p-6">
            <Suspense
              fallback={
                <p role="status" className="text-sm text-slate-500">
                  Cargando…
                </p>
              }
            >
              {route.page === 'seccion-general' && (
                <SeccionGeneral globalSearch={globalSearch} />
              )}
              {route.page === 'fibra-optica' && <FibraOptica />}
              {route.page === 'inventario-por-equipos' && <InventarioPorEquipos />}
              {route.page === 'transferencias' && <Transferencias />}
              {route.page === 'reportes' && (
                <Reportes
                  key={`${route.sub ?? ''}-${route.equipoId ?? ''}-${route.actividadId ?? ''}`}
                  initialSub={route.sub}
                  initialEquipoId={route.equipoId}
                  initialActividadId={route.actividadId}
                />
              )}
              {route.page === 'auditoria' && <Auditoria />}
            </Suspense>
          </main>
        </div>
      </div>
    </NavigationContext.Provider>
  )
}
