# Session Summary — 2026-02-22

## Project Context

**Sadovniki-bot** — Telegram-bot for professional consultations on berry crops with RAG system (PostgreSQL + pgvector) and OpenAI GPT.

**Current Stage:** Production system (v1.5.4) with enhanced broadcast system, funnel stage triggers, HTTPS/SSL on production domain, and YooKassa payment method fix.

**Tech Stack:**
- Backend: Python 3.11+, Aiogram 3.x, asyncpg, OpenAI API
- Frontend: React + TypeScript (Admin Panel), Vite
- Database: PostgreSQL 16 + pgvector
- AI: OpenAI GPT models with flexible configuration, database-driven prompts

---

## Session Goal

**Primary Goal (v1.5.3):** Enhance the broadcast system (resend dialog, multi-button clicks, text responses to buttons), add funnel stage triggers (auto-send broadcast when client moves to a kanban stage), improve CRM activity feed and kanban client cards, configure HTTPS/SSL for proagro56.ru domain, and clean up node_modules from git tracking.

**Secondary Goal (v1.5.4):** Disable `save_payment_method` in YooKassa subscription payments until recurring payment permission is granted by YooKassa.

---

## Accomplishments

### v1.5.3 — Broadcasts v2, Funnels, CRM, HTTPS/SSL

#### Broadcast System Enhancements

**New DB migrations:**

`db/schema_64_broadcast_runs_and_triggers.sql`:
- `broadcast_runs` table — each broadcast can now be sent multiple times (resend). Tracks run_number, target_type, per-run counters (total_recipients, sent_count, failed_count), and timestamps per run.
- `broadcast_recipients` extended with `run_id` FK — unique constraint changed from (broadcast_id, user_id) to (broadcast_id, run_id, user_id) — allows same user to receive different runs.
- `funnel_stage_triggers` table — links a funnel stage to a broadcast; when a client is moved to that stage, the broadcast is sent automatically.
- `funnel_trigger_log` table — one-per-user deduplication: each trigger is only sent once per user.

`db/schema_65_button_clicks_multi.sql`:
- Changed UNIQUE constraint on `broadcast_button_clicks` from (broadcast_id, run_id, user_id) to (broadcast_id, run_id, user_id, option_key) — allows a user to click multiple different buttons in one broadcast, but not the same button twice.

`db/schema_66_broadcast_text_responses.sql`:
- Added `text_response TEXT` and `response_at TIMESTAMPTZ` columns to `broadcast_button_clicks` — stores the user's free-text response when a button has `ask_for_response=true`.

**New backend files:**

`src/handlers/broadcast_responses.py`:
- Router that catches the next text message from a user who is in `waiting_broadcast_response` state (set by broadcast_callbacks when a quick_reply button with `ask_for_response=true` is clicked).
- Saves the response text via `broadcast_repo.save_button_text_response`.
- Clears the state after saving.

`src/services/db/funnel_trigger_repo.py`:
- `get_active_triggers_for_stage(funnel_id, stage_key)` — returns active triggers for a stage.
- `has_trigger_been_sent(trigger_id, user_id)` — deduplication check.
- `log_trigger_sent(trigger_id, user_id, status, error_message)` — records delivery attempt.

`src/services/funnel_trigger_sender.py`:
- `execute_stage_triggers(user_id, telegram_user_id, funnel_id, stage_key)` — called when a client is moved to a funnel stage; checks all active triggers for that stage, skips already-sent ones, and sends the broadcast content (text/photo/poll/buttons) to the user.

**Modified backend files:**

`src/services/broadcast_sender.py`:
- Reworked to support `broadcast_runs`: each call to `execute_broadcast` creates a new `broadcast_run` record.
- SSE progress events now include `run_id`.

`src/services/db/broadcast_repo.py`:
- New functions: `create_broadcast_run`, `update_broadcast_run_status`, `increment_run_counters`, `save_button_text_response`.
- Existing functions updated to work with run_id.

`src/handlers/broadcast_callbacks.py`:
- Added handling for `ask_for_response=true` buttons: sets `CONSULTATION_STATE[user_id] = "waiting_broadcast_response"` and stores `broadcast_id` + `option_key` in `CONSULTATION_CONTEXT`.

