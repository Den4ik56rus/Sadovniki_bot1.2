// Zustand store for Moderation Queue + KB Browser

import { create } from 'zustand'
import { api } from '@/services/api'
import type { ModerationItem, ModerationStatus, ModerationStats, KBEntry } from '@/types'

interface ModerationStore {
  // Queue
  items: ModerationItem[]
  total: number
  pendingCount: number
  isLoading: boolean
  error: string | null
  statusFilter: ModerationStatus | 'all'
  currentPage: number

  // Selected item
  selectedItemId: number | null
  selectedItem: ModerationItem | null
  isLoadingItem: boolean

  // AI edit
  aiEditResult: string | null
  isEditingAI: boolean

  // Stats
  stats: ModerationStats | null

  // KB Browser
  kbItems: KBEntry[]
  kbTotal: number
  kbSearch: string
  kbCategoryFilter: string | null
  kbSubcategoryFilter: string | null
  kbPage: number
  isLoadingKB: boolean
  kbCategories: string[]
  kbSubcategories: string[]

  // Active tab
  activeTab: 'queue' | 'kb'

  // Queue actions
  fetchQueue: () => Promise<void>
  fetchItem: (id: number) => Promise<void>
  selectItem: (id: number | null) => void
  setCategory: (id: number, category: string) => Promise<boolean>
  updateAnswer: (id: number, answer: string) => Promise<boolean>
  editAnswerAI: (id: number, instructions: string) => Promise<void>
  clearAIEdit: () => void
  approveItem: (id: number) => Promise<boolean>
  rejectItem: (id: number) => Promise<boolean>
  setStatusFilter: (status: ModerationStatus | 'all') => void
  setPage: (page: number) => void
  fetchStats: () => Promise<void>

  // KB actions
  fetchKBEntries: () => Promise<void>
  setKBSearch: (search: string) => void
  setKBCategoryFilter: (cat: string | null) => void
  setKBSubcategoryFilter: (sub: string | null) => void
  fetchKBOptions: () => Promise<void>
  updateKBEntry: (id: number, data: Partial<KBEntry>) => Promise<boolean>
  setActiveTab: (tab: 'queue' | 'kb') => void
}

const PAGE_SIZE = 30

