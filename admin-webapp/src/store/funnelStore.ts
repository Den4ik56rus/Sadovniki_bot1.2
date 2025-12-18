// Zustand store for Unified Funnels

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '@/services/api'
import type { Funnel, FunnelStage, FunnelClient, CreateFunnelDto, CreateStageDto } from '@/types'

interface FunnelStore {
  // State
  funnels: Funnel[]
  currentFunnelId: string | null
  stages: FunnelStage[]
  clients: Record<string, FunnelClient[]>
  stats: Record<string, number>
  isLoading: boolean
  isLoadingClients: boolean
  error: string | null
  isSettingsMode: boolean

  // Funnel actions
  fetchFunnels: () => Promise<void>
  setCurrentFunnel: (funnelId: string) => void
  createFunnel: (data: CreateFunnelDto) => Promise<Funnel | null>
  updateFunnel: (funnelId: string, data: { title?: string; description?: string; icon?: string }) => Promise<void>
  deleteFunnel: (funnelId: string) => Promise<boolean>
  reorderFunnels: (funnelIds: string[]) => Promise<void>

  // Stage actions
  fetchStages: (funnelId: string) => Promise<void>
  createStage: (funnelId: string, data: CreateStageDto) => Promise<FunnelStage | null>
  updateStage: (funnelId: string, stageKey: string, data: { title?: string; color?: string }) => Promise<void>
  deleteStage: (funnelId: string, stageKey: string) => Promise<boolean>
  reorderStages: (funnelId: string, stageKeys: string[]) => Promise<void>

  // Client actions
  fetchClients: (funnelId: string) => Promise<void>
  moveClient: (userId: number, fromStage: string, toStage: string) => void
  transferClient: (userId: number, toFunnelId: string, toStageKey?: string) => Promise<boolean>
  removeClient: (userId: number, fromStage: string) => void

  // Settings mode
  toggleSettingsMode: () => void

  // Reset
  reset: () => void
}