`src/api/handlers/broadcasts.py`:
- New endpoints for resend: `POST /broadcasts/{id}/resend` — creates a new run.
- New endpoint: `GET /broadcasts/{id}/runs` — list of all runs with per-run stats.

`src/api/handlers/funnels.py`:
- New endpoints for stage triggers: CRUD for `funnel_stage_triggers`.

`src/handlers/__init__.py`:
- `broadcast_responses_router` registered (before consultation routers, after broadcast_callbacks).

`src/handlers/consultation/entry.py`:
- On client funnel stage change, calls `execute_stage_triggers` to fire any configured trigger broadcasts.

`src/handlers/menu.py`:
- Minor update (related to state management or CRM integration).

`src/main.py`:
- No new background tasks; `broadcast_responses_router` lifecycle handled by registration.

`src/api/routes.py`:
- New routes for resend and trigger management.

`src/api/middleware.py`:
- Minor update (likely for new routes or CORS).

`src/config.py`:
- Minor update.

#### Funnel System Improvements

`admin-webapp/src/components/funnel/StageTriggerEditor.tsx` (NEW):
- UI component for editing stage triggers: select a broadcast to attach to a funnel stage.
- Shows attached broadcast name, allows adding/removing triggers.

`admin-webapp/src/components/funnel/FunnelClientCard.tsx`:
- Enhanced client card display in kanban.

`admin-webapp/src/components/funnel/FunnelColumn.tsx`:
- Updated to integrate StageTriggerEditor.

`admin-webapp/src/components/funnel/FunnelKanban.tsx`:
- Updated kanban layout/interactions.

`admin-webapp/src/store/funnelStore.ts`:
- Added trigger management state: `fetchStageTriggers`, `addStageTrigger`, `removeStageTrigger`.

#### Broadcast UI Enhancements

`admin-webapp/src/components/broadcast/ResendDialog.tsx` (NEW):
- Modal dialog for resending a broadcast: select target (same/different) and confirm.

`admin-webapp/src/components/broadcast/BroadcastDetail.tsx`:
- Added "Отправить ещё раз" button for completed broadcasts (opens ResendDialog).
- Shows per-run stats (list of runs).

`admin-webapp/src/components/broadcast/BroadcastForm.tsx`:
- Improvements to form UX.

`admin-webapp/src/components/broadcast/BroadcastList.tsx`:
- Status badge improvements.

`admin-webapp/src/components/broadcast/BroadcastPage.tsx`:
- Layout updates.

`admin-webapp/src/components/broadcast/BroadcastStats.tsx`:
- Stats now display per-run breakdown.

`admin-webapp/src/components/broadcast/ButtonEditor.tsx`:
- Added `ask_for_response` toggle for quick_reply buttons (enables text response collection).

`admin-webapp/src/components/broadcast/PollEditor.tsx`:
- Minor improvements.

`admin-webapp/src/store/broadcastStore.ts`:
- Added `resendBroadcast`, `getBroadcastRuns` actions.

`admin-webapp/src/services/api.ts`:
- Added: `resendBroadcast`, `getBroadcastRuns`, `getStageTriggers`, `addStageTrigger`, `removeStageTrigger`.

`admin-webapp/src/types/index.ts`:
- New types: `BroadcastRun`, `BroadcastRunsResponse`, `FunnelStageTrigger`, `StageTriggerCreate`.

#### CRM Activity Feed

`admin-webapp/src/components/crm/RightPanel/ActivityItem.tsx`:
- Updated broadcast event renderers (avatar support, improved layout).

#### Infrastructure — HTTPS/SSL

`nginx/nginx.conf`:
- Domain-specific config for `proagro56.ru` and `www.proagro56.ru`.
- HTTP (port 80) redirects to HTTPS.
- HTTPS (port 443) with Let's Encrypt certificates (`/etc/letsencrypt/live/proagro56.ru/`).
- TLS protocols: TLSv1.2 + TLSv1.3.

