/**
 * WeekRow - Строка недели с событиями
 * Отображает дни в виде сетки с событиями
 */

import { getDate, getMonth, isWeekend, isSameMonth, isToday, isSameDay, format } from 'date-fns';
import { parseLocalDateTime } from '@utils/dateUtils';
import { useCalendarStore } from '@store/calendarStore';
import { useUIStore } from '@store/uiStore';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import type { CalendarEvent } from '@/types/event';
import { getWeekEvents, getEventColor, type PositionedEvent } from '@utils/eventLayoutUtils';
import { MONTHS_FULL } from '@constants/ui';
import styles from './WeekRow.module.css';

// Типы для drag state (из useCalendarDrag)
interface DragState {
  eventId: string | null;
  isDragging: boolean;
  isResizing: 'start' | 'end' | null;
  previewStartDate: Date | null;
  previewEndDate: Date | null;
}

interface WeekRowProps {
  weekDays: Date[];
  events: CalendarEvent[];
  dragState: DragState;
  onEventPointerDown: (event: CalendarEvent, e: React.PointerEvent) => void;
  onResizePointerDown: (event: CalendarEvent, edge: 'start' | 'end', e: React.PointerEvent) => void;
  getEventPreview: (eventId: string) => { startDate: Date; endDate: Date } | null;
}

export function WeekRow({
  weekDays,
  events,
  dragState,
  onEventPointerDown,
  onResizePointerDown,
  getEventPreview,
}: WeekRowProps) {
  const { currentDate, selectedDate, setSelectedDate } = useCalendarStore();
  const { selectedEventId, selectEvent } = useUIStore();
  const openEventDetails = useUIStore((state) => state.openEventDetails);
  const { light } = useTelegramHaptic();

  // Позиционируем события для этой недели
  const positionedEvents = getWeekEvents(weekDays, events);

  // Проверяем, нужно ли показать перетаскиваемое событие в этой неделе
  // (если оно перетаскивается сюда из другой недели)
  const draggedEventInThisWeek = (() => {
    if (!dragState.eventId || !dragState.isDragging || !dragState.previewStartDate) {
      return null;
    }

    // Уже есть в positionedEvents?
    if (positionedEvents.some(pe => pe.event.id === dragState.eventId)) {
      return null;
    }

    // Проверяем попадает ли preview в эту неделю
    const weekStart = weekDays[0];
    const weekEnd = weekDays[6];
    const previewStart = dragState.previewStartDate;
    const previewEnd = dragState.previewEndDate || previewStart;

    if (previewStart <= weekEnd && previewEnd >= weekStart) {
      // Событие попадает в эту неделю - найдём его в events
      const event = events.find(e => e.id === dragState.eventId);
      if (event) {
        return event;
      }
    }

    return null;
  })();

  const handleDayClick = (day: Date) => {
    light();
    setSelectedDate(day);
    selectEvent(null);
  };

  const handleEventClick = (event: CalendarEvent) => {
    light();
    openEventDetails(event.id);
  };

  // Вычисляем позицию для перетаскиваемого события из другой недели
  const getDraggedEventPosition = (event: CalendarEvent): PositionedEvent | null => {
    if (!dragState.previewStartDate) return null;

    const weekStart = weekDays[0];
    const weekEnd = weekDays[6];
    const previewStart = dragState.previewStartDate;
    const previewEnd = dragState.previewEndDate || previewStart;

    let startCol = weekDays.findIndex(d => isSameDay(d, previewStart));
    let endCol = weekDays.findIndex(d => isSameDay(d, previewEnd));

    // Если начало до этой недели
    if (startCol === -1 && previewStart < weekStart) {
      startCol = 0;
    }
    // Если конец после этой недели
    if (endCol === -1 && previewEnd > weekEnd) {
      endCol = 6;
    }

    if (startCol === -1) startCol = 0;
    if (endCol === -1) endCol = 6;

    return {
      event,
      startCol,
      endCol,
      row: 0,
      continuesFromPrev: previewStart < weekStart,
      continuesToNext: previewEnd > weekEnd,
    };
  };

  return (
    <div className={styles.weekRow}>
      {/* Сетка ячеек дней */}
      <div className={styles.dayCells}>
        {weekDays.map((day) => {
          const dayNum = getDate(day);
          const isFirstOfMonth = dayNum === 1;
          const monthName = isFirstOfMonth ? MONTHS_FULL[getMonth(day)] : null;
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
              {isFirstOfMonth ? (
                <span className={styles.monthLabel}>
                  <span className={numberClasses}>{dayNum}</span>
                  <span className={styles.monthName}>{monthName}</span>
                </span>
              ) : (
                <span className={numberClasses}>{dayNum}</span>
              )}
            </button>
          );
        })}
      </div>

      {/* Overlay событий */}
      {(positionedEvents.length > 0 || draggedEventInThisWeek) && (
        <div className={styles.eventsOverlay}>
          {positionedEvents.map((pe) => (
            <EventBar
              key={pe.event.id}
              positioned={pe}
              weekDays={weekDays}
              isSelected={selectedEventId === pe.event.id}
              isDragging={dragState.eventId === pe.event.id && dragState.isDragging}
              isResizing={dragState.eventId === pe.event.id ? dragState.isResizing : null}
              onEventClick={handleEventClick}
              onPointerDown={onEventPointerDown}
              onResizePointerDown={onResizePointerDown}
              getEventPreview={getEventPreview}
            />
          ))}
          {/* Перетаскиваемое событие из другой недели */}
          {draggedEventInThisWeek && (() => {
            const draggedPosition = getDraggedEventPosition(draggedEventInThisWeek);
            if (!draggedPosition) return null;
            return (
              <EventBar
                key={`dragged-${draggedEventInThisWeek.id}`}
                positioned={draggedPosition}
                weekDays={weekDays}
                isSelected={selectedEventId === draggedEventInThisWeek.id}
                isDragging={true}
                isResizing={null}
                onEventClick={handleEventClick}
                onPointerDown={onEventPointerDown}
                onResizePointerDown={onResizePointerDown}
                getEventPreview={getEventPreview}
              />
            );
          })()}
        </div>
      )}
    </div>
  );
}

