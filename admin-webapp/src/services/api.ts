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
} from '@/types'

const API_BASE = '/api/admin'
const CBR_API = 'https://www.cbr-xml-daily.ru/daily_json.js'

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
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
    })

    if (!response.ok) {
      throw new Error(`Delete failed: ${response.status}`)
    }

    return response.json()
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
