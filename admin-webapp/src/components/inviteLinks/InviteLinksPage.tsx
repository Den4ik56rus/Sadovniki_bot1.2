// Invite Links Page — управление инвайт-ссылками для отслеживания кампаний

import { useEffect, useState, useCallback } from 'react'
import { format, startOfMonth, endOfMonth, subMonths, addMonths, parse } from 'date-fns'
import { ru } from 'date-fns/locale'
import { useInviteLinksStore } from '@/store/inviteLinksStore'
import { getParam, setParams } from '@/router'
import type { InviteLink } from '@/types'
import styles from './InviteLinksPage.module.css'

type ViewMode = 'month' | 'all'

export function InviteLinksPage() {
  const {
    links,
    summary,
    isLoading,
    error,
    fetchLinks,
    setDateRange,
    createLink,
    updateLink,
    toggleLinkActive,
    deleteLink,
  } = useInviteLinksStore()

  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    const urlMode = getParam('view')
    return urlMode === 'month' ? 'month' : 'all'
  })
  const [currentDate, setCurrentDate] = useState(() => {
    const urlMonth = getParam('month')
    if (urlMonth) {
      try { return parse(urlMonth + '-01', 'yyyy-MM-dd', new Date()) } catch { /* fallback */ }
    }
    return new Date()
  })
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newLinkName, setNewLinkName] = useState('')
  const [newBonusTokens, setNewBonusTokens] = useState(0)
  const [newDiscountPercent, setNewDiscountPercent] = useState(0)
  const [newDiscountDays, setNewDiscountDays] = useState(0)
  const [newMaxUsers, setNewMaxUsers] = useState(0)
  const [newTokenBonusPercent, setNewTokenBonusPercent] = useState(0)
  const [newAllowExisting, setNewAllowExisting] = useState(false)
  const [newExistingBonusTokens, setNewExistingBonusTokens] = useState(true)
  const [newExistingDiscount, setNewExistingDiscount] = useState(true)
  const [newExistingTokenBonus, setNewExistingTokenBonus] = useState(true)
  const [creating, setCreating] = useState(false)
  const [copiedId, setCopiedId] = useState<number | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editingName, setEditingName] = useState('')
  const [editingBonusTokens, setEditingBonusTokens] = useState(0)
  const [editingDiscountPercent, setEditingDiscountPercent] = useState(0)
  const [editingDiscountDays, setEditingDiscountDays] = useState(0)
  const [editingMaxUsers, setEditingMaxUsers] = useState(0)
  const [editingTokenBonusPercent, setEditingTokenBonusPercent] = useState(0)
  const [editingAllowExisting, setEditingAllowExisting] = useState(false)
  const [editingExistingBonusTokens, setEditingExistingBonusTokens] = useState(true)
  const [editingExistingDiscount, setEditingExistingDiscount] = useState(true)
  const [editingExistingTokenBonus, setEditingExistingTokenBonus] = useState(true)

  // Date range label
  const dateRangeLabel = `${format(startOfMonth(currentDate), 'd MMM yyyy', { locale: ru })} – ${format(endOfMonth(currentDate), 'd MMM yyyy', { locale: ru })}`

  const goToPrevMonth = useCallback(() => {
    const newDate = subMonths(currentDate, 1)
    setCurrentDate(newDate)
    setParams({ month: format(newDate, 'yyyy-MM') })
    setDateRange(
      format(startOfMonth(newDate), 'yyyy-MM-dd'),
      format(endOfMonth(newDate), 'yyyy-MM-dd'),
    )
  }, [currentDate, setDateRange])

  const goToNextMonth = useCallback(() => {
    const newDate = addMonths(currentDate, 1)
    setCurrentDate(newDate)
    setParams({ month: format(newDate, 'yyyy-MM') })
    setDateRange(
      format(startOfMonth(newDate), 'yyyy-MM-dd'),
      format(endOfMonth(newDate), 'yyyy-MM-dd'),
    )
  }, [currentDate, setDateRange])

  const switchToMonth = useCallback(() => {
    setViewMode('month')
    setParams({ view: 'month', month: format(currentDate, 'yyyy-MM') })
    setDateRange(
      format(startOfMonth(currentDate), 'yyyy-MM-dd'),
      format(endOfMonth(currentDate), 'yyyy-MM-dd'),
    )
  }, [currentDate, setDateRange])

  const switchToAll = useCallback(() => {
    setViewMode('all')
    setParams({ view: null, month: null })
    setDateRange(undefined, undefined)
  }, [setDateRange])

  // Set initial date range from URL state on mount
  useEffect(() => {
    if (viewMode === 'month') {
      setDateRange(
        format(startOfMonth(currentDate), 'yyyy-MM-dd'),
        format(endOfMonth(currentDate), 'yyyy-MM-dd'),
      )
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Fetch on mount
  useEffect(() => {
    fetchLinks()
  }, [fetchLinks])

  // Subscribe to date changes
  useEffect(() => {
    const unsub = useInviteLinksStore.subscribe(
      (state, prevState) => {
        if (state.startDate !== prevState.startDate || state.endDate !== prevState.endDate) {
          state.fetchLinks()
        }
      },
    )
    return unsub
  }, [])

  const handleCreate = async () => {
    if (!newLinkName.trim()) return
    setCreating(true)
    const ok = await createLink({
      name: newLinkName.trim(),
      bonus_tokens: newBonusTokens,
      discount_percent: newDiscountPercent,
      discount_duration_days: newDiscountDays,
      max_users: newMaxUsers,
      token_bonus_percent: newTokenBonusPercent,
      allow_existing_users: newAllowExisting,
      existing_user_bonus_tokens: newExistingBonusTokens,
      existing_user_discount: newExistingDiscount,
      existing_user_token_bonus: newExistingTokenBonus,
    })
    setCreating(false)
    if (ok) {
      setNewLinkName('')
      setNewBonusTokens(0)
      setNewDiscountPercent(0)
      setNewDiscountDays(0)
      setNewMaxUsers(0)
      setNewTokenBonusPercent(0)
      setNewAllowExisting(false)
      setNewExistingBonusTokens(true)
      setNewExistingDiscount(true)
      setNewExistingTokenBonus(true)
      setShowCreateForm(false)
    }
  }

  const handleCopy = async (deepLink: string, id: number) => {
    try {
      await navigator.clipboard.writeText(deepLink)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    } catch {
      const input = document.createElement('input')
      input.value = deepLink
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
      setCopiedId(id)
      setTimeout(() => setCopiedId(null), 2000)
    }
  }

  const handleStartEdit = (link: InviteLink) => {
    setEditingId(link.id)
    setEditingName(link.name)
    setEditingBonusTokens(link.bonus_tokens || 0)
    setEditingDiscountPercent(link.discount_percent || 0)
    setEditingDiscountDays(link.discount_duration_days || 0)
    setEditingMaxUsers(link.max_users || 0)
    setEditingTokenBonusPercent(link.token_bonus_percent || 0)
    setEditingAllowExisting(link.allow_existing_users || false)
    setEditingExistingBonusTokens(link.existing_user_bonus_tokens !== false)
    setEditingExistingDiscount(link.existing_user_discount !== false)
    setEditingExistingTokenBonus(link.existing_user_token_bonus !== false)
  }

  const handleSaveEdit = async () => {
    if (!editingId || !editingName.trim()) return
    await updateLink(editingId, {
      name: editingName.trim(),
      bonus_tokens: editingBonusTokens,
      discount_percent: editingDiscountPercent,
      discount_duration_days: editingDiscountDays,
      max_users: editingMaxUsers,
      token_bonus_percent: editingTokenBonusPercent,
      allow_existing_users: editingAllowExisting,
      existing_user_bonus_tokens: editingExistingBonusTokens,
      existing_user_discount: editingExistingDiscount,
      existing_user_token_bonus: editingExistingTokenBonus,
    })
    setEditingId(null)
    setEditingName('')
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditingName('')
  }

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Удалить ссылку "${name}"?`)) return
    await deleteLink(id)
  }

  const formatDate = (dateStr: string) => {
    try {
      return format(new Date(dateStr), 'd MMM yyyy', { locale: ru })
    } catch {
      return dateStr
    }
  }

  const renderLinkCard = (link: InviteLink) => {
    const isEditing = editingId === link.id
    const isActive = link.is_active !== false

    if (isEditing) {
      return (
        <div key={link.id} className={styles.linkCard}>
          <div className={styles.editForm}>
            {/* Header: toggle + name input + save/cancel */}
            <div className={styles.editHeader}>
              <button
                className={`${styles.toggleSwitch} ${isActive ? styles.toggleSwitchOn : ''}`}
                onClick={() => toggleLinkActive(link.id, !isActive)}
                title={isActive ? 'Отключить' : 'Включить'}
              >
                <span className={styles.toggleSwitchKnob} />
              </button>
              <input
                className={styles.editNameInput}
                value={editingName}
                onChange={(e) => setEditingName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') handleSaveEdit()
                  if (e.key === 'Escape') handleCancelEdit()
                }}
                autoFocus
              />
              <button className={styles.editSaveBtn} onClick={handleSaveEdit} title="Сохранить">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 7L6 10L11 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <button className={styles.editCancelBtn} onClick={handleCancelEdit} title="Отмена">
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 3L11 11M11 3L3 11" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>

            {/* Fields grid */}
            <div className={styles.editFields}>
              <div className={styles.editFieldGroup}>
                <label className={styles.editFieldLabel}>Бонус токенов</label>
                <input type="number" min="0" className={styles.editNumberInput}
                  value={editingBonusTokens} onChange={(e) => setEditingBonusTokens(Number(e.target.value) || 0)} />
              </div>
              <div className={styles.editFieldGroup}>
                <label className={styles.editFieldLabel}>Скидка %</label>
                <input type="number" min="0" max="100" className={styles.editNumberInput}
                  value={editingDiscountPercent} onChange={(e) => setEditingDiscountPercent(Number(e.target.value) || 0)} />
              </div>
              <div className={styles.editFieldGroup}>
                <label className={styles.editFieldLabel}>Бонус токенов %</label>
                <input type="number" min="0" max="100" className={styles.editNumberInput}
                  value={editingTokenBonusPercent} onChange={(e) => setEditingTokenBonusPercent(Number(e.target.value) || 0)} />
              </div>
              <div className={styles.editFieldGroup}>
                <label className={styles.editFieldLabel}>Дней скидки</label>
                <input type="number" min="0" className={styles.editNumberInput}
                  value={editingDiscountDays} onChange={(e) => setEditingDiscountDays(Number(e.target.value) || 0)} />
              </div>
              <div className={styles.editFieldGroup}>
                <label className={styles.editFieldLabel}>Лимит (0 = ∞)</label>
                <input type="number" min="0" className={styles.editNumberInput}
                  value={editingMaxUsers} onChange={(e) => setEditingMaxUsers(Number(e.target.value) || 0)} />
              </div>
            </div>

            {/* Existing users section */}
            <div className={styles.existingUsersSection}>
              <label className={styles.toggleLabel}>
                <input
                  type="checkbox"
                  checked={editingAllowExisting}
                  onChange={(e) => setEditingAllowExisting(e.target.checked)}
                />
                <span>Для существующих пользователей</span>
              </label>
              {editingAllowExisting && (
                <div className={styles.existingCheckboxes}>
                  <label className={styles.checkboxLabel}>
                    <input type="checkbox" checked={editingExistingBonusTokens}
                      onChange={(e) => setEditingExistingBonusTokens(e.target.checked)} />
                    <span>Разовые токены</span>
                  </label>
                  <label className={styles.checkboxLabel}>
                    <input type="checkbox" checked={editingExistingDiscount}
                      onChange={(e) => setEditingExistingDiscount(e.target.checked)} />
                    <span>Скидка на цену</span>
                  </label>
                  <label className={styles.checkboxLabel}>
                    <input type="checkbox" checked={editingExistingTokenBonus}
                      onChange={(e) => setEditingExistingTokenBonus(e.target.checked)} />
                    <span>Бонус на токены</span>
                  </label>
                </div>
              )}
            </div>
          </div>
        </div>
      )
    }

    // Normal view mode
    const hasBonuses = link.bonus_tokens > 0 || link.discount_percent > 0 || link.token_bonus_percent > 0 || link.discount_duration_days > 0 || link.allow_existing_users

    return (
      <div key={link.id} className={`${styles.linkCard} ${!isActive ? styles.linkCardInactive : ''}`}>
        {/* Header: toggle + name + edit/delete */}
        <div className={styles.cardHeader}>
          <div className={styles.cardHeaderLeft}>
            <button
              className={`${styles.toggleSwitch} ${isActive ? styles.toggleSwitchOn : ''}`}
              onClick={() => toggleLinkActive(link.id, !isActive)}
              title={isActive ? 'Отключить' : 'Включить'}
            >
              <span className={styles.toggleSwitchKnob} />
            </button>
            <span className={styles.cardName}>{link.name}</span>
          </div>
          <div className={styles.cardHeaderActions}>
            <button className={styles.editButton} onClick={() => handleStartEdit(link)} title="Редактировать">
              ✏️
            </button>
            <button className={styles.deleteButton} onClick={() => handleDelete(link.id, link.name)} title="Удалить">
              🗑️
            </button>
          </div>
        </div>

        {/* Deep link */}
        <div className={styles.deepLinkRow}>
          <a href={link.deep_link} target="_blank" rel="noopener noreferrer" className={styles.deepLinkUrl}>
            {link.deep_link}
          </a>
          <button
            className={`${styles.copyButton} ${copiedId === link.id ? styles.copied : ''}`}
            onClick={() => handleCopy(link.deep_link, link.id)}
            title={copiedId === link.id ? 'Скопировано!' : 'Скопировать ссылку'}
          >
            {copiedId === link.id ? (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3 7L6 10L11 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            ) : (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <rect x="4" y="4" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M10 4V2.5C10 1.67 9.33 1 8.5 1H2.5C1.67 1 1 1.67 1 2.5V8.5C1 9.33 1.67 10 2.5 10H4" stroke="currentColor" strokeWidth="1.5"/>
              </svg>
            )}
          </button>
        </div>

        {/* Badges */}
        {hasBonuses && (
          <div className={styles.badgesRow}>
            {link.bonus_tokens > 0 && (
              <span className={`${styles.badge} ${styles.badgeBonus}`}>+{link.bonus_tokens} токенов</span>
            )}
            {link.discount_percent > 0 && (
              <span className={`${styles.badge} ${styles.badgeDiscount}`}>Скидка {link.discount_percent}%</span>
            )}
            {link.token_bonus_percent > 0 && (
              <span className={`${styles.badge} ${styles.badgeTokenBonus}`}>Бонус +{link.token_bonus_percent}%</span>
            )}
            {link.discount_duration_days > 0 && (
              <span className={`${styles.badge} ${styles.badgeDays}`}>{link.discount_duration_days} дн.</span>
            )}
            {link.max_users > 0 && (
              <span className={`${styles.badge} ${
                link.total_users_count >= link.max_users ? styles.badgeLimitReached
                : link.total_users_count >= link.max_users * 0.8 ? styles.badgeLimitWarning
                : styles.badgeLimit
              }`}>
                {link.total_users_count}/{link.max_users}{link.total_users_count >= link.max_users ? ' 🔒' : ''}
              </span>
            )}
            {link.allow_existing_users && (
              <span className={`${styles.badge} ${styles.badgeExisting}`}>Для существующих</span>
            )}
          </div>
        )}

        {/* Stats */}
        <div className={styles.statsRow}>
          <span className={styles.statItem}>
            👥 <span className={styles.statValue}>{link.total_users_count}</span> всего
          </span>
          <span className={styles.statItem}>
            🆕 <span className={styles.statValue}>{link.new_users_count}</span> новых
          </span>
          {link.existing_users_count > 0 && (
            <span className={styles.statItem}>
              🔄 <span className={styles.statValue}>{link.existing_users_count}</span> существующих
            </span>
          )}
          {link.users_count !== link.total_users_count && (
            <span className={styles.statItem}>
              📊 <span className={styles.statValue}>{link.users_count}</span> за период
            </span>
          )}
          <span className={styles.statItem}>
            💰 <span className={styles.statValue}>{link.total_revenue_rub.toLocaleString('ru-RU')} ₽</span>
          </span>
          <span className={styles.statItem}>
            📅 {formatDate(link.created_at)}
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <h2>Инвайт-ссылки</h2>
          <button
            className={styles.addButton}
            onClick={() => setShowCreateForm(!showCreateForm)}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 1V13M1 7H13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            Создать
          </button>
        </div>

        <div className={styles.dateControls}>
          <div className={styles.viewToggle}>
            <button
              className={`${styles.toggleButton} ${viewMode === 'month' ? styles.toggleActive : ''}`}
              onClick={switchToMonth}
            >
              По месяцам
            </button>
            <button
              className={`${styles.toggleButton} ${viewMode === 'all' ? styles.toggleActive : ''}`}
              onClick={switchToAll}
            >
              Всё время
            </button>
          </div>

          {viewMode === 'month' && (
            <div className={styles.dateNavigation}>
              <button className={styles.navButton} onClick={goToPrevMonth}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M10 4L6 8L10 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <div className={styles.dateRange}>{dateRangeLabel}</div>
              <button className={styles.navButton} onClick={goToNextMonth}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M6 4L10 8L6 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <div className={styles.createForm}>
          <div className={styles.createFields}>
            <input
              className={styles.createInput}
              type="text"
              placeholder="Название ссылки (например: Instagram Февраль)"
              value={newLinkName}
              onChange={(e) => setNewLinkName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              autoFocus
            />
            <div className={styles.bonusFields}>
              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>Бонус токенов</label>
                <input
                  className={styles.numberInput}
                  type="number"
                  min="0"
                  value={newBonusTokens}
                  onChange={(e) => setNewBonusTokens(Number(e.target.value) || 0)}
                />
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>Скидка %</label>
                <input
                  className={styles.numberInput}
                  type="number"
                  min="0"
                  max="100"
                  value={newDiscountPercent}
                  onChange={(e) => setNewDiscountPercent(Number(e.target.value) || 0)}
                />
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>Бонус токенов %</label>
                <input
                  className={styles.numberInput}
                  type="number"
                  min="0"
                  max="100"
                  value={newTokenBonusPercent}
                  onChange={(e) => setNewTokenBonusPercent(Number(e.target.value) || 0)}
                />
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>Дней скидки</label>
                <input
                  className={styles.numberInput}
                  type="number"
                  min="0"
                  value={newDiscountDays}
                  onChange={(e) => setNewDiscountDays(Number(e.target.value) || 0)}
                />
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>Лимит (0 = ∞)</label>
                <input
                  className={styles.numberInput}
                  type="number"
                  min="0"
                  value={newMaxUsers}
                  onChange={(e) => setNewMaxUsers(Number(e.target.value) || 0)}
                />
              </div>
            </div>
            {/* Секция: для существующих пользователей */}
            <div className={styles.existingUsersSection}>
              <label className={styles.toggleLabel}>
                <input
                  type="checkbox"
                  checked={newAllowExisting}
                  onChange={(e) => setNewAllowExisting(e.target.checked)}
                />
                <span>Для существующих пользователей</span>
              </label>
              {newAllowExisting && (
                <div className={styles.existingCheckboxes}>
                  <label className={styles.checkboxLabel}>
                    <input type="checkbox" checked={newExistingBonusTokens}
                      onChange={(e) => setNewExistingBonusTokens(e.target.checked)} />
                    <span>Разовые токены</span>
                  </label>
                  <label className={styles.checkboxLabel}>
                    <input type="checkbox" checked={newExistingDiscount}
                      onChange={(e) => setNewExistingDiscount(e.target.checked)} />
                    <span>Скидка на цену</span>
                  </label>
                  <label className={styles.checkboxLabel}>
                    <input type="checkbox" checked={newExistingTokenBonus}
                      onChange={(e) => setNewExistingTokenBonus(e.target.checked)} />
                    <span>Бонус на токены</span>
                  </label>
                </div>
              )}
            </div>
          </div>
          <div className={styles.createActions}>
            <button
              className={styles.createSubmit}
              onClick={handleCreate}
              disabled={creating || !newLinkName.trim()}
            >
              {creating ? 'Создание...' : 'Создать'}
            </button>
            <button
              className={styles.createCancel}
              onClick={() => { setShowCreateForm(false); setNewLinkName(''); setNewBonusTokens(0); setNewDiscountPercent(0); setNewDiscountDays(0); setNewMaxUsers(0); setNewTokenBonusPercent(0); setNewAllowExisting(false); setNewExistingBonusTokens(true); setNewExistingDiscount(true); setNewExistingTokenBonus(true) }}
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {/* Summary Cards */}
      {summary && (
        <div className={styles.summaryCards}>
          <div className={styles.summaryCard}>
            <div className={styles.summaryValue}>{summary.total_links}</div>
            <div className={styles.summaryLabel}>Ссылок</div>
          </div>
          <div className={styles.summaryCard}>
            <div className={styles.summaryValue}>{summary.total_users}</div>
            <div className={styles.summaryLabel}>Пользователей</div>
          </div>
          <div className={styles.summaryCard}>
            <div className={styles.summaryValue}>
              {summary.total_revenue_rub.toLocaleString('ru-RU')} ₽
            </div>
            <div className={styles.summaryLabel}>Выручка</div>
          </div>
        </div>
      )}

      {/* Content */}
      {isLoading ? (
        <div className={styles.loading}>Загрузка...</div>
      ) : error ? (
        <div className={styles.error}>Ошибка: {error}</div>
      ) : links.length === 0 ? (
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>🔗</div>
          <div className={styles.emptyText}>Нет инвайт-ссылок</div>
          <div className={styles.emptyHint}>Создайте первую ссылку для отслеживания кампании</div>
        </div>
      ) : (
        <div className={styles.linksList}>
          {links.map(renderLinkCard)}
        </div>
      )}
    </div>
  )
}
