# Broadcast Discount Button Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new `discount` button type in broadcast editor that grants users a time-limited personal discount on all subscription tiers, showing them a special subscription menu with crossed-out prices.

**Architecture:** New 4th button type `discount` (alongside `url`, `quick_reply`, `payment`). It's a callback button — does NOT generate YooKassa links. On click: discount saved to new `user_broadcast_discounts` table with `expires_at`. Normal subscription menu ignores discount; only the special discount menu shows it. Payment service reads both invite and broadcast discounts, applies the higher one.

**Tech Stack:** asyncpg (DB), aiogram 3.x (bot callbacks), React + TypeScript (admin panel ButtonEditor), aiohttp (API validation)

---

## Task 1: DB Migration

**Files:**
- Create: `db/schema_71_broadcast_discounts.sql`

**Step 1: Create migration file**

```sql
-- db/schema_71_broadcast_discounts.sql
-- Персональные скидки, активированные через кнопку рассылки

CREATE TABLE IF NOT EXISTS user_broadcast_discounts (
    id SERIAL PRIMARY KEY,
    user_id           INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    broadcast_id      INT NOT NULL REFERENCES broadcasts(id) ON DELETE CASCADE,
    option_key        VARCHAR(50) NOT NULL,
    discount_percent  INT NOT NULL,
    bonus_tokens      INT NOT NULL DEFAULT 0,
    activated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at        TIMESTAMPTZ NOT NULL,
    UNIQUE(user_id)
);

CREATE INDEX IF NOT EXISTS idx_ubd_user    ON user_broadcast_discounts(user_id);
CREATE INDEX IF NOT EXISTS idx_ubd_expires ON user_broadcast_discounts(expires_at);
```

**Step 2: Apply migration to local DB**

```bash
docker exec -i sadovniki_bot1_2-db-1 psql -U postgres -d sadovniki < db/schema_71_broadcast_discounts.sql
```

Expected: `CREATE TABLE`, `CREATE INDEX`, `CREATE INDEX`

**Step 3: Commit**

```bash
git add db/schema_71_broadcast_discounts.sql
git commit -m "feat: add user_broadcast_discounts table (schema_71)"
```

---

## Task 2: DB Repository

**Files:**
- Create: `src/services/db/discount_repo.py`

Reference: `src/services/db/invite_link_repo.py` lines 133–155 for query pattern.

**Step 1: Create the repo file**

```python
# src/services/db/discount_repo.py
"""
Репозиторий для персональных скидок рассылки.

Функции:
    - upsert_broadcast_discount — создать или заменить скидку пользователя
    - get_user_active_broadcast_discount — получить активную скидку (не истёкшую)
"""

import logging
from typing import Optional, Dict, Any

from src.services.db.pool import get_pool

logger = logging.getLogger(__name__)


async def upsert_broadcast_discount(
    user_id: int,
    broadcast_id: int,
    option_key: str,
    discount_percent: int,
    bonus_tokens: int,
    duration_hours: int,
) -> Dict[str, Any]:
    """
    Создать или заменить активную скидку пользователя.
    UNIQUE(user_id) — при повторном клике старая скидка заменяется.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO user_broadcast_discounts
                (user_id, broadcast_id, option_key, discount_percent, bonus_tokens, expires_at)
            VALUES
                ($1, $2, $3, $4, $5, NOW() + ($6 * INTERVAL '1 hour'))
            ON CONFLICT (user_id) DO UPDATE SET
                broadcast_id     = EXCLUDED.broadcast_id,
                option_key       = EXCLUDED.option_key,
                discount_percent = EXCLUDED.discount_percent,
                bonus_tokens     = EXCLUDED.bonus_tokens,
                activated_at     = NOW(),
                expires_at       = NOW() + ($6 * INTERVAL '1 hour')
            RETURNING *
            """,
            user_id, broadcast_id, option_key, discount_percent, bonus_tokens, duration_hours,
        )
    return dict(row)


async def get_user_active_broadcast_discount(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Вернуть активную скидку (не истёкшую) или None.
    Возвращает: discount_percent, bonus_tokens, expires_at, broadcast_id
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT discount_percent, bonus_tokens, expires_at, broadcast_id
            FROM user_broadcast_discounts
            WHERE user_id = $1 AND expires_at > NOW()
            """,
            user_id,
        )
    return dict(row) if row else None
```

