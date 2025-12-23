/**
 * Zustand store для управления промптами.
 */

import { create } from 'zustand'
import { api } from '@/services/api'
import type { PromptGroup, Prompt, PromptHistoryItem } from '@/types'

interface PromptStore {
  // State
  groups: PromptGroup[]
  prompts: Prompt[]
  selectedPrompt: Prompt | null
  history: PromptHistoryItem[]
  isLoading: boolean
  isSaving: boolean
  isLoadingHistory: boolean
  error: string | null

  // Expanded groups state
  expandedGroups: Set<number>
  expandedSubgroups: Set<string>
  expandedCultureTypes: Set<string>  // Для вложенных групп внутри Клубника/Малина+Ежевика

  // Actions
  fetchGroups: () => Promise<void>
  fetchPrompts: (groupId?: number, subgroupId?: number) => Promise<void>
  selectPrompt: (id: number) => Promise<void>
  updatePrompt: (id: number, content: string) => Promise<void>
  togglePromptEnabled: (id: number, enabled: boolean) => Promise<void>
  fetchHistory: (promptId: number) => Promise<void>
  revertToVersion: (promptId: number, version: number) => Promise<void>
  clearSelection: () => void
  toggleGroupExpanded: (groupId: number) => void
  toggleSubgroupExpanded: (groupId: number, subgroupId: number) => void
  toggleCultureTypeExpanded: (subgroupId: number, cultureType: string) => void
  setError: (error: string | null) => void
}

export const usePromptStore = create<PromptStore>((set, get) => ({
  // Initial state
  groups: [],
  prompts: [],
  selectedPrompt: null,
  history: [],
  isLoading: false,
  isSaving: false,
  isLoadingHistory: false,
  error: null,
  expandedGroups: new Set<number>(),
  expandedSubgroups: new Set<string>(),
  expandedCultureTypes: new Set<string>(),

  // Fetch all groups with subgroups
  fetchGroups: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await api.getPromptGroups()
      set({ groups: response.groups, isLoading: false })

      // Auto-expand first group
      if (response.groups.length > 0 && get().expandedGroups.size === 0) {
        const firstGroupId = response.groups[0].id
        set({ expandedGroups: new Set([firstGroupId]) })
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch groups'
      set({ error: message, isLoading: false })
    }
  },

  // Fetch prompts with optional filters
  fetchPrompts: async (groupId?: number, subgroupId?: number) => {
    set({ isLoading: true, error: null })
    try {
      const response = await api.getPrompts({ group_id: groupId, subgroup_id: subgroupId })
      set({ prompts: response.prompts, isLoading: false })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch prompts'
      set({ error: message, isLoading: false })
    }
  },

  // Select and load a prompt
  selectPrompt: async (id: number) => {
    set({ isLoading: true, error: null })
    try {
      const response = await api.getPrompt(id)
      set({ selectedPrompt: response.prompt, isLoading: false })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch prompt'
      set({ error: message, isLoading: false })
    }
  },

  // Update prompt content
  updatePrompt: async (id: number, content: string) => {
    set({ isSaving: true, error: null })
    try {
      const response = await api.updatePrompt(id, content)
      if (response.success) {
        // Update in prompts list
        set((state) => ({
          prompts: state.prompts.map((p) =>
            p.id === id ? { ...p, content, version: response.prompt.version, updated_at: response.prompt.updated_at } : p
          ),
          selectedPrompt: state.selectedPrompt?.id === id
            ? { ...state.selectedPrompt, content, version: response.prompt.version, updated_at: response.prompt.updated_at }
            : state.selectedPrompt,
          isSaving: false,
        }))
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update prompt'
      set({ error: message, isSaving: false })
    }
  },

  // Toggle prompt enabled/disabled
  togglePromptEnabled: async (id: number, enabled: boolean) => {
    set({ error: null })
    try {
      const response = await api.togglePromptEnabled(id, enabled)
      if (response.success) {
        // Update in prompts list
        set((state) => ({
          prompts: state.prompts.map((p) =>
            p.id === id ? { ...p, is_enabled: enabled } : p
          ),
          selectedPrompt: state.selectedPrompt?.id === id
            ? { ...state.selectedPrompt, is_enabled: enabled }
            : state.selectedPrompt,
        }))
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to toggle prompt'
      set({ error: message })
    }
  },

  // Fetch prompt history
  fetchHistory: async (promptId: number) => {
    set({ isLoadingHistory: true, error: null })
    try {
      const response = await api.getPromptHistory(promptId)
      set({ history: response.history, isLoadingHistory: false })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to fetch history'
      set({ error: message, isLoadingHistory: false })
    }
  },

  // Revert to a specific version
  revertToVersion: async (promptId: number, version: number) => {
    set({ isSaving: true, error: null })
    try {
      const response = await api.revertPromptToVersion(promptId, version)
      if (response.success) {
        // Refresh the prompt
        const promptResponse = await api.getPrompt(promptId)
        set({
          selectedPrompt: promptResponse.prompt,
          prompts: get().prompts.map((p) =>
            p.id === promptId ? promptResponse.prompt : p
          ),
          isSaving: false,
        })
        // Refresh history
        await get().fetchHistory(promptId)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to revert prompt'
      set({ error: message, isSaving: false })
    }
  },

  // Clear selection
  clearSelection: () => {
    set({ selectedPrompt: null, history: [] })
  },

  // Toggle group expanded state
  toggleGroupExpanded: (groupId: number) => {
    set((state) => {
      const newExpanded = new Set(state.expandedGroups)
      if (newExpanded.has(groupId)) {
        newExpanded.delete(groupId)
      } else {
        newExpanded.add(groupId)
      }
      return { expandedGroups: newExpanded }
    })
  },

  // Toggle subgroup expanded state
  toggleSubgroupExpanded: (groupId: number, subgroupId: number) => {
    const key = `${groupId}-${subgroupId}`
    set((state) => {
      const newExpanded = new Set(state.expandedSubgroups)
      if (newExpanded.has(key)) {
        newExpanded.delete(key)
      } else {
        newExpanded.add(key)
      }
      return { expandedSubgroups: newExpanded }
    })
  },

  // Toggle culture type expanded state (для вложенных групп в Клубника/Малина+Ежевика)
  toggleCultureTypeExpanded: (subgroupId: number, cultureType: string) => {
    const key = `${subgroupId}-${cultureType}`
    set((state) => {
      const newExpanded = new Set(state.expandedCultureTypes)
      if (newExpanded.has(key)) {
        newExpanded.delete(key)
      } else {
        newExpanded.add(key)
      }
      return { expandedCultureTypes: newExpanded }
    })
  },

  // Set error message
  setError: (error: string | null) => {
    set({ error })
  },
}))
