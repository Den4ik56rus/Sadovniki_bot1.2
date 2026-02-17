# Session Summary — 2026-02-18

## Project Context

**Sadovniki-bot** — Telegram-бот для профессиональных консультаций по ягодным культурам с RAG-системой на базе PostgreSQL + pgvector и OpenAI GPT.

**Current Stage:** Production system (v1.2.3) with new complexity-based consultation flow, avatar system, invite links, and full message logging.

**Tech Stack:**
- Backend: Python 3.11+, Aiogram 3.x, asyncpg, OpenAI API
- Frontend: React + TypeScript (Admin Panel), Vite
- Database: PostgreSQL 16 + pgvector
- AI: OpenAI GPT models with flexible configuration, database-driven prompts

---

## Session Goal

**Primary Goal:** Implement complexity-based consultation flow (question difficulty classification that determines cost and answer type), add user avatar support, build invite link campaign tracking system, and enhance CRM with full chat history and message logging.

---

## Accomplishments

### 1. Complexity Classification System (complexity_llm.py)

**What was built:**
- New LLM-based classifier `src/services/llm/complexity_llm.py` that analyzes each incoming user question
- Classifies into 3 tiers: `short_answer` (1 token), `long_answer` (2 tokens), `turnkey_solution` (purchase)
- Detects `phase_eligible` — whether a short question can be answered more fully by season phase
- Returns `confirm_message` and `phase_button_label` for personalized UI prompts
- Supports seasonal phases: весна-цветение, цветение-плодоношение, плодоношение-зима
- Detects multi-topic questions and prompts user to select one topic

**Key logic:**
- System prompt instructs classifier to default to `short_answer` unless user EXPLICITLY requests a plan/schema
- `phase_eligible=true` for questions about питание/защита/обрезка/полив where season context adds value
- Тип B = 1 phase plan, Тип C = full season (multiple phases)
- Turnkey = multiple topics + complex care request requiring product purchase

**Feature flag:** `FEATURE_COMPLEXITY_ENABLED=true` in env (on by default)

### 2. Pricing System Overhaul (pricing.py)

**Changes:**
- Added `PHASE_COST = 2` constant for long_answer tier
- Added `COMPLEXITY_TIERS` dict with full tier definitions including turnkey price (1190 RUB)
- Added `SEASONAL_PHASES` dict with phase chain (next phase pointers)
- Added `PHASE_DISPLAY_NAMES` — user-friendly phase labels for display
- New functions: `get_complexity_cost()`, `get_next_phase()`, `get_phase_display_name()`, `should_suggest_product()`
- `pluralize_questions()` moved earlier in file and changed from "вопросов" to "токенов"
- Old `CATEGORY_COSTS`-based `get_consultation_cost()` marked DEPRECATED (still present for compatibility)

### 3. Consultation Entry Handler (entry.py) — Major Extension

**What was added (~1292 lines total, +1100 lines this session):**

**New helper functions:**
- `serialize_keyboard(markup)` — converts Aiogram keyboard markup to dict for message meta (for display in admin CRM)
- `_log_bot_msg(text, ...)` — logs bot service messages (buttons, prompts) to messages table with SSE broadcast
- `_log_user_callback(text, callback, ...)` — logs inline button presses to messages table

**Complexity flow integration:**
- After question logging, calls `detect_answer_complexity()` (shadow mode)
- If `long_answer` or `turnkey_solution`: saves to `CONSULTATION_CONTEXT["_pending_complexity"]`, shows confirm keyboard
- If `short_answer` with `phase_eligible=True`: shows `get_phase_eligible_keyboard()` — choice between short/phase/turnkey
- If multi-topic `long_answer`: saves `_pending_topic_select`, shows topic selection keyboard
- Callback handlers for `complexity_confirm:short/long/turnkey_info/cancel` and `phase_continue:*` and `topic_select:*`

**Phase mode tracking:**
- After delivering a long_answer for one phase, stores `_phase_continuation` context
- Handles `waiting_phase_continue` state — user can get next phase
- Tracks `phases_delivered` list, `current_phase`, `next_phase`
- Logs `phase_mode`, `phase_key`, `phase_number` to `consultation_logs` (schema_49)

