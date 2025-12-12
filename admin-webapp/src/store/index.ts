// Zustand Stores

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, Topic, ConsultationLog, RecentLog, Stats, EmbeddingStats, View, Document, Message } from '@/types'
import { api } from '@/services/api'

// UI Store with persistence
interface UIState {
  currentView: View
  selectedUserId: number | null
  selectedTopicId: number | null
  isLiveFeedPaused: boolean
  setView: (view: View) => void
  selectUser: (userId: number | null) => void
  selectTopic: (topicId: number | null) => void
  toggleLiveFeed: () => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      currentView: 'users',
      selectedUserId: null,
      selectedTopicId: null,
      isLiveFeedPaused: false,
      setView: (view) => set({ currentView: view }),
      selectUser: (userId) => set({ selectedUserId: userId, selectedTopicId: null }),
      selectTopic: (topicId) => set({ selectedTopicId: topicId }),
      toggleLiveFeed: () => set((state) => ({ isLiveFeedPaused: !state.isLiveFeedPaused })),
    }),
    {
      name: 'admin-ui-state',
      partialize: (state) => ({
        currentView: state.currentView,
        selectedUserId: state.selectedUserId,
        selectedTopicId: state.selectedTopicId,
      }),
    }
  )
)

// Users Store
interface UsersState {
  users: User[]
  total: number
  isLoading: boolean
  error: string | null
  searchQuery: string
  fetchUsers: (search?: string) => Promise<void>
  setSearchQuery: (query: string) => void
}

