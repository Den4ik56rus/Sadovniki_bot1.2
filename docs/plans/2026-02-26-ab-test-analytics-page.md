# A/B Test Analytics Page — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated "A/B тест" page under Analytics in the sidebar, showing funnel conversion per stage (Новые → Попробовали → Триал закончился → Оплатили) for both variants A and B in amoCRM-style layout.

**Architecture:** Extend the existing `/api/admin/ab-test/stats` endpoint to return per-stage counts (`tried`, `trial_ended`). Extend the Zustand store type. Create a new `ABTestPage` component with horizontal funnel table + progress bars. Wire into sidebar navigation and App.tsx routing.

**Tech Stack:** React + TypeScript, CSS Modules, Zustand, Python/aiohttp API

---

### Task 1: Extend API — add `tried` and `trial_ended` to stats

**Files:**
- Modify: `src/api/handlers/ab_test.py`

**Step 1: Replace the SQL query**

In `src/api/handlers/ab_test.py`, replace the existing `rows = await conn.fetch(...)` call with:

```python
rows = await conn.fetch("""
    SELECT
        u.funnel_variant,
        COUNT(DISTINCT u.id) AS users,
        COUNT(DISTINCT CASE WHEN u.crm_status IN ('tried','trial_ended','paid') THEN u.id END) AS tried,
        COUNT(DISTINCT CASE WHEN u.crm_status IN ('trial_ended','paid') THEN u.id END) AS trial_ended,
        COUNT(DISTINCT p.user_id) AS paid
    FROM users u
    LEFT JOIN payments p ON p.user_id = u.id AND p.status = 'paid'
    WHERE u.funnel_variant IS NOT NULL
    GROUP BY u.funnel_variant
    ORDER BY u.funnel_variant
""")
```

**Step 2: Update the variants dict construction**

Replace the loop that builds `variants` dict:

```python
variants = {}
for row in rows:
    variant = row['funnel_variant']
    users = row['users']
    paid = row['paid']
    tried = row['tried']
    trial_ended = row['trial_ended']
    conversion = round(paid / users * 100, 1) if users > 0 else 0.0
    variants[variant] = {
        'users': users,
        'tried': tried,
        'trial_ended': trial_ended,
        'paid': paid,
        'conversion': conversion
    }

# Гарантировать наличие обоих вариантов в ответе
for v in ('A', 'B'):
    if v not in variants:
        variants[v] = {'users': 0, 'tried': 0, 'trial_ended': 0, 'paid': 0, 'conversion': 0.0}
```

**Step 3: Verify manually**

```bash
curl http://localhost:8080/api/admin/ab-test/stats | python3 -m json.tool
```

Expected: response now includes `tried` and `trial_ended` fields in each variant object.

**Step 4: Commit**

```bash
git add src/api/handlers/ab_test.py
git commit -m "feat: extend ab-test stats API with tried/trial_ended funnel stages"
```

---

### Task 2: Extend Zustand store type

**Files:**
- Modify: `admin-webapp/src/store/index.ts` (around line 937)

**Step 1: Update `ABTestVariantStats` interface**

Find the interface (around line 937) and add two new fields:

```ts
interface ABTestVariantStats {
  users: number
  tried: number        // NEW
  trial_ended: number  // NEW
  paid: number
  conversion: number
}
```

**Step 2: Update default fallback values**

In `fetchStats`, find the two fallback lines and update:

```ts
// Before (line ~26 in ABTestSection.tsx, mirrored in store):
const a = stats?.variants.A ?? { users: 0, paid: 0, conversion: 0 }
const b = stats?.variants.B ?? { users: 0, paid: 0, conversion: 0 }

// In store index.ts the default object in setVariant doesn't need updating,
// but any place that constructs ABTestVariantStats manually should now include tried/trial_ended.
```

In `admin-webapp/src/store/index.ts`, the `fetchStats` function uses raw fetch — no changes needed there. The TypeScript interface change is sufficient; the API response will now include the new fields.

**Step 3: Commit**

```bash
git add admin-webapp/src/store/index.ts
git commit -m "feat: extend ABTestVariantStats type with tried/trial_ended fields"
```

---

### Task 3: Add `'ab-test'` to View type

**Files:**
- Modify: `admin-webapp/src/types/index.ts` (line 230)

**Step 1: Extend View union**

