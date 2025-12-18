// API Service for Admin Panel

import type {
  UsersResponse,
  Topic,
  TopicLogsResponse,
  RecentLog,
  Stats,
  EmbeddingStats,
  DocumentsResponse,
  Document,
  UploadResponse,
  CrmClientsResponse,
  CrmClient,
  CrmClientFull,
  FunnelStatus,
  FunnelColumnConfig,
  ClientPriority,
  ClientTag,
  CustomField,
  CustomFieldValue,
  ClientTask,
  ClientNote,
  ActivityEvent,
  CreateCustomFieldDto,
  CreateTagDto,
  CreateTaskDto,
  UpdateTaskDto,
  CreateNoteDto,
  BuyersResponse,
  Buyer,
  BuyerFull,
  BuyerStatus,
  BuyerColumnConfig,
  // Unified Funnels
  Funnel,
  FunnelStage,
  FunnelClientsResponse,
  FunnelsResponse,
  FunnelStagesResponse,
  CreateFunnelDto,
  CreateStageDto,
  ClientFunnelInfo,
  // Admin Articles
  AdminArticle,
  AdminArticlesResponse,
  // Expenses
  Expense,
  ExpenseCategory,
  ExpensesResponse,
  ExpenseStats,
  CreateExpenseDto,
  ExpenseFilters,
} from '@/types'

