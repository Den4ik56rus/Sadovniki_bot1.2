import { create } from 'zustand'
import { api } from '@/services/api'
import type {
  AutomationTrigger,
  TriggerLogEntry,
  CreateTriggerDto,
  TriggerEventType,
} from '@/types'

interface TriggerState {
  triggers: AutomationTrigger[]
  currentTrigger: AutomationTrigger | null
  triggerLog: TriggerLogEntry[]
  isLoading: boolean
  error: string | null

  // Фильтры
  filterEventType: TriggerEventType | null
  filterFunnelId: string | null

  // CRUD
  fetchTriggers: () => Promise<void>
  fetchTrigger: (id: number) => Promise<void>
  createTrigger: (data: CreateTriggerDto) => Promise<AutomationTrigger | null>
  updateTrigger: (id: number, data: Partial<CreateTriggerDto> & { is_active?: boolean }) => Promise<boolean>
  deleteTrigger: (id: number) => Promise<boolean>
  toggleTrigger: (id: number, isActive: boolean) => Promise<boolean>

  // Лог
  fetchTriggerLog: (triggerId: number) => Promise<void>

  // Превью
  previewUsers: (conditions: any) => Promise<number>

  // Фильтры
  setFilterEventType: (eventType: TriggerEventType | null) => void
  setFilterFunnelId: (funnelId: string | null) => void
  setCurrentTrigger: (trigger: AutomationTrigger | null) => void
}

export const useTriggerStore = create<TriggerState>((set, get) => ({
  triggers: [],
  currentTrigger: null,
  triggerLog: [],
  isLoading: false,
  error: null,
  filterEventType: null,
  filterFunnelId: null,

  fetchTriggers: async () => {
    set({ isLoading: true, error: null })
    try {
      const { filterEventType, filterFunnelId } = get()
      const params: Record<string, string> = {}
      if (filterEventType) params.event_type = filterEventType
      if (filterFunnelId) params.funnel_id = filterFunnelId
      const data = await api.getAutomationTriggers(params)
      set({ triggers: data.triggers, isLoading: false })
    } catch (e) {
      set({ error: (e as Error).message, isLoading: false })
    }
  },

  fetchTrigger: async (id: number) => {
    try {
      const data = await api.getAutomationTrigger(id)
      set({ currentTrigger: data.trigger })
    } catch (e) {
      set({ error: (e as Error).message })
    }
  },

  createTrigger: async (data: CreateTriggerDto) => {
    try {
      const result = await api.createAutomationTrigger(data)
      await get().fetchTriggers()
      return result.trigger
    } catch (e) {
      set({ error: (e as Error).message })
      return null
    }
  },

  updateTrigger: async (id, data) => {
    try {
      const result = await api.updateAutomationTrigger(id, data)
      // Обновляем в списке
      set(state => ({
        triggers: state.triggers.map(t => t.id === id ? result.trigger : t),
        currentTrigger: state.currentTrigger?.id === id ? result.trigger : state.currentTrigger,
      }))
      return true
    } catch (e) {
      set({ error: (e as Error).message })
      return false
    }
  },

  deleteTrigger: async (id) => {
    try {
      await api.deleteAutomationTrigger(id)
      set(state => ({
        triggers: state.triggers.filter(t => t.id !== id),
        currentTrigger: state.currentTrigger?.id === id ? null : state.currentTrigger,
      }))
      return true
    } catch (e) {
      set({ error: (e as Error).message })
      return false
    }
  },

  toggleTrigger: async (id, isActive) => {
    try {
      const result = await api.toggleAutomationTrigger(id, isActive)
      set(state => ({
        triggers: state.triggers.map(t => t.id === id ? result.trigger : t),
        currentTrigger: state.currentTrigger?.id === id ? result.trigger : state.currentTrigger,
      }))
      return true
    } catch (e) {
      set({ error: (e as Error).message })
      return false
    }
  },

  fetchTriggerLog: async (triggerId) => {
    try {
      const data = await api.getAutomationTriggerLog(triggerId)
      set({ triggerLog: data.log })
    } catch (e) {
      set({ error: (e as Error).message })
    }
  },

  previewUsers: async (conditions) => {
    try {
      const data = await api.previewAutomationTriggerUsers(conditions)
      return data.count
    } catch (e) {
      set({ error: (e as Error).message })
      return 0
    }
  },

  setFilterEventType: (eventType) => {
    set({ filterEventType: eventType })
    get().fetchTriggers()
  },

  setFilterFunnelId: (funnelId) => {
    set({ filterFunnelId: funnelId })
    get().fetchTriggers()
  },

  setCurrentTrigger: (trigger) => set({ currentTrigger: trigger }),
}))
