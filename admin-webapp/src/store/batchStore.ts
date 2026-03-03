// Batch Store — Zustand store for batch presentation generation
import { create } from 'zustand'
import { api } from '@/services/api'
import type { BatchListItem, Batch, BatchProgressEvent } from '@/types'

interface BatchStore {
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
  updateBatchInList: (batch: Partial<BatchListItem> & { id: number }) => void
  clearCurrentBatch: () => void
}

export const useBatchStore = create<BatchStore>((set, get) => ({
  batches: [],
  total: 0,
  isLoading: false,
  currentBatch: null,
  isLoadingDetail: false,
  progressEvent: null,

  fetchBatches: async () => {
    set({ isLoading: true })
    try {
      const res = await api.getBatches({ limit: 50 })
      set({ batches: res.batches, total: res.total })
    } catch (err) {
      console.error('Failed to fetch batches:', err)
    } finally {
      set({ isLoading: false })
    }
  },

  fetchBatch: async (id: number) => {
    set({ isLoadingDetail: true })
    try {
      const batch = await api.getBatch(id)
      set({ currentBatch: batch })
    } catch (err) {
      console.error('Failed to fetch batch:', err)
    } finally {
      set({ isLoadingDetail: false })
    }
  },

  cancelBatch: async (id: number) => {
    try {
      await api.cancelBatch(id)
      // Refresh
      await get().fetchBatches()
      if (get().currentBatch?.id === id) {
        await get().fetchBatch(id)
      }
    } catch (err) {
      console.error('Failed to cancel batch:', err)
    }
  },

  deleteBatch: async (id: number) => {
    try {
      await api.deleteBatch(id)
      set(state => ({
        batches: state.batches.filter(b => b.id !== id),
        currentBatch: state.currentBatch?.id === id ? null : state.currentBatch,
      }))
    } catch (err) {
      console.error('Failed to delete batch:', err)
    }
  },

  setProgressEvent: (event) => set({ progressEvent: event }),

  updateBatchInList: (partial) => {
    set(state => ({
      batches: state.batches.map(b =>
        b.id === partial.id ? { ...b, ...partial } : b
      ),
    }))
  },

  clearCurrentBatch: () => set({ currentBatch: null, progressEvent: null }),
}))
