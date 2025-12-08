/**
 * Events Store - Состояние событий с синхронизацией через API
 *
 * В Telegram WebApp: данные загружаются с сервера
 * В браузере (dev mode): используется localStorage
 */

import { create } from 'zustand';
import { format, isSameDay } from 'date-fns';
import { parseLocalDateTime } from '@utils/dateUtils';
import type { CalendarEvent, EventStatus, EventType } from '@/types';
// ВРЕМЕННО: демо-данные - удалить после тестирования!
import { generateDemoEvents } from '@/data/demoEvents';

// Полифил для crypto.randomUUID (не работает в старых мобильных браузерах)
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback для браузеров без crypto.randomUUID
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

interface EventsStore {
  // State
  events: Record<string, CalendarEvent>; // id -> event
  isLoading: boolean;
  isSynced: boolean;
  error: string | null;

  // Actions
  fetchEvents: (start?: Date, end?: Date) => Promise<void>;
  addEvent: (
    event: Omit<CalendarEvent, 'id' | 'createdAt' | 'updatedAt'>
  ) => Promise<string>;
  updateEvent: (id: string, data: Partial<CalendarEvent>) => Promise<void>;
  deleteEvent: (id: string) => Promise<void>;
  setEventStatus: (id: string, status: EventStatus) => Promise<void>;
  clearError: () => void;

  // Selectors
  getEventById: (id: string) => CalendarEvent | undefined;
  getEventsByDate: (date: Date, cultureCode?: string | null) => CalendarEvent[];
  getEventsForMonth: (month: Date, cultureCode?: string | null) => Map<string, CalendarEvent[]>;
  getAllEvents: (cultureCode?: string | null) => CalendarEvent[];
}

// ВРЕМЕННО: кэшируем демо-события - удалить после тестирования!
const DEMO_EVENTS = generateDemoEvents();

// Store для локальной разработки (localStorage)
const createLocalStore = (
  set: (fn: (state: EventsStore) => Partial<EventsStore>) => void,
  get: () => EventsStore
): EventsStore => ({
  // ВРЕМЕННО: используем демо-события - удалить после тестирования!
  events: DEMO_EVENTS,
  isLoading: false,
  isSynced: true, // В локальном режиме всегда "синхронизировано"
  error: null,

  fetchEvents: async () => {
    // В локальном режиме данные уже в store через persist
  },

  addEvent: async (eventData) => {
    const id = generateUUID();
    const now = new Date().toISOString();
    const event: CalendarEvent = {
      ...eventData,
      id,
      createdAt: now,
      updatedAt: now,
    };
    set((state) => ({
      events: { ...state.events, [id]: event },
    }));
    return id;
  },

  updateEvent: async (id, data) => {
    set((state) => {
      const existingEvent = state.events[id];
      if (!existingEvent) return {};

      return {
        events: {
          ...state.events,
          [id]: {
            ...existingEvent,
            ...data,
            updatedAt: new Date().toISOString(),
          },
        },
      };
    });
  },

  deleteEvent: async (id) => {
    set((state) => {
      const { [id]: _, ...rest } = state.events;
      return { events: rest };
    });
  },

  setEventStatus: async (id, status) => {
    set((state) => {
      const existingEvent = state.events[id];
      if (!existingEvent) return {};

      return {
        events: {
          ...state.events,
          [id]: {
            ...existingEvent,
            status,
            updatedAt: new Date().toISOString(),
          },
        },
      };
    });
  },

  clearError: () => set(() => ({ error: null })),

  getEventById: (id) => get().events[id],

  getEventsByDate: (date, cultureCode) => {
    let events = Object.values(get().events);

    // Фильтр по культуре если задан
    if (cultureCode) {
      events = events.filter((event) => event.cultureCode === cultureCode);
    }

    return events
      .filter((event) => {
        const eventDate = parseLocalDateTime(event.startDateTime);
        return isSameDay(eventDate, date);
      })
      .sort((a, b) => {
        if (a.allDay && !b.allDay) return -1;
        if (!a.allDay && b.allDay) return 1;
        return a.startDateTime.localeCompare(b.startDateTime);
      });
  },

  getEventsForMonth: (_month, cultureCode) => {
    const map = new Map<string, CalendarEvent[]>();
    let events = Object.values(get().events);

    // Фильтр по культуре если задан
    if (cultureCode) {
      events = events.filter((event) => event.cultureCode === cultureCode);
    }

    events.forEach((event) => {
      const dateKey = event.startDateTime.slice(0, 10);
      const existing = map.get(dateKey) || [];
      map.set(dateKey, [...existing, event]);
    });

    map.forEach((dayEvents, key) => {
      map.set(
        key,
        dayEvents.sort((a, b) => {
          if (a.allDay && !b.allDay) return -1;
          if (!a.allDay && b.allDay) return 1;
          return a.startDateTime.localeCompare(b.startDateTime);
        })
      );
    });

    return map;
  },

  getAllEvents: (cultureCode) => {
    let events = Object.values(get().events);
    if (cultureCode) {
      events = events.filter((event) => event.cultureCode === cultureCode);
    }
    return events;
  },
});

// ВРЕМЕННО: отключаем persist и используем демо-данные напрямую
// Удалить после тестирования и вернуть persist!
export const useEventsStore = create<EventsStore>()(
  (set, get) => createLocalStore(set, get)
);

/**
 * Helper: Create a new event with defaults
 */
export function createEventDefaults(date: Date): Partial<CalendarEvent> {
  return {
    title: '',
    startDateTime: format(date, "yyyy-MM-dd'T'09:00:00"),
    endDateTime: null,
    allDay: false,
    type: 'other' as EventType,
    status: 'planned' as EventStatus,
  };
}
