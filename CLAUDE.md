# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL: Read This First

**SOURCE OF TRUTH:** [docs/PROJECT_MAP.md](docs/PROJECT_MAP.md)

Before making ANY changes:
1. Read `docs/PROJECT_MAP.md` — contains architecture, active context, constraints
2. Read `session-summary.md` — contains latest session changes
3. Check relevant docs in `docs/features/` or `docs/architecture/`

**Current Project State (2026-02-25):**
- Version: 1.5.5
- Phase: Payment reliability + broadcast buttons v3 (discount + payment types)
- Latest changes: Graceful shutdown hardened, invite link new/existing user breakdown
- CRITICAL: DB schemas 62-66 NOT YET APPLIED ON PRODUCTION — must apply all five before using broadcasts or funnel triggers
- PENDING PLANS: 3 implementation plans ready in `docs/plans/` — payment reliability, broadcast payment button, broadcast discount button
- See: `session-summary.md` for details

## Collaboration Rules

1. Execute the task immediately. No intros, no summaries, no extra comments.
2. Ask clarifying questions when the user's intent is unclear or ambiguous.
3. **КРИТИЧНО: Отправка сообщений пользователям** — НИКОГДА не отправлять ничего реальным пользователям бота без явного разрешения. Тестирование через API (`/api/admin/broadcasts/*/send`, прямые `bot.send_message` и т.п.) — только для администраторов. Перед любой отправкой на сервере ВСЕГДА спросить: "Это уйдёт реальным пользователям — подтверждаешь?"
4. **КРИТИЧНО: Кириллица в коде** — ВСЕГДА писать русский текст напрямую (`'Загрузка...'`), НИКОГДА не использовать Unicode escape sequences (`'\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430...'`). Это касается всех строк в JS/TS/TSX файлах.
5. Locate all necessary files yourself using `docs/` as starting point:
   - Architecture questions → `docs/architecture/OVERVIEW.md`
   - Feature understanding → `docs/features/` (check relevant doc first)
   - Setup issues → `docs/development/SETUP.md`

   Only ask for files if not found after checking docs and `src/` structure.
6. When modifying a file, return the full updated file.
   - Typical sizes: handlers 200-500 lines, services 100-400 lines
   - Large files (>500 lines): `unified_retriever.py`, `entry.py`
   - If file >600 lines, confirm full replacement is needed
7. Keep explanations minimal (3–6 short bullet points). No line-by-line analysis unless I explicitly ask.
8. When a feature or logic is changed:
   - **Update existing doc** in `docs/features/` or `docs/architecture/`
   - **Create new doc** only if explicitly requested (avoid ephemeral docs)
   - Update `DOCUMENTATION_STATUS.md` if structure changes
9. Always use context7 when I need code generation, setup or configuration steps, or library/API documentation. This means you should automatically use the Context7 MCP tools to resolve library id and get library docs without me having to explicitly ask.
10. **После изменений в webapp — обязательно проверить через Playwright MCP:**
   - **НИКОГДА не запускать dev server или backend самостоятельно** — пользователь запускает их сам
   - **Считай что сервера уже запущены:** backend на `localhost:8080`, admin-webapp на `localhost:5174`
   - Сразу использовать `browser_snapshot` для проверки UI
   - Проверить логику: кликнуть по затронутым элементам, заполнить формы
   - При ошибках: сделать `browser_take_screenshot` для отладки
   - **Если браузер занят** — не перезапускать, просто сообщить пользователю
11. После комита на гит хаб обязательно обновить версию приложения и добавить одну десятую к номеру версии (это требуется для того чтобы телеграм знал что это новая версия)
12. Сам не пуш в гит хаб — делай только когда об этом просят напрямую

## Деплой на сервер

**SSH:** `ssh -i ~/.ssh/id_rsa_server root@72.56.121.98`
**Путь:** `/root/Sadovniki_bot1.2`

### Команды деплоя

```bash
# Бот (быстрая сборка ~5с):
ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
  'cd /root/Sadovniki_bot1.2 && git pull && docker compose up -d --build bot'

# Nginx/admin-webapp (долгая сборка, в фоне):
ssh -i ~/.ssh/id_rsa_server root@72.56.121.98 \
  "nohup bash -c 'cd /root/Sadovniki_bot1.2 && git pull && docker compose up -d --build nginx' > /tmp/nginx_build.log 2>&1 &"
# Проверить: ssh ... 'tail /tmp/nginx_build.log && docker ps | grep nginx'
```

### Graceful shutdown бота

При `docker compose up -d --build bot` Docker отправляет SIGTERM старому контейнеру.
Бот использует **graceful shutdown** (`src/shutdown.py` + `src/main.py`):

1. SIGTERM → наш signal handler ставит флаг + сигнализирует aiogram остановить polling
2. `start_polling()` завершается (с `close_bot_session=False` — сессия НЕ закрывается)
3. **finally блок ждёт завершения всех handler-задач** (LLM-ответы отправляются пользователям)
4. Только потом закрывается bot.session, DB pool и т.д.
5. Docker `stop_grace_period: 75s` — бот имеет 65с на завершение ответов

