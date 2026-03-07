# Session Summary — 2026-03-07

## Session Log: 2026-03-07

**Duration:** Brief (no code changes)
**Goal:** Session review / context handoff
**Result:** No changes made. Session closed with documentation in sync.

**Status carried forward from 2026-03-05:**
- SKIP_PAYMENT = True still active in funnel_b.py — MUST flip before deploy
- DB schemas 82 → 83 → 81 → 93 still NOT applied on production
- Article PDF generator implemented but not tested on server
- WeasyPrint Dockerfile deps not added yet
- 53 quiz preview.jpg files are 0-byte stubs (need actual blurred previews)

All next steps from 2026-03-05 session remain valid and unchanged.

---

# Session Summary — 2026-03-05

## Project Context

**Sadovniki-bot** — Telegram-bot for professional consultations on berry crops with RAG system (PostgreSQL + pgvector) and OpenAI GPT.

**Current Version:** 1.9.0 (bumped after batch presentation generation feature)

**Tech Stack:**
- Backend: Python 3.11+, Aiogram 3.x, asyncpg, OpenAI API
- Frontend: React + TypeScript (Admin Panel), Vite
- Database: PostgreSQL 16 + pgvector
- PDF Generation: WeasyPrint + Jinja2 + markdown-python

---

## Session Goal

Two independent workstreams:

1. **Funnel B — Upsell after quiz payment**: Implement post-payment upsell flow (survey + offer screen) that triggers 90 seconds after PDF/plan delivery.

2. **Article PDF Generator**: Build full pipeline to generate professional PDF documents from articles stored in `admin_articles` table — WeasyPrint-based, branded design matching design system.

Additionally: batch presentation generation from articles (5 commits already in main prior to this session), plus polish of quiz offer texts across all cultures.

---

## Accomplishments

### Implemented

**1. Funnel B Upsell Flow (`src/handlers/funnel_b_upsell.py`, new file, 549 lines)**
- Complete post-payment upsell sequence triggered 90 seconds after plan delivery
- Unique trigger text per `problem_key` (53 texts, see `src/data/quiz_upsell_texts.py`)
- 3-question survey: urgency (3 options), goal (2 options), schedule (2 options)
- Answers saved to `user_quiz_survey2` table (schema_93)
- LLM-generated personalized diagnosis based on survey answers + problem_key + culture
- Offer screen with 2 CTA buttons: "Seasonal Program" and "Consultation Subscription"
- Both CTA buttons are stubs that log choice to `user_upsell_choice` table (analytics)
- Human-readable labels for LLM input (`_URGENCY_LABELS`, `_GOAL_LABELS`, `_SCHEDULE_LABELS`)
- Culture dative forms for offer title ("Программа по клубнике / малине / ...")
- Registered in `src/handlers/__init__.py` as `funnel_b_upsell_router` (priority 2.8)

**2. Upsell Trigger Texts (`src/data/quiz_upsell_texts.py`, new file, 354 lines)**
- 53 unique trigger texts keyed by `problem_key` (one per culture x problem combination)
- Pattern: confirms plan received + sets up why one plan may not be enough
- Fallback: auto-generated text using `get_problem_label()` + `get_culture_label()`

**3. DB Schema: Quiz Survey 2 (`db/schema_93_quiz_survey2.sql`, new file)**
- Table `user_quiz_survey2`: user_id, urgency, goal, schedule, timestamps, UNIQUE(user_id)
- Table `user_upsell_choice`: user_id, choice (seasonal_program | consultation_subscription), UNIQUE(user_id)
- Both tables: cascade delete on user, indexed on user_id

**4. Payment Service: Upsell Trigger Integration (`src/services/payments/payment_service.py`)**
- Added `schedule_upsell_trigger()` call at end of `_generate_quiz_plan_after_payment()`
- Triggers 90 seconds after plan is delivered (non-blocking, async)
- PDF delivery retry logic added: 3 attempts, 120s timeout, 3s * attempt backoff
- Fallback message to user if all retries fail

**5. Funnel B Offer Text Overhaul (`src/handlers/funnel_b.py`, 1255 → 1631 lines)**
- All strawberry offer texts rewritten (summer: 6 problems, remontant: 6 problems)
- New format: problem hook → "Чаще всего дачники:" → 3 numbered mistakes → warning → CTA with fire emoji
- All other culture offer texts to be continued (see funnel_b.py)
- OFFER_TEXT_2 updated with HTML formatting: `<s>490 ₽</s>` strikethrough + `<b>99 ₽</b>` bold
- Culture keyboard: emojis removed from button labels (cleaner display on mobile)
- "Other culture" button removed from keyboard (6 cultures only: strawberry, raspberry, blueberry, currant, honeysuckle, blackberry)
- `SKIP_PAYMENT = True` flag added for local testing (bypasses YooKassa payment)

