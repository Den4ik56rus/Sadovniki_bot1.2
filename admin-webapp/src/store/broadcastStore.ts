// Zustand store for Broadcasts (Рассылки)

import { create } from 'zustand'
import { api } from '@/services/api'
import type { Broadcast, BroadcastUser, BroadcastRecipient, CreateBroadcastDto, BroadcastTargetType, BroadcastStats, StatUser, BroadcastRun } from '@/types'

interface BroadcastStore {
  // State
  broadcasts: Broadcast[]
  currentBroadcast: Broadcast | null
  selectedIds: Set<number>
  users: BroadcastUser[]
  recipients: BroadcastRecipient[]
  recipientPreviewCount: number | null
  stats: BroadcastStats | null
  statUsers: StatUser[]
  isLoading: boolean
  isSending: boolean
  isTestSending: boolean
  error: string | null

  // Runs state
  runs: BroadcastRun[]
  currentRunId: number | null

  // Actions
  fetchBroadcasts: () => Promise<void>
  createBroadcast: (data: CreateBroadcastDto) => Promise<Broadcast | null>
  updateBroadcast: (id: number, data: Partial<CreateBroadcastDto>) => Promise<boolean>
  deleteBroadcast: (id: number) => Promise<boolean>
  deleteBroadcastsBulk: () => Promise<boolean>
  toggleSelect: (id: number) => void
  selectAll: () => void
  clearSelection: () => void
  sendBroadcast: (id: number) => Promise<boolean>
  testSendBroadcast: (id: number) => Promise<boolean>
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

  // Reminder actions
  cancelReminder: (broadcastId: number, reminderId: number) => Promise<boolean>

  // Runs actions
  fetchRuns: (broadcastId: number) => Promise<void>
  resendBroadcast: (id: number, data: {
    target_type: BroadcastTargetType
    target_invite_link_id?: number | null
    target_funnel_id?: string | null
    target_stage_key?: string | null
    target_user_ids?: number[] | null
  }) => Promise<boolean>
  setCurrentRun: (runId: number | null) => void
  fetchRunStats: (broadcastId: number, runId: number) => Promise<void>
  fetchRunStatUsers: (broadcastId: number, runId: number, type: 'button' | 'poll', key: string) => Promise<void>
}

export const useBroadcastStore = create<BroadcastStore>()((set, get) => ({
  broadcasts: [],
  currentBroadcast: null,
  selectedIds: new Set<number>(),
  users: [],
  recipients: [],
  recipientPreviewCount: null,
  stats: null,
  statUsers: [],
  isLoading: false,
  isSending: false,
  isTestSending: false,
  error: null,
  runs: [],
  currentRunId: null,

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

  deleteBroadcastsBulk: async () => {
    const ids = Array.from(get().selectedIds)
    if (ids.length === 0) return false
    try {
      await api.deleteBroadcastsBulk(ids)
      const deletedSet = new Set(ids)
      set((state) => ({
        broadcasts: state.broadcasts.filter((b) => !deletedSet.has(b.id)),
        currentBroadcast: state.currentBroadcast && deletedSet.has(state.currentBroadcast.id) ? null : state.currentBroadcast,
        selectedIds: new Set<number>(),
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  toggleSelect: (id: number) => {
    set((state) => {
      const next = new Set(state.selectedIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { selectedIds: next }
    })
  },

  selectAll: () => {
    set((state) => ({
      selectedIds: new Set(state.broadcasts.filter((b) => b.status !== 'sending').map((b) => b.id)),
    }))
  },

  clearSelection: () => set({ selectedIds: new Set<number>() }),

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

  testSendBroadcast: async (id: number) => {
    set({ isTestSending: true })
    try {
      const result = await api.testSendBroadcast(id)
      set({ isTestSending: false })
      return result.success
    } catch (e) {
      set({ error: String(e), isTestSending: false })
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
    set({ currentBroadcast: broadcast, recipients: [], runs: [], currentRunId: null })
    // Подгрузить полные данные (включая reminders) с сервера
    if (broadcast) {
      get().refreshBroadcast(broadcast.id)
    }
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

  // ═══════════════════════════════════════════════════════════════════
  // REMINDERS — напоминалки
  // ═══════════════════════════════════════════════════════════════════

  cancelReminder: async (broadcastId: number, reminderId: number) => {
    try {
      await api.cancelReminder(broadcastId, reminderId)
      await get().refreshBroadcast(broadcastId)
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  // ═══════════════════════════════════════════════════════════════════
  // RUNS — повторные запуски
  // ═══════════════════════════════════════════════════════════════════

  fetchRuns: async (broadcastId: number) => {
    try {
      const data = await api.getBroadcastRuns(broadcastId)
      set({ runs: data.runs })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  resendBroadcast: async (id, data) => {
    set({ isSending: true })
    try {
      await api.resendBroadcast(id, data)
      await get().refreshBroadcast(id)
      await get().fetchRuns(id)
      set({ isSending: false })
      return true
    } catch (e) {
      set({ error: String(e), isSending: false })
      return false
    }
  },

  setCurrentRun: (runId) => {
    set({ currentRunId: runId, stats: null, statUsers: [] })
  },

  fetchRunStats: async (broadcastId, runId) => {
    try {
      const stats = await api.getRunStats(broadcastId, runId)
      set({ stats })
    } catch (e) {
      set({ error: String(e) })
    }
  },

  fetchRunStatUsers: async (broadcastId, runId, type, key) => {
    try {
      const data = await api.getRunStatUsers(broadcastId, runId, type, key)
      set({ statUsers: data.users })
    } catch (e) {
      set({ error: String(e) })
    }
  },
}))
