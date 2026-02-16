# Тестовый чеклист перед запуском

**Версия:** 1.2.2
**Дата:** 2026-02-15

---

## 🔧 Предварительная подготовка

### 1. Окружение

```bash
# 1. Проверить версию Python
python --version  # Должно быть >= 3.11

# 2. Активировать виртуальное окружение
cd /Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2
source venv/bin/activate

# 3. Проверить зависимости
pip list | grep -E "aiogram|asyncpg|openai|yookassa"
```

**Ожидаемый вывод:**
```
aiogram           3.x.x
asyncpg           0.x.x
openai            1.x.x
yookassa          2.x.x
```

---

### 2. База данных

```bash
# 1. Проверить подключение к PostgreSQL
psql -h localhost -U bot_user -d garden_bot -c "SELECT version();"

# 2. Применить отсутствующие миграции
cd db
for schema in schema_37_documents_full_text.sql \
              schema_38_embedding_nullable.sql \
              schema_39_admin_settings.sql \
              schema_40_culture_rules_split.sql \
              schema_41_category_prompts_migration.sql \
              schema_42_llm_settings.sql \
              schema_44_trial_questions.sql \
              schema_45_pricing_update.sql \
              schema_46_referrals.sql; do
    echo "Применяю $schema..."
    psql -h localhost -U bot_user -d garden_bot -f "$schema"
done

# 3. Верификация
psql -h localhost -U bot_user -d garden_bot <<EOF
-- Проверить существование таблиц
\dt referrals
\dt admin_settings
\dt subscription_plans

-- Проверить триальные вопросы
SELECT * FROM admin_settings WHERE key LIKE 'trial%';

-- Проверить планы подписок
SELECT id, name, price_rub, tokens_included FROM subscription_plans WHERE is_active = true;

-- Проверить пакеты токенов
SELECT id, name, price_rub, tokens_amount FROM token_packages WHERE is_active = true;
EOF
```

**Ожидаемый результат:**
- Таблица `referrals` существует
- Таблица `admin_settings` содержит запись `trial_questions_count` = 3
- Есть минимум 1 активный план подписки
- Есть минимум 1 активный пакет токенов

---

### 3. Конфигурация (.env)

```bash
# Проверить критичные переменные
grep -E "OPENAI_MODEL|YOOKASSA|DB_" .env
```

**Проверить:**
- [ ] `OPENAI_MODEL_CONSULTATION` = корректное название модели (gpt-4o, gpt-4o-mini)
- [ ] `OPENAI_MODEL_CLASSIFICATION` = корректное название модели
- [ ] `OPENAI_API_KEY` заполнен
- [ ] `YOOKASSA_SHOP_ID` заполнен
- [ ] `YOOKASSA_SECRET_KEY` заполнен (test_ или live_)
- [ ] `YOOKASSA_WEBHOOK_URL` корректен и доступен
- [ ] `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` заполнены

**⚠️ КРИТИЧНО:** Исправить названия моделей OpenAI!

```bash
# Заменить некорректные названия (если есть gpt-5-mini или gpt-4.1-mini)
sed -i '' 's/gpt-5-mini/gpt-4o-mini/g' .env
sed -i '' 's/gpt-4.1-mini/gpt-4o-mini/g' .env
```

---

### 4. Запуск сервисов

**Terminal 1: Backend + Bot**
```bash
cd /Users/denis/Desktop/Main/Sadovniki-bot/Sadovniki_bot1.2
source venv/bin/activate
python -m src
```

**Ожидаемый вывод:**
```
INFO - Bot started successfully
INFO - API server listening on 0.0.0.0:8080
INFO - PostgreSQL pool created
INFO - Admin IDs: [833371989, 5208832236]
```

**Terminal 2: Ngrok (для webhook)**
```bash
ngrok http 8080
```

**Скопировать HTTPS URL из вывода ngrok:**
```
Forwarding  https://xxxx-xxxx-xxxx.ngrok-free.app -> http://localhost:8080
```

**Обновить .env:**
```bash
# Заменить URL (используйте скопированный URL из ngrok)
sed -i '' 's|YOOKASSA_WEBHOOK_URL=.*|YOOKASSA_WEBHOOK_URL=https://xxxx-xxxx-xxxx.ngrok-free.app/api/webhooks/yookassa|' .env
```

**Перезапустить backend** (Ctrl+C в Terminal 1, затем снова `python -m src`)

**Terminal 3: Admin Panel (опционально)**
```bash
cd admin-webapp
npm run dev
```

**Открыть:** http://localhost:5174

---

## ✅ Тестовые сценарии

