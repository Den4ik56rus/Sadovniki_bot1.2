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
  // Complexity tracking
  complexity_tier: string | null             // short_answer | long_answer | turnkey_solution
  complexity_metadata: Record<string, unknown>
  complexity_classification_cost_usd: number // Стоимость классификатора сложности
  complexity_classification_tokens: number   // Токены классификатора сложности
}

export interface KeyboardButton {
  text: string
  callback_data?: string
}

export interface KeyboardMeta {
  type: 'inline' | 'reply'
  buttons: KeyboardButton[][]
}

export interface Message {
  id: number
  direction: 'user' | 'bot' | 'system'
  text: string
  created_at: string | null
  topic_id?: number | null
  meta?: {
    keyboard?: KeyboardMeta
    type?: 'callback' | 'manual'
    callback_data?: string
    source?: 'admin' | string
  } | null
}

export interface ChatHistoryTopic {
  id: number
  culture: string | null
  category: string | null
  status: string
  created_at: string | null
}

export interface ChatHistoryResponse {
  messages: Message[]
  topics: ChatHistoryTopic[]
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

// Image Generator
export interface ImageGeneration {
  id: number
  user_prompt: string
  optimized_prompt: string | null
  preset: string
  image_path: string | null
  reference_image_path: string | null
  image_model: string
  status: 'pending' | 'optimizing' | 'generating' | 'completed' | 'failed'
  error_message: string | null
  input_tokens: number
  output_tokens: number
  prompt_tokens: number
  prompt_completion_tokens: number
  cost_usd: number
  created_at: string
}

export interface ImageGeneratorPreset {
  key: string
  label: string
  description: string
  requires_reference: boolean
}

// View types
export type View = 'dashboard' | 'crm' | 'messages' | 'buyers' | 'tasks' | 'lists' | 'stats' | 'settings' | 'users' | 'live' | 'documents' | 'expenses' | 'rag-docs' | 'prompts' | 'prompt-preview' | 'payments' | 'invite-links' | 'guides' | 'moderation' | 'ab-test' | 'triggers' | 'articles' | 'presentations' | 'batch-presentations' | 'batch-article-presentations' | 'image-generator'

// CRM Types
// FunnelStatus can be standard statuses or custom column IDs like 'custom_1', 'custom_2', etc.
export type FunnelStatus = 'new' | 'tried' | 'trial_ended' | 'paid' | `custom_${number}`

export interface CrmClient {
  id: number
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  avatar_url?: string | null
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
export type ActivityEventType = 'consultation' | 'chat_message' | 'task_created' | 'task_completed' | 'note' | 'status_change' | 'tag_change' | 'field_change' | 'article' | 'payment' | 'broadcast_sent' | 'broadcast_button_click' | 'broadcast_poll_answer'

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
  source?: 'activity' | 'topic' | 'message'
  event_type: ActivityEventType
  event_data: Record<string, unknown>
  created_at: string
}

export interface ReferrerInfo {
  id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  created_at: string
}

export interface CrmClientFull extends CrmClient {
  priority: ClientPriority
  source: string | null
  tags: ClientTag[]
  custom_fields: CustomFieldValue[]
  referrer?: ReferrerInfo | null
  referrals_count?: number
  referral_code?: string | null
  // Billing data
  sub_id?: number | null
  subscription_plan_id?: number | null
  subscription_plan_name?: string | null
  subscription_started_at?: string | null
  subscription_expires_at?: string | null
  subscription_status?: string | null
  personal_discount_percent?: number
  personal_discount_valid_until?: string | null
  subscription_token_balance?: number
  purchased_token_balance?: number
  // Funnel & Quiz
  funnel_variant?: string | null
  quiz_culture?: string | null
  quiz_region?: string | null
  quiz_problem?: string | null
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
  avatar_url?: string | null
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
  avatar_url?: string | null
  user_created_at: string | null
  status: string  // stage_key
  manual_override: boolean
  entered_at: string | null
  status_updated_at: string | null
  total_consultations: number
  total_tokens: number
  total_cost_usd: number
  last_consultation_at: string | null
  token_balance: number
  subscription_plan_name: string | null
  subscription_status: string | null
  subscription_expires_at: string | null
  latest_purchase_type: string | null  // 'subscription' | 'seasonal_program' | 'single_block'
}

export type FunnelSortOption =
  | 'last_activity_desc' | 'last_activity_asc'
  | 'entered_desc' | 'entered_asc'
  | 'cost_desc' | 'cost_asc'

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

export interface GenerateArticleDto {
  topic: string
  category?: string | null
  culture?: string | null
  model_override?: string | null
  reasoning_effort?: string | null
  use_scripts: boolean
  use_problem_solving: boolean
  use_rag: boolean
}

export interface GenerateArticleResponse {
  article_id: number
  article: AdminArticle
}

// =============================================================================
// Presentations Types (AI-генерация слайдов)
// =============================================================================

export interface PresentationStyle {
  id: number
  name: string
  description: string | null
  style_xml: string
  created_at: string
  updated_at: string
}

export interface PresentationTemplate {
  id: number
  name: string
  description: string | null
  template_text: string
  created_at: string
  updated_at: string
}

export interface SlideVersion {
  id: number
  slide_id: number
  version_number: number
  image_path: string | null
  edit_instruction: string | null
  nbp_prompt: string
  nbp_input_tokens: number
  nbp_output_tokens: number
  nbp_cost_usd: number
  status: 'pending' | 'generating' | 'completed' | 'failed'
  error_message: string | null
  created_at: string
}

export interface PresentationSlide {
  id: number
  presentation_id: number
  slide_index: number
  slide_title: string | null
  slide_prompt: string
  slide_notes: string | null
  created_at: string
  versions: SlideVersion[]
}

export interface Presentation {
  id: number
  title: string
  source_text: string
  style_id: number | null
  template_id: number | null
  status: 'draft' | 'generating' | 'completed' | 'failed'
  slide_count: number
  llm_model: string | null
  reasoning_effort: string | null
  text_prompt_tokens: number
  text_completion_tokens: number
  text_cost_usd: number
  image_input_tokens: number
  image_output_tokens: number
  image_cost_usd: number
  total_cost_usd: number
  generation_mode?: 'article' | 'problem'
  culture_key?: string | null
  variety_key?: string | null
  problem_key?: string | null
  article_cost_usd?: number
  article_prompt_tokens?: number
  article_completion_tokens?: number
  custom_system_prompt?: string | null
  pdf_path: string | null
  error_message: string | null
  created_at: string
  updated_at: string
  slides?: PresentationSlide[]
}

export interface PresentationListItem {
  id: number
  title: string
  status: string
  slide_count: number
  llm_model: string | null
  total_cost_usd: number
  pdf_path: string | null
  created_at: string
  updated_at: string
}

export interface PresentationsResponse {
  presentations: PresentationListItem[]
  total: number
  limit: number
  offset: number
}

export interface CreatePresentationDto {
  title: string
  source_text: string
  style_id?: number | null
  template_id?: number | null
  llm_model?: string | null
  reasoning_effort?: string | null
  image_model?: string | null
  test_slide_index?: number | null
  generation_mode?: 'article' | 'problem' | 'category'
  culture_key?: string | null
  variety_key?: string | null
  problem_key?: string | null
  category_key?: string | null
  custom_system_prompt?: string | null
}

export interface ProblemDef {
  key: string
  label: string
  hint?: string | null
}

export interface CultureDef {
  key: string
  label: string
  has_varieties: boolean
  varieties: { key: string; label: string }[]
  problems: Record<string, ProblemDef[]>
}

export interface PresentationStylesResponse {
  styles: PresentationStyle[]
}

export interface PresentationTemplatesResponse {
  templates: PresentationTemplate[]
}

export interface CompletedSlideInfo {
  slide_index: number
  version_id: number
  slide_id: number
  slide_title: string
}

export interface PresentationProgressEvent {
  type: string
  presentation_id?: number
  slide_index?: number
  slide_count?: number
  slide_title?: string
  slide_cost_usd?: number
  total_image_cost_usd?: number
  text_cost_usd?: number
  total_cost_usd?: number
  message?: string
  error?: string
  version_id?: number
  slide_id?: number
  article_cost_usd?: number
  article_length?: number
}

export interface ImageModelInfo {
  id: string
  name: string
  input_price_per_1m: number
  output_price_per_1m: number
  cost_per_image: number
}

// =============================================================================
// Presentation Batch Types (Пакетная генерация)
// =============================================================================

export interface BatchItem {
  id: number
  batch_id: number
  culture_key: string
  variety_key: string | null
  problem_key: string
  status: 'pending' | 'generating' | 'completed' | 'failed' | 'skipped'
  presentation_id: number | null
  content_pdf_path: string | null
  error_message: string | null
  retry_count: number
  started_at: string | null
  finished_at: string | null
  sort_order: number
}

export interface Batch {
  id: number
  status: 'pending' | 'running' | 'completed' | 'cancelled'
  style_id: number | null
  template_id: number | null
  llm_model: string | null
  reasoning_effort: string | null
  image_model: string | null
  custom_system_prompt: string | null
  total_items: number
  completed_items: number
  failed_items: number
  current_item_index: number | null
  total_cost_usd: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  error_message: string | null
  items?: BatchItem[]
}

export interface BatchListItem {
  id: number
  status: string
  total_items: number
  completed_items: number
  failed_items: number
  current_item_index: number | null
  total_cost_usd: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  llm_model: string | null
  image_model: string | null
  style_id: number | null
}

export interface BatchesResponse {
  batches: BatchListItem[]
  total: number
  limit: number
  offset: number
}

export interface CreateBatchDto {
  items: { culture_key: string; variety_key?: string | null; problem_key: string }[]
  style_id?: number | null
  template_id?: number | null
  llm_model?: string | null
  reasoning_effort?: string | null
  image_model?: string | null
  custom_system_prompt?: string | null
}

export interface BatchProgressEvent {
  batch_id: number
  item_id?: number
  index?: number
  total?: number
  title?: string
  culture?: string
  problem?: string
  presentation_id?: number
  cost?: number
  error?: string
  // Inherited from presentation progress
  type?: string
  slide_index?: number
  slide_count?: number
  slide_title?: string
  message?: string
}

// =============================================================================
// Article Batch Types (Пакетная генерация статей)
// =============================================================================

export interface ArticleCategoryDef {
  key: string
  label: string
  consultation_category: string
}

export interface ArticleCultureDef {
  culture_key: string
  variety_key: string | null
  label: string
  culture_russian: string
}

export interface ArticleDefinitionsResponse {
  categories: ArticleCategoryDef[]
  cultures: ArticleCultureDef[]
}

export interface ArticleBatchItem {
  id: number
  batch_id: number
  culture_key: string
  variety_key: string | null
  category_key: string
  topic: string
  culture_label: string
  category_label: string
  status: 'pending' | 'generating' | 'completed' | 'failed' | 'skipped'
  article_id: number | null
  error_message: string | null
  started_at: string | null
  finished_at: string | null
  sort_order: number
}

export interface ArticleBatch {
  id: number
  status: 'pending' | 'running' | 'completed' | 'cancelled'
  llm_model: string | null
  total_items: number
  completed_items: number
  failed_items: number
  current_item_index: number | null
  total_cost_usd: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  items?: ArticleBatchItem[]
}

export interface ArticleBatchListItem {
  id: number
  status: string
  total_items: number
  completed_items: number
  failed_items: number
  current_item_index: number | null
  total_cost_usd: number
  created_at: string
  started_at: string | null
  finished_at: string | null
  llm_model: string | null
}

export interface ArticleBatchesResponse {
  batches: ArticleBatchListItem[]
  total: number
  limit: number
  offset: number
}

export interface CreateArticleBatchDto {
  items: { culture_key: string; variety_key?: string | null; category_key: string }[]
  llm_model?: string | null
  reasoning_effort?: string | null
}

export interface ArticleBatchProgressEvent {
  batch_id: number
  item_id?: number
  index?: number
  total?: number
  topic?: string
  culture?: string
  category?: string
  article_id?: number
  cost?: number
  article_length?: number
  error?: string
  type?: string
}

// =============================================================================
// Article Presentation Batch Types (Пакетная генерация презентаций по статьям)
// =============================================================================

export interface ArticlePresentationCultureDef {
  culture_key: string
  variety_key: string | null
  label: string
  culture_russian: string
  existing_categories: string[]
  article_count: number
}

export interface ArticlePresentationDefinitionsResponse {
  categories: ArticleCategoryDef[]
  cultures: ArticlePresentationCultureDef[]
}

export interface CreateArticlePresentationBatchDto {
  cultures: { culture_key: string; variety_key?: string | null }[]
  include_season_plan?: boolean
  style_id?: number | null
  template_id?: number | null
  llm_model?: string | null
  reasoning_effort?: string | null
  image_model?: string | null
  custom_system_prompt?: string | null
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
// Payments & Subscriptions Types (Платежи и подписки)
// =============================================================================

export type PaymentStatus = 'pending' | 'succeeded' | 'canceled'
export type PaymentType = 'subscription' | 'tokens'

export interface Payment {
  id: number
  user_id: number
  yookassa_payment_id: string
  payment_type: PaymentType
  subscription_plan_id: number | null
  token_package_id: number | null
  amount_rub: number
  status: PaymentStatus
  paid: boolean
  created_at: string
  paid_at: string | null
  canceled_at: string | null

