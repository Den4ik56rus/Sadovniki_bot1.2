// RAG Documents Store — Паспортизация чанков
import { create } from 'zustand'
import { api } from '@/services/api'
import type {
  RagDocument,
  RagChunk,
  PassportOptions,
  UpdatePassportDto,
} from '@/types'

interface RagDocumentState {
  // Документы
  documents: RagDocument[]
  currentDocument: RagDocument | null

  // Чанки
  chunks: RagChunk[]
  currentChunkIndex: number

  // Справочники паспорта
  passportOptions: PassportOptions | null

  // Сохранённый выбор паспорта (для автозаполнения следующих чанков)
  lastPassportSelection: UpdatePassportDto

  // Состояние UI
  isLoading: boolean
  isUpdating: boolean
  isGeneratingContext: boolean
  isEmbedding: boolean  // Загрузка в библиотеку
  error: string | null

  // Режим редактора
  isEditorOpen: boolean

  // Actions
  fetchDocuments: () => Promise<void>
  fetchDocument: (id: number) => Promise<void>
  fetchChunks: (documentId: number) => Promise<void>
  fetchPassportOptions: () => Promise<void>

  updateChunkPassport: (chunkId: number, passport: UpdatePassportDto) => Promise<boolean>
  generateContext: (chunkId: number) => Promise<void>
  embedDocument: (id: number) => Promise<boolean>  // Загрузка в библиотеку
  updateDocumentSubcategory: (id: number, subcategory: string) => Promise<boolean>
  deleteDocument: (id: number) => Promise<void>
  clearAllDocuments: () => Promise<void>

  // Навигация по чанкам
  setCurrentChunk: (index: number) => void
  nextChunk: () => void
  prevChunk: () => void

  // Редактор
  openEditor: (documentId: number) => Promise<void>
  closeEditor: () => void

  // Helpers
  getCurrentChunk: () => RagChunk | null
  clearError: () => void
}