**Complexity data stored in logs:**
- `complexity_tier`, `complexity_metadata` (JSONB), `complexity_classification_cost_usd`, `complexity_classification_tokens`

### 4. New Consultation Keyboards (common.py)

**New keyboard functions:**
- `get_complexity_confirm_keyboard(tier, cost, show_turnkey, phase_button_label)` — for long_answer/turnkey confirmation with personalized button label
- `get_phase_eligible_keyboard(phase_button_label, phase_cost)` — 3-button choice: краткий / по фазам / готовое решение
- `get_next_phase_keyboard(next_phase_display)` — "Continue to next phase" button after delivering a phase plan
- `get_phase_select_keyboard(phases)` — choose which phase to start from (for full-season Тип C)
- `get_topic_select_keyboard(topics)` — choose one topic from a multi-topic question

### 5. Database Schemas 48-51

**schema_48_complexity_tracking.sql:**
- Adds `complexity_tier VARCHAR(50)`, `complexity_metadata JSONB`, `complexity_classification_cost_usd`, `complexity_classification_tokens` to `consultation_logs`
- Adds `admin_settings` entries for complexity model configuration: `model_complexity`, `temp_complexity`, `reasoning_complexity`

**schema_49_phase_tracking.sql:**
- Adds `phase_mode VARCHAR(20)`, `phase_key VARCHAR(50)`, `phase_number INTEGER` to `consultation_logs`
- Tracks which phase of seasonal plan was delivered

**schema_50_user_avatars.sql:**
- Adds `avatar_path TEXT` to `users` table

**schema_51_invite_links.sql:**
- New table `invite_links` (id, name, code, created_at) — named campaign tracking links
- New table `invite_link_users` (invite_link_id, user_id, created_at) — tracks which users came via which link
- Unique constraint on user_id (one user can only be attributed to one invite link)

### 6. User Avatar System

**Backend:**
- `src/services/avatars.py` — downloads user profile photo from Telegram via `bot.get_user_profile_photos()`
- Saves to `data/avatars/{telegram_user_id}.jpg` (smallest 160x160 photo)
- `fetch_avatars.py` — one-time script to retroactively download avatars for all existing users
- `users_repo.update_user_avatar()` — updates `avatar_path` in users table

**Integration in menu.py:**
- On `/start` command: downloads avatar automatically for new and returning users
- On `user_mode` callback: avatar downloaded/updated on login

**API serving:**
- Static file route added: `GET /api/admin/avatars/{filename}` serves from `data/avatars/` directory

**CRM integration:**
- `crm.py _serialize_dict()` now converts `avatar_path` → `avatar_url` automatically
- ClientCard, FunnelClientCard, BuyerCard all updated to display avatars with fallback initials

### 7. Invite Links — Campaign Tracking

**Backend:**
- `src/services/db/invite_link_repo.py` — full CRUD + statistics with revenue aggregation
- `src/api/handlers/invite_links.py` — REST API handler (GET/POST/PATCH/DELETE)
- Routes registered in `src/api/routes.py`: `/api/admin/invite-links`

**Deep link format:** `https://t.me/{BOT_USERNAME}?start=inv_{CODE}`
- `inv_` prefix in `start_param` triggers invite link tracking in `menu.py`
- Code is 8-character alphanumeric (URL-safe, uppercase)

**Frontend:**
- `admin-webapp/src/components/inviteLinks/InviteLinksPage.tsx` — full management UI
- `admin-webapp/src/store/inviteLinksStore.ts` — Zustand store
- Features: create/rename/delete links, copy deep link, monthly/all-time revenue stats
- Sidebar entry added (link icon)

**Statistics:** users_count per link, total_revenue_rub (from paid payments), date filtering

### 8. Full Message Logging (messages_repo.py)

**Changes:**
- `log_message()` now returns `msg_id` AND broadcasts SSE `new_message` event with topic_id
- New `attach_topic_to_message(message_id, topic_id)` — retroactively links a message to a topic
- New `attach_pending_messages_to_topic(user_id, topic_id, since_msg_id)` — bulk attach messages to topic

**Impact:** All bot messages (user questions, bot responses, button presses, service prompts) are now logged to `messages` table. Admin panel CRM shows full conversation history in real-time via SSE.

### 9. CRM Activity Feed — chat_message Events