### Тест 1: Новый пользователь + Триальные вопросы

**Цель:** Проверить onboarding нового пользователя

**Подготовка:**
```sql
-- Удалить тестового пользователя (если есть)
psql -h localhost -U bot_user -d garden_bot -c "DELETE FROM users WHERE telegram_user_id = 123456789;"
```

**Шаги:**
1. В Telegram отправить `/start` от нового аккаунта
2. Проверить БД:
   ```sql
   psql -h localhost -U bot_user -d garden_bot <<EOF
   SELECT
       telegram_user_id,
       tokens,
       trial_questions_granted,
       subscription_status,
       created_at
   FROM users
   WHERE telegram_user_id = [ВАШ_TG_ID];
   EOF
   ```

**Ожидаемый результат:**
```
 telegram_user_id | tokens | trial_questions_granted | subscription_status |     created_at
------------------+--------+-------------------------+---------------------+---------------------
        123456789 |      3 | t                       | none                | 2026-02-15 12:00:00
```

**Проверка:**
- [ ] `tokens` = 3 (триальные вопросы начислены)
- [ ] `trial_questions_granted` = true
- [ ] Пользователь создан в БД

3. Отправить консультационный вопрос: "Как подкормить малину?"
4. Проверить уменьшение токенов:
   ```sql
   SELECT tokens FROM users WHERE telegram_user_id = [ВАШ_TG_ID];
   -- Должно быть 2 (3 - 1)
   ```

**Статус:** ⬜ PASS / ⬜ FAIL

**Примечания:** _______________________________________________

---

### Тест 2: Консультации — Уточнение типа культуры

**Цель:** Проверить многоэтапный диалог

**Сценарий 1: Малина общая → Уточнение → Ремонтантная**

1. Отправить: "Как подкормить малину?"
   - **Ожидается:** "Какая у вас малина: летняя (обычная) или ремонтантная?"
2. Ответить: "Ремонтантная"
   - **Ожидается:** Детальный ответ с учетом ремонтантной малины
   - **Проверить:** Есть упоминания специфичных удобрений (Азофоска, Монофосфат калия)
3. Проверить БД:
   ```sql
   SELECT culture FROM topics ORDER BY created_at DESC LIMIT 1;
   -- Должно быть: "малина ремонтантная"
   ```

**Проверка:**
- [ ] Бот задал уточняющий вопрос
- [ ] Ответ содержит RAG-данные (конкретные удобрения из БД)
- [ ] Культура сохранена в топике
- [ ] Ответ отформатирован (жирный текст, списки)

**Статус:** ⬜ PASS / ⬜ FAIL

---

**Сценарий 2: Клубника общая → Летняя**

1. Отправить: "Когда обрезать клубнику?"
   - **Ожидается:** "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
2. Ответить: "Летняя"
   - **Ожидается:** Детальный ответ про обрезку летней клубники

**Проверка:**
- [ ] Уточняющий вопрос задан
- [ ] Ответ специфичен для летней клубники

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 3: Консультации — Конкретная культура

**Цель:** Проверить прямой ответ без уточнений

1. Отправить: "Как ухаживать за голубикой?"
   - **Ожидается:** Сразу детальный ответ (БЕЗ уточняющих вопросов)
   - **Проверить:** Упоминания кислой почвы (pH 4.0-5.5), серосодержащих удобрений

**Проверка:**
- [ ] Бот НЕ задал уточняющих вопросов
- [ ] Ответ содержит специфичную информацию для голубики
- [ ] RAG использован (есть ссылки на документы)

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 4: Консультации — Неопределенная культура

**Цель:** Проверить обработку неясного вопроса

1. Отправить: "Как бороться с вредителями?"
   - **Ожидается:** "Уточните, пожалуйста, о какой культуре идет речь?"
2. Ответить: "Про клубнику"
   - **Ожидается:** "Какая у вас клубника: летняя (июньская) или ремонтантная (НСД)?"
3. Ответить: "Летняя"
   - **Ожидается:** Детальный ответ про вредителей клубники летней

**Проверка:**
- [ ] Первый уточняющий вопрос задан (культура неясна)
- [ ] Второй уточняющий вопрос задан (тип культуры)
- [ ] Финальный ответ учитывает оба уточнения
- [ ] Контекст сохранен между шагами

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 5: Консультации — Followup-вопрос

**Цель:** Проверить сохранение контекста в топике

1. Отправить: "Как ухаживать за малиной ремонтантной?"
   - **Ожидается:** Детальный ответ
