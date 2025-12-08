/**
 * EventRow - Строка события в списке работ
 * Формат: "5 ЯНВАРЯ — Название события [иконка культуры]"
 */

import { format, isSameDay } from 'date-fns';
import { ru } from 'date-fns/locale';
import { parseLocalDateTime } from '@utils/dateUtils';
import { getCultureIconComponent, getCultureTypeFromCode } from '@/constants/plantingCultures';
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

export function EventRow({ event, onClick }: EventRowProps) {
  const dateRange = formatDateRange(event);
  const cultureType = event.cultureCode ? getCultureTypeFromCode(event.cultureCode) : null;
  const CultureIcon = cultureType ? getCultureIconComponent(cultureType) : null;

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
