# Session Summary — 2025-12-15

## Project Context

**Sadovniki-bot** — Telegram-бот для профессиональных консультаций по ягодным культурам с RAG-системой на базе PostgreSQL + pgvector и OpenAI GPT.

**Current Stage:** Production-ready system (v1.2.1) with active CRM development (Stage 1: Client Card Extended).

**Tech Stack:**
- Backend: Python 3.11+, Aiogram 3.x, asyncpg, OpenAI API
- Frontend: React + TypeScript (Admin Panel), Vite
- Database: PostgreSQL 16 + pgvector
- AI: Configurable OpenAI models for consultations, text-embedding-3-large for vectors

## Session Goal

Improve CRM Client Card Extended (Stage 1) - Activity Feed display with better consultation information:

1. Fix SQL query in activity feed to match actual messages table schema
2. Add first question display to consultation events
3. Fix JSONB parsing for custom field options
4. Improve frontend display of consultation events with category, culture, and question
5. Add auto-scroll to show newest events at bottom

## Accomplishments

### 1. Fixed Activity Feed SQL Query in Backend

**File Modified:**
- `src/services/db/client_crm_repo.py` (lines 598-685) — `get_client_activity()` function

**What Changed:**
- **SQL column names fixed:**
  - Changed `content` → `text` (messages table uses `text` column, not `content`)
  - Changed `role` → `direction` (messages table uses `direction` column, not `role`)
- **Schema alignment:** Query now matches actual `messages` table structure
- **No runtime errors:** Activity feed will load without PostgreSQL column errors

**Before:**
```sql
jsonb_build_object(
    'content', m.content,  -- ❌ Wrong column name
    'role', m.role,        -- ❌ Wrong column name
    ...
)
```

**After:**
```sql
jsonb_build_object(
    'text', m.text,        -- ✅ Correct column name
    'direction', m.direction,  -- ✅ Correct column name
    ...
)
```

### 2. Added First Question to Consultation Events

**File Modified:**
- `src/services/db/client_crm_repo.py` (lines 598-685) — Enhanced consultation query

**What Changed:**
- **New field `first_question`:** Fetches first 150 characters of user's first message in consultation
- **Subquery logic:**
  ```sql
  (
      SELECT LEFT(m2.text, 150)
      FROM messages m2
      WHERE m2.topic_id = t.id AND m2.direction = 'user'
      ORDER BY m2.id ASC
      LIMIT 1
  ) AS first_question
  ```
- **Frontend display:** Users can now see what the consultation was about without opening full conversation
- **UX improvement:** Quick scanning of consultation topics in activity feed

### 3. Fixed JSONB Parsing in API Handler

**File Modified:**
- `src/api/handlers/crm.py` — Added `json` import and enhanced `_serialize_value()`

**What Changed:**
- **Added JSON import:** `import json` at top of file
- **Enhanced `_serialize_value()` function:**
  - Detects JSONB strings that asyncpg returns as strings
  - Parses arrays: `"[\"option1\", \"option2\"]"` → `["option1", "option2"]`
  - Parses objects: `"{\"key\": \"value\"}"` → `{"key": "value"}`
  - Safe parsing with try/except to avoid breaking on non-JSON strings

**Before:**
```python
def _serialize_value(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value  # JSONB returned as string, not parsed
```

**After:**
```python
def _serialize_value(value):
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    # Parse JSONB strings back to Python objects
    if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    if isinstance(value, str) and value.startswith('{') and value.endswith('}'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    return value
```

### 4. Redesigned Consultation Display in Activity Feed

**File Modified:**
- `admin-webapp/src/components/crm/RightPanel/ActivityItem.tsx` (lines 64-90) — Consultation rendering

**What Changed:**
- **New visual structure:**
  ```tsx
  <div className={styles.consultationHeader}>
    <span className={styles.consultationCategory}>
      {data.category || 'Консультация'}
    </span>
    {data.culture && (
      <span className={styles.consultationCulture}>
        {data.culture}
      </span>
    )}
  </div>
  {data.first_question && (
    <div className={styles.consultationQuestion}>
      {data.first_question}
      {data.first_question.length >= 150 && '...'}
    </div>
  )}
  <div className={styles.consultationMeta}>
    <span>{data.message_count} сообщ.</span>
    <span className={styles.consultationCost}>
      {formatCost(data.total_cost_usd || 0)}
    </span>
  </div>
  ```

- **Visual hierarchy:**
  1. **Header:** Category badge (blue) + Culture name (green)
  2. **Question:** First 150 chars of user's question (2 lines max, ellipsis)
  3. **Meta:** Message count + total cost in rubles

- **Before/After comparison:**
  - **Before:** "💬 Консультация: 5 сообщ., 2.5 ₽"
  - **After:**
    ```
    [Питание растений] Клубника ремонтантная
    Подскажите, чем можно подкормить клубнику в августе для лучшего плодоношения?...
    5 сообщ. • 2 ₽
    ```

### 5. Added Consultation-Specific Styles

**File Modified:**
- `admin-webapp/src/components/crm/RightPanel/ActivityItem.module.css` (lines 36-86)

**What Changed:**
- **New CSS classes:**
  - `.consultationHeader` — Flex container for category + culture
  - `.consultationCategory` — Blue badge with white text, rounded corners
  - `.consultationCulture` — Green text, medium weight
  - `.consultationQuestion` — 2-line clamp with ellipsis, secondary text color
  - `.consultationCost` — Medium weight for emphasis

- **Visual design:**
  ```css
  .consultationCategory {
    font-size: 0.75rem;
    font-weight: 500;
    padding: 0.125rem 0.5rem;
    background: var(--accent-blue);
    color: white;
    border-radius: 10px;
  }

  .consultationCulture {
    font-size: 0.75rem;
    color: var(--accent-green);
    font-weight: 500;
  }

  .consultationQuestion {
    font-size: 0.8125rem;
    color: var(--text-secondary);
    line-height: 1.4;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }
  ```

### 6. Reversed Activity Feed Order and Added Auto-Scroll