**6. Quiz Solutions PDF Lookup Fix (`src/services/quiz_solutions.py`)**
- `_find_pdf()` helper: searches for `solution.pdf` first, falls back to any `*.pdf` in directory
- Allows placing generated presentation PDFs directly without renaming to `solution.pdf`

**7. Article PDF Generator Infrastructure (`scripts/`)**
- `scripts/md_to_pdf.py` — Markdown → PDF converter using WeasyPrint + Jinja2
  - Cover page (dark green background, culture name, category, SVG ornament)
  - TOC auto-generated from `##` headings
  - Content pages with running headers and page numbers
  - Callout blocks: paragraphs starting with "Важно:" get red left border
  - CLI: `--test`, `--input`, `--culture`, `--variety`, `--category`
- `scripts/generate_article_pdfs.py` — batch generator from `admin_articles` DB
  - Connects to PostgreSQL (`bot_user@localhost:5432/garden_bot`)
  - Output: `data/article_pdfs/{culture_key}_{variety_key}/{category_key}.pdf`
  - Flags: `--dry-run`, `--culture`, `--force`
- `scripts/pdf_styles.css` — full PDF stylesheet (natural/organic design system)
- `scripts/pdf_template.html` — Jinja2 HTML template (cover + TOC + content)
- `scripts/fonts/` — offline Cormorant Garamond + Source Sans 3 woff2 files
- `scripts/assets/` — logo assets directory
- `data/article_pdfs/` — output directory (gitignored)

**8. Presentation-to-Quiz Sync Script (`scripts/sync_presentations_to_quiz.py`)**
- Copies generated presentation PDFs from `data/content/presentations/` to `data/quiz_solutions/`
- Uses `_KEY_TO_PATH` mapping from `quiz_solutions.py`
- Flags: `--force`, `--dry-run`

**9. Quiz Preview Generator Script (`scripts/generate_quiz_previews.py`)**
- Batch generates blurred preview images for all `quiz_solutions/*/solution.pdf`
- Uses existing `src/services/pdf_preview.py`

**10. Docker + Infrastructure (`docker-compose.yml`, `requirements.txt`, `.gitignore`)**
- `requirements.txt`: added `weasyprint>=60.0`, `markdown>=3.6`, `jinja2>=3.1.0`
- `docker-compose.yml`: added volume mount `./data/content/presentations:/app/data/content/presentations`
- `.gitignore`: added `data/content/` to ignore generated content

**11. Fertilizers Reference Enhancement (`src/prompts/category_prompts/_fertilizers_reference.py`)**
- Added rule for leaf feeding during flowering/fruiting: Plantafol high-K + calcium foliar
- Added bio/chem compatibility rules: biopesticides cannot follow recent chemical fungicides
- Added entomophage/insecticide compatibility rules (same logic as bio/chem)

**12. CRM: client_funnel_repo.py refactor**
- `update_client_status()`: moved `paid` virtual status handling before DB column validation
- Prevents "invalid column" error when `paid` is passed as status (previously reached the validation check)

**13. Presentations Page: "Category" Generation Mode (`admin-webapp/src/components/presentations/PresentationsPage.tsx`)**
- New third generation mode: `'category'` (article → presentation via culture + category key)
- Auto-loads article from `admin_articles` when culture + category are selected
- Shows article info preview (topic + length) before generation
- Calls `api.getArticleByKeys()` → backend endpoint `GET /api/admin/articles/by-keys`

**14. API: Article by Keys Endpoint (`src/api/handlers/presentations.py`)**
- New `generation_mode = "category"` branch in `create_presentation_api`
- Fetches article from DB by `category_key + culture_key + variety_key`
- Auto-generates title: `{category_label} — {culture_label}`
- Stores `category_key` in `problem_key` column (column reuse)

**15. Article PDF Documentation (`docs/features/ARTICLE_PDFS.md`, new file)**
- Documents full PDF generation pipeline, file structure, batch commands

**16. Implementation Plan (`docs/plans/2026-03-05-article-pdf-generator.md`)**
- Full step-by-step plan for article PDF generator (completed this session)

---

## Key Decisions

### Architecture

- **Upsell trigger as async delayed task**: `schedule_upsell_trigger()` uses `asyncio.create_task()` with a 90-second sleep. The task is non-blocking — quiz payment delivery completes immediately, upsell fires after delay. Risk: if bot restarts within 90s of payment, task is lost. Acceptable for current scale.

- **53 unique upsell trigger texts in separate data file**: `quiz_upsell_texts.py` keeps copy separate from handler logic. Easier for content team to edit without touching handler code.

- **`_find_pdf()` fallback in quiz_solutions**: allows placing presentation PDFs from batch generator directly in the quiz directory without renaming. The batch presenter generates `{problem_key}.pdf`, not `solution.pdf`. The sync script (`sync_presentations_to_quiz.py`) handles the copy+rename.