export const useRagDocumentStore = create<RagDocumentState>((set, get) => ({
  // Initial state
  documents: [],
  currentDocument: null,
  chunks: [],
  currentChunkIndex: 0,
  passportOptions: null,
  lastPassportSelection: {
    cultures: [],
    culture_subtypes: {},
    goals: [],
    growth_phases: [],
  },
  isLoading: false,
  isUpdating: false,
  isGeneratingContext: false,
  isEmbedding: false,
  error: null,
  isEditorOpen: false,

  // Fetch all documents
  fetchDocuments: async () => {
    set({ isLoading: true, error: null })
    try {
      const response = await api.getRagDocuments()
      set({ documents: response.documents, isLoading: false })
    } catch (err) {
      set({ error: String(err), isLoading: false })
    }
  },

  // Fetch single document
  fetchDocument: async (id: number) => {
    set({ isLoading: true, error: null })
    try {
      const doc = await api.getRagDocument(id)
      set({ currentDocument: doc, isLoading: false })
    } catch (err) {
      set({ error: String(err), isLoading: false })
    }
  },

  // Fetch chunks for document
  fetchChunks: async (documentId: number) => {
    set({ isLoading: true, error: null })
    try {
      const response = await api.getRagDocumentChunks(documentId)
      set({
        chunks: response.chunks,
        currentChunkIndex: 0,
        isLoading: false,
      })
    } catch (err) {
      set({ error: String(err), isLoading: false })
    }
  },

  // Fetch passport options (справочники)
  fetchPassportOptions: async () => {
    try {
      const options = await api.getPassportOptions()
      set({ passportOptions: options })
    } catch (err) {
      console.error('Failed to fetch passport options:', err)
    }
  },

  // Update chunk passport
  updateChunkPassport: async (chunkId: number, passport: UpdatePassportDto) => {
    set({ isUpdating: true, error: null })
    try {
      const response = await api.updateChunkPassport(chunkId, passport)

      if (response.success) {
        // Обновляем чанк в списке
        const chunks = get().chunks.map(c =>
          c.id === chunkId
            ? {
                ...c,
                cultures: response.chunk.cultures || [],
                culture_subtypes: response.chunk.culture_subtypes || {},
                goals: response.chunk.goals || [],
                growth_phases: response.chunk.growth_phases || [],
                chunk_text: response.chunk.chunk_text || c.chunk_text,
                chunk_size: response.chunk.chunk_size || c.chunk_size,
                prefix: response.chunk.prefix,
                context: response.chunk.context ?? c.context,
                is_passported: response.chunk.is_passported,
              }
            : c
        )

        // Сохраняем выбор для следующих чанков (без chunk_text и context)
        set({
          chunks,
          lastPassportSelection: {
            cultures: passport.cultures,
            culture_subtypes: passport.culture_subtypes,
            goals: passport.goals,
            growth_phases: passport.growth_phases,
          },
          isUpdating: false,
        })

        return true
      }

      set({ isUpdating: false })
      return false
    } catch (err) {
      set({ error: String(err), isUpdating: false })
      return false
    }
  },

  // Generate context for chunk
  generateContext: async (chunkId: number) => {
    set({ isGeneratingContext: true, error: null })
    try {
      const response = await api.generateChunkContext(chunkId)

      if (response.success) {
        // Обновляем чанк в списке
        const chunks = get().chunks.map(c =>
          c.id === chunkId
            ? { ...c, context: response.context }
            : c
        )
        set({ chunks, isGeneratingContext: false })
      } else {
        set({ isGeneratingContext: false })
      }
    } catch (err) {
      set({ error: String(err), isGeneratingContext: false })
    }
  },

  // Embed document (загрузка в библиотеку)
  embedDocument: async (id: number) => {
    set({ isEmbedding: true, error: null })
    try {
      const response = await api.embedRagDocument(id)

      if (response.success) {
        // Обновляем документ в списке
        const documents = get().documents.map(d =>
          d.id === id
            ? {
                ...d,
                status: 'completed' as const,
                is_embedded: true,
                embedding_tokens: response.embedding_tokens || d.embedding_tokens,
                embedding_cost: response.embedding_cost || d.embedding_cost,
              }
            : d
        )

        // Обновляем currentDocument если это текущий документ
        const currentDocument = get().currentDocument
        if (currentDocument?.id === id) {
          set({
            currentDocument: {
              ...currentDocument,
              status: 'completed',
              is_embedded: true,
              embedding_tokens: response.embedding_tokens || currentDocument.embedding_tokens,
              embedding_cost: response.embedding_cost || currentDocument.embedding_cost,
            },
          })
        }

        set({ documents, isEmbedding: false })
        return true
      }

      set({ error: response.error || 'Ошибка загрузки', isEmbedding: false })
      return false
    } catch (err) {
      set({ error: String(err), isEmbedding: false })
      return false
    }
  },

  // Update document subcategory
  updateDocumentSubcategory: async (id: number, subcategory: string) => {
    try {
      const response = await api.updateRagDocumentSubcategory(id, subcategory)
      if (response.success) {
        set((state) => ({
          documents: state.documents.map(d =>
            d.id === id ? { ...d, subcategory: response.subcategory } : d
          ),
        }))
        return true
      }
      return false
    } catch (err) {
      console.error('Failed to update subcategory:', err)
      return false
    }
  },

  // Delete document
  deleteDocument: async (id: number) => {
    set({ isLoading: true, error: null })
    try {
      await api.deleteRagDocument(id)
      const documents = get().documents.filter(d => d.id !== id)
      set({ documents, isLoading: false })
    } catch (err) {
      set({ error: String(err), isLoading: false })
    }
  },

  // Clear all documents
  clearAllDocuments: async () => {
    set({ isLoading: true, error: null })
    try {
      await api.clearAllRagDocuments()
      set({ documents: [], chunks: [], currentDocument: null, isLoading: false })
    } catch (err) {
      set({ error: String(err), isLoading: false })
    }
  },

  // Navigation
  setCurrentChunk: (index: number) => {
    const chunks = get().chunks
    if (index >= 0 && index < chunks.length) {
      set({ currentChunkIndex: index })
    }
  },

  nextChunk: () => {
    const { currentChunkIndex, chunks } = get()
    if (currentChunkIndex < chunks.length - 1) {
      set({ currentChunkIndex: currentChunkIndex + 1 })
    }
  },

  prevChunk: () => {
    const { currentChunkIndex } = get()
    if (currentChunkIndex > 0) {
      set({ currentChunkIndex: currentChunkIndex - 1 })
    }
  },

  // Editor
  openEditor: async (documentId: number) => {
    set({ isEditorOpen: true, isLoading: true })
    try {
      // Загружаем документ, чанки и опции параллельно
      const [doc, chunksResponse] = await Promise.all([
        api.getRagDocument(documentId),
        api.getRagDocumentChunks(documentId),
      ])

      // Загружаем опции если ещё не загружены
      if (!get().passportOptions) {
        await get().fetchPassportOptions()
      }

      set({
        currentDocument: doc,
        chunks: chunksResponse.chunks,
        currentChunkIndex: 0,
        isLoading: false,
      })
    } catch (err) {
      set({ error: String(err), isLoading: false })
    }
  },

  closeEditor: () => {
    set({
      isEditorOpen: false,
      currentDocument: null,
      chunks: [],
      currentChunkIndex: 0,
    })
  },

  // Helpers
  getCurrentChunk: () => {
    const { chunks, currentChunkIndex } = get()
    return chunks[currentChunkIndex] || null
  },

  clearError: () => set({ error: null }),
}))