**Step 2: Commit**

```bash
git add src/services/db/discount_repo.py
git commit -m "feat: add discount_repo for broadcast discounts"
```

---

## Task 3: TypeScript Types

**Files:**
- Modify: `admin-webapp/src/types/index.ts` line 1187

**Step 1: Update BroadcastButton interface**

In `admin-webapp/src/types/index.ts`, find `BroadcastButton` interface (line 1184). Change:

```typescript
// BEFORE:
  type: 'url' | 'quick_reply' | 'payment'

// AFTER:
  type: 'url' | 'quick_reply' | 'payment' | 'discount'
```

And add after the existing `payment_package_id` field (line 1197):

```typescript
  // discount button fields (all-plans discount)
  discount_percent?: number | null
  discount_bonus_tokens?: number | null
  discount_duration_hours?: number | null
```

**Step 2: Commit**

```bash
git add admin-webapp/src/types/index.ts
git commit -m "feat: add discount type and fields to BroadcastButton"
```

---

## Task 4: API Validation

**Files:**
- Modify: `src/api/handlers/broadcasts.py` — function `_validate_inline_buttons()` starting at line 635

**Step 1: Extend type check (line 649)**

Change:
```python
# BEFORE:
        if btn_type not in ('url', 'quick_reply', 'payment'):
            raise web.HTTPBadRequest(text='Button type must be "url", "quick_reply" or "payment"')

# AFTER:
        if btn_type not in ('url', 'quick_reply', 'payment', 'discount'):
            raise web.HTTPBadRequest(text='Button type must be "url", "quick_reply", "payment" or "discount"')
```

**Step 2: Add discount validation block — insert AFTER the existing `payment` validation block (after line 666)**

```python
        if btn_type == 'discount':
            dp = btn.get('discount_percent')
            dh = btn.get('discount_duration_hours')
            if not dp or not isinstance(dp, int) or not (1 <= dp <= 99):
                raise web.HTTPBadRequest(text='Discount button requires discount_percent (1-99)')
            if not dh or not isinstance(dh, int) or dh < 1:
                raise web.HTTPBadRequest(text='Discount button requires discount_duration_hours >= 1')
```

Also fix the text validation at line 653 — currently it skips text check only for `payment`, extend to also skip for `discount`:

```python
# BEFORE:
        if btn_type != 'payment' and (not text or len(text) > 64):
# AFTER:
        if btn_type not in ('payment', 'discount') and (not text or len(text) > 64):
```

And add for `discount` text length check:
```python
        if btn_type == 'discount' and len(text) > 64:
            raise web.HTTPBadRequest(text='Button text must be max 64 characters')
```

**Step 3: Commit**

```bash
git add src/api/handlers/broadcasts.py
git commit -m "feat: add discount button type to API validation"
```

---

## Task 5: Broadcast Sender

**Files:**
- Modify: `src/services/broadcast_sender.py` — function `build_inline_keyboard()` around line 200

**Step 1: Add discount branch**

After the last `elif` block in `build_inline_keyboard()` (after the token payment block ending ~line 202), add BEFORE the `if row_buttons:` check:

```python
            elif btn['type'] == 'discount':
                option_key = btn.get('option_key', f"discount_{row_idx}")
                callback_data = f"bcast_discount:{broadcast_id}:{option_key}"
                btn_text = btn.get('text', '').strip()
                if not btn_text:
                    pct = btn.get('discount_percent', 0)
                    hours = btn.get('discount_duration_hours', 24)
                    btn_text = f"🏷️ Скидка {pct}% на {hours}ч"
                row_buttons.append(InlineKeyboardButton(
                    text=btn_text,
                    callback_data=callback_data,
                ))
```