2. Через 30 секунд отправить: "А когда лучше поливать?"
   - **Ожидается:** Ответ в контексте малины ремонтантной, БЕЗ запроса культуры
3. Проверить БД:
   ```sql
   SELECT topic_id, direction, text FROM messages
   WHERE session_id = (SELECT session_id FROM topics ORDER BY created_at DESC LIMIT 1)
   ORDER BY created_at;
   ```

**Проверка:**
- [ ] Бот НЕ запросил культуру во втором вопросе
- [ ] Ответ релевантен малине ремонтантной
- [ ] Оба вопроса в одном топике (topic_id одинаковый)

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 6: Покупка подписки (YooKassa)

**Цель:** Проверить полный цикл покупки и активации

**Подготовка:** Убедиться, что ngrok запущен и URL в .env обновлен

**Шаги:**
1. В боте: "💰 Купить вопросы" → "📅 Подписки"
2. Выбрать план (например, "Стандарт 500₽/мес")
3. Нажать "💳 Оплатить" → перейти на страницу YooKassa
4. Оплатить тестовой картой:
   - **Номер:** 4111 1111 1111 1111
   - **Срок:** 12/24
   - **CVC:** 123
5. После оплаты YooKassa должна отправить webhook

**Проверка логов backend:**
```
INFO - Webhook received: event=payment.succeeded, payment_id=..., status=succeeded, paid=True
INFO - Payment ... processed successfully
```

6. Проверить БД:
   ```sql
   SELECT
       p.id,
       p.yookassa_payment_id,
       p.status,
       p.paid,
       p.amount_rub,
       us.status AS subscription_status,
       u.tokens
   FROM payments p
   LEFT JOIN user_subscriptions us ON us.payment_id = p.id
   LEFT JOIN users u ON u.id = p.user_id
   WHERE p.user_id = (SELECT id FROM users WHERE telegram_user_id = [ВАШ_TG_ID])
   ORDER BY p.created_at DESC LIMIT 1;
   ```

**Ожидаемый результат:**
```
 id | yookassa_payment_id | status    | paid | amount_rub | subscription_status | tokens
----+---------------------+-----------+------+------------+---------------------+--------
  1 | 2d1234...           | succeeded | t    | 500.00     | active              | 999
```

7. Отправить консультационный вопрос → проверить, что токены НЕ уменьшаются

**Проверка:**
- [ ] Платеж создан в БД
- [ ] Webhook обработан (логи показывают success)
- [ ] Подписка активирована (`subscription_status` = 'active')
- [ ] Токены начислены (999 или значение из плана)
- [ ] Консультации работают без расхода токенов
- [ ] В Admin Panel → CRM → вкладка "Платежи" виден платеж

**Статус:** ⬜ PASS / ⬜ FAIL

**Примечания:** _______________________________________________

---

### Тест 7: Покупка пакета токенов

**Цель:** Проверить разовую покупку вопросов

**Шаги:**
1. В боте: "💰 Купить вопросы" → "🎁 Разовые пакеты"
2. Выбрать пакет (например, "20 вопросов за 200₽")
3. Оплатить тестовой картой
4. Проверить БД:
   ```sql
   SELECT
       p.payment_type,
       p.token_package_id,
       p.status,
       p.paid,
       u.tokens
   FROM payments p
   JOIN users u ON u.id = p.user_id
   WHERE p.user_id = (SELECT id FROM users WHERE telegram_user_id = [ВАШ_TG_ID])
   ORDER BY p.created_at DESC LIMIT 1;
   ```

**Ожидаемый результат:**
```
 payment_type  | token_package_id | status    | paid | tokens
---------------+------------------+-----------+------+--------
 token_package |                1 | succeeded | t    | 20
```

5. Отправить консультационный вопрос
6. Проверить: `tokens` уменьшился на 1

**Проверка:**
- [ ] Платеж типа `token_package` создан
- [ ] Токены начислены сразу после оплаты
- [ ] Токены расходуются при консультациях
- [ ] Платеж виден в Admin Panel

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 8: Отмена платежа

**Цель:** Проверить обработку отмененного платежа

**Шаги:**
1. Начать создание платежа (подписка или токены)
2. Получить ссылку на оплату YooKassa
3. **НЕ оплачивать** → закрыть страницу
4. Через YooKassa dashboard вручную отменить платеж (или дождаться автоотмены через 15 минут)
5. Проверить БД:
   ```sql
   SELECT status, paid, canceled_at FROM payments
   WHERE yookassa_payment_id = '[PAYMENT_ID]';
   ```

**Ожидаемый результат:**
```
  status  | paid | canceled_at
----------+------+---------------------
 canceled | f    | 2026-02-15 13:00:00
```

