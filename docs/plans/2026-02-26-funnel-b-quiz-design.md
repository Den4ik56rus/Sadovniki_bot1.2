# Funnel B: Quiz Onboarding Flow — Design

**Date:** 2026-02-26
**Status:** Approved

## Context

Тип Б воронки (funnel_b.py) сейчас содержит 23-строчную заглушку с базовым приветствием. Нужно реализовать полный онбординг-квиз: 3 вопроса с кнопками → персонализированный оффер → CTA на оплату или бесплатную консультацию. Цель — повысить конверсию за счёт вовлечения пользователя перед предложением платного плана.

---

## User Flow

```
/start (новый пользователь тип Б)
│
├─ Msg 1: Приветствие ("Рад, что Вы присоединились!...")
│
├─ Msg 2 (Квиз 1): "🌱 Выращиваешь ягоды на даче?..."
│   └─ InlineKeyboard: 6 культур (сетка 2×3) + 1 "Другая"
│
├─ callback quiz_culture_{value} → сохр. в БД
│   Msg 3 (Квиз 2): "Отлично. В каком регионе выращиваешь?"
│   └─ InlineKeyboard: средняя полоса / юг / север / указать свой
│
├─ callback quiz_region_{value} → сохр. в БД
│   (если "указать свой" — ждём текстовый ввод региона)
│   Msg 4 (Квиз 3): "Что сейчас больше всего волнует?"
│   └─ InlineKeyboard: 5 проблем
│
├─ callback quiz_problem_{value} → сохр. в БД
│   Msg 5: "По твоему региону чаще всего теряют до 25–40%..."
│   Msg 6 (сразу): "Обычно такой план стоит 1990 ₽. Сегодня — 990 ₽..."
│   └─ InlineKeyboard:
│       ├─ 🔥 Получить персональный план → show_payment_menu()
│       └─ Получить бесплатную консультацию → consultation flow
```

**Повторный /start:**
- Если `user_quiz_answers` запись есть → показать `get_main_keyboard()` (стандартное меню)
- Если нет (квиз в процессе или не начат) → запустить квиз с начала

---

## Тексты сообщений

**Msg 1 (приветствие):**
```
Рад, что Вы присоединились! Я Ваш агроном!🙏

Следуй моему плану - и урожай будет на 30% больше.
Или вернем деньги

В моей базе знаний огромное количество профильной литературы, но главное — в меня заложен практический опыт ягодных хозяйств.

Со мной у Вас будут богатые урожаи при минимуме ухода!
```

**Msg 2 (квиз 1 — культура):**
```
🌱 Выращиваешь ягоды на даче?
80% дачников теряют часть урожая из-за 3 типичных ошибок.
Давай проверим, всё ли у Вас в порядке. Это займёт 1 минуту.
Какая культура у Вас преобладает?
```
Кнопки (2+2+2+1):
```
[🍓 Клубника   ] [🍇 Малина    ]
[🫐 Голубика   ] [🌿 Смородина ]
[Жимолость     ] [Ежевика      ]
[👉 Другая культура            ]
```

**Msg 3 (квиз 2 — регион):**
```
Отлично. В каком регионе выращиваешь?
```
Кнопки (2+2):
```
[Средняя полоса] [Юг           ]
[Север         ] [Указать свой  ]
```

**Msg 4 (квиз 3 — проблема):**
```
Что сейчас больше всего волнует?
```
Кнопки (вертикально по 1):
```
[Мелкие ягоды          ]
[Болезни               ]
[Мало урожая           ]
[Хочу увеличить урожай ]
[Просто проверить уход ]
```

**Msg 5 (оффер — часть 1):**
```
По твоему региону чаще всего теряют до 25–40% урожая из-за:
1️⃣ Неправильной схемы подкормки
2️⃣ Ошибок в поливе
3️⃣ Поздней защиты от грибка
Я могу составить для тебя персональный план ухода до конца сезона с точными дозировками и сроками.
```