Note: `discount` buttons use `callback_data` (not `url`) and do NOT need per-user generation. The existing `has_personal_buttons` check only looks at `url` and `payment` types — no changes needed there.

**Step 2: Commit**

```bash
git add src/services/broadcast_sender.py
git commit -m "feat: add discount button branch in build_inline_keyboard"
```

---

## Task 6: Discount Subscription Menu (Bot)

**Files:**
- Create: `src/handlers/payments/discount_menu.py`

**Step 1: Create the file**

```python
# src/handlers/payments/discount_menu.py
"""
Меню подписок с персональной скидкой из рассылки.

Вызывается только при клике по discount-кнопке рассылки.
Показывает то же меню тарифов, но с зачёркнутыми ценами и баннером скидки.
"""

import logging
from datetime import datetime, timezone

from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from src.services.db import subscription_plan_repo
from src.services.db.discount_repo import get_user_active_broadcast_discount

logger = logging.getLogger(__name__)


def _compute_time_left(expires_at: datetime) -> tuple[int, int]:
    """Возвращает (hours_left, minutes_left) до истечения скидки."""
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = expires_at - now
    total_seconds = max(0, int(delta.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return hours, minutes


async def show_discount_subscription_menu(callback: CallbackQuery, user_id: int) -> None:
    """
    Показать меню тарифов со скидкой.
    Если скидка истекла — показать обычное платёжное меню.
    """
    discount = await get_user_active_broadcast_discount(user_id)

    if not discount:
        # Скидка истекла — показываем обычное меню
        await callback.message.edit_text(
            "⏰ Срок действия скидки истёк.\n\nВы можете оформить подписку по стандартным ценам:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Перейти к тарифам", callback_data="show_payment_menu")]
            ])
        )
        return

    discount_pct = discount['discount_percent']
    expires_at = discount['expires_at']
    hours_left, minutes_left = _compute_time_left(expires_at)

    plans = await subscription_plan_repo.get_all_active()

    # Баннер
    time_str = f"{hours_left}ч {minutes_left}мин" if hours_left > 0 else f"{minutes_left}мин"
    banner = (
        f"🔥 <b>Ваша персональная скидка {discount_pct}%</b>\n"
        f"Действует ещё: <b>{time_str}</b>\n\n"
    )

    # Список тарифов со скидкой
    plan_lines = []
    for plan in plans:
        original = int(plan['price_rub'])
        discounted = int(original * (100 - discount_pct) / 100)
        plan_lines.append(
            f"📅 <b>{plan['name']}</b>: <s>{original}₽</s> → <b>{discounted}₽</b>/мес"
        )

    text = banner + "\n".join(plan_lines) + "\n\nВыберите тариф для оформления:"

    # Кнопки — стандартные buy_subscription_{id}, скидка применится в payment_service
    buttons = []
    for plan in plans:
        original = int(plan['price_rub'])
        discounted = int(original * (100 - discount_pct) / 100)
        buttons.append([InlineKeyboardButton(
            text=f"{plan['name']} — {original}₽ → {discounted}₽",
            callback_data=f"buy_subscription_{plan['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="show_payment_menu")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML",
    )
```

**Step 2: Commit**

```bash
git add src/handlers/payments/discount_menu.py
git commit -m "feat: add discount subscription menu handler"
```

---

## Task 7: Broadcast Discount Callback Handler

**Files:**
- Modify: `src/handlers/broadcast_callbacks.py` — add new handler after existing `handle_broadcast_button_click`

**Step 1: Add imports at top of file**

After line 11 (`import json`), the imports already have everything needed except the discount imports. Add after the existing imports:

```python
import json  # already there
# Add to existing imports section:
```

No new top-level imports needed — all imports will be local in the handler.

