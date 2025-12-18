// Zustand store for Expenses

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '@/services/api'
import type { Expense, ExpenseCategory, ExpenseStats, ExpenseFilters, CreateExpenseDto } from '@/types'

interface ExpenseStore {
  // State
  expenses: Expense[]
  categories: ExpenseCategory[]
  stats: ExpenseStats | null
  filters: ExpenseFilters
  total: number
  isLoading: boolean
  isLoadingStats: boolean
  error: string | null

  // Modal state
  isFormOpen: boolean
  editingExpense: Expense | null

  // Actions
  fetchExpenses: () => Promise<void>
  fetchCategories: () => Promise<void>
  fetchStats: () => Promise<void>
  setFilters: (filters: Partial<ExpenseFilters>) => void
  clearFilters: () => void

  // CRUD
  createExpense: (data: CreateExpenseDto) => Promise<Expense | null>
  updateExpense: (id: number, data: Partial<CreateExpenseDto>) => Promise<Expense | null>
  deleteExpense: (id: number) => Promise<boolean>

  // Categories
  createCategory: (name: string, color?: string) => Promise<ExpenseCategory | null>
  deleteCategory: (id: number) => Promise<boolean>

  // Modal
  openForm: (expense?: Expense) => void
  closeForm: () => void
}

export const useExpenseStore = create<ExpenseStore>()(
  persist(
    (set, get) => ({
      // Initial state
      expenses: [],
      categories: [],
      stats: null,
      filters: {},
      total: 0,
      isLoading: false,
      isLoadingStats: false,
      error: null,
      isFormOpen: false,
      editingExpense: null,

      // Fetch expenses with current filters
      fetchExpenses: async () => {
        set({ isLoading: true, error: null })
        try {
          const { filters } = get()
          const result = await api.getExpenses({
            ...filters,
            limit: 200,
          })
          set({
            expenses: result.expenses,
            total: result.total,
            isLoading: false,
          })
        } catch (error) {
          set({ error: String(error), isLoading: false })
        }
      },

      // Fetch categories
      fetchCategories: async () => {
        try {
          const categories = await api.getExpenseCategories()
          set({ categories })
        } catch (error) {
          console.error('Error fetching expense categories:', error)
        }
      },

      // Fetch stats
      fetchStats: async () => {
        set({ isLoadingStats: true })
        try {
          const { filters } = get()
          const stats = await api.getExpenseStats({
            start_date: filters.start_date,
            end_date: filters.end_date,
          })
          set({ stats, isLoadingStats: false })
        } catch (error) {
          console.error('Error fetching expense stats:', error)
          set({ isLoadingStats: false })
        }
      },

      // Set filters and refetch
      setFilters: (newFilters) => {
        set(state => ({
          filters: { ...state.filters, ...newFilters },
        }))
        // Refetch expenses and stats with new filters
        get().fetchExpenses()
        get().fetchStats()
      },

      // Clear all filters
      clearFilters: () => {
        set({ filters: {} })
        get().fetchExpenses()
        get().fetchStats()
      },

      // Create expense
      createExpense: async (data) => {
        try {
          const expense = await api.createExpense(data)
          // Refetch to get updated list and stats
          get().fetchExpenses()
          get().fetchStats()
          return expense
        } catch (error) {
          console.error('Error creating expense:', error)
          return null
        }
      },

      // Update expense
      updateExpense: async (id, data) => {
        try {
          const expense = await api.updateExpense(id, data)
          // Refetch to get updated list and stats
          get().fetchExpenses()
          get().fetchStats()
          return expense
        } catch (error) {
          console.error('Error updating expense:', error)
          return null
        }
      },

      // Delete expense
      deleteExpense: async (id) => {
        try {
          await api.deleteExpense(id)
          // Refetch to get updated list and stats
          get().fetchExpenses()
          get().fetchStats()
          return true
        } catch (error) {
          console.error('Error deleting expense:', error)
          return false
        }
      },

      // Create category
      createCategory: async (name, color) => {
        try {
          const category = await api.createExpenseCategory({ name, color })
          // Update local state
          set(state => ({
            categories: [...state.categories, category],
          }))
          return category
        } catch (error) {
          console.error('Error creating category:', error)
          return null
        }
      },

      // Delete category
      deleteCategory: async (id) => {
        try {
          await api.deleteExpenseCategory(id)
          // Update local state
          set(state => ({
            categories: state.categories.filter(c => c.id !== id),
          }))
          return true
        } catch (error) {
          console.error('Error deleting category:', error)
          return false
        }
      },

      // Open form modal
      openForm: (expense) => {
        set({
          isFormOpen: true,
          editingExpense: expense || null,
        })
      },

      // Close form modal
      closeForm: () => {
        set({
          isFormOpen: false,
          editingExpense: null,
        })
      },
    }),
    {
      name: 'expense-filters',
      partialize: (state) => ({
        filters: state.filters,
      }),
    }
  )
)