**Msg 6 (оффер — часть 2, сразу после Msg 5):**
```
Обычно такой план стоит 1990 ₽.
Сегодня - 990 ₽.
Если будешь следовать рекомендациям и не увидишь разницы в урожае — вернём деньги.
```
Кнопки:
```
[🔥 Получить персональный план]
[Получить бесплатную консультацию]
```

---

## Архитектура

### Файлы для изменения

| Файл | Изменение |
|------|-----------|
| `src/handlers/funnel_b.py` | Полная переработка — вся логика квиза |
| `db/schema_82_quiz_answers.sql` | Новый файл — таблица `user_quiz_answers` |

### Новая таблица

```sql
-- db/schema_82_quiz_answers.sql
CREATE TABLE IF NOT EXISTS user_quiz_answers (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    culture TEXT,
    region TEXT,
    problem TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id)
);
```

### State management

Используем существующий механизм (`CONSULTATION_STATE` / `CONSULTATION_CONTEXT` из `src/handlers/common.py`):

| State key | Смысл |
|-----------|-------|
| `"quiz_awaiting_culture"` | Ждём выбор культуры |
| `"quiz_awaiting_region"` | Ждём выбор региона |
| `"quiz_awaiting_region_text"` | Ждём текстовый ввод региона |
| `"quiz_awaiting_problem"` | Ждём выбор проблемы |

### Callback data схема

```
quiz_culture_strawberry
quiz_culture_raspberry
quiz_culture_blueberry
quiz_culture_currant
quiz_culture_honeysuckle
quiz_culture_blackberry
quiz_culture_other
quiz_region_central
quiz_region_south
quiz_region_north
quiz_region_custom
quiz_problem_small_berries
quiz_problem_diseases
quiz_problem_low_yield
quiz_problem_increase_yield
quiz_problem_check_care
```

### Handlers в funnel_b.py

```python
# Точка входа (вызывается из menu.py)
async def start_funnel_b(message, user_id) -> None

# Callback handlers (регистрируются в router)
async def handle_quiz_culture(callback, user_id) -> None
async def handle_quiz_region(callback, user_id) -> None
async def handle_quiz_region_text(message) -> None  # для "указать свой"
async def handle_quiz_problem(callback, user_id) -> None

# Вспомогательные функции
async def _save_quiz_answer(user_id, field, value) -> None
async def _show_offer(message_or_callback) -> None
async def _quiz_already_done(user_id) -> bool  # проверка наличия в user_quiz_answers
```

### Интеграция с menu.py (start handler)

В `cmd_start()` (`src/handlers/menu.py`) уже есть проверка `is_new_user`. Нужно добавить:
```python
if active_variant == 'B':
    quiz_done = await _quiz_already_done(internal_user_id)
    if quiz_done:
        await message.answer("...", reply_markup=get_main_keyboard())
        return
    await start_funnel_b(message, user_id)
    return
```

### Финальные CTA handlers

- `quiz_cta_payment` → вызвать `show_payment_menu()` из `src/handlers/payments/menu.py`
- `quiz_cta_consultation` → выполнить логику из `handle_consultation_button()` (закрыть топики, выставить состояние, отправить приветствие консультации)

---

## Verification

1. Применить `schema_82_quiz_answers.sql` на локальной БД
2. Установить `active_funnel_variant = 'B'` через API или DB
3. Написать `/start` как новый пользователь → проверить Msg 1 + Msg 2 с кнопками
4. Пройти все 3 шага квиза → убедиться что Msg 5 + Msg 6 с CTA появляются
5. Нажать "🔥 Получить персональный план" → убедиться что открывается payment menu
6. Нажать "Получить бесплатную консультацию" → убедиться что открывается consultation flow
7. Написать `/start` повторно → убедиться что показывается `get_main_keyboard()`
8. Проверить в БД: `SELECT * FROM user_quiz_answers WHERE user_id = <id>` — данные должны быть сохранены
