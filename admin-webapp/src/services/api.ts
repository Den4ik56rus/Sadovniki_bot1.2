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
  // RAG Documents v2.0
  RagDocument,
  RagDocumentsResponse,
  RagChunk,
  RagChunksResponse,
  PassportOptions,
  UpdatePassportDto,
  GenerateContextResponse,
  EmbedDocumentResponse,
  // Prompts
  PromptGroupsResponse,
  Prompt,
  PromptsResponse,
  PromptHistoryResponse,
  VersionDiffResponse,
  // Payments
  PaymentStatus,
  PaymentType,
  PaymentsResponse,
  PaymentStats,
  SubscriptionPlan,
  TokenPackage,
  // Prompt Preview
  PromptPreviewResponse,
  PromptPreviewOptionsResponse,
  // Chat History
  ChatHistoryResponse,
  // Invite Links
  InviteLink,
  InviteLinksResponse,
  // Guides
  GuideOrder,
  GuideOrdersResponse,
  GuideStats,
  // Server Metrics
  ServerMetrics,
  ServerMetricsHistory,
  OpenAIBalance,
  // Moderation
  ModerationStatus,
  ModerationItem,
  ModerationQueueResponse,
  ModerationStats,
  KBEntry,
  KBListResponse,
  // Broadcasts
  Broadcast,
  BroadcastsResponse,
  BroadcastRecipientsResponse,
  BroadcastUsersResponse,
  CreateBroadcastDto,
  BroadcastTargetType,
  BroadcastStats,
  BroadcastStatsUsersResponse,
  BroadcastRun,
  BroadcastRunsResponse,
  FunnelStageTrigger,
  FunnelTriggersResponse,
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
  async getClientFull(id: number, funnelId?: string): Promise<CrmClientFull> {
    const params = funnelId ? `?funnel_id=${encodeURIComponent(funnelId)}` : ''
    return fetchApi<CrmClientFull>(`/crm/clients/${id}/full${params}`)
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

  async updateClientBilling(
    id: number,
    data: {
      subscription_plan_id?: number | null
      subscription_started_at?: string | null
      subscription_expires_at?: string | null
      personal_discount_percent?: number
      personal_discount_valid_until?: string | null
      subscription_token_balance?: number
      purchased_token_balance?: number
    }
  ): Promise<{ success: boolean }> {
    return fetchApi(`/crm/clients/${id}/billing`, {
      method: 'PATCH',
      body: JSON.stringify(data),
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

  async getClientChatHistory(clientId: number): Promise<ChatHistoryResponse> {
    return fetchApi<ChatHistoryResponse>(`/crm/clients/${clientId}/chat`)
  },

  async sendMessageToClient(clientId: number, text: string): Promise<{ success: boolean; message_id: number }> {
    return fetchApi(`/crm/clients/${clientId}/send-message`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    })
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
  async getFunnelClients(funnelId: string, params?: { invite_link_id?: number }): Promise<FunnelClientsResponse> {
    const searchParams = new URLSearchParams()
    if (params?.invite_link_id) searchParams.set('invite_link_id', String(params.invite_link_id))
    const query = searchParams.toString()
    return fetchApi<FunnelClientsResponse>(`/funnels/${funnelId}/clients${query ? `?${query}` : ''}`)
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

  // ============================================================================
  // Moderation API (Модерация вопросов/ответов + База знаний)
  // ============================================================================

  async getModerationQueue(params?: {
    status?: ModerationStatus | 'all'
    limit?: number
    offset?: number
    sort?: 'oldest' | 'newest'
  }): Promise<ModerationQueueResponse> {
    const searchParams = new URLSearchParams()
    if (params?.status) searchParams.set('status', params.status)
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    if (params?.sort) searchParams.set('sort', params.sort)
    const query = searchParams.toString()
    return fetchApi<ModerationQueueResponse>(`/moderation/queue${query ? `?${query}` : ''}`)
  },

  async getModerationItem(id: number): Promise<ModerationItem> {
    return fetchApi<ModerationItem>(`/moderation/queue/${id}`)
  },

  async setModerationCategory(id: number, category: string): Promise<{ success: boolean }> {
    return fetchApi(`/moderation/queue/${id}/category`, {
      method: 'PATCH',
      body: JSON.stringify({ category }),
    })
  },

  async updateModerationAnswer(id: number, answer: string): Promise<{ success: boolean }> {
    return fetchApi(`/moderation/queue/${id}/answer`, {
      method: 'PATCH',
      body: JSON.stringify({ answer }),
    })
  },

  async editModerationAnswerAI(id: number, instructions: string): Promise<{ improved_answer: string }> {
    return fetchApi(`/moderation/queue/${id}/edit-ai`, {
      method: 'POST',
      body: JSON.stringify({ instructions }),
    })
  },

  async approveModerationItem(id: number): Promise<{ success: boolean; kb_id: number; category: string; subcategory: string }> {
    return fetchApi(`/moderation/queue/${id}/approve`, {
      method: 'POST',
    })
  },

  async rejectModerationItem(id: number): Promise<{ success: boolean }> {
    return fetchApi(`/moderation/queue/${id}/reject`, {
      method: 'POST',
    })
  },

  async getModerationStats(): Promise<ModerationStats> {
    return fetchApi<ModerationStats>('/moderation/stats')
  },

  // KB Browser
  async getKBEntries(params?: {
    search?: string
    category?: string
    subcategory?: string
    is_active?: boolean
    limit?: number
    offset?: number
  }): Promise<KBListResponse> {
    const searchParams = new URLSearchParams()
    if (params?.search) searchParams.set('search', params.search)
    if (params?.category) searchParams.set('category', params.category)
    if (params?.subcategory) searchParams.set('subcategory', params.subcategory)
    if (params?.is_active !== undefined) searchParams.set('is_active', String(params.is_active))
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    const query = searchParams.toString()
    return fetchApi<KBListResponse>(`/moderation/kb${query ? `?${query}` : ''}`)
  },

  async getKBEntry(id: number): Promise<KBEntry> {
    return fetchApi<KBEntry>(`/moderation/kb/${id}`)
  },

  async updateKBEntry(id: number, data: Partial<KBEntry>): Promise<{ success: boolean; entry: KBEntry }> {
    return fetchApi(`/moderation/kb/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  async getKBCategories(): Promise<{ categories: string[] }> {
    return fetchApi('/moderation/kb/categories')
  },

  async getKBSubcategories(): Promise<{ subcategories: string[] }> {
    return fetchApi('/moderation/kb/subcategories')
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

    /**
     * SSE endpoint для real-time обновлений воронки (CRM, Покупатели, кастомные)
     * @param funnelId - ID воронки ('crm', 'buyers', или UUID кастомной)
     */
    funnelEvents: (funnelId: string): string => {
      return `${API_BASE}/events/funnel/${funnelId}`
    },

    /**
     * SSE endpoint для real-time обновлений конкретного клиента
     * @param userId - Внутренний ID пользователя (users.id)
     */
    clientEvents: (userId: number): string => {
      return `${API_BASE}/events/client/${userId}`
    },
  },

  // ============================================
  // RAG Documents API v2.0 — Паспортизация чанков
  // ============================================

  async getRagDocuments(): Promise<RagDocumentsResponse> {
    const response = await fetch(`${API_BASE}/rag-documents`)
    if (!response.ok) throw new Error('Failed to fetch RAG documents')
    return response.json()
  },

  async getRagDocument(id: number): Promise<RagDocument> {
    const response = await fetch(`${API_BASE}/rag-documents/${id}`)
    if (!response.ok) throw new Error('RAG document not found')
    return response.json()
  },

  async getRagDocumentChunks(id: number): Promise<RagChunksResponse> {
    const response = await fetch(`${API_BASE}/rag-documents/${id}/chunks`)
    if (!response.ok) throw new Error('Failed to fetch chunks')
    return response.json()
  },

  async getPassportOptions(): Promise<PassportOptions> {
    const response = await fetch(`${API_BASE}/rag-documents/passport-options`)
    if (!response.ok) throw new Error('Failed to fetch passport options')
    return response.json()
  },

  async updateChunkPassport(chunkId: number, passport: UpdatePassportDto): Promise<{ success: boolean; chunk: RagChunk }> {
    const response = await fetch(`${API_BASE}/rag-documents/chunks/${chunkId}/passport`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(passport),
    })
    if (!response.ok) throw new Error('Failed to update passport')
    return response.json()
  },

  async generateChunkContext(chunkId: number): Promise<GenerateContextResponse> {
    const response = await fetch(`${API_BASE}/rag-documents/chunks/${chunkId}/generate-context`, {
      method: 'POST',
    })
    if (!response.ok) throw new Error('Failed to generate context')
    return response.json()
  },

  async deleteRagDocument(id: number): Promise<{ success: boolean; message: string }> {
    const response = await fetch(`${API_BASE}/rag-documents/${id}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('Failed to delete document')
    return response.json()
  },

  async clearAllRagDocuments(): Promise<{ success: boolean; deleted_documents: number; deleted_chunks: number }> {
    const response = await fetch(`${API_BASE}/rag-documents/clear-all`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('Failed to clear documents')
    return response.json()
  },

  async updateRagDocumentSubcategory(id: number, subcategory: string): Promise<{ success: boolean; document_id: number; subcategory: string }> {
    return fetchApi(`/rag-documents/${id}/subcategory`, {
      method: 'PATCH',
      body: JSON.stringify({ subcategory }),
    })
  },

  async embedRagDocument(id: number): Promise<EmbedDocumentResponse> {
    const response = await fetch(`${API_BASE}/rag-documents/${id}/embed`, {
      method: 'POST',
    })
    // Возвращаем JSON даже при ошибке, так как там может быть error message
    return response.json()
  },

  // ============================================================================
  // Admin Settings API (Глобальные настройки)
  // ============================================================================

  async getSettings(): Promise<{ settings: Array<{ key: string; value: string; description: string | null; updated_at: string }> }> {
    return fetchApi('/settings')
  },

  async updateSetting(key: string, value: string): Promise<{ setting: { key: string; value: string }; success: boolean }> {
    return fetchApi(`/settings/${key}`, {
      method: 'PATCH',
      body: JSON.stringify({ value }),
    })
  },

  // ============================================================================
  // Pricing API (Управление тарифами)
  // ============================================================================

  async getSubscriptionPlans(): Promise<{ plans: SubscriptionPlan[] }> {
    return fetchApi('/settings/pricing/plans')
  },

  async createSubscriptionPlan(data: {
    name: string
    price_rub: number
    tokens_included: number
    duration_days?: number
    description?: string
    max_carryover?: number
    token_discount_percent?: number
  }): Promise<{ plan: SubscriptionPlan; success: boolean }> {
    return fetchApi('/settings/pricing/plans', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateSubscriptionPlan(
    id: number,
    data: Partial<SubscriptionPlan>
  ): Promise<{ plan: SubscriptionPlan; success: boolean }> {
    return fetchApi(`/settings/pricing/plans/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async getTokenPackages(): Promise<{ packages: TokenPackage[] }> {
    return fetchApi('/settings/pricing/packages')
  },

  async createTokenPackage(data: {
    name: string
    price_rub: number
    tokens_amount: number
    description?: string
  }): Promise<{ package: TokenPackage; success: boolean }> {
    return fetchApi('/settings/pricing/packages', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateTokenPackage(
    id: number,
    data: Partial<TokenPackage>
  ): Promise<{ package: TokenPackage; success: boolean }> {
    return fetchApi(`/settings/pricing/packages/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  // ============================================================================
  // Payments API (Платежи и подписки)
  // ============================================================================

  async getUserPayments(
    userId: number,
    params?: { limit?: number; offset?: number; status?: PaymentStatus }
  ): Promise<PaymentsResponse> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    if (params?.status) searchParams.set('status', params.status)

    const query = searchParams.toString()
    return fetchApi<PaymentsResponse>(
      `/payments/user/${userId}${query ? `?${query}` : ''}`
    )
  },

  async getAllPayments(params?: {
    limit?: number
    offset?: number
    status?: PaymentStatus
    payment_type?: PaymentType
    user_id?: number
  }): Promise<PaymentsResponse> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    if (params?.status) searchParams.set('status', params.status)
    if (params?.payment_type) searchParams.set('payment_type', params.payment_type)
    if (params?.user_id) searchParams.set('user_id', String(params.user_id))

    const query = searchParams.toString()
    return fetchApi<PaymentsResponse>(`/payments${query ? `?${query}` : ''}`)
  },

  async getPaymentStats(period?: 'day' | 'week' | 'month' | 'all'): Promise<PaymentStats> {
    const query = period ? `?period=${period}` : ''
    return fetchApi<PaymentStats>(`/payments/stats${query}`)
  },

  // ============================================================================
  // Prompts API (Редактор промптов)
  // ============================================================================

  async getPromptGroups(): Promise<PromptGroupsResponse> {
    return fetchApi<PromptGroupsResponse>('/prompts/groups')
  },

  async getPrompts(filters?: { group_id?: number; subgroup_id?: number; is_enabled?: boolean }): Promise<PromptsResponse> {
    const params = new URLSearchParams()
    if (filters?.group_id !== undefined) params.set('group_id', String(filters.group_id))
    if (filters?.subgroup_id !== undefined) params.set('subgroup_id', String(filters.subgroup_id))
    if (filters?.is_enabled !== undefined) params.set('is_enabled', String(filters.is_enabled))
    const queryString = params.toString()
    return fetchApi<PromptsResponse>(`/prompts${queryString ? `?${queryString}` : ''}`)
  },

  async getPrompt(id: number): Promise<{ prompt: Prompt }> {
    return fetchApi<{ prompt: Prompt }>(`/prompts/${id}`)
  },

  async updatePrompt(id: number, content: string, updatedBy?: string): Promise<{ prompt: Prompt; success: boolean }> {
    return fetchApi<{ prompt: Prompt; success: boolean }>(`/prompts/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ content, updated_by: updatedBy || 'admin' }),
    })
  },

  async togglePromptEnabled(id: number, enabled: boolean): Promise<{ prompt: Prompt; success: boolean }> {
    return fetchApi<{ prompt: Prompt; success: boolean }>(`/prompts/${id}/toggle`, {
      method: 'PATCH',
      body: JSON.stringify({ enabled }),
    })
  },

  async getPromptHistory(id: number): Promise<PromptHistoryResponse> {
    return fetchApi<PromptHistoryResponse>(`/prompts/${id}/history`)
  },

  async getPromptVersionDiff(id: number, version: number): Promise<VersionDiffResponse> {
    return fetchApi<VersionDiffResponse>(`/prompts/${id}/history/${version}/diff`)
  },

  async revertPromptToVersion(id: number, version: number, revertedBy?: string): Promise<{ prompt: Prompt; success: boolean }> {
    return fetchApi<{ prompt: Prompt; success: boolean }>(`/prompts/${id}/revert`, {
      method: 'POST',
      body: JSON.stringify({ version, reverted_by: revertedBy || 'admin' }),
    })
  },

  // ============================================================================
  // Prompt Preview API (Превью собранного промпта)
  // ============================================================================

  async getPromptPreviewOptions(): Promise<PromptPreviewOptionsResponse> {
    return fetchApi<PromptPreviewOptionsResponse>('/prompts/preview/options')
  },

  async getPromptPreview(category: string, culture: string): Promise<PromptPreviewResponse> {
    const params = new URLSearchParams()
    params.set('category', category)
    params.set('culture', culture)
    return fetchApi<PromptPreviewResponse>(`/prompts/preview?${params.toString()}`)
  },

  // =========================================================================
  // Invite Links (Инвайт-ссылки)
  // =========================================================================

  async getInviteLinks(params?: { start_date?: string; end_date?: string }): Promise<InviteLinksResponse> {
    const searchParams = new URLSearchParams()
    if (params?.start_date) searchParams.set('start_date', params.start_date)
    if (params?.end_date) searchParams.set('end_date', params.end_date)
    const query = searchParams.toString()
    return fetchApi<InviteLinksResponse>(`/invite-links${query ? `?${query}` : ''}`)
  },

  async createInviteLink(data: { name: string; bonus_tokens?: number; discount_percent?: number; discount_duration_days?: number; max_users?: number }): Promise<InviteLink> {
    return fetchApi<InviteLink>('/invite-links', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async updateInviteLink(id: number, data: { name: string; bonus_tokens?: number; discount_percent?: number; discount_duration_days?: number; max_users?: number }): Promise<InviteLink> {
    return fetchApi<InviteLink>(`/invite-links/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    })
  },

  async toggleInviteLinkActive(id: number, is_active: boolean): Promise<InviteLink> {
    return fetchApi<InviteLink>(`/invite-links/${id}/toggle`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active }),
    })
  },

  async deleteInviteLink(id: number): Promise<{ success: boolean }> {
    return fetchApi<{ success: boolean }>(`/invite-links/${id}`, {
      method: 'DELETE',
    })
  },

  // =========================================================================
  // Guides (Готовые решения — PDF-гайды)
  // =========================================================================

  async getGuideOrders(params?: {
    limit?: number
    offset?: number
    status?: string
  }): Promise<GuideOrdersResponse> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    if (params?.status) searchParams.set('status', params.status)
    const query = searchParams.toString()
    return fetchApi<GuideOrdersResponse>(`/guides${query ? `?${query}` : ''}`)
  },

  async getGuideStats(): Promise<GuideStats> {
    return fetchApi<GuideStats>('/guides/stats')
  },

  async getGuideDetail(id: number): Promise<GuideOrder> {
    return fetchApi<GuideOrder>(`/guides/${id}`)
  },

  // =========================================================================
  // Server Metrics (Мониторинг сервера)
  // =========================================================================

  async getServerMetrics(): Promise<ServerMetrics> {
    return fetchApi<ServerMetrics>('/server-metrics')
  },

  async getServerMetricsHistory(hours?: number): Promise<ServerMetricsHistory> {
    const query = hours ? `?hours=${hours}` : ''
    return fetchApi<ServerMetricsHistory>(`/server-metrics/history${query}`)
  },

  // =========================================================================
  // OpenAI Balance (Мониторинг расходов OpenAI)
  // =========================================================================

  async getOpenAIBalance(days?: number): Promise<OpenAIBalance> {
    const query = days ? `?days=${days}` : ''
    return fetchApi<OpenAIBalance>(`/openai-balance${query}`)
  },

  async updateOpenAIBudget(budgetUsd: number): Promise<{ success: boolean; budget_usd: number }> {
    return fetchApi<{ success: boolean; budget_usd: number }>('/openai-balance/budget', {
      method: 'PATCH',
      body: JSON.stringify({ budget_usd: budgetUsd }),
    })
  },

  // =========================================================================
  // Broadcasts (Рассылки)
  // =========================================================================

  async getBroadcasts(params?: { limit?: number; offset?: number }): Promise<BroadcastsResponse> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))
    const query = searchParams.toString()
    return fetchApi<BroadcastsResponse>(`/broadcasts${query ? `?${query}` : ''}`)
  },

  async createBroadcast(data: CreateBroadcastDto): Promise<Broadcast> {
    return fetchApi<Broadcast>('/broadcasts', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async getBroadcast(id: number): Promise<Broadcast> {
    return fetchApi<Broadcast>(`/broadcasts/${id}`)
  },

  async updateBroadcast(id: number, data: Partial<CreateBroadcastDto>): Promise<Broadcast> {
    return fetchApi<Broadcast>(`/broadcasts/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async deleteBroadcast(id: number): Promise<{ success: boolean }> {
    return fetchApi<{ success: boolean }>(`/broadcasts/${id}`, {
      method: 'DELETE',
    })
  },

  async deleteBroadcastsBulk(ids: number[]): Promise<{ success: boolean; deleted_count: number }> {
    return fetchApi<{ success: boolean; deleted_count: number }>('/broadcasts/bulk-delete', {
      method: 'POST',
      body: JSON.stringify({ ids }),
    })
  },

  async sendBroadcast(id: number): Promise<{ success: boolean; total_recipients: number }> {
    return fetchApi<{ success: boolean; total_recipients: number }>(`/broadcasts/${id}/send`, {
      method: 'POST',
    })
  },

  async testSendBroadcast(id: number): Promise<{ success: boolean; admin_count: number }> {
    return fetchApi<{ success: boolean; admin_count: number }>(`/broadcasts/${id}/test-send`, {
      method: 'POST',
    })
  },

  async scheduleBroadcast(id: number, scheduledAt: string): Promise<Broadcast> {
    return fetchApi<Broadcast>(`/broadcasts/${id}/schedule`, {
      method: 'POST',
      body: JSON.stringify({ scheduled_at: scheduledAt }),
    })
  },

  async cancelBroadcast(id: number): Promise<{ success: boolean }> {
    return fetchApi<{ success: boolean }>(`/broadcasts/${id}/cancel`, {
      method: 'POST',
    })
  },

  async getBroadcastRecipients(id: number, status?: string): Promise<BroadcastRecipientsResponse> {
    const query = status ? `?status=${status}` : ''
    return fetchApi<BroadcastRecipientsResponse>(`/broadcasts/${id}/recipients${query}`)
  },

  async previewBroadcastCount(data: {
    target_type: BroadcastTargetType
    target_invite_link_id?: number | null
    target_funnel_id?: string | null
    target_stage_key?: string | null
    target_user_ids?: number[] | null
  }): Promise<{ count: number }> {
    return fetchApi<{ count: number }>('/broadcasts/preview-count', {
      method: 'POST',
      body: JSON.stringify(data),
    })
  },

  async getBroadcastUsers(): Promise<BroadcastUsersResponse> {
    return fetchApi<BroadcastUsersResponse>('/broadcasts/users')
  },

  async uploadBroadcastPhoto(file: File): Promise<{ photo_path: string }> {
    const formData = new FormData()
    formData.append('photo', file)
    const response = await fetch(`${API_BASE}/broadcasts/upload-photo`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      const text = await response.text()
      throw new Error(text || 'Upload failed')
    }
    return response.json()
  },

  async getBroadcastStats(id: number): Promise<BroadcastStats> {
    return fetchApi<BroadcastStats>(`/broadcasts/${id}/stats`)
  },

  async getBroadcastStatUsers(id: number, type: 'button' | 'poll', key: string): Promise<BroadcastStatsUsersResponse> {
    const param = type === 'button' ? `key=${key}` : `option=${key}`
    return fetchApi<BroadcastStatsUsersResponse>(`/broadcasts/${id}/stats/users?type=${type}&${param}`)
  },

  // Broadcast Runs (повторные запуски)
  async resendBroadcast(id: number, data: {
    target_type: BroadcastTargetType
    target_invite_link_id?: number | null
    target_funnel_id?: string | null
    target_stage_key?: string | null
    target_user_ids?: number[] | null
  }): Promise<{ success: boolean; run: BroadcastRun; total_recipients: number }> {
    return fetchApi(`/broadcasts/${id}/resend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  async getBroadcastRuns(id: number): Promise<BroadcastRunsResponse> {
    return fetchApi<BroadcastRunsResponse>(`/broadcasts/${id}/runs`)
  },

  async getRunStats(broadcastId: number, runId: number): Promise<BroadcastStats> {
    return fetchApi<BroadcastStats>(`/broadcasts/${broadcastId}/runs/${runId}/stats`)
  },

  async getRunStatUsers(broadcastId: number, runId: number, type: 'button' | 'poll', key: string): Promise<BroadcastStatsUsersResponse> {
    const param = type === 'button' ? `key=${key}` : `option=${key}`
    return fetchApi<BroadcastStatsUsersResponse>(`/broadcasts/${broadcastId}/runs/${runId}/stats/users?type=${type}&${param}`)
  },

  async getRunRecipients(broadcastId: number, runId: number, status?: string): Promise<BroadcastRecipientsResponse> {
    const query = status ? `?status=${status}` : ''
    return fetchApi<BroadcastRecipientsResponse>(`/broadcasts/${broadcastId}/runs/${runId}/recipients${query}`)
  },

  // Broadcast Reminders (напоминалки)
  async cancelReminder(broadcastId: number, reminderId: number): Promise<{ success: boolean }> {
    return fetchApi<{ success: boolean }>(`/broadcasts/${broadcastId}/reminders/${reminderId}/cancel`, {
      method: 'POST',
    })
  },

  // Funnel Stage Triggers
  async getFunnelTriggers(funnelId: string): Promise<FunnelTriggersResponse> {
    return fetchApi<FunnelTriggersResponse>(`/funnels/${funnelId}/triggers`)
  },

  async getStageTriggers(funnelId: string, stageKey: string): Promise<FunnelTriggersResponse> {
    return fetchApi<FunnelTriggersResponse>(`/funnels/${funnelId}/stages/${stageKey}/triggers`)
  },

  async createStageTrigger(
    funnelId: string,
    stageKey: string,
    broadcastId: number,
    delayMinutes?: number,
    paymentConfig?: import('@/types').TriggerPaymentConfig | null,
  ): Promise<{ trigger: FunnelStageTrigger }> {
    return fetchApi(`/funnels/${funnelId}/stages/${stageKey}/triggers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        broadcast_id: broadcastId,
        delay_minutes: delayMinutes ?? 0,
        payment_config: paymentConfig ?? null,
      }),
    })
  },

  async deleteStageTrigger(triggerId: number): Promise<{ success: boolean }> {
    return fetchApi(`/funnels/triggers/${triggerId}`, {
      method: 'DELETE',
    })
  },

  async toggleStageTrigger(triggerId: number, isActive: boolean): Promise<{ trigger: FunnelStageTrigger }> {
    return fetchApi(`/funnels/triggers/${triggerId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: isActive }),
    })
  },

  async updateStageTrigger(
    triggerId: number,
    updates: {
      is_active?: boolean
      delay_minutes?: number
      payment_config?: import('@/types').TriggerPaymentConfig | null
    },
  ): Promise<{ trigger: FunnelStageTrigger }> {
    return fetchApi(`/funnels/triggers/${triggerId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
  },
}