**Step 2: Add handler after the existing `handle_broadcast_button_click` function (after line 124)**

```python
@router.callback_query(F.data.startswith("bcast_discount:"))
async def handle_broadcast_discount_click(callback: CallbackQuery) -> None:
    """Обработка клика по discount-кнопке рассылки. Сохраняет скидку и открывает меню тарифов."""
    try:
        parts = callback.data.split(":", 2)
        if len(parts) != 3:
            await callback.answer("Ошибка формата")
            return

        broadcast_id = int(parts[1])
        option_key = parts[2]

        # Резолвим user_id из БД
        from src.services.db.pool import get_pool
        pool = get_pool()
        async with pool.acquire() as conn:
            user_row = await conn.fetchrow(
                "SELECT id FROM users WHERE telegram_user_id = $1",
                callback.from_user.id,
            )

        if not user_row:
            await callback.answer("Пользователь не найден")
            return

        user_id = user_row['id']

        # Получаем конфиг кнопки из broadcast.inline_buttons
        broadcast = await get_broadcast(broadcast_id)
        btn_config = None
        button_text = option_key
        if broadcast and broadcast.get('inline_buttons'):
            buttons = broadcast['inline_buttons']
            if isinstance(buttons, str):
                buttons = json.loads(buttons)
            for btn in buttons:
                if btn.get('option_key') == option_key and btn.get('type') == 'discount':
                    btn_config = btn
                    button_text = btn.get('text', option_key)
                    break

        if not btn_config:
            await callback.answer()
            return

        # Сохраняем скидку в БД
        from src.services.db.discount_repo import upsert_broadcast_discount
        await upsert_broadcast_discount(
            user_id=user_id,
            broadcast_id=broadcast_id,
            option_key=option_key,
            discount_percent=btn_config['discount_percent'],
            bonus_tokens=btn_config.get('discount_bonus_tokens') or 0,
            duration_hours=btn_config['discount_duration_hours'],
        )

        # Трекируем клик (та же инфраструктура что и у quick_reply)
        run_id = await resolve_run_id_from_recipient(broadcast_id, user_id)
        await record_button_click(
            broadcast_id=broadcast_id,
            user_id=user_id,
            telegram_user_id=callback.from_user.id,
            option_key=option_key,
            button_text=button_text,
            run_id=run_id,
        )

        await callback.answer()

        # Показываем меню подписок со скидкой
        from src.handlers.payments.discount_menu import show_discount_subscription_menu
        await show_discount_subscription_menu(callback, user_id)

    except Exception as e:
        logger.error(f"Error handling broadcast discount click: {e}", exc_info=True)
        await callback.answer("Произошла ошибка")
```

**Step 3: Commit**

```bash
git add src/handlers/broadcast_callbacks.py
git commit -m "feat: add bcast_discount callback handler"
```

---

## Task 8: Apply Discount in Payment Service

**Files:**
- Modify: `src/services/payments/payment_service.py` — function `create_subscription_payment()` around line 266

**Step 1: Replace the invite discount block with combined logic**

Find in `create_subscription_payment()` (lines 266–268):

```python
    # Применить скидку по инвайт-ссылке
    original_price = Decimal(str(plan["price_rub"]))
    final_price, discount_percent = await _apply_invite_discount(user_id, original_price)
```

Replace with:

```python
    # Применить скидку — берём максимальную из инвайт-ссылки и рассылки
    original_price = Decimal(str(plan["price_rub"]))
    _, invite_discount_pct = await _apply_invite_discount(user_id, original_price)

    from src.services.db.discount_repo import get_user_active_broadcast_discount
    broadcast_disc = await get_user_active_broadcast_discount(user_id)
    broadcast_discount_pct = broadcast_disc['discount_percent'] if broadcast_disc else 0
    broadcast_bonus_tokens = broadcast_disc['bonus_tokens'] if broadcast_disc else 0

    best_pct = max(invite_discount_pct or 0, broadcast_discount_pct)
    if best_pct > 0:
        discount_amount = original_price * Decimal(best_pct) / Decimal(100)
        final_price = original_price - discount_amount
        if final_price < Decimal('1.00'):
            final_price = Decimal('1.00')
        discount_percent = best_pct
    else:
        final_price = original_price
        discount_percent = None
```

