# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Collaboration Rules

1. Execute the task immediately. No intros, no summaries, no extra comments.
2. Do not ask clarifying questions unless the task is technically impossible without them.
3. Do not propose plans. Go straight to implementation.
4. Locate all necessary files yourself. Do not ask me to provide files unless they truly cannot be found.
5. When modifying a file, always return the full updated file.
6. Keep explanations minimal (3–6 short bullet points). No line-by-line analysis unless I explicitly ask.
7. Do not create new files or restructure the project unless I explicitly instruct you to.
8. Do not suggest additional improvements. Perform only the task I describe.


## Project Overview

This is a Telegram bot for gardening consultations (Sadovniki-bot) specializing in berry crops (strawberries, raspberries, currants, gooseberries, etc.). The bot uses OpenAI's GPT models for consultations and implements a RAG (Retrieval-Augmented Generation) system with PostgreSQL + pgvector for knowledge base search.

## Development Commands

### Running the bot
```bash
# Activate virtual environment
source venv/bin/activate

# Run the bot
python -m src.main
```

### Database setup
```bash
# Start PostgreSQL with pgvector using Docker
docker-compose up -d

# Apply database schema
psql -h localhost -U bot_user -d garden_bot -f db/schema.sql
psql -h localhost -U bot_user -d garden_bot -f db/schema_topics.sql
```

### Dependencies
```bash
# Install dependencies
pip install -r requirements.txt
```

## Architecture

### Entry Point Flow
1. [src/main.py](src/main.py) - Application entry point
   - Initializes database pool via `init_db_pool()`
   - Creates bot and dispatcher via `create_bot_and_dispatcher()`
   - Starts polling with `dp.start_polling(bot)`
   - Closes database pool on shutdown

2. [src/bot.py](src/bot.py) - Bot factory
   - Creates Bot instance with token and HTML parse mode
   - Creates Dispatcher
   - Calls `setup_routers()` to register all handlers

3. [src/handlers/__init__.py](src/handlers/__init__.py) - Router registration
   - Registers menu handlers
   - Registers consultation handlers
   - Registers admin/moderation handlers

### Configuration System
- [src/config.py](src/config.py) defines `Settings` class using `pydantic-settings`
- Reads from environment variables and `.env` file
- Key settings:
  - `telegram_bot_token` - Bot token from BotFather
  - `db_host`, `db_port`, `db_name`, `db_user`, `db_password` - PostgreSQL connection
  - `openai_api_key`, `openai_model`, `openai_embeddings_model` - OpenAI API configuration
- Global `settings` object is imported throughout the codebase

### Database Architecture
- Uses asyncpg for async PostgreSQL access
- [src/services/db/pool.py](src/services/db/pool.py) manages connection pool
  - `init_db_pool()` - Create pool at startup
  - `get_pool()` - Get current pool (used by all repos)
  - `close_db_pool()` - Close pool at shutdown

Key repositories:
- `users_repo.py` - User CRUD operations
- `topics_repo.py` - Conversation topics management (tracks user sessions)
- `messages_repo.py` - Message logging for conversation history
- `kb_repo.py` - Knowledge base operations with vector search
- `moderation_repo.py` - Moderation queue for knowledge base candidates

### Consultation Flow
1. User sends text message → [src/handlers/consultation/entry.py](src/handlers/consultation/entry.py)
2. Handler calls `get_or_create_user()` and `get_or_create_open_topic()`
3. User message logged via `log_message()`
4. `ask_consultation_llm()` called with user text and session context
5. LLM response sent back to user
6. Bot response logged
7. Q&A pair added to moderation queue for potential knowledge base addition

### LLM Integration
- [src/services/llm/core_llm.py](src/services/llm/core_llm.py) - Low-level OpenAI client
  - `create_chat_completion()` - Makes chat completion requests
  - Uses AsyncOpenAI client configured with API key from settings

- [src/services/llm/embeddings_llm.py](src/services/llm/embeddings_llm.py) - Embedding generation
  - Creates embeddings for RAG similarity search

