import api from './api'
import type { Kpis } from '../types'

export async function getKpis(): Promise<Kpis> {
  const { data } = await api.get<Kpis>('/kpis')
  return data
}