**Step 2: Add broadcast_bonus_tokens to metadata**

Find the metadata dict (around line 286) and add bonus tokens from broadcast discount:

```python
    metadata = {
        "user_id": str(user_id),
        "telegram_user_id": str(telegram_user_id),
        "payment_type": "subscription",
        "plan_id": str(plan_id),
    }
    if discount_percent:
        metadata["discount_percent"] = str(discount_percent)
        metadata["original_price_rub"] = str(original_price)
    # Бонусные токены из скидки рассылки (начисляются в process_payment_success)
    if broadcast_bonus_tokens and broadcast_bonus_tokens > 0:
        metadata["bonus_tokens"] = str(broadcast_bonus_tokens)
```

Note: `process_payment_success()` already handles `bonus_tokens` in metadata (same pattern used by `create_subscription_payment_custom`). Verify this works by checking around line 806 in payment_service.py.

**Step 3: Commit**

```bash
git add src/services/payments/payment_service.py
git commit -m "feat: apply broadcast discount in create_subscription_payment"
```

---

## Task 9: Admin Panel ButtonEditor UI

**Files:**
- Modify: `admin-webapp/src/components/broadcast/ButtonEditor.tsx`

**Step 1: Add helper function for discount button auto-text** (after the existing `buildTokenButtonText` function, around line 54)

```typescript
function buildDiscountButtonText(discountPercent: number | null | undefined, durationHours: number | null | undefined): string {
  const pct = discountPercent ?? 0
  const hours = durationHours ?? 24
  return `🏷️ Скидка ${pct}% на ${hours}ч`
}
```

**Step 2: Add `discount` to `hasPaymentButton` check** (line 121)

```typescript
// BEFORE:
  const hasPaymentButton = buttons.some((b) => b.type === 'payment')
// AFTER:
  const hasPaymentButton = buttons.some((b) => b.type === 'payment' || b.type === 'discount')
```

Wait — discount buttons don't actually need subscription plans loaded. Skip this change.

**Step 3: Update the type select dropdown** (line 259)

In the `onChange` handler of the type select, change the type annotation:

```typescript
// BEFORE (line 259):
                            const newType = e.target.value as 'url' | 'quick_reply' | 'payment'
// AFTER:
                            const newType = e.target.value as 'url' | 'quick_reply' | 'payment' | 'discount'
```

Add handling for switching TO `discount` type in the `updateButton` call (lines 273–282). Replace:

```typescript
                            updateButton(rowIdx, btnIdx, {
                              type: newType,
                              url: newType === 'url' ? (btn.url || '') : undefined,
                              option_key: btn.option_key || `opt_${optIdx}`,
                              reply_text: newType !== 'quick_reply' ? undefined : btn.reply_text,
                              payment_plan_id: newType === 'payment' ? (btn.payment_plan_id ?? null) : undefined,
                              payment_custom_price: newType === 'payment' ? (btn.payment_custom_price ?? null) : undefined,
                              payment_bonus_tokens: newType === 'payment' ? (btn.payment_bonus_tokens ?? null) : undefined,
                              payment_package_id: newType === 'payment' ? (btn.payment_package_id ?? null) : undefined,
                            })
```

With:

