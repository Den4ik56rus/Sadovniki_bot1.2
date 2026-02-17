# Complexity Classification Flow

**Status:** Implemented (2026-02-18) — migrations pending, end-to-end testing needed
**Related systems:** Consultation entry, pricing, keyboards, consultation_logs

---

## Purpose

The complexity classification system determines the appropriate answer type and token cost for each user question before delivering a consultation. Instead of flat per-category pricing, the bot analyzes the specific question and classifies it into one of three tiers based on required answer complexity.

---

## Architecture

### Components

```
User Question
      |
      v
detect_answer_complexity()         <- src/services/llm/complexity_llm.py
      |
      v
ComplexityResult {
  tier: short_answer | long_answer | turnkey_solution
  phase_eligible: bool
  metadata: {current_phase, next_phase, topics, total_phases, multi_topic}
  confirm_message: str   (personalized explanation for user)
  phase_button_label: str (button text, max 35 chars)
  cost_usd / tokens
}
      |
      v
entry.py — route based on tier:
  short_answer (phase_eligible=false) --> direct consultation
  short_answer (phase_eligible=true)  --> show phase choice keyboard
  long_answer                         --> show confirm + cost keyboard
  turnkey_solution                    --> show purchase info + plan option
```

### Classifier Model

- Model: `gpt-4.1-mini` (configured via `admin_settings.model_complexity`)
- Temperature: empty by default (use model default)
- Reasoning effort: empty by default
- Feature flag: `FEATURE_COMPLEXITY_ENABLED=true` in environment

---

## Three Tiers

### Tier 1: short_answer (1 token)

Default tier. Applies when user asks a specific factual question answerable in 3-5 points.

**Examples:**
- "Какая кислотность почвы нужна для голубики?"
- "Когда лучше обрезать малину?"
- "Чем обработать клубнику от серой гнили?"

**Subtype — phase_eligible=true:**
Short question BUT answer would be significantly enhanced with seasonal phase breakdown. Applies to питание, защита, обрезка, полив topics where recommendations change by season.

- Shows 3-button keyboard: Краткий ответ / Подробно по фазам / Готовое решение
- `phase_button_label` example: "Подробно: подкормки по фазам"
- `confirm_message` explains that season context adds value

### Tier 2: long_answer (2 tokens per phase)

Applies when user EXPLICITLY requests a plan, schema, schedule, or sequence.

**Required keywords in question:** план, схема, расписать, распиши, последовательность, по порядку, пошагово, календарь, график, по месяцам

**Subtype B (total_phases=1):** Single-phase plan
- "Распиши план подкормок клубники на весну"

**Subtype C (total_phases=2-3):** Full-season plan
- "Дай план защиты на сезон"
- Keywords: на сезон, на весь год

**Delivery:** One phase at a time. After first phase delivered, "Next phase" button offered.

### Tier 3: turnkey_solution (purchase)

Applies to comprehensive multi-topic care requests covering питание + защита + уход for a full season. Priced as a product (1190 RUB), not tokens.

**Examples:**
- "Уход под ключ для клубники"
- "Полный план для малины на сезон"
- "Всё для ухода за голубикой: питание, защита, обрезка"

**Keywords:** под ключ, полный уход, всё для, комплексный, на весь сезон (multi-topic context)

---

## Seasonal Phases

Three phases in a fixed chain:

| Phase Key | Display Name | Months |
|-----------|-------------|--------|
| весна-цветение | ранняя весна — начало цветения | март-май |
| цветение-плодоношение | цветение — окончание плодоношения | июнь-август |
| плодоношение-зима | конец плодоношения — уход в зиму | сентябрь-февраль |

Next phase is determined by `PHASE_NEXT` dict in `complexity_llm.py` and `SEASONAL_PHASES` in `pricing.py`.

---

## Files

| File | Purpose |
|------|---------|
| `src/services/llm/complexity_llm.py` | Classifier — LLM call, prompt, response parsing |
| `src/pricing.py` | `COMPLEXITY_TIERS`, `SEASONAL_PHASES`, `PHASE_DISPLAY_NAMES`, cost functions |
| `src/handlers/consultation/entry.py` | Integration — calls classifier, routes by tier |
| `src/keyboards/consultation/common.py` | 5 new keyboard functions for complexity UI |
| `db/schema_48_complexity_tracking.sql` | DB columns: complexity_tier, complexity_metadata in consultation_logs |
| `db/schema_49_phase_tracking.sql` | DB columns: phase_mode, phase_key, phase_number in consultation_logs |

---

## New Keyboard Functions (common.py)

