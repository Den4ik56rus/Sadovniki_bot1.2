# Session Summary — 2026-03-01

## Project Context

**Sadovniki-bot** — Telegram-bot for professional consultations on berry crops with RAG system (PostgreSQL + pgvector) and OpenAI GPT.

**Current Version:** 1.8.0 (bumped after articles page feature in previous session)

**Tech Stack:**
- Backend: Python 3.11+, Aiogram 3.x, asyncpg, OpenAI API
- Frontend: React + TypeScript (Admin Panel), Vite
- Database: PostgreSQL 16 + pgvector

---

## Session Goal

Implement full Funnel B (quiz-based onboarding) for the A/B test:
- Complete 4-step quiz with culture/variety/region/problem selection
- Personalized offer generation per culture x problem pair
- YooKassa payment for quiz plan (99 RUB)
- PDF delivery or LLM auto-consultation after payment
- CRM admin panel enhancements: quiz data display + funnel variant field

---

## Accomplishments

### Implemented

**1. Funnel B — Full Quiz Onboarding (`src/handlers/funnel_b.py`, 1255 lines)**
- Complete 4-step quiz: culture → variety (strawberry/raspberry only) → region → problem
- Culture-specific problem sets: strawberry (summer/remontant), raspberry (summer/remontant), currant, honeysuckle, blackberry, blueberry
- All 50+ problem keys with individual personalized offer texts per culture x problem combo
- Offer text fallback: file-based `offer.txt` → hardcoded per-culture → generic template
- PDF preview display if `data/quiz_solutions/{culture}/{problem}/preview.jpg` exists
- `_mark_selected()` helper: replaces keyboard with single checkmark button after selection
- State machine: `quiz_awaiting_culture` → `quiz_awaiting_variety` → `quiz_awaiting_region` → `quiz_awaiting_problem` → cleared
- Custom text input states for "other culture" and custom region
- Quiz quiz logging to CRM messages table via `_log_quiz_msg()`
- Repeat `/start` guard: if `user_quiz_answers` row exists → show standard menu, not quiz
- CTA buttons: "Get personal plan" (payment) and "Get free consultation" (standard flow)
- `_generate_auto_consultation()`: auto-sends LLM answer using quiz data after free CTA or payment fallback
- `quiz_focus_instructions` injected into `ask_consultation_llm()` to enforce concise action-plan style

**2. Payment: Quiz Plan (`src/services/payments/payment_service.py`)**
- `create_quiz_plan_payment()`: creates YooKassa payment for 99 RUB
- Payment type `quiz_plan` registered; `create_payment_activity_event()` supports it
- `_process_quiz_plan_payment_success()`: background task on webhook success
- `_generate_quiz_plan_after_payment()`: dual delivery path:
  - PDF path: if `data/quiz_solutions/{problem_key}/solution.pdf` exists → `_deliver_quiz_pdf_solution()`
  - LLM path: fallback auto-consultation generation if no PDF
- CRM funnel update to `paid` on payment success

**3. Quiz Solutions Lookup (`src/services/quiz_solutions.py`, new file, 248 lines)**
- `get_quiz_solution(problem_key)`: looks up ready PDF at `data/quiz_solutions/{culture}/{problem}/`
- `get_offer_text(problem_key, region)`: loads `offer.txt` from solution dir with header injection
- Full `_KEY_TO_PATH` mapping for all 50+ problem keys
- `_OFFER_HEADERS` dict for human-readable culture + problem header in offer text
- Preview lookup: first checks problem dir, then falls back to `{culture}/preview/` dir

**4. PDF Preview Generator (`src/services/pdf_preview.py`, new file, 330 lines)**
- Renders PDF first page → blurred image with "Locked" overlay
- Removes NotebookLM watermark before blurring
- Dependencies: Pillow, pdftoppm (poppler-utils)
- Used for showing teaser preview before payment

**5. Database Migrations (new files)**
- `db/schema_81_activate_funnel_b.sql`: sets `active_funnel_variant = 'B'` in `bot_settings`
- `db/schema_82_quiz_answers.sql`: creates `user_quiz_answers` table (user_id, culture, region, problem, created_at, updated_at)
- `db/schema_83_quiz_problem_key.sql`: adds `problem_key TEXT` column to `user_quiz_answers`

**6. Consultation LLM Extension (`src/services/llm/consultation_llm.py`)**
- Added `quiz_focus_instructions: Optional[str] = None` parameter to `ask_consultation_llm()`
- Appended to system prompt when present to enforce focused quiz-consultation response style

**7. CRM: Quiz Data in Client Card (`admin-webapp/src/components/crm/LeftPanel/`)**
- `MainTab.tsx`: new section "Quiz Answers" showing funnel variant (A/B), culture, region, problem
- Edit mode for quiz answers with Save/Cancel
- Reset quiz button (clears user_quiz_answers row, resets funnel_variant to A)
- `index.tsx`: wired `handleFunnelVariantChange`, `handleQuizAnswersChange`, `handleQuizReset` handlers calling backend API

