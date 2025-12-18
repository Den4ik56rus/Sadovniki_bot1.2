// Expense Filters - Spendee-like horizontal filters with icons

import { useState, useRef, useEffect } from 'react'
import { useExpenseStore } from '@/store/expenseStore'
import { CategoryIcon, getIconFromCategoryName } from './CategoryIcon'
import styles from './ExpenseFilters.module.css'

export function ExpenseFilters() {
  const { filters, categories, setFilters, clearFilters } = useExpenseStore()

  // Dropdown states
  const [isCategoryOpen, setIsCategoryOpen] = useState(false)
  const [isPaidByOpen, setIsPaidByOpen] = useState(false)
  const categoryRef = useRef<HTMLDivElement>(null)
  const paidByRef = useRef<HTMLDivElement>(null)

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (categoryRef.current && !categoryRef.current.contains(event.target as Node)) {
        setIsCategoryOpen(false)
      }
      if (paidByRef.current && !paidByRef.current.contains(event.target as Node)) {
        setIsPaidByOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Check if category/paid_by filters are active (not date - that's in header)
  const hasActiveFilters = !!(filters.category_id || filters.paid_by)

  // Get selected category
  const selectedCategory = filters.category_id
    ? categories.find((c) => c.id === filters.category_id)
    : null

  return (
    <div className={styles.filtersContainer}>
      <div className={styles.filtersHeader}>
        <span className={styles.filtersLabel}>Фильтры</span>
        {hasActiveFilters && (
          <button className={styles.resetButton} onClick={clearFilters}>
            Сбросить фильтры
          </button>
        )}
      </div>

      <div className={styles.filtersRow}>
        {/* Category Filter - Custom Dropdown */}
        <div className={styles.filterGroup} ref={categoryRef}>
          <label className={styles.filterLabel}>По категории</label>
          <div className={styles.dropdown}>
            <button
              type="button"
              className={styles.dropdownTrigger}
              onClick={() => setIsCategoryOpen(!isCategoryOpen)}
            >
              {selectedCategory ? (
                <CategoryIcon
                  icon={selectedCategory.icon || getIconFromCategoryName(selectedCategory.name)}
                  color={selectedCategory.color}
                  size="sm"
                />
              ) : (
                <span className={styles.allCategoriesIcon}>{categories.length}</span>
              )}
              <span className={styles.dropdownText}>
                {selectedCategory?.name || 'Все категории'}
              </span>
              <svg
                className={`${styles.dropdownChevron} ${isCategoryOpen ? styles.open : ''}`}
                width="10" height="6" viewBox="0 0 10 6" fill="none"
              >
                <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>

            {isCategoryOpen && (
              <div className={styles.dropdownMenu}>
                <button
                  type="button"
                  className={`${styles.dropdownOption} ${!filters.category_id ? styles.selected : ''}`}
                  onClick={() => {
                    setFilters({ category_id: undefined })
                    setIsCategoryOpen(false)
                  }}
                >
                  <span className={styles.allCategoriesIcon}>{categories.length}</span>
                  <span>Все категории</span>
                </button>
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    className={`${styles.dropdownOption} ${filters.category_id === cat.id ? styles.selected : ''}`}
                    onClick={() => {
                      setFilters({ category_id: cat.id })
                      setIsCategoryOpen(false)
                    }}
                  >
                    <CategoryIcon
                      icon={cat.icon || getIconFromCategoryName(cat.name)}
                      color={cat.color}
                      size="sm"
                    />
                    <span>{cat.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Paid By Filter - Custom Dropdown */}
        <div className={styles.filterGroup} ref={paidByRef}>
          <label className={styles.filterLabel}>По плательщику</label>
          <div className={styles.dropdown}>
            <button
              type="button"
              className={styles.dropdownTrigger}
              onClick={() => setIsPaidByOpen(!isPaidByOpen)}
            >
              <span className={styles.personIcon}>
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="7" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
                  <path d="M3 13C3 10.24 4.79 8 7 8C9.21 8 11 10.24 11 13" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                </svg>
              </span>
              <span className={styles.dropdownText}>
                {filters.paid_by || 'Все'}
              </span>
              <svg
                className={`${styles.dropdownChevron} ${isPaidByOpen ? styles.open : ''}`}
                width="10" height="6" viewBox="0 0 10 6" fill="none"
              >
                <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>

            {isPaidByOpen && (
              <div className={styles.dropdownMenu}>
                <button
                  type="button"
                  className={`${styles.dropdownOption} ${!filters.paid_by ? styles.selected : ''}`}
                  onClick={() => {
                    setFilters({ paid_by: undefined })
                    setIsPaidByOpen(false)
                  }}
                >
                  <span className={styles.personIcon}>
                    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
                      <circle cx="7" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
                      <path d="M3 13C3 10.24 4.79 8 7 8C9.21 8 11 10.24 11 13" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
                    </svg>
                  </span>
                  <span>Все</span>
                </button>
                <button
                  type="button"
                  className={`${styles.dropdownOption} ${filters.paid_by === 'Денис' ? styles.selected : ''}`}
                  onClick={() => {
                    setFilters({ paid_by: 'Денис' })
                    setIsPaidByOpen(false)
                  }}
                >
                  <span className={`${styles.paidByAvatar} ${styles.denis}`}>Д</span>
                  <span>Денис</span>
                </button>
                <button
                  type="button"
                  className={`${styles.dropdownOption} ${filters.paid_by === 'Данил' ? styles.selected : ''}`}
                  onClick={() => {
                    setFilters({ paid_by: 'Данил' })
                    setIsPaidByOpen(false)
                  }}
                >
                  <span className={`${styles.paidByAvatar} ${styles.danil}`}>Д</span>
                  <span>Данил</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
