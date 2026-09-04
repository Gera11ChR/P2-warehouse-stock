import { useEffect, useState } from 'react'
import { listAudit } from '../services/audit'
import { ACCIONES_AUDITORIA } from '../types'
import type { AuditLogItem } from '../types'

function formatDate(value: string): string {
  return new Date(value).toLocaleString('es-MX')
}

export default function Auditoria() {
  const [items, setItems] = useState<AuditLogItem[]>([])

  useEffect(() => {
    listAudit().then(setItems)
  }, [])

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3">Fecha</th>
            <th className="px-4 py-3">Acción</th>
            <th className="px-4 py-3">Actor</th>
            <th className="px-4 py-3">Detalles</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((item) => (
            <tr key={item.log_id}>
              <td className="px-4 py-3 text-slate-500">
                {formatDate(item.created_at)}
              </td>
              <td className="px-4 py-3">
                <span className="inline-flex rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-700">
                  {ACCIONES_AUDITORIA[item.action] ?? item.action}
                </span>
              </td>
              <td className="px-4 py-3 text-slate-700">{item.actor}</td>
              <td className="max-w-xs truncate px-4 py-3 font-mono text-xs text-slate-500">
                {item.details ? JSON.stringify(item.details) : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
