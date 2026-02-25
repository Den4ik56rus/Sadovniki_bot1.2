# Broadcast Payment Button + Create-in-Trigger Modal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `payment` button type to broadcasts (creates a personal YooKassa payment URL per recipient) and add a "Create broadcast" modal inside the StageTriggerEditor so admins don't need to leave the funnel page.

**Architecture:**
- `payment` button is a new value for `BroadcastButton.type`. During send, `build_inline_keyboard()` calls `create_subscription_payment_custom()` for each recipient to generate a personal payment URL. The URL is embedded directly as an inline URL button (no redirect tracker needed — it's already personal).
- The "Create broadcast" modal renders `<BroadcastForm>` inside a fixed overlay in `StageTriggerEditor`. After save it refreshes the broadcast list and auto-selects the new broadcast.

**Tech Stack:** React+TS (Vite), Aiogram 3.x, asyncpg, YooKassa (existing), Zustand

---

## Task 1: Add `payment` type to TypeScript types

**Files:**
- Modify: `admin-webapp/src/types/index.ts`

**Step 1: Find `BroadcastButton` interface**

It's around line 1200+ in `types/index.ts`. The `type` field currently is `'url' | 'quick_reply'`.

**Step 2: Update `BroadcastButton`**

Add `payment` type and new optional fields:

```typescript
export interface BroadcastButton {
  row: number
  text: string
  type: 'url' | 'quick_reply' | 'payment'
  url?: string
  option_key?: string
  reply_text?: string
  ask_for_response?: boolean
  // New: payment button fields
  payment_plan_id?: number | null
  payment_custom_price?: number | null
  payment_bonus_tokens?: number | null
}
```

**Step 3: Verify no TypeScript errors**

```bash
cd admin-webapp && npx tsc --noEmit 2>&1 | head -30
```

**Step 4: Commit**

```bash
git add admin-webapp/src/types/index.ts
git commit -m "feat: add payment button type to BroadcastButton"
```

---

## Task 2: Update `ButtonEditor.tsx` to support `payment` type

**Files:**
- Modify: `admin-webapp/src/components/broadcast/ButtonEditor.tsx`

**Step 1: Add subscription plans state**

At the top of the `ButtonEditor` component (after existing `useState` calls), add:

```typescript
import { api } from '@/services/api'

interface SubscriptionPlan {
  id: number
  name: string
  price_rub: number
  tokens_included: number
  is_active: boolean
}
```

And inside the component:

```typescript
const [plans, setPlans] = useState<SubscriptionPlan[]>([])
const hasPaymentButton = buttons.some((b) => b.type === 'payment')

useEffect(() => {
  if (hasPaymentButton && plans.length === 0) {
    api.getSubscriptionPlans().then((data) => {
      setPlans((data.plans as SubscriptionPlan[]).filter((p) => p.is_active))
    }).catch(() => {})
  }
}, [hasPaymentButton, plans.length])
```

**Step 2: Add `payment` to type dropdown**

In the `<select>` for button type (currently has `quick_reply` and `url` options), add:

```tsx
<option value="payment">💳 Оплата</option>
```

**Step 3: Handle type switch to `payment`**

In the `onChange` handler for the type `<select>`, extend to handle `payment`:

```typescript
onChange={(e) => {
  const newType = e.target.value as 'url' | 'quick_reply' | 'payment'
  const optIdx = buttons.length
  updateButton(rowIdx, btnIdx, {
    type: newType,
    url: newType === 'url' ? (btn.url || '') : undefined,
    option_key: btn.option_key || `opt_${optIdx}`,
    reply_text: newType !== 'quick_reply' ? undefined : btn.reply_text,
    payment_plan_id: newType === 'payment' ? (btn.payment_plan_id ?? null) : undefined,
    payment_custom_price: newType === 'payment' ? (btn.payment_custom_price ?? null) : undefined,
    payment_bonus_tokens: newType === 'payment' ? (btn.payment_bonus_tokens ?? null) : undefined,
  })
}}
```

**Step 4: Add payment button UI section**

After the `{btn.type === 'url' && ...}` block and `{btn.type === 'quick_reply' && ...}` block, add:

```tsx
{btn.type === 'payment' && (
  <div className={styles.paymentSection}>
    <select
      className={styles.typeSelect}
      value={btn.payment_plan_id ?? ''}
      onChange={(e) => updateButton(rowIdx, btnIdx, {
        payment_plan_id: e.target.value ? Number(e.target.value) : null
      })}
    >
      <option value="">Выберите тариф</option>
      {plans.map((p) => (
        <option key={p.id} value={p.id}>
          {p.name} — {p.price_rub}₽/мес
        </option>
      ))}
    </select>
    <div className={styles.paymentFields}>
      <input
        className={styles.urlInput}
        type="number"
        placeholder={
          btn.payment_plan_id
            ? String(plans.find((p) => p.id === btn.payment_plan_id)?.price_rub ?? 'цена')
            : 'Цена (₽)'
        }
        value={btn.payment_custom_price ?? ''}
        min={1}
        onChange={(e) => updateButton(rowIdx, btnIdx, {
          payment_custom_price: e.target.value ? Number(e.target.value) : null
        })}
      />
      <input
        className={styles.urlInput}
        type="number"
        placeholder="Бонус токенов"
        value={btn.payment_bonus_tokens ?? ''}
        min={0}
        onChange={(e) => updateButton(rowIdx, btnIdx, {
          payment_bonus_tokens: e.target.value ? Number(e.target.value) : null
        })}
      />
    </div>
    {btn.payment_plan_id && (() => {
      const plan = plans.find((p) => p.id === btn.payment_plan_id)
      if (!plan) return null
      const price = btn.payment_custom_price ?? plan.price_rub
      const tokens = plan.tokens_included + (btn.payment_bonus_tokens ?? 0)
      const discount = btn.payment_custom_price && btn.payment_custom_price < plan.price_rub
        ? Math.round((1 - btn.payment_custom_price / plan.price_rub) * 100)
        : 0
      return (
        <div className={styles.paymentHint}>
          {discount > 0
            ? <><s>{plan.price_rub}₽</s> → <b>{price}₽</b>/мес (скидка {discount}%)</>
            : <><b>{price}₽</b>/мес</>
          }
          {' · '}{tokens} токенов/мес
        </div>
      )
    })()}
    <div className={styles.urlHint}>
      Пользователь получит персональную ссылку оплаты на YooKassa
    </div>
  </div>
)}
```

**Step 5: Add CSS for new elements**

In `ButtonEditor.module.css`, add:

```css
.paymentSection {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}

.paymentFields {
  display: flex;
  gap: 6px;
}

.paymentFields .urlInput {
  flex: 1;
}

.paymentHint {
  font-size: 11px;
  color: var(--text-secondary);
  padding: 4px 6px;
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
}
```

**Step 6: Check in browser**

- Navigate to `http://localhost:5174` → Рассылки → Новая рассылка → Добавить кнопки → Добавить ряд → Тип: 💳 Оплата
- Verify: plan dropdown appears, price and bonus fields appear, hint text shows

**Step 7: Commit**

```bash
git add admin-webapp/src/components/broadcast/ButtonEditor.tsx admin-webapp/src/components/broadcast/ButtonEditor.module.css
git commit -m "feat: add payment button type to ButtonEditor UI"
```

---

## Task 3: Update `build_inline_keyboard()` in `broadcast_sender.py`

**Files:**
- Modify: `src/services/broadcast_sender.py`

**Context:** `build_inline_keyboard()` is at line 96-154. It currently handles `url` and `quick_reply` types. We need to handle `payment` type: call `create_subscription_payment_custom()` and use the returned confirmation URL as the button URL.

**Step 1: Make `build_inline_keyboard` async**

The function needs to call `create_subscription_payment_custom()` which is async. Change the signature:

```python
async def build_inline_keyboard(
    broadcast_id: int,
    buttons: list,
    telegram_user_id: int = 0,
    user_id: int = 0,
) -> Optional[InlineKeyboardMarkup]:
```

**Step 2: Add payment button handling inside the row loop**

After the existing `elif btn['type'] == 'quick_reply':` block, add:

```python
elif btn['type'] == 'payment' and btn.get('payment_plan_id') and user_id and telegram_user_id:
    try:
        from src.services.payments.payment_service import create_subscription_payment_custom
        payment_result = await create_subscription_payment_custom(
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            plan_id=btn['payment_plan_id'],
            custom_price=btn.get('payment_custom_price'),
            bonus_tokens=btn.get('payment_bonus_tokens'),
        )
        payment_url = payment_result.get('confirmation_url')
        if payment_url:
            row_buttons.append(InlineKeyboardButton(
                text=btn['text'] or '💳 Оплатить',
                url=payment_url,
            ))
    except Exception as e:
        logger.warning(f"Failed to create payment for broadcast button: {e}")
```

**Step 3: Update all callers of `build_inline_keyboard`**

Search for all usages:

```bash
grep -n "build_inline_keyboard" src/services/broadcast_sender.py
```

For each call site inside `execute_broadcast` and `send_to_single_user`, add `await` and pass `user_id`:

In `execute_broadcast` (find the line with `build_inline_keyboard`):
```python
# Before (approx):
keyboard = build_inline_keyboard(broadcast_id, buttons, r['telegram_user_id'])
# After:
keyboard = await build_inline_keyboard(broadcast_id, buttons, r['telegram_user_id'], r['user_id'])
```

In `send_to_single_user`:
```python
# Before:
keyboard = build_inline_keyboard(broadcast_id, buttons, telegram_user_id)
# After:
keyboard = await build_inline_keyboard(broadcast_id, buttons, telegram_user_id, user_id)
```

**Step 4: Verify no syntax errors**

```bash
python -c "from src.services.broadcast_sender import build_inline_keyboard; print('OK')"
```

**Step 5: Commit**

```bash
git add src/services/broadcast_sender.py
git commit -m "feat: payment button type in broadcast_sender generates personal YooKassa URL"
```

---

## Task 4: Handle `payment` button in `send_to_single_user` (funnel triggers)

**Files:**
- Modify: `src/services/funnel_trigger_sender.py`

**Context:** `send_to_single_user` is called by funnel trigger sender. It also calls `build_inline_keyboard`. Now that it's async, update the call there too.

**Step 1: Find the call in funnel_trigger_sender.py**

```bash
grep -n "build_inline_keyboard\|send_to_single_user" src/services/funnel_trigger_sender.py
```

**Step 2: Ensure `user_id` is passed through**

The `send_to_single_user` function signature in `broadcast_sender.py` already accepts `user_id`. Verify it's being passed from the trigger sender:

```python
# In funnel_trigger_sender.py:
from src.services.broadcast_sender import send_to_single_user
await send_to_single_user(trigger['broadcast_id'], user_id, telegram_user_id)
```

This should already be correct since `user_id` is a parameter of `execute_stage_triggers`.

**Step 3: Commit**

```bash
git add src/services/funnel_trigger_sender.py
git commit -m "fix: pass user_id to send_to_single_user for payment button support"
```

---

## Task 5: Add "Create broadcast" modal to `StageTriggerEditor`

**Files:**
- Modify: `admin-webapp/src/components/funnel/StageTriggerEditor.tsx`
- Modify: `admin-webapp/src/components/funnel/StageTriggerEditor.module.css`
- Modify: `admin-webapp/src/store/broadcastStore.ts` (ensure `createBroadcast` returns the new broadcast)

**Step 1: Import BroadcastForm**

At the top of `StageTriggerEditor.tsx`, add:

```typescript
import { BroadcastForm } from '@/components/broadcast/BroadcastForm'
import { useBroadcastStore } from '@/store/broadcastStore'
```

**Step 2: Add modal state**

Inside the `StageTriggerEditor` component, add:

```typescript
const { fetchBroadcasts } = useBroadcastStore()
const [showCreateBroadcast, setShowCreateBroadcast] = useState(false)
```

**Step 3: Add "Create broadcast" button in the broadcast dropdown section**

In the JSX, after the `<select className={styles.selectBroadcast}>` element, add:

```tsx
<button
  type="button"
  className={styles.createBroadcastBtn}
  onClick={() => setShowCreateBroadcast(true)}
>
  + Создать рассылку
</button>
```

**Step 4: Add modal overlay**

At the bottom of the component's return, before the closing `</div>`, add:

```tsx
{showCreateBroadcast && (
  <div className={styles.modalBackdrop} onClick={() => setShowCreateBroadcast(false)}>
    <div className={styles.modalPanel} onClick={(e) => e.stopPropagation()}>
      <div className={styles.modalHeader}>
        <span>Новая рассылка</span>
        <button
          className={styles.modalCloseBtn}
          onClick={() => setShowCreateBroadcast(false)}
        >
          ✕
        </button>
      </div>
      <div className={styles.modalBody}>
        <BroadcastForm
          broadcast={null}
          onSaved={async () => {
            setShowCreateBroadcast(false)
            // Reload broadcasts list so new one appears in dropdown
            const data = await api.getBroadcasts()
            const all = data.broadcasts.filter((b: any) =>
              b.message_text || b.photo_path || b.poll_question
            )
            setBroadcasts(all)
            // Auto-select the newest broadcast (highest id)
            if (all.length > 0) {
              const newest = all.reduce((a: any, b: any) => (a.id > b.id ? a : b))
              setSelectedBroadcastId(newest.id)
            }
          }}
          onCancel={() => setShowCreateBroadcast(false)}
        />
      </div>
    </div>
  </div>
)}
```

**Step 5: Add CSS for modal**

In `StageTriggerEditor.module.css`, add:

```css
/* Create broadcast button */
.createBroadcastBtn {
  width: 100%;
  padding: 5px 8px;
  font-size: 11px;
  color: var(--accent-primary);
  background: var(--accent-primary-light, #f0fdf4);
  border: 1px dashed var(--accent-primary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s;
  text-align: center;
}

.createBroadcastBtn:hover {
  background: var(--accent-primary);
  color: white;
}

/* Modal */
.modalBackdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 40px;
}

.modalPanel {
  background: var(--bg-primary);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
  width: 680px;
  max-width: calc(100vw - 40px);
  max-height: calc(100vh - 80px);
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.modalHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-default);
  font-weight: 600;
  font-size: 14px;
}

.modalCloseBtn {
  background: none;
  border: none;
  font-size: 14px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.modalCloseBtn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.modalBody {
  overflow-y: auto;
  flex: 1;
  padding: 16px;
}
```

**Step 6: Test in browser**

1. Navigate to `http://localhost:5174` → Воронки → выбрать воронку → кликнуть на этап → "Добавить триггер"
2. Verify "Создать рассылку" button appears below the broadcast dropdown
3. Click "Создать рассылку" → modal opens with full BroadcastForm
4. Create a draft broadcast → click save → modal closes → new broadcast auto-selected in dropdown

**Step 7: Commit**

```bash
git add admin-webapp/src/components/funnel/StageTriggerEditor.tsx admin-webapp/src/components/funnel/StageTriggerEditor.module.css
git commit -m "feat: add 'Create broadcast' modal to StageTriggerEditor"
```

---

## Task 6: Ensure `api.getBroadcasts()` is usable without store

**Files:**
- Check: `admin-webapp/src/services/api.ts`

**Step 1: Verify getBroadcasts exists in api.ts**

```bash
grep -n "getBroadcasts" admin-webapp/src/services/api.ts | head -5
```

If it exists and returns `{ broadcasts: Broadcast[] }`, no changes needed.

**Step 2: Commit if no changes needed**

No commit needed for this task if api.ts already has it.

---

## Task 7: Final TypeScript build check

**Step 1: Run type check**

```bash
cd admin-webapp && npx tsc --noEmit 2>&1
```

Expected: no errors.

**Step 2: If errors, fix them**

Common issues:
- `build_inline_keyboard` changed to async — Python only, no TS impact
- `BroadcastForm` props — `onSaved` is `() => void`, but we pass async fn → safe (TS allows `() => Promise<void>` where `() => void` is expected)

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: broadcast payment button + create-in-trigger modal (v1.5.5)"
```

---

## Verification Checklist

1. **Payment button in broadcast:**
   - Create a broadcast → Add buttons → Тип: 💳 Оплата → select plan → set custom price → preview shows crossed-out price
   - Send to test recipient → Telegram message has inline button with YooKassa URL
   - Click button → redirects to real YooKassa payment page
   - Complete payment → webhook fires → subscription activated with bonus_tokens

2. **Create broadcast modal in trigger editor:**
   - Funnel page → Stage → Add trigger → "Создать рассылку" button visible
   - Click → modal opens with full BroadcastForm (title, text editor, photo, buttons, etc.)
   - Save draft → modal closes → new broadcast selected in trigger dropdown
   - Click Cancel → modal closes, no broadcast created

3. **No regression:**
   - Existing URL and quick_reply buttons still work
   - Existing broadcasts send correctly
   - Funnel triggers still fire correctly
