/**
 * EventDots - Индикаторы событий в ячейке дня
 * Показывает иконки культур или цветные точки, до 3 элементов, затем "+N"
 */

import type { CalendarEvent } from '@/types/event';
import { EVENT_TYPES } from '@constants/eventTypes';
import { getCultureIconFromCode } from '@constants/plantingCultures';
import styles from './EventDots.module.css';

interface EventDotsProps {
  events: CalendarEvent[];
  maxDots?: number;
}

export function EventDots({ events, maxDots = 3 }: EventDotsProps) {
  const visibleEvents = events.slice(0, maxDots);
  const remainingCount = events.length - maxDots;

  return (
    <div className={styles.dots}>
      {visibleEvents.map((event) => {
        const typeInfo = EVENT_TYPES[event.type];
        const color = event.color || typeInfo?.color || '#9E9E9E';

        // Если есть культура — показываем иконку
        if (event.cultureCode) {
          const CultureIcon = getCultureIconFromCode(event.cultureCode);
          if (CultureIcon) {
            return (
              <span
                key={event.id}
                className={styles.cultureIcon}
                style={{ color }}
              >
                <CultureIcon width={12} height={12} />
              </span>
            );
          }
        }

        // Иначе — обычная точка
        return (
          <span
            key={event.id}
            className={styles.dot}
            style={{ backgroundColor: color }}
          />
        );
      })}
      {remainingCount > 0 && (
        <span className={styles.more}>+{remainingCount}</span>
      )}
    </div>
  );
}
