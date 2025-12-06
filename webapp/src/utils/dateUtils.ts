/**
 * Date Utils - Утилиты для работы с датами
 */

import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
  isToday,
  isWeekend,
  format,
  parseISO,
  addMonths,
  subMonths,
} from 'date-fns';
import { ru } from 'date-fns/locale';

/**
 * Парсит ISO datetime строку и возвращает дату в локальном времени
 * Избегает проблем с часовыми поясами
 */
export function parseLocalDateTime(isoString: string): Date {
  // Извлекаем компоненты из ISO строки
  const datePart = isoString.slice(0, 10); // YYYY-MM-DD
  const timePart = isoString.slice(11, 19) || '00:00:00'; // HH:mm:ss

  const [year, month, day] = datePart.split('-').map(Number);
  const [hours, minutes, seconds] = timePart.split(':').map(Number);

  return new Date(year, month - 1, day, hours || 0, minutes || 0, seconds || 0);
}

/**
 * Создаёт дату в локальном времени из компонентов YYYY-MM-DD
 */
export function createLocalDate(year: number, month: number, day: number): Date {
  return new Date(year, month - 1, day, 12, 0, 0); // Полдень чтобы избежать проблем с DST
}

/**
 * Генерация сетки календаря для месяца
 * @param month - Дата месяца
 * @param weekStartsOn - День начала недели (1 = понедельник)
 * @returns Массив недель, каждая неделя - массив дат
 */
export function generateCalendarGrid(
  month: Date,
  weekStartsOn: 0 | 1 = 1
): Date[][] {
  const monthStart = startOfMonth(month);
  const monthEnd = endOfMonth(month);

  // Получаем полную сетку включая дни соседних месяцев
  const gridStart = startOfWeek(monthStart, { weekStartsOn });
  const gridEnd = endOfWeek(monthEnd, { weekStartsOn });

  const allDays = eachDayOfInterval({ start: gridStart, end: gridEnd });

  // Разбиваем на недели (строки)
  const weeks: Date[][] = [];
  for (let i = 0; i < allDays.length; i += 7) {
    weeks.push(allDays.slice(i, i + 7));
  }

  return weeks; // 5 или 6 недель
}

/**
 * Получить информацию о дне
 */
export function getDayInfo(
  day: Date,
  currentMonth: Date,
  selectedDate: Date | null
) {
  return {
    date: day,
    isCurrentMonth: isSameMonth(day, currentMonth),
    isToday: isToday(day),
    isSelected: selectedDate ? isSameDay(day, selectedDate) : false,
    isWeekend: isWeekend(day),
  };
}

/**
 * Получить статус дня для стилизации (alias для getDayInfo)
 */
export function getDayStatus(
  day: Date,
  currentMonth: Date,
  selectedDate: Date | null
) {
  return {
    isCurrentMonth: isSameMonth(day, currentMonth),
    isToday: isToday(day),
    isSelected: selectedDate ? isSameDay(day, selectedDate) : false,
  };
}

/**
 * Форматирование месяца и года на русском
 * @example "Январь 2026"
 */
export function formatMonthYear(date: Date): string {
  return format(date, 'LLLL yyyy', { locale: ru });
}

/**
 * Форматирование даты на русском
 * @example "15 января 2026"
 */
export function formatDateFull(date: Date): string {
  return format(date, 'd MMMM yyyy', { locale: ru });
}

/**
 * Форматирование даты коротко
 * @example "15 янв"
 */
export function formatDateShort(date: Date): string {
  return format(date, 'd MMM', { locale: ru });
}

/**
 * Форматирование времени
 * @example "09:00"
 */
export function formatTime(date: Date | string): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'HH:mm');
}

/**
 * Форматирование даты и времени
 * @example "15 янв, 09:00"
 */
export function formatDateTime(date: Date | string): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'd MMM, HH:mm', { locale: ru });
}

/**
 * Форматирование для input date
 * @example "2026-01-15"
 */
export function formatDateForInput(date: Date): string {
  return format(date, 'yyyy-MM-dd');
}

/**
 * Форматирование для input time
 * @example "09:00"
 */
export function formatTimeForInput(date: Date): string {
  return format(date, 'HH:mm');
}

/**
 * Парсинг ISO даты
 */
export function parseDateISO(dateString: string): Date {
  return parseISO(dateString);
}

/**
 * Создать ISO datetime строку
 */
export function toISODateTime(date: string, time: string): string {
  return `${date}T${time}:00`;
}

/**
 * Получить ключ даты для группировки событий
 * @example "2026-01-15"
 */
export function getDateKey(date: Date | string): string {
  const d = typeof date === 'string' ? parseISO(date) : date;
  return format(d, 'yyyy-MM-dd');
}

/**
 * Проверить, является ли дата сегодняшней
 */
export { isToday };

/**
 * Проверить, совпадают ли две даты (без учёта времени)
 */
export { isSameDay };

/**
 * Проверить, в том же месяце ли дата
 */
export { isSameMonth };

/**
 * Добавить месяцы к дате
 */
export { addMonths, subMonths };
