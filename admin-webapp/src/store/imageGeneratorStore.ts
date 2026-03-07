import { create } from 'zustand'
import { api } from '@/services/api'
import type { ImageGeneration, ImageGeneratorPreset } from '@/types'

interface ImageGeneratorState {
  // History
  generations: ImageGeneration[]
  total: number
  isLoading: boolean

  // Presets
  presets: ImageGeneratorPreset[]

  // Current generation
  currentGeneration: ImageGeneration | null
  isGenerating: boolean

  // Actions
  fetchHistory: (params?: { limit?: number; offset?: number; preset?: string }) => Promise<void>
  fetchPresets: () => Promise<void>
  setCurrentGeneration: (gen: ImageGeneration | null) => void
  updateCurrentGeneration: (updates: Partial<ImageGeneration>) => void
  setIsGenerating: (v: boolean) => void
  deleteGeneration: (id: number) => Promise<boolean>
}

export const useImageGeneratorStore = create<ImageGeneratorState>()((set, get) => ({
  generations: [],
  total: 0,
  isLoading: false,
  presets: [],
  currentGeneration: null,
  isGenerating: false,

  fetchHistory: async (params) => {
    set({ isLoading: true })
    try {
      const data = await api.getImageHistory(params)
      set({ generations: data.generations, total: data.total, isLoading: false })
    } catch (error) {
      console.error('Failed to fetch image history:', error)
      set({ isLoading: false })
    }
  },

  fetchPresets: async () => {
    try {
      const data = await api.getImageGeneratorPresets()
      set({ presets: data.presets })
    } catch (error) {
      console.error('Failed to fetch presets:', error)
    }
  },

  setCurrentGeneration: (gen) => set({ currentGeneration: gen }),

  updateCurrentGeneration: (updates) => {
    const current = get().currentGeneration
    if (current) {
      set({ currentGeneration: { ...current, ...updates } })
    }
  },

  setIsGenerating: (v) => set({ isGenerating: v }),

  deleteGeneration: async (id) => {
    try {
      await api.deleteImageGeneration(id)
      set((state) => ({
        generations: state.generations.filter((g) => g.id !== id),
        total: state.total - 1,
      }))
      return true
    } catch (error) {
      console.error('Failed to delete generation:', error)
      return false
    }
  },
}))