**Проверка:**
- [ ] Платеж отменен в БД (`status` = 'canceled')
- [ ] Подписка НЕ активирована
- [ ] Токены НЕ начислены
- [ ] Webhook обработан корректно (логи)

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 9: Реферальная программа (требует доработки)

**⚠️ ВНИМАНИЕ:** Этот тест ПРОЙДЕТ только после доработки кода (см. LAUNCH_READINESS.md)

**Предусловия:**
- [ ] Реализована обработка deeplink в `start.py`
- [ ] Реализовано отображение кода в `profile.py`
- [ ] Реализовано начисление бонусов в `payment_service.py`

**Шаги:**

**Пользователь A (реферер):**
1. Отправить `/start` → бот отвечает
2. Отправить "👤 Профиль" (или аналогичную команду)
3. Проверить: Отображается реферальный код (например, `ABC12345`)
4. Скопировать ссылку: `https://t.me/garden_bot_ai_bot?start=ref_ABC12345`

**Пользователь B (реферал):**
1. Перейти по ссылке из шага 4
2. Бот должен написать: "Вас пригласил [имя A]! Получите +2 вопроса после первой оплаты."
3. Проверить БД:
   ```sql
   SELECT r.referrer_id, r.referee_id, r.referrer_bonus_granted, r.referee_bonus_granted
   FROM referrals r
   WHERE r.referee_id = (SELECT id FROM users WHERE telegram_user_id = [B_TG_ID]);
   ```

**Ожидаемый результат:**
```
 referrer_id | referee_id | referrer_bonus_granted | referee_bonus_granted
-------------+------------+------------------------+----------------------
           1 |          2 | f                      | f
```

4. Пользователь B покупает подписку / токены → оплачивает
5. Webhook обрабатывает платеж → начисляет бонусы

6. Проверить БД:
   ```sql
   -- Проверить tokens
   SELECT u.telegram_user_id, u.tokens
   FROM users u
   WHERE u.id IN (
       SELECT referrer_id FROM referrals WHERE referee_id = (SELECT id FROM users WHERE telegram_user_id = [B_TG_ID])
       UNION
       SELECT referee_id FROM referrals WHERE referee_id = (SELECT id FROM users WHERE telegram_user_id = [B_TG_ID])
   );

   -- Проверить флаги
   SELECT referrer_bonus_granted, referee_bonus_granted
   FROM referrals
   WHERE referee_id = (SELECT id FROM users WHERE telegram_user_id = [B_TG_ID]);
   ```

**Ожидаемый результат:**
```
 telegram_user_id | tokens
------------------+--------
        [A_TG_ID] | [N+3]   # +3 за приглашение
        [B_TG_ID] | [M+2]   # +2 за регистрацию

 referrer_bonus_granted | referee_bonus_granted
------------------------+----------------------
 t                      | t
```

**Проверка:**
- [ ] Реферальная связь создана при переходе по ссылке
- [ ] Бонусы начислены ПОСЛЕ первой оплаты
- [ ] Флаги `*_bonus_granted` = true
- [ ] Пользователь A получил +3 вопроса
- [ ] Пользователь B получил +2 вопроса
- [ ] В Admin Panel CRM видна реферальная информация

**Статус:** ⬜ PASS / ⬜ FAIL / ⬜ NOT IMPLEMENTED

**Примечания:** _______________________________________________

---

### Тест 10: Admin Panel — Live Feed (SSE)

**Цель:** Проверить real-time мониторинг консультаций

**Подготовка:** Открыть Admin Panel: http://localhost:5174

**Шаги:**
1. В Admin Panel перейти на "Live Feed"
2. В Telegram отправить консультационный вопрос: "Как подкормить клубнику?"
3. Проверить: Консультация появилась в Live Feed **в реальном времени** (без обновления страницы)
4. Кликнуть на консультацию → должна открыться детальная view
5. Проверить в детальной view:
   - Вопрос пользователя
   - Ответ бота
   - Метаданные (culture, category, tokens used, cost)
   - RAG snippets (если использовались)

**Проверка:**
- [ ] Консультация появилась без обновления страницы (SSE работает)
- [ ] Индикатор "🟢 Подключено" активен
- [ ] Детальная view показывает полную информацию
- [ ] RAG snippets отображаются (если были использованы)

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 11: Admin Panel — CRM

**Цель:** Проверить карточку клиента и платежи