`docker-compose.yml`:
- Updated for HTTPS (likely volume mount for `/etc/letsencrypt`).

`.env.production.example`:
- Updated with new environment variable examples.

`.gitignore`:
- `admin-webapp/node_modules/` added — previously was accidentally tracked.

---

### v1.5.4 — Disable save_payment_method

`src/services/payments/payment_service.py`:
- `create_subscription_payment()`: changed `save_payment_method=True` to `save_payment_method=False`.
- Reason: YooKassa requires a separate "recurring payments" approval from the merchant. Enabling `save_payment_method` without approval causes payment errors.
- Comment updated: "Рекуррентные платежи требуют отдельного разрешения от ЮКассы".

---

## Key Decisions

### 1. Broadcast Runs — Resend Architecture

**Decision:** Each broadcast send is a `broadcast_run`, not a state change on the broadcast itself.

**Rationale:**
- A completed broadcast can be resent to a new or different audience — both send histories must be preserved.
- Unique constraint shifted from (broadcast_id, user_id) to (broadcast_id, run_id, user_id) — same user can be in different runs.
- Stats are aggregated per run and also across all runs.

### 2. ask_for_response on Buttons

**Decision:** Quick_reply buttons can have `ask_for_response=true` — clicking them puts the user in a `waiting_broadcast_response` state, next text message is captured as the button response.

**Rationale:**
- Enables surveys/qualification flows where user needs to elaborate.
- Text response stored in `broadcast_button_clicks.text_response` — co-located with the click record.
- Deduplication: same option_key can only be answered once per run per user (schema_65 constraint).

### 3. Funnel Stage Triggers

**Decision:** Attach broadcasts to funnel stages as triggers — when a CRM client is moved to that stage, the broadcast content is sent automatically, but only once per user.

**Rationale:**
- Enables automated nurturing sequences tied to sales pipeline position.
- `funnel_trigger_log` prevents re-sending if admin accidentally moves client back and forth.
- Uses same broadcast content/format as manual broadcasts — no new message format needed.

### 4. Disable save_payment_method (YooKassa)

**Decision:** `save_payment_method=False` until YooKassa grants recurring payment permission.

**Rationale:**
- YooKassa merchant account requires explicit approval for recurring payments (separate application process).
- Without approval, `save_payment_method=True` causes payment creation errors.
- This is a temporary fix; when approval is granted, revert to `True` and test autopayments.

### 5. HTTPS/SSL via Let's Encrypt for proagro56.ru

**Decision:** Configure nginx with Let's Encrypt certificates; HTTP redirects to HTTPS.

**Rationale:**
- Production bot webhook requires HTTPS (Telegram requirement).
- Let's Encrypt is free, auto-renewable.
- Certificates mounted into nginx container via Docker volume.

---

## Problems & Limitations

### Active Issues — CRITICAL

1. **DB migrations 62-66 status on production is unclear:**
   - Schemas 62-63 were from v1.5.2 (first broadcast commit) — unknown if applied.
   - Schemas 64-66 from v1.5.3 — almost certainly NOT applied on production.
   - Must apply all sequentially before using broadcast system or funnel triggers.
   - Order: `schema_62` → `schema_63` → `schema_64` → `schema_65` → `schema_66`.

2. **save_payment_method disabled permanently until YooKassa approves:**
   - Autopayments (recurring subscriptions) will NOT work until approval.
   - Users can still manually renew subscriptions.
   - Pending action: apply for YooKassa recurring payment permission.

### Active Issues — Medium Priority

3. **Funnel stage triggers not yet end-to-end tested:**
   - `execute_stage_triggers` is called from `entry.py` on stage change — needs manual verification that the trigger fires and the message is delivered in Telegram.

4. **Broadcast cancellation mid-send still not interrupt-safe:**
   - Setting status to `cancelled` does not stop an in-progress `execute_broadcast` task.
   - The sender checks status only once per batch.

5. **ActivityFilters broadcast filter buttons still not shown:**
   - `broadcast_sent`, `broadcast_button_click`, `broadcast_poll_answer` appear in "Все" but have no individual filter button in `ActivityFilters.tsx`.

### Technical Debt

