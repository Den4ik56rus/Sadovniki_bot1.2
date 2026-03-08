// Zustand Stores

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, Topic, ConsultationLog, RecentLog, Stats, EmbeddingStats, View, Document, Message, CrmClient, FunnelStatus, Buyer, BuyerStatus, OpenAIBalance } from '@/types'
import { api } from '@/services/api'

// UI Store with persistence
interface UIState {
  currentView: View
  selectedUserId: number | null
  selectedTopicId: number | null
  isLiveFeedPaused: boolean
  globalSearchQuery: string
  setView: (view: View) => void
  selectUser: (userId: number | null) => void
  selectTopic: (topicId: number | null) => void
  toggleLiveFeed: () => void
  setGlobalSearchQuery: (query: string) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      currentView: 'crm',
      selectedUserId: null,
      selectedTopicId: null,
      isLiveFeedPaused: false,
      globalSearchQuery: '',
      setView: (view) => set({ currentView: view, globalSearchQuery: '' }),
      selectUser: (userId) => set({ selectedUserId: userId, selectedTopicId: null }),
      selectTopic: (topicId) => set({ selectedTopicId: topicId }),
      toggleLiveFeed: () => set((state) => ({ isLiveFeedPaused: !state.isLiveFeedPaused })),
      setGlobalSearchQuery: (query) => set({ globalSearchQuery: query }),
    }),
    {
      name: 'admin-ui-state',
      partialize: (state) => ({
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

// CRM Store
interface ColumnConfig {
  id: FunnelStatus
  title: string
  color: string
  is_system: boolean
}

interface CrmState {
  clients: Partial<Record<FunnelStatus, CrmClient[]>>
  stats: Partial<Record<FunnelStatus, number>>
  selectedClientId: number | null
  isLoading: boolean
  error: string | null
  // Settings mode
  isSettingsMode: boolean
  columnConfigs: ColumnConfig[]
  columnsLoaded: boolean
  // Actions
  fetchClients: () => Promise<void>
  fetchColumns: () => Promise<void>
  updateClientStatus: (clientId: number, newStatus: FunnelStatus) => Promise<boolean>
  moveClient: (clientId: number, fromStatus: FunnelStatus, toStatus: FunnelStatus) => void
  selectClient: (clientId: number | null) => void
  // Settings mode actions
  toggleSettingsMode: () => void
  updateColumnTitle: (id: FunnelStatus, title: string) => Promise<void>
  updateColumnColor: (id: FunnelStatus, color: string) => Promise<void>
  addColumnAfter: (afterId: FunnelStatus) => Promise<void>
  deleteColumn: (id: FunnelStatus) => Promise<void>
  reorderColumns: (activeId: FunnelStatus, overId: FunnelStatus) => Promise<void>
}

const DEFAULT_COLUMN_CONFIGS: ColumnConfig[] = [
  { id: 'new', title: 'НЕРАЗОБРАННОЕ', color: '#3B82F6', is_system: true },
  { id: 'tried', title: 'БИРЖА ЛИДОВ', color: '#8B5CF6', is_system: true },
  { id: 'trial_ended', title: 'ВЗЯТ В РАБОТУ', color: '#F59E0B', is_system: true },
  { id: 'paid', title: 'УЗНАЛ ЦЕНУ', color: '#22C55E', is_system: true },
]

export const useCrmStore = create<CrmState>()((set, get) => ({
  clients: {
    new: [],
    tried: [],
    trial_ended: [],
    paid: [],
  },
  stats: {
    new: 0,
    tried: 0,
    trial_ended: 0,
    paid: 0,
  },
  selectedClientId: null,
  isLoading: false,
  error: null,
  // Settings mode
  isSettingsMode: false,
  columnConfigs: DEFAULT_COLUMN_CONFIGS,
  columnsLoaded: false,

  fetchColumns: async () => {
    try {
      const columns = await api.getFunnelColumns()
      // Map backend format to frontend format
      const columnConfigs: ColumnConfig[] = columns.map((c) => ({
        id: c.id,
        title: c.title,
        color: c.color,
        is_system: c.is_system ?? false,
      }))
      set({ columnConfigs, columnsLoaded: true })
    } catch (error) {
      console.error('Failed to fetch columns, using defaults:', error)
      set({ columnConfigs: DEFAULT_COLUMN_CONFIGS, columnsLoaded: true })
    }
  },

  fetchClients: async () => {
    set({ isLoading: true, error: null })
    try {
      // Ensure columns are loaded first
      if (!get().columnsLoaded) {
        await get().fetchColumns()
      }

      const result = await api.getCrmClients()

      // Initialize clients/stats for all columns
      const columnConfigs = get().columnConfigs
      const clients: Partial<Record<FunnelStatus, CrmClient[]>> = {}
      const stats: Partial<Record<FunnelStatus, number>> = {}

      for (const col of columnConfigs) {
        clients[col.id] = result.clients[col.id] || []
        stats[col.id] = result.stats[col.id] || 0
      }

      set({
        clients,
        stats,
        isLoading: false,
      })
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },

  updateClientStatus: async (clientId, newStatus) => {
    try {
      await api.updateClientStatus(clientId, newStatus)
      // Refetch to get updated data
      get().fetchClients()
      return true
    } catch (error) {
      set({ error: String(error) })
      return false
    }
  },

  // Optimistic update for drag-and-drop
  moveClient: (clientId, fromStatus, toStatus) => {
    if (fromStatus === toStatus) return

    set((state) => {
      const fromClients = state.clients[fromStatus] || []
      const client = fromClients.find((c) => c.id === clientId)
      if (!client) return state

      const updatedClient = { ...client, status: toStatus, manual_override: true }
      const toClients = state.clients[toStatus] || []

      return {
        clients: {
          ...state.clients,
          [fromStatus]: fromClients.filter((c) => c.id !== clientId),
          [toStatus]: [updatedClient, ...toClients],
        },
        stats: {
          ...state.stats,
          [fromStatus]: (state.stats[fromStatus] || 0) - 1,
          [toStatus]: (state.stats[toStatus] || 0) + 1,
        },
      }
    })

    // Update on server (works for all columns now including custom)
    api.updateClientStatus(clientId, toStatus).catch((error) => {
      console.error('Failed to update client status:', error)
      // Revert on failure by refetching
      get().fetchClients()
    })
  },

  selectClient: (clientId) => set({ selectedClientId: clientId }),

  // Settings mode actions
  toggleSettingsMode: () => set((state) => ({ isSettingsMode: !state.isSettingsMode })),

  updateColumnTitle: async (id, title) => {
    // Optimistic update
    set((state) => ({
      columnConfigs: state.columnConfigs.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    }))

    // Sync to server
    try {
      await api.updateFunnelColumn(id, { title })
    } catch (error) {
      console.error('Failed to update column title:', error)
      // Revert by refetching
      get().fetchColumns()
    }
  },

  updateColumnColor: async (id, color) => {
    // Optimistic update
    set((state) => ({
      columnConfigs: state.columnConfigs.map((c) =>
        c.id === id ? { ...c, color } : c
      ),
    }))

    // Sync to server
    try {
      await api.updateFunnelColumn(id, { color })
    } catch (error) {
      console.error('Failed to update column color:', error)
      get().fetchColumns()
    }
  },

  addColumnAfter: async (afterId) => {
    const colors = ['#3B82F6', '#8B5CF6', '#F59E0B', '#22C55E', '#EF4444', '#EC4899', '#14B8A6', '#6B7280']
    const randomColor = colors[Math.floor(Math.random() * colors.length)]

    try {
      // Create on server
      const newColumn = await api.createFunnelColumn({
        title: 'НОВЫЙ ЭТАП',
        color: randomColor,
        after_id: afterId,
      })

      // Refetch columns to get correct order
      await get().fetchColumns()

      // Initialize clients/stats for new column
      set((state) => ({
        clients: {
          ...state.clients,
          [newColumn.id]: [],
        },
        stats: {
          ...state.stats,
          [newColumn.id]: 0,
        },
      }))
    } catch (error) {
      console.error('Failed to create column:', error)
    }
  },

  deleteColumn: async (id) => {
    try {
      await api.deleteFunnelColumn(id)
      // Refetch everything
      await get().fetchColumns()
      await get().fetchClients()
    } catch (error) {
      console.error('Failed to delete column:', error)
    }
  },

  reorderColumns: async (activeId, overId) => {
    if (activeId === overId) return

    // Optimistic update
    set((state) => {
      const oldIndex = state.columnConfigs.findIndex((c) => c.id === activeId)
      const newIndex = state.columnConfigs.findIndex((c) => c.id === overId)

      if (oldIndex < 0 || newIndex < 0) return state

      const newConfigs = [...state.columnConfigs]
      const [movedColumn] = newConfigs.splice(oldIndex, 1)
      newConfigs.splice(newIndex, 0, movedColumn)

      return { columnConfigs: newConfigs }
    })

    // Sync to server
    try {
      const columnIds = get().columnConfigs.map((c) => c.id)
      await api.reorderFunnelColumns(columnIds)
    } catch (error) {
      console.error('Failed to reorder columns:', error)
      get().fetchColumns()
    }
  },
}))


// =============================================================================
// Buyers Store (Покупатели)
// =============================================================================

interface BuyerColumnConfig {
  id: BuyerStatus
  title: string
  color: string
  is_system: boolean
}

interface BuyersState {
  buyers: Partial<Record<BuyerStatus, Buyer[]>>
  stats: Partial<Record<BuyerStatus, number>>
  selectedBuyerId: number | null
  isLoading: boolean
  error: string | null
  // Settings mode
  isSettingsMode: boolean
  columnConfigs: BuyerColumnConfig[]
  columnsLoaded: boolean
  // Actions
  fetchBuyers: () => Promise<void>
  fetchColumns: () => Promise<void>
  updateBuyerStatus: (buyerId: number, newStatus: BuyerStatus) => Promise<boolean>
  moveBuyer: (buyerId: number, fromStatus: BuyerStatus, toStatus: BuyerStatus) => void
  selectBuyer: (buyerId: number | null) => void
  // Settings mode actions
  toggleSettingsMode: () => void
  updateColumnTitle: (id: BuyerStatus, title: string) => Promise<void>
  updateColumnColor: (id: BuyerStatus, color: string) => Promise<void>
  addColumnAfter: (afterId: BuyerStatus) => Promise<void>
  deleteColumn: (id: BuyerStatus) => Promise<void>
  reorderColumns: (activeId: BuyerStatus, overId: BuyerStatus) => Promise<void>
}

const DEFAULT_BUYER_COLUMN_CONFIGS: BuyerColumnConfig[] = [
  { id: 'pending_payment', title: 'Ожидает оплаты', color: '#F59E0B', is_system: true },
  { id: 'paid', title: 'Оплачено', color: '#22C55E', is_system: true },
  { id: 'active', title: 'Активна', color: '#3B82F6', is_system: true },
  { id: 'expired', title: 'Истекла', color: '#EF4444', is_system: true },
]

export const useBuyersStore = create<BuyersState>()((set, get) => ({
  buyers: {
    pending_payment: [],
    paid: [],
    active: [],
    expired: [],
  },
  stats: {
    pending_payment: 0,
    paid: 0,
    active: 0,
    expired: 0,
  },
  selectedBuyerId: null,
  isLoading: false,
  error: null,
  // Settings mode
  isSettingsMode: false,
  columnConfigs: DEFAULT_BUYER_COLUMN_CONFIGS,
  columnsLoaded: false,

  fetchColumns: async () => {
    try {
      const columns = await api.getBuyerColumns()
      const columnConfigs: BuyerColumnConfig[] = columns.map((c) => ({
        id: c.id as BuyerStatus,
        title: c.title,
        color: c.color,
        is_system: c.is_system ?? false,
      }))
      set({ columnConfigs, columnsLoaded: true })
    } catch (error) {
      console.error('Failed to fetch buyer columns, using defaults:', error)
      set({ columnConfigs: DEFAULT_BUYER_COLUMN_CONFIGS, columnsLoaded: true })
    }
  },

  fetchBuyers: async () => {
    set({ isLoading: true, error: null })
    try {
      // Ensure columns are loaded first
      if (!get().columnsLoaded) {
        await get().fetchColumns()
      }

      const result = await api.getBuyers()

      // Initialize buyers/stats for all columns
      const columnConfigs = get().columnConfigs
      const buyers: Partial<Record<BuyerStatus, Buyer[]>> = {}
      const stats: Partial<Record<BuyerStatus, number>> = {}

      for (const col of columnConfigs) {
        buyers[col.id] = result.buyers[col.id] || []
        stats[col.id] = result.stats[col.id] || 0
      }

      set({
        buyers,
        stats,
        isLoading: false,
      })
    } catch (error) {
      set({ error: String(error), isLoading: false })
    }
  },

  updateBuyerStatus: async (buyerId, newStatus) => {
    try {
      await api.updateBuyerStatus(buyerId, newStatus)
      get().fetchBuyers()
      return true
    } catch (error) {
      set({ error: String(error) })
      return false
    }
  },

  // Optimistic update for drag-and-drop
  moveBuyer: (buyerId, fromStatus, toStatus) => {
    if (fromStatus === toStatus) return

    set((state) => {
      const fromBuyers = state.buyers[fromStatus] || []
      const buyer = fromBuyers.find((b) => b.id === buyerId)
      if (!buyer) return state

      const updatedBuyer = { ...buyer, status: toStatus, manual_override: true }
      const toBuyers = state.buyers[toStatus] || []

      return {
        buyers: {
          ...state.buyers,
          [fromStatus]: fromBuyers.filter((b) => b.id !== buyerId),
          [toStatus]: [updatedBuyer, ...toBuyers],
        },
        stats: {
          ...state.stats,
          [fromStatus]: (state.stats[fromStatus] || 0) - 1,
          [toStatus]: (state.stats[toStatus] || 0) + 1,
        },
      }
    })

    api.updateBuyerStatus(buyerId, toStatus).catch((error) => {
      console.error('Failed to update buyer status:', error)
      get().fetchBuyers()
    })
  },

  selectBuyer: (buyerId) => set({ selectedBuyerId: buyerId }),

  // Settings mode actions
  toggleSettingsMode: () => set((state) => ({ isSettingsMode: !state.isSettingsMode })),

  updateColumnTitle: async (id, title) => {
    set((state) => ({
      columnConfigs: state.columnConfigs.map((c) =>
        c.id === id ? { ...c, title } : c
      ),
    }))

    try {
      await api.updateBuyerColumn(id, { title })
    } catch (error) {
      console.error('Failed to update buyer column title:', error)
      get().fetchColumns()
    }
  },

  updateColumnColor: async (id, color) => {
    set((state) => ({
      columnConfigs: state.columnConfigs.map((c) =>
        c.id === id ? { ...c, color } : c
      ),
    }))

    try {
      await api.updateBuyerColumn(id, { color })
    } catch (error) {
      console.error('Failed to update buyer column color:', error)
      get().fetchColumns()
    }
  },

  addColumnAfter: async (afterId) => {
    const colors = ['#3B82F6', '#8B5CF6', '#F59E0B', '#22C55E', '#EF4444', '#EC4899', '#14B8A6', '#6B7280']
    const randomColor = colors[Math.floor(Math.random() * colors.length)]

    try {
      const newColumn = await api.createBuyerColumn({
        title: 'НОВЫЙ ЭТАП',
        color: randomColor,
        after_id: afterId,
      })

      await get().fetchColumns()

      set((state) => ({
        buyers: {
          ...state.buyers,
          [newColumn.id]: [],
        },
        stats: {
          ...state.stats,
          [newColumn.id]: 0,
        },
      }))
    } catch (error) {
      console.error('Failed to create buyer column:', error)
    }
  },

  deleteColumn: async (id) => {
    try {
      await api.deleteBuyerColumn(id)
      await get().fetchColumns()
      await get().fetchBuyers()
    } catch (error) {
      console.error('Failed to delete buyer column:', error)
    }
  },

  reorderColumns: async (activeId, overId) => {
    if (activeId === overId) return

    set((state) => {
      const oldIndex = state.columnConfigs.findIndex((c) => c.id === activeId)
      const newIndex = state.columnConfigs.findIndex((c) => c.id === overId)

      if (oldIndex < 0 || newIndex < 0) return state

      const newConfigs = [...state.columnConfigs]
      const [movedColumn] = newConfigs.splice(oldIndex, 1)
      newConfigs.splice(newIndex, 0, movedColumn)

      return { columnConfigs: newConfigs }
    })

    try {
      const columnIds = get().columnConfigs.map((c) => c.id)
      await api.reorderBuyerColumns(columnIds)
    } catch (error) {
      console.error('Failed to reorder buyer columns:', error)
      get().fetchColumns()
    }
  },
}))

// =============================================================================
// A/B Test Store
// =============================================================================

interface ABTestVariantStats {
  users: number
  tried: number
  trial_ended: number
  saw_pricing: number
  paid: number
  conversion: number
}

interface ABTestTag {
  id: number
  name: string
  color: string
}

interface ABTestStats {
  active_variant: 'A' | 'B'
  variants: {
    A: ABTestVariantStats
    B: ABTestVariantStats
  }
  available_tags?: ABTestTag[]
  selected_tag_id?: number | null
}

interface ABTestState {
  stats: ABTestStats | null
  loading: boolean
  selectedTagId: number | null
  fetchStats: (tagId?: number | null) => Promise<void>
  setSelectedTag: (tagId: number | null) => void
  setVariant: (variant: 'A' | 'B') => Promise<void>
}

export const useABTestStore = create<ABTestState>((set, get) => ({
  stats: null,
  loading: false,
  selectedTagId: null,

  fetchStats: async (tagId?: number | null) => {
    set({ loading: true })
    const tid = tagId !== undefined ? tagId : get().selectedTagId
    try {
      const query = tid ? `?tag_id=${tid}` : ''
      const res = await fetch(`/api/admin/ab-test/stats${query}`)
      const data = await res.json()
      set({ stats: data })
    } catch (error) {
      console.error('Error fetching AB test stats:', error)
    } finally {
      set({ loading: false })
    }
  },

  setSelectedTag: (tagId: number | null) => {
    set({ selectedTagId: tagId })
    get().fetchStats(tagId)
  },

  setVariant: async (variant: 'A' | 'B') => {
    await fetch('/api/admin/ab-test/variant', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ variant }),
    })
  },
}))


// OpenAI Balance Store
interface OpenAIBalanceState {
  balance: OpenAIBalance | null
  isLoading: boolean
  isEditingBudget: boolean
  error: string | null
  fetchBalance: () => Promise<void>
  updateBudget: (budgetUsd: number) => Promise<boolean>
}

export const useOpenAIBalanceStore = create<OpenAIBalanceState>((set, get) => ({
  balance: null,
  isLoading: false,
  isEditingBudget: false,
  error: null,
  fetchBalance: async () => {
    // Не рефетчим если загрузка уже идёт
    if (get().isLoading) return
    set({ isLoading: true, error: null })
    try {
      const balance = await api.getOpenAIBalance(30)
      set({ balance, isLoading: false })
    } catch (error) {
      console.error('Error fetching OpenAI balance:', error)
      set({ error: 'Не удалось загрузить данные OpenAI', isLoading: false })
    }
  },
  updateBudget: async (budgetUsd: number) => {
    set({ isEditingBudget: true })
    try {
      await api.updateOpenAIBudget(budgetUsd)
      // Рефетчим баланс после обновления
      const balance = await api.getOpenAIBalance(30)
      set({ balance, isEditingBudget: false })
      return true
    } catch (error) {
      console.error('Error updating OpenAI budget:', error)
      set({ isEditingBudget: false })
      return false
    }
  },
}))
