/**
 * useFilteredEvents - Хук для получения отфильтрованных событий
 */

import { useMemo } from 'react';
import { useEventsStore } from '@store/eventsStore';
import { useFilterStore } from '@store/filterStore';
import type { CalendarEvent } from '@/types';

/**
 * Возвращает все события, отфильтрованные по настройкам видимости
 */
export function useFilteredEvents(): CalendarEvent[] {
  const events = useEventsStore((state) => state.events);
  const { visibleTypes, visibleCultures } = useFilterStore();

  return useMemo(() => {
    return Object.values(events).filter((event) => {
      // Проверяем видимость типа
      if (!visibleTypes[event.type]) {
        return false;
      }

      // Проверяем видимость культуры (если указана)
      if (event.cultureCode && !visibleCultures[event.cultureCode]) {
        return false;
      }

      return true;
    });
  }, [events, visibleTypes, visibleCultures]);
}

/**
 * Возвращает события как Record<id, event>, отфильтрованные по настройкам видимости
 */
export function useFilteredEventsRecord(): Record<string, CalendarEvent> {
  const events = useEventsStore((state) => state.events);
  const { visibleTypes, visibleCultures } = useFilterStore();

  return useMemo(() => {
    const filtered: Record<string, CalendarEvent> = {};

    Object.entries(events).forEach(([id, event]) => {
      // Проверяем видимость типа
      if (!visibleTypes[event.type]) {
        return;
      }

      // Проверяем видимость культуры (если указана)
      if (event.cultureCode && !visibleCultures[event.cultureCode]) {
        return;
      }

      filtered[id] = event;
    });

    return filtered;
  }, [events, visibleTypes, visibleCultures]);
}