1. `sanitize_html_for_telegram()` still in `broadcast_sender.py` — should move to `src/utils/formatting.py`.
2. BroadcastPage error handling uses `console.error` + alert dialogs — needs toast notification system.
3. No pagination in BroadcastList (fetches all broadcasts).
4. `@remirror/` packages may still exist in `admin-webapp/node_modules` (leftover from earlier install) — node_modules is no longer tracked in git, so this is only a local concern.

---

## Rejected Ideas

### Resend by Cloning Broadcast

- **Proposal:** Resending creates a new broadcast record (a copy).
- **Rejected:** Would lose the connection to the original broadcast's stats; makes it harder to compare performance across multiple sends of the same content.
- **Chosen:** `broadcast_runs` concept — one broadcast, multiple runs.

### Separate Message Format for Funnel Triggers

- **Proposal:** Funnel triggers use a separate simpler message format (just text).
- **Rejected:** Unnecessary duplication of message sending logic.
- **Chosen:** Reuse broadcast content format exactly — attach any existing broadcast to a stage trigger.

---

## Current Code State

### New Files Created (v1.5.3)

**Backend:**
- `src/handlers/broadcast_responses.py` — text response capture handler
- `src/services/db/funnel_trigger_repo.py` — funnel trigger DB operations
- `src/services/funnel_trigger_sender.py` — stage trigger execution logic

**Database Migrations:**
- `db/schema_64_broadcast_runs_and_triggers.sql` — broadcast_runs + funnel_stage_triggers + funnel_trigger_log
- `db/schema_65_button_clicks_multi.sql` — allow multiple button clicks per user per broadcast (per option_key)
- `db/schema_66_broadcast_text_responses.sql` — text_response + response_at on broadcast_button_clicks

**Frontend:**
- `admin-webapp/src/components/broadcast/ResendDialog.tsx` — resend broadcast modal
- `admin-webapp/src/components/funnel/StageTriggerEditor.tsx` — funnel stage trigger UI

### Modified Files (v1.5.3)

**Backend:**
- `src/services/broadcast_sender.py` — run-based architecture
- `src/services/db/broadcast_repo.py` — run-aware CRUD
- `src/handlers/broadcast_callbacks.py` — ask_for_response state handling
- `src/handlers/__init__.py` — broadcast_responses_router registered
- `src/handlers/consultation/entry.py` — fires stage triggers on kanban move
- `src/api/handlers/broadcasts.py` — resend + runs endpoints
- `src/api/handlers/funnels.py` — trigger CRUD endpoints
- `src/api/routes.py` — new routes
- `src/services/db/client_crm_repo.py` — activity feed updates
- `src/services/db/funnel_repo.py` — kanban updates
- `nginx/nginx.conf` — HTTPS/SSL for proagro56.ru
- `docker-compose.yml` — Let's Encrypt volume
- `.gitignore` — node_modules excluded

**Frontend:**
- `admin-webapp/src/components/broadcast/` — BroadcastDetail, BroadcastForm, BroadcastList, BroadcastPage, BroadcastStats, ButtonEditor, PollEditor updated
- `admin-webapp/src/components/funnel/FunnelClientCard.tsx`, `FunnelColumn.tsx`, `FunnelKanban.tsx`
- `admin-webapp/src/components/crm/RightPanel/ActivityItem.tsx`
- `admin-webapp/src/store/broadcastStore.ts`, `funnelStore.ts`
- `admin-webapp/src/services/api.ts`
- `admin-webapp/src/types/index.ts`

### Modified Files (v1.5.4)

- `src/services/payments/payment_service.py` — `save_payment_method=False`

### What's Working