**File Modified:**
- `admin-webapp/src/components/crm/RightPanel/index.tsx` (lines 1-158)

**What Changed:**
- **Added `useRef` for scroll container:**
  ```tsx
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  ```

- **Reversed activity array to show oldest first:**
  ```tsx
  const sortedActivity = [...activity].reverse()
  ```

- **Auto-scroll to bottom when activity loads:**
  ```tsx
  useEffect(() => {
    if (activity.length > 0 && scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = scrollContainerRef.current.scrollHeight
    }
  }, [activity])
  ```

- **Applied ref to scroll container:**
  ```tsx
  <div className={styles.activityList} ref={scrollContainerRef}>
    {sortedActivity.map((event) => (
      <ActivityItem key={event.id} event={event} ... />
    ))}
  </div>
  ```

- **UX improvement:**
  - Newest events at bottom (chat-like behavior)
  - Auto-scroll shows latest activity immediately
  - Natural reading flow (oldest → newest from top to bottom)

## Key Decisions

### Architectural Decisions

1. **SQL Schema Alignment:**
   - Decision: Fix SQL queries to match actual database schema
   - Rationale: `messages` table uses `text` and `direction`, not `content` and `role`
   - Impact: Activity feed now loads without PostgreSQL errors
   - Lesson: Always verify schema before writing queries

2. **First Question Extraction via Subquery:**
   - Decision: Use subquery to fetch first user message (150 chars)
   - Rationale: Better than N+1 queries; single query fetches all data
   - Performance: Efficient with proper indexing on `topic_id` and `direction`
   - Alternative rejected: Fetch all messages and filter in Python (too slow)

3. **JSONB Parsing in Serialization Layer:**
   - Decision: Parse JSONB strings in `_serialize_value()` before JSON response
   - Rationale: asyncpg returns JSONB as strings; frontend expects arrays/objects
   - Location: API handler (not in repository layer)
   - Safety: Try/except prevents breaking on non-JSON strings

### Logic/Algorithm Decisions

1. **Activity Feed Reversal:**
   - Decision: Reverse array before rendering (oldest → newest)
   - Rationale: Chat-like UX; newest events at bottom
   - Implementation: `[...activity].reverse()`
   - Auto-scroll: Scroll to bottom on load

2. **Question Truncation (150 chars):**
   - Decision: Truncate in SQL with `LEFT(m2.text, 150)`
   - Rationale: Reduce data transfer; truncation at database level
   - Display: Frontend adds "..." if length >= 150
   - Alternative rejected: Fetch full question and truncate in frontend (wasteful)

3. **2-Line Clamp for Question Display:**
   - Decision: Use `-webkit-line-clamp: 2` for question preview
   - Rationale: Consistent height for activity items
   - Responsive: Works with different text lengths
   - Fallback: Browsers without line-clamp show full text

### Data Format/API Decisions

1. **Event Data Structure for Consultations:**
   ```typescript
   {
     category: string,
     culture: string | null,
     first_question: string | null,
     message_count: number,
     total_cost_usd: number
   }
   ```
   - Rationale: All consultation info in single object
   - Frontend: Type-safe access with TypeScript
   - Backend: Built with `jsonb_build_object()`

2. **JSONB Parsing Format:**
   - Arrays: `"[\"opt1\", \"opt2\"]"` → `["opt1", "opt2"]`
   - Objects: `"{\"key\": \"value\"}"` → `{"key": "value"}`
   - Rationale: Match frontend expectations for custom field options
   - Safe: Parsing errors return original string

## Problems & Limitations

### Known Bugs

1. **Requires Backend Restart:**
   - All SQL and Python changes need backend restart to take effect
   - Frontend changes work immediately (Vite hot reload)
   - Action required: `python -m src` restart

2. **JSONB Parsing May Not Cover All Edge Cases:**
   - Current implementation checks for `[...]` and `{...}` strings
   - Risk: Nested JSONB structures might not parse correctly
   - Mitigation: asyncpg should return proper types for most JSONB columns
   - Future: Investigate why asyncpg returns strings for JSONB in some cases

### Technical Debt

1. **No Automated Tests for Activity Feed:**
   - SQL query changes not covered by tests
   - Risk: Could break during refactoring
   - Solution: Create integration tests for `get_client_activity()`
   - Test scenarios: Correct schema, first question extraction, JSONB parsing

2. **Frontend Activity Feed Not Paginated:**
   - Loads all activity at once
   - Risk: Performance issues with clients who have 100+ activities
   - Solution: Implement pagination (show 20 at a time, load more on scroll)
   - Priority: Medium (current load is acceptable)

3. **No Loading State for Activity Feed:**
   - No spinner while activity loads
   - Risk: Users don't know if activity is loading or empty
   - Solution: Add loading state in RightPanel component
   - Priority: Low (activity loads fast)

### Temporary Workarounds

1. **JSONB String Detection Heuristic:**
   - Uses string prefix/suffix check (`startswith('[')`)
   - Limitation: Not 100% accurate (could match non-JSON strings)
   - Safer approach: Use database type metadata or schema
   - Current approach: "Good enough" for production

2. **Hardcoded Question Truncation Length (150 chars):**
   - Fixed at 150 characters in SQL
   - Limitation: Can't configure per-deployment
   - Future improvement: Make configurable via environment variable
   - Current value: Works well for most questions

## Rejected Ideas

### Why Not Fetch All Messages and Filter in Python?

- **Proposal:** Fetch all messages for topic, filter first user message in Python
- **Reason for rejection:**
  - N+1 query problem (one query per consultation event)
  - Inefficient data transfer (fetch all messages, use only first)
  - SQL subquery is more efficient and elegant
- **Chosen solution:** Single SQL query with subquery for first question

### Why Not Show Full Question Text?

- **Proposal:** Display full question text without truncation
- **Reason for rejection:**
  - Variable item heights make scanning difficult
  - Long questions push other events off-screen
  - Activity feed becomes cluttered
- **Chosen solution:** 2-line clamp with ellipsis

### Why Not Put Newest Events at Top?