**Changes in `ActivityItem.tsx`:**
- New `chat_message` event type rendered as chat bubbles (user/bot alignment)
- Shows callback button badge for button-press messages
- Renders inline keyboard buttons from `meta.keyboard.buttons`
- `stripHtml()` helper removes Telegram HTML markup for display

**Changes in `TopicView.tsx`:**
- Complexity classification block displayed inline (tier, cost, phase info)
- `complexity_classification_cost_usd` added to cost totals
- Inline keyboard buttons rendered inside message timeline
- Callback badge shown for user button presses

**Changes in `crm.py`:**
- New endpoint `GET /api/admin/crm/clients/{id}/chat` — returns full chat history
- Avatar path → URL conversion in `_serialize_dict()`

### 10. ChatHistory Component (new)

**`admin-webapp/src/components/crm/RightPanel/ChatHistory.tsx`:**
- Full conversation timeline view for a client
- Groups messages by topic with clickable dividers (navigate to TopicView)
- Date separators between days
- Chat bubbles aligned by direction (user right, bot left, system centered)
- Shows inline keyboard buttons rendered as UI elements
- Callback badge for button-press events
- Scrolls to bottom on load

**`admin-webapp/src/components/crm/RightPanel/ChatHistory.module.css`** (new) — full styling

### 11. menu.py Enhancements

**New on /start:**
- Invite link tracking (`inv_` prefix detection in start_param)
- Avatar download on first launch
- Full message logging for welcome message and button presses

**Referral system notifications:**
- When referrer gets bonus tokens, sends Telegram notification to referrer with token count
- Uses `pluralize_questions()` for proper Russian inflection

---

## Key Decisions

### 1. Complexity Classification Architecture

**Decision:** Run complexity classifier in shadow mode (FEATURE_COMPLEXITY_ENABLED=true), but complexity result affects cost and flow immediately (not truly shadow).

**Rationale:**
- Complexity classification is a separate LLM call (lightweight, cheap model `gpt-4.1-mini`)
- Does not change consultation quality — only determines price and flow
- Feature flag allows easy rollback if classifier has issues
- Shadow mode terminology retained in code comments for historical clarity

**Cost:** `model_complexity` = `gpt-4.1-mini` (configurable via admin_settings)

### 2. Default to short_answer

**Decision:** Classifier prompt instructs model to default to `short_answer` when in doubt.

**Rationale:**
- Better user experience (not overcharging)
- Phase-eligible questions still get enhanced offer
- Prevents false long_answer classification

### 3. serialize_keyboard for Message Logging

**Decision:** Serialize Aiogram keyboard markup to JSON dict in `meta` field of messages.

**Rationale:**
- Allows CRM to display the exact keyboard presented to user at each step
- Enables full conversation flow visualization without maintaining separate state
- Retroactive — already logged messages with keyboards are displayable

### 4. One Invite Link Per User

**Decision:** `invite_link_users.user_id` has UNIQUE constraint — each user can only be attributed to one invite link.

**Rationale:**
- Prevents double-counting in campaign analytics
- First touch attribution model (most common in marketing)
- Simplest to implement and reason about

### 5. Avatar Serving via Static Route

**Decision:** Serve avatars directly from aiohttp static file route, not via base64 or external CDN.

**Rationale:**
- Simplest implementation — no additional services
- Files are small (160x160 JPG)
- Can be replaced with S3/CDN later if needed
- URL format: `/api/admin/avatars/{telegram_user_id}.jpg`

---

## Problems & Limitations

### Active Issues

1. **Complexity Flow Not Fully Connected:**
   - The callback handlers for `complexity_confirm:*` and `phase_continue:*` are written into entry.py but the full state machine for delivering phase plans (asking LLM for phase-specific response) is not yet fully wired.
   - `_pending_complexity` context is saved but the callback handler that responds to it needs verification.
   - **Priority:** HIGH — core new feature

2. **Phase LLM Prompt Not Implemented:**
   - When user confirms `long_answer`, the bot should call `ask_consultation_llm()` with phase-specific prompt context (питание на весна-цветение).
   - The phase prompt composition (`phase_mode`, `phase_key`, `phase_topic` kwargs) is passed to LLM service but `consultation_llm.py` may not use them yet.
   - **Priority:** HIGH

