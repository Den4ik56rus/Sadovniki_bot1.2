// Article Presentation Batch Store — Zustand store for batch presentation generation from articles
import { create } from 'zustand'
import { api } from '@/services/api'
import type { BatchListItem, Batch, BatchProgressEvent } from '@/types'

interface ArticlePresentationBatchStore {
  // List
  batches: BatchListItem[]
  total: number
  isLoading: boolean

  // Current batch detail
  currentBatch: Batch | null
  isLoadingDetail: boolean

  // Progress tracking
  progressEvent: BatchProgressEvent | null

  // Actions
  fetchBatches: () => Promise<void>
  fetchBatch: (id: number) => Promise<void>
  cancelBatch: (id: number) => Promise<void>
  deleteBatch: (id: number) => Promise<void>
  setProgressEvent: (event: BatchProgressEvent | null) => void
  clearCurrentBatch: () => void
}

export const useArticlePresentationBatchStore = create<ArticlePresentationBatchStore>((set, get) => ({
  batches: [],
  total: 0,
  isLoading: false,
  currentBatch: null,
  isLoadingDetail: false,
  progressEvent: null,

  fetchBatches: async () => {
    set({ isLoading: true })
    try {
      const res = await api.getArticlePresentationBatches({ limit: 50 })
      set({ batches: res.batches, total: res.total })
    } catch (err) {
      console.error('Failed to fetch article presentation batches:', err)
    } finally {
      set({ isLoading: false })
    }
  },

  fetchBatch: async (id: number) => {
    set({ isLoadingDetail: true })
    try {
      const batch = await api.getArticlePresentationBatch(id)
      set({ currentBatch: batch })
    } catch (err) {
      console.error('Failed to fetch article presentation batch:', err)
    } finally {
      set({ isLoadingDetail: false })
    }
  },

  cancelBatch: async (id: number) => {
    try {
      await api.cancelArticlePresentationBatch(id)
      await get().fetchBatches()
      if (get().currentBatch?.id === id) {
        await get().fetchBatch(id)
      }
    } catch (err) {
      console.error('Failed to cancel article presentation batch:', err)
    }
  },

  deleteBatch: async (id: number) => {
    try {
      await api.deleteArticlePresentationBatch(id)
      set(state => ({
        batches: state.batches.filter(b => b.id !== id),
        currentBatch: state.currentBatch?.id === id ? null : state.currentBatch,
      }))
    } catch (err) {
      console.error('Failed to delete article presentation batch:', err)
    }
  },

  setProgressEvent: (event) => set({ progressEvent: event }),

  clearCurrentBatch: () => set({ currentBatch: null, progressEvent: null }),
}))
