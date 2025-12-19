// Zustand store для управления промт-документами

import { create } from 'zustand'
import { api } from '@/services/api'
import type {
  PromptCulture,
  PromptSubculture,
  PromptWorkType,
  PromptDocument,
  PromptDocumentFilters,
} from '@/types'

interface PromptDocumentStore {
  // State
  cultures: PromptCulture[]
  subcultures: PromptSubculture[]
  workTypes: PromptWorkType[]
  documents: PromptDocument[]
  total: number

  filters: PromptDocumentFilters
  selectedDocument: PromptDocument | null
  documentContent: string | null

  isLoading: boolean
  isUploading: boolean
  error: string | null

  // Modal state
  isUploadModalOpen: boolean
  isPreviewModalOpen: boolean

  // Actions
  fetchCultures: () => Promise<void>
  fetchSubcultures: (cultureId: number) => Promise<void>
  fetchWorkTypes: () => Promise<void>
  fetchDocuments: () => Promise<void>

  setFilters: (filters: Partial<PromptDocumentFilters>) => void
  clearFilters: () => void

  uploadDocument: (
    file: File,
    cultureId: number,
    subcultureId: number | null,
    workTypeId: number
  ) => Promise<boolean>
  deleteDocument: (id: number) => Promise<boolean>
  replaceDocument: (id: number, file: File) => Promise<boolean>

  selectDocument: (doc: PromptDocument | null) => void
  fetchDocumentContent: (id: number) => Promise<void>

  // Modal actions
  openUploadModal: () => void
  closeUploadModal: () => void
  openPreviewModal: (doc: PromptDocument) => void
  closePreviewModal: () => void

  clearError: () => void
}

export const usePromptDocumentStore = create<PromptDocumentStore>((set, get) => ({
  // Initial state
  cultures: [],
  subcultures: [],
  workTypes: [],
  documents: [],
  total: 0,

  filters: {},
  selectedDocument: null,
  documentContent: null,

  isLoading: false,
  isUploading: false,
  error: null,

  isUploadModalOpen: false,
  isPreviewModalOpen: false,

  // Fetch cultures
  fetchCultures: async () => {
    try {
      const cultures = await api.getPromptCultures()
      set({ cultures })
    } catch (error) {
      console.error('Failed to fetch cultures:', error)
      set({ error: 'Не удалось загрузить список культур' })
    }
  },

  // Fetch subcultures for a culture
  fetchSubcultures: async (cultureId: number) => {
    try {
      const subcultures = await api.getPromptSubcultures(cultureId)
      set({ subcultures })
    } catch (error) {
      console.error('Failed to fetch subcultures:', error)
      set({ subcultures: [] })
    }
  },

  // Fetch work types
  fetchWorkTypes: async () => {
    try {
      const workTypes = await api.getPromptWorkTypes()
      set({ workTypes })
    } catch (error) {
      console.error('Failed to fetch work types:', error)
      set({ error: 'Не удалось загрузить типы работ' })
    }
  },

  // Fetch documents with current filters
  fetchDocuments: async () => {
    const { filters } = get()
    set({ isLoading: true, error: null })

    try {
      const response = await api.getPromptDocuments(filters)
      set({
        documents: response.documents,
        total: response.total,
        isLoading: false,
      })
    } catch (error) {
      console.error('Failed to fetch documents:', error)
      set({
        error: 'Не удалось загрузить документы',
        isLoading: false,
      })
    }
  },

  // Set filters and refetch
  setFilters: (newFilters: Partial<PromptDocumentFilters>) => {
    const { filters, fetchDocuments, fetchSubcultures } = get()
    const updatedFilters = { ...filters, ...newFilters }

    // If culture changed, clear subculture and fetch new subcultures
    if (newFilters.culture_id !== undefined && newFilters.culture_id !== filters.culture_id) {
      updatedFilters.subculture_id = undefined
      if (newFilters.culture_id) {
        fetchSubcultures(newFilters.culture_id)
      } else {
        set({ subcultures: [] })
      }
    }

    set({ filters: updatedFilters })
    fetchDocuments()
  },

  // Clear all filters
  clearFilters: () => {
    set({
      filters: {},
      subcultures: [],
    })
    get().fetchDocuments()
  },

  // Upload new document
  uploadDocument: async (
    file: File,
    cultureId: number,
    subcultureId: number | null,
    workTypeId: number
  ) => {
    set({ isUploading: true, error: null })

    try {
      await api.uploadPromptDocument(file, cultureId, subcultureId, workTypeId)
      set({ isUploading: false, isUploadModalOpen: false })
      get().fetchDocuments()
      return true
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Ошибка загрузки'
      console.error('Failed to upload document:', error)
      set({
        error: message,
        isUploading: false,
      })
      return false
    }
  },

  // Delete document
  deleteDocument: async (id: number) => {
    try {
      await api.deletePromptDocument(id)
      get().fetchDocuments()
      return true
    } catch (error) {
      console.error('Failed to delete document:', error)
      set({ error: 'Не удалось удалить документ' })
      return false
    }
  },

  // Replace document file
  replaceDocument: async (id: number, file: File) => {
    set({ isUploading: true, error: null })

    try {
      await api.replacePromptDocument(id, file)
      set({ isUploading: false })
      get().fetchDocuments()
      return true
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Ошибка замены'
      console.error('Failed to replace document:', error)
      set({
        error: message,
        isUploading: false,
      })
      return false
    }
  },

  // Select document for preview
  selectDocument: (doc: PromptDocument | null) => {
    set({ selectedDocument: doc, documentContent: null })
  },

  // Fetch document content for preview
  fetchDocumentContent: async (id: number) => {
    try {
      const response = await api.getPromptDocumentContent(id)
      set({ documentContent: response.content })
    } catch (error) {
      console.error('Failed to fetch document content:', error)
      set({ documentContent: null })
    }
  },

  // Modal actions
  openUploadModal: () => set({ isUploadModalOpen: true, error: null }),
  closeUploadModal: () => set({ isUploadModalOpen: false }),

  openPreviewModal: (doc: PromptDocument) => {
    set({
      selectedDocument: doc,
      isPreviewModalOpen: true,
      documentContent: null,
    })
    get().fetchDocumentContent(doc.id)
  },
  closePreviewModal: () => set({ isPreviewModalOpen: false, selectedDocument: null, documentContent: null }),

  clearError: () => set({ error: null }),
}))