3. **Schemas 48-51 Not Applied to Production:**
   - New DB schemas are created but NOT yet applied.
   - Without schema_48, complexity fields in `consultation_logs` don't exist → saving complexity data will fail silently or error.
   - **Priority:** CRITICAL — apply before next bot usage

4. **Avatar Download Race Condition:**
   - `download_user_avatar()` called on every `/start`. If Telegram API is slow, it delays the welcome message.
   - Should be moved to background task.
   - **Priority:** MEDIUM

5. **invite_link_repo Date Filter Bug:**
   - In `get_invite_links_with_stats()`, the date filter uses `$1/$2` for `ilu.created_at` and then `$3/$4` for `p.paid_at` but params are added in a way that may mismatch if only one date filter block is populated.
   - Needs review before production use.
   - **Priority:** MEDIUM

6. **ChatHistory API Endpoint:**
   - `GET /api/admin/crm/clients/{id}/chat` is wired in routes but `get_user_chat_history()` function in `messages_repo.py` needs to be verified — it is called but may not exist yet (only `attach_topic_to_message` and `attach_pending_messages_to_topic` were shown in diff).
   - **Priority:** HIGH — ChatHistory component will show error if not implemented

### Technical Debt

1. **entry.py size:** Now ~1292 lines — extraction of complexity callbacks into separate file recommended
2. **Duplicate user_id lookups:** Multiple places in entry.py do `get_or_create_user()` — should use context cache
3. **pluralize_questions renamed semantics:** Function now says "токенов" but the name says "questions" — minor naming inconsistency

---

## Rejected Ideas

### Why Not Real Shadow Mode for Complexity?

- **Proposal:** Run complexity classification but ignore result — only log for analytics
- **Rejected:** Adds latency with no user benefit; better to make it functional immediately
- **Chosen:** Active mode — complexity tier determines actual cost and flow

### Why Not Use Existing CATEGORY_COSTS for Complexity Pricing?

- **Proposal:** Map complexity tiers to existing category-based costs
- **Rejected:** Categories and complexity are orthogonal concepts; complexity is question-specific, not category-specific
- **Chosen:** Separate `COMPLEXITY_TIERS` dict with explicit costs

### Why Not Store Avatars in Database?

- **Proposal:** Store avatar as base64 BYTEA in users table
- **Rejected:** Large binary data in DB impacts backup size, query performance
- **Chosen:** Filesystem storage with path in DB, served via static route

---

## Current Code State

### New Files Created

**Backend:**
- `src/services/llm/complexity_llm.py` — question complexity classifier (LLM-based)
- `src/services/avatars.py` — Telegram avatar download service
- `src/services/db/invite_link_repo.py` — invite link CRUD + stats
- `src/api/handlers/invite_links.py` — invite links REST API
- `fetch_avatars.py` — one-time script to download avatars for existing users

**Database Migrations:**
- `db/schema_48_complexity_tracking.sql` — complexity fields in consultation_logs
- `db/schema_49_phase_tracking.sql` — phase tracking fields in consultation_logs
- `db/schema_50_user_avatars.sql` — avatar_path in users
- `db/schema_51_invite_links.sql` — invite_links and invite_link_users tables

**Frontend:**
- `admin-webapp/src/components/crm/RightPanel/ChatHistory.tsx` — full chat history view
- `admin-webapp/src/components/crm/RightPanel/ChatHistory.module.css`
- `admin-webapp/src/components/inviteLinks/InviteLinksPage.tsx`
- `admin-webapp/src/components/inviteLinks/InviteLinksPage.module.css`
- `admin-webapp/src/components/inviteLinks/index.ts`
- `admin-webapp/src/store/inviteLinksStore.ts`

### Modified Files

