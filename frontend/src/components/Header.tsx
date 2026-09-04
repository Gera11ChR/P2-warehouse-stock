import { useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'

interface HeaderProps {
  breadcrumb: string
  onSearch: (term: string) => void
}

export default function Header({ breadcrumb, onSearch }: HeaderProps) {
  const [term, setTerm] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  return (
    <header className="flex h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6">
      <nav className="text-sm text-slate-500">
        <span>Dashboard</span>
        <span className="mx-2 text-slate-300">/</span>
        <span className="font-medium text-slate-800">{breadcrumb}</span>
      </nav>
      <div className="relative w-full max-w-md">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          ref={inputRef}
          type="text"
          value={term}
          onChange={(event) => {
            setTerm(event.target.value)
            onSearch(event.target.value)
          }}
          placeholder="Buscar materiales, SKU o descripción..."
          className="w-full rounded-md border border-slate-300 py-2 pl-9 pr-16 text-sm focus:border-blue-500 focus:outline-none"
        />
        <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
          Ctrl + K
        </span>
      </div>
    </header>
  )
}