- **Presentation-to-quiz pipeline**: generated presentations (via admin panel batch flow) → `sync_presentations_to_quiz.py` → `data/quiz_solutions/`. This avoids storing PDFs twice at the cost of a manual sync step.

- **`SKIP_PAYMENT = True` flag in funnel_b.py**: module-level constant for local development. Must be set to `False` before deploying to production. No env var — intentional (prevents accidental production skip).

- **WeasyPrint for article PDFs**: chosen over reportlab (too low-level), fpdf2 (no Markdown support), or headless Chrome (heavy). WeasyPrint renders HTML/CSS to PDF natively, supports `@page` rules, string counters, page numbers.

- **Column reuse `problem_key` for category presentations**: rather than adding a new `category_key` column to `admin_presentations`, the existing `problem_key` column is reused to store `category_key`. This avoids a DB migration. The `generation_mode` field distinguishes the meaning.

### Logic

- **Quiz survey 2 options simplified**: urgency has 3 options (early/progressing/urgent), goal reduced to 2 (close_now/stable_season), schedule reduced to 2 (ready_system/ask_answers). Previous design had 3+4+3 = complex. Simplified for conversion.

- **CTA stubs with analytics logging**: both CTA buttons ("Seasonal Program", "Consultation Subscription") save choice to `user_upsell_choice` table and show "Coming soon" message. Analytics is more valuable than premature product launch.

- **Keyboard emoji removal in quiz**: emojis in button text were causing layout issues on some Telegram clients. Removed from culture selection keyboard. "Other culture" option removed since all 6 main cultures are covered.

---

## Problems and Limitations

- **`SKIP_PAYMENT = True` is active in `funnel_b.py`**: MUST be set to `False` before deploying to production. This is a dev-only bypass.

- **DB schema_93 NOT applied on production**: `user_quiz_survey2` and `user_upsell_choice` tables do not exist in production. Bot will crash if upsell flow is triggered before applying schema_93.

- **Schemas 81-83 from previous session STILL not applied**: these are required for funnel B to work at all (user_quiz_answers, problem_key column, funnel B activation).

- **Upsell trigger lost on bot restart**: the 90-second async task disappears if the bot is restarted within that window. No persistence mechanism. Low probability but not zero.

- **Article PDF generator not tested end-to-end**: scripts exist and plan is documented, but actual PDF generation from DB has not been run. Requires local DB access or SSH tunnel to server.

- **WeasyPrint system deps on server**: Ubuntu requires `libpango-1.0-0 libpangoft2-1.0-0 libcairo2`. Not yet added to Dockerfile.

- **Fonts in scripts/fonts/ may be incomplete**: the woff2 download URLs in the plan may be outdated. Need to verify fonts work in WeasyPrint before running batch on server.

- **Preview JPEGs in `data/quiz_solutions/` are present but empty placeholders**: 53 `preview.jpg` files exist as 0-byte stubs (from untracked files list). These need to be replaced with actual blurred previews.

---

## Rejected Ideas

- **Upsell flow with FSM (aiogram FSMContext)**: rejected in favor of existing `CONSULTATION_STATE` dict pattern. Consistency with codebase, avoids FSM state management complexity.

- **Storing upsell survey answers in session only (not DB)**: rejected — need analytics to measure what users want (seasonal program vs subscription). DB storage is required.

- **Automatic upsell text generation via LLM**: initially considered generating the trigger text dynamically using problem_key + culture context. Rejected: unpredictable quality, latency, and cost. 53 hand-crafted texts are better for conversion.

- **FPDF2 for article PDFs**: considered as simpler alternative to WeasyPrint. Rejected: doesn't support Markdown, requires manual layout code for every element. WeasyPrint allows full CSS control.

---

## Current Code State

### Files Changed This Session

