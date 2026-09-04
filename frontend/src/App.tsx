import MainLayout from './layouts/MainLayout'
import { ToastProvider } from './components/ToastProvider'

function App() {
  return (
    <ToastProvider>
      <MainLayout />
    </ToastProvider>
  )
}

export default App
