// Zustand store for Invite Links

import { create } from 'zustand'
import { api } from '@/services/api'
import type { InviteLink, InviteLinksSummary } from '@/types'

interface InviteLinkData {
  name: string
  bonus_tokens: number
  discount_percent: number
  discount_duration_days: number
  max_users: number
}

interface InviteLinksStore {
  // State
  links: InviteLink[]
  summary: InviteLinksSummary | null
  isLoading: boolean
  error: string | null

  // Date filters
  startDate: string | undefined
  endDate: string | undefined

  // Actions
  fetchLinks: () => Promise<void>
  setDateRange: (start?: string, end?: string) => void
  createLink: (data: InviteLinkData) => Promise<boolean>
  updateLink: (id: number, data: InviteLinkData) => Promise<boolean>
  deleteLink: (id: number) => Promise<boolean>
}

export const useInviteLinksStore = create<InviteLinksStore>()((set, get) => ({
  links: [],
  summary: null,
  isLoading: false,
  error: null,
  startDate: undefined,
  endDate: undefined,

  fetchLinks: async () => {
    const { startDate, endDate } = get()
    set({ isLoading: true, error: null })
    try {
      const data = await api.getInviteLinks({
        start_date: startDate,
        end_date: endDate,
      })
      set({ links: data.links, summary: data.summary, isLoading: false })
    } catch (e) {
      set({ error: String(e), isLoading: false })
    }
  },

  setDateRange: (start?: string, end?: string) => {
    set({ startDate: start, endDate: end })
  },

  createLink: async (data: InviteLinkData) => {
    try {
      const link = await api.createInviteLink(data)
      set((state) => ({
        links: [link, ...state.links],
        summary: state.summary
          ? { ...state.summary, total_links: state.summary.total_links + 1 }
          : null,
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  updateLink: async (id: number, data: InviteLinkData) => {
    try {
      const updated = await api.updateInviteLink(id, data)
      set((state) => ({
        links: state.links.map((l) =>
          l.id === id ? { ...l, ...updated } : l
        ),
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  deleteLink: async (id: number) => {
    try {
      await api.deleteInviteLink(id)
      set((state) => ({
        links: state.links.filter((l) => l.id !== id),
      }))
      // Refetch для обновления summary
      get().fetchLinks()
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },
}))