```typescript
                            updateButton(rowIdx, btnIdx, {
                              type: newType,
                              url: newType === 'url' ? (btn.url || '') : undefined,
                              option_key: btn.option_key || `opt_${optIdx}`,
                              reply_text: newType !== 'quick_reply' ? undefined : btn.reply_text,
                              payment_plan_id: newType === 'payment' ? (btn.payment_plan_id ?? null) : undefined,
                              payment_custom_price: newType === 'payment' ? (btn.payment_custom_price ?? null) : undefined,
                              payment_bonus_tokens: newType === 'payment' ? (btn.payment_bonus_tokens ?? null) : undefined,
                              payment_package_id: newType === 'payment' ? (btn.payment_package_id ?? null) : undefined,
                              discount_percent: newType === 'discount' ? (btn.discount_percent ?? null) : undefined,
                              discount_bonus_tokens: newType === 'discount' ? (btn.discount_bonus_tokens ?? null) : undefined,
                              discount_duration_hours: newType === 'discount' ? (btn.discount_duration_hours ?? null) : undefined,
                            })
```

**Step 4: Add `discount` option to the select** (after line 287 `<option value="payment">💳 Оплата</option>`)

```tsx
                          <option value="discount">🏷️ Скидка на все тарифы</option>
```

**Step 5: Add discount UI section** — after the payment section (after line 551 `})()}`), before the remove button:

```tsx
                        {btn.type === 'discount' && (
                          <div className={styles.paymentSection}>
                            <div className={styles.paymentFields}>
                              <div className={styles.paymentFieldGroup}>
                                <label className={styles.paymentFieldLabel}>Скидка (%)</label>
                                <input
                                  className={styles.urlInput}
                                  type="number"
                                  placeholder="30"
                                  value={btn.discount_percent ?? ''}
                                  min={1}
                                  max={99}
                                  onChange={(e) => {
                                    const pct = e.target.value ? Number(e.target.value) : null
                                    const autoText = buildDiscountButtonText(pct, btn.discount_duration_hours)
                                    updateButton(rowIdx, btnIdx, {
                                      discount_percent: pct,
                                      text: autoText,
                                    })
                                  }}
                                />
                              </div>
                              <div className={styles.paymentFieldGroup}>
                                <label className={styles.paymentFieldLabel}>Срок (часов)</label>
                                <input
                                  className={styles.urlInput}
                                  type="number"
                                  placeholder="24"
                                  value={btn.discount_duration_hours ?? ''}
                                  min={1}
                                  onChange={(e) => {
                                    const hours = e.target.value ? Number(e.target.value) : null
                                    const autoText = buildDiscountButtonText(btn.discount_percent, hours)
                                    updateButton(rowIdx, btnIdx, {
                                      discount_duration_hours: hours,
                                      text: autoText,
                                    })
                                  }}
                                />
                              </div>
                              <div className={styles.paymentFieldGroup}>
                                <label className={styles.paymentFieldLabel}>Бонус токенов</label>
                                <input
                                  className={styles.urlInput}
                                  type="number"
                                  placeholder="0"
                                  value={btn.discount_bonus_tokens ?? ''}
                                  min={0}
                                  onChange={(e) => {
                                    updateButton(rowIdx, btnIdx, {
                                      discount_bonus_tokens: e.target.value ? Number(e.target.value) : null,
                                    })
                                  }}
                                />
                              </div>
                            </div>
                            {btn.discount_percent && btn.discount_duration_hours && (
                              <div className={styles.paymentHint}>
                                При нажатии: откроется меню тарифов со скидкой <b>{btn.discount_percent}%</b> на <b>{btn.discount_duration_hours}ч</b>
                                {btn.discount_bonus_tokens ? ` + ${btn.discount_bonus_tokens} бонус-токенов` : ''}
                              </div>
                            )}
                            <div className={styles.urlHint}>
                              Скидка действует на все тарифы. Пользователь провалится в специальное меню с зачёркнутыми ценами.
                            </div>
                          </div>
                        )}
```

**Step 6: Run dev server and check visually via Playwright MCP**

```bash
cd admin-webapp && npm run dev
```

Then use `browser_navigate` → `http://localhost:5174` → открыть рассылку → добавить кнопку → переключить тип на "Скидка на все тарифы" → проверить UI.

**Step 7: Commit**

