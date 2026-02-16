// Expenses Page - Spendee-like layout

import { useEffect, useState } from 'react'
import { format, startOfMonth, endOfMonth, subMonths, addMonths } from 'date-fns'
import { ru } from 'date-fns/locale'
import { useExpenseStore } from '@/store/expenseStore'
import { ExpenseStats } from './ExpenseStats'
import { ExpenseFilters } from './ExpenseFilters'
import { ExpenseList } from './ExpenseList'
import { ExpenseForm } from './ExpenseForm'
import styles from './ExpensesPage.module.css'

type ViewMode = 'month' | 'all'

export function ExpensesPage() {
  const {
    fetchExpenses,
    fetchCategories,
    fetchStats,
    setFilters,
    clearFilters,
    isFormOpen,
    openForm,
    closeForm,
  } = useExpenseStore()

  // View mode: month or all time
  const [viewMode, setViewMode] = useState<ViewMode>('month')

  // Current month navigation
  const [currentDate, setCurrentDate] = useState(new Date())

  // Format date range label
  const dateRangeLabel = `${format(startOfMonth(currentDate), 'd MMM yyyy', { locale: ru })} – ${format(endOfMonth(currentDate), 'd MMM yyyy', { locale: ru })}`

  // Navigate months
  const goToPrevMonth = () => {
    const newDate = subMonths(currentDate, 1)
    setCurrentDate(newDate)
    setFilters({
      start_date: format(startOfMonth(newDate), 'yyyy-MM-dd'),
      end_date: format(endOfMonth(newDate), 'yyyy-MM-dd'),
    })
  }

  const goToNextMonth = () => {
    const newDate = addMonths(currentDate, 1)
    setCurrentDate(newDate)
    setFilters({
      start_date: format(startOfMonth(newDate), 'yyyy-MM-dd'),
      end_date: format(endOfMonth(newDate), 'yyyy-MM-dd'),
    })
  }

  // Switch view mode
  const switchToMonth = () => {
    setViewMode('month')
    setFilters({
      start_date: format(startOfMonth(currentDate), 'yyyy-MM-dd'),
      end_date: format(endOfMonth(currentDate), 'yyyy-MM-dd'),
    })
  }

  const switchToAll = () => {
    setViewMode('all')
    setFilters({
      start_date: undefined,
      end_date: undefined,
    })
  }

  // Fetch data on mount
  useEffect(() => {
    fetchExpenses()
    fetchCategories()
    fetchStats()
  }, [fetchExpenses, fetchCategories, fetchStats])

  // Set initial date filter to current month
  useEffect(() => {
    setFilters({
      start_date: format(startOfMonth(currentDate), 'yyyy-MM-dd'),
      end_date: format(endOfMonth(currentDate), 'yyyy-MM-dd'),
    })
  }, [])

  return (
    <div className={styles.container}>
      {/* Header - Button left, Date navigation right */}
      <div className={styles.header}>
        {isFormOpen ? (
          <button className={styles.closeFormButton} onClick={() => closeForm()}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 4L12 12M4 12L12 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            Закрыть
          </button>
        ) : (
          <button className={styles.addButton} onClick={() => openForm()}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M8 5V11M5 8H11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            Добавить расход
          </button>
        )}

        <div className={styles.dateNavigation}>
          {/* View mode toggle */}
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
              За всё время
            </button>
          </div>

          {viewMode === 'month' && (
            <button className={styles.navButton} onClick={goToPrevMonth} title="Предыдущий месяц">
              <svg style={{ width: 36, height: 36 }} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M15 5L8 12L15 19" stroke="#374151" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          )}

          <div className={styles.dateRange}>
            <span className={styles.dateRangeText}>
              {viewMode === 'all' ? 'За всё время' : dateRangeLabel}
            </span>
            <svg className={styles.dateRangeIcon} width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="2" y="3" width="12" height="11" rx="2" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M2 6H14" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M5 1V3M11 1V3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>

          {viewMode === 'month' && (
            <button className={styles.navButton} onClick={goToNextMonth} title="Следующий месяц">
              <svg style={{ width: 36, height: 36 }} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 5L16 12L9 19" stroke="#374151" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Floating Form - appears over content when open */}
      {isFormOpen && (
        <div className={styles.formOverlay}>
          <ExpenseForm />
        </div>
      )}

      {/* Content with dimming when form is open */}
      <div className={`${styles.content} ${isFormOpen ? styles.dimmed : ''}`}>
        {/* Filters Row */}
        <ExpenseFilters />

        {/* Stats Cards Row */}
        <ExpenseStats />

        {/* Expense List */}
        <ExpenseList />
      </div>
    </div>
  )
}
