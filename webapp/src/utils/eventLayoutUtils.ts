/**
 * Event Layout Utils - Утилиты для позиционирования многодневных событий
 */

import {
  startOfDay,
  endOfDay,
  isBefore,
  isAfter,
  isSameDay,
  differenceInDays,
  max,
  min,
} from 'date-fns';

import type { CalendarEvent } from '@/types/event';

/**
 * Парсит ISO дату и возвращает начало дня в локальном времени
 * "2024-11-13T09:00:00" -> Date 13 ноября 00:00:00 (локальное время)
 */
function parseEventDate(isoString: string): Date {
  // Извлекаем дату из ISO строки (первые 10 символов: YYYY-MM-DD)
  const datePart = isoString.slice(0, 10);
  const [year, month, day] = datePart.split('-').map(Number);
  // Создаём дату в локальном времени (месяц 0-based)
  return new Date(year, month - 1, day);
}

/**
 * Событие, позиционированное в неделе
 */
export interface PositionedEvent {
  event: CalendarEvent;
  startCol: number;      // Начальная колонка (0-6)
  endCol: number;        // Конечная колонка (0-6)
  row: number;           // Строка в пределах недели
  continuesFromPrev: boolean;  // Продолжается с предыдущей недели
  continuesToNext: boolean;    // Продолжается на следующую неделю
}

/**
 * Получить события для недели с позиционированием
 */
export function getWeekEvents(
  weekDays: Date[],
  events: CalendarEvent[]
): PositionedEvent[] {
  const weekStart = startOfDay(weekDays[0]);
  const weekEnd = endOfDay(weekDays[6]);

  // Фильтруем события, которые пересекаются с этой неделей
  const weekEvents = events.filter((event) => {
    const eventStart = parseEventDate(event.startDateTime);
    const eventEnd = event.endDateTime ? parseEventDate(event.endDateTime) : eventStart;

    return !isAfter(startOfDay(eventStart), weekEnd) &&
           !isBefore(endOfDay(eventEnd), weekStart);
  });

  // Сортируем: сначала многодневные (длинные), потом по дате начала
  const sorted = [...weekEvents].sort((a, b) => {
    const aStart = parseEventDate(a.startDateTime);
    const aEnd = a.endDateTime ? parseEventDate(a.endDateTime) : aStart;
    const bStart = parseEventDate(b.startDateTime);
    const bEnd = b.endDateTime ? parseEventDate(b.endDateTime) : bStart;

    const aDuration = differenceInDays(aEnd, aStart);
    const bDuration = differenceInDays(bEnd, bStart);

    // Сначала более длинные события
    if (bDuration !== aDuration) return bDuration - aDuration;

    // Затем по дате начала
    return aStart.getTime() - bStart.getTime();
  });

  // Массив занятых ячеек: rows[row][col] = eventId или null
  const rows: (string | null)[][] = [];
  const positioned: PositionedEvent[] = [];

  for (const event of sorted) {
    const eventStart = parseEventDate(event.startDateTime);
    const eventEnd = event.endDateTime ? parseEventDate(event.endDateTime) : eventStart;

    // Вычисляем колонки в пределах недели
    const clampedStart = max([startOfDay(eventStart), weekStart]);
    const clampedEnd = min([endOfDay(eventEnd), weekEnd]);

    const startCol = weekDays.findIndex((d) => isSameDay(d, clampedStart));
    const endCol = weekDays.findIndex((d) => isSameDay(d, clampedEnd));

    if (startCol === -1 || endCol === -1) continue;

    // Проверяем продолжение
    const continuesFromPrev = isBefore(startOfDay(eventStart), weekStart);
    const continuesToNext = isAfter(endOfDay(eventEnd), weekEnd);

    // Находим первую свободную строку
    let row = 0;
    while (true) {
      if (!rows[row]) {
        rows[row] = Array(7).fill(null);
      }

      // Проверяем, свободны ли все ячейки
      let canPlace = true;
      for (let col = startCol; col <= endCol; col++) {
        if (rows[row][col] !== null) {
          canPlace = false;
          break;
        }
      }

      if (canPlace) {
        // Занимаем ячейки
        for (let col = startCol; col <= endCol; col++) {
          rows[row][col] = event.id;
        }
        break;
      }
      row++;

      // Лимит строк (для производительности)
      if (row > 10) break;
    }

    positioned.push({
      event,
      startCol,
      endCol,
      row,
      continuesFromPrev,
      continuesToNext,
    });
  }

  return positioned;
}

/**
 * Получить цвет события по типу
 */
export function getEventColor(event: CalendarEvent): string {
  if (event.color) return event.color;

  const colors: Record<string, string> = {
    nutrition: 'var(--color-nutrition)',
    soil: 'var(--color-soil)',
    protection: 'var(--color-protection)',
    harvest: 'var(--color-harvest)',
    planting: 'var(--color-planting)',
    other: 'var(--color-other)',
  };

  return colors[event.type] || colors.other;
}

/**
 * Получить количество строк для событий в неделе
 */
export function getMaxEventRows(positionedEvents: PositionedEvent[]): number {
  if (positionedEvents.length === 0) return 0;
  return Math.max(...positionedEvents.map((e) => e.row)) + 1;
}