export const useFunnelStore = create<FunnelStore>()(
  persist(
    (set, get) => ({
      // Initial state
      funnels: [],
      currentFunnelId: null,
      stages: [],
      clients: {},
      stats: {},
      isLoading: false,
      isLoadingClients: false,
      error: null,
      isSettingsMode: false,

      // Funnel actions
      fetchFunnels: async () => {
        set({ isLoading: true, error: null })
        try {
          const response = await api.getFunnels()
          set({ funnels: response.funnels, isLoading: false })

          // Auto-select first funnel if none selected AND no persisted funnel
          const state = get()
          if (!state.currentFunnelId && response.funnels.length > 0) {
            get().setCurrentFunnel(response.funnels[0].id)
          } else if (state.currentFunnelId) {
            // Verify persisted funnel still exists, otherwise reset to first
            const funnelExists = response.funnels.some(f => f.id === state.currentFunnelId)
            if (!funnelExists && response.funnels.length > 0) {
              get().setCurrentFunnel(response.funnels[0].id)
            } else if (funnelExists) {
              // Re-fetch stages and clients for persisted funnel
              get().fetchStages(state.currentFunnelId)
              get().fetchClients(state.currentFunnelId)
            }
          }
        } catch (error) {
          set({ error: (error as Error).message, isLoading: false })
        }
      },

      setCurrentFunnel: (funnelId: string) => {
        set({ currentFunnelId: funnelId })
        // Fetch stages and clients for the funnel
        get().fetchStages(funnelId)
        get().fetchClients(funnelId)
      },

      createFunnel: async (data: CreateFunnelDto) => {
        try {
          const funnel = await api.createFunnel(data)
          set((state) => ({
            funnels: [...state.funnels, funnel],
          }))
          return funnel
        } catch (error) {
          set({ error: (error as Error).message })
          return null
        }
      },

      updateFunnel: async (funnelId: string, data) => {
        // Optimistic update
        set((state) => ({
          funnels: state.funnels.map((f) =>
            f.id === funnelId ? { ...f, ...data } : f
          ),
        }))

        try {
          await api.updateFunnel(funnelId, data)
        } catch (error) {
          // Revert on failure
          get().fetchFunnels()
        }
      },

      deleteFunnel: async (funnelId: string) => {
        try {
          const result = await api.deleteFunnel(funnelId)
          if (result.success) {
            set((state) => ({
              funnels: state.funnels.filter((f) => f.id !== funnelId),
              currentFunnelId: state.currentFunnelId === funnelId ? null : state.currentFunnelId,
            }))
            return true
          }
          return false
        } catch (error) {
          set({ error: (error as Error).message })
          return false
        }
      },

      reorderFunnels: async (funnelIds: string[]) => {
        // Optimistic update
        set((state) => ({
          funnels: funnelIds.map((id, idx) => {
            const funnel = state.funnels.find((f) => f.id === id)
            return funnel ? { ...funnel, sort_order: idx } : funnel!
          }).filter(Boolean),
        }))

        try {
          await api.reorderFunnels(funnelIds)
        } catch (error) {
          get().fetchFunnels()
        }
      },

      // Stage actions
      fetchStages: async (funnelId: string) => {
        try {
          const response = await api.getFunnelStages(funnelId)
          set({ stages: response.stages })
        } catch (error) {
          set({ error: (error as Error).message })
        }
      },

      createStage: async (funnelId: string, data: CreateStageDto) => {
        try {
          const stage = await api.createFunnelStage(funnelId, data)
          set((state) => ({
            stages: [...state.stages, stage],
            clients: { ...state.clients, [stage.stage_key]: [] },
            stats: { ...state.stats, [stage.stage_key]: 0 },
          }))
          return stage
        } catch (error) {
          set({ error: (error as Error).message })
          return null
        }
      },

      updateStage: async (funnelId: string, stageKey: string, data) => {
        // Optimistic update
        set((state) => ({
          stages: state.stages.map((s) =>
            s.stage_key === stageKey ? { ...s, ...data } : s
          ),
        }))

        try {
          await api.updateFunnelStage(funnelId, stageKey, data)
        } catch (error) {
          get().fetchStages(funnelId)
        }
      },

      deleteStage: async (funnelId: string, stageKey: string) => {
        try {
          const result = await api.deleteFunnelStage(funnelId, stageKey)
          if (result.success) {
            // Refetch to get updated client positions
            get().fetchStages(funnelId)
            get().fetchClients(funnelId)
            return true
          }
          return false
        } catch (error) {
          set({ error: (error as Error).message })
          return false
        }
      },

      reorderStages: async (funnelId: string, stageKeys: string[]) => {
        // Optimistic update
        set((state) => ({
          stages: stageKeys.map((key, idx) => {
            const stage = state.stages.find((s) => s.stage_key === key)
            return stage ? { ...stage, sort_order: idx } : stage!
          }).filter(Boolean),
        }))

        try {
          await api.reorderFunnelStages(funnelId, stageKeys)
        } catch (error) {
          get().fetchStages(funnelId)
        }
      },

      // Client actions
      fetchClients: async (funnelId: string) => {
        set({ isLoadingClients: true })
        try {
          const response = await api.getFunnelClients(funnelId)
          set({
            clients: response.clients,
            stats: response.stats,
            isLoadingClients: false,
          })
        } catch (error) {
          set({ error: (error as Error).message, isLoadingClients: false })
        }
      },

      moveClient: (userId: number, fromStage: string, toStage: string) => {
        if (fromStage === toStage) return

        const state = get()
        const funnelId = state.currentFunnelId
        if (!funnelId) return

        // Optimistic update
        set((state) => {
          const fromClients = state.clients[fromStage] || []
          const client = fromClients.find((c) => c.id === userId)
          if (!client) return state

          const updatedClient = { ...client, status: toStage }
          const toClients = state.clients[toStage] || []

          return {
            clients: {
              ...state.clients,
              [fromStage]: fromClients.filter((c) => c.id !== userId),
              [toStage]: [updatedClient, ...toClients],
            },
            stats: {
              ...state.stats,
              [fromStage]: (state.stats[fromStage] || 0) - 1,
              [toStage]: (state.stats[toStage] || 0) + 1,
            },
          }
        })

        // Update on server
        api.moveClientStage(funnelId, userId, toStage).catch((error) => {
          console.error('Failed to move client:', error)
          // Revert on failure
          get().fetchClients(funnelId)
        })
      },

      transferClient: async (userId: number, toFunnelId: string, toStageKey?: string) => {
        const state = get()
        const fromFunnelId = state.currentFunnelId
        if (!fromFunnelId) return false

        try {
          const result = await api.transferClient(fromFunnelId, userId, toFunnelId, toStageKey)
          if (result.success) {
            // Remove from current funnel's client list
            set((state) => {
              const newClients = { ...state.clients }
              for (const stage in newClients) {
                newClients[stage] = newClients[stage].filter((c) => c.id !== userId)
              }

              const newStats = { ...state.stats }
              for (const stage in newStats) {
                const clientWasHere = state.clients[stage]?.some((c) => c.id === userId)
                if (clientWasHere) {
                  newStats[stage] = Math.max(0, (newStats[stage] || 0) - 1)
                }
              }

              return { clients: newClients, stats: newStats }
            })
            return true
          }
          return false
        } catch (error) {
          set({ error: (error as Error).message })
          return false
        }
      },

      removeClient: (userId: number, fromStage: string) => {
        const state = get()
        const funnelId = state.currentFunnelId
        if (!funnelId) return

        // Optimistic update
        set((state) => {
          const fromClients = state.clients[fromStage] || []
          return {
            clients: {
              ...state.clients,
              [fromStage]: fromClients.filter((c) => c.id !== userId),
            },
            stats: {
              ...state.stats,
              [fromStage]: Math.max(0, (state.stats[fromStage] || 0) - 1),
            },
          }
        })

        // Update on server
        api.removeClientFromFunnel(funnelId, userId).catch((error) => {
          console.error('Failed to remove client:', error)
          // Revert on failure
          get().fetchClients(funnelId)
        })
      },

      // Settings mode
      toggleSettingsMode: () => set((state) => ({ isSettingsMode: !state.isSettingsMode })),

      // Reset
      reset: () => set({
        funnels: [],
        currentFunnelId: null,
        stages: [],
        clients: {},
        stats: {},
        isLoading: false,
        isLoadingClients: false,
        error: null,
        isSettingsMode: false,
      }),
    }),
    {
      name: 'funnel-storage',
      // Only persist currentFunnelId
      partialize: (state) => ({ currentFunnelId: state.currentFunnelId }),
    }
  )
)