**ВАЖНО:** НЕ менять `handle_signals`, `close_bot_session` в `dp.start_polling()` — это критично для graceful shutdown.

## Quick Commands

```bash
# Admin Panel dev server (localhost:5174)
cd admin-webapp && npm run dev

# Бот + API сервер (localhost:8080)
python -m src

# База данных
docker-compose up -d db
```

## Quick Reference

### File Navigation
- **Handlers:** `src/handlers/{admin,menu,consultation}/` (200-500 lines each)
- **Services:** `src/services/{llm,rag,db}/` (100-400 lines)
- **Database:** `db/schema*.sql` (apply sequentially: 01→02→03→04)
- **Docs:** `docs/{architecture,features,development}/`
- **Tests:** Root level `test_*.py` (run individually)

### Common Tasks
- **Add consultation category:**
  1. Create prompt in `src/prompts/category_prompts/`
  2. Add handler in `src/handlers/consultation/`
  3. Update `docs/features/CONSULTATION_FLOW.md`

- **Modify RAG behavior:**
  - Retrieval: `src/services/rag/unified_retriever.py` (681 lines)
  - LLM integration: `src/services/llm/consultation_llm.py`

- **Database changes:**
  - Create schema in `db/schema_05.sql` (next version)
  - Add repository in `src/services/db/*_repo.py`
  - Update `docs/architecture/DATABASE.md`

## Code Patterns (must preserve)

### Async Operations
- All services use `async def` with `await`
- DB access: always `pool = get_pool()` (never create new connections)
- Error handling: use `try/except` with logging via `logger.error()`

### State Management
- Global state: `src/handlers/common.py` → `user_data`, `user_terminology`
- Be careful with dict mutations (async race conditions possible)

### Database Queries
- Use parameterized queries: `$1, $2, ...` (never f-strings)
- Vector search: `embedding <=> $1` operator for similarity

### Testing
- No pytest framework — run directly: `python test_*.py`
- Requires DB setup: `docker-compose up -d db`

### Admin Panel (admin-webapp/)
- **Dev server:** `cd admin-webapp && npm run dev` (порт 5174)
- **Backend:** `python -m src` (порт 8080)
- **SSE:** Server-Sent Events для real-time обновлений
  - Live Feed: мгновенное появление новых консультаций
  - Consultation View: real-time обновления топика
  - Проверка подключения: индикатор "🟢 Подключено" / "🔴 Отключено"
- **Документация:** [docs/features/ADMIN_PANEL.md](docs/features/ADMIN_PANEL.md)

### Webapp UI Testing (Playwright MCP)
- **НЕ запускать сервера** — пользователь запускает их сам
- **Порты:**
  - `localhost:5174` — Admin Panel (Vite dev server)
  - `localhost:8080` — Backend API (Python)
- **Тестирование CRM:** `browser_navigate` → `http://localhost:5174` → перейти в раздел CRM
- **Snapshot:** `browser_snapshot` — получить структуру UI
- **Клики:** `browser_click` с указанием ref элемента
- **Скриншоты:** `browser_take_screenshot` для отладки
- **Проверять после:** любых изменений в `admin-webapp/src/`
- **Если браузер занят** — сообщить пользователю, не пытаться перезапускать

### Webapp Design System
- **Дизайн-система:** [webapp/DESIGN_SYSTEM.md](webapp/DESIGN_SYSTEM.md) — полное описание стиля
- **Концепция:** "Органический ботанический сад" — природные тона, органические формы
- **Шрифты:** Cormorant Garamond (заголовки) + Source Sans 3 (текст)
- **Основные цвета:** зелёный #4A7C59, ягодный #C75B5B, кремовый #FDFBF7
- **Уникальные формы:** `--radius-leaf` для выбранных элементов
- **CSS переменные:** `webapp/src/styles/variables.css`
- **Темы:** `webapp/src/styles/themes/{light,dark}.css`

## Technology Notes

- **Aiogram 3.x:** Use `@router.message()` decorators, not `@dp.message_handler()`
- **asyncpg:** Connection pooling via `get_pool()`, queries return `asyncpg.Record`
- **OpenAI API:** Use `openai.AsyncOpenAI`, models: `gpt-4o`, embeddings: `text-embedding-3-large`
- **pgvector:** Store embeddings as `vector(3072)`, use `<=>` for cosine distance

## Project Overview

**Sadovniki-bot** — Telegram-бот для профессиональных консультаций по ягодным культурам. Использует OpenAI GPT для генерации ответов и RAG-систему с PostgreSQL + pgvector для поиска в базе знаний.

**Основные технологии:** Aiogram 3.x, asyncpg, OpenAI API, PostgreSQL с pgvector

## Документация

Полная документация проекта находится в папке `docs/`:

- **Архитектура:** [docs/architecture/OVERVIEW.md](docs/architecture/OVERVIEW.md) — обзор архитектуры системы
- **Функциональность:** [docs/features/](docs/features/) — документация по всем функциям
- **Разработка:** [docs/development/SETUP.md](docs/development/SETUP.md) — установка и настройка

Для быстрого старта см. [README.md](README.md)