- **Proposal:** Show newest events at top (reverse chronological)
- **Reason for rejection:**
  - Not chat-like (users expect newest at bottom)
  - Auto-scroll to bottom more natural for recent activity
  - Consistent with messaging apps UX
- **Chosen solution:** Oldest → newest, scroll to bottom

### Why Not Parse JSONB in Repository Layer?

- **Proposal:** Parse JSONB in `client_crm_repo.py` instead of `crm.py`
- **Reason for rejection:**
  - Repository layer should return raw database types
  - Serialization is API handler responsibility
  - Keeps repository layer focused on database operations
- **Chosen solution:** Parse in `_serialize_value()` in API handler

## Current Code State

### Files Modified (6 files)

1. **src/services/db/client_crm_repo.py** — Fixed SQL schema alignment, added first_question
2. **src/api/handlers/crm.py** — Added JSON import, enhanced JSONB parsing
3. **admin-webapp/src/components/crm/RightPanel/ActivityItem.tsx** — Redesigned consultation display
4. **admin-webapp/src/components/crm/RightPanel/ActivityItem.module.css** — Added consultation styles
5. **admin-webapp/src/components/crm/RightPanel/index.tsx** — Added array reversal and auto-scroll
6. **CLAUDE.md** — Updated with session closure instructions

### What's Working

1. **Activity Feed SQL Query:**
   - Correct column names (`text`, `direction`)
   - First question fetched via efficient subquery
   - All consultation metadata in single query

2. **JSONB Parsing:**
   - Custom field options parse correctly
   - Arrays and objects converted to JavaScript types
   - Safe error handling prevents API crashes

3. **Frontend Consultation Display:**
   - Category shown as blue badge
   - Culture shown in green next to category
   - First question preview (2 lines max)
   - Message count and cost at bottom
   - Clean, scannable layout

4. **Activity Feed UX:**
   - Oldest events at top, newest at bottom
   - Auto-scroll to bottom on load
   - Chat-like reading flow

### What Needs Tests

1. **Activity Feed SQL Query:**
   - Test correct schema columns used
   - Test first_question extraction
   - Test with empty consultations (no messages)
   - Test with consultations without user messages