**Шаги:**
1. В Admin Panel перейти в "CRM"
2. Найти клиента (по имени или ID)
3. Кликнуть на клиента → открылась карточка
4. Проверить вкладки:
   - **Main:** Основная информация, Activity Feed
   - **Консультации:** История вопросов
   - **Платежи:** Транзакции (если были)
5. В Activity Feed проверить наличие событий:
   - Консультации
   - Платежи (pending → succeeded)

**Проверка:**
- [ ] Карточка клиента отображается корректно
- [ ] Все вкладки работают
- [ ] Activity Feed показывает события
- [ ] Платежи отображаются с корректными суммами и статусами

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 12: Превышение лимита токенов

**Цель:** Проверить поведение при нулевом балансе

**Подготовка:**
```sql
-- Обнулить токены пользователя
UPDATE users SET tokens = 0 WHERE telegram_user_id = [ВАШ_TG_ID];
```

**Шаги:**
1. Отправить консультационный вопрос
2. Ожидаемое сообщение: "У вас закончились вопросы. Купите подписку или пакет токенов."
3. Проверить: Кнопки "💰 Купить вопросы" отображаются

**Проверка:**
- [ ] Бот корректно обработал нулевой баланс
- [ ] Уведомление пользователя информативно
- [ ] Кнопки покупки доступны

**Статус:** ⬜ PASS / ⬜ FAIL

---

### Тест 13: Истечение подписки

**Цель:** Проверить автоматическую деактивацию подписки

**Подготовка:**
```sql
-- Установить дату истечения в прошлом
UPDATE user_subscriptions
SET expires_at = NOW() - INTERVAL '1 day'
WHERE user_id = (SELECT id FROM users WHERE telegram_user_id = [ВАШ_TG_ID])
AND status = 'active';
```

**Шаги:**
1. Проверить БД (триггер должен сработать):
   ```sql
   SELECT status, is_active FROM user_subscriptions
   WHERE user_id = (SELECT id FROM users WHERE telegram_user_id = [ВАШ_TG_ID])
   ORDER BY created_at DESC LIMIT 1;
   ```

**Ожидаемый результат:**
```
  status  | is_active
----------+-----------
 expired  | f
```

2. Отправить консультационный вопрос
3. Проверить: Токены расходуются (подписка не активна)

**Проверка:**
- [ ] Подписка автоматически деактивирована (`status` = 'expired')
- [ ] `is_active` = false
- [ ] Токены расходуются при консультациях

**Статус:** ⬜ PASS / ⬜ FAIL

---

## 📊 Итоговый отчет

### Результаты тестирования

| Тест | Название | Статус | Примечания |
|------|----------|--------|-----------|
| 1 | Новый пользователь + Триальные вопросы | ⬜ | |
| 2 | Консультации — Уточнение типа культуры | ⬜ | |
| 3 | Консультации — Конкретная культура | ⬜ | |
| 4 | Консультации — Неопределенная культура | ⬜ | |
| 5 | Консультации — Followup-вопрос | ⬜ | |
| 6 | Покупка подписки | ⬜ | |
| 7 | Покупка пакета токенов | ⬜ | |
| 8 | Отмена платежа | ⬜ | |
| 9 | Реферальная программа | ⬜ | Требует доработки |
| 10 | Admin Panel — Live Feed | ⬜ | |
| 11 | Admin Panel — CRM | ⬜ | |
| 12 | Превышение лимита токенов | ⬜ | |
| 13 | Истечение подписки | ⬜ | |

**Общий статус:** ⬜ PASS / ⬜ FAIL / ⬜ PARTIAL

**Критичные проблемы:**
1. _____________________________________________
2. _____________________________________________
3. _____________________________________________

**Некритичные проблемы:**
1. _____________________________________________
2. _____________________________________________

**Рекомендации:**
_______________________________________________
_______________________________________________
_______________________________________________

---

## 🔍 Дополнительные проверки

### Security

- [ ] API ключи не в git (проверить `.gitignore`)
- [ ] Webhook signature verification (YooKassa)
- [ ] SQL injection защита (параметризованные запросы)
- [ ] Rate limiting для API endpoints

### Performance

- [ ] Время ответа консультации < 10 секунд
- [ ] RAG retrieval < 2 секунд
- [ ] Database connection pooling работает
- [ ] SSE не теряет подключение

### Logs

- [ ] Логи консультаций пишутся корректно
- [ ] Логи платежей информативны
- [ ] Ошибки логируются с трейсбэками
- [ ] Уровни логирования настроены правильно

---

**Тестировщик:** _______________
**Дата тестирования:** _______________
**Окружение:** ⬜ Development / ⬜ Staging / ⬜ Production
**Версия бота:** 1.2.2
