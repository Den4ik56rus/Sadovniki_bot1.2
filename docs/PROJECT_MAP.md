# PROJECT MAP — Source of Truth

**Last Updated:** 2026-02-25
**Project:** Sadovniki-bot v1.5.5
**Status:** Active development — broadcasts v2 + funnel triggers + graceful shutdown; DB migrations 62-66 pending on production; payment reliability + discount/payment broadcast buttons planned

## Quick Navigation

- **Architecture:** See [Architecture Overview](#architecture-overview)
- **Features:** See [Feature Status](#feature-status)
- **Current Work:** See [Active Context](#active-context)
- **Documentation Index:** See [Documentation](#documentation)

---

## Project Overview

**Sadovniki-bot** — Professional Telegram consultation bot for berry crops (strawberry, raspberry, blackberry, currant, blueberry, honeysuckle, gooseberry) using RAG (Retrieval-Augmented Generation) with vector search and OpenAI GPT.

**Core Technologies:**
- Python 3.11+, Aiogram 3.x, asyncpg, OpenAI API
- PostgreSQL 16 + pgvector (vector search)
- React + TypeScript (Admin Panel)
- RAG: 3-level priority search (Q&A → priority docs → general docs)

**Key Capabilities:**
- 12 culture types classification
- 6 consultation categories
- Multi-turn context-aware dialogues
- Culture-specific prompts with detailed agronomic instructions
- Real-time admin monitoring via SSE
- Article generation mode for administrators

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM USERS                           │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              TELEGRAM BOT (Aiogram 3.x)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Handlers                                             │   │
│  │ • consultation/entry.py — main consultation logic    │   │
│  │ • consultation/pitanie_rastenii.py — nutrition mode  │   │
│  │ • admin/moderation.py — KB moderation                │   │
│  │ • admin/terminology.py — terminology management      │   │
│  │ • admin/article_writing.py — article generation      │   │
│  │ • menu/ — user menu handlers                         │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                     SERVICES LAYER                          │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ LLM Services     │  │ RAG System       │                │
│  │ • consultation   │  │ • unified        │                │
│  │ • classification │  │   retriever      │                │
│  │ • article        │  │ • 3-level search │                │
│  │ • embeddings     │  └──────────────────┘                │
│  └──────────────────┘                                       │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ DB Repositories  │  │ Document Pipeline│                │
│  │ • kb_repo        │  │ • PDF extraction │                │
│  │ • topics_repo    │  │ • chunking       │                │
│  │ • messages_repo  │  │ • embedding      │                │
│  └──────────────────┘  └──────────────────┘                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              POSTGRESQL + pgvector                          │
│  • users, topics, messages                                  │
│  • knowledge_base (Q&A pairs)                               │
│  • documents, document_chunks (RAG corpus)                  │
│  • moderation_queue, terminology                            │
│  • consultation_logs (monitoring)                           │
│  • CRM: client_funnel_status, client_funnel_columns        │
│  • Buyers: buyer_status, buyer_funnel_columns              │
│  • Payments: payments, subscription_plans, token_packages  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    ADMIN PANEL (React)                      │
│  • Live Feed (SSE) — real-time consultations                │
│  • Consultation View — detailed view with RAG snippets      │
│  • Cost Tracking — tokens, pricing, latency                 │
│  • CRM — Client Kanban (Deals funnel)                       │
│  • Buyers — Subscription lifecycle management               │
│  • Payments — Transaction history and statistics            │
│  • SSE Manager — server-sent events for real-time updates   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow: Consultation Request

```
User Question
    ↓
1. Log user message to messages table (SSE broadcast)
    ↓
2. Classification (detect_category_and_culture)
    ↓
3. Complexity Classification (detect_answer_complexity — gpt-4.1-mini)
    ├── short_answer (1 token) — default
    ├── short_answer + phase_eligible — offer phase plan
    ├── long_answer (2 tokens) — plan for one seasonal phase
    └── turnkey_solution — purchase offer
    ↓
4. Based on complexity tier:
    ├── short_answer → direct consultation flow
    ├── short_answer + phase_eligible → show phase choice keyboard
    ├── long_answer → show confirm + cost keyboard
    └── turnkey_solution → show purchase info + plan option
    ↓ (user confirms or auto for short_answer)
5. Topic Management (create or continue topic)
    ↓
6. Clarification Check (need more info?)
    ↓ (if sufficient info)
7. Question Composition (compose_full_question with culture context)
    ↓
8. Embedding Generation (get_text_embedding_with_usage)
    ↓
9. RAG Search (retrieve_unified_snippets)
    ├── Level 1: Q&A pairs (kb)
    ├── Level 2: Priority documents (subcategory-specific)
    └── Level 3: General documents (category-wide)
    ↓
10. Prompt Building (culture-specific prompt + RAG context + phase context if applicable)
    ↓
11. LLM Generation (OpenAI GPT-4o)
    ↓
12. Markdown → HTML Formatting (markdown_to_telegram_html)
    ↓
13. Response Delivery (with follow-up buttons or next-phase button)
    ↓
14. Logging (consultation_logs with complexity/phase fields, messages, SSE broadcast)
```

---

## Feature Status

### Core Features

| Feature | Status | Documentation | Notes |
|---------|--------|---------------|-------|
| Multi-turn Consultations | ✅ Production | [CONSULTATION_FLOW.md](features/CONSULTATION_FLOW.md) | State machine with context |
| Complexity Classification | ⏳ Implemented, needs testing | [COMPLEXITY_FLOW.md](features/COMPLEXITY_FLOW.md) | LLM-based tier detection |
| Phase-Based Plans | ⏳ Implemented, needs testing | [COMPLEXITY_FLOW.md](features/COMPLEXITY_FLOW.md) | Seasonal phase plan delivery |
| Culture Classification | ✅ Production | [CLASSIFICATION.md](features/CLASSIFICATION.md) | 12 culture types |
| RAG System | ✅ Production | [RAG_SYSTEM.md](../architecture/RAG_SYSTEM.md) | 3-level priority search |
| Culture-Specific Prompts | ✅ Production | [PROMPTS.md](features/PROMPTS.md) | Detailed for strawberry/raspberry |
| Markdown Formatting | ✅ Production | - | Bot responses support MD → HTML |
| Topic Management | ✅ Production | [TOPIC_MANAGEMENT.md](TOPIC_MANAGEMENT.md) | Session tracking |
| KB Moderation | ✅ Production | [MODERATION.md](features/MODERATION.md) | Queue system |
| Terminology Management | ✅ Production | [TERMINOLOGY.md](features/TERMINOLOGY.md) | Preferred wording |
| Admin Panel (SSE) | ✅ Production | [ADMIN_PANEL.md](features/ADMIN_PANEL.md) | Real-time monitoring |
| User Avatars | ✅ Production | - | Telegram profile photos |
| Invite Links | ✅ Production | - | Campaign tracking with revenue stats |
| Full Message Logging | ✅ Production | - | All bot/user messages + buttons logged |
| CRM ChatHistory | ✅ Production | - | Full conversation timeline per client |
| Broadcasts | ⏳ Implemented v2, DB migrations 62-66 pending | [BROADCASTS.md](features/BROADCASTS.md) | Mass messaging with photos/polls/buttons; resend runs; text responses |
| Broadcast Discount Button | ❌ Planned | docs/plans/2026-02-23-broadcast-discount-button.md | Time-limited personal discount on all subscription plans |
| Broadcast Payment Button | ❌ Planned | docs/plans/2026-02-23-broadcast-payment-button-and-create-modal.md | Personal YooKassa URL per recipient |
| Payment Webhook Reliability | ❌ Planned | docs/plans/2026-02-23-payment-reliability.md | Async queue, reconciliation, alerts |
| Funnel Stage Triggers | ⏳ Implemented, DB migrations pending | - | Auto-send broadcast when client moves to kanban stage |
| Article Writing Mode | ✅ Production | - | Admin feature, needs docs |
| Document Upload | ✅ Production | [DOCUMENT_PIPELINE.md](features/DOCUMENT_PIPELINE.md) | PDF/TXT/MD/DOCX |
| CRM Deals Kanban | ✅ Production | - | Sales funnel management, needs docs |
| Buyers Section | ✅ Production | - | Subscription lifecycle, needs docs |

### Consultation Categories

| Category | Status | Culture-Specific Prompts | Documentation |
|----------|--------|--------------------------|---------------|
| Питание растений | ✅ Production | ✅ group_strawberry, group_raspberry, group_b_berries | nutrition.py (900+ lines) |
| Посадка и уход | ✅ Production | ⏳ Generic prompt | planting_care.py |
| Защита растений | ✅ Production | ⏳ Technical template | diseases_pests.py (250+ lines) |
| Улучшение почвы | ✅ Production | ⏳ Generic prompt | soil_improvement.py |
| Подбор сортов | ✅ Production | ⏳ Generic prompt | variety_selection.py |
| Другие вопросы | ✅ Production | ❌ No specific prompt | Uses base prompt only |

### Culture Support

| Culture Type | Classification | Nutrition Prompts | Protection Prompts |
|-------------|----------------|-------------------|-------------------|
| Клубника летняя | ✅ | ✅ group_strawberry | ⏳ |
| Клубника ремонтантная | ✅ | ✅ group_strawberry | ⏳ |
| Малина летняя | ✅ | ✅ group_raspberry | ⏳ |
| Малина ремонтантная | ✅ | ✅ group_raspberry | ⏳ |
| Ежевика | ✅ | ✅ group_raspberry | ⏳ |
| Смородина | ✅ | ✅ group_b_berries | ⏳ |
| Голубика | ✅ | ✅ group_b_berries | ⏳ |
| Жимолость | ✅ | ✅ group_b_berries | ⏳ |
| Крыжовник | ✅ | ✅ group_b_berries | ⏳ |
| Ирга | ✅ | ✅ group_b_berries | ⏳ |
| Арония | ✅ | ✅ group_b_berries | ⏳ |

**Legend:**
- ✅ Implemented and working
- ⏳ In progress or needs improvement
- ❌ Not implemented

---

## Active Context

### Current Phase: Payment Reliability + Broadcast Buttons v3

**Focus Areas:**
1. Payment webhook reliability (async queue + periodic reconciliation)
2. Broadcast `discount` button type (personal time-limited discount on all plans)
3. Broadcast `payment` button type (personal YooKassa URL per recipient)
4. "Create broadcast" modal inside StageTriggerEditor

**Last Session Changes (2026-02-25 — v1.5.5, documentation only):**
- No code changes — session closed immediately after opening
- Three implementation plan docs staged for commit (created 2026-02-23):
  - `docs/plans/2026-02-23-payment-reliability.md`
  - `docs/plans/2026-02-23-broadcast-payment-button-and-create-modal.md`
  - `docs/plans/2026-02-23-broadcast-discount-button.md`

**Previous Session Changes (2026-02-25 — v1.5.5):**
- Graceful shutdown hardened: `close_bot_session=False` + `handle_signals=False`, finally block waits for handler tasks
- Invite link analytics: new vs existing user breakdown in invite link stats
- Invite link tracking: always tracks even after `member_limit` reached
- CLAUDE.md: deploy commands and graceful shutdown notes added

**Pending Implementation (Plans Ready — see docs/plans/):**
- `payment-reliability.md` — webhook queue, reconciliation, alerts, activity feed fix
- `broadcast-payment-button-and-create-modal.md` — `payment` button type, create-in-trigger modal
- `broadcast-discount-button.md` — `discount` button type, `user_broadcast_discounts` table, discount menu

### Constraints & Invariants

**MUST NOT CHANGE:**
1. Database schema (without migration files in `db/schema_*.sql`)
2. OpenAI API models (gpt-4o for consultations, text-embedding-3-large for vectors)
3. Telegram API limits (4096 chars per message, auto-split with `send_long_message`)
4. RAG 3-level priority structure (Level 1: Q&A, Level 2: Priority Docs, Level 3: General Docs)
5. Async patterns (all services use `async def`, never blocking calls)

**SAFE TO CHANGE:**
1. Prompt texts (but preserve structure for culture-specific prompts)
2. RAG search parameters (limits, thresholds)
3. UI components in Admin Panel (CSS, React components)
4. Keyboard layouts (inline buttons)
5. Logging levels and messages

**TECHNICAL DEBT TO ADDRESS:**
1. Split large prompt files (`nutrition.py` 900+ lines → separate files per culture group)
2. Add automated tests for Markdown formatting
3. Add automated tests for culture-specific prompts
4. Add automated tests for temperature configuration
5. Add automated tests for KB fallback behavior
6. Move culture groups mapping to config/database
7. Implement prompt versioning system
8. Track moderation notices in database (needs_kb_improvement field)

---

## Documentation

### Architecture Documents

- [OVERVIEW.md](architecture/OVERVIEW.md) — System architecture, components, data flow
- [DATABASE.md](architecture/DATABASE.md) — Schema, indices, connection pooling
- [LLM_INTEGRATION.md](architecture/LLM_INTEGRATION.md) — OpenAI API integration, token management
- [RAG_SYSTEM.md](architecture/RAG_SYSTEM.md) — Retrieval-Augmented Generation, 3-level search

### Feature Documents

- [CONSULTATION_FLOW.md](features/CONSULTATION_FLOW.md) — Multi-turn dialogues, state machine
- [COMPLEXITY_FLOW.md](features/COMPLEXITY_FLOW.md) — Complexity classification, phase plans, pricing tiers
- [CLASSIFICATION.md](features/CLASSIFICATION.md) — Culture classification (12 types)
- [PROMPTS.md](features/PROMPTS.md) — Prompt system, culture-specific prompts
- [MODERATION.md](features/MODERATION.md) — Knowledge base moderation
- [TERMINOLOGY.md](features/TERMINOLOGY.md) — Terminology management
- [ADMIN_PANEL.md](features/ADMIN_PANEL.md) — Admin monitoring, SSE, cost tracking
- [BROADCASTS.md](features/BROADCASTS.md) — Mass messaging system (broadcasts)
- [DOCUMENT_PIPELINE.md](features/DOCUMENT_PIPELINE.md) — PDF processing, chunking, embedding
- [TOPIC_MANAGEMENT.md](TOPIC_MANAGEMENT.md) — Session tracking, topic continuation

### Development Documents

- [SETUP.md](development/SETUP.md) — Installation, environment setup
- [TESTING.md](development/TESTING.md) — Test scripts, validation
- [CHANGELOG.md](development/CHANGELOG.md) — Version history

### Missing Documents (TO CREATE)

- [ ] `docs/features/ARTICLE_MODE.md` — Article generation feature
- [ ] `docs/features/MARKDOWN_FORMATTING.md` — Markdown → HTML conversion
- [ ] `docs/architecture/PROMPT_SYSTEM.md` — Detailed prompt architecture
- [ ] `docs/development/CONTRIBUTING.md` — Contribution guidelines

### CRM Development Documents

**Roadmap & Models:**
- [CRM_ROADMAP.md](crm/CRM_ROADMAP.md) — Мастер-документ: все 10 этапов разработки CRM
- [DATA_MODELS.md](crm/DATA_MODELS.md) — Единые справочники: статусы, культуры, типы событий

**Stage Specifications:**
- [STAGE_0_PREPARATION.md](crm/specs/STAGE_0_PREPARATION.md) — Скелет данных и событий
- [STAGE_1_CLIENT_CARD.md](crm/specs/STAGE_1_CLIENT_CARD.md) — Карточка клиента v1
- [STAGE_2_SUPPORT.md](crm/specs/STAGE_2_SUPPORT.md) — Kanban поддержки
- [STAGE_3_FINANCES.md](crm/specs/STAGE_3_FINANCES.md) — Подписки/лимиты/деньги
- [STAGE_4_BUYERS.md](crm/specs/STAGE_4_BUYERS.md) — Покупатели + сегменты
- [STAGE_5_AI_INTERESTS.md](crm/specs/STAGE_5_AI_INTERESTS.md) — AI-выдержки интересов
- [STAGE_6_TRIGGERS.md](crm/specs/STAGE_6_TRIGGERS.md) — Триггеры + задачи
- [STAGE_7_REFERRALS.md](crm/specs/STAGE_7_REFERRALS.md) — Реферальная программа
- [STAGE_8_DASHBOARDS.md](crm/specs/STAGE_8_DASHBOARDS.md) — Управленческие дашборды
- [STAGE_9_POLISH.md](crm/specs/STAGE_9_POLISH.md) — Полировка и защита

---

## File Structure Reference

### Handlers (src/handlers/)

**Consultation Handlers:**
- `consultation/entry.py` (681 lines) — Main consultation logic, culture classification, RAG orchestration
- `consultation/pitanie_rastenii.py` (400+ lines) — Nutrition category handler (legacy, being phased out)
- `consultation/router.py` — Consultation router setup

**Admin Handlers:**
- `admin/moderation.py` (1000+ lines) — KB moderation, Q&A approval/rejection
- `admin/terminology.py` (200+ lines) — Terminology CRUD
- `admin/article_writing.py` (155 lines) — Article generation mode

**Menu Handlers:**
- `menu/start.py` — /start command
- `menu/help.py` — /help command
- `menu/profile.py` — User profile

### Services (src/services/)

**LLM Services (services/llm/):**
- `consultation_llm.py` (500+ lines) — Main consultation LLM service
- `classification_llm.py` (1000+ lines) — Culture/category classification
- `article_llm.py` (177 lines) — Article generation
- `embeddings_llm.py` (100 lines) — Text embedding generation
- `core_llm.py` (200 lines) — Core OpenAI API calls
- `question_builder_llm.py` (200 lines) — Question composition

**RAG Services (services/rag/):**
- `unified_retriever.py` (681 lines) — Unified 3-level RAG search

**Database Repositories (services/db/):**
- `kb_repo.py` — Knowledge base (Q&A) operations
- `topics_repo.py` — Topics (sessions) CRUD
- `messages_repo.py` — Messages logging
- `document_chunks_repo.py` — Document chunks search
- `consultation_logs_repo.py` — Consultation logs for admin panel
- `users_repo.py` — User management
- `moderation_queue_repo.py` — Moderation queue
- `terminology_repo.py` — Terminology CRUD

**Document Pipeline (services/documents/):**
- `pdf_extractor.py` — PDF text extraction
- `chunker.py` — Text chunking for RAG

### Prompts (src/prompts/)

**Base Prompts:**
- `base_prompt.py` — Base system prompt (full and minimal versions)
- `consultation_prompts.py` — Consultation-specific prompts
- `article_prompt.py` — Article generation prompt

**Category Prompts (prompts/category_prompts/):**
- `nutrition.py` (900+ lines) — Nutrition category with culture-specific prompts
- `diseases_pests.py` (250+ lines) — Plant protection technical template
- `planting_care.py` — Planting and care category
- `soil_improvement.py` — Soil improvement category
- `variety_selection.py` — Variety selection category
- `_culture_groups.py` — Culture → prompt group mapping
- `_fertilizers_reference.py` — Fertilizers and pesticides reference

### Utilities (src/utils/)

- `formatting.py` (195 lines) — Markdown → Telegram HTML conversion
- `message_utils.py` — Message splitting, text utils
- `date_utils.py` — Date formatting

### API (src/api/)

**Handlers:**
- `handlers/sse.py` — Server-Sent Events endpoints
- `handlers/documents.py` — Document upload API
- `handlers/consultations.py` — Consultations API

**Infrastructure:**
- `sse_manager.py` — SSE connection management
- `middleware.py` — CORS, auth, logging
- `server.py` — aiohttp server setup

### Admin Panel (admin-webapp/)

**Components:**
- `components/consultation/ConsultationView.tsx` — Consultation detail view
- `components/consultation/LiveFeed.tsx` — Real-time feed
- `components/common/CollapsibleSection.tsx` — Collapsible UI element

**Services:**
- `services/api.ts` — API client
- `services/sse.ts` — SSE client

---

## Key Code Patterns

### Pattern 1: Async Database Access

```python
from src.services.db.database import get_pool

async def my_function():
    pool = get_pool()  # NEVER create new connections
    async with pool.acquire() as conn:
        result = await conn.fetch(
            "SELECT * FROM table WHERE id = $1",  # Parameterized queries
            some_id
        )
```

**Rules:**
- Always use `get_pool()`, never create connections
- Use `$1, $2, ...` for parameters (never f-strings)
- Use `async with pool.acquire()` for transactions

### Pattern 2: LLM Service Calls

```python
from src.services.llm.core_llm import create_chat_completion_with_usage

response = await create_chat_completion_with_usage(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question}
    ],
    model=settings.openai_model,
    temperature=0.3
)

answer = response["content"]
tokens = response["total_tokens"]
cost = response["cost_usd"]
```

**Rules:**
- Always use `create_chat_completion_with_usage` (includes token tracking)
- Temperature: 0.3 for consultations, 0.4 for articles
- Log tokens and cost for monitoring

### Pattern 3: Culture-Specific Prompts

```python
from src.prompts.category_prompts._culture_groups import get_prompt_group_for_culture
from src.prompts.category_prompts.nutrition import get_nutrition_category_prompt

# Get prompt group for culture
group = get_prompt_group_for_culture("питание растений", "малина летняя")
# group = "group_raspberry"

# Get category-specific prompt
category_prompt, use_minimal_base = get_nutrition_category_prompt(
    culture="малина летняя",
    default_location="средняя полоса",
    default_growing_type="открытый грунт"
)

# Combine with base prompt
if use_minimal_base:
    base = get_base_system_prompt_minimal()
else:
    base = get_base_system_prompt()

full_prompt = f"{base}\n\n{category_prompt}"
```

**Rules:**
- Always check if culture has specific prompt via `get_prompt_group_for_culture`
- Respect `use_minimal_base` flag (detailed prompts already have format instructions)
- Culture groups are defined in `_culture_groups.py`

### Pattern 4: Markdown Formatting

```python
from src.utils.formatting import markdown_to_telegram_html

# LLM returns Markdown
answer_text = "**Important:** Use `Azofоска` for feeding."

# Convert before sending to Telegram
html_text = markdown_to_telegram_html(answer_text)
# Result: "<b>Important:</b> Use <code>Azofоска</code> for feeding."

await message.answer(html_text, parse_mode="HTML")
```

**Rules:**
- ALWAYS convert LLM responses with `markdown_to_telegram_html` before sending
- Parse mode MUST be "HTML" (not "Markdown")
- Tables are converted to vertical cards automatically

### Pattern 5: SSE Broadcasting

```python
from src.api.sse_manager import sse_manager

await sse_manager.broadcast_event(
    event_type="consultation_update",
    data={
        "topic_id": topic_id,
        "message": {...}
    },
    topic_id=topic_id  # Optional filter
)
```

**Rules:**
- Use `broadcast_event` for all real-time updates
- Event types: `new_consultation`, `consultation_update`, `message_added`
- Always include relevant IDs for filtering

---

## Development Checklist

### Before Making Changes

- [ ] Read relevant docs from `docs/` folder
- [ ] Check if similar code exists elsewhere (avoid duplication)
- [ ] Verify database schema if touching repositories
- [ ] Check if changes affect Admin Panel (frontend rebuild needed)

### After Making Changes

- [ ] Update relevant docs in `docs/`
- [ ] Update this PROJECT_MAP.md if architecture changed
- [ ] Run existing tests (if applicable)
- [ ] Test manually in Telegram (if bot logic changed)
- [ ] Test Admin Panel (if API/SSE changed)
- [ ] Update `session-summary.md` with changes

### Before Committing

- [ ] Review all changed files
- [ ] Ensure no secrets in code (.env only)
- [ ] Check git status for untracked files
- [ ] Write descriptive commit message
- [ ] Update version in README.md if needed (1.2.1 → 1.2.2)

---

## Contact & Support

**Documentation Questions:** Check `docs/` folder first
**Code Questions:** Read this PROJECT_MAP.md and relevant .md files
**Issues:** Create detailed bug reports with logs

**Key Files to Read:**
1. This file (`docs/PROJECT_MAP.md`) — overall map
2. `CLAUDE.md` — AI collaboration rules
3. `docs/architecture/OVERVIEW.md` — system design
4. `session-summary.md` — latest session changes
