# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Collaboration Rules

1. Execute the task immediately. No intros, no summaries, no extra comments.
2. Ask clarifying questions when the user's intent is unclear or ambiguous.
3. Locate all necessary files yourself using `docs/` as starting point:
   - Architecture questions → `docs/architecture/OVERVIEW.md`
   - Feature understanding → `docs/features/` (check relevant doc first)
   - Setup issues → `docs/development/SETUP.md`

   Only ask for files if not found after checking docs and `src/` structure.
4. When modifying a file, return the full updated file.
   - Typical sizes: handlers 200-500 lines, services 100-400 lines
   - Large files (>500 lines): `unified_retriever.py`, `entry.py`
   - If file >600 lines, confirm full replacement is needed
5. Keep explanations minimal (3–6 short bullet points). No line-by-line analysis unless I explicitly ask.
6. When a feature or logic is changed:
   - **Update existing doc** in `docs/features/` or `docs/architecture/`
   - **Create new doc** only if explicitly requested (avoid ephemeral docs)
   - Update `DOCUMENTATION_STATUS.md` if structure changes
7. Always use context7 when I need code generation, setup   or configuration steps, or
  library/API documentation. This means you should automatically use the Context7 MCP
  tools to resolve library id and get library docs without me having to explicitly ask.
8. **После изменений в webapp — обязательно проверить через Playwright MCP:**
   - **Если dev server уже запущен и страница открыта** — НЕ запускать сервер повторно, сразу использовать `browser_snapshot`
   - Если сервер не запущен: `cd webapp && npm run dev`
   НЕ открывать приложение повторно, сразу использовать
   - Если приложение не открыто: Открыть приложение: `browser_navigate` → `http://localhost:5173`
   - Проверить визуально: `browser_snapshot` — убедиться, что UI не сломан
   - Проверить логику: кликнуть по затронутым элементам, заполнить формы
   - При ошибках: сделать `browser_take_screenshot` для отладки

## Quick Commands

```bash
# Webapp dev server (localhost:5173)
cd webapp && npm run dev

# Бот
python -m src.entry

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

### Webapp UI Testing (Playwright MCP)
- **Dev server:** `cd webapp && npm run dev` (порт 5173)
- **Навигация:** `browser_navigate` → `http://localhost:5173`
- **Snapshot:** `browser_snapshot` — получить структуру UI
- **Клики:** `browser_click` с указанием ref элемента
- **Скриншоты:** `browser_take_screenshot` для отладки
- **Проверять после:** любых изменений в `webapp/src/`

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
