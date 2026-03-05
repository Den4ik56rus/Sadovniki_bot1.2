// Article Batch Store — Zustand store for batch article generation
import { create } from 'zustand'
import { api } from '@/services/api'
import type { ArticleBatchListItem, ArticleBatch, ArticleBatchProgressEvent } from '@/types'

interface ArticleBatchStore {
  // List
  batches: ArticleBatchListItem[]
  total: number
  isLoading: boolean

  // Current batch detail
  currentBatch: ArticleBatch | null
  isLoadingDetail: boolean

  // Progress tracking
  progressEvent: ArticleBatchProgressEvent | null

  // Actions
  fetchBatches: () => Promise<void>
  fetchBatch: (id: number) => Promise<void>
  cancelBatch: (id: number) => Promise<void>
  deleteBatch: (id: number) => Promise<void>
  setProgressEvent: (event: ArticleBatchProgressEvent | null) => void
  clearCurrentBatch: () => void
}

export const useArticleBatchStore = create<ArticleBatchStore>((set, get) => ({
  batches: [],
  total: 0,
  isLoading: false,
  currentBatch: null,
  isLoadingDetail: false,
  progressEvent: null,

  fetchBatches: async () => {
    set({ isLoading: true })
    try {
      const res = await api.getArticleBatches({ limit: 50 })
      set({ batches: res.batches as unknown as ArticleBatchListItem[], total: res.total })
    } catch (err) {
      console.error('Failed to fetch article batches:', err)
    } finally {
      set({ isLoading: false })
    }
  },

  fetchBatch: async (id: number) => {
    set({ isLoadingDetail: true })
    try {
      const batch = await api.getArticleBatch(id)
      set({ currentBatch: batch as unknown as ArticleBatch })
    } catch (err) {
      console.error('Failed to fetch article batch:', err)
    } finally {
      set({ isLoadingDetail: false })
    }
  },

  cancelBatch: async (id: number) => {
    try {
      await api.cancelArticleBatch(id)
      await get().fetchBatches()
      if (get().currentBatch?.id === id) {
        await get().fetchBatch(id)
      }
    } catch (err) {
      console.error('Failed to cancel article batch:', err)
    }
  },

  deleteBatch: async (id: number) => {
    try {
      await api.deleteArticleBatch(id)
      set(state => ({
        batches: state.batches.filter(b => b.id !== id),
        currentBatch: state.currentBatch?.id === id ? null : state.currentBatch,
      }))
    } catch (err) {
      console.error('Failed to delete article batch:', err)
    }
  },

  setProgressEvent: (event) => set({ progressEvent: event }),

  clearCurrentBatch: () => set({ currentBatch: null, progressEvent: null }),
}))
