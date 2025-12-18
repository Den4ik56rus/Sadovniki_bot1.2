// Expense List - Spendee-like table view with category icons

import { useMemo } from 'react'
import { format, isToday, isYesterday, parseISO } from 'date-fns'
import { ru } from 'date-fns/locale'
import { useExpenseStore } from '@/store/expenseStore'
import { CategoryIcon, getIconFromCategoryName } from './CategoryIcon'
import type { Expense } from '@/types'
import styles from './ExpenseList.module.css'

interface GroupedExpenses {
  date: string
  label: string
  total: number
  expenses: Expense[]
}

export function ExpenseList() {
  const { expenses, isLoading, openForm, deleteExpense } = useExpenseStore()

  // Format amount as RUB
  const formatRub = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount)
  }

  // Group expenses by date
  const groupedExpenses = useMemo<GroupedExpenses[]>(() => {
    const groups: Record<string, { total: number; expenses: Expense[] }> = {}

    for (const expense of expenses) {
      const dateKey = expense.date
      if (!groups[dateKey]) {
        groups[dateKey] = { total: 0, expenses: [] }
      }
      groups[dateKey].expenses.push(expense)
      groups[dateKey].total += expense.amount
    }

    // Sort by date descending and format labels
    return Object.entries(groups)
      .sort(([a], [b]) => b.localeCompare(a))
      .map(([dateStr, data]) => {
        const date = parseISO(dateStr)
        let label: string

        if (isToday(date)) {
          label = 'Сегодня'
        } else if (isYesterday(date)) {
          label = 'Вчера'
        } else {
          label = format(date, 'd MMMM yyyy', { locale: ru })
        }

        return {
          date: dateStr,
          label,
          total: data.total,
          expenses: data.expenses,
        }
      })
  }, [expenses])

  // Handle delete with confirmation
  const handleDelete = async (expense: Expense) => {
    if (confirm(`Удалить расход "${expense.name}"?`)) {
      await deleteExpense(expense.id)
    }
  }

  if (isLoading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner} />
        <span>Загрузка расходов...</span>
      </div>
    )
  }

  if (expenses.length === 0) {
    return (
      <div className={styles.emptyContainer}>
        <div className={styles.emptyIcon}>
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="12" stroke="currentColor" strokeWidth="1.5" strokeDasharray="4 4"/>
            <path d="M16 10V18M12 14H20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </div>
        <p>Расходы не найдены</p>
        <span>Нажмите «Добавить расход» чтобы начать отслеживание</span>
      </div>
    )
  }

  return (
    <div className={styles.listContainer}>
      {groupedExpenses.map((group) => (
        <div key={group.date} className={styles.dateGroup}>
          {/* Date Header */}
          <div className={styles.dateHeader}>
            <span className={styles.dateLabel}>{group.label}</span>
            <span className={styles.dateTotal}>-{formatRub(group.total)} ₽</span>
          </div>

          {/* Expense Items */}
          <div className={styles.expenseItems}>
            {group.expenses.map((expense) => (
              <div key={expense.id} className={styles.expenseItem}>
                {/* Category Icon */}
                <CategoryIcon
                  icon={expense.category_icon || getIconFromCategoryName(expense.category_name)}
                  color={expense.category_color || '#6B7280'}
                  size="md"
                />

                {/* Expense Info */}
                <div className={styles.expenseInfo}>
                  <span className={styles.expenseName}>{expense.name}</span>
                  <div className={styles.expenseCategory}>
                    <span
                      className={styles.categoryTag}
                      style={{
                        backgroundColor: `${expense.category_color || '#6B7280'}15`,
                        color: expense.category_color || '#6B7280'
                      }}
                    >
                      {expense.category_name || 'Без категории'}
                    </span>
                  </div>
                </div>

                {/* Paid By Badge */}
                <span className={styles.paidByBadge}>
                  {expense.paid_by}
                </span>

                {/* Amount */}
                <span className={styles.expenseAmount}>
                  -{formatRub(expense.amount)} ₽
                </span>

                {/* Actions */}
                <div className={styles.expenseActions}>
                  <button
                    className={styles.actionButton}
                    onClick={() => openForm(expense)}
                    title="Редактировать"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M10.5 1.5L12.5 3.5L4.5 11.5H2.5V9.5L10.5 1.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                    </svg>
                  </button>
                  <button
                    className={`${styles.actionButton} ${styles.deleteButton}`}
                    onClick={() => handleDelete(expense)}
                    title="Удалить"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <path d="M2 4H12M5 4V2H9V4M11 4V12C11 12.5 10.5 13 10 13H4C3.5 13 3 12.5 3 12V4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