**Backend:**
- `src/handlers/consultation/entry.py` (+1100 lines) — complexity flow, phase tracking, full message logging
- `src/handlers/consultation/pitanie_rastenii.py` (+150 lines) — complexity integration
- `src/handlers/consultation/culture_callback.py` (+24 lines) — complexity callbacks
- `src/handlers/menu.py` (+261 lines) — avatar download, invite link tracking, message logging
- `src/keyboards/consultation/common.py` (+206 lines) — 5 new keyboard functions
- `src/pricing.py` (+121 lines) — complexity tiers, phase data, new functions
- `src/prompts/consultation_prompts.py` (+63 lines) — phase prompt support
- `src/services/db/messages_repo.py` (+165 lines) — SSE broadcast, attach functions
- `src/services/db/users_repo.py` (+55 lines) — update_user_avatar, complexity-related queries
- `src/services/db/consultation_logs_repo.py` (+56 lines) — complexity/phase fields
- `src/services/llm/consultation_llm.py` (+67 lines) — phase kwargs support
- `src/services/payments/payment_service.py` (+32 lines) — minor updates
- `src/services/payments/subscription_service.py` (+14 lines) — minor updates
- `src/api/handlers/crm.py` (+26 lines) — chat history endpoint, avatar URL conversion
- `src/api/handlers/settings.py` (+2 lines) — minor updates
- `src/api/handlers/buyers.py` (+5 lines) — avatar support
- `src/api/routes.py` (+15 lines) — invite links routes, avatar static route, chat history route
- `src/config.py` (+6 lines) — telegram_bot_username setting
- `db/schema_30_payments.sql` (+4 lines) — minor fix
- `db/schema_45_pricing_update.sql` (+12 lines) — pricing data update

**Frontend:**
- `admin-webapp/src/App.tsx` (+4 lines) — invite links route
- `admin-webapp/src/components/buyers/BuyerCard.tsx` (+19 lines) — avatar display
- `admin-webapp/src/components/consultation/ConsultationView.tsx` (+54 lines) — complexity info
- `admin-webapp/src/components/consultation/ConsultationView.module.css` (+42 lines)
- `admin-webapp/src/components/crm/ClientCard.tsx` (+19 lines) — avatar display
- `admin-webapp/src/components/crm/ClientCard.module.css` (+8 lines)
- `admin-webapp/src/components/crm/RightPanel/ActivityFilters.tsx` (+6 lines) — chat_message filter
- `admin-webapp/src/components/crm/RightPanel/ActivityItem.tsx` (+56 lines) — chat_message type rendering
- `admin-webapp/src/components/crm/RightPanel/ActivityItem.module.css` (+113 lines) — chat bubble styles
- `admin-webapp/src/components/crm/RightPanel/RightPanel.module.css` (+3 lines)
- `admin-webapp/src/components/crm/RightPanel/TopicView.tsx` (+75 lines) — complexity block, keyboard display
- `admin-webapp/src/components/crm/RightPanel/TopicView.module.css` (+109 lines) — complexity/keyboard styles
- `admin-webapp/src/components/crm/RightPanel/index.tsx` (+6 lines) — ChatHistory tab
- `admin-webapp/src/components/funnel/FunnelClientCard.tsx` (+19 lines) — avatar display
- `admin-webapp/src/components/funnel/FunnelClientCard.module.css` (+8 lines)
- `admin-webapp/src/components/layout/Sidebar.tsx` (+12 lines) — invite links nav item
- `admin-webapp/src/components/settings/SettingsPage.tsx` (+8 lines) — minor update
- `admin-webapp/src/hooks/useAutoRefresh.ts` (+30 lines)
- `admin-webapp/src/services/api.ts` (+41 lines) — invite links API, chat history API
- `admin-webapp/src/types/index.ts` (+68 lines) — InviteLink, ChatHistoryTopic, Message types update

### What's Working

1. **Complexity LLM classifier** — runs on every question, returns tier + metadata
2. **Pricing system** — complexity-based costs with tier definitions
3. **User avatars** — download on /start, serve via static route, displayed in CRM cards
4. **Invite links** — create, manage, track users + revenue, copy deep links
5. **Full message logging** — all bot messages (including service prompts, button presses) logged
6. **CRM chat bubbles** — `chat_message` events render as conversation bubbles in activity feed
7. **ChatHistory component** — full conversation view with topic dividers and date separators
8. **Phase tracking** — schema for logging which season phase was delivered

### What Needs Work