// Компонент события
interface EventBarProps {
  positioned: PositionedEvent;
  weekDays: Date[];
  isSelected: boolean;
  isDragging: boolean;
  isResizing: 'start' | 'end' | null;
  onEventClick: (event: CalendarEvent) => void;
  onPointerDown: (event: CalendarEvent, e: React.PointerEvent) => void;
  onResizePointerDown: (event: CalendarEvent, edge: 'start' | 'end', e: React.PointerEvent) => void;
  getEventPreview: (eventId: string) => { startDate: Date; endDate: Date } | null;
}

function EventBar({
  positioned,
  weekDays,
  isSelected,
  isDragging,
  isResizing,
  onEventClick,
  onPointerDown,
  onResizePointerDown,
  getEventPreview,
}: EventBarProps) {
  const { event, startCol, endCol, row, continuesFromPrev, continuesToNext } = positioned;
  const color = getEventColor(event);

  // Время события (если не allDay)
  const timeLabel = !event.allDay
    ? format(parseLocalDateTime(event.startDateTime), 'HH:mm')
    : null;

  // Проверяем есть ли preview для этого события
  const preview = getEventPreview(event.id);

  // Вычисляем колонки с учётом preview
  let displayStartCol = startCol;
  let displayEndCol = endCol;

  if (preview && (isDragging || isResizing)) {
    // Находим колонки для preview дат в этой неделе
    const previewStartIdx = weekDays.findIndex(d => isSameDay(d, preview.startDate));
    const previewEndIdx = weekDays.findIndex(d => isSameDay(d, preview.endDate));

    // Событие может быть частично или полностью вне этой недели
    if (previewStartIdx !== -1 || previewEndIdx !== -1) {
      displayStartCol = previewStartIdx !== -1 ? previewStartIdx : 0;
      displayEndCol = previewEndIdx !== -1 ? previewEndIdx : 6;

      // Если обе даты вне недели, не показываем
      if (previewStartIdx === -1 && previewEndIdx === -1) {
        // Проверяем, попадает ли неделя между start и end
        const weekStart = weekDays[0];
        const weekEnd = weekDays[6];
        if (preview.startDate <= weekEnd && preview.endDate >= weekStart) {
          displayStartCol = 0;
          displayEndCol = 6;
        } else {
          return null; // Событие не в этой неделе
        }
      }
    } else {
      // Preview полностью вне этой недели - проверяем попадает ли неделя внутрь
      const weekStart = weekDays[0];
      const weekEnd = weekDays[6];
      if (preview.startDate <= weekEnd && preview.endDate >= weekStart) {
        displayStartCol = preview.startDate > weekStart ? weekDays.findIndex(d => isSameDay(d, preview.startDate)) : 0;
        displayEndCol = preview.endDate < weekEnd ? weekDays.findIndex(d => isSameDay(d, preview.endDate)) : 6;
        if (displayStartCol === -1) displayStartCol = 0;
        if (displayEndCol === -1) displayEndCol = 6;
      } else {
        return null;
      }
    }
  }

  const span = displayEndCol - displayStartCol + 1;

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

  const handleDoubleClick = () => {
    onEventClick(event);
  };

  return (
    <div
      className={classes}
      style={style}
      onPointerDown={(e) => onPointerDown(event, e)}
      onDoubleClick={handleDoubleClick}
      title={event.title}
    >
      {timeLabel && <span className={styles.eventTime}>{timeLabel}</span>}
      <span className={styles.eventTitle}>{event.title}</span>

      {/* Resize handles - показываем только на реальных концах события */}
      {isSelected && !isDragging && (
        <>
          {/* Левый ползунок только если событие НЕ продолжается с предыдущей недели */}
          {!continuesFromPrev && (
            <div
              className={`${styles.resizeHandle} ${styles.resizeHandleStart}`}
              onPointerDown={(e) => onResizePointerDown(event, 'start', e)}
            />
          )}
          {/* Правый ползунок только если событие НЕ продолжается в следующую неделю */}
          {!continuesToNext && (
            <div
              className={`${styles.resizeHandle} ${styles.resizeHandleEnd}`}
              onPointerDown={(e) => onResizePointerDown(event, 'end', e)}
            />
          )}
        </>
      )}
    </div>
  );
}