```python
get_complexity_confirm_keyboard(tier, cost, show_turnkey, phase_button_label)
# For long_answer / turnkey confirmation. Buttons:
#   [Готовое решение «Уход под ключ»] (optional)
#   [{phase_button_label} (N вопроса)]
#   [Отмена]

get_phase_eligible_keyboard(phase_button_label, phase_cost)
# For phase_eligible=True short questions. 3 buttons:
#   [Краткий ответ (1 вопрос)]
#   [{phase_button_label} (2 вопроса)]
#   [Готовое решение «Уход под ключ»]

get_next_phase_keyboard(next_phase_display)
# After delivering a phase. Button:
#   [Следующая фаза: {display_name}]

get_phase_select_keyboard(phases)
# Select which phase to start from (Тип C full-season flow)

get_topic_select_keyboard(topics)
# For multi-topic questions: pick one topic to address
```

---

## Callback Handlers (entry.py)

| Callback Data | Action |
|--------------|--------|
| `complexity_confirm:short` | Proceed with short_answer flow (1 token) |
| `complexity_confirm:long` | Proceed with long_answer flow (2 tokens, phase plan) |
| `complexity_confirm:turnkey_info` | Show turnkey product information |
| `complexity_confirm:cancel` | Cancel, return to menu |
| `phase_continue:{phase_key}` | Deliver next seasonal phase |
| `topic_select:{topic}` | Select one topic from multi-topic question |

---

## State Machine States

```
waiting_complexity_confirm   — shown confirm keyboard for long_answer
waiting_phase_eligible       — shown phase choice keyboard for phase_eligible
waiting_topic_select         — shown topic selection for multi-topic
waiting_phase_continue       — delivered phase, offering next
waiting_followup             — normal follow-up state
```

Stored in: `CONSULTATION_STATE[telegram_user_id]`
Context stored in: `CONSULTATION_CONTEXT[telegram_user_id]`

---

## Context Keys (CONSULTATION_CONTEXT)

When routing to complexity flow, these keys are saved:

```python
{
    "_pending_complexity": True,          # flag: awaiting user confirmation
    "_pending_topic_select": True,        # flag: awaiting topic selection
    "_phase_continuation": True,          # flag: in phase delivery sequence
    "complexity_result": ComplexityResult,
    "tier": "long_answer",
    "question_text": str,
    "question_msg_id": int,               # messages.id of user's question
    "internal_user_id": int,
    "category": str,
    "culture": str,
    "phase_mode": "single_phase" | "seasonal_phase",
    "phase_key": "весна-цветение",
    "phase_topic": "питание",
    "phase_number": 1,
    "current_phase": str,
    "next_phase": str | None,
    "phases_delivered": [str],
    "is_last_phase": bool,
}
```

---

## Database Storage

After consultation, these fields are written to `consultation_logs`:

```sql
-- From schema_48
complexity_tier VARCHAR(50)           -- 'short_answer' | 'long_answer' | 'turnkey_solution'
complexity_metadata JSONB             -- {current_phase, next_phase, topics, total_phases, multi_topic}
complexity_classification_cost_usd NUMERIC(10,6)
complexity_classification_tokens INTEGER

-- From schema_49
phase_mode VARCHAR(20)                -- 'single_phase' | 'seasonal_phase' | NULL
phase_key VARCHAR(50)                 -- 'весна-цветение' | 'цветение-плодоношение' | 'плодоношение-зима'
phase_number INTEGER                  -- 1, 2, 3 for Тип C
```

---

## Admin Panel Display

**TopicView.tsx:** Shows complexity block per consultation log:
- Tier label (Краткий ответ / План на фазу / Готовое решение)
- Token cost
- Phase info (current, next)
- Complexity classification cost in USD

**ActivityItem.tsx:** chat_message events show as conversation bubbles with keyboard rendering.

---

## Edge Cases & Risks

1. **LLM hallucination in classification:** Classifier may misclassify. Prompt instructs to default to `short_answer` to prevent over-charging. Monitor via admin panel analytics.

2. **Multi-topic detection:** If `len(topics) > 1`, system asks user to pick one topic. This adds UX friction — may be relaxed later.

3. **Phase context in LLM prompt:** `consultation_llm.py` must use `phase_mode`/`phase_key`/`phase_topic` kwargs to inject phase context. Verify implementation.

4. **Feature flag rollback:** Set `FEATURE_COMPLEXITY_ENABLED=false` in `.env` to disable complexity flow entirely and fall back to flat 1-token pricing.

---

## TODO / Next Steps

- [ ] Apply schema_48 and schema_49 to production database
- [ ] Verify `complexity_confirm:long` callback handler delivers phase plan correctly
- [ ] Test phase context injection in `consultation_llm.py` (phase prompt composition)
- [ ] Verify `get_user_chat_history()` function exists in messages_repo.py
- [ ] Monitor complexity classification accuracy via admin panel logs
- [ ] Consider caching complexity result per question to avoid re-classification on retry
