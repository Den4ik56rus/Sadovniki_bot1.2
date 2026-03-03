// Presentations Store — Zustand store for AI-generated presentations
import { create } from 'zustand'
import { api } from '@/services/api'
import type {
  PresentationListItem,
  Presentation,
  PresentationStyle,
  PresentationTemplate,
  PresentationProgressEvent,
  CompletedSlideInfo,
} from '@/types'

interface PresentationStore {
  // List
  presentations: PresentationListItem[]
  total: number
  isLoading: boolean

  // Detail
  selectedPresentation: Presentation | null
  isLoadingDetail: boolean

  // Styles
  styles: PresentationStyle[]
  isLoadingStyles: boolean

  // Templates
  templates: PresentationTemplate[]
  isLoadingTemplates: boolean

  // Generation
  isGenerating: boolean
  generationProgress: PresentationProgressEvent | null
  completedSlides: CompletedSlideInfo[]

  // Actions
  fetchPresentations: (params?: { limit?: number; offset?: number }) => Promise<void>
  fetchPresentation: (id: number) => Promise<void>
  fetchStyles: () => Promise<void>
  fetchTemplates: () => Promise<void>
  clearSelection: () => void
  setGenerationProgress: (event: PresentationProgressEvent | null) => void
  setIsGenerating: (v: boolean) => void
  addCompletedSlide: (slide: CompletedSlideInfo) => void
  clearCompletedSlides: () => void
}

export const usePresentationStore = create<PresentationStore>((set) => ({
  presentations: [],
  total: 0,
  isLoading: false,
  selectedPresentation: null,
  isLoadingDetail: false,
  styles: [],
  isLoadingStyles: false,
  templates: [],
  isLoadingTemplates: false,
  isGenerating: false,
  generationProgress: null,
  completedSlides: [],

  fetchPresentations: async (params) => {
    set({ isLoading: true })
    try {
      const result = await api.getPresentations(params)
      set({ presentations: result.presentations, total: result.total })
    } catch (err) {
      console.error('Failed to fetch presentations:', err)
    } finally {
      set({ isLoading: false })
    }
  },

  fetchPresentation: async (id) => {
    set({ isLoadingDetail: true })
    try {
      const pres = await api.getPresentation(id)
      set({ selectedPresentation: pres })
    } catch (err) {
      console.error('Failed to fetch presentation:', err)
    } finally {
      set({ isLoadingDetail: false })
    }
  },

  fetchStyles: async () => {
    set({ isLoadingStyles: true })
    try {
      const result = await api.getPresentationStyles()
      set({ styles: result.styles })
    } catch (err) {
      console.error('Failed to fetch styles:', err)
    } finally {
      set({ isLoadingStyles: false })
    }
  },

  fetchTemplates: async () => {
    set({ isLoadingTemplates: true })
    try {
      const result = await api.getPresentationTemplates()
      set({ templates: result.templates })
    } catch (err) {
      console.error('Failed to fetch templates:', err)
    } finally {
      set({ isLoadingTemplates: false })
    }
  },

  clearSelection: () => set({ selectedPresentation: null }),

  setGenerationProgress: (event) => set({ generationProgress: event }),

  setIsGenerating: (v) => set({ isGenerating: v }),

  addCompletedSlide: (slide) => set((state) => ({
    completedSlides: [...state.completedSlides.filter(s => s.slide_index !== slide.slide_index), slide]
      .sort((a, b) => a.slide_index - b.slide_index),
  })),

  clearCompletedSlides: () => set({ completedSlides: [] }),
}))
