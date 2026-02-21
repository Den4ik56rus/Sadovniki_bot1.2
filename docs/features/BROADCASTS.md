# Feature: Broadcasts (Рассылки)

**Status:** Implemented, DB migrations pending on production (2026-02-21)
**Version:** 1.5.2

---

## Purpose

Mass messaging system allowing administrators to send targeted broadcasts to bot users from the admin panel. Supports text, photos, polls, and interactive inline buttons. Provides real-time delivery progress via SSE and per-broadcast statistics.

---

## Architecture & Logic

### Components

```
Admin Panel (BroadcastPage)
    │
    ├── BroadcastList — list of all broadcasts (status, title, counters)
    ├── BroadcastDetail — view/edit detail
    │   ├── BroadcastForm — create/edit form
    │   │   ├── MessageEditor (TipTap)
    │   │   ├── PhotoUploader
    │   │   ├── PollEditor
    │   │   ├── ButtonEditor
    │   │   └── RecipientSelector
    │   ├── BroadcastProgress — SSE live delivery bar
    │   └── BroadcastStats — delivery report + click/poll stats
    │
    ↓ (API calls)

Backend REST API (/api/admin/broadcasts/*)
    │
    ├── broadcast_repo.py — DB operations
    ├── broadcast_sender.py — async Telegram sender
    └── broadcast_scheduler.py — auto-send scheduled broadcasts

    ↓ (Telegram)

Bot Callbacks (broadcast_callbacks.py)
    ├── bcast:{id}:{option_key} — quick_reply button click
    └── PollAnswer — Telegram poll response
```

### Database Schema

Tables (schema_62, schema_63):

- `broadcasts` — master record (title, content, targeting, schedule, status, counters)
- `broadcast_recipients` — per-user delivery record (status: pending/sent/failed, sent_at)
- `broadcast_button_clicks` — records quick_reply button presses (unique per user)
- `broadcast_poll_answers` — records Telegram PollAnswer (only for non-anonymous polls)

Columns:
- `broadcasts.inline_buttons` — JSONB array: `[{row, text, type, url?, option_key?}]`
- `broadcasts.poll_options` — JSONB array of strings
- `broadcasts.target_user_ids` — JSONB array of int (manual targeting)
- `broadcast_recipients.telegram_poll_id` — maps Telegram poll_id back to broadcast

### Message Content Types

A broadcast can contain one or more of:
1. **Text** — TipTap HTML, sanitized to Telegram HTML tags by `sanitize_html_for_telegram()`
2. **Photo** — uploaded via multipart, stored in `data/broadcast_photos/`, sent as `FSInputFile`
3. **Poll** — Telegram native poll (question + 2-10 options, anonymous/multiple settings)
4. **Inline buttons** — row-based layout, two types:
   - `url` — opens URL in browser
   - `quick_reply` — callback `bcast:{broadcast_id}:{option_key}`, records click in DB

### Targeting

| `target_type` | Description |
|---------------|-------------|
| `all` | All users with `is_blocked=False` |
| `invite_link` | Users who joined via specific invite link |
| `funnel_stage` | Users at a specific CRM funnel stage |
| `manual` | Manually selected list of user IDs |

Preview count available before sending via `POST /api/admin/broadcasts/preview-count`.

### Status Lifecycle

```
draft → scheduled → sending → completed
  │         │          │
  └─────────┴──────→ cancelled
                 └──→ failed
```

- `draft` — default on create
- `scheduled` — set by `/schedule` endpoint with `scheduled_at` datetime
- `sending` — set when sender starts; auto-transitions from `scheduled` by scheduler loop
- `completed` — all recipients processed
- `failed` — critical error during send
- `cancelled` — cancelled by admin before/during send

### Delivery Engine