- `consultation_llm.py` (high-level) orchestrates:
  1. Generate embedding for user query
  2. Retrieve similar answers from knowledge base via RAG
  3. Build system prompt from [src/prompts/consultation_prompts.py](src/prompts/consultation_prompts.py)
  4. Add conversation history
  5. Call `create_chat_completion()`
  6. Return structured answer

### RAG System
- [src/services/rag/kb_retriever.py](src/services/rag/kb_retriever.py) - Knowledge base retrieval
- `retrieve_kb_snippets()` searches by:
  - `category` - Consultation type (питание растений, посадка и уход, защита растений, etc.)
  - `subcategory` - Specific crop (малина, клубника, голубика, etc.)
  - `query_embedding` - Vector similarity search
- Two-tier fallback: if no results for specific subcategory, searches entire category
- Uses PostgreSQL pgvector for embedding similarity search

### Prompt Engineering
[src/prompts/consultation_prompts.py](src/prompts/consultation_prompts.py) defines system prompts:
- Bot is positioned as professional agronomist consultant for berry crops only
- Strict scope limitation: only berry crops (strawberries, raspberries, currants, gooseberries, etc.)
- Rejects off-topic questions with brief redirect message
- Avoids generic closing phrases like "if you have more questions..."
- Two-phase consultation pattern:
  1. Ask clarifying questions (all in one message)
  2. Provide structured final answer with problem diagnosis, step-by-step actions, important nuances

### Knowledge Base Moderation
- Admin handlers in [src/handlers/admin/moderation.py](src/handlers/admin/moderation.py)
- `/kb_pending` command shows moderation queue
- Admins can approve/reject Q&A pairs for knowledge base
- Approved pairs stored with embeddings for future RAG retrieval
- Admin user IDs configured in `src.handlers.admin.ADMIN_IDS`

## Important Implementation Notes

### Session Management
- Sessions tracked via `session_id` built from message metadata
- Topics table stores conversation context with `meta` JSON field
- Each topic linked to user and can be open or closed

### Message Logging
- All user and bot messages logged to `messages` table
- Enables conversation history for context-aware responses
- Used for debugging and analytics

### Database Schema
- `users` - User profiles (telegram_user_id, username, etc.)
- `topics` - Conversation topics with metadata
- `messages` - All messages (user + bot) with timestamps
- `knowledge_base` - Approved Q&A with embeddings for RAG
- `moderation_queue` - Pending Q&A pairs awaiting approval

Database uses pgvector extension for embedding storage and similarity search.

## Environment Variables

Required in `.env` file:
- `TELEGRAM_BOT_TOKEN` - From BotFather
- `OPENAI_API_KEY` - OpenAI API key
- `OPENAI_MODEL` - Model name (default: gpt-4.1-mini)
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL connection

## Code Organization Principles

1. **Handlers** ([src/handlers/](src/handlers/)) - Aiogram handlers only, no business logic
2. **Services** ([src/services/](src/services/)) - Business logic, database access, LLM calls
3. **Keyboards** ([src/keyboards/](src/keyboards/)) - Reply and Inline keyboards, no logic
4. **Models** ([src/models/](src/models/)) - Pydantic models for data validation
5. **Prompts** ([src/prompts/](src/prompts/)) - LLM system prompts and prompt builders
6. **Utils** ([src/utils/](src/utils/)) - Utility functions (logging, text processing, JSON handling)

Each consultation type (питание растений, посадка и уход, защита растений, etc.) has:
- Handler in [src/handlers/consultation/](src/handlers/consultation/)
- Keyboard in [src/keyboards/consultation/](src/keyboards/consultation/)

## Testing Considerations

When testing consultations:
- Ensure PostgreSQL is running with pgvector extension
- Database must be initialized with schema files
- OpenAI API key must be valid
- Test both with and without RAG context (empty knowledge base vs. populated)
- Test scope limitation (off-topic questions should be rejected)
