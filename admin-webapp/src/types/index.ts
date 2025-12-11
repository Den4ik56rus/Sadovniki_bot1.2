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
export type View = 'users' | 'live' | 'stats' | 'documents'
