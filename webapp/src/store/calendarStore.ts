/**
 * Calendar Store - Состояние календаря
 */

import { create } from 'zustand';
import { addMonths, subMonths, startOfToday } from 'date-fns';
import type { ViewMode } from '@/types';

export type SlideDirection = 'left' | 'right' | null;

interface CalendarStore {
  // State
  currentDate: Date;
  selectedDate: Date | null;
  viewMode: ViewMode;
  slideDirection: SlideDirection;

  // Actions
  setCurrentDate: (date: Date) => void;
  setSelectedDate: (date: Date | null) => void;
  goToNextMonth: () => void;
  goToPrevMonth: () => void;
  goToToday: () => void;
  setViewMode: (mode: ViewMode) => void;
  clearSlideDirection: () => void;
}

export const useCalendarStore = create<CalendarStore>((set) => ({
  // Initial state
  currentDate: startOfToday(),
  selectedDate: null,
  viewMode: 'month',
  slideDirection: null,

  // Actions
  setCurrentDate: (date) => set({ currentDate: date }),

  setSelectedDate: (date) => set({ selectedDate: date }),

  goToNextMonth: () =>
    set((state) => ({
      currentDate: addMonths(state.currentDate, 1),
      slideDirection: 'left',
    })),

  goToPrevMonth: () =>
    set((state) => ({
      currentDate: subMonths(state.currentDate, 1),
      slideDirection: 'right',
    })),

  goToToday: () => {
    const today = startOfToday();
    set({
      currentDate: today,
      selectedDate: today,
      slideDirection: null,
    });
  },

  setViewMode: (mode) => set({ viewMode: mode }),

  clearSlideDirection: () => set({ slideDirection: null }),
}));
