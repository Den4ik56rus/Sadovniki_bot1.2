# Funnel B — Quiz Onboarding Flow

**Status:** Implemented, DB schemas NOT applied on production (2026-03-01)
**Related feature:** A/B Test (funnel_variant field on users table)

---

## Purpose

Funnel B is the alternative onboarding for new users in the A/B test. Instead of showing the standard main menu on `/start`, new users go through a 4-step quiz that:
1. Collects their culture, variety (if applicable), region, and main problem
2. Shows a personalized offer based on their answers
3. Offers a paid "personal plan" (99 RUB via YooKassa) or free consultation

Goal: higher conversion by engaging the user before presenting the paid offer.

---

## Files and Entry Points

| File | Role |
|------|------|
| `src/handlers/funnel_b.py` | All quiz logic, handlers, offer texts (1255 lines) |
| `src/services/quiz_solutions.py` | PDF solution lookup, offer.txt loading |
| `src/services/pdf_preview.py` | PDF blur preview generator (Pillow + poppler) |
| `src/services/payments/payment_service.py` | `create_quiz_plan_payment()`, `_process_quiz_plan_payment_success()` |
| `src/handlers/menu.py` | `/start` handler routes new users to funnel B |
| `db/schema_81_activate_funnel_b.sql` | Activates funnel B in bot_settings |
| `db/schema_82_quiz_answers.sql` | Creates `user_quiz_answers` table |
| `db/schema_83_quiz_problem_key.sql` | Adds `problem_key` column to `user_quiz_answers` |
| `data/quiz_solutions/` | PDF files, previews, offer texts (structure below) |

---

## Architecture and Logic

### User Flow

```
/start (new user, active_funnel_variant = 'B')
    |
    v
start_funnel_b()
    |
    v
Msg: "Ок, начинаем диагностику..." (WELCOME_TEXT)
3s typing pause
    |
    v
Quiz 1: "Какая культура у Вас преобладает?"
  [Клубника] [Малина] [Голубика] [Смородина] [Жимолость] [Ежевика] [Другая]
    |
    +-- quiz_culture_strawberry or quiz_culture_raspberry
    |       |
    |       v
    |   Quiz 1.5: "Какой сорт у Вас?"
    |     [Летняя] [Ремонтантная]
    |       |
    +-- (other cultures skip this step)
    |
    v
Quiz 2: "В каком регионе выращиваете?"
  [Средняя полоса] [Юг] [Север] [Указать свой]
    |
    +-- quiz_region_custom: text input state
    |
    v
Quiz 3: "Что сейчас больше всего волнует?"
  (culture-specific problem list, e.g. for summer strawberry: Мало ягод, Желтые листья, ...)
    |
    v
Offer Message 1: personalized text (problem_key → function → text)
    + optional preview photo (data/quiz_solutions/{culture}/{problem}/preview.jpg)
Offer Message 2: "Обычно такой план стоит 490 ₽. Сегодня - 99 ₽."
  [🔥 Получить персональную схему] [Получить бесплатную консультацию]
    |
    +-- quiz_cta_payment
    |       |
    |       v
    |   create_quiz_plan_payment() → YooKassa URL
    |   Show payment link button
    |       |
    |       v (webhook: payment succeeded)
    |   _process_quiz_plan_payment_success()
    |       |
    |       +-- if PDF exists: _deliver_quiz_pdf_solution() → send document
    |       +-- else: _generate_auto_consultation() → LLM answer
    |
    +-- quiz_cta_consultation
            |
            v
        set state = "waiting_consultation_question"
        show standard consultation entry text
```

### Repeat /start

If `user_quiz_answers` has a row for this user → they already completed the quiz.
`_quiz_already_done()` is called in `/start`. If true → standard menu (not quiz).

### State Machine

Quiz states stored in `CONSULTATION_STATE[tg_user.id]`:
- `quiz_awaiting_culture`
- `quiz_awaiting_variety` (strawberry/raspberry only)
- `quiz_awaiting_region`
- `quiz_awaiting_region_text` (if "указать свой")
- `quiz_awaiting_culture_text` (if "другая культура")
- `quiz_awaiting_problem`
- State cleared after problem selection

### Culture-Specific Problem Keys

All problem keys follow `{culture_prefix}_{variety_prefix}_{problem_name}` pattern:

