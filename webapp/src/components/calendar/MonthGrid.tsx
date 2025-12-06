/**
 * MonthGrid - Сетка месяца
 * Grid view с многодневными событиями (стиль Apple Calendar)
 */

import { useRef, useMemo } from 'react';
import { useCalendarStore } from '@store/calendarStore';
import { useEventsStore } from '@store/eventsStore';
import { useUIStore } from '@store/uiStore';
import { useCalendarDrag } from '@hooks/useCalendarDrag';
import { generateCalendarGrid } from '@utils/dateUtils';
import { WEEKDAYS_SHORT } from '@constants/ui';
import { WeekRow } from './WeekRow';
import styles from './MonthGrid.module.css';

export function MonthGrid() {
  const { currentDate } = useCalendarStore();
  const events = useEventsStore((state) => state.events);
  const isCalendarExpanded = useUIStore((state) => state.isCalendarExpanded);
  const weeksContainerRef = useRef<HTMLDivElement>(null);

  // Генерируем сетку календаря
  const weeks = generateCalendarGrid(currentDate, 1);

  // Все дни в flat array для drag
  const allDays = useMemo(() => weeks.flat(), [weeks]);

  // Все события как массив
  const allEvents = Object.values(events);

  // Хук для drag по всему календарю
  const { dragState, handleEventPointerDown, handleResizePointerDown, getEventPreview } = useCalendarDrag({
    gridRef: weeksContainerRef,
    allDays,
  });

  return (
    <div
      className={`${styles.container} ${isCalendarExpanded ? styles.expanded : styles.collapsed}`}
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
        <div className={styles.weeksContainer} ref={weeksContainerRef}>
          {weeks.map((week, weekIndex) => (
            <WeekRow
              key={weekIndex}
              weekDays={week}
              events={allEvents}
              dragState={dragState}
              onEventPointerDown={handleEventPointerDown}
              onResizePointerDown={handleResizePointerDown}
              getEventPreview={getEventPreview}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