1. Broadcast CRUD — create/edit/delete/send/schedule/cancel
2. Broadcast resend — create a new run for any broadcast
3. Resend dialog in admin panel UI
4. Text response collection via quick_reply buttons with `ask_for_response=true`
5. Button click uniqueness per option_key (schema_65)
6. Funnel stage trigger CRUD in admin panel (StageTriggerEditor)
7. Funnel stage trigger execution on client stage change
8. HTTPS/SSL on proagro56.ru (nginx + Let's Encrypt)
9. Subscription payments without `save_payment_method` (YooKassa-safe)

### What Needs Testing

1. Full broadcast resend flow: create → send → resend → verify two runs in DB
2. Text response collection: click button with `ask_for_response` → type text → verify saved
3. Funnel stage trigger: move client to stage with trigger → verify Telegram message sent
4. Trigger deduplication: move client back and forth → verify no duplicate sends
5. HTTPS: verify SSL certificate works on proagro56.ru production
6. YooKassa payment creation with `save_payment_method=False`

---

## Next Steps

### Critical (Before Production Use)

1. **Apply DB migrations 62-66 on production server:**
   ```bash
   psql -h localhost -U bot_user -d garden_bot -f db/schema_62_broadcasts.sql
   psql -h localhost -U bot_user -d garden_bot -f db/schema_63_broadcast_buttons_and_stats.sql
   psql -h localhost -U bot_user -d garden_bot -f db/schema_64_broadcast_runs_and_triggers.sql
   psql -h localhost -U bot_user -d garden_bot -f db/schema_65_button_clicks_multi.sql
   psql -h localhost -U bot_user -d garden_bot -f db/schema_66_broadcast_text_responses.sql
   ```

2. **Verify Docker volume for Let's Encrypt certs:**
   - Check that `/etc/letsencrypt` is mounted in nginx container in `docker-compose.yml`.
   - Verify cert renewal cron job exists on server (or certbot auto-renew).

3. **Apply for YooKassa recurring payment permission:**
   - Log into YooKassa merchant panel → apply for recurring payments.
   - When approved: set `save_payment_method=True` in `payment_service.py` and re-enable autopayments.

### High Priority

4. **End-to-end test broadcast resend:**
   - Create broadcast, send once, then resend — verify two `broadcast_runs` records and messages in Telegram.

5. **Test ask_for_response flow:**
   - Create broadcast with a button (type=quick_reply, ask_for_response=true).
   - Send to self → click button → type text → verify `text_response` saved in `broadcast_button_clicks`.

6. **Test funnel stage triggers:**
   - Attach a broadcast to a funnel stage in admin panel.
   - Move a test client to that stage.
   - Verify: message received in Telegram, `funnel_trigger_log` record created, no duplicate on second move.

### Medium Priority

7. **Add broadcast filter buttons to ActivityFilters:**
   - Add visible entries for `broadcast_sent`, `broadcast_button_click`, `broadcast_poll_answer` in `VISIBLE_FILTERS` array in `admin-webapp/src/components/crm/RightPanel/ActivityFilters.tsx`.

8. **Move `sanitize_html_for_telegram()` to utils:**
   - Move from `src/services/broadcast_sender.py` to `src/utils/formatting.py`.

9. **Deploy v1.5.4 to production:**
   ```bash
   ssh root@72.56.121.98
   cd /root/Sadovniki_bot1.2 && git pull
   docker compose up -d --build bot
   # Then apply DB migrations
   # Then rebuild nginx:
   nohup bash -c 'docker compose up -d --build nginx > /tmp/nginx_build.log 2>&1' &
   ```

---

## Session Statistics

**Sessions covered:** 2026-02-22 (two commits: v1.5.3 and v1.5.4)

**v1.5.3:**
- Files Modified: ~20 backend + frontend files
- Files Created: 5 new files (3 backend, 2 frontend)
- DB Migrations: 3 new schemas (64-66)
- New Features: Broadcast resend, text responses on buttons, funnel stage triggers, HTTPS/SSL

**v1.5.4:**
- Files Modified: 1 file (`payment_service.py`)
- Bug Fix: Disable `save_payment_method` (YooKassa approval required)

---

**Session completed:** 2026-02-22
**Version:** 1.5.4
**Status:** Production ready (pending DB migrations 62-66 on server and HTTPS verification)
**Breaking Changes:** None (all additive; schema changes are backward-compatible via `ADD COLUMN IF NOT EXISTS` and `ALTER TABLE`)
**Migration Required:** YES — schemas 62-66 must be applied before using broadcast features or funnel triggers