export const useModerationStore = create<ModerationStore>()((set, get) => ({
  // Queue state
  items: [],
  total: 0,
  pendingCount: 0,
  isLoading: false,
  error: null,
  statusFilter: 'pending',
  currentPage: 0,

  // Selected item
  selectedItemId: null,
  selectedItem: null,
  isLoadingItem: false,

  // AI edit
  aiEditResult: null,
  isEditingAI: false,

  // Stats
  stats: null,

  // KB Browser
  kbItems: [],
  kbTotal: 0,
  kbSearch: '',
  kbCategoryFilter: null,
  kbSubcategoryFilter: null,
  kbPage: 0,
  isLoadingKB: false,
  kbCategories: [],
  kbSubcategories: [],

  activeTab: 'queue',

  // ---------- Queue ----------

  fetchQueue: async () => {
    const { statusFilter, currentPage } = get()
    set({ isLoading: true, error: null })
    try {
      const data = await api.getModerationQueue({
        status: statusFilter,
        limit: PAGE_SIZE,
        offset: currentPage * PAGE_SIZE,
        sort: 'oldest',
      })
      set({
        items: data.items,
        total: data.total,
        pendingCount: data.pending_count,
        isLoading: false,
      })
    } catch (e) {
      set({ error: String(e), isLoading: false })
    }
  },

  fetchItem: async (id: number) => {
    set({ isLoadingItem: true })
    try {
      const item = await api.getModerationItem(id)
      set({ selectedItem: item, selectedItemId: id, isLoadingItem: false })
    } catch {
      set({ isLoadingItem: false })
    }
  },

  selectItem: (id: number | null) => {
    if (id === null) {
      set({ selectedItemId: null, selectedItem: null, aiEditResult: null })
      return
    }
    const item = get().items.find((i) => i.id === id) || null
    set({ selectedItemId: id, selectedItem: item, aiEditResult: null })
    if (!item) get().fetchItem(id)
  },

  setCategory: async (id: number, category: string) => {
    try {
      await api.setModerationCategory(id, category)
      // Обновляем локально
      set((s) => ({
        items: s.items.map((i) => (i.id === id ? { ...i, category_guess: category } : i)),
        selectedItem: s.selectedItem?.id === id
          ? { ...s.selectedItem, category_guess: category }
          : s.selectedItem,
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  updateAnswer: async (id: number, answer: string) => {
    try {
      await api.updateModerationAnswer(id, answer)
      set((s) => ({
        items: s.items.map((i) => (i.id === id ? { ...i, answer } : i)),
        selectedItem: s.selectedItem?.id === id
          ? { ...s.selectedItem, answer }
          : s.selectedItem,
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  editAnswerAI: async (id: number, instructions: string) => {
    set({ isEditingAI: true, aiEditResult: null })
    try {
      const res = await api.editModerationAnswerAI(id, instructions)
      set({ aiEditResult: res.improved_answer, isEditingAI: false })
    } catch (e) {
      set({ error: String(e), isEditingAI: false })
    }
  },

  clearAIEdit: () => set({ aiEditResult: null }),

  approveItem: async (id: number) => {
    try {
      await api.approveModerationItem(id)
      set((s) => ({
        items: s.items.filter((i) => i.id !== id),
        selectedItem: s.selectedItemId === id ? null : s.selectedItem,
        selectedItemId: s.selectedItemId === id ? null : s.selectedItemId,
        pendingCount: Math.max(0, s.pendingCount - 1),
        total: s.total - 1,
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  rejectItem: async (id: number) => {
    try {
      await api.rejectModerationItem(id)
      set((s) => ({
        items: s.items.filter((i) => i.id !== id),
        selectedItem: s.selectedItemId === id ? null : s.selectedItem,
        selectedItemId: s.selectedItemId === id ? null : s.selectedItemId,
        pendingCount: Math.max(0, s.pendingCount - 1),
        total: s.total - 1,
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  setStatusFilter: (status) => {
    set({ statusFilter: status, currentPage: 0, selectedItemId: null, selectedItem: null })
    get().fetchQueue()
  },

  setPage: (page) => {
    set({ currentPage: page })
    get().fetchQueue()
  },

  fetchStats: async () => {
    try {
      const stats = await api.getModerationStats()
      set({ stats, pendingCount: stats.pending_count })
    } catch {
      // Не критично
    }
  },

  // ---------- KB Browser ----------

  fetchKBEntries: async () => {
    const { kbSearch, kbCategoryFilter, kbSubcategoryFilter, kbPage } = get()
    set({ isLoadingKB: true })
    try {
      const data = await api.getKBEntries({
        search: kbSearch || undefined,
        category: kbCategoryFilter || undefined,
        subcategory: kbSubcategoryFilter || undefined,
        limit: PAGE_SIZE,
        offset: kbPage * PAGE_SIZE,
      })
      set({ kbItems: data.items, kbTotal: data.total, isLoadingKB: false })
    } catch (e) {
      set({ error: String(e), isLoadingKB: false })
    }
  },

  setKBSearch: (search) => {
    set({ kbSearch: search, kbPage: 0 })
  },

  setKBCategoryFilter: (cat) => {
    set({ kbCategoryFilter: cat, kbPage: 0 })
    get().fetchKBEntries()
  },

  setKBSubcategoryFilter: (sub) => {
    set({ kbSubcategoryFilter: sub, kbPage: 0 })
    get().fetchKBEntries()
  },

  fetchKBOptions: async () => {
    try {
      const [catRes, subRes] = await Promise.all([
        api.getKBCategories(),
        api.getKBSubcategories(),
      ])
      set({ kbCategories: catRes.categories, kbSubcategories: subRes.subcategories })
    } catch {
      // Не критично
    }
  },

  updateKBEntry: async (id, data) => {
    try {
      const res = await api.updateKBEntry(id, data)
      set((s) => ({
        kbItems: s.kbItems.map((i) => (i.id === id ? { ...i, ...res.entry } : i)),
      }))
      return true
    } catch (e) {
      set({ error: String(e) })
      return false
    }
  },

  setActiveTab: (tab) => {
    set({ activeTab: tab })
    if (tab === 'kb') {
      get().fetchKBEntries()
      get().fetchKBOptions()
    }
  },
}))
