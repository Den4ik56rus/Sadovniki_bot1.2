/**
 * MonthGrid - Сетка месяца
 * Grid view с многодневными событиями (стиль Apple Calendar)
 */

import { useRef, useMemo, useEffect, useState, useCallback } from 'react';
import { useCalendarStore } from '@store/calendarStore';
import { useUIStore } from '@store/uiStore';
import { useCalendarDrag, useFilteredEvents, useSwipeNavigation, hapticImpact } from '@hooks/index';
import { generateCalendarGrid } from '@utils/dateUtils';
import { WEEKDAYS_SHORT } from '@constants/ui';
import { WeekRow } from './WeekRow';
import styles from './MonthGrid.module.css';

export function MonthGrid() {
  const { currentDate, slideDirection, clearSlideDirection, goToNextMonth, goToPrevMonth } = useCalendarStore();
  const filteredEvents = useFilteredEvents();
  const isCalendarExpanded = useUIStore((state) => state.isCalendarExpanded);
  const weeksContainerRef = useRef<HTMLDivElement>(null);
  const [isAnimating, setIsAnimating] = useState(false);

  // Обработчики свайпа
  const handleSwipeLeft = useCallback(() => {
    if (isAnimating) return;
    hapticImpact('light');
    goToNextMonth();
  }, [isAnimating, goToNextMonth]);

  const handleSwipeRight = useCallback(() => {
    if (isAnimating) return;
    hapticImpact('light');
    goToPrevMonth();
  }, [isAnimating, goToPrevMonth]);

  const swipeHandlers = useSwipeNavigation({
    onSwipeLeft: handleSwipeLeft,
    onSwipeRight: handleSwipeRight,
    threshold: 50,
    enabled: isCalendarExpanded && !isAnimating,
  });

  // Запускаем анимацию при изменении направления
  useEffect(() => {
    if (slideDirection) {
      setIsAnimating(true);
      const timer = setTimeout(() => {
        setIsAnimating(false);
        clearSlideDirection();
      }, 300);
      return () => clearTimeout(timer);
    }
  }, [slideDirection, clearSlideDirection]);

  // Генерируем сетку календаря
  const weeks = generateCalendarGrid(currentDate, 1);

  // Все дни в flat array для drag
  const allDays = useMemo(() => weeks.flat(), [weeks]);

  // Отфильтрованные события
  const allEvents = filteredEvents;

  // Хук для drag по всему календарю
  const { dragState, handleEventPointerDown, handleResizePointerDown, getEventPreview } = useCalendarDrag({
    gridRef: weeksContainerRef,
    allDays,
  });

  // Определяем класс анимации
  const getAnimationClass = () => {
    if (!slideDirection || !isAnimating) return '';
    return slideDirection === 'left' ? styles.slideLeft : styles.slideRight;
  };

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

        {/* Сетка недель с анимацией */}
        <div
          key={currentDate.toISOString()}
          className={`${styles.weeksContainer} ${getAnimationClass()}`}
          ref={weeksContainerRef}
        >
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