const API_BASE = import.meta.env.VITE_API_URL || '/api/admin'
const CBR_API = 'https://www.cbr-xml-daily.ru/daily_json.js'

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      'ngrok-skip-browser-warning': 'true',  // Skip ngrok interstitial page
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`)
  }

  return response.json()
}

export const api = {
  // Users
  async getUsers(params?: {
    limit?: number
    offset?: number
    search?: string
  }): Promise<UsersResponse> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    if (params?.search) searchParams.set('search', params.search)

    const query = searchParams.toString()
    return fetchApi<UsersResponse>(`/users${query ? `?${query}` : ''}`)
  },

  // Topics
  async getUserTopics(
    userId: number,
    params?: { limit?: number; offset?: number }
  ): Promise<Topic[]> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))

    const query = searchParams.toString()
    return fetchApi<Topic[]>(`/users/${userId}/topics${query ? `?${query}` : ''}`)
  },

  // Logs
  async getTopicLogs(topicId: number): Promise<TopicLogsResponse> {
    return fetchApi<TopicLogsResponse>(`/topics/${topicId}/logs`)
  },

  async getRecentLogs(params?: {
    limit?: number
    since_id?: number
  }): Promise<RecentLog[]> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.since_id) searchParams.set('since_id', String(params.since_id))

    const query = searchParams.toString()
    return fetchApi<RecentLog[]>(`/logs/recent${query ? `?${query}` : ''}`)
  },

  // Stats
  async getStats(period?: 'day' | 'week' | 'month' | 'all'): Promise<Stats> {
    const query = period ? `?period=${period}` : ''
    return fetchApi<Stats>(`/stats${query}`)
  },

  // Embedding Stats
  async getEmbeddingStats(period?: 'day' | 'week' | 'month' | 'all'): Promise<EmbeddingStats> {
    const query = period ? `?period=${period}` : ''
    return fetchApi<EmbeddingStats>(`/stats/embeddings${query}`)
  },

  // Currency exchange rate (CBR)
  async getUsdRate(): Promise<number> {
    try {
      const response = await fetch(CBR_API)
      const data = await response.json()
      return data.Valute.USD.Value
    } catch {
      // Fallback rate if API is unavailable
      return 100
    }
  },

  // Documents
  async getDocuments(subcategory?: string): Promise<DocumentsResponse> {
    const query = subcategory ? `?subcategory=${encodeURIComponent(subcategory)}` : ''
    return fetchApi<DocumentsResponse>(`/documents${query}`)
  },

  async getDocumentStatus(id: number): Promise<Document> {
    return fetchApi<Document>(`/documents/${id}/status`)
  },

  async uploadDocument(file: File, subcategory: string): Promise<UploadResponse> {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('subcategory', subcategory)

    const response = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      headers: {
        'ngrok-skip-browser-warning': 'true',
      },
      body: formData,
    })

    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || `Upload failed: ${response.status}`)
    }

    return response.json()
  },

  async deleteDocument(id: number): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE}/documents/${id}`, {
      method: 'DELETE',
      headers: {
        'ngrok-skip-browser-warning': 'true',
      },
    })

    if (!response.ok) {
      throw new Error(`Delete failed: ${response.status}`)
    }

    return response.json()
  },

  // CRM
  async getCrmClients(): Promise<CrmClientsResponse> {
    return fetchApi<CrmClientsResponse>('/crm/clients')
  },

  async getCrmClient(id: number): Promise<CrmClient> {
    return fetchApi<CrmClient>(`/crm/clients/${id}`)
  },

  async updateClientStatus(
    id: number,
    status: FunnelStatus
  ): Promise<{ success: boolean; status: FunnelStatus }> {
    return fetchApi(`/crm/clients/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
  },

  async getClientTopics(
    clientId: number,
    params?: { limit?: number; offset?: number }
  ): Promise<Topic[]> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))

    const query = searchParams.toString()
    return fetchApi<Topic[]>(`/crm/clients/${clientId}/topics${query ? `?${query}` : ''}`)
  },

  async getCrmFunnelStats(): Promise<Record<FunnelStatus, number>> {
    return fetchApi('/crm/stats')
  },

  // CRM Extended: Client full data
  async getClientFull(id: number): Promise<CrmClientFull> {
    return fetchApi<CrmClientFull>(`/crm/clients/${id}/full`)
  },

  async updateClientPriority(
    id: number,
    priority: ClientPriority
  ): Promise<{ success: boolean }> {
    return fetchApi(`/crm/clients/${id}/priority`, {
      method: 'PATCH',
      body: JSON.stringify({ priority }),
    })
  },

  async updateClientSource(
    id: number,
    source: string
  ): Promise<{ success: boolean }> {
    return fetchApi(`/crm/clients/${id}/source`, {
      method: 'PATCH',
      body: JSON.stringify({ source }),
    })
  },

  // CRM: Custom fields
  async getCustomFields(): Promise<CustomField[]> {
    return fetchApi<CustomField[]>('/crm/custom-fields')
  },

  async createCustomField(data: CreateCustomFieldDto): Promise<CustomField> {
    return fetchApi<CustomField>('/crm/custom-fields', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateCustomField(id: number, data: Partial<CreateCustomFieldDto>): Promise<CustomField> {
    return fetchApi<CustomField>(`/crm/custom-fields/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteCustomField(id: number): Promise<{ success: boolean }> {
    return fetchApi(`/crm/custom-fields/${id}`, {
      method: 'DELETE',
    })
  },

  async getClientFieldValues(clientId: number): Promise<CustomFieldValue[]> {
    return fetchApi<CustomFieldValue[]>(`/crm/clients/${clientId}/fields`)
  },

  async updateClientFieldValues(
    clientId: number,
    fields: Record<number, unknown>
  ): Promise<{ success: boolean }> {
    return fetchApi(`/crm/clients/${clientId}/fields`, {
      method: 'PUT',
      body: JSON.stringify({ fields }),
    })
  },

  // CRM: Tags
  async getTags(): Promise<ClientTag[]> {
    return fetchApi<ClientTag[]>('/crm/tags')
  },

  async createTag(data: CreateTagDto): Promise<ClientTag> {
    return fetchApi<ClientTag>('/crm/tags', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateTag(id: number, data: Partial<CreateTagDto>): Promise<ClientTag> {
    return fetchApi<ClientTag>(`/crm/tags/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteTag(id: number): Promise<{ success: boolean }> {
    return fetchApi(`/crm/tags/${id}`, {
      method: 'DELETE',
    })
  },

  async getClientTags(clientId: number): Promise<ClientTag[]> {
    return fetchApi<ClientTag[]>(`/crm/clients/${clientId}/tags`)
  },

  async updateClientTags(clientId: number, tagIds: number[]): Promise<{ success: boolean }> {
    return fetchApi(`/crm/clients/${clientId}/tags`, {
      method: 'PUT',
      body: JSON.stringify({ tag_ids: tagIds }),
    })
  },

  // CRM: Tasks
  async getClientTasks(clientId: number, includeCompleted = true): Promise<ClientTask[]> {
    const query = `?include_completed=${includeCompleted}`
    return fetchApi<ClientTask[]>(`/crm/clients/${clientId}/tasks${query}`)
  },

  async createTask(clientId: number, data: CreateTaskDto): Promise<ClientTask> {
    return fetchApi<ClientTask>(`/crm/clients/${clientId}/tasks`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async getTask(taskId: number): Promise<ClientTask> {
    return fetchApi<ClientTask>(`/crm/tasks/${taskId}`)
  },

  async updateTask(taskId: number, data: UpdateTaskDto): Promise<ClientTask> {
    return fetchApi<ClientTask>(`/crm/tasks/${taskId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteTask(taskId: number): Promise<{ success: boolean }> {
    return fetchApi(`/crm/tasks/${taskId}`, {
      method: 'DELETE',
    })
  },

  async completeTask(taskId: number): Promise<ClientTask> {
    return fetchApi<ClientTask>(`/crm/tasks/${taskId}/complete`, {
      method: 'POST',
    })
  },

  // CRM: Notes
  async getClientNotes(clientId: number): Promise<ClientNote[]> {
    return fetchApi<ClientNote[]>(`/crm/clients/${clientId}/notes`)
  },

  async createNote(clientId: number, data: CreateNoteDto): Promise<ClientNote> {
    return fetchApi<ClientNote>(`/crm/clients/${clientId}/notes`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async deleteNote(noteId: number): Promise<{ success: boolean }> {
    return fetchApi(`/crm/notes/${noteId}`, {
      method: 'DELETE',
    })
  },

  // CRM: Activity feed
  async getClientActivity(
    clientId: number,
    params?: { types?: string[]; limit?: number; offset?: number }
  ): Promise<ActivityEvent[]> {
    const searchParams = new URLSearchParams()
    if (params?.types?.length) searchParams.set('types', params.types.join(','))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))

    const query = searchParams.toString()
    return fetchApi<ActivityEvent[]>(`/crm/clients/${clientId}/activity${query ? `?${query}` : ''}`)
  },

  // CRM: Funnel columns (Kanban)
  async getFunnelColumns(): Promise<FunnelColumnConfig[]> {
    return fetchApi<FunnelColumnConfig[]>('/crm/columns')
  },

  async createFunnelColumn(data: {
    title?: string
    color?: string
    after_id?: string
  }): Promise<FunnelColumnConfig> {
    return fetchApi<FunnelColumnConfig>('/crm/columns', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateFunnelColumn(
    id: string,
    data: { title?: string; color?: string; sort_order?: number }
  ): Promise<FunnelColumnConfig> {
    return fetchApi<FunnelColumnConfig>(`/crm/columns/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteFunnelColumn(id: string): Promise<{ success: boolean }> {
    return fetchApi(`/crm/columns/${id}`, {
      method: 'DELETE',
    })
  },

  async reorderFunnelColumns(columnIds: string[]): Promise<{ success: boolean }> {
    return fetchApi('/crm/columns/reorder', {
      method: 'PUT',
      body: JSON.stringify({ column_ids: columnIds }),
    })
  },

  // =============================================================================
  // Buyers (Покупатели)
  // =============================================================================

  async getBuyers(): Promise<BuyersResponse> {
    return fetchApi<BuyersResponse>('/buyers')
  },

  async getBuyer(id: number): Promise<Buyer> {
    return fetchApi<Buyer>(`/buyers/${id}`)
  },

  async getBuyerFull(id: number): Promise<BuyerFull> {
    return fetchApi<BuyerFull>(`/buyers/${id}/full`)
  },

  async updateBuyerStatus(
    id: number,
    status: BuyerStatus
  ): Promise<{ success: boolean; status: BuyerStatus }> {
    return fetchApi(`/buyers/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
  },

  async getBuyerTopics(
    buyerId: number,
    params?: { limit?: number; offset?: number }
  ): Promise<Topic[]> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))

    const query = searchParams.toString()
    return fetchApi<Topic[]>(`/buyers/${buyerId}/topics${query ? `?${query}` : ''}`)
  },

  async getBuyerStats(): Promise<Record<BuyerStatus, number>> {
    return fetchApi('/buyers/stats')
  },

  async getBuyerActivity(
    buyerId: number,
    params?: { types?: string[]; limit?: number; offset?: number }
  ): Promise<ActivityEvent[]> {
    const searchParams = new URLSearchParams()
    if (params?.types?.length) searchParams.set('types', params.types.join(','))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))

    const query = searchParams.toString()
    return fetchApi<ActivityEvent[]>(`/buyers/${buyerId}/activity${query ? `?${query}` : ''}`)
  },

  // Buyers: Columns (Kanban)
  async getBuyerColumns(): Promise<BuyerColumnConfig[]> {
    return fetchApi<BuyerColumnConfig[]>('/buyers/columns')
  },

  async createBuyerColumn(data: {
    title?: string
    color?: string
    after_id?: string
  }): Promise<BuyerColumnConfig> {
    return fetchApi<BuyerColumnConfig>('/buyers/columns', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateBuyerColumn(
    id: string,
    data: { title?: string; color?: string; sort_order?: number }
  ): Promise<BuyerColumnConfig> {
    return fetchApi<BuyerColumnConfig>(`/buyers/columns/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteBuyerColumn(id: string): Promise<{ success: boolean }> {
    return fetchApi(`/buyers/columns/${id}`, {
      method: 'DELETE',
    })
  },

  async reorderBuyerColumns(columnIds: string[]): Promise<{ success: boolean }> {
    return fetchApi('/buyers/columns/reorder', {
      method: 'PUT',
      body: JSON.stringify({ column_ids: columnIds }),
    })
  },

  // =============================================================================
  // Unified Funnels (Универсальная система воронок)
  // =============================================================================

  // Funnels CRUD
  async getFunnels(): Promise<FunnelsResponse> {
    return fetchApi<FunnelsResponse>('/funnels')
  },

  async getFunnel(funnelId: string): Promise<Funnel> {
    return fetchApi<Funnel>(`/funnels/${funnelId}`)
  },

  async createFunnel(data: CreateFunnelDto): Promise<Funnel> {
    return fetchApi<Funnel>('/funnels', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateFunnel(
    funnelId: string,
    data: { title?: string; description?: string; icon?: string }
  ): Promise<Funnel> {
    return fetchApi<Funnel>(`/funnels/${funnelId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteFunnel(funnelId: string): Promise<{ success: boolean }> {
    return fetchApi(`/funnels/${funnelId}`, {
      method: 'DELETE',
    })
  },

  async reorderFunnels(funnelIds: string[]): Promise<{ success: boolean }> {
    return fetchApi('/funnels/reorder', {
      method: 'PUT',
      body: JSON.stringify({ funnel_ids: funnelIds }),
    })
  },

  // Funnel Stages
  async getFunnelStages(funnelId: string): Promise<FunnelStagesResponse> {
    return fetchApi<FunnelStagesResponse>(`/funnels/${funnelId}/stages`)
  },

  async createFunnelStage(funnelId: string, data: CreateStageDto): Promise<FunnelStage> {
    return fetchApi<FunnelStage>(`/funnels/${funnelId}/stages`, {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateFunnelStage(
    funnelId: string,
    stageKey: string,
    data: { title?: string; color?: string }
  ): Promise<FunnelStage> {
    return fetchApi<FunnelStage>(`/funnels/${funnelId}/stages/${stageKey}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteFunnelStage(funnelId: string, stageKey: string): Promise<{ success: boolean }> {
    return fetchApi(`/funnels/${funnelId}/stages/${stageKey}`, {
      method: 'DELETE',
    })
  },

  async reorderFunnelStages(funnelId: string, stageKeys: string[]): Promise<{ success: boolean }> {
    return fetchApi(`/funnels/${funnelId}/stages/reorder`, {
      method: 'PUT',
      body: JSON.stringify({ stage_keys: stageKeys }),
    })
  },

  // Funnel Clients
  async getFunnelClients(funnelId: string): Promise<FunnelClientsResponse> {
    return fetchApi<FunnelClientsResponse>(`/funnels/${funnelId}/clients`)
  },

  async getFunnelStats(funnelId: string): Promise<{ stats: Record<string, number> }> {
    return fetchApi(`/funnels/${funnelId}/stats`)
  },

  async moveClientStage(
    funnelId: string,
    userId: number,
    stageKey: string
  ): Promise<{ success: boolean; stage_key: string }> {
    return fetchApi(`/funnels/${funnelId}/clients/${userId}/stage`, {
      method: 'PATCH',
      body: JSON.stringify({ stage_key: stageKey }),
    })
  },

  async transferClient(
    fromFunnelId: string,
    userId: number,
    toFunnelId: string,
    toStageKey?: string
  ): Promise<{ success: boolean; to_funnel_id: string; to_stage_key: string }> {
    return fetchApi(`/funnels/${fromFunnelId}/clients/${userId}/transfer`, {
      method: 'POST',
      body: JSON.stringify({ to_funnel_id: toFunnelId, to_stage_key: toStageKey }),
    })
  },

  async addClientToFunnel(
    funnelId: string,
    userId: number,
    stageKey?: string
  ): Promise<{ success: boolean }> {
    return fetchApi(`/funnels/${funnelId}/clients/${userId}`, {
      method: 'POST',
      body: JSON.stringify({ stage_key: stageKey }),
    })
  },

  async removeClientFromFunnel(funnelId: string, userId: number): Promise<{ success: boolean }> {
    return fetchApi(`/funnels/${funnelId}/clients/${userId}`, {
      method: 'DELETE',
    })
  },

  async getClientFunnels(userId: number): Promise<{ funnels: ClientFunnelInfo[] }> {
    return fetchApi(`/clients/${userId}/funnels`)
  },

  // =============================================================================
  // Admin Articles (Статьи, сгенерированные администратором)
  // =============================================================================

  async getArticles(params?: {
    limit?: number
    offset?: number
    admin_telegram_id?: number
  }): Promise<AdminArticlesResponse> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    if (params?.admin_telegram_id) searchParams.set('admin_telegram_id', String(params.admin_telegram_id))

    const query = searchParams.toString()
    return fetchApi<AdminArticlesResponse>(`/articles${query ? `?${query}` : ''}`)
  },

  async getArticle(articleId: number): Promise<AdminArticle> {
    return fetchApi<AdminArticle>(`/articles/${articleId}`)
  },

  // =============================================================================
  // Expenses (Расходы проекта)
  // =============================================================================

  async getExpenses(params?: ExpenseFilters & {
    limit?: number
    offset?: number
  }): Promise<ExpensesResponse> {
    const searchParams = new URLSearchParams()
    if (params?.start_date) searchParams.set('start_date', params.start_date)
    if (params?.end_date) searchParams.set('end_date', params.end_date)
    if (params?.category_id) searchParams.set('category_id', String(params.category_id))
    if (params?.paid_by) searchParams.set('paid_by', params.paid_by)
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))

    const query = searchParams.toString()
    return fetchApi<ExpensesResponse>(`/expenses${query ? `?${query}` : ''}`)
  },

  async getExpense(id: number): Promise<Expense> {
    return fetchApi<Expense>(`/expenses/${id}`)
  },

  async createExpense(data: CreateExpenseDto): Promise<Expense> {
    return fetchApi<Expense>('/expenses', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateExpense(id: number, data: Partial<CreateExpenseDto>): Promise<Expense> {
    return fetchApi<Expense>(`/expenses/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteExpense(id: number): Promise<{ success: boolean }> {
    return fetchApi(`/expenses/${id}`, {
      method: 'DELETE',
    })
  },

  async getExpenseStats(params?: {
    start_date?: string
    end_date?: string
  }): Promise<ExpenseStats> {
    const searchParams = new URLSearchParams()
    if (params?.start_date) searchParams.set('start_date', params.start_date)
    if (params?.end_date) searchParams.set('end_date', params.end_date)

    const query = searchParams.toString()
    return fetchApi<ExpenseStats>(`/expenses/stats${query ? `?${query}` : ''}`)
  },

  async getExpenseCategories(): Promise<ExpenseCategory[]> {
    return fetchApi<ExpenseCategory[]>('/expenses/categories')
  },

  async createExpenseCategory(data: { name: string; color?: string }): Promise<ExpenseCategory> {
    return fetchApi<ExpenseCategory>('/expenses/categories', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateExpenseCategory(id: number, data: { name?: string; color?: string }): Promise<ExpenseCategory> {
    return fetchApi<ExpenseCategory>(`/expenses/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteExpenseCategory(id: number): Promise<{ success: boolean }> {
    return fetchApi(`/expenses/categories/${id}`, {
      method: 'DELETE',
    })
  },

  // SSE endpoints (Server-Sent Events для real-time обновлений)
  sse: {
    /**
     * SSE endpoint для Live Feed — получение новых логов консультаций в реальном времени
     * @param lastEventId - ID последнего полученного события (для reconnect)
     */
    liveFeed: (lastEventId?: string): string => {
      const params = lastEventId ? `?last_event_id=${lastEventId}` : ''
      return `${API_BASE}/events/live-feed${params}`
    },

    /**
     * SSE endpoint для логов конкретного топика — получение новых сообщений в реальном времени
     * @param topicId - ID топика
     * @param lastEventId - ID последнего полученного события
     */
    topicLogs: (topicId: number, lastEventId?: string): string => {
      const params = lastEventId ? `?last_event_id=${lastEventId}` : ''
      return `${API_BASE}/events/logs/${topicId}${params}`
    },

    /**
     * SSE endpoint для статуса обработки документа — получение обновлений в реальном времени
     * @param documentId - ID документа
     */
    documentStatus: (documentId: number): string => {
      return `${API_BASE}/events/documents/${documentId}`
    },
  },
}
