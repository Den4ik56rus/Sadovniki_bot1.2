/**
 * useFilteredEvents - Хук для получения отфильтрованных событий
 */

import { useMemo } from 'react';
import { useEventsStore } from '@store/eventsStore';
import { useFilterStore } from '@store/filterStore';
import { useUIStore } from '@store/uiStore';
import { usePlantingsStore } from '@store/plantingsStore';
import { getCultureCode } from '@constants/plantingCultures';
import type { CalendarEvent } from '@/types';

/**
 * Возвращает все события, отфильтрованные по настройкам видимости
 * и по выбранной культуре из топбара
 */
export function useFilteredEvents(): CalendarEvent[] {
  const events = useEventsStore((state) => state.events);
  const { visibleTypes, visibleCultures } = useFilterStore();
  const selectedCultureFilter = useUIStore((state) => state.selectedCultureFilter);
  const plantings = usePlantingsStore((state) => state.plantings);

  // Получаем cultureCode для выбранной посадки
  const selectedCultureCode = useMemo(() => {
    if (!selectedCultureFilter) return null;
    const planting = plantings.find((p) => p.id === selectedCultureFilter);
    return planting ? getCultureCode(planting) : null;
  }, [selectedCultureFilter, plantings]);

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

      // Фильтр по выбранной культуре из топбара (если выбрана)
      if (selectedCultureCode && event.cultureCode !== selectedCultureCode) {
        return false;
      }

      return true;
    });
  }, [events, visibleTypes, visibleCultures, selectedCultureCode]);
}

/**
 * Возвращает события как Record<id, event>, отфильтрованные по настройкам видимости
 * и по выбранной культуре из топбара
 */
export function useFilteredEventsRecord(): Record<string, CalendarEvent> {
  const events = useEventsStore((state) => state.events);
  const { visibleTypes, visibleCultures } = useFilterStore();
  const selectedCultureFilter = useUIStore((state) => state.selectedCultureFilter);
  const plantings = usePlantingsStore((state) => state.plantings);

  // Получаем cultureCode для выбранной посадки
  const selectedCultureCode = useMemo(() => {
    if (!selectedCultureFilter) return null;
    const planting = plantings.find((p) => p.id === selectedCultureFilter);
    return planting ? getCultureCode(planting) : null;
  }, [selectedCultureFilter, plantings]);

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

      // Фильтр по выбранной культуре из топбара (если выбрана)
      if (selectedCultureCode && event.cultureCode !== selectedCultureCode) {
        return;
      }

      filtered[id] = event;
    });

    return filtered;
  }, [events, visibleTypes, visibleCultures, selectedCultureCode]);
}
