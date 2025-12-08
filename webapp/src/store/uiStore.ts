/**
 * UI Store - Состояние интерфейса (без persistence)
 */

import { create } from 'zustand';
import type { Theme } from '@/types';

interface UIStore {
  // State
  isSideMenuOpen: boolean;
  isEventFormOpen: boolean;
  isEventDetailsOpen: boolean;
  isCalendarExpanded: boolean;
  isSearchOpen: boolean;
  editingEventId: string | null;
  viewingEventId: string | null;
  theme: Theme;
  initialFormDate: Date | null;  // Дата для предзаполнения формы

  // Culture filter
  isCultureFilterOpen: boolean;
  selectedCultureFilter: string | null; // null = все культуры, иначе planting.id

  // Plantings page state
  isPlantingsPageOpen: boolean;
  isPlantingFormOpen: boolean;
  editingPlantingId: string | null;

  // Event interaction (drag/resize)
  selectedEventId: string | null;

  // Actions
  openSideMenu: () => void;
  closeSideMenu: () => void;
  toggleSideMenu: () => void;

  openEventForm: (eventId?: string, initialDate?: Date) => void;
  closeEventForm: () => void;

  openEventDetails: (eventId: string) => void;
  closeEventDetails: () => void;

  // Plantings page actions
  openPlantingsPage: () => void;
  closePlantingsPage: () => void;
  openPlantingForm: (plantingId?: string) => void;
  closePlantingForm: () => void;

  setTheme: (theme: Theme) => void;

  // Calendar expand/collapse
  toggleCalendar: () => void;
  expandCalendar: () => void;
  collapseCalendar: () => void;

  // Search
  openSearch: () => void;
  closeSearch: () => void;

  // Culture filter
  toggleCultureFilter: () => void;
  closeCultureFilter: () => void;
  setCultureFilter: (plantingId: string | null) => void;

  // Event selection (for drag/resize)
  selectEvent: (eventId: string | null) => void;

  // Close all modals
  closeAll: () => void;
}

export const useUIStore = create<UIStore>((set) => ({
  // Initial state
  isSideMenuOpen: false,
  isEventFormOpen: false,
  isEventDetailsOpen: false,
  isCalendarExpanded: false, // ВРЕМЕННО: false для демо (показывать WorksList первым)
  isSearchOpen: false,
  editingEventId: null,
  viewingEventId: null,
  theme: 'light',
  initialFormDate: null,
  selectedEventId: null,

  // Culture filter
  isCultureFilterOpen: false,
  selectedCultureFilter: null,

  // Plantings page state
  isPlantingsPageOpen: false,
  isPlantingFormOpen: false,
  editingPlantingId: null,

  // Side Menu
  openSideMenu: () => set({ isSideMenuOpen: true }),
  closeSideMenu: () => set({ isSideMenuOpen: false }),
  toggleSideMenu: () => set((state) => ({ isSideMenuOpen: !state.isSideMenuOpen })),

  // Event Form
  openEventForm: (eventId, initialDate) =>
    set({
      isEventFormOpen: true,
      isEventDetailsOpen: false,  // Close details when opening form
      editingEventId: eventId || null,
      initialFormDate: initialDate || null,
    }),

  closeEventForm: () =>
    set({
      isEventFormOpen: false,
      editingEventId: null,
      initialFormDate: null,
    }),

  // Event Details
  openEventDetails: (eventId) =>
    set({
      isEventDetailsOpen: true,
      viewingEventId: eventId,
    }),

  closeEventDetails: () =>
    set({
      isEventDetailsOpen: false,
      viewingEventId: null,
    }),

  // Plantings Page
  openPlantingsPage: () =>
    set({
      isPlantingsPageOpen: true,
      isSideMenuOpen: false,  // Close side menu when opening plantings page
    }),

  closePlantingsPage: () =>
    set({
      isPlantingsPageOpen: false,
      isPlantingFormOpen: false,
      editingPlantingId: null,
    }),

  // Planting Form
  openPlantingForm: (plantingId) =>
    set({
      isPlantingFormOpen: true,
      editingPlantingId: plantingId || null,
    }),

  closePlantingForm: () =>
    set({
      isPlantingFormOpen: false,
      editingPlantingId: null,
    }),

  // Theme
  setTheme: (theme) => set({ theme }),

  // Calendar expand/collapse
  toggleCalendar: () => set((state) => ({ isCalendarExpanded: !state.isCalendarExpanded })),
  expandCalendar: () => set({ isCalendarExpanded: true }),
  collapseCalendar: () => set({ isCalendarExpanded: false }),

  // Search
  openSearch: () => set({ isSearchOpen: true }),
  closeSearch: () => set({ isSearchOpen: false }),

  // Culture filter
  toggleCultureFilter: () => set((state) => ({ isCultureFilterOpen: !state.isCultureFilterOpen })),
  closeCultureFilter: () => set({ isCultureFilterOpen: false }),
  setCultureFilter: (plantingId) => set({ selectedCultureFilter: plantingId, isCultureFilterOpen: false }),

  // Event selection (for drag/resize)
  selectEvent: (eventId) => set({ selectedEventId: eventId }),

  // Close all modals
  closeAll: () =>
    set({
      isSideMenuOpen: false,
      isEventFormOpen: false,
      isEventDetailsOpen: false,
      isSearchOpen: false,
      isCultureFilterOpen: false,
      isPlantingsPageOpen: false,
      isPlantingFormOpen: false,
      editingEventId: null,
      viewingEventId: null,
      editingPlantingId: null,
      initialFormDate: null,
      selectedEventId: null,
    }),
}));

/**
 * Helper: Check if any modal is open
 */
export function useAnyModalOpen() {
  const {
    isSideMenuOpen,
    isEventFormOpen,
    isEventDetailsOpen,
    isPlantingsPageOpen,
    isPlantingFormOpen,
    isCultureFilterOpen,
  } = useUIStore();
  return (
    isSideMenuOpen ||
    isEventFormOpen ||
    isEventDetailsOpen ||
    isPlantingsPageOpen ||
    isPlantingFormOpen ||
    isCultureFilterOpen
  );
}