`src/services/broadcast_sender.py`:
- Rate: 0.05s per message (~20 msg/sec, well under Telegram's 30/sec limit)
- SSE progress: broadcasts `broadcast_progress` event every 5 messages
- On completion: broadcasts `broadcast_completed` event
- HTML sanitization: strips non-Telegram tags, converts `<p>` and `<br>` to newlines

`src/services/broadcast_scheduler.py`:
- Polls DB every 60 seconds for broadcasts where `status='scheduled' AND scheduled_at <= NOW()`
- Executes matching broadcasts via `execute_broadcast()`

### Real-Time Progress (SSE)

Endpoint: `GET /api/admin/events/broadcast/{broadcast_id}`

Events:
- `broadcast_progress` — `{broadcast_id, sent_count, failed_count, total_recipients}`
- `broadcast_completed` — `{broadcast_id, sent_count, failed_count, total_recipients, status}`

### Statistics

`GET /api/admin/broadcasts/{id}/stats` returns:
- `button_clicks` — per `option_key`: click_count + percentage of total_recipients
- `poll_answers` — per `option_index`: answer_count + percentage of total_poll_respondents
- `total_button_respondents` — unique users who clicked any button
- `total_poll_respondents` — unique users who answered poll

Drill-down: `GET /api/admin/broadcasts/{id}/stats/users?type=button&key=opt_0` — list of users who clicked a specific button.

---

## Files & Entry Points

### Backend

| File | Purpose |
|------|---------|
| `src/services/db/broadcast_repo.py` | All DB queries |
| `src/services/broadcast_sender.py` | Telegram delivery engine |
| `src/services/broadcast_scheduler.py` | Scheduled broadcast checker |
| `src/handlers/broadcast_callbacks.py` | Bot: button clicks + poll answers |
| `src/api/handlers/broadcasts.py` | REST API handlers |
| `src/api/handlers/sse.py` (broadcast_stream) | SSE progress endpoint |
| `src/api/routes.py` | Route registration |
| `src/handlers/__init__.py` | Router registration |
| `src/main.py` | Scheduler task lifecycle |

### Database

| File | Contains |
|------|---------|
| `db/schema_62_broadcasts.sql` | broadcasts + broadcast_recipients tables |
| `db/schema_63_broadcast_buttons_and_stats.sql` | inline_buttons column + click/poll stats tables |

### Frontend

| File | Purpose |
|------|---------|
| `admin-webapp/src/components/broadcast/` | All UI components (22 files) |
| `admin-webapp/src/store/broadcastStore.ts` | Zustand state |
| `admin-webapp/src/services/api.ts` | 13 API methods for broadcasts |
| `admin-webapp/src/types/index.ts` | TypeScript types |

---

## Key Decisions

1. **Inline buttons as JSONB** — no separate table, buttons are broadcast-specific and never reused across broadcasts
2. **one-response-per-user UNIQUE constraint** on `broadcast_button_clicks` — prevents spam, mirrors survey semantics
3. **Non-anonymous polls only tracked** — Telegram only fires `PollAnswer` updates for `is_anonymous=False`
4. **TipTap editor** — HTML output with sanitizer for Telegram; preferred over Remirror for simpler API
5. **Simple scheduler loop** — 60s polling in asyncio background task, no external scheduler infrastructure

---

## Edge Cases & Risks

1. **Mid-send cancellation** — Cancel endpoint sets DB status but does not interrupt running `execute_broadcast` task. The sender will complete the current batch before seeing the cancellation. This is acceptable for typical send volumes.
2. **Poll anonymity** — If `poll_is_anonymous=True` (default), no `PollAnswer` events are fired by Telegram — stats will be empty. Admin should set `is_anonymous=False` for trackable polls.
3. **Photo storage in Docker** — `data/broadcast_photos/` must be a Docker volume mount. Without it, photos are lost on container restart.
4. **Duplicate sends** — No idempotency guard on `POST /broadcasts/{id}/send`. Calling it twice will attempt to re-send to already-completed recipients (DB unique constraint will skip them, but the broadcast counters may double-count).

---

## TODO / Next Steps

- [ ] Apply schema_62 and schema_63 to production database
- [ ] Verify `data/broadcast_photos/` Docker volume mount
- [ ] End-to-end test: create → send → verify Telegram delivery
- [ ] Add broadcast event filter buttons in `ActivityFilters.tsx` (VISIBLE_FILTERS)
- [ ] Move `sanitize_html_for_telegram()` to `src/utils/formatting.py`
- [ ] Add idempotency guard on `/send` endpoint (check if already completed/sending)
- [ ] Consider pagination in BroadcastList for >100 broadcasts