  // Enriched fields (from JOINs)
  subscription_plan_name?: string | null
  token_package_name?: string | null
  duration_days?: number | null
  tokens_amount?: number | null
  username?: string | null
  first_name?: string | null
  telegram_user_id?: number
}

export interface PaymentsResponse {
  payments: Payment[]
  total: number
  total_paid?: number
  stats?: PaymentStats
}

export interface PaymentStats {
  total_count: number
  total_amount: number
  paid_amount: number
  pending_amount: number
  by_type?: {
    subscription?: { count: number; amount: number }
    tokens?: { count: number; amount: number }
  }
  by_status?: {
    succeeded?: { count: number; amount: number }
    pending?: { count: number; amount: number }
    canceled?: { count: number; amount: number }
  }
}

export interface SubscriptionPlan {
  id: number
  name: string
  description: string | null
  price_rub: number
  duration_days: number
  tokens_included: number
  is_active: boolean
  max_carryover: number
  token_discount_percent: number
  created_at: string | null
}

export interface TokenPackage {
  id: number
  name: string
  description: string | null
  price_rub: number
  tokens_amount: number
  is_active: boolean
  created_at: string | null
}

// ============================================
// RAG Documents v2.0 — Паспортизация чанков
// ============================================

// Расширенный статус документа для двухэтапной обработки
export type RagDocumentStatus = 'pending' | 'processing' | 'chunked' | 'completed' | 'failed'

export interface RagDocument {
  id: number
  filename: string
  subcategory: string | null
  status: RagDocumentStatus
  error: string | null
  chunks_count: number
  passported_chunks: number
  file_size: number
  // Двухэтапная обработка: chunking + embedding
  chunking_tokens: number      // Токены для semantic chunking (768d)
  chunking_cost: number        // Стоимость semantic chunking
  embedding_tokens: number     // Токены для финальных embeddings (3072d)
  embedding_cost: number       // Стоимость финальных embeddings
  context_cost: number         // Стоимость генерации контекста
  total_cost: number           // Общая стоимость
  context_tokens: number
  is_embedded: boolean         // Загружен ли в библиотеку
  created_at: string | null
}

export interface EmbedDocumentResponse {
  success: boolean
  document_id?: number
  chunks_count?: number
  embedding_tokens?: number
  embedding_cost?: number
  error?: string
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
  cultures: string[]
  culture_subtypes: Record<string, string> // { "малина": "ремонтантная", "клубника": "летняя" }
  goals: string[]
  growth_phases: string[]
  prefix: string | null
  context: string | null
  assembled_text: string
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
  cultures: string[]
  culture_subtypes: Record<string, string> // { "малина": "ремонтантная" }
  goals: string[]
  growth_phases: string[]
  chunk_text?: string
  context?: string
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

// =============================================================================
// Prompt Preview Types (Превью собранного промпта)
// =============================================================================

export interface PromptPreviewSection {
  id: string
  label: string
  source: 'base' | 'culture' | 'category' | 'prompt_doc' | 'rag' | 'terminology' | 'reference'
  color: string
  content: string | null
  is_from_db?: boolean
  is_enabled?: boolean
  is_placeholder?: boolean
  placeholder_text?: string
  skipped_reason?: string
  prompt_id?: number | null
  prompt_ids?: number[]
}

export interface PromptPreviewMetadata {
  category: string
  culture: string
  culture_group: string | null
  use_minimal_base: boolean
  base_source: 'db' | 'python'
  category_source: 'db' | 'python'
  total_chars: number
}

export interface PromptPreviewResponse {
  sections: PromptPreviewSection[]
  metadata: PromptPreviewMetadata
}

export interface PromptPreviewOption {
  value: string
  label: string
}

export interface PromptPreviewOptionsResponse {
  categories: PromptPreviewOption[]
  cultures: PromptPreviewOption[]
}

// =============================================================================
// Invite Links Types (Инвайт-ссылки для отслеживания кампаний)
// =============================================================================

export interface InviteLink {
  id: number
  name: string
  code: string
  created_at: string
  users_count: number
  total_users_count: number
  new_users_count: number
  existing_users_count: number
  total_revenue_rub: number
  deep_link: string
  bonus_tokens: number
  discount_percent: number
  discount_duration_days: number
  max_users: number
  is_active: boolean
  token_bonus_percent: number
  allow_existing_users: boolean
  existing_user_bonus_tokens: boolean
  existing_user_discount: boolean
  existing_user_token_bonus: boolean
}

export interface InviteLinksSummary {
  total_links: number
  total_users: number
  total_revenue_rub: number
}

export interface InviteLinksResponse {
  links: InviteLink[]
  summary: InviteLinksSummary
}

// =============================================================================
// Guide Types (Готовые решения — PDF-гайды)
// =============================================================================

export interface GuideSectionMeta {
  title: string
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number
  model: string
  user_question: string
  system_prompt: string
  rag_snippets_count: number
}

export interface GuideOrder {
  id: number
  user_id: number
  payment_id: number | null
  culture_key: string
  culture_display: string
  status: string
  total_llm_cost_usd: number
  total_llm_tokens: number
  llm_model: string | null
  sections_meta: Record<string, GuideSectionMeta> | null
  file_size_bytes: number | null
  error_message: string | null
  retry_count: number
  created_at: string
  updated_at: string
  // JOIN fields
  username?: string | null
  first_name?: string | null
  telegram_user_id?: number
}

export interface GuideOrdersResponse {
  orders: GuideOrder[]
  total: number
  limit: number
  offset: number
}

export interface GuideStats {
  total_orders: number
  completed_orders: number
  failed_orders: number
  total_cost_usd: number
  avg_cost_usd: number
  total_tokens: number
  by_culture: Array<{ culture_key: string; count: number; total_cost: number }>
}

// =============================================================================
// Server Metrics (Мониторинг сервера)
// =============================================================================

export interface ServerMetrics {
  timestamp: string
  cpu: {
    percent: number
    cores: number
    load_1m: number
    load_5m: number
    load_15m: number
  }
  memory: {
    total_mb: number
    used_mb: number
    available_mb: number
    buffers_mb: number
    cached_mb: number
    free_mb: number
    used_percent: number
    swap_total_mb: number
    swap_used_mb: number
    swap_percent: number
  }
  disk: {
    total_gb: number
    used_gb: number
    available_gb: number
    used_percent: number
  }
  disk_io: {
    read_mb: number
    write_mb: number
  }
  network: {
    rx_total_mb: number
    tx_total_mb: number
    rx_rate_kbps: number
    tx_rate_kbps: number
  }
  uptime: {
    seconds: number
    formatted: string
  }
  docker: Array<{
    name: string
    cpu: string
    mem_usage: string
    mem_percent: string
    net_io: string
    pids: string
  }>
}

export interface MetricsHistoryPoint {
  time: string
  cpu: number
  memory: number
  disk: number
  net_rx: number
  net_tx: number
  load: number
}

export interface ServerMetricsHistory {
  history: MetricsHistoryPoint[]
  hours: number
}

// =============================================================================
// OpenAI Balance (Мониторинг расходов OpenAI)
// =============================================================================

export interface OpenAIBalance {
  total_cost_usd: number
  budget_usd: number | null
  remaining_usd: number | null
  daily_costs: Array<{ date: string; cost_usd: number }>
  days: number
  error: string | null
  has_admin_key: boolean
}

// =============================================================================
// Moderation Types (Модерация вопросов/ответов + База знаний)
// =============================================================================

export type ModerationStatus = 'pending' | 'approved' | 'rejected'

export interface ModerationItem {
  id: number
  user_id: number
  topic_id: number | null
  question: string
  answer: string
  category_guess: string | null
  status: ModerationStatus
  admin_id: number | null
  kb_id: number | null
  created_at: string
  updated_at: string | null
  username: string | null
  first_name: string | null
  telegram_user_id: number | null
}

export interface ModerationQueueResponse {
  items: ModerationItem[]
  total: number
  pending_count: number
}

export interface ModerationStats {
  pending_count: number
  approved_today: number
  approved_total: number
  rejected_total: number
  oldest_date: string | null
}

export interface KBEntry {
  id: number
  category: string
  subcategory: string | null
  question: string | null
  answer: string
  source_type: string
  is_active: boolean
  created_at: string
}

export interface KBListResponse {
  items: KBEntry[]
  total: number
}

// =============================================================================
// Broadcast Types (Рассылки)
// =============================================================================

export type BroadcastStatus = 'draft' | 'scheduled' | 'sending' | 'completed' | 'failed' | 'cancelled'
export type BroadcastTargetType = 'all' | 'invite_link' | 'funnel_stage' | 'manual'

export interface BroadcastButton {
  row: number
  text: string
  type: 'url' | 'quick_reply' | 'payment' | 'discount' | 'quiz_start'
  url?: string
  option_key?: string
  reply_text?: string
  ask_for_response?: boolean
  // payment button fields (subscription)
  payment_plan_id?: number | null
  payment_custom_price?: number | null
  payment_bonus_tokens?: number | null
  // payment button fields (token package)
  payment_package_id?: number | null
  // discount button fields (all-plans discount)
  discount_percent?: number | null
  discount_bonus_tokens?: number | null
  discount_bonus_tokens_mode?: 'absolute' | 'percent'
  discount_duration_hours?: number | null
}

export interface Broadcast {
  id: number
  title: string
  message_text: string | null
  photo_path: string | null
  poll_question: string | null
  poll_options: string[] | null
  poll_is_anonymous: boolean
  poll_allows_multiple: boolean
  inline_buttons: BroadcastButton[] | null
  target_type: BroadcastTargetType
  target_invite_link_id: number | null
  target_funnel_id: string | null
  target_stage_key: string | null
  target_user_ids: number[] | null
  scheduled_at: string | null
  status: BroadcastStatus
  total_recipients: number
  sent_count: number
  failed_count: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  reminders?: BroadcastReminder[]
}

export interface BroadcastsResponse {
  broadcasts: Broadcast[]
}

export interface BroadcastRecipient {
  id: number
  broadcast_id: number
  user_id: number
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
  status: 'pending' | 'sent' | 'failed'
  error_message: string | null
  sent_at: string | null
}

export interface BroadcastRecipientsResponse {
  recipients: BroadcastRecipient[]
}

export interface BroadcastUser {
  id: number
  telegram_user_id: number
  username: string | null
  first_name: string | null
  last_name: string | null
}

export interface BroadcastUsersResponse {
  users: BroadcastUser[]
}

export interface CreateBroadcastDto {
  title: string
  message_text?: string | null
  photo_path?: string | null
  poll_question?: string | null
  poll_options?: string[] | null
  poll_is_anonymous?: boolean
  poll_allows_multiple?: boolean
  inline_buttons?: BroadcastButton[] | null
  target_type: BroadcastTargetType
  target_invite_link_id?: number | null
  target_funnel_id?: string | null
  target_stage_key?: string | null
  target_user_ids?: number[] | null
  scheduled_at?: string | null
  reminders?: BroadcastReminder[]
}

// Broadcast Stats Types
export interface ButtonClickStat {
  option_key: string
  button_text: string
  click_count: number
  percentage: number
}

export interface PollAnswerStat {
  option_index: number
  option_text: string
  answer_count: number
  percentage: number
}

export interface BroadcastStats {
  button_clicks: ButtonClickStat[]
  poll_answers: PollAnswerStat[]
  total_button_respondents: number
  total_poll_respondents: number
}

export interface StatUser {
  user_id: number
  first_name: string | null
  last_name: string | null
  username: string | null
  clicked_at?: string
  answered_at?: string
  text_response?: string | null
  response_at?: string | null
}

export interface BroadcastStatsUsersResponse {
  users: StatUser[]
}

// Broadcast Reminders (напоминалки)
export type ReminderTriggerType = 'after_send' | 'before_discount_end'
export type ReminderStatus = 'pending' | 'scheduled' | 'sending' | 'sent' | 'cancelled' | 'skipped'

export interface BroadcastReminder {
  id?: number
  sort_order: number
  message_text: string | null
  photo_path: string | null
  inline_buttons: BroadcastButton[] | null
  poll_question: string | null
  poll_options: string[] | null
  poll_is_anonymous: boolean
  poll_allows_multiple: boolean
  offset_hours: number
  trigger_type: ReminderTriggerType
  exclude_bought: boolean
  exclude_clicked_buttons: string[] | null
  // Read-only status
  reminder_status?: ReminderStatus
  reminder_scheduled_at?: string | null
  sent_count?: number
  failed_count?: number
  total_recipients?: number
}

// Broadcast Runs (повторные запуски)
export interface BroadcastRun {
  id: number
  broadcast_id: number
  run_number: number
  target_type: BroadcastTargetType
  target_invite_link_id: number | null
  target_funnel_id: string | null
  target_stage_key: string | null
  target_user_ids: number[] | null
  status: string
  total_recipients: number
  sent_count: number
  failed_count: number
  started_at: string | null
  completed_at: string | null
  created_at: string
}

export interface BroadcastRunsResponse {
  runs: BroadcastRun[]
}

// Funnel Stage Triggers
export interface TriggerPaymentConfig {
  plan_id: number
  custom_price?: number | null
  bonus_tokens?: number | null
}

export interface FunnelStageTrigger {
  id: number
  funnel_id: string
  stage_key: string
  broadcast_id: number
  broadcast_title: string
  broadcast_status: string
  is_active: boolean
  delay_minutes: number
  payment_config: TriggerPaymentConfig | null
  created_at: string
}

export interface FunnelTriggersResponse {
  triggers: FunnelStageTrigger[]
}

// ═══════════════════════════════════════════════════════════════════
// Automation Triggers (универсальные триггеры автоматизации)
// ═══════════════════════════════════════════════════════════════════

export type TriggerEventType = 'stage_transition' | 'payment_success' | 'tag_changed' | 'subscription_expiring'

export type TriggerActionType = 'send_broadcast' | 'move_to_stage' | 'add_tag' | 'remove_tag' | 'set_custom_field' | 'send_payment_offer'

export interface ConditionRule {
  type: 'has_tag' | 'not_has_tag' | 'from_invite_link' | 'at_funnel_stage' | 'not_at_funnel_stage'
  tag_id?: number
  invite_link_id?: number
  funnel_id?: string
  stage_key?: string
}

export interface ConditionGroup {
  operator: 'AND' | 'OR'
  rules: ConditionRule[]
}

export interface ConditionTree {
  operator: 'AND' | 'OR'
  groups: ConditionGroup[]
}

export interface TriggerAction {
  type: TriggerActionType
  broadcast_id?: number
  funnel_id?: string
  stage_key?: string
  tag_id?: number
  field_id?: number
  value?: string
  plan_id?: number
  custom_price?: number
  bonus_tokens?: number
}

export interface AutomationTrigger {
  id: number
  name: string
  description: string | null
  event_type: TriggerEventType
  event_config: Record<string, any>
  conditions: ConditionTree | null
  actions: TriggerAction[]
  delay_minutes: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface TriggerLogEntry {
  id: number
  trigger_id: number
  user_id: number
  telegram_user_id: number
  first_name: string | null
  last_name: string | null
  username: string | null
  event_snapshot: Record<string, any> | null
  status: 'pending' | 'sent' | 'failed' | 'skipped'
  send_at: string
  executed_at: string | null
  actions_result: Record<string, any>[] | null
  error_message: string | null
  created_at: string
}

export interface CreateTriggerDto {
  name: string
  description?: string
  event_type: TriggerEventType
  event_config: Record<string, any>
  conditions?: ConditionTree | null
  actions: TriggerAction[]
  delay_minutes?: number
}

export interface AutomationTriggersResponse {
  triggers: AutomationTrigger[]
}

export interface TriggerLogResponse {
  log: TriggerLogEntry[]
  limit: number
  offset: number
}
