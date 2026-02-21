// Zustand store for Broadcasts (Рассылки)

import { create } from 'zustand'
import { api } from '@/services/api'
import type { Broadcast, BroadcastUser, BroadcastRecipient, CreateBroadcastDto, BroadcastTargetType, BroadcastStats, StatUser } from '@/types'

interface BroadcastStore {
  // State
  broadcasts: Broadcast[]
  currentBroadcast: Broadcast | null
  users: BroadcastUser[]
  recipients: BroadcastRecipient[]
  recipientPreviewCount: number | null
  stats: BroadcastStats | null
  statUsers: StatUser[]
  isLoading: boolean
  isSending: boolean
  error: string | null

  // Actions
  fetchBroadcasts: () => Promise<void>
  createBroadcast: (data: CreateBroadcastDto) => Promise<Broadcast | null>
  updateBroadcast: (id: number, data: Partial<CreateBroadcastDto>) => Promise<boolean>
  deleteBroadcast: (id: number) => Promise<boolean>
  sendBroadcast: (id: number) => Promise<boolean>
  scheduleBroadcast: (id: number, scheduledAt: string) => Promise<boolean>
  cancelBroadcast: (id: number) => Promise<boolean>
  fetchUsers: () => Promise<void>
  fetchRecipients: (id: number, status?: string) => Promise<void>
  previewCount: (data: {
    target_type: BroadcastTargetType
    target_invite_link_id?: number | null
    target_funnel_id?: string | null
    target_stage_key?: string | null
    target_user_ids?: number[] | null
  }) => Promise<void>
  uploadPhoto: (file: File) => Promise<string | null>
  selectBroadcast: (broadcast: Broadcast | null) => void
  refreshBroadcast: (id: number) => Promise<void>
  fetchStats: (id: number) => Promise<void>
  fetchStatUsers: (id: number, type: 'button' | 'poll', key: string) => Promise<void>
  clearError: () => void
}

export const useBroadcastStore = create<BroadcastStore>()((set, get) => ({
  broadcasts: [],
  currentBroadcast: null,
  users: [],
  recipients: [],
  recipientPreviewCount: null,
  stats: null,
  statUsers: [],
  isLoading: false,
  isSending: false,
  error: null,

  fetchBroadcasts: async () => {
    set({ isLoading: true, error: null })
    try {
      const data = await api.getBroadcasts()
      set({ broadcasts: data.broadcasts, isLoading: false })
    } catch (e) {
      set({ error: String(e), isLoading: false })
    }
  },

  createBroadcast: async (data: CreateBroadcastDto) => {
    try {
      const broadcast = await api.createBroadcast(data)
      set((state) => ({
        broadcasts: [broadcast, ...state.broadcasts],
        currentBroadcast: broadcast,
      }))
      return broadcast
    } catch (e) {
      set({ error: String(e) })
      return null
    }
  },

  updateBroadcast: async (id: number, data: Partial<CreateBroadcastDto>) => {
    try {
      const updated = await api.updateBroadcast(id, data)
      set((state) => ({
        broadcasts: state.broadcasts.map((b) => (b.id === id ? updated : b)),
        currentBroadcast: state.currentBroadcast?.id === id ? updated : state.currentBroadcast,
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  deleteBroadcast: async (id: number) => {
    try {
      await api.deleteBroadcast(id)
      set((state) => ({
        broadcasts: state.broadcasts.filter((b) => b.id !== id),
        currentBroadcast: state.currentBroadcast?.id === id ? null : state.currentBroadcast,
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  sendBroadcast: async (id: number) => {
    set({ isSending: true })
    try {
      await api.sendBroadcast(id)
      // Обновляем рассылку после запуска
      await get().refreshBroadcast(id)
      set({ isSending: false })
      return true
    } catch (e) {
      set({ error: String(e), isSending: false })
      return false
    }
  },

  scheduleBroadcast: async (id: number, scheduledAt: string) => {
    try {
      const updated = await api.scheduleBroadcast(id, scheduledAt)
      set((state) => ({
        broadcasts: state.broadcasts.map((b) => (b.id === id ? updated : b)),
        currentBroadcast: state.currentBroadcast?.id === id ? updated : state.currentBroadcast,
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  cancelBroadcast: async (id: number) => {
    try {
      await api.cancelBroadcast(id)
      await get().refreshBroadcast(id)
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  fetchUsers: async () => {
    try {
      const data = await api.getBroadcastUsers()
      set({ users: data.users })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  fetchRecipients: async (id: number, status?: string) => {
    try {
      const data = await api.getBroadcastRecipients(id, status)
      set({ recipients: data.recipients })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  previewCount: async (data) => {
    try {
      const result = await api.previewBroadcastCount(data)
      set({ recipientPreviewCount: result.count })
    } catch (e) {
      set({ recipientPreviewCount: null })
    }
  },

  uploadPhoto: async (file: File) => {
    try {
      const result = await api.uploadBroadcastPhoto(file)
      return result.photo_path
    } catch (e) {
      set({ error: String(e) })
      return null
    }
  },

  selectBroadcast: (broadcast: Broadcast | null) => {
    set({ currentBroadcast: broadcast, recipients: [] })
  },

  refreshBroadcast: async (id: number) => {
    try {
      const broadcast = await api.getBroadcast(id)
      set((state) => ({
        broadcasts: state.broadcasts.map((b) => (b.id === id ? broadcast : b)),
        currentBroadcast: state.currentBroadcast?.id === id ? broadcast : state.currentBroadcast,
      }))
    } catch {
      // ignore
    }
  },

  fetchStats: async (id: number) => {
    try {
      const stats = await api.getBroadcastStats(id)
      set({ stats })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  fetchStatUsers: async (id: number, type: 'button' | 'poll', key: string) => {
    try {
      const data = await api.getBroadcastStatUsers(id, type, key)
      set({ statUsers: data.users })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  clearError: () => set({ error: null }),
}))
