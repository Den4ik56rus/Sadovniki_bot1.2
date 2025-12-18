// Expense Form - Spendee-like inline form at the top

import { useState, useEffect, useRef } from 'react'
import { useExpenseStore } from '@/store/expenseStore'
import { CategoryIcon, getIconFromCategoryName } from './CategoryIcon'
import type { CreateExpenseDto } from '@/types'
import styles from './ExpenseForm.module.css'

export function ExpenseForm() {
  const {
    editingExpense,
    categories,
    closeForm,
    createExpense,
    updateExpense,
    createCategory,
  } = useExpenseStore()

  const isEditing = !!editingExpense

  // Form state
  const [date, setDate] = useState('')
  const [name, setName] = useState('')
  const [categoryId, setCategoryId] = useState<number | ''>('')
  const [amount, setAmount] = useState('')
  const [paidBy, setPaidBy] = useState<'Денис' | 'Данил' | 'Оба'>('Денис')
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Category dropdown state
  const [isCategoryOpen, setIsCategoryOpen] = useState(false)
  const categoryDropdownRef = useRef<HTMLDivElement>(null)

  // New category modal
  const [showNewCategory, setShowNewCategory] = useState(false)
  const [newCategoryName, setNewCategoryName] = useState('')
  const [newCategoryColor, setNewCategoryColor] = useState('#6B7280')

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (categoryDropdownRef.current && !categoryDropdownRef.current.contains(event.target as Node)) {
        setIsCategoryOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Populate form when editing
  useEffect(() => {
    if (editingExpense) {
      setDate(editingExpense.date)
      setName(editingExpense.name)
      setCategoryId(editingExpense.category_id || '')
      setAmount(String(editingExpense.amount))
      setPaidBy(editingExpense.paid_by)
    } else {
      // Default to today for new expenses
      const today = new Date().toISOString().split('T')[0]
      setDate(today)
    }
  }, [editingExpense])

  // Handle form submit
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!date || !name || !categoryId || !amount || !paidBy) {
      alert('Заполните все обязательные поля')
      return
    }

    setIsSubmitting(true)

    try {
      const data: CreateExpenseDto = {
        date,
        name,
        category_id: Number(categoryId),
        amount: Number(amount),
        paid_by: paidBy,
      }

      if (isEditing && editingExpense) {
        await updateExpense(editingExpense.id, data)
      } else {
        await createExpense(data)
      }
      closeForm()
    } catch (error) {
      console.error('Error saving expense:', error)
      alert('Ошибка при сохранении')
    } finally {
      setIsSubmitting(false)
    }
  }

  // Handle new category creation
  const handleCreateCategory = async () => {
    if (!newCategoryName.trim()) {
      alert('Введите название категории')
      return
    }

    const category = await createCategory(newCategoryName.trim(), newCategoryColor)
    if (category) {
      setCategoryId(category.id)
      setShowNewCategory(false)
      setNewCategoryName('')
      setNewCategoryColor('#6B7280')
    } else {
      alert('Ошибка при создании категории')
    }
  }

  // Get selected category for display
  const selectedCategory = categories.find(c => c.id === categoryId)

  return (
    <div className={styles.formContainer}>
      <form onSubmit={handleSubmit} className={styles.form}>
        {/* Row 1: Category, Date, Note, Amount, Currency */}
        <div className={styles.formRow}>
          {/* Category - Custom Dropdown */}
          <div className={styles.field} ref={categoryDropdownRef}>
            <label className={styles.label}>Категория</label>
            <div className={styles.categoryDropdown}>
              <button
                type="button"
                className={styles.categoryTrigger}
                onClick={() => setIsCategoryOpen(!isCategoryOpen)}
              >
                <CategoryIcon
                  icon={selectedCategory?.icon || getIconFromCategoryName(selectedCategory?.name)}
                  color={selectedCategory?.color || '#22C55E'}
                  size="sm"
                />
                <span className={styles.categoryTriggerText}>
                  {selectedCategory?.name || 'Выберите...'}
                </span>
                <svg
                  className={`${styles.categoryChevron} ${isCategoryOpen ? styles.open : ''}`}
                  width="10" height="6" viewBox="0 0 10 6" fill="none"
                >
                  <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>

              {isCategoryOpen && (
                <div className={styles.categoryMenu}>
                  {categories.map((cat) => (
                    <button
                      key={cat.id}
                      type="button"
                      className={`${styles.categoryOption} ${categoryId === cat.id ? styles.selected : ''}`}
                      onClick={() => {
                        setCategoryId(cat.id)
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
                  <button
                    type="button"
                    className={styles.categoryOptionNew}
                    onClick={() => {
                      setShowNewCategory(true)
                      setIsCategoryOpen(false)
                    }}
                  >
                    <span className={styles.newCategoryIcon}>+</span>
                    <span>Новая категория</span>
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Date */}
          <div className={styles.field}>
            <label className={styles.label}>Дата</label>
            <input
              type="date"
              className={styles.input}
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
            />
          </div>

          {/* Note/Name */}
          <div className={`${styles.field} ${styles.fieldWide}`}>
            <label className={styles.label}>Описание</label>
            <input
              type="text"
              className={styles.input}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Введите описание"
              required
            />
          </div>

          {/* Amount */}
          <div className={styles.field}>
            <label className={styles.label}>Сумма</label>
            <div className={styles.amountWrapper}>
              <input
                type="number"
                className={`${styles.input} ${styles.amountInput}`}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="-0.00"
                min="0"
                step="0.01"
                required
              />
            </div>
          </div>

          {/* Currency (static for now) */}
          <div className={styles.field}>
            <label className={styles.label}>Валюта</label>
            <div className={styles.currencyBadge}>RUB</div>
          </div>
        </div>

        {/* Row 2: Paid By selector and Submit button */}
        <div className={styles.formRow}>
          {/* Paid By */}
          <div className={styles.paidByGroup}>
            <label
              className={`${styles.paidByOption} ${paidBy === 'Денис' ? styles.active : ''}`}
            >
              <input
                type="radio"
                name="paidBy"
                value="Денис"
                checked={paidBy === 'Денис'}
                onChange={() => setPaidBy('Денис')}
                className={styles.radioInput}
              />
              <span className={`${styles.paidByAvatar} ${styles.denis}`}>Д</span>
              <span className={styles.paidByName}>Денис</span>
            </label>
            <label
              className={`${styles.paidByOption} ${paidBy === 'Данил' ? styles.active : ''}`}
            >
              <input
                type="radio"
                name="paidBy"
                value="Данил"
                checked={paidBy === 'Данил'}
                onChange={() => setPaidBy('Данил')}
                className={styles.radioInput}
              />
              <span className={`${styles.paidByAvatar} ${styles.danil}`}>Д</span>
              <span className={styles.paidByName}>Данил</span>
            </label>
            <label
              className={`${styles.paidByOption} ${paidBy === 'Оба' ? styles.active : ''}`}
            >
              <input
                type="radio"
                name="paidBy"
                value="Оба"
                checked={paidBy === 'Оба'}
                onChange={() => setPaidBy('Оба')}
                className={styles.radioInput}
              />
              <span className={`${styles.paidByAvatar} ${styles.both}`}>½</span>
              <span className={styles.paidByName}>Оба</span>
            </label>
          </div>

          <div className={styles.formActions}>
            {/* Submit */}
            <button
              type="submit"
              className={styles.submitButton}
              disabled={isSubmitting}
            >
              {isSubmitting ? 'Сохранение...' : isEditing ? 'Сохранить' : 'Добавить'}
            </button>
          </div>
        </div>

        {/* New Category Inline Form */}
        {showNewCategory && (
          <div className={styles.newCategoryForm}>
            <input
              type="text"
              className={styles.input}
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              placeholder="Название категории"
              autoFocus
            />
            <input
              type="color"
              className={styles.colorInput}
              value={newCategoryColor}
              onChange={(e) => setNewCategoryColor(e.target.value)}
            />
            <button
              type="button"
              className={styles.cancelButton}
              onClick={() => setShowNewCategory(false)}
            >
              Отмена
            </button>
            <button
              type="button"
              className={styles.createButton}
              onClick={handleCreateCategory}
            >
              Создать
            </button>
          </div>
        )}
      </form>
    </div>
  )
}
