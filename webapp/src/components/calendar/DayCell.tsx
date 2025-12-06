/**
 * DayCell - Ячейка дня в календаре
 * Отображает число и индикаторы событий
 */

import { getDate, isWeekend } from 'date-fns';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import type { CalendarEvent } from '@/types/event';
import { EventDots } from './EventDots';
import styles from './DayCell.module.css';

interface DayCellProps {
  date: Date;
  events: CalendarEvent[];
  isCurrentMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
  onClick: () => void;
}

export function DayCell({
  date,
  events,
  isCurrentMonth,
  isToday,
  isSelected,
  onClick,
}: DayCellProps) {
  const { light } = useTelegramHaptic();
  const dayNumber = getDate(date);
  const isWeekendDay = isWeekend(date);

  const handleClick = () => {
    light();
    onClick();
  };

  const cellClasses = [
    styles.cell,
    !isCurrentMonth && styles.otherMonth,
    isToday && styles.today,
    isSelected && styles.selected,
    isWeekendDay && styles.weekend,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      className={cellClasses}
      onClick={handleClick}
      aria-label={date.toLocaleDateString('ru-RU')}
      aria-pressed={isSelected}
    >
      <span className={styles.number}>{dayNumber}</span>
      {events.length > 0 && <EventDots events={events} />}
    </button>
  );
}