Find line 230:
```ts
export type View = 'dashboard' | 'crm' | 'messages' | 'buyers' | 'tasks' | 'lists' | 'stats' | 'settings' | 'users' | 'live' | 'documents' | 'expenses' | 'rag-docs' | 'prompts' | 'prompt-preview' | 'payments' | 'invite-links' | 'guides' | 'moderation'
```

Add `'ab-test'` to the end:
```ts
export type View = 'dashboard' | 'crm' | 'messages' | 'buyers' | 'tasks' | 'lists' | 'stats' | 'settings' | 'users' | 'live' | 'documents' | 'expenses' | 'rag-docs' | 'prompts' | 'prompt-preview' | 'payments' | 'invite-links' | 'guides' | 'moderation' | 'ab-test'
```

**Step 2: Commit**

```bash
git add admin-webapp/src/types/index.ts
git commit -m "feat: add ab-test to View type"
```

---

### Task 4: Create ABTestPage component

**Files:**
- Create: `admin-webapp/src/components/abtest/ABTestPage.tsx`
- Create: `admin-webapp/src/components/abtest/ABTestPage.module.css`

**Step 1: Create the CSS module**

Create `admin-webapp/src/components/abtest/ABTestPage.module.css`:

```css
.container {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.title {
  font-size: 20px;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary, #111);
}

/* Toggle buttons */
.toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toggleLabel {
  font-size: 14px;
  color: var(--text-secondary, #6b7280);
}

.toggleButtons {
  display: flex;
  gap: 4px;
  background: var(--bg-secondary, #f3f4f6);
  border-radius: 6px;
  padding: 3px;
}

.toggleBtn {
  padding: 6px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary, #6b7280);
  background: transparent;
  transition: all 0.15s;
}

.toggleBtn:hover {
  color: var(--text-primary, #111);
}

.toggleBtn.active {
  background: var(--primary, #4A7C59);
  color: #fff;
}

/* Funnel table */
.funnelCard {
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 24px;
}

.funnelTable {
  width: 100%;
  border-collapse: collapse;
}

/* Stage header row */
.stageHeaderRow th {
  padding: 0;
  font-weight: 600;
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stageHeaderRow th:first-child {
  width: 120px;
  min-width: 100px;
}

.stageHeader {
  padding: 14px 16px;
  text-align: center;
  border-left: 1px solid var(--border-color, #e5e7eb);
  color: #fff;
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* Variant rows */
.variantRow {
  border-top: 2px solid var(--border-color, #e5e7eb);
}

.variantRow.activeVariant {
  background: var(--bg-highlight, #f0fdf4);
}

.variantLabel {
  padding: 16px;
  font-weight: 700;
  font-size: 14px;
  color: var(--text-primary, #111);
  vertical-align: middle;
  white-space: nowrap;
  border-right: 1px solid var(--border-color, #e5e7eb);
}

.activeDot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--primary, #4A7C59);
  margin-left: 6px;
  vertical-align: middle;
}

.stageCell {
  padding: 16px;
  text-align: center;
  border-left: 1px solid var(--border-color, #e5e7eb);
  vertical-align: middle;
  min-width: 140px;
}

.stageCount {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary, #111);
  display: block;
  margin-bottom: 6px;
}

.stageCountLabel {
  font-size: 11px;
  color: var(--text-secondary, #9ca3af);
  margin-bottom: 8px;
  display: block;
}

.progressWrap {
  height: 6px;
  background: var(--bg-secondary, #f3f4f6);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 4px;
}

.progressBar {
  height: 100%;
  border-radius: 3px;
  transition: width 0.4s ease;
}

.progressPercent {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
  font-weight: 500;
}

/* Conversion cell (last column) */
.conversionCell {
  padding: 16px;
  text-align: center;
  border-left: 1px solid var(--border-color, #e5e7eb);
  vertical-align: middle;
  min-width: 120px;
}

.conversionValue {
  font-size: 24px;
  font-weight: 800;
  display: block;
  margin-bottom: 4px;
}

.conversionLabel {
  font-size: 11px;
  color: var(--text-secondary, #9ca3af);
}

/* Summary cards */
.summaryRow {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.summaryCard {
  flex: 1;
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color, #e5e7eb);
  border-radius: 10px;
  padding: 20px;
  text-align: center;
}

.summaryCard.winner {
  border-color: var(--primary, #4A7C59);
  background: var(--bg-highlight, #f0fdf4);
}

.summaryVariant {
  font-size: 13px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary, #6b7280);
  margin-bottom: 4px;
}

.summaryConversion {
  font-size: 32px;
  font-weight: 800;
  color: var(--text-primary, #111);
}

.summaryUnit {
  font-size: 16px;
  font-weight: 400;
  color: var(--text-secondary, #6b7280);
}

.summaryUsers {
  font-size: 13px;
  color: var(--text-secondary, #9ca3af);
  margin-top: 4px;
}

.winnerBadge {
  display: inline-block;
  background: var(--primary, #4A7C59);
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 10px;
  margin-top: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.loading {
  color: var(--text-secondary, #6b7280);
  font-size: 14px;
  padding: 40px 24px;
  text-align: center;
}
```

