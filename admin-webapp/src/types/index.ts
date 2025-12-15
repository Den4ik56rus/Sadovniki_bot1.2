// Types for Admin Panel

export interface User {
  id: number
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  token_balance: number
  total_consultations: number
  total_tokens: number
  total_cost_usd: number
  last_consultation_at: string | null
}

export interface UsersResponse {
  users: User[]
  total: number
  limit: number
  offset: number
}

export interface Topic {
  id: number
  session_id: string
  status: 'open' | 'closed'
  culture: string | null
  category: string | null
  message_count: number
  total_tokens: number
  total_cost_usd: number
  created_at: string | null
  updated_at: string | null
}

export interface RagSnippet {
  source_type: 'qa' | 'document'
  priority_level: number
  content: string
  distance: number
  category: string | null
  subcategory: string | null
}

export interface LlmParams {
  model: string
  temperature: number
}

export interface ConsultationLog {
  id: number
  user_message: string
  bot_response: string
  system_prompt: string
  rag_snippets: RagSnippet[]
  llm_params: LlmParams
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_usd: number
  latency_ms: number
  consultation_category: string | null
  culture: string | null
  created_at: string | null
  composed_question: string | null  // Сформированный вопрос для RAG-поиска
  // Детализация стоимости и токенов по шагам
  embedding_tokens: number          // Токены для RAG embedding
  embedding_cost_usd: number        // Стоимость RAG embedding
  embedding_model: string | null    // Модель embedding (text-embedding-3-small, etc.)
  compose_cost_usd: number          // Стоимость форматирования вопроса (gpt-4o-mini)
  compose_tokens: number            // Токены форматирования вопроса
  llm_cost_usd: number              // Стоимость основного LLM вызова (gpt-4o)
  classification_cost_usd: number   // Стоимость классификации (gpt-4o)
  classification_tokens: number     // Токены классификации
}

export interface Message {
  id: number
  direction: 'user' | 'bot'
  text: string
  created_at: string | null
}

export interface TopicLogsResponse {
  topic: {
    id: number
    session_id: string
    status: string
    culture: string | null
    created_at: string | null
    updated_at: string | null
    user: {
      username: string | null
      first_name: string | null
      telegram_user_id: number
    }
  } | null
  logs: ConsultationLog[]
  messages: Message[]
}

export interface RecentLog {
  id: number
  user_id: number
  topic_id: number | null
  user_message: string
  bot_response: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_usd: number
  latency_ms: number
  consultation_category: string | null
  culture: string | null
  created_at: string | null
  user: {
    username: string | null
    first_name: string | null
    telegram_user_id: number
  }
}

export interface Stats {
  overview: {
    total_consultations: number
    total_tokens: number
    total_cost_usd: number
    avg_latency_ms: number
  }
  today: {
    consultations: number
    tokens: number
    cost_usd: number
  }
  by_culture: Array<{ culture: string; count: number }>
  by_category: Array<{ category: string; count: number }>
}

export interface EmbeddingModelStats {
  model: string
  consultations_tokens: number
  consultations_cost_usd: number
  documents_tokens: number
  documents_cost_usd: number
  total_tokens: number
  total_cost_usd: number
}

export interface EmbeddingStats {
  consultations: {
    tokens: number
    cost_usd: number
  }
  documents: {
    tokens: number
    cost_usd: number
  }
  total: {
    tokens: number
    cost_usd: number
  }
  by_model: EmbeddingModelStats[]
}

// Document types
export type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'

export interface Document {
  id: number
  filename: string
  subcategory: string
  status: DocumentStatus
  error: string | null
  chunks_count: number
  file_size: number
  embedding_tokens: number
  embedding_cost_usd: number
  created_at: string | null
}

export interface DocumentsResponse {
  documents: Document[]
  total: number
  subcategories: string[]
}

export interface UploadResponse {
  status: string
  filename: string
  subcategory: string
  message: string
}

// View types
export type View = 'users' | 'live' | 'stats' | 'documents' | 'crm'

// CRM Types
export type FunnelStatus = 'new' | 'tried' | 'trial_ended' | 'paid'

export interface CrmClient {
  id: number
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  user_created_at: string | null
  status: FunnelStatus
  auto_status: FunnelStatus | null
  manual_override: boolean
  status_updated_at: string | null
  total_consultations: number
  total_tokens: number
  total_cost_usd: number
  last_consultation_at: string | null
  token_balance?: number
  region?: string | null
}

export interface CrmClientsResponse {
  clients: Record<FunnelStatus, CrmClient[]>
  stats: Record<FunnelStatus, number>
}

export interface FunnelColumn {
  id: FunnelStatus
  title: string
  clients: CrmClient[]
}

// Extended CRM Types
export type ClientPriority = 'low' | 'normal' | 'high' | 'vip'
export type CustomFieldType = 'text' | 'number' | 'date' | 'checkbox' | 'select' | 'multiselect'
export type TaskPriority = 'low' | 'medium' | 'high'
export type TaskStatus = 'pending' | 'completed' | 'cancelled'
export type RepeatInterval = 'none' | 'daily' | 'weekly' | 'monthly'
export type ActivityEventType = 'consultation' | 'task_created' | 'task_completed' | 'note' | 'status_change' | 'tag_change' | 'field_change'

export interface ClientTag {
  id: number
  name: string
  color: string
  created_at?: string
}

export interface CustomField {
  id: number
  name: string
  field_type: CustomFieldType
  options: string[] | null
  sort_order: number
  is_required: boolean
  created_at?: string
}

export interface CustomFieldValue extends CustomField {
  value: string | number | boolean | string[] | null
}

export interface ClientTask {
  id: number
  user_id: number
  title: string
  description: string | null
  due_date: string | null
  priority: TaskPriority
  status: TaskStatus
  assignee: string | null
  reminder_at: string | null
  repeat_interval: RepeatInterval | null
  completed_at: string | null
  created_at: string
  updated_at: string
}

export interface ClientNote {
  id: number
  user_id: number
  text: string
  created_at: string
}

export interface ActivityEvent {
  id: number
  source?: 'activity' | 'topic'
  event_type: ActivityEventType
  event_data: Record<string, unknown>
  created_at: string
}

export interface CrmClientFull extends CrmClient {
  priority: ClientPriority
  source: string | null
  tags: ClientTag[]
  custom_fields: CustomFieldValue[]
}

// Create/Update DTOs
export interface CreateCustomFieldDto {
  name: string
  field_type: CustomFieldType
  options?: string[]
  sort_order?: number
  is_required?: boolean
}

export interface CreateTagDto {
  name: string
  color?: string
}

export interface CreateTaskDto {
  title: string
  description?: string
  due_date?: string
  priority?: TaskPriority
  assignee?: string
  reminder_at?: string
  repeat_interval?: RepeatInterval
}

export interface UpdateTaskDto extends Partial<CreateTaskDto> {
  status?: TaskStatus
}

export interface CreateNoteDto {
  text: string
}