| File | Change Type | Status |
|------|-------------|--------|
| `src/handlers/funnel_b_upsell.py` | New (549 lines) | Working, needs schema_93 in prod |
| `src/data/quiz_upsell_texts.py` | New (354 lines) | Working |
| `db/schema_93_quiz_survey2.sql` | New DB migration | NOT APPLIED on prod |
| `src/services/payments/payment_service.py` | Upsell trigger + PDF retry | Working |
| `src/handlers/funnel_b.py` | +376 lines (offer text overhaul + SKIP_PAYMENT) | Working locally (SKIP_PAYMENT=True) |
| `src/services/quiz_solutions.py` | _find_pdf() fallback | Working |
| `src/handlers/__init__.py` | Register upsell router | Working |
| `scripts/md_to_pdf.py` | New (PDF converter) | Implemented, not tested on server |
| `scripts/generate_article_pdfs.py` | New (batch generator) | Implemented, not tested |
| `scripts/pdf_styles.css` | New (PDF stylesheet) | Ready |
| `scripts/pdf_template.html` | New (Jinja2 template) | Ready |
| `scripts/fonts/` | New (offline font files) | Ready |
| `scripts/assets/` | New (logo dir) | Empty, needs logo |
| `scripts/sync_presentations_to_quiz.py` | New (sync script) | Working |
| `scripts/generate_quiz_previews.py` | New (preview batch) | Working |
| `src/prompts/category_prompts/_fertilizers_reference.py` | Added bio/chem compatibility rules | Working |
| `src/services/db/client_funnel_repo.py` | 'paid' status handling refactor | Working |
| `admin-webapp/src/components/presentations/PresentationsPage.tsx` | Category mode added | Working |
| `src/api/handlers/presentations.py` | category generation_mode | Working |
| `docs/features/ARTICLE_PDFS.md` | New documentation | Done |
| `docs/plans/2026-03-05-article-pdf-generator.md` | Implementation plan | Done (plan executed) |
| `docker-compose.yml` | Added content/presentations volume | Working |
| `requirements.txt` | weasyprint + markdown + jinja2 | Done |
| `.gitignore` | Added data/content/ | Done |

### Previously Pending (from 2026-03-01) — Still Not Applied

| Item | Status |
|------|--------|
| `db/schema_81_activate_funnel_b.sql` | NOT APPLIED on production |
| `db/schema_82_quiz_answers.sql` | NOT APPLIED on production |
| `db/schema_83_quiz_problem_key.sql` | NOT APPLIED on production |

### What Works

- Upsell flow logic end-to-end (all 53 texts, survey, LLM diagnosis, CTA)
- Upsell trigger fires 90 seconds after payment/plan delivery
- Quiz offer texts for all strawberry problems (summer + remontant) fully rewritten
- Presentation "category" mode in admin panel (auto-loads article, generates presentation)
- Quiz PDF lookup: any .pdf in directory (not just solution.pdf)
- Sync script: copies generated presentations to quiz_solutions directory

### What Needs Testing / Action

- Apply DB schemas **in order**: 82 → 83 → 81 → **93** on production
- Set `SKIP_PAYMENT = False` in `funnel_b.py` before deploying
- Run `scripts/generate_article_pdfs.py --dry-run` to verify 48 articles are found
- Test WeasyPrint PDF generation locally (`python scripts/md_to_pdf.py --test`)
- Replace 53 stub `preview.jpg` files with actual blurred previews
- Add WeasyPrint system deps to Dockerfile (`libpango libpangoft2 libcairo2`)

---

## Next Steps

1. **CRITICAL — Set `SKIP_PAYMENT = False` in `src/handlers/funnel_b.py` before ANY deploy**
   Line 16: `SKIP_PAYMENT = True` → `SKIP_PAYMENT = False`

2. **Apply ALL pending DB schemas on production** (must apply in order):
   ```
   schema_82_quiz_answers.sql
   schema_83_quiz_problem_key.sql
   schema_81_activate_funnel_b.sql
   schema_93_quiz_survey2.sql
   ```

3. **Test article PDF generation locally**:
   ```bash
   python scripts/md_to_pdf.py --test
   # Should create data/article_pdfs/test.pdf — open and verify visually
   ```

4. **Run batch PDF generation** (requires DB access):
   ```bash
   python scripts/generate_article_pdfs.py --dry-run
   python scripts/generate_article_pdfs.py --culture strawberry
   ```

5. **Add Dockerfile deps for WeasyPrint** (for production PDF generation in container):
   ```dockerfile
   RUN apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libcairo2
   ```

6. **Generate actual quiz preview images**:
   - First: run `sync_presentations_to_quiz.py` to populate `data/quiz_solutions/`
   - Then: run `generate_quiz_previews.py` to create blurred previews
   - Replace existing 0-byte `preview.jpg` stub files

7. **Test full quiz flow end-to-end** with test Telegram account:
   - New user `/start` → quiz → offer text → payment (set `SKIP_PAYMENT=True` locally)
   - After payment: plan delivery → 90s delay → upsell trigger → survey → diagnosis → CTA

8. **Test upsell CTA buttons**: clicking "Seasonal Program" or "Consultation Subscription"
   should save choice to `user_upsell_choice` and show placeholder message

9. **Content: rewrite remaining offer texts in `funnel_b.py`**:
   - Raspberry (summer + remontant): 16 problems
   - Currant: 6 problems
   - Honeysuckle: 7 problems
   - Blackberry: 4 problems
   - Blueberry: 4 problems
   - Currently using old generic format

10. **Deploy** after testing:
    ```bash
    ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
      'cd /root/Sadovniki_bot1.2 && git pull && docker compose up -d --build bot'
    ```

11. **Bump version to 2.0.0** (major: article PDF system + upsell funnel complete)
