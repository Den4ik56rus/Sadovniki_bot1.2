/**
 * WeekRow - Строка недели с событиями
 * Отображает дни в виде сетки с событиями
 */

import { useRef } from 'react';
import { getDate, isWeekend, isSameMonth, isToday, isSameDay } from 'date-fns';
import { useCalendarStore } from '@store/calendarStore';
import { useUIStore } from '@store/uiStore';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { useEventDragResize } from '@hooks/useEventDragResize';
import type { CalendarEvent } from '@/types/event';
import { getWeekEvents, getEventColor, type PositionedEvent } from '@utils/eventLayoutUtils';
import styles from './WeekRow.module.css';

interface WeekRowProps {
  weekDays: Date[];
  events: CalendarEvent[];
}

export function WeekRow({ weekDays, events }: WeekRowProps) {
  const { currentDate, selectedDate, setSelectedDate } = useCalendarStore();
  const { selectedEventId, selectEvent } = useUIStore();
  const openEventDetails = useUIStore((state) => state.openEventDetails);
  const { light } = useTelegramHaptic();
  const overlayRef = useRef<HTMLDivElement>(null);

  // Позиционируем события
  const positionedEvents = getWeekEvents(weekDays, events);

  const handleDayClick = (day: Date) => {
    light();
    setSelectedDate(day);
    // Снимаем выделение с события при клике на день
    selectEvent(null);
  };

  const handleEventClick = (event: CalendarEvent) => {
    light();
    openEventDetails(event.id);
  };

  return (
    <div className={styles.weekRow}>
      {/* Сетка ячеек дней */}
      <div className={styles.dayCells}>
        {weekDays.map((day) => {
          const dayNum = getDate(day);
          const isCurrentMonth = isSameMonth(day, currentDate);
          const isTodayDay = isToday(day);
          const isSelected = selectedDate ? isSameDay(day, selectedDate) : false;
          const isWeekendDay = isWeekend(day);

          const cellClasses = [
            styles.dayCell,
            !isCurrentMonth && styles.otherMonth,
            isWeekendDay && styles.weekend,
          ].filter(Boolean).join(' ');

          const numberClasses = [
            styles.dayNumber,
            isTodayDay && styles.today,
            isSelected && styles.selected,
          ].filter(Boolean).join(' ');

          return (
            <button
              key={day.toISOString()}
              className={cellClasses}
              onClick={() => handleDayClick(day)}
            >
              <span className={numberClasses}>{dayNum}</span>
            </button>
          );
        })}
      </div>

      {/* Overlay событий - поверх ячеек дней */}
      {positionedEvents.length > 0 && (
        <div className={styles.eventsOverlay} ref={overlayRef}>
          {positionedEvents.map((pe) => (
            <EventBar
              key={pe.event.id}
              positioned={pe}
              weekDays={weekDays}
              containerRef={overlayRef}
              isSelected={selectedEventId === pe.event.id}
              onEventClick={handleEventClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Компонент события (полоска)
interface EventBarProps {
  positioned: PositionedEvent;
  weekDays: Date[];
  containerRef: React.RefObject<HTMLDivElement | null>;
  isSelected: boolean;
  onEventClick: (event: CalendarEvent) => void;
}

function EventBar({ positioned, weekDays, containerRef, isSelected, onEventClick }: EventBarProps) {
  const { event, startCol, endCol, row, continuesFromPrev, continuesToNext } = positioned;
  const color = getEventColor(event);

  // Хук для drag/resize
  const {
    isDragging,
    isResizing,
    previewStartCol,
    previewEndCol,
    handlePointerDown,
    handleResizePointerDown,
  } = useEventDragResize({
    event,
    startCol,
    endCol,
    weekDays,
    containerRef,
  });

  // Используем preview позиции при drag/resize
  const displayStartCol = isDragging || isResizing ? previewStartCol : startCol;
  const displayEndCol = isDragging || isResizing ? previewEndCol : endCol;
  const span = displayEndCol - displayStartCol + 1;

  // CSS переменные для позиционирования
  const style: React.CSSProperties = {
    '--start-col': displayStartCol,
    '--span': span,
    '--row': row,
    '--event-color': color,
  } as React.CSSProperties;

  const classes = [
    styles.eventBar,
    continuesFromPrev && !isDragging && styles.continuesLeft,
    continuesToNext && !isDragging && styles.continuesRight,
    isSelected && styles.eventBarSelected,
    isDragging && styles.eventBarDragging,
  ].filter(Boolean).join(' ');

  // Обработчик двойного клика для открытия деталей
  const handleDoubleClick = () => {
    onEventClick(event);
  };

  return (
    <div
      className={classes}
      style={style}
      onPointerDown={handlePointerDown}
      onDoubleClick={handleDoubleClick}
      title={event.title}
    >
      <span className={styles.eventTitle}>{event.title}</span>

      {/* Resize handles - показываем только для выделенного события */}
      {isSelected && !isDragging && (
        <>
          {/* Левая ручка (начало) */}
          <div
            className={`${styles.resizeHandle} ${styles.resizeHandleStart}`}
            onPointerDown={(e) => handleResizePointerDown('start', e)}
          />
          {/* Правая ручка (конец) */}
          <div
            className={`${styles.resizeHandle} ${styles.resizeHandleEnd}`}
            onPointerDown={(e) => handleResizePointerDown('end', e)}
          />
        </>
      )}
    </div>
  );
}
