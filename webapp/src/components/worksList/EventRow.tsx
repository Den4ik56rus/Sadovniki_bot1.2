/**
 * EventRow - Строка события в списке работ
 * Формат: "5 ЯНВАРЯ — Название события [иконка культуры]"
 */

import { format, isSameDay } from 'date-fns';
import { ru } from 'date-fns/locale';
import { parseLocalDateTime } from '@utils/dateUtils';
import { getCultureIcon } from '@/constants/plantingCultures';
import type { CalendarEvent } from '@/types';
import styles from './EventRow.module.css';

interface EventRowProps {
  event: CalendarEvent;
  onClick: () => void;
}

/**
 * Форматирует диапазон дат для отображения
 * Однодневное: "5 ЯНВАРЯ"
 * Многодневное: "5-11 ЯНВАРЯ" или "28 ЯНВАРЯ - 3 ФЕВРАЛЯ"
 */
function formatDateRange(event: CalendarEvent): string {
  const startDate = parseLocalDateTime(event.startDateTime);
  const endDate = event.endDateTime ? parseLocalDateTime(event.endDateTime) : null;

  // Если нет endDateTime или даты совпадают — однодневное событие
  if (!endDate || isSameDay(startDate, endDate)) {
    return format(startDate, 'd MMMM', { locale: ru }).toUpperCase();
  }

  // Проверяем, в одном ли месяце даты
  const sameMonth = startDate.getMonth() === endDate.getMonth() &&
                    startDate.getFullYear() === endDate.getFullYear();

  if (sameMonth) {
    // "5-11 ЯНВАРЯ"
    const startDay = format(startDate, 'd', { locale: ru });
    const endFormatted = format(endDate, 'd MMMM', { locale: ru });
    return `${startDay}–${endFormatted}`.toUpperCase();
  } else {
    // "28 ЯНВАРЯ – 3 ФЕВРАЛЯ"
    const startFormatted = format(startDate, 'd MMMM', { locale: ru });
    const endFormatted = format(endDate, 'd MMMM', { locale: ru });
    return `${startFormatted} – ${endFormatted}`.toUpperCase();
  }
}

/**
 * Извлекает базовый код культуры из полного кода
 * "клубника ремонтантная" -> "strawberry"
 */
function getCultureBaseCode(cultureCode?: string): string | null {
  if (!cultureCode) return null;

  const cultureLower = cultureCode.toLowerCase();
  if (cultureLower.includes('клубник') || cultureLower.includes('земляник')) return 'strawberry';
  if (cultureLower.includes('малин')) return 'raspberry';
  if (cultureLower.includes('ежевик')) return 'blackberry';
  if (cultureLower.includes('смородин')) return 'currant';
  if (cultureLower.includes('голубик')) return 'blueberry';
  if (cultureLower.includes('жимолост')) return 'honeysuckle';
  if (cultureLower.includes('крыжовник')) return 'gooseberry';

  return null;
}

export function EventRow({ event, onClick }: EventRowProps) {
  const dateRange = formatDateRange(event);
  const cultureBaseCode = getCultureBaseCode(event.cultureCode);
  const CultureIcon = cultureBaseCode ? getCultureIcon(cultureBaseCode) : null;

  return (
    <button className={styles.row} onClick={onClick} type="button">
      <div className={styles.content}>
        <span className={styles.date}>{dateRange}</span>
        <span className={styles.separator}>—</span>
        <span className={styles.title}>{event.title}</span>
      </div>
      {CultureIcon && (
        <div className={styles.cultureIcon}>
          <CultureIcon />
        </div>
      )}
    </button>
  );
}
