/**
 * useCalendarDrag - Хук для drag событий по всему календарю (включая между неделями)
 *
 * Логика:
 * - Клик без движения: выделяет событие
 * - Клик + движение: drag по всей сетке (X = день недели, Y = неделя)
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { format, addDays, differenceInDays } from 'date-fns';
import { parseLocalDateTime } from '@utils/dateUtils';
import { useEventsStore } from '@store/eventsStore';
import { useUIStore } from '@store/uiStore';
import { useTelegramHaptic } from './useTelegramHaptic';
import type { CalendarEvent } from '@/types/event';

interface DragState {
  eventId: string | null;
  isDragging: boolean;
  isResizing: 'start' | 'end' | null;
  // Preview дата (для визуального отображения)
  previewStartDate: Date | null;
  previewEndDate: Date | null;
}

interface UseCalendarDragOptions {
  gridRef: React.RefObject<HTMLElement | null>;
  allDays: Date[]; // Все дни календаря (flat array из weeks)
}

interface UseCalendarDragReturn {
  dragState: DragState;
  // Обработчики для EventBar
  handleEventPointerDown: (event: CalendarEvent, e: React.PointerEvent) => void;
  handleResizePointerDown: (event: CalendarEvent, edge: 'start' | 'end', e: React.PointerEvent) => void;
  // Получить preview позицию для события
  getEventPreview: (eventId: string) => { startDate: Date; endDate: Date } | null;
}

type InteractionMode = 'none' | 'pending' | 'drag' | 'resize-start' | 'resize-end';

const DRAG_THRESHOLD = 3;

export function useCalendarDrag({
  gridRef,
  allDays,
}: UseCalendarDragOptions): UseCalendarDragReturn {
  const updateEvent = useEventsStore((state) => state.updateEvent);
  const selectEvent = useUIStore((state) => state.selectEvent);
  const { light, medium } = useTelegramHaptic();

  const [dragState, setDragState] = useState<DragState>({
    eventId: null,
    isDragging: false,
    isResizing: null,
    previewStartDate: null,
    previewEndDate: null,
  });

  // Refs
  const modeRef = useRef<InteractionMode>('none');
  const initialPointer = useRef({ x: 0, y: 0 });
  const initialEvent = useRef<CalendarEvent | null>(null);
  const cellSize = useRef({ width: 0, height: 0 });
  const gridRect = useRef<DOMRect | null>(null);
  // Refs для preview (чтобы иметь актуальные значения в onUp)
  const previewRef = useRef<{ startDate: Date | null; endDate: Date | null }>({
    startDate: null,
    endDate: null,
  });

  // Вычислить размеры ячейки
  const updateCellSize = useCallback(() => {
    if (gridRef.current) {
      const rect = gridRef.current.getBoundingClientRect();
      gridRect.current = rect;
      // 7 колонок, N рядов (allDays.length / 7)
      const rows = Math.ceil(allDays.length / 7);
      cellSize.current = {
        width: rect.width / 7,
        height: rect.height / rows,
      };
    }
  }, [gridRef, allDays.length]);

  // Конвертировать координаты в индекс дня
  const pointerToDay = useCallback((clientX: number, clientY: number): Date | null => {
    if (!gridRect.current || cellSize.current.width === 0) return null;

    const x = clientX - gridRect.current.left;
    const y = clientY - gridRect.current.top;

    const col = Math.floor(x / cellSize.current.width);
    const row = Math.floor(y / cellSize.current.height);

    const clampedCol = Math.max(0, Math.min(6, col));
    const clampedRow = Math.max(0, Math.min(Math.ceil(allDays.length / 7) - 1, row));

    const dayIndex = clampedRow * 7 + clampedCol;
    return allDays[dayIndex] || null;
  }, [allDays]);

  // Сохранить изменения
  const saveChanges = useCallback((newStartDate: Date, newEndDate: Date | null) => {
    const event = initialEvent.current;
    if (!event) return;

    const originalStart = parseLocalDateTime(event.startDateTime);
    const originalEnd = event.endDateTime ? parseLocalDateTime(event.endDateTime) : null;

    const startTime = event.allDay ? '00:00:00' : format(originalStart, 'HH:mm:ss');
    const endTime = originalEnd
      ? (event.allDay ? '23:59:59' : format(originalEnd, 'HH:mm:ss'))
      : '23:59:59';

    const newStartDateTime = `${format(newStartDate, 'yyyy-MM-dd')}T${startTime}`;
    const newEndDateTime = newEndDate
      ? `${format(newEndDate, 'yyyy-MM-dd')}T${endTime}`
      : null;

    // Проверяем что что-то изменилось
    if (newStartDateTime !== event.startDateTime || newEndDateTime !== event.endDateTime) {
      updateEvent(event.id, {
        startDateTime: newStartDateTime,
        endDateTime: newEndDateTime,
      });
      medium();
    }
  }, [updateEvent, medium]);

  // Refs для handlers
  const handlersRef = useRef({
    onMove: (_e: PointerEvent) => {},
    onUp: () => {},
  });

  // Обработчик движения
  handlersRef.current.onMove = (e: PointerEvent) => {
    const event = initialEvent.current;
    if (!event) return;

    const deltaX = e.clientX - initialPointer.current.x;
    const deltaY = e.clientY - initialPointer.current.y;
    const mode = modeRef.current;

    // Проверяем threshold для начала drag
    if (mode === 'pending') {
      if (Math.abs(deltaX) >= DRAG_THRESHOLD || Math.abs(deltaY) >= DRAG_THRESHOLD) {
        modeRef.current = 'drag';
        setDragState(prev => ({ ...prev, isDragging: true }));
      } else {
        return;
      }
    }

    const currentDay = pointerToDay(e.clientX, e.clientY);
    if (!currentDay) return;

    const originalStart = parseLocalDateTime(event.startDateTime);
    const originalEnd = event.endDateTime ? parseLocalDateTime(event.endDateTime) : originalStart;
    const eventDuration = differenceInDays(originalEnd, originalStart);

    if (modeRef.current === 'drag') {
      // Drag: перемещаем всё событие
      const newStart = currentDay;
      const newEnd = eventDuration > 0 ? addDays(currentDay, eventDuration) : null;

      previewRef.current = { startDate: newStart, endDate: newEnd };
      setDragState(prev => ({
        ...prev,
        previewStartDate: newStart,
        previewEndDate: newEnd,
      }));
    } else if (mode === 'resize-start') {
      // Resize start: меняем начало, конец фиксирован
      const newStart = currentDay;
      // Не даём начало быть после конца
      if (newStart <= originalEnd) {
        previewRef.current = { startDate: newStart, endDate: originalEnd };
        setDragState(prev => ({
          ...prev,
          previewStartDate: newStart,
          previewEndDate: originalEnd,
        }));
      }
    } else if (mode === 'resize-end') {
      // Resize end: меняем конец, начало фиксировано
      const newEnd = currentDay;
      // Не даём конец быть до начала
      if (newEnd >= originalStart) {
        previewRef.current = { startDate: originalStart, endDate: newEnd };
        setDragState(prev => ({
          ...prev,
          previewStartDate: originalStart,
          previewEndDate: newEnd,
        }));
      }
    }
  };

  // Обработчик отпускания
  handlersRef.current.onUp = () => {
    const mode = modeRef.current;

    document.removeEventListener('pointermove', globalMoveHandler);
    document.removeEventListener('pointerup', globalUpHandler);
    document.removeEventListener('pointercancel', globalUpHandler);

    // Сохраняем если был drag/resize (используем ref для актуальных значений)
    if (mode === 'drag' || mode === 'resize-start' || mode === 'resize-end') {
      if (previewRef.current.startDate) {
        saveChanges(previewRef.current.startDate, previewRef.current.endDate);
      }
    }

    // Сбрасываем состояние
    modeRef.current = 'none';
    initialEvent.current = null;
    previewRef.current = { startDate: null, endDate: null };
    setDragState({
      eventId: null,
      isDragging: false,
      isResizing: null,
      previewStartDate: null,
      previewEndDate: null,
    });
  };

  const globalMoveHandler = useCallback((e: PointerEvent) => {
    handlersRef.current.onMove(e);
  }, []);

  const globalUpHandler = useCallback(() => {
    handlersRef.current.onUp();
  }, []);

  // Обработчик pointerdown на событии
  const handleEventPointerDown = useCallback((event: CalendarEvent, e: React.PointerEvent) => {
    e.stopPropagation();
    e.preventDefault();

    selectEvent(event.id);
    light();

    updateCellSize();
    initialPointer.current = { x: e.clientX, y: e.clientY };
    initialEvent.current = event;
    modeRef.current = 'pending';

    const originalStart = parseLocalDateTime(event.startDateTime);
    const originalEnd = event.endDateTime ? parseLocalDateTime(event.endDateTime) : null;

    setDragState({
      eventId: event.id,
      isDragging: false,
      isResizing: null,
      previewStartDate: originalStart,
      previewEndDate: originalEnd,
    });

    document.addEventListener('pointermove', globalMoveHandler);
    document.addEventListener('pointerup', globalUpHandler);
    document.addEventListener('pointercancel', globalUpHandler);
  }, [selectEvent, light, updateCellSize, globalMoveHandler, globalUpHandler]);

  // Обработчик resize
  const handleResizePointerDown = useCallback((event: CalendarEvent, edge: 'start' | 'end', e: React.PointerEvent) => {
    e.stopPropagation();
    e.preventDefault();

    light();

    updateCellSize();
    initialPointer.current = { x: e.clientX, y: e.clientY };
    initialEvent.current = event;
    modeRef.current = edge === 'start' ? 'resize-start' : 'resize-end';

    const originalStart = parseLocalDateTime(event.startDateTime);
    const originalEnd = event.endDateTime ? parseLocalDateTime(event.endDateTime) : originalStart;

    setDragState({
      eventId: event.id,
      isDragging: false,
      isResizing: edge,
      previewStartDate: originalStart,
      previewEndDate: originalEnd,
    });

    document.addEventListener('pointermove', globalMoveHandler);
    document.addEventListener('pointerup', globalUpHandler);
    document.addEventListener('pointercancel', globalUpHandler);
  }, [light, updateCellSize, globalMoveHandler, globalUpHandler]);

  // Получить preview для конкретного события
  const getEventPreview = useCallback((eventId: string) => {
    if (dragState.eventId === eventId && dragState.previewStartDate) {
      return {
        startDate: dragState.previewStartDate,
        endDate: dragState.previewEndDate || dragState.previewStartDate,
      };
    }
    return null;
  }, [dragState]);

  // Cleanup
  useEffect(() => {
    return () => {
      document.removeEventListener('pointermove', globalMoveHandler);
      document.removeEventListener('pointerup', globalUpHandler);
      document.removeEventListener('pointercancel', globalUpHandler);
    };
  }, [globalMoveHandler, globalUpHandler]);

  return {
    dragState,
    handleEventPointerDown,
    handleResizePointerDown,
    getEventPreview,
  };
}