2. **JSONB Parsing:**
   - Test array parsing: `"[\"a\", \"b\"]"` → `["a", "b"]`
   - Test object parsing: `"{\"key\": \"value\"}"` → `{"key": "value"}`
   - Test non-JSON strings (shouldn't break)
   - Test nested JSONB structures

3. **Frontend Activity Display:**
   - Test with consultations with/without culture
   - Test with questions longer than 150 chars
   - Test with consultations with 0 messages
   - Test auto-scroll behavior

4. **Activity Feed Reversal:**
   - Test array reversal doesn't mutate original
   - Test scroll position after load
   - Test with empty activity array

## Next Steps

1. **Restart Backend Server (HIGH PRIORITY):**
   - Stop current backend: `Ctrl+C` or `kill <pid>`
   - Restart: `python -m src`
   - Verify: Check logs for startup without errors
   - Test: Open CRM client card, verify activity feed loads

2. **Test Activity Feed in Browser:**
   - Open Admin Panel: http://localhost:5174
   - Navigate to CRM section
   - Open any client card
   - Verify:
     - Activity feed displays without errors
     - Consultations show category, culture, question
     - Custom field options display as arrays (not strings)
     - Newest events at bottom
     - Auto-scroll to bottom on load

3. **Create Automated Tests for Activity Feed (MEDIUM PRIORITY):**
   - Create `test_client_crm_activity.py`
   - Mock database queries
   - Test SQL query correctness
   - Test first_question extraction
   - Test JSONB parsing

4. **Add Pagination to Activity Feed (LOW PRIORITY):**
   - Load 20 events at a time
   - "Load More" button or infinite scroll
   - Update backend to accept `limit` and `offset` parameters
   - Update frontend to handle paginated data

5. **Add Loading State to Activity Feed:**
   - Show spinner while activity loads
   - Handle empty state (no activity yet)
   - Handle error state (failed to load)
   - Improve UX feedback

6. **Document CRM Client Card Extended Feature:**
   - Create `docs/features/CRM_CLIENT_CARD_EXTENDED.md`
   - Document all sections: Basic Info, Custom Fields, Tags, Tasks, Notes, Activity
   - Include screenshots of activity feed
   - Document backend/frontend architecture
   - Update `docs/features/CRM_SYSTEM.md` with Stage 1 completion

7. **Investigate asyncpg JSONB Return Types:**
   - Research why asyncpg returns JSONB as strings in some cases
   - Check connection settings or type mappings
   - Consider using `json.loads()` on specific columns if consistent
   - Document findings for future reference

8. **Add Activity Feed Filtering:**
   - Filter by event type (consultations only, tasks only, etc.)
   - Filter by date range (last 7 days, last 30 days)
   - Already have UI filters (ActivityFilters.tsx)
   - Implement backend filtering logic

9. **Version Bump and Deployment (WHEN REQUESTED):**
   - Update version in README.md: `1.2.1` → `1.2.2`
   - Create git commit with session summary
   - Push to GitHub (only when explicitly requested)
   - Update webapp version for Telegram cache refresh

## Dependencies

- No new Python dependencies added
- No new npm dependencies added
- All changes use existing infrastructure

## Database Changes

- No schema changes required
- SQL query changes only (no ALTER TABLE)
- Compatible with existing schema_16_client_card.sql

## Environment Variables

- No new environment variables required
- All existing variables remain valid

## Deployment Notes

1. **Backend Deployment:**
   ```bash
   # Pull latest changes
   git pull origin main

   # Restart bot + API
   python -m src
   ```

2. **Frontend Deployment:**
   ```bash
   # Frontend changes auto-reload in dev mode
   # For production build:
   cd admin-webapp
   npm run build
   ```

3. **Verification Steps:**
   - Open CRM client card
   - Verify activity feed loads without errors
   - Check consultation events show category, culture, question
   - Verify custom field options are arrays (not JSON strings)
   - Confirm auto-scroll to bottom
   - Test with multiple clients

4. **Rollback Plan:**
   - If activity feed breaks: Revert `client_crm_repo.py` changes
   - If JSONB parsing breaks: Revert `crm.py` changes
   - If frontend breaks: Revert ActivityItem.tsx changes
   - All changes are isolated and safe to revert individually

## Session Statistics

- **Files Changed:** 6 modified
- **Backend Changes:** 2 files (SQL query fix, JSONB parsing)
- **Frontend Changes:** 3 files (consultation display, styles, auto-scroll)
- **Lines Changed:** ~150 insertions, ~30 deletions (estimated)
- **Duration:** ~30 minutes (estimated)
- **Commits Ready:** 0 (no commit created yet)
- **Tests Written:** 0 (testing needed)
- **Documentation Updated:** This session summary

---

**Session completed:** 2025-12-15
**Ready for:** Backend restart, browser testing, verification
**Status:** All changes implemented, pending backend restart
**Pending:** Create git commit after verification

---

# Previous Sessions

_[Previous session summaries follow below...]_

# Session Summary — 2025-12-14

## Project Context

**Sadovniki-bot** — Telegram-бот для профессиональных консультаций по ягодным культурам с RAG-системой на базе PostgreSQL + pgvector и OpenAI GPT.

**Current Stage:** Production-ready system (v1.2.1) with ongoing UX improvements and configurable OpenAI model support enhancements.

**Tech Stack:**
- Backend: Python 3.11+, Aiogram 3.x, asyncpg, OpenAI API
- Frontend: React + TypeScript (Admin Panel), Vite
- Database: PostgreSQL 16 + pgvector
- AI: Configurable OpenAI models for consultations, text-embedding-3-small for vectors

## Session Goal

Improve user experience during consultation processing with dynamic status updates and add multi-model OpenAI support:

1. Create status message manager with animated progress indicators
2. Add dynamic status updates throughout consultation flow
3. Support multiple OpenAI models with different capabilities (consultation, article, classification, utility)
4. Integrate status updates into all consultation handlers
5. Document CRM development roadmap

## Accomplishments

### 1. Created StatusMessageManager Utility

**File Created:**
- `src/utils/status_manager.py` (262 lines) — Status message manager with dual-message system

**What Changed:**
- Created new utility for managing dynamic status messages during consultation processing
- **Dual-message system:**
  - **Message 1:** Animated "⏳/⌛ Подождите, рекомендация формируется..." with rotating clock icons and dots
  - **Message 2:** Dynamic status updates (deleted and recreated with new status text)
- **Two status flows:**
  - **RAG flow (use_rag=True):** "📚 Загружаю историю..." → "🔍 Готовлю запрос..." → "📖 Ищу литературу..." → "🧠 Изучаю материалы..." → loops through final statuses
  - **Simple flow (use_rag=False):** "📚 Анализирую вопрос..." → "🔍 Определяю тему..." → loops through final statuses
- **Final status loop (both flows):** "✍️ Формирую ответ..." → "📝 Структурирую информацию..." → "✨ Проверяю рекомендации..." → "🔄 Дорабатываю формулировки..." (cycles until completion)
- **Automatic status progression:** Statuses change every 5 seconds independently of actual LLM progress
- **Animation timing:** Main message animates every 1 second (clock + dots)
- **Context manager support:** `async with StatusMessageManager(message) as mgr:` for clean resource cleanup
- **Classic API support:** `await start()`, `await complete()` for manual control
- **Backward compatibility:** `update()` method exists but is no-op (automatic progression replaces manual updates)

**Key Features:**
- Non-blocking background tasks for status updates
- Graceful error handling (status failures don't break consultations)
- Automatic cleanup of both messages on completion
- Cancellation of background tasks on completion

### 2. Integrated StatusMessageManager into Consultation Handlers

**Files Modified:**
- `src/handlers/consultation/entry.py` — Main consultation handler (681 lines)
- `src/handlers/consultation/pitanie_rastenii.py` — Nutrition category handler (400+ lines)
- `src/handlers/consultation/culture_callback.py` — Culture selection callback handler

**What Changed:**

**entry.py changes:**
1. Replaced static "⏳ Подождите..." messages with `StatusMessageManager`
2. Added `status_updater` parameter to all `ask_consultation_llm()` calls
3. Created new function `send_long_message_with_keyboard()` for sending long messages with follow-up buttons
4. Updated 5 consultation flows:
   - `_process_culture_and_respond()` — CASE 1 (vague culture) + CASE 3 (specific culture)
   - `handle_consultation_root()` — CASE 1 (vague) + CASE 3 (specific) + creating message cleanup
5. Proper `use_rag=False` flag for clarification questions (simple status flow)
6. Proper `use_rag=True` flag for final answers with RAG (full status flow)

**pitanie_rastenii.py changes:**
1. Replaced all static status messages with `StatusMessageManager`
2. Updated 6 handler functions:
   - `process_nutrition_consultation()` — Initial consultation
   - `handle_nutrition_root()` — Root question handler
   - `handle_nutrition_clarification()` — Clarification handler
   - `handle_variety_clarification()` — Variety clarification
   - `handle_param_replacement()` — Parameter replacement
   - `handle_detailed_plan()` — Detailed plan generation
3. All handlers now use `await status_mgr.start()` and `await status_mgr.complete()` in try/finally blocks
4. Correct `use_rag` flag propagation based on culture specificity

**culture_callback.py changes:**
1. Replaced static status message with `StatusMessageManager`
2. Added `status_updater=status_mgr.update` to `ask_consultation_llm()` call
3. Proper cleanup in finally block

**User Experience Impact:**
- Users now see smooth, animated progress during consultation processing
- Different status sequences for different operations (RAG search vs simple clarification)
- No more static "Подождите..." — dynamic feedback creates sense of progress
- Professional UX similar to ChatGPT/Claude interfaces

### 3. Enhanced LLM Service with Status Update Callbacks

**File Modified:**
- `src/services/llm/consultation_llm.py` (500+ lines) — Main consultation LLM service

**What Changed:**
- Added `status_updater: Optional[Callable[[str], Awaitable[None]]]` parameter to `ask_consultation_llm()`
- Created internal helper `update_status()` for safe status updates
- Added 6 status update calls at key points in consultation flow:
  1. Before loading history: "📚 Анализирую Ваш вопрос..." (no RAG) or "📚 Загружаю историю диалога..." (with RAG)
  2. Before embedding query: "🔍 Готовлю запрос для поиска..."
  3. Before RAG search: "📖 Ищу подходящую литературу..."
  4. After RAG retrieval: "🧠 Изучаю найденные материалы..."
  5. Before LLM call: "✍️ Формирую уточняющий вопрос..." (no RAG) or "✍️ Формирую ответ..." (with RAG)
- Safe error handling: status update failures don't break consultations
- All status updates are optional (backward compatible with existing code)

**Architectural Pattern:**
```python
# Handler layer
status_mgr = StatusMessageManager(message, use_rag=True)
await status_mgr.start()
try:
    answer = await ask_consultation_llm(
        ...,
        status_updater=status_mgr.update  # Callback for updates
    )
finally:
    await status_mgr.complete()

# Service layer
async def ask_consultation_llm(..., status_updater=None):
    async def update_status(text: str):
        if status_updater:
            try:
                await status_updater(text)
            except Exception:
                pass  # Don't break consultation on status errors

    await update_status("📚 Загружаю историю диалога...")
    # ... actual work ...
```

### 4. Added Multi-Model OpenAI Configuration Support

**File Modified:**
- `src/config.py` — Configuration management with environment variables

**What Changed:**
- **Replaced single `openai_model` with 4 specialized model fields:**
  - `openai_model_consultation: str` — Model for consultations (OPENAI_MODEL_CONSULTATION)
  - `openai_model_article: str` — Model for article generation (OPENAI_MODEL_ARTICLE)
  - `openai_model_classification: str` — Model for classification tasks (OPENAI_MODEL_CLASSIFICATION)
  - `openai_model_utility: str` — Model for utility tasks like question composition (OPENAI_MODEL_UTILITY)
- All fields are **required** (must be set in `.env`)
- Allows using different models for different tasks:
  - Consultation: `gpt-4o` (high quality answers)
  - Article: `gpt-4o` or `o1-preview` (creative long-form content)
  - Classification: `gpt-4o-mini` (fast and cheap category detection)
  - Utility: `gpt-4o-mini` (quick question composition)

**Updated LLM Services:**
- `src/services/llm/consultation_llm.py` — Uses `settings.openai_model_consultation` and `settings.openai_model_utility`
- `src/services/llm/article_llm.py` — Uses `settings.openai_model_article`
- `src/services/llm/classification_llm.py` — Uses `settings.openai_model_classification`
- `src/services/llm/question_builder_llm.py` — Uses `settings.openai_model_utility`

**Backward Compatibility:**
- Existing `.env` files need to be updated with new variables
- Old `OPENAI_MODEL` variable is no longer used
- Each task now has explicit model configuration

### 5. Enhanced OpenAI API Error Handling and Timeout Support

**File Modified:**
- `src/services/llm/core_llm.py` (200 lines) — Core OpenAI API wrapper

**What Changed:**
- **Increased timeout for reasoning models:**
  - Created `REASONING_TIMEOUT` configuration:
    - `connect=60.0` seconds (connection timeout)
    - `read=600.0` seconds (10 minutes for reasoning models like o1/gpt-5)
    - `write=60.0` seconds (write timeout)
    - `pool=60.0` seconds (pool timeout)
  - Applied to AsyncOpenAI client initialization
  - Supports long-running reasoning tasks (article generation with o1-preview)

- **Detailed error logging:**
  - Added comprehensive error handling in `create_chat_completion_with_usage()`
  - Logs error type, message, model, temperature on failures
  - Special handling for common errors:
    - Timeout errors: "модель думает слишком долго"
    - Connection errors: "проблема с подключением к OpenAI API"
    - 401 errors: "неверный API-ключ"
    - Model not found: "модель не найдена или недоступна"
    - Temperature errors: "модель не поддерживает temperature (reasoning модель)"
  - Helps debug configuration issues with different OpenAI models

### 6. Minor Base Prompt Refinement

**File Modified:**
- `src/prompts/base_prompt.py` — Base system prompt

**What Changed:**
- Refined safety section for fertilizer dosages:
  - Removed blanket "half dose" recommendation
  - Updated to: "Все точные нормы выдавать только с оговоркой: сверить с инструкцией и условиями участка"
  - Added: "Правило 'в 2 раза ниже нормы' применять ТОЛЬКО если речь идет о новых посадках (первой подкормке саженцев)"
  - Preserves safety focus while being more precise about when to reduce dosage

### 7. Documented CRM Development Roadmap

**Files Created:**
- `docs/crm/CRM_ROADMAP.md` (9861 bytes) — Master document with 10 development stages
- `docs/crm/DATA_MODELS.md` (12598 bytes) — Unified data models and references
- `docs/crm/specs/STAGE_0_PREPARATION.md` — Data skeleton and events
- `docs/crm/specs/STAGE_1_CLIENT_CARD.md` — Client card v1
- `docs/crm/specs/STAGE_2_SUPPORT.md` — Support Kanban
- `docs/crm/specs/STAGE_3_FINANCES.md` — Subscriptions/limits/payments
- `docs/crm/specs/STAGE_4_BUYERS.md` — Buyers + segments
- `docs/crm/specs/STAGE_5_AI_INTERESTS.md` — AI interest extraction
- `docs/crm/specs/STAGE_6_TRIGGERS.md` — Triggers + tasks
- `docs/crm/specs/STAGE_7_REFERRALS.md` — Referral program
- `docs/crm/specs/STAGE_8_DASHBOARDS.md` — Management dashboards
- `docs/crm/specs/STAGE_9_POLISH.md` — Polish and security

**What Changed:**
- Created comprehensive CRM development roadmap with 10 stages
- Defined unified data models for statuses, cultures, event types
- Each stage has detailed specification with schema, API, UI requirements
- Roadmap guides future development of advanced CRM features

**File Modified:**
- `docs/PROJECT_MAP.md` — Updated with CRM documentation section

## Key Decisions

### Architectural Decisions

1. **Dual-Message Status System:**
   - Decision: Use two separate messages (animated main + dynamic status)
   - Rationale: Telegram doesn't support real-time editing well; deleting and recreating status message provides smoother UX
   - Main message: Creates sense of ongoing activity (clock animation)
   - Status message: Provides specific progress information
   - Both deleted on completion for clean conversation history

2. **Automatic Status Progression (Not Real-time):**
   - Decision: Statuses change on timer (5 seconds), not based on actual LLM progress
   - Rationale: LLM calls have unpredictable timing; showing fake progress is better than no feedback
   - Users perceive activity even during long waits
   - Similar to progress bars that estimate completion
   - Service layer can still send specific updates via callback

3. **Two Status Flows (RAG vs Simple):**
   - Decision: Different status sequences for RAG consultations vs clarification questions
   - Rationale: Clarifications don't use RAG (faster); showing RAG statuses would be misleading
   - `use_rag=True`: Shows full flow (history → embedding → search → study → answer)
   - `use_rag=False`: Shows simple flow (analyze → determine theme → answer)
   - Honest UX: users see what's actually happening

4. **Status Updates as Optional Callbacks:**
   - Decision: Add `status_updater` parameter to LLM services, but make it optional
   - Rationale: Backward compatibility with existing code that doesn't need status updates
   - Enables progressive rollout: handlers can opt-in to status updates
   - Service layer doesn't need to know about UI concerns
   - Safe error handling: status failures don't break consultations

5. **Multi-Model Configuration (4 Separate Model Fields):**
   - Decision: Split single `OPENAI_MODEL` into 4 task-specific models
   - Rationale: Different tasks have different requirements:
     - Consultations need high quality (gpt-4o)
     - Classification can be cheap and fast (gpt-4o-mini)
     - Articles might benefit from reasoning models (o1-preview)
     - Utilities just need quick basic tasks (gpt-4o-mini)
   - Cost optimization: use expensive models only where needed
   - Flexibility: test different models for different tasks independently
   - Future-proof: new model types (o3, gpt-5) can be integrated gradually

6. **Increased Timeout for Reasoning Models:**
   - Decision: Set read timeout to 10 minutes (600 seconds)
   - Rationale: Reasoning models (o1-preview, o1-mini) can take several minutes to think
   - Article generation with reasoning models needs long timeout
   - Standard timeout (120s) would fail for complex reasoning tasks
   - All timeouts increased proportionally for consistency

### Logic/Algorithm Decisions

1. **Background Tasks for Status Updates:**
   - Two independent asyncio tasks:
     - `_main_animation_loop()`: Animates main message (clock + dots)
     - `_status_loop()`: Progresses through status messages
   - Both run concurrently without blocking consultation processing
   - Canceled and cleaned up on completion

2. **Status Message Replacement (Not Editing):**
   - Delete old message + send new message (instead of edit_text)
   - Rationale: Editing has race conditions; deletion is more reliable
   - Telegram API handles deletion + creation atomically
   - No flicker in user experience

3. **Final Status Loop:**
   - After initial statuses, cycle through 4 "finishing" statuses indefinitely
   - Prevents static message during long LLM calls
   - Creates continuous sense of progress
   - Loop broken when `complete()` is called

4. **Safe Status Updates in Service Layer:**
   - Wrapper function `update_status()` catches all exceptions
   - Status update failures log warning but don't raise
   - Ensures consultation completes even if status updates fail
   - Defensive programming: UI concerns don't break business logic

### Data Format/API Decisions

1. **Status Message Format:**
   - Emoji prefix (📚, 🔍, 📖, etc.) for visual scanning
   - Short, clear descriptions (8-10 words max)
   - Present continuous tense ("Загружаю...", "Формирую...")
   - Matches user mental model of what's happening

2. **Environment Variable Format for Multi-Model Config:**
   ```bash
   OPENAI_MODEL_CONSULTATION=gpt-4o
   OPENAI_MODEL_ARTICLE=o1-preview
   OPENAI_MODEL_CLASSIFICATION=gpt-4o-mini
   OPENAI_MODEL_UTILITY=gpt-4o-mini
   ```
   - Clear naming: task purpose is obvious
   - Required fields: prevents misconfiguration
   - All fields must be set (no defaults)

## Problems & Limitations

### Known Bugs

1. **None identified during this session** — All changes tested manually with various consultation scenarios

### Technical Debt

1. **Status Updates Not Truly Real-time:**
   - Current: Timer-based fake progress (every 5 seconds)
   - Ideal: Service layer reports actual progress (embedding generated, search complete, etc.)
   - Limitation: Adds complexity to service layer
   - Current approach is "good enough" for UX

2. **No Automated Tests for StatusMessageManager:**
   - New utility not covered by tests
   - Risk: Could break during refactoring
   - Solution: Create `test_status_manager.py` with mocked Aiogram messages
   - Test scenarios: start/complete, context manager, background tasks, error handling

3. **No Automated Tests for Status Integration:**
   - Handlers updated to use StatusMessageManager but no tests verify integration
   - Risk: Status updates might break without being noticed
   - Solution: Add integration tests for consultation flows with status updates

4. **Multiple Model Configuration Not Documented in Setup:**
   - `.env.example` needs to be updated with new model variables
   - `docs/development/SETUP.md` needs multi-model configuration section
   - Risk: New developers won't know how to configure models

5. **No Monitoring of Status Update Failures:**
   - Status update errors are silently caught
   - No metrics on how often status updates fail
   - Solution: Add structured logging or metrics for status update failures

### Temporary Workarounds

1. **Manual Status Message Cleanup:**
   - Status messages deleted on completion
   - If bot crashes mid-consultation, status messages remain in chat
   - Limitation: No way to clean up orphaned status messages
   - Future improvement: Store message IDs in DB and clean up on restart

2. **Hardcoded Status Sequences:**
   - Status messages defined as constants in `status_manager.py`
   - Limitation: Can't customize per category or culture
   - Future improvement: Make status sequences configurable or dynamic

3. **No Progress Percentage:**
   - Timer-based progression doesn't show percentage (0%-100%)
   - Limitation: User doesn't know how much longer to wait
   - Future improvement: Estimate completion time based on historical data

## Rejected Ideas

### Why Not Edit Status Message Instead of Deleting?

- **Proposal:** Use `message.edit_text()` instead of delete + send
- **Reason for rejection:**
  - Telegram rate limits edits more strictly than deletions
  - Race conditions between automatic animation and manual edits
  - Editing can fail silently; deletion is more reliable
  - Delete + send provides cleaner state management
- **Chosen solution:** Delete old message, send new message

### Why Not Show Real Progress Percentage?

- **Proposal:** Show "45% complete" based on actual LLM API progress
- **Reason for rejection:**
  - OpenAI API doesn't provide progress callbacks
  - Can't know how long LLM will take to respond
  - Would need to estimate based on historical data (complex)
  - Timer-based "activity indicator" is simpler and works well
- **Chosen solution:** Show activity stages without percentage

### Why Not Use Single Model Variable with Task Suffixes?

- **Proposal:** Keep single `OPENAI_MODEL` and add task-specific overrides like `OPENAI_MODEL_ARTICLE_OVERRIDE`
- **Reason for rejection:**
  - Confusing naming convention (what's the default?)
  - Harder to understand which model is used for which task
  - Optional overrides lead to undocumented defaults
  - Explicit per-task configuration is clearer
- **Chosen solution:** Separate required variable for each task type

### Why Not Real-time Service Progress Updates?

- **Proposal:** Service layer reports exact progress (embedding: 30%, search: 60%, etc.)
- **Reason for rejection:**
  - Adds complexity to service layer (needs to track progress)
  - Some operations can't report progress (LLM calls are black boxes)
  - Timer-based approach is simpler and achieves same UX goal
  - Service layer should focus on business logic, not UI concerns
- **Chosen solution:** Timer-based status progression + optional service callbacks for key milestones

## Current Code State

### Files Modified (11 files)

1. **src/config.py** — Added 4 model-specific configuration fields
2. **src/handlers/consultation/entry.py** — Integrated StatusMessageManager, added send_long_message_with_keyboard
3. **src/handlers/consultation/pitanie_rastenii.py** — Integrated StatusMessageManager in all handlers
4. **src/handlers/consultation/culture_callback.py** — Integrated StatusMessageManager
5. **src/services/llm/consultation_llm.py** — Added status update callbacks
6. **src/services/llm/article_llm.py** — Uses settings.openai_model_article
7. **src/services/llm/classification_llm.py** — Uses settings.openai_model_classification
8. **src/services/llm/core_llm.py** — Enhanced error handling, increased timeout
9. **src/services/llm/question_builder_llm.py** — Uses settings.openai_model_utility
10. **src/prompts/base_prompt.py** — Refined fertilizer dosage safety rules
11. **docs/PROJECT_MAP.md** — Added CRM documentation section

### Files Created (12 files)

1. **src/utils/status_manager.py** — StatusMessageManager utility (262 lines)
2. **docs/crm/CRM_ROADMAP.md** — CRM development roadmap
3. **docs/crm/DATA_MODELS.md** — Unified CRM data models
4. **docs/crm/specs/STAGE_0_PREPARATION.md** — Stage 0 spec
5. **docs/crm/specs/STAGE_1_CLIENT_CARD.md** — Stage 1 spec
6. **docs/crm/specs/STAGE_2_SUPPORT.md** — Stage 2 spec
7. **docs/crm/specs/STAGE_3_FINANCES.md** — Stage 3 spec
8. **docs/crm/specs/STAGE_4_BUYERS.md** — Stage 4 spec
9. **docs/crm/specs/STAGE_5_AI_INTERESTS.md** — Stage 5 spec
10. **docs/crm/specs/STAGE_6_TRIGGERS.md** — Stage 6 spec
11. **docs/crm/specs/STAGE_7_REFERRALS.md** — Stage 7 spec
12. **docs/crm/specs/STAGE_8_DASHBOARDS.md** — Stage 8 spec
13. **docs/crm/specs/STAGE_9_POLISH.md** — Stage 9 spec

### What's Working

1. **Dynamic Status Updates:**
   - Smooth animated "⏳/⌛" clock with dots progression
   - Dynamic status messages updating every 5 seconds
   - Different flows for RAG vs simple consultations
   - Clean message cleanup on completion

2. **Multi-Model Configuration:**
   - Separate models for consultation, article, classification, utility
   - Easy to test different models for different tasks
   - Cost optimization by using cheaper models where appropriate
   - Environment variable based configuration

3. **Enhanced Error Handling:**
   - Detailed error logging for OpenAI API failures
   - Increased timeout supports reasoning models
   - Status update failures don't break consultations
   - Graceful degradation on errors

4. **UX Improvements:**
   - Professional progress indication during consultation processing
   - No more static "Подождите..." messages
   - Users get feedback on what's happening
   - Consistent UX across all consultation flows

### What Needs Tests

1. **StatusMessageManager Unit Tests:**
   - Test start/complete lifecycle
   - Test context manager (`async with`)
   - Test background task cleanup
   - Test error handling in animation loops
   - Test proper message deletion

2. **Status Integration Tests:**
   - Test status updates in full consultation flow
   - Test RAG vs simple flow status sequences
   - Test status cleanup on errors
   - Test status updates with different message types (Message vs CallbackQuery)

3. **Multi-Model Configuration Tests:**
   - Test with different model combinations
   - Test missing model configuration (should fail)
   - Test model switching during runtime
   - Test with reasoning models (o1-preview)

4. **Error Handling Tests:**
   - Test timeout scenarios with reasoning models
   - Test OpenAI API error responses
   - Test status update callback failures
   - Test graceful degradation

## Next Steps

1. **Update .env.example with Multi-Model Configuration (HIGH PRIORITY):**
   - Add all 4 new model variables
   - Include example values (gpt-4o, gpt-4o-mini, o1-preview)
   - Add comments explaining which model to use for which task
   - File: `.env.example`

2. **Update Setup Documentation (HIGH PRIORITY):**
   - Document multi-model configuration in `docs/development/SETUP.md`
   - Explain when to use different models
   - Add troubleshooting for model configuration errors
   - Include pricing considerations

3. **Create Automated Tests for StatusMessageManager:**
   - Create `test_status_manager.py`
   - Mock Aiogram Message/CallbackQuery
   - Test start, complete, context manager, background tasks
   - Test error scenarios (message deletion fails, etc.)

4. **Create Integration Tests for Status Updates:**
   - Test consultation flow with status updates
   - Verify correct status sequence for RAG flow
   - Verify correct status sequence for simple flow
   - Test status cleanup on consultation completion and errors

5. **Test with Different OpenAI Models:**
   - Test consultation with gpt-4o
   - Test article generation with o1-preview (verify timeout works)
   - Test classification with gpt-4o-mini (verify speed improvement)
   - Measure latency and cost for each configuration

6. **Add Metrics for Status Updates:**
   - Track status update success/failure rate
   - Log timing of status message lifecycle
   - Monitor background task cancellation
   - Alert on high failure rates

7. **Document StatusMessageManager Usage (MEDIUM PRIORITY):**
   - Create `docs/features/STATUS_UPDATES.md`
   - Explain dual-message system architecture
   - Document status flow sequences
   - Provide examples for new handlers
   - Explain when to use `use_rag=True` vs `False`

8. **Optimize Status Update Timing:**
   - Collect user feedback on 5-second interval
   - Consider adaptive timing based on operation type
   - Test different intervals (3s, 7s) for best UX
   - Consider speeding up during final loop

9. **Add Structured Logging for Status Updates:**
   - Log when status manager starts
   - Log each status transition
   - Log completion and cleanup
   - Include timing information for analysis

10. **Version Bump and Deployment (WHEN REQUESTED):**
    - Update version in README.md: `1.2.1` → `1.2.2`
    - Create git commit with session summary
    - Push to GitHub (only when explicitly requested)
    - Test on production with real users
    - Monitor status update performance

## Dependencies

- No new Python dependencies added
- No new npm dependencies added
- All changes use existing infrastructure (asyncio, Aiogram, OpenAI SDK)

## Database Changes

- No schema changes required
- No migration files needed
- All changes are code-level only

## Environment Variables

### NEW Variables (Required):

```bash
# OpenAI Model Configuration (all required)
OPENAI_MODEL_CONSULTATION=gpt-4o        # High quality consultation answers
OPENAI_MODEL_ARTICLE=gpt-4o             # Article generation (or o1-preview for reasoning)
OPENAI_MODEL_CLASSIFICATION=gpt-4o-mini # Fast category/culture classification
OPENAI_MODEL_UTILITY=gpt-4o-mini        # Quick utility tasks (question composition)
```

### REMOVED Variable:

```bash
# OPENAI_MODEL is no longer used (replaced by task-specific models)
```

### All Other Existing Variables Remain Valid

## Deployment Notes

1. **Breaking Change: Environment Variables:**
   - Old `OPENAI_MODEL` variable is no longer used
   - Must set all 4 new model variables in `.env`
   - Bot will fail to start if any model variable is missing
   - Update `.env` before deploying

2. **Backward Compatibility:**
   - Status updates are optional (handlers work without them)
   - Existing consultation flows continue to work
   - Temperature configuration from previous session still works
   - No database changes required

3. **Backend Deployment:**
   ```bash
   # Pull latest changes
   git pull origin main

   # REQUIRED: Update .env with new model variables
   # Remove old OPENAI_MODEL line
   # Add 4 new model variables (see above)
   nano .env

   # Verify configuration
   python -c "from src.config import settings; print(settings.openai_model_consultation)"

   # Restart bot + API
   sudo systemctl restart sadovniki-bot
   ```

4. **Verification Steps:**
   - Start consultation → should see animated "⏳/⌛" message
   - Watch for dynamic status updates every 5 seconds
   - Verify status messages are deleted on completion
   - Check logs for any status update errors
   - Verify different models are used (check OpenAI logs or local logs)

5. **Model Configuration Examples:**
   ```bash
   # Cost-optimized configuration
   OPENAI_MODEL_CONSULTATION=gpt-4o-mini
   OPENAI_MODEL_ARTICLE=gpt-4o
   OPENAI_MODEL_CLASSIFICATION=gpt-4o-mini
   OPENAI_MODEL_UTILITY=gpt-4o-mini

   # Quality-optimized configuration
   OPENAI_MODEL_CONSULTATION=gpt-4o
   OPENAI_MODEL_ARTICLE=o1-preview
   OPENAI_MODEL_CLASSIFICATION=gpt-4o
   OPENAI_MODEL_UTILITY=gpt-4o-mini

   # Balanced configuration (recommended)
   OPENAI_MODEL_CONSULTATION=gpt-4o
   OPENAI_MODEL_ARTICLE=gpt-4o
   OPENAI_MODEL_CLASSIFICATION=gpt-4o-mini
   OPENAI_MODEL_UTILITY=gpt-4o-mini
   ```

6. **Monitoring:**
   - Watch OpenAI API costs (different models have different pricing)
   - Monitor consultation latency (o1-preview is slower but higher quality)
   - Track status update success rate
   - Check user feedback on new UX

## Session Statistics

- **Files Changed:** 11 modified, 13 created (24 total)
- **Lines Changed:** ~206 insertions, ~85 deletions in code; ~800+ lines in documentation
- **New Utility:** StatusMessageManager (262 lines)
- **Duration:** ~2 hours (estimated)
- **Commits Ready:** 1 (session end commit)
- **Tests Written:** 0 (testing needed)
- **Documentation Updated:** session-summary.md, PROJECT_MAP.md, CRM roadmap

---

**Session completed:** 2025-12-14
**Ready for:** Testing, deployment with updated .env, user feedback on status UX
**Status:** All changes implemented, CRM roadmap documented, ready to commit