**Step 2: Create ABTestPage.tsx**

Create `admin-webapp/src/components/abtest/ABTestPage.tsx`:

```tsx
import { useEffect } from 'react'
import { useABTestStore } from '@/store'
import styles from './ABTestPage.module.css'

const STAGE_COLORS = {
  users:       '#3B82F6',  // синий — Новые
  tried:       '#8B5CF6',  // фиолетовый — Попробовали
  trial_ended: '#F59E0B',  // жёлтый — Триал закончился
  paid:        '#22C55E',  // зелёный — Оплатили
}

const STAGE_LABELS = {
  users:       'Новые',
  tried:       'Попробовали',
  trial_ended: 'Триал закончился',
  paid:        'Оплатили',
}

type StageKey = keyof typeof STAGE_COLORS

export function ABTestPage() {
  const { stats, loading, fetchStats, setVariant } = useABTestStore()

  useEffect(() => {
    fetchStats()
  }, [])

  const handleSwitch = async (variant: 'A' | 'B') => {
    if (stats?.active_variant === variant) return
    const label = variant === 'B' ? 'Тип Б' : 'Тип А'
    const confirmed = window.confirm(
      `Все новые пользователи будут получать ${label}. Продолжить?`
    )
    if (!confirmed) return
    await setVariant(variant)
    await fetchStats()
  }

  if (loading && !stats) {
    return <div className={styles.loading}>Загрузка...</div>
  }

  const active = stats?.active_variant ?? 'A'
  const a = stats?.variants.A ?? { users: 0, tried: 0, trial_ended: 0, paid: 0, conversion: 0 }
  const b = stats?.variants.B ?? { users: 0, tried: 0, trial_ended: 0, paid: 0, conversion: 0 }

  const stages: StageKey[] = ['users', 'tried', 'trial_ended', 'paid']

  const getPercent = (count: number, total: number) =>
    total > 0 ? Math.round((count / total) * 100) : 0

  const winnerVariant = a.conversion >= b.conversion ? 'A' : 'B'

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>A/B тест воронок</h1>
        <div className={styles.toggle}>
          <span className={styles.toggleLabel}>Воронка для новых:</span>
          <div className={styles.toggleButtons}>
            <button
              className={`${styles.toggleBtn} ${active === 'A' ? styles.active : ''}`}
              onClick={() => handleSwitch('A')}
            >
              Тип А
            </button>
            <button
              className={`${styles.toggleBtn} ${active === 'B' ? styles.active : ''}`}
              onClick={() => handleSwitch('B')}
            >
              Тип Б
            </button>
          </div>
        </div>
      </div>

      {/* Summary cards */}
      <div className={styles.summaryRow}>
        {(['A', 'B'] as const).map((variant) => {
          const v = variant === 'A' ? a : b
          const isWinner = winnerVariant === variant && (a.users > 0 || b.users > 0)
          return (
            <div
              key={variant}
              className={`${styles.summaryCard} ${isWinner ? styles.winner : ''}`}
            >
              <div className={styles.summaryVariant}>
                Тип {variant} {active === variant && '●'}
              </div>
              <div className={styles.summaryConversion}>
                {v.conversion}<span className={styles.summaryUnit}>%</span>
              </div>
              <div className={styles.summaryUsers}>{v.users} пользователей</div>
              {isWinner && <div className={styles.winnerBadge}>Лидирует</div>}
            </div>
          )
        })}
      </div>

      {/* Funnel table */}
      <div className={styles.funnelCard}>
        <table className={styles.funnelTable}>
          <thead>
            <tr className={styles.stageHeaderRow}>
              <th />
              {stages.map((stage) => (
                <th key={stage}>
                  <div
                    className={styles.stageHeader}
                    style={{ background: STAGE_COLORS[stage] }}
                  >
                    {STAGE_LABELS[stage]}
                  </div>
                </th>
              ))}
              <th>
                <div className={styles.stageHeader} style={{ background: '#4A7C59' }}>
                  Конверсия
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {(['A', 'B'] as const).map((variant) => {
              const v = variant === 'A' ? a : b
              return (
                <tr
                  key={variant}
                  className={`${styles.variantRow} ${active === variant ? styles.activeVariant : ''}`}
                >
                  <td className={styles.variantLabel}>
                    Тип {variant}
                    {active === variant && <span className={styles.activeDot} />}
                  </td>
                  {stages.map((stage) => {
                    const count = v[stage as keyof typeof v] as number
                    const pct = getPercent(count, v.users)
                    return (
                      <td key={stage} className={styles.stageCell}>
                        <span className={styles.stageCount}>{count}</span>
                        <span className={styles.stageCountLabel}>чел.</span>
                        <div className={styles.progressWrap}>
                          <div
                            className={styles.progressBar}
                            style={{
                              width: `${pct}%`,
                              background: STAGE_COLORS[stage],
                            }}
                          />
                        </div>
                        <span className={styles.progressPercent}>{pct}%</span>
                      </td>
                    )
                  })}
                  <td className={styles.conversionCell}>
                    <span
                      className={styles.conversionValue}
                      style={{ color: STAGE_COLORS.paid }}
                    >
                      {v.conversion}%
                    </span>
                    <span className={styles.conversionLabel}>конверсия</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

**Step 3: Commit**

```bash
git add admin-webapp/src/components/abtest/ABTestPage.tsx admin-webapp/src/components/abtest/ABTestPage.module.css
git commit -m "feat: add ABTestPage component with amoCRM-style funnel table"
```

---

### Task 5: Wire into navigation and routing

**Files:**
- Modify: `admin-webapp/src/components/layout/Sidebar.tsx` (line 132–135)
- Modify: `admin-webapp/src/App.tsx`

**Step 1: Add `ab-test` to stats-group in Sidebar**

In `Sidebar.tsx`, find the `stats-group` submenu (around line 129):

```ts
{
  id: 'stats-group',
  icon: Icons.stats,
  label: 'Аналитика',
  submenu: [
    { id: 'stats', label: 'Статистика' },
    { id: 'invite-links', label: 'Инвайт-ссылки' },
  ],
},
```

Replace with:

```ts
{
  id: 'stats-group',
  icon: Icons.stats,
  label: 'Аналитика',
  submenu: [
    { id: 'stats', label: 'Статистика' },
    { id: 'invite-links', label: 'Инвайт-ссылки' },
    { id: 'ab-test', label: 'A/B тест' },
  ],
},
```

**Step 2: Add ABTestPage import and route in App.tsx**

Add import after existing abtest imports (near the top of `App.tsx`):

```tsx
import { ABTestPage } from '@/components/abtest/ABTestPage'
```

Add route after `{currentView === 'invite-links' && <InviteLinksPage />}` (around line 74):

```tsx
{/* A/B тест воронок */}
{currentView === 'ab-test' && <ABTestPage />}
```

**Step 3: Commit**

```bash
git add admin-webapp/src/components/layout/Sidebar.tsx admin-webapp/src/App.tsx
git commit -m "feat: add A/B тест to Analytics navigation menu"
```

---

### Task 6: Verify in browser with Playwright

**Step 1: Navigate to the new page**

```
browser_navigate → http://localhost:5174
```

**Step 2: Click "Аналитика" in sidebar, then "A/B тест"**

Use `browser_snapshot` to find the submenu items, click `A/B тест`.

**Step 3: Take screenshot**

```
browser_take_screenshot
```

Expected: page loads with "A/B тест воронок" heading, toggle buttons, summary cards, funnel table with 4 stage columns.

**Step 4: Check for console errors**

```
browser_console_messages level=error
```

Expected: no errors.

**Step 5: If data shows zeros — that's expected** (production data has real users, local dev may have no `funnel_variant` set). The UI structure should be correct regardless.

---

### Task 7: Update version

**Files:**
- Modify: `admin-webapp/package.json` (version field)

**Step 1: Bump version by 0.1**

Find current version in `admin-webapp/package.json` and increment by 0.1.

**Step 2: Commit**

```bash
git add admin-webapp/package.json
git commit -m "chore: bump version after ab-test analytics page"
```
