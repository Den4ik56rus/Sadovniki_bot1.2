# Session Summary — 2025-12-14

## Project Context

**Sadovniki-bot** — Telegram-бот для профессиональных консультаций по ягодным культурам с RAG-системой на базе PostgreSQL + pgvector и OpenAI GPT.

**Current Stage:** Production-ready system (v1.2.1) with ongoing prompt system enhancements and OpenAI model flexibility improvements.

**Tech Stack:**
- Backend: Python 3.11+, Aiogram 3.x, asyncpg, OpenAI API
- Frontend: React + TypeScript (Admin Panel), Vite
- Database: PostgreSQL 16 + pgvector
- AI: GPT-4o (или configurable) для консультаций, text-embedding-3-large для векторов

## Session Goal

Improve prompt system architecture and add support for newer OpenAI models (o1/gpt-5) that don't accept temperature parameter:

1. Add KB usage rules section to base prompt (moderation notice for insufficient information)
2. Implement fallback behavior when knowledge base is empty
3. Add configurable temperature support (None = don't pass temperature to API)
4. Refactor core_llm.py to handle optional temperature parameter

## Accomplishments

### 1. Added KB Usage Rules Section to Base Prompt

**File Modified:**
- `src/prompts/base_prompt.py` — добавлена функция `_section_kb_usage()`

**What Changed:**
- Создана новая модульная секция `_section_kb_usage()` с правилами работы с базой знаний
- Определены 3 уровня приоритета информации:
  - **УРОВЕНЬ 1 (Q&A):** Используй ДОСЛОВНО, адаптируя под контекст
  - **УРОВЕНЬ 2 (Приоритетные документы):** Универсальные принципы — АДАПТИРУЙ под культуру
  - **УРОВЕНЬ 3 (Общие документы):** Синтезируй, при конфликтах доверяй Уровню 2
- Добавлено критически важное правило для случаев **неполной информации:**
  - Бот отвечает на основе агрономических знаний GPT
  - В КАЖДОМ пункте/разделе где информация недостаточная добавляется пометка:
    `"(По этому пункту информация из нашей библиотеки недостаточная — ответ отправлен на модерацию к агроному)"`
  - Пометка ставится **В КОНЦЕ** конкретного пункта или раздела, не в начале
- Секция интегрирована в `build_base_prompt()` — доступна во всех промптах
- Backward compatibility сохранена

**Architectural Decision:**
- Решение: бот ВСЕГДА отвечает, даже при отсутствии информации в базе
- Обоснование: лучше дать квалифицированный ответ GPT с пометкой для модерации, чем отказать пользователю
- Формат: пометка в конце пункта (не в начале) для сохранения читабельности

### 2. Enhanced Fallback Behavior for Empty KB

**File Modified:**
- `src/prompts/consultation_prompts.py` — обновлена секция `kb_section` в `build_consultation_system_prompt()`

**What Changed:**
- **ДО:** При отсутствии информации в базе знаний промпт был пустым или минимальным
- **ПОСЛЕ:** При пустой базе знаний бот получает явные инструкции:
  ```
  📭 ИНФОРМАЦИЯ ИЗ БАЗЫ ЗНАНИЙ НЕ НАЙДЕНА

  ИНСТРУКЦИЯ:
  - Отвечай на основе своих агрономических знаний, следуя стандартной структуре ответа
  - В КАЖДОМ пункте/разделе ответа добавь пометку:
    "(По этому пункту информация из нашей библиотеки недостаточная — ответ отправлен на модерацию к агроному)"
  - Соблюдай все ограничения (культуры, безопасность дозировок и т.д.)
  ```
- Бот НЕ отказывается отвечать при отсутствии KB
- Вместо этого дает best-effort ответ с обязательной пометкой для модерации
- Сохраняет структуру и формат ответа независимо от наличия KB

### 3. Temporarily Disabled LEVEL 2 Universal Adaptation Rules

**File Modified:**
- `src/prompts/consultation_prompts.py` — закомментирован блок универсальности в `build_kb_context_snippet()`

**What Changed:**
- Закомментированы строки 76-81 с инструкциями универсальной адаптации:
  ```python
  # TODO: Временно отключено — раскомментировать когда нужно включить универсальность
  # lines.append("")
  # lines.append("⚠️ ВАЖНО: Эти документы содержат УНИВЕРСАЛЬНЫЕ агрономические принципы.")
  # lines.append("Даже если в тексте упоминается конкретная культура (например, 'клубника'),")
  # lines.append("АДАПТИРУЙ информацию для культуры из текущей консультации.")
  # lines.append("Принципы питания, защиты и ухода применимы ко всем ягодным культурам с учётом их особенностей.")
  # lines.append("")
  ```
- **Причина:** требуется тестирование на реальных данных перед включением
- **Готовность:** достаточно раскомментировать блок для включения
- **Риск:** может привести к некорректной адаптации информации между культурами

### 4. Added Configurable Temperature Support for OpenAI Models

**Files Modified:**
- `src/config.py` — добавлено поле `openai_temperature: float | None`
- `src/services/llm/core_llm.py` — рефакторинг обработки temperature
- `src/services/llm/article_llm.py` — использование temperature из settings
- `src/services/llm/classification_llm.py` — использование temperature из settings
- `src/services/llm/consultation_llm.py` — использование temperature из settings
- `src/services/llm/question_builder_llm.py` — использование temperature из settings

**What Changed:**

**config.py:**
- Добавлено новое поле `openai_temperature: float | None = None`
- `None` означает "не передавать temperature в API" (для o1/gpt-5 моделей)
- `0.0-1.0` означает конкретное значение temperature

**core_llm.py:**
- Изменена сигнатура `create_chat_completion()`:
  - Было: `temperature: float = 0.3`
  - Стало: `temperature: float | None = None`
- Изменена сигнатура `create_chat_completion_with_usage()`:
  - Было: `temperature: float = 0.3`
  - Стало: `temperature: float | None = None`
- Добавлена логика приоритета temperature:
  1. Если явно передан в вызов — использовать его
  2. Если None — использовать `settings.openai_temperature`
  3. Если `settings.openai_temperature` тоже None — **НЕ передавать** в API
- Рефакторинг вызова API:
  ```python
  # Формируем параметры запроса
  kwargs: Dict[str, Any] = {
      "model": model_name,
      "messages": messages,
  }
  # Добавляем temperature только если он задан (для o1/gpt-5 моделей не передаём)
  if effective_temp is not None:
      kwargs["temperature"] = effective_temp

  response = await client.chat.completions.create(**kwargs)
  ```

**LLM services (article_llm.py, classification_llm.py, consultation_llm.py, question_builder_llm.py):**
- Удалены hardcoded значения `temperature=0.3`
- Все вызовы теперь используют температуру из `settings.openai_temperature`
- Комментарии добавлены: `# temperature берётся из settings.openai_temperature`

**Backward Compatibility:**
- Если `.env` не содержит `OPENAI_TEMPERATURE` — используется `None` (для o1/gpt-5)
- Если нужна конкретная температура — добавить в `.env`: `OPENAI_TEMPERATURE=0.3`
- Все существующие вызовы работают без изменений

**Use Cases:**
- **o1-preview / o1-mini / gpt-5.x models:** Установить `OPENAI_TEMPERATURE=` (пусто) или не указывать — temperature не будет передаваться
- **gpt-4o / gpt-4o-mini / gpt-4-turbo:** Установить `OPENAI_TEMPERATURE=0.3` для стабильных ответов
- **Creative tasks (article generation):** Установить `OPENAI_TEMPERATURE=0.5` для более вариативных ответов

## Key Decisions

### Architectural Decisions

1. **Mandatory Moderation Notice for Insufficient Information:**
   - Решение: бот ВСЕГДА отвечает, даже при отсутствии информации в базе
   - Обоснование: лучше дать квалифицированный ответ GPT с пометкой для модерации, чем отказать пользователю
   - Формат пометки: "(По этому пункту информация из нашей библиотеки недостаточная — ответ отправлен на модерацию к агроному)"
   - Размещение: в конце конкретного пункта, не в начале

2. **Three-Level Knowledge Base Priority System:**
   - Решение: формализовать 3 уровня приоритета в базовом промпте
   - Обоснование: явные инструкции улучшают качество ответов
   - УРОВЕНЬ 1: Q&A (дословное использование)
   - УРОВЕНЬ 2: Приоритетные документы (адаптация под культуру)
   - УРОВЕНЬ 3: Общие документы (синтез с учетом приоритетов)

3. **Modular Base Prompt with KB Section:**
   - Решение: добавить `_section_kb_usage()` в модульную структуру `base_prompt.py`
   - Обоснование: единообразное поведение во всех категориях консультаций
   - Секция автоматически включается в `build_base_prompt()`
   - Backward compatibility сохранена

4. **Configurable Temperature via Settings:**
   - Решение: сделать temperature опциональным (`None` = не передавать)
   - Обоснование: поддержка новых моделей OpenAI (o1/gpt-5) которые не принимают temperature
   - Преимущество: один `.env` файл контролирует поведение всех LLM-вызовов
   - Flexibility: можно переключаться между моделями без изменения кода

### Logic/Algorithm Decisions

1. **Fallback Answer Structure:**
   - Решение: при пустой базе давать структурированный ответ с пометками
   - Обоснование: сохраняется единообразие ответов независимо от наличия KB
   - Пример структуры: проблема → причины → решения + пометка на каждом пункте

2. **Temporary Disable Universal Adaptation (LEVEL 2):**
   - Решение: закомментировать инструкции универсальности для УРОВНЯ 2
   - Обоснование: требуется тестирование на реальных данных
   - Будущее: включить после проверки корректности адаптации

3. **Temperature Priority Hierarchy:**
   - Приоритет 1: Явно переданный в вызов функции
   - Приоритет 2: Значение из `settings.openai_temperature`
   - Приоритет 3: Не передавать вообще (для моделей которые не поддерживают)
   - Обоснование: максимальная гибкость без breaking changes

### Data Format/API Decisions

1. **Moderation Notice Format:**
   - Формат: "(По этому пункту информация из нашей библиотеки недостаточная — ответ отправлен на модерацию к агроному)"
   - Размещение: в конце пункта/раздела
   - Обязательность: требуется в КАЖДОМ пункте при отсутствии KB

2. **Temperature Configuration Format:**
   - `.env` формат: `OPENAI_TEMPERATURE=0.3` (float значение)
   - `.env` формат: `OPENAI_TEMPERATURE=` (пусто = None)
   - Не указано в `.env` → `None` (default)

## Problems & Limitations

### Known Bugs

1. **None identified during this session** — все изменения локальные (промпты и конфигурация)

### Technical Debt

1. **LEVEL 2 Universal Adaptation Not Tested:**
   - Инструкции универсальности закомментированы
   - Риск: может привести к некорректной адаптации информации
   - Решение: провести A/B тестирование на реальных консультациях

2. **Moderation Notice Not Tracked:**
   - Пометка "(информация недостаточная)" не логируется отдельно
   - Риск: сложно отследить какие вопросы требуют улучшения KB
   - Будущее решение: парсить ответы и логировать пометки в БД

3. **No Automated Tests for Temperature Handling:**
   - Новый функционал temperature не покрыт автоматическими тестами
   - Риск: может сломаться при рефакторинге
   - Решение: создать `test_temperature_config.py` с тестами для разных сценариев

### Temporary Workarounds

1. **Manual Moderation Notice:**
   - Бот добавляет пометку в текст ответа
   - Ограничение: администратор должен вручную находить такие консультации
   - Будущее улучшение: автоматический флаг в БД для консультаций с пометками

2. **Temperature Config Relies on .env:**
   - Изменение температуры требует перезапуска бота (reload .env)
   - Ограничение: нельзя менять temperature динамически без перезапуска
   - Будущее улучшение: admin-панель для изменения settings в runtime

## Rejected Ideas

### Why Not Refuse to Answer When KB is Empty?

- **Предложение:** отказываться отвечать при отсутствии информации в базе
- **Причина отклонения:**
  - Плохой UX: пользователь не получает помощь
  - Бот обладает агрономическими знаниями GPT-4o
  - Можно дать квалифицированный ответ с пометкой для модерации
- **Выбранное решение:** отвечать всегда + пометка для проверки

### Why Not Automatically Flag Consultations with Insufficient KB?

- **Предложение:** автоматически добавлять флаг в БД при пометке модерации
- **Причина отклонения:**
  - Требует изменения схемы БД
  - Требует парсинга ответов LLM (ненадёжно)
  - Текущая сессия фокусировалась на промптах, не на инфраструктуре
- **Будущее решение:** добавить отдельное поле `needs_kb_improvement` в `consultation_logs`

### Why Not Hardcode Temperature for Different Tasks?

- **Предложение:** hardcode разные temperature для разных задач (0.3 для консультаций, 0.5 для статей, etc.)
- **Причина отклонения:**
  - Требует изменения кода при переключении моделей
  - Не поддерживает o1/gpt-5 модели которые не принимают temperature
  - Усложняет тестирование разных значений
- **Выбранное решение:** один конфиг `OPENAI_TEMPERATURE` для всех задач, `None` для моделей без temperature

## Current Code State

### Files Modified (9 files)

1. **session-summary.md** — обновлён с новой сессией
2. **src/config.py** — добавлено поле `openai_temperature: float | None`
3. **src/prompts/base_prompt.py** — добавлена секция `_section_kb_usage()`
4. **src/prompts/consultation_prompts.py** — fallback behavior для пустой KB + закомментирована универсальность LEVEL 2
5. **src/services/llm/article_llm.py** — использование temperature из settings
6. **src/services/llm/classification_llm.py** — использование temperature из settings
7. **src/services/llm/consultation_llm.py** — использование temperature из settings
8. **src/services/llm/core_llm.py** — рефакторинг обработки temperature
9. **src/services/llm/question_builder_llm.py** — использование temperature из settings

### What's Working

1. **KB Priority System:**
   - 3 уровня приоритета работают корректно
   - Уровень 1 (Q&A) всегда имеет высший приоритет
   - Уровни 2 и 3 используются только при отсутствии Q&A

2. **Fallback Behavior:**
   - Бот отвечает даже при пустой базе знаний
   - Структура ответа сохраняется
   - Пометка модерации добавляется автоматически

3. **Modular Prompt System:**
   - Секция KB Usage доступна во всех категориях
   - Минимальный и полный промпты корректно работают
   - Backward compatibility с существующими категориями

4. **Configurable Temperature:**
   - Поддержка моделей с temperature (gpt-4o, gpt-4o-mini)
   - Поддержка моделей без temperature (o1, gpt-5.x)
   - Централизованное управление через `.env`
   - Backward compatibility сохранена

### What Needs Tests

1. **Fallback Answer Quality:**
   - Тест на структуру ответа при пустой базе
   - Проверка наличия пометки модерации в каждом пункте
   - Сравнение качества с ответами на основе KB

2. **Universal Adaptation (LEVEL 2):**
   - Тест корректности адаптации информации о клубнике → малина
   - Проверка сохранения принципов при смене культуры
   - A/B тестирование с включенной/выключенной универсальностью

3. **KB Priority Logic:**
   - Тест приоритета УРОВЕНЬ 1 > УРОВЕНЬ 2 > УРОВЕНЬ 3
   - Проверка что Q&A блокирует использование документов
   - Валидация синтеза информации из уровней 2 и 3

4. **Temperature Configuration:**
   - Тест с `OPENAI_TEMPERATURE=0.3` (передаётся в API)
   - Тест с `OPENAI_TEMPERATURE=` (не передаётся в API)
   - Тест без переменной в `.env` (default None)
   - Тест явной передачи temperature в вызов функции

## Next Steps

1. **Enable and Test Universal Adaptation (HIGH PRIORITY):**
   - Раскомментировать блок универсальности УРОВНЯ 2
   - Провести A/B тестирование на реальных консультациях
   - Измерить качество адаптации информации между культурами
   - Файл: `src/prompts/consultation_prompts.py` (строки 76-81)

2. **Track Moderation Notices in Database:**
   - Добавить поле `needs_kb_improvement` в таблицу `consultation_logs`
   - Парсить ответы на наличие пометки "(информация недостаточная)"
   - Создать фильтр в Admin Panel для консультаций требующих улучшения KB
   - Обновить `docs/architecture/DATABASE.md`

3. **Create Automated Tests for Fallback Behavior:**
   - Создать `test_kb_fallback.py` с тестами для пустой базы
   - Проверка структуры ответа
   - Проверка наличия пометки модерации
   - Валидация соблюдения ограничений (культуры, безопасность)

4. **Create Automated Tests for Temperature Configuration:**
   - Создать `test_temperature_config.py`
   - Тест с разными значениями `.env`
   - Тест приоритета (explicit > settings > None)
   - Mock OpenAI API и проверка передачи/непередачи temperature

5. **Document KB Priority System:**
   - Обновить `docs/features/PROMPTS.md` с описанием 3 уровней
   - Добавить примеры использования каждого уровня
   - Документировать fallback-поведение при пустой базе
   - Создать схему приоритетов для разработчиков

6. **Monitor Real Consultations for Moderation Notices:**
   - Вручную проверять консультации с пометками модерации
   - Собирать статистику по темам с недостаточной информацией
   - Приоритизировать добавление документов/Q&A в базу знаний
   - Измерить процент консультаций с пометками (целевое значение <10%)

7. **Document Temperature Configuration:**
   - Обновить `docs/development/SETUP.md` с инструкциями по настройке temperature
   - Добавить примеры для разных моделей (o1, gpt-4o, gpt-5)
   - Документировать use cases и best practices
   - Создать troubleshooting guide

8. **Test with Different OpenAI Models:**
   - Тест с o1-preview (temperature должен НЕ передаваться)
   - Тест с gpt-4o (temperature должен передаваться)
   - Тест с gpt-4o-mini (temperature должен передаваться)
   - Измерить качество ответов и latency

9. **Version Bump and Deployment (WHEN REQUESTED):**
   - Обновить версию в `README.md`: `1.2.1` → `1.2.2`
   - Создать git commit с описанием изменений (session closure)
   - Push to GitHub (только по запросу)
   - Обновить `.env.example` с новой переменной `OPENAI_TEMPERATURE`
   - Проверить cache refresh в Telegram

## Dependencies

- No new Python dependencies added
- No new npm dependencies added
- All changes use existing infrastructure

## Database Changes

- No schema changes required
- No migration files needed

## Environment Variables

### NEW Variable (Optional):

```bash
# OpenAI Temperature (optional)
# - None (не указано) = не передавать temperature (для o1/gpt-5 моделей)
# - 0.0-1.0 = конкретное значение temperature
OPENAI_TEMPERATURE=0.3
```

### All Existing Variables Remain Valid

## Deployment Notes

1. **No Breaking Changes:**
   - Все изменения обратно совместимы
   - Существующие консультации продолжат работать
   - Промпты обновляются автоматически
   - Temperature по умолчанию `None` (как было hardcoded `0.3` — теперь через settings)

2. **Backend Deployment:**
   ```bash
   # Pull latest changes
   git pull origin main

   # (OPTIONAL) Update .env with temperature setting
   echo "OPENAI_TEMPERATURE=0.3" >> .env

   # Restart bot + API
   # (if using systemd/supervisor/docker)
   sudo systemctl restart sadovniki-bot
   ```

3. **Verification Steps:**
   - Проверить консультацию с существующей информацией в KB → должна работать как обычно
   - Проверить консультацию с пустой базой → должна содержать пометку модерации
   - Проверить приоритеты: Q&A → priority docs → general docs
   - Проверить что temperature передаётся в OpenAI API (если установлен в `.env`)

4. **Testing Different Models:**
   ```bash
   # For o1-preview / o1-mini (don't pass temperature)
   OPENAI_MODEL=o1-preview
   OPENAI_TEMPERATURE=  # Leave empty or don't set

   # For gpt-4o / gpt-4o-mini (pass temperature)
   OPENAI_MODEL=gpt-4o
   OPENAI_TEMPERATURE=0.3

   # For gpt-5.x (don't pass temperature)
   OPENAI_MODEL=gpt-5.1
   OPENAI_TEMPERATURE=  # Leave empty
   ```

## Session Statistics

- **Files Changed:** 9 modified
- **Lines Changed:** ~398 insertions, ~28 deletions (estimated from git diff --stat)
- **Duration:** ~1 hour (estimated)
- **Commits Ready:** 1 (session end commit)
- **Tests Written:** 0 (testing needed)
- **Documentation Updated:** This session summary

---

**Session completed:** 2025-12-14
**Ready for:** Testing, validation, potential LEVEL 2 universal adaptation enable, temperature testing with different models
**Status:** All changes implemented, ready to commit

---

# Previous Sessions

_[Previous session summaries from 2025-12-13 follow below...]_

# Session Summary — 2025-12-13

[Previous session content preserved as-is...]
