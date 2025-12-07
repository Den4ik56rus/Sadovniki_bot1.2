/**
 * Filter Store - Фильтры видимости событий с localStorage persistence
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { EventType } from '@/types';

interface FilterStore {
  // Visible event types (true = visible)
  visibleTypes: Record<EventType, boolean>;
  // Visible cultures (true = visible)
  visibleCultures: Record<string, boolean>;

  // Actions
  toggleTypeVisibility: (type: EventType) => void;
  toggleCultureVisibility: (culture: string) => void;
  setTypeVisibility: (type: EventType, visible: boolean) => void;
  setCultureVisibility: (culture: string, visible: boolean) => void;
  showAllTypes: () => void;
  hideAllTypes: () => void;
  showAllCultures: () => void;
  hideAllCultures: () => void;

  // Selectors
  isTypeVisible: (type: EventType) => boolean;
  isCultureVisible: (culture: string) => boolean;
}

// Default all types visible
const defaultVisibleTypes: Record<EventType, boolean> = {
  nutrition: true,
  soil: true,
  protection: true,
  harvest: true,
  planting: true,
  other: true,
};

// Default all cultures visible
const defaultVisibleCultures: Record<string, boolean> = {
  // Клубника и подтипы
  'клубника': true,
  'клубника ремонтантная': true,
  'клубника летняя': true,
  // Малина и подтипы
  'малина': true,
  'малина ремонтантная': true,
  'малина летняя': true,
  // Остальные культуры
  'смородина': true,
  'голубика': true,
  'жимолость': true,
  'крыжовник': true,
  'ежевика': true,
};

export const useFilterStore = create<FilterStore>()(
  persist(
    (set, get) => ({
      visibleTypes: { ...defaultVisibleTypes },
      visibleCultures: { ...defaultVisibleCultures },

      toggleTypeVisibility: (type) => {
        set((state) => ({
          visibleTypes: {
            ...state.visibleTypes,
            [type]: !state.visibleTypes[type],
          },
        }));
      },

      toggleCultureVisibility: (culture) => {
        set((state) => ({
          visibleCultures: {
            ...state.visibleCultures,
            [culture]: !state.visibleCultures[culture],
          },
        }));
      },

      setTypeVisibility: (type, visible) => {
        set((state) => ({
          visibleTypes: {
            ...state.visibleTypes,
            [type]: visible,
          },
        }));
      },

      setCultureVisibility: (culture, visible) => {
        set((state) => ({
          visibleCultures: {
            ...state.visibleCultures,
            [culture]: visible,
          },
        }));
      },

      showAllTypes: () => {
        set({ visibleTypes: { ...defaultVisibleTypes } });
      },

      hideAllTypes: () => {
        set({
          visibleTypes: Object.fromEntries(
            Object.keys(defaultVisibleTypes).map((k) => [k, false])
          ) as Record<EventType, boolean>,
        });
      },

      showAllCultures: () => {
        set({ visibleCultures: { ...defaultVisibleCultures } });
      },

      hideAllCultures: () => {
        set({
          visibleCultures: Object.fromEntries(
            Object.keys(defaultVisibleCultures).map((k) => [k, false])
          ),
        });
      },

      isTypeVisible: (type) => get().visibleTypes[type] ?? true,

      isCultureVisible: (culture) => {
        // If culture is empty or undefined, show the event
        if (!culture) return true;
        return get().visibleCultures[culture] ?? true;
      },
    }),
    {
      name: 'sadovniki-calendar-filters',
      version: 1,
    }
  )
);
