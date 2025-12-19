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
export type View = 'dashboard' | 'crm' | 'messages' | 'buyers' | 'tasks' | 'lists' | 'stats' | 'settings' | 'users' | 'live' | 'documents' | 'expenses' | 'prompt-docs' | 'rag-docs' | 'prompts'

// CRM Types
// FunnelStatus can be standard statuses or custom column IDs like 'custom_1', 'custom_2', etc.
export type FunnelStatus = 'new' | 'tried' | 'trial_ended' | 'paid' | `custom_${number}`

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
  source: string | null
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

// Funnel column configuration (from backend)
export interface FunnelColumnConfig {
  id: FunnelStatus
  title: string
  color: string
  sort_order: number
  is_system: boolean
}

// Extended CRM Types
export type ClientPriority = 'low' | 'normal' | 'high' | 'vip'
export type CustomFieldType = 'text' | 'number' | 'date' | 'checkbox' | 'select' | 'multiselect'
export type TaskPriority = 'low' | 'medium' | 'high'
export type TaskStatus = 'pending' | 'completed' | 'cancelled'
export type RepeatInterval = 'none' | 'daily' | 'weekly' | 'monthly'
export type ActivityEventType = 'consultation' | 'task_created' | 'task_completed' | 'note' | 'status_change' | 'tag_change' | 'field_change' | 'article'

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

// =============================================================================
// Buyers Types (Покупатели)
// =============================================================================

// BuyerStatus can be standard statuses or custom column IDs like 'custom_1', 'custom_2', etc.
export type BuyerStatus = 'pending_payment' | 'paid' | 'active' | 'expired' | `custom_${number}`

export interface Buyer {
  id: number
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  user_created_at: string | null
  status: BuyerStatus
  manual_override: boolean
  status_updated_at: string | null
  buyer_created_at: string | null
  source: string | null
  total_consultations: number
  total_tokens: number
  total_cost_usd: number
  last_consultation_at: string | null
  token_balance?: number
  region?: string | null
}

export interface BuyersResponse {
  buyers: Record<BuyerStatus, Buyer[]>
  stats: Record<BuyerStatus, number>
}

export interface BuyerColumnConfig {
  id: BuyerStatus
  title: string
  color: string
  sort_order: number
  is_system: boolean
}

export interface BuyerFull extends Buyer {
  priority: ClientPriority
  source: string | null
  tags: ClientTag[]
  custom_fields: CustomFieldValue[]
  buyer_status: BuyerStatus
}

// =============================================================================
// Unified Funnels Types (Универсальная система воронок)
// =============================================================================