```bash
git add admin-webapp/src/components/broadcast/ButtonEditor.tsx
git commit -m "feat: add discount button UI in ButtonEditor"
```

---

## Task 10: Check bonus_tokens in process_payment_success

**Files:**
- Read: `src/services/payments/payment_service.py` around line 806

**Step 1: Verify bonus_tokens handling exists**

Search for `bonus_tokens` in `payment_service.py`:

```bash
grep -n "bonus_tokens" src/services/payments/payment_service.py
```

Expected: should find references in `process_payment_success` that already handle bonus tokens from metadata (via `create_subscription_payment_custom` pattern).

If `bonus_tokens` from metadata is NOT handled in `process_payment_success`, add it:

Find the section in `process_payment_success` that processes subscription payments and add:

```python
# После начисления стандартных токенов подписки:
bonus_tokens = int(metadata.get("bonus_tokens", 0) or 0)
if bonus_tokens > 0:
    await add_purchased_tokens(user_id=user_id, tokens=bonus_tokens)
    logger.info(f"Broadcast discount bonus tokens credited: {bonus_tokens} to user {user_id}")
```

**Step 2: Commit only if changes were made**

```bash
git add src/services/payments/payment_service.py
git commit -m "feat: handle bonus_tokens from broadcast discount in payment success"
```

---

## Task 11: Register discount_menu handler (if needed)

**Files:**
- Check: `src/handlers/payments/__init__.py` or wherever payment routers are registered

**Step 1: Check how routers are registered**

```bash
grep -rn "payments_subscription\|buy_subscription" src/handlers/ --include="*.py" | head -20
```

The `discount_menu.py` doesn't define a router — it only exports `show_discount_subscription_menu()` called directly from `broadcast_callbacks.py`. No router registration needed.

Verify `broadcast_callbacks` router is already registered in the main app setup:

```bash
grep -n "broadcast_callbacks" src/handlers/__init__.py src/entry.py 2>/dev/null || grep -rn "broadcast_callbacks" src/ --include="*.py"
```

Expected: should find it already included.

---

## Task 12: End-to-End Verification

**Step 1: Apply DB migration on test environment** (already done in Task 1 Step 2)

**Step 2: Admin panel check via Playwright**

- Navigate to `http://localhost:5174`
- Open Broadcasts → Create new → Add button
- Select type "🏷️ Скидка на все тарифы"
- Fill: Скидка 30%, Срок 24ч, Бонус токенов 500
- Verify hint text shows
- Verify button text auto-fills to "🏷️ Скидка 30% на 24ч"
- Save broadcast as draft

**Step 3: Test the DB repo manually**

```python
# Quick test (run in python -m src REPL or test script):
import asyncio
from src.services.db.pool import create_pool
from src.services.db.discount_repo import upsert_broadcast_discount, get_user_active_broadcast_discount

async def test():
    await create_pool()
    # Use a real user_id from DB
    result = await upsert_broadcast_discount(
        user_id=1, broadcast_id=1, option_key="test",
        discount_percent=30, bonus_tokens=500, duration_hours=24
    )
    print(result)
    active = await get_user_active_broadcast_discount(1)
    print(active)

asyncio.run(test())
```

**Step 4: Test the full flow**

- Send test broadcast with discount button to yourself
- Click button → should show subscription menu with banner "🔥 Ваша персональная скидка 30%" and crossed-out prices
- Navigate to normal subscription menu (callback `show_payment_menu`) → no discount shown
- Click a plan from discount menu → payment page should show discounted price

**Step 5: Manually expire discount and verify fallback**

```sql
UPDATE user_broadcast_discounts SET expires_at = NOW() - INTERVAL '1 second' WHERE user_id = <your_user_id>;
```

Click discount button again → should show "⏰ Срок действия скидки истёк."

**Step 6: Commit version bump**

After all verification passes:

```bash
# Update version in the appropriate config/version file
git add .
git commit -m "feat: broadcast discount button — personal time-limited discount on all plans (v1.5.6)"
```
