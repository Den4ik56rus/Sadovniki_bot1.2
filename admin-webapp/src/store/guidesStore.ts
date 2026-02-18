// Zustand store for Guides (Готовые решения — PDF-гайды)

import { create } from 'zustand'
import { api } from '@/services/api'
import type { GuideOrder, GuideStats } from '@/types'

interface GuidesStore {
  // State
  orders: GuideOrder[]
  total: number
  stats: GuideStats | null
  expandedId: number | null
  isLoading: boolean
  error: string | null
  statusFilter: string | undefined

  // Actions
  fetchOrders: (params?: { limit?: number; offset?: number }) => Promise<void>
  fetchStats: () => Promise<void>
  setStatusFilter: (status?: string) => void
  toggleExpanded: (id: number) => void
}

export const useGuidesStore = create<GuidesStore>()((set, get) => ({
  orders: [],
  total: 0,
  stats: null,
  expandedId: null,
  isLoading: false,
  error: null,
  statusFilter: undefined,

  fetchOrders: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const data = await api.getGuideOrders({
        ...params,
        status: get().statusFilter,
      })
      set({ orders: data.orders, total: data.total, isLoading: false })
    } catch (e) {
      set({ error: String(e), isLoading: false })
    }
  },

  fetchStats: async () => {
    try {
      const stats = await api.getGuideStats()
      set({ stats })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  setStatusFilter: (status?: string) => {
    set({ statusFilter: status, expandedId: null })
    get().fetchOrders()
  },

  toggleExpanded: (id: number) => {
    set((state) => ({
      expandedId: state.expandedId === id ? null : id,
    }))
  },
}))
