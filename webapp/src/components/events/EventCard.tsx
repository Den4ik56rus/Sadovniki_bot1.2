/**
 * EventCard - Карточка события в списке
 * Отображает даты, заголовок и тип события
 */

import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { parseLocalDateTime } from '@utils/dateUtils';
import type { CalendarEvent } from '@/types/event';
import { EVENT_TYPES } from '@constants/eventTypes';
import { CULTURES } from '@constants/cultures';
import styles from './EventCard.module.css';

interface EventCardProps {
  event: CalendarEvent;
  onClick: () => void;
}

export function EventCard({ event, onClick }: EventCardProps) {
  const typeInfo = EVENT_TYPES[event.type];
  const cultureInfo = event.cultureCode ? CULTURES[event.cultureCode] : null;
  const color = event.color || typeInfo?.color || '#9E9E9E';

  // Форматируем даты
  const startDate = parseLocalDateTime(event.startDateTime);
  const endDate = event.endDateTime ? parseLocalDateTime(event.endDateTime) : null;
  const startDateStr = format(startDate, 'd MMM', { locale: ru });
  const endDateStr = endDate ? format(endDate, 'd MMM', { locale: ru }) : null;
  const hasEndDate = endDate && endDateStr !== startDateStr;

  const dateLabel = hasEndDate ? `${startDateStr} — ${endDateStr}` : startDateStr;

  return (
    <button
      className={styles.card}
      onClick={onClick}
      style={{ '--event-color': color } as React.CSSProperties}
    >
      <div className={styles.colorBar} />
      <div className={styles.content}>
        <div className={styles.header}>
          <span className={styles.date}>{dateLabel}</span>
          {cultureInfo && (
            <span className={styles.culture}>{cultureInfo.icon}</span>
          )}
        </div>
        <h3 className={styles.title}>{event.title}</h3>
        {event.plotId && (
          <span className={styles.plot}>{event.plotId}</span>
        )}
      </div>
    </button>
  );
}
