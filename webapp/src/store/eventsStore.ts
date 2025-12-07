/**
 * Events Store - Состояние событий с синхронизацией через API
 *
 * В Telegram WebApp: данные загружаются с сервера
 * В браузере (dev mode): используется localStorage
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { format, isSameDay } from 'date-fns';
import { parseLocalDateTime } from '@utils/dateUtils';
import type { CalendarEvent, EventStatus, EventType } from '@/types';
import { api } from '@services/api';

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
  getEventsByDate: (date: Date) => CalendarEvent[];
  getEventsForMonth: (month: Date) => Map<string, CalendarEvent[]>;
  getAllEvents: () => CalendarEvent[];
}

// Store для работы с API (Telegram WebApp)
const createApiStore = (
  set: (fn: (state: EventsStore) => Partial<EventsStore>) => void,
  get: () => EventsStore
): EventsStore => ({
  events: {},
  isLoading: false,
  isSynced: false,
  error: null,

  fetchEvents: async (start?: Date, end?: Date) => {
    set(() => ({ isLoading: true, error: null }));
    try {
      const events = await api.getEvents(
        start?.toISOString(),
        end?.toISOString()
      );
      const eventsMap = Object.fromEntries(events.map((e) => [e.id, e]));
      set(() => ({ events: eventsMap, isSynced: true }));
    } catch (error) {
      console.error('Failed to fetch events:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to fetch events',
      }));
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  addEvent: async (eventData) => {
    set(() => ({ isLoading: true, error: null }));
    try {
      const event = await api.createEvent(eventData);
      set((state) => ({
        events: { ...state.events, [event.id]: event },
      }));
      return event.id;
    } catch (error) {
      console.error('Failed to create event:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to create event',
      }));
      throw error;
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  updateEvent: async (id, data) => {
    set(() => ({ isLoading: true, error: null }));
    try {
      const event = await api.updateEvent(id, data);
      set((state) => ({
        events: { ...state.events, [event.id]: event },
      }));
    } catch (error) {
      console.error('Failed to update event:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to update event',
      }));
      throw error;
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  deleteEvent: async (id) => {
    set(() => ({ isLoading: true, error: null }));
    try {
      await api.deleteEvent(id);
      set((state) => {
        const { [id]: _, ...rest } = state.events;
        return { events: rest };
      });
    } catch (error) {
      console.error('Failed to delete event:', error);
      set(() => ({
        error: error instanceof Error ? error.message : 'Failed to delete event',
      }));
      throw error;
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  setEventStatus: async (id, status) => {
    set(() => ({ isLoading: true, error: null }));
    try {
      const event = await api.updateEventStatus(id, status);
      set((state) => ({
        events: { ...state.events, [event.id]: event },
      }));
    } catch (error) {
      console.error('Failed to update event status:', error);
      set(() => ({
        error:
          error instanceof Error ? error.message : 'Failed to update event status',
      }));
      throw error;
    } finally {
      set(() => ({ isLoading: false }));
    }
  },

  clearError: () => set(() => ({ error: null })),

  getEventById: (id) => get().events[id],

  getEventsByDate: (date) => {
    const events = Object.values(get().events);
    return events
      .filter((event) => {
        const eventDate = parseLocalDateTime(event.startDateTime);
        return isSameDay(eventDate, date);
      })
      .sort((a, b) => {
        // All-day events first
        if (a.allDay && !b.allDay) return -1;
        if (!a.allDay && b.allDay) return 1;
        // Then by start time
        return a.startDateTime.localeCompare(b.startDateTime);
      });
  },

  getEventsForMonth: (_month) => {
    const map = new Map<string, CalendarEvent[]>();
    const events = Object.values(get().events);

    events.forEach((event) => {
      const dateKey = event.startDateTime.slice(0, 10); // YYYY-MM-DD
      const existing = map.get(dateKey) || [];
      map.set(dateKey, [...existing, event]);
    });

    // Sort events within each day
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

  getAllEvents: () => Object.values(get().events),
});

// Store для локальной разработки (localStorage)
const createLocalStore = (
  set: (fn: (state: EventsStore) => Partial<EventsStore>) => void,
  get: () => EventsStore
): EventsStore => ({
  events: {},
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

  getEventsByDate: (date) => {
    const events = Object.values(get().events);
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

  getEventsForMonth: (_month) => {
    const map = new Map<string, CalendarEvent[]>();
    const events = Object.values(get().events);

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

  getAllEvents: () => Object.values(get().events),
});

// Определяем, какой store использовать
const shouldUseApi = () => {
  // Используем API если:
  // 1. Есть Telegram WebApp initData
  // 2. Настроен API URL
  return api.isTelegramWebApp() && api.isApiConfigured();
};

// Создаём store с условной персистенцией
export const useEventsStore = create<EventsStore>()(
  // Оборачиваем в persist только для локального режима
  shouldUseApi()
    ? (set, get) => createApiStore(set, get)
    : persist(
        (set, get) => createLocalStore(set, get),
        {
          name: 'sadovniki-calendar-events',
          version: 1,
          migrate: (persistedState: unknown, _version: number) => {
            return persistedState as EventsStore;
          },
        }
      )
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