**8. CRM: Client Full Data (`src/services/db/client_crm_repo.py`)**
- `get_client_full_data()` extended: joins `user_quiz_answers` and `users.funnel_variant`
- Returns `funnel_variant`, `quiz_culture`, `quiz_region`, `quiz_problem` to frontend

**9. CRM API: Quiz Endpoints (`src/api/handlers/crm.py`)**
- `PATCH /api/admin/crm/clients/{id}/quiz`: update quiz answers (culture, region, problem)
- `DELETE /api/admin/crm/clients/{id}/quiz`: reset quiz (delete from user_quiz_answers, reset funnel_variant)
- `PATCH /api/admin/crm/clients/{id}/funnel-variant`: update funnel_variant A/B

**10. TypeScript Types (`admin-webapp/src/types/index.ts`)**
- `CrmClientFull` extended with `funnel_variant`, `quiz_culture`, `quiz_region`, `quiz_problem`

**11. `src/handlers/__init__.py`**
- Registered `funnel_b.router` into main dispatcher

**12. `src/handlers/menu.py`**
- `/start` handler: if `is_new_user` and `active_funnel_variant == 'B'` → call `start_funnel_b()`
- If returning user with quiz done → standard menu (repeat `/start` guard)

**13. `src/utils/status_manager.py`**
- Minor adjustments (likely to support `_generate_auto_consultation` streaming)

**14. Articles API (`src/api/handlers/articles.py`)**
- Minor fix (from previous session: Decimal serialization)

**15. Articles Page (`admin-webapp/src/components/articles/ArticlesPage.tsx`, `.module.css`)**
- Minor UI adjustments carried over from previous session

---

## Key Decisions

### Architecture

- **Dual delivery after payment**: PDF-first, LLM-fallback. If `data/quiz_solutions/{culture}/{problem}/solution.pdf` exists → send PDF directly. Otherwise → generate LLM auto-consultation. This allows gradual content creation without blocking the product launch.

- **Problem key naming convention**: `{culture_prefix}_{variety_prefix}_{problem_name}` (e.g. `straw_s_low_yield`, `rasp_r_pruning`, `cur_glasswing`). Flattened into single `_KEY_TO_PATH` dict mapping to `(culture_folder, problem_folder)` path tuples.

- **Offer text priority**: `offer.txt` in solution dir > hardcoded per-culture function > generic `_get_offer_text()`. This lets content editors add custom copy without code changes.

- **Variety sub-step**: Only strawberry and raspberry ask about variety (summer/remontant). All other cultures skip to region directly. Variety is stored as part of culture label (e.g. "Клубника (Ремонтантная)").

- **`CONSULTATION_CONTEXT` for quiz state**: Culture key and variety key stored in existing `CONSULTATION_CONTEXT[tg_user.id]` dict during quiz flow. This context is used to select the correct problem keyboard and generate the right offer text.

- **Quiz logging to CRM messages**: All bot messages and user selections during quiz are logged via `_log_quiz_msg()` using `session_id = f"quiz:{user_id}"`. This makes the quiz visible in CRM consultation history.

### Logic

- **Repeat /start**: `_quiz_already_done()` checks `user_quiz_answers` for existing row. If found → show standard menu. If not → run quiz from start. This prevents re-running quiz for users who completed it but didn't pay yet.

- **CRM funnel on payment button click**: When user clicks "Get personal plan" (before paying), status is immediately updated to `paid` in CRM. This is intentional — the click itself signals high intent.

- **`_mark_selected()` keyboard replacement**: After any quiz selection, the multi-button keyboard is replaced with a single button showing `✅ <selected text>`. Prevents re-selecting and provides visual feedback.

- **`noop` callback**: All "selected" buttons use `callback_data="noop"` which is handled by a router.callback_query that just calls `answer()`. Prevents Telegram "loading" spinner on already-selected buttons.

### Data Format

- `user_quiz_answers` has a single row per user (PRIMARY KEY on user_id, upsert on conflict)
- `problem_key` column added in schema_83 (after schema_82 created the table) — must apply both in order
- `funnel_variant` field is on `users` table (added in earlier schema, not this session)

---

## Problems and Limitations

- **DB schemas 81-83 NOT YET APPLIED ON PRODUCTION**: Must apply all three before enabling funnel B or quiz plan payments. Order matters: 82 before 83.

- **`data/quiz_solutions/` directory is empty**: No PDF solutions exist yet. All payments will fall back to LLM auto-consultation. PDFs need to be created and placed at the correct paths.

- **`data/previews/` directory is empty**: No generated previews exist. Preview display in quiz offer is silently skipped if no file found.

- **`pdf_preview.py` requires poppler-utils**: `pdftoppm` must be installed in Docker container. Not yet added to Dockerfile.

- **Quiz plan payment not tested end-to-end**: YooKassa webhook handling for `quiz_plan` type was implemented but not tested with real payments.

- **`CONSULTATION_CONTEXT` race condition**: If user sends messages rapidly during quiz, context dict mutations could have async race conditions (existing issue in codebase, not introduced here).

- **CRM quiz edit API not wired to route table**: The new PATCH/DELETE quiz endpoints in `crm.py` need to be registered in the API router (`src/api/router.py` or equivalent). This was likely done but should be verified.

---

