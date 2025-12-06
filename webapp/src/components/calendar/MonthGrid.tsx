/**
 * MonthGrid - Сетка месяца
 * Grid view с многодневными событиями (стиль Apple Calendar)
 */

import { useCalendarStore } from '@store/calendarStore';
import { useEventsStore } from '@store/eventsStore';
import { useUIStore } from '@store/uiStore';
import { useSwipeNavigation } from '@hooks/useSwipeNavigation';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { generateCalendarGrid } from '@utils/dateUtils';
import { WEEKDAYS_SHORT } from '@constants/ui';
import { WeekRow } from './WeekRow';
import styles from './MonthGrid.module.css';

export function MonthGrid() {
  const { currentDate, goToNextMonth, goToPrevMonth } = useCalendarStore();
  const events = useEventsStore((state) => state.events);
  const isCalendarExpanded = useUIStore((state) => state.isCalendarExpanded);
  const { light } = useTelegramHaptic();

  // Свайп навигация
  const swipeHandlers = useSwipeNavigation({
    onSwipeLeft: () => {
      light();
      goToNextMonth();
    },
    onSwipeRight: () => {
      light();
      goToPrevMonth();
    },
    threshold: 50,
  });

  // Генерируем сетку календаря
  const weeks = generateCalendarGrid(currentDate, 1); // Начало с понедельника

  // Все события как массив
  const allEvents = Object.values(events);

  return (
    <div
      className={`${styles.container} ${isCalendarExpanded ? styles.expanded : styles.collapsed}`}
      {...swipeHandlers}
    >
      <div className={styles.content}>
        {/* Заголовок с днями недели */}
        <div className={styles.weekdaysHeader}>
          {WEEKDAYS_SHORT.map((day, index) => (
            <div
              key={day}
              className={`${styles.weekday} ${index >= 5 ? styles.weekend : ''}`}
            >
              {day}
            </div>
          ))}
        </div>

        {/* Сетка недель */}
        <div className={styles.weeksContainer}>
          {weeks.map((week, weekIndex) => (
            <WeekRow
              key={weekIndex}
              weekDays={week}
              events={allEvents}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
