/**
 * Events Store - Состояние событий с localStorage persistence
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { format, isSameDay } from 'date-fns';
import { parseLocalDateTime } from '@utils/dateUtils';
import type { CalendarEvent, EventStatus, EventType } from '@/types';

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
  events: Record<string, CalendarEvent>;  // id -> event
  isLoading: boolean;

  // Actions
  addEvent: (event: Omit<CalendarEvent, 'id' | 'createdAt' | 'updatedAt'>) => string;
  updateEvent: (id: string, data: Partial<CalendarEvent>) => void;
  deleteEvent: (id: string) => void;
  setEventStatus: (id: string, status: EventStatus) => void;

  // Selectors
  getEventById: (id: string) => CalendarEvent | undefined;
  getEventsByDate: (date: Date) => CalendarEvent[];
  getEventsForMonth: (month: Date) => Map<string, CalendarEvent[]>;
  getAllEvents: () => CalendarEvent[];
}

export const useEventsStore = create<EventsStore>()(
  persist(
    (set, get) => ({
      events: {},
      isLoading: false,

      addEvent: (eventData) => {
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

      updateEvent: (id, data) => {
        set((state) => {
          const existingEvent = state.events[id];
          if (!existingEvent) return state;

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

      deleteEvent: (id) => {
        set((state) => {
          const { [id]: _, ...rest } = state.events;
          return { events: rest };
        });
      },

      setEventStatus: (id, status) => {
        set((state) => {
          const existingEvent = state.events[id];
          if (!existingEvent) return state;

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
    }),
    {
      name: 'sadovniki-calendar-events',
      version: 1,
      // Migrate function for future schema changes
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