export const useUsersStore = create<UsersState>((set) => ({
  users: [],
  total: 0,
  isLoading: false,
  error: null,
  searchQuery: '',
  fetchUsers: async (search) => {
    set({ isLoading: true, error: null })
    try {
      const result = await api.getUsers({ limit: 100, search })
      set({ users: result.users, total: result.total, isLoading: false })
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },
  setSearchQuery: (query) => set({ searchQuery: query }),
}))

// Topics Store
interface TopicsState {
  topics: Topic[]
  isLoading: boolean
  error: string | null
  fetchTopics: (userId: number) => Promise<void>
  clearTopics: () => void
}

export const useTopicsStore = create<TopicsState>((set) => ({
  topics: [],
  isLoading: false,
  error: null,
  fetchTopics: async (userId) => {
    set({ isLoading: true, error: null })
    try {
      const topics = await api.getUserTopics(userId)
      set({ topics, isLoading: false })
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },
  clearTopics: () => set({ topics: [] }),
}))

// Consultation Logs Store
interface LogsState {
  logs: ConsultationLog[]
  messages: Message[]
  topicInfo: {
    id: number
    session_id: string
    status: string
    culture: string | null
    user: {
      username: string | null
      first_name: string | null
      telegram_user_id: number
    }
  } | null
  isLoading: boolean
  error: string | null
  sseConnected: boolean
  fetchLogs: (topicId: number) => Promise<void>
  addLog: (log: ConsultationLog) => void  // NEW для SSE
  addMessage: (message: Message) => void  // NEW для SSE
  setSseConnected: (connected: boolean) => void  // NEW для SSE
  clearLogs: () => void
}

export const useLogsStore = create<LogsState>((set) => ({
  logs: [],
  messages: [],
  topicInfo: null,
  isLoading: false,
  error: null,
  sseConnected: false,
  fetchLogs: async (topicId) => {
    set({ isLoading: true, error: null })
    try {
      const result = await api.getTopicLogs(topicId)
      set({
        logs: result.logs,
        messages: result.messages || [],
        topicInfo: result.topic,
        isLoading: false,
      })
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },
  // NEW: добавление нового лога из SSE (инкрементально)
  addLog: (log) => {
    set((state) => {
      // Дедупликация по id
      if (state.logs.some((l) => l.id === log.id)) {
        return state
      }

      return {
        logs: [...state.logs, log].sort((a, b) =>
          new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
        ),
      }
    })
  },
  // NEW: добавление нового сообщения из SSE
  addMessage: (message) => {
    set((state) => {
      // Дедупликация по id
      if (state.messages.some((m) => m.id === message.id)) {
        return state
      }

      return {
        messages: [...state.messages, message].sort((a, b) =>
          new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
        ),
      }
    })
  },
  // NEW: установка статуса SSE подключения
  setSseConnected: (connected) => set({ sseConnected: connected }),
  clearLogs: () => set({ logs: [], messages: [], topicInfo: null }),
}))

// Live Feed Store
interface LiveFeedState {
  logs: RecentLog[]
  lastId: number | null
  isLoading: boolean
  error: string | null
  sseConnected: boolean
  fetchRecentLogs: () => Promise<void>
  pollNewLogs: () => Promise<void>
  addNewLog: (log: RecentLog) => void  // NEW для SSE
  setSseConnected: (connected: boolean) => void  // NEW для SSE
  clearLogs: () => void
}

export const useLiveFeedStore = create<LiveFeedState>((set, get) => ({
  logs: [],
  lastId: null,
  isLoading: false,
  error: null,
  sseConnected: false,
  fetchRecentLogs: async () => {
    set({ isLoading: true, error: null })
    try {
      const logs = await api.getRecentLogs({ limit: 50 })
      const lastId = logs.length > 0 ? Math.max(...logs.map((l) => l.id)) : null
      set({ logs, lastId, isLoading: false })
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },
  pollNewLogs: async () => {
    const { lastId } = get()
    try {
      const newLogs = await api.getRecentLogs({
        limit: 50,
        since_id: lastId ?? undefined,
      })
      if (newLogs.length > 0) {
        const newLastId = Math.max(...newLogs.map((l) => l.id))
        set((state) => ({
          logs: [...newLogs, ...state.logs].slice(0, 100),
          lastId: newLastId,
        }))
      }
    } catch (error) {
      console.error('Poll error:', error)
    }
  },
  // NEW: добавление нового лога из SSE (инкрементально)
  addNewLog: (log) => {
    set((state) => {
      // Дедупликация по id
      if (state.logs.some((l) => l.id === log.id)) {
        return state
      }

      const newLastId = Math.max(state.lastId ?? 0, log.id)
      return {
        logs: [log, ...state.logs].slice(0, 100),  // Limit 100
        lastId: newLastId,
      }
    })
  },
  // NEW: установка статуса SSE подключения
  setSseConnected: (connected) => set({ sseConnected: connected }),
  clearLogs: () => set({ logs: [], lastId: null }),
}))

// Stats Store
interface StatsState {
  stats: Stats | null
  embeddingStats: EmbeddingStats | null
  period: 'day' | 'week' | 'month' | 'all'
  isLoading: boolean
  error: string | null
  fetchStats: (period?: 'day' | 'week' | 'month' | 'all') => Promise<void>
  fetchEmbeddingStats: (period?: 'day' | 'week' | 'month' | 'all') => Promise<void>
  setPeriod: (period: 'day' | 'week' | 'month' | 'all') => void
}

export const useStatsStore = create<StatsState>((set) => ({
  stats: null,
  embeddingStats: null,
  period: 'all',
  isLoading: false,
  error: null,
  fetchStats: async (period = 'all') => {
    set({ isLoading: true, error: null })
    try {
      const stats = await api.getStats(period)
      set({ stats, period, isLoading: false })
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },
  fetchEmbeddingStats: async (period = 'all') => {
    try {
      const embeddingStats = await api.getEmbeddingStats(period)
      set({ embeddingStats })
    } catch (error) {
      console.error('Error fetching embedding stats:', error)
    }
  },
  setPeriod: (period) => set({ period }),
}))

// Currency Store
interface CurrencyState {
  usdRate: number
  lastUpdated: Date | null
  isLoading: boolean
  fetchRate: () => Promise<void>
}

export const useCurrencyStore = create<CurrencyState>((set, get) => ({
  usdRate: 100, // Fallback rate
  lastUpdated: null,
  isLoading: false,
  fetchRate: async () => {
    // Don't fetch if updated less than 1 hour ago
    const { lastUpdated } = get()
    if (lastUpdated && Date.now() - lastUpdated.getTime() < 3600000) {
      return
    }

    set({ isLoading: true })
    try {
      const rate = await api.getUsdRate()
      set({ usdRate: rate, lastUpdated: new Date(), isLoading: false })
    } catch {
      set({ isLoading: false })
    }
  },
}))

// Documents Store
interface DocumentsState {
  documents: Document[]
  subcategories: string[]
  isLoading: boolean
  isUploading: boolean
  error: string | null
  uploadError: string | null
  fetchDocuments: () => Promise<void>
  uploadDocument: (file: File, subcategory: string) => Promise<boolean>
  deleteDocument: (id: number) => Promise<boolean>
  pollProcessingDocuments: () => Promise<void>
  updateDocumentStatus: (documentId: number, status: Partial<Document>) => void  // NEW для SSE
}

export const useDocumentsStore = create<DocumentsState>((set, get) => ({
  documents: [],
  subcategories: [],
  isLoading: false,
  isUploading: false,
  error: null,
  uploadError: null,

  fetchDocuments: async () => {
    set({ isLoading: true, error: null })
    try {
      const result = await api.getDocuments()
      set({
        documents: result.documents,
        subcategories: result.subcategories,
        isLoading: false,
      })
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },

  uploadDocument: async (file, subcategory) => {
    set({ isUploading: true, uploadError: null })
    try {
      await api.uploadDocument(file, subcategory)
      set({ isUploading: false })
      // Refresh documents list
      get().fetchDocuments()
      return true
    } catch (error) {
      set({ uploadError: String(error), isUploading: false })
      return false
    }
  },

  deleteDocument: async (id) => {
    try {
      await api.deleteDocument(id)
      // Remove from local state
      set((state) => ({
        documents: state.documents.filter((d) => d.id !== id),
      }))
      return true
    } catch (error) {
      set({ error: String(error) })
      return false
    }
  },

  pollProcessingDocuments: async () => {
    const { documents } = get()
    const processingIds = documents
      .filter((d) => d.status === 'processing' || d.status === 'pending')
      .map((d) => d.id)

    if (processingIds.length === 0) return

    // Fetch updated status for each processing document
    try {
      const updatedDocs = await Promise.all(
        processingIds.map((id) => api.getDocumentStatus(id))
      )

      set((state) => ({
        documents: state.documents.map((doc) => {
          const updated = updatedDocs.find((u) => u.id === doc.id)
          return updated || doc
        }),
      }))
    } catch (error) {
      console.error('Polling error:', error)
    }
  },

  // NEW: обновление статуса документа из SSE (инкрементально)
  updateDocumentStatus: (documentId, statusUpdate) => {
    set((state) => ({
      documents: state.documents.map((doc) =>
        doc.id === documentId ? { ...doc, ...statusUpdate } : doc
      ),
    }))
  },
}))