export interface Funnel {
  id: string
  title: string
  description: string | null
  icon: string
  sort_order: number
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface FunnelStage {
  id: number
  funnel_id: string
  stage_key: string
  title: string
  color: string
  sort_order: number
  is_system: boolean
}

export interface FunnelClient {
  id: number
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  user_created_at: string | null
  status: string  // stage_key
  manual_override: boolean
  entered_at: string | null
  status_updated_at: string | null
  total_consultations: number
  total_tokens: number
  total_cost_usd: number
  last_consultation_at: string | null
}

export interface FunnelClientsResponse {
  clients: Record<string, FunnelClient[]>
  stats: Record<string, number>
}

export interface FunnelsResponse {
  funnels: Funnel[]
}

export interface FunnelStagesResponse {
  stages: FunnelStage[]
}

export interface CreateFunnelDto {
  id: string
  title: string
  description?: string
  icon?: string
  stages?: Array<{
    stage_key: string
    title: string
    color?: string
  }>
}

export interface CreateStageDto {
  stage_key?: string
  title: string
  color?: string
}

export interface ClientFunnelInfo {
  funnel_id: string
  funnel_title: string
  stage_key: string
  stage_title: string | null
  entered_at: string
  updated_at: string
}

// =============================================================================
// Admin Articles Types (Статьи, сгенерированные администратором)
// =============================================================================

export interface AdminArticle {
  id: number
  admin_telegram_id: number
  topic: string
  article_text: string
  rag_snippets: RagSnippet[] | null
  rag_snippets_count: number
  system_prompt: string | null
  embedding_tokens: number
  llm_prompt_tokens: number
  llm_completion_tokens: number
  total_tokens: number
  cost_usd: number
  llm_model: string | null
  created_at: string
}

export interface AdminArticleListItem {
  id: number
  admin_telegram_id: number
  topic: string
  article_length: number
  rag_snippets_count: number
  total_tokens: number
  cost_usd: number
  llm_model: string | null
  created_at: string
}

export interface AdminArticlesResponse {
  articles: AdminArticleListItem[]
  total: number
  limit: number
  offset: number
}

// =============================================================================
// Expenses Types (Расходы проекта)
// =============================================================================

export interface ExpenseCategory {
  id: number
  name: string
  color: string
  icon: string
  is_system: boolean
  sort_order: number
  created_at?: string
}

export interface Expense {
  id: number
  date: string
  name: string
  category_id: number | null
  category_name?: string
  category_color?: string
  category_icon?: string
  amount: number
  paid_by: 'Денис' | 'Данил'
  created_at: string
  updated_at: string
}

export interface ExpensesResponse {
  expenses: Expense[]
  total: number
  limit: number
  offset: number
}

export interface ExpenseStats {
  total_amount: number
  by_category: Array<{
    category_id: number | null
    category_name: string | null
    color: string | null
    amount: number
    count: number
  }>
  by_paid_by: Array<{
    paid_by: string
    amount: number
    count: number
  }>
}

export interface CreateExpenseDto {
  date: string
  name: string
  category_id: number
  amount: number
  paid_by: 'Денис' | 'Данил' | 'Оба'
}

export interface ExpenseFilters {
  start_date?: string
  end_date?: string
  category_id?: number
  paid_by?: string
}

// =============================================================================
// Prompt Documents Types (Документы для промптов)
// =============================================================================

export interface PromptCulture {
  id: number
  name: string
  sort_order: number
  created_at?: string
}

export interface PromptSubculture {
  id: number
  culture_id: number
  name: string
  sort_order: number
  created_at?: string
}

export interface PromptWorkType {
  id: number
  name: string
  sort_order: number
  created_at?: string
}

export type PromptDocumentExtractionStatus = 'pending' | 'completed' | 'failed'

export interface PromptDocument {
  id: number
  culture_id: number
  culture_name: string
  subculture_id: number | null
  subculture_name: string | null
  work_type_id: number
  work_type_name: string
  filename: string
  original_filename: string
  file_size: number
  file_type: string
  extraction_status: PromptDocumentExtractionStatus
  extraction_error: string | null
  created_at: string
  updated_at: string
}

export interface PromptDocumentsResponse {
  documents: PromptDocument[]
  total: number
}

export interface PromptDocumentFilters {
  culture_id?: number
  subculture_id?: number
  work_type_id?: number
}

// ============================================
// RAG Documents v2.0 — Паспортизация чанков
// ============================================

export interface RagDocument {
  id: number
  filename: string
  subcategory: string | null
  status: DocumentStatus
  error: string | null
  chunks_count: number
  passported_chunks: number
  file_size: number
  context_cost: number
  context_tokens: number
  created_at: string | null
}

export interface RagDocumentsResponse {
  documents: RagDocument[]
  total: number
}

export interface RagChunk {
  id: number
  chunk_index: number
  chunk_text: string
  chunk_size: number
  page_number: number | null
  culture: string | null
  culture_subtype: string | null
  goal: string | null
  growth_phase: string | null
  prefix: string | null
  context: string | null
  is_passported: boolean
  created_at: string | null
}

export interface RagChunksResponse {
  document_id: number
  filename: string
  chunks: RagChunk[]
  total: number
}

export interface PassportOption {
  id: number
  name: string
}

export interface PassportOptions {
  cultures: PassportOption[]
  subtypes: Record<number, PassportOption[]>
  goals: PassportOption[]
  phases: PassportOption[]
}

export interface UpdatePassportDto {
  culture: string | null
  culture_subtype: string | null
  goal: string | null
  growth_phase: string | null
}

export interface GenerateContextResponse {
  success: boolean
  context: string
  tokens: {
    input: number
    output: number
  }
  cost: number
  chunk: {
    id: number
    context: string
  }
}

// =============================================================================
// Prompts Types (Редактор промптов)
// =============================================================================

export interface PromptSubgroup {
  id: number
  slug: string
  name: string
  description: string | null
  sort_order: number
  is_system: boolean
  prompts_count: number
}

export interface PromptGroup {
  id: number
  slug: string
  name: string
  description: string | null
  icon: string | null
  sort_order: number
  is_system: boolean
  prompts_count: number
  subgroups: PromptSubgroup[]
}

export interface Prompt {
  id: number
  group_id: number
  subgroup_id: number | null
  slug: string
  name: string
  description: string | null
  content: string
  is_enabled: boolean
  use_minimal_base: boolean
  is_system: boolean
  version: number
  updated_by: string | null
  created_at: string
  updated_at: string
  group_slug?: string
  group_name?: string
  subgroup_slug?: string | null
  subgroup_name?: string | null
}

export interface PromptHistoryItem {
  id: number
  version: number
  content: string
  changed_by: string | null
  change_reason: string | null
  created_at: string
}

export interface PromptGroupsResponse {
  groups: PromptGroup[]
}

export interface PromptsResponse {
  prompts: Prompt[]
}

export interface PromptHistoryResponse {
  history: PromptHistoryItem[]
}

// Diff для сравнения версий
export interface DiffChange {
  type: 'unchanged' | 'added' | 'removed'
  line: string
  old_line_number: number | null
  new_line_number: number | null
}

export interface DiffResult {
  unified: string
  lines_added: number
  lines_removed: number
  changes: DiffChange[]
}

export interface VersionDiffResponse {
  diff: DiffResult
  version: PromptHistoryItem
  current_version: number
}