1. **Complexity callback handlers** — verify `complexity_confirm:long` correctly triggers consultation with phase-specific prompt
2. **`get_user_chat_history()` in messages_repo.py** — verify function exists and returns correct shape `{messages, topics}`
3. **Phase-specific LLM prompt composition** — `consultation_llm.py` phase kwargs need to be used in actual prompt building
4. **Apply schemas 48-51** — CRITICAL before testing
5. **Test full complexity flow end-to-end** — question → classify → confirm → deliver phase plan → next phase offer

---

## Next Steps

### Critical (Before Testing)

1. **Apply DB migrations 48-51:**
   ```bash
   psql -h localhost -U bot_user -d garden_bot -f db/schema_48_complexity_tracking.sql
   psql -h localhost -U bot_user -d garden_bot -f db/schema_49_phase_tracking.sql
   psql -h localhost -U bot_user -d garden_bot -f db/schema_50_user_avatars.sql
   psql -h localhost -U bot_user -d garden_bot -f db/schema_51_invite_links.sql
   ```

2. **Verify `get_user_chat_history()` function in messages_repo.py:**
   - Check if function exists
   - If not, implement it: return `{messages: [...], topics: [...]}`
   - Messages should be ordered by `created_at ASC`

3. **Test complexity flow end-to-end:**
   - Send short question → verify `short_answer` classification → normal consultation
   - Send phase-eligible question (e.g., "питание клубники") → verify phase offer keyboard shown
   - Send plan question (e.g., "распиши план подкормок") → verify `long_answer` → confirm keyboard → phase plan delivered

4. **Verify avatar serving:**
   - Run `python fetch_avatars.py` to download avatars for existing users
   - Check `GET /api/admin/avatars/{telegram_user_id}.jpg` returns image
   - Check CRM client cards show avatar circles

### High Priority

5. **Test invite links:**
   - Create link in admin panel → copy deep link → open in Telegram
   - Verify user registered via link appears in invite_link_users table
   - Check revenue stats update when user makes payment

6. **Verify ChatHistory tab in CRM:**
   - Open CRM → select client → "Полный чат" tab
   - Verify messages grouped by topic with date separators
   - Verify topic dividers are clickable (navigate to TopicView)

7. **Test message logging completeness:**
   - After consultation: check messages table has both user message and bot response
   - Verify service messages (button prompts) are logged with keyboard meta
   - Check SSE broadcasts new_message events for messages with topic_id

### Medium Priority

8. **Implement phase-specific LLM prompt:**
   - `consultation_llm.py` should use `phase_mode`, `phase_key`, `phase_topic` kwargs
   - Add phase context to prompt: "Ответ строго для фазы: {phase_key}"
   - Test phase plan format matches expected length (~1200 chars)

9. **Set `TELEGRAM_BOT_USERNAME` in config:**
   - `invite_links.py` uses `settings.telegram_bot_username` for deep link generation
   - Add to `.env`: `TELEGRAM_BOT_USERNAME=your_bot_username`
   - Without this, deep links show only `inv_{code}` (no full URL)

10. **Background avatar download:**
    - Move avatar download in `menu.py` to `asyncio.create_task()` to not block welcome message

### Database Migration Checklist

Before applying schemas, verify:
- [ ] schema_48: complexity columns don't already exist in consultation_logs
- [ ] schema_49: phase columns don't already exist in consultation_logs
- [ ] schema_50: avatar_path column doesn't already exist in users
- [ ] schema_51: invite_links and invite_link_users tables don't already exist

After applying:
- [ ] Run `\d consultation_logs` — verify complexity_tier, phase_mode columns present
- [ ] Run `\d users` — verify avatar_path column present
- [ ] Run `\d invite_links` — verify table structure

---

## Session Statistics

- **Files Modified:** 51 files (per git status)
- **Files Created (untracked):** ~16 new files
- **Lines Added:** ~3,162 insertions
- **Lines Deleted:** ~264 deletions
- **DB Migrations:** 4 new schemas (48-51)
- **New Features:** 5 major (complexity flow, avatars, invite links, full message logging, ChatHistory)
- **Session Date:** 2026-02-18

---

**Session completed:** 2026-02-18
**Version:** 1.2.3 (no version bump this session — code not deployed)
**Status:** Implementation complete, CRITICAL migrations not applied, testing required
**Breaking Changes:** None (all new fields are additive)
**Migration Required:** YES — schemas 48-51 must be applied before bot restart