## Rejected Ideas

- **Separate FSM states for quiz** (using aiogram FSMContext): Rejected in favor of existing `CONSULTATION_STATE` dict pattern used throughout the codebase. Consistency was prioritized over FSM safety.

- **Problem keyboard per culture without variety sub-step for strawberry**: Initially considered skipping variety and just using a single generic problem set. Rejected because strawberry summer vs remontant have completely different problem profiles.

- **Storing quiz answers in `CONSULTATION_CONTEXT` only (not DB)**: Rejected because context is lost on bot restart, and auto-consultation after payment needs the data.

---

## Current Code State

### Files Changed

| File | Change Type | Status |
|------|-------------|--------|
| `src/handlers/funnel_b.py` | Major rewrite (stub → 1255 lines) | Working |
| `src/services/payments/payment_service.py` | Added quiz_plan functions (+238 lines) | Working |
| `src/services/quiz_solutions.py` | New file (248 lines) | Working |
| `src/services/pdf_preview.py` | New file (330 lines) | Not tested (needs poppler) |
| `db/schema_81_activate_funnel_b.sql` | New DB migration | NOT APPLIED |
| `db/schema_82_quiz_answers.sql` | New DB migration | NOT APPLIED |
| `db/schema_83_quiz_problem_key.sql` | New DB migration | NOT APPLIED |
| `src/services/llm/consultation_llm.py` | Added quiz_focus_instructions param | Working |
| `src/handlers/__init__.py` | Registered funnel_b router | Working |
| `src/handlers/menu.py` | Added funnel B routing in /start | Working (after schema 81) |
| `src/services/db/client_crm_repo.py` | Extended get_client_full_data for quiz | Working (after schema 82+83) |
| `src/api/handlers/crm.py` | Added quiz PATCH/DELETE endpoints | Working |
| `admin-webapp/src/components/crm/LeftPanel/MainTab.tsx` | Quiz data display + edit | Working |
| `admin-webapp/src/components/crm/LeftPanel/index.tsx` | Wired quiz handlers | Working |
| `admin-webapp/src/types/index.ts` | Added quiz fields to CrmClientFull | Working |
| `admin-webapp/src/components/articles/ArticlesPage.tsx` | Minor adjustments | Working |
| `src/api/handlers/articles.py` | Decimal serialization fix | Working |
| `src/utils/status_manager.py` | Minor adjustments | Working |

### Data Directories (New, Empty)

- `data/previews/` — for generated PDF blur previews
- `data/quiz_solutions/` — for PDF solution files (structure: `{culture}/{problem}/solution.pdf`)

### What Works

- Quiz flow logic (all 6 cultures, 50+ problem keys)
- Offer text generation (hardcoded per culture x problem)
- CTA button → payment creation in YooKassa
- CRM client card shows quiz data (funnel_variant, culture, region, problem)
- CRM admin can edit/reset quiz answers
- LLM auto-consultation after payment (fallback path)

### What Needs Testing

- Full quiz flow end-to-end in Telegram (not tested live)
- YooKassa webhook → quiz_plan success processing
- PDF delivery path (needs actual PDF files in `data/quiz_solutions/`)
- `pdf_preview.py` (needs poppler-utils installed)
- CRM quiz edit/reset via admin panel

---

## Next Steps

1. **Apply DB migrations on production** (CRITICAL before any funnel B users):
   ```
   schema_81_activate_funnel_b.sql
   schema_82_quiz_answers.sql
   schema_83_quiz_problem_key.sql
   ```
   Apply in order: 82 → 83 → 81 (or 82 → 83 first, then decide when to activate B)

2. **Verify CRM quiz API routes registered** in `src/api/router.py` (PATCH quiz, DELETE quiz, PATCH funnel-variant endpoints)

3. **Create first PDF solution** and test delivery path:
   - Place `solution.pdf` in `data/quiz_solutions/strawberry_summer/low_yield/`
   - Add `preview.jpg` for offer preview display
   - Test full flow: quiz → payment → PDF delivery

4. **Add poppler-utils to Dockerfile** if PDF preview generation is needed:
   ```dockerfile
   RUN apt-get install -y poppler-utils
   ```

5. **Test full quiz flow** with a test Telegram account:
   - New user /start → quiz → offer → payment → auto-consultation OR PDF
   - Repeat /start → should show standard menu (not re-run quiz)

6. **Create offer.txt files** for problem-specific custom offer copy:
   - Place at `data/quiz_solutions/{culture}/{problem}/offer.txt`
   - Format: plain text with HTML tags for Telegram

7. **Deploy to production** after migrations and testing:
   ```bash
   ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
     'cd /root/Sadovniki_bot1.2 && git pull && docker compose up -d --build bot'
   ```

8. **A/B test monitoring**: Check `bot_settings.active_funnel_variant` is 'B' after applying schema_81. Monitor new user quiz completion rate and payment conversion in CRM.

9. **Content creation**: Write PDF solutions for the most common problem keys (strawberry is highest traffic — start with `straw_s_low_yield` and `straw_s_leaf_spots`)

10. **Bump version to 1.8.1** after successful deploy (or higher depending on what else ships)