| Culture | Variety | Example Keys |
|---------|---------|-------------|
| strawberry | summer (s) | straw_s_low_yield, straw_s_yellow_leaves, straw_s_leaf_spots, straw_s_pests, straw_s_planting, straw_s_soil_prep |
| strawberry | remontant (r) | straw_r_leaf_spots, straw_r_rot, straw_r_yellow_leaves, straw_r_dieback, straw_r_planting, straw_r_soil_prep |
| raspberry | summer (s) | rasp_s_diseases, rasp_s_pruning, rasp_s_larvae, rasp_s_white_berry, rasp_s_small_berry, rasp_s_stem_spots, rasp_s_planting, rasp_s_soil_prep |
| raspberry | remontant (r) | rasp_r_diseases, rasp_r_pruning, rasp_r_larvae, rasp_r_small_berry, rasp_r_white_berry, rasp_r_stem_spots, rasp_r_planting, rasp_r_soil_prep |
| currant | (none) | cur_yellow_leaves, cur_drying, cur_glasswing, cur_pruning, cur_planting, cur_soil_prep |
| honeysuckle | (none) | hon_bad_taste, hon_low_yield, hon_brown_leaves, hon_no_berries, hon_pruning, hon_planting, hon_soil_prep |
| blackberry | (none) | blk_pruning, blk_shelter, blk_planting, blk_soil_prep |
| blueberry | (none) | blu_yellow_leaves, blu_no_fruit, blu_soil_prep, blu_planting |

### Offer Text Priority

For each `problem_key` the offer text is resolved in this order:
1. `data/quiz_solutions/{culture_folder}/{problem_folder}/offer.txt` (file-based, editable without code)
2. Hardcoded per-culture function (e.g. `_get_strawberry_offer_text()`)
3. Generic `_get_offer_text(culture_key, problem_key)` template

### PDF Solution Delivery

After successful YooKassa payment:
1. `_generate_quiz_plan_after_payment()` runs as background task
2. Calls `get_quiz_solution(problem_key)` from `quiz_solutions.py`
3. If `data/quiz_solutions/{culture}/{problem}/solution.pdf` exists:
   - `_deliver_quiz_pdf_solution()` sends the PDF as Telegram document
4. If no PDF: `_generate_auto_consultation()` runs LLM with quiz data as context

### data/quiz_solutions/ Structure

```
data/quiz_solutions/
  strawberry_summer/
    low_yield/
      solution.pdf        (required for PDF path)
      preview.jpg         (optional — shown in offer before payment)
      offer.txt           (optional — custom offer copy)
      config.json         (optional — title, teaser, captions)
    leaf_spots/
      ...
  strawberry_remontant/
    ...
  raspberry_summer/
    ...
  currant/
    ...
  honeysuckle/
    ...
  blackberry/
    ...
  blueberry/
    ...
```

---

## Key Decisions

- **CONSULTATION_CONTEXT** stores `quiz_culture_key` and `quiz_variety_key` during quiz to select the right problem keyboard. This is the same global dict used by consultation flow.
- **Upsert on conflict** for `user_quiz_answers` — quiz can be partially re-run, each step overwrites previous value.
- **`_mark_selected()`** replaces the full keyboard with a single "✅ Selected" button after each choice to prevent re-selection.
- **`noop` callback handler** absorbs clicks on already-selected buttons without showing error.
- **Quiz messages logged** via `_log_quiz_msg()` with `session_id = "quiz:{user_id}"` for CRM visibility.

---

## DB Schema

```sql
-- schema_82: Created by quiz onboarding
CREATE TABLE IF NOT EXISTS user_quiz_answers (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    culture TEXT,
    region TEXT,
    problem TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id)
);

-- schema_83: problem_key column for PDF lookup
ALTER TABLE user_quiz_answers ADD COLUMN IF NOT EXISTS problem_key TEXT;

-- schema_81: Activates funnel B
UPDATE bot_settings SET value = 'B', updated_at = NOW() WHERE key = 'active_funnel_variant';
```

---

## Edge Cases and Risks

- **Empty data/quiz_solutions/**: All payments fall back to LLM auto-consultation. This is handled gracefully.
- **CRM funnel moved to `paid` on button click** (before payment completes): intentional to track high intent.
- **`CONSULTATION_CONTEXT` cleared on restart**: If bot restarts mid-quiz, user may see wrong problem keyboard. Mitigated by DB persistence of each quiz step.
- **poppler-utils required for pdf_preview.py**: Must be installed in Docker if PDF previews are needed. Not added to Dockerfile yet.
- **YooKassa payment not tested end-to-end**: Need test with real payment or YooKassa test mode.

---

## TODO / Next Steps

- [ ] Apply schemas 81-83 on production (in order: 82 → 83 → 81)
- [ ] Verify quiz API routes registered (PATCH/DELETE /api/admin/crm/clients/{id}/quiz)
- [ ] Create first PDF: `data/quiz_solutions/strawberry_summer/low_yield/solution.pdf`
- [ ] Add `poppler-utils` to Dockerfile if PDF previews needed
- [ ] Test full flow end-to-end in Telegram (quiz → payment → delivery)
- [ ] Write offer.txt files for high-traffic problem keys
- [ ] Monitor A/B test: quiz completion rate, payment conversion rate
