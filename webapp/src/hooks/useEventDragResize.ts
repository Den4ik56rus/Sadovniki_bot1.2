/**
 * useEventDragResize - Хук для drag и resize событий в календаре
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { format } from 'date-fns';
import { parseLocalDateTime } from '@utils/dateUtils';
import { useEventsStore } from '@store/eventsStore';
import { useUIStore } from '@store/uiStore';
import { useTelegramHaptic } from './useTelegramHaptic';
import type { CalendarEvent } from '@/types/event';

interface UseEventDragResizeOptions {
  event: CalendarEvent;
  startCol: number;
  endCol: number;
  weekDays: Date[];
  containerRef: React.RefObject<HTMLElement | null>;
}

interface UseEventDragResizeReturn {
  isDragging: boolean;
  isResizing: 'start' | 'end' | null;
  previewStartCol: number;
  previewEndCol: number;
  handlePointerDown: (e: React.PointerEvent) => void;
  handleResizePointerDown: (edge: 'start' | 'end', e: React.PointerEvent) => void;
}

type InteractionMode = 'none' | 'drag' | 'resize-start' | 'resize-end';

export function useEventDragResize({
  event,
  startCol,
  endCol,
  weekDays,
  containerRef,
}: UseEventDragResizeOptions): UseEventDragResizeReturn {
  const updateEvent = useEventsStore((state) => state.updateEvent);
  const selectEvent = useUIStore((state) => state.selectEvent);
  const { light, medium } = useTelegramHaptic();

  // State для UI
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState<'start' | 'end' | null>(null);
  const [previewStartCol, setPreviewStartCol] = useState(startCol);
  const [previewEndCol, setPreviewEndCol] = useState(endCol);

  // Refs для отслеживания состояния (не вызывают ререндер)
  const modeRef = useRef<InteractionMode>('none');
  const initialX = useRef(0);
  const initialStartCol = useRef(startCol);
  const initialEndCol = useRef(endCol);
  const colWidth = useRef(0);
  const hasMoved = useRef(false);

  // Синхронизация при изменении props
  useEffect(() => {
    if (modeRef.current === 'none') {
      setPreviewStartCol(startCol);
      setPreviewEndCol(endCol);
    }
  }, [startCol, endCol]);

  // Вычисление ширины колонки
  const getColWidth = useCallback(() => {
    if (containerRef.current) {
      return containerRef.current.offsetWidth / 7;
    }
    return 50; // fallback
  }, [containerRef]);

  // Конвертация колонки в дату
  const colToDate = useCallback((col: number): Date => {
    const clampedCol = Math.max(0, Math.min(6, col));
    return weekDays[clampedCol];
  }, [weekDays]);

  // Сохранение изменений в store
  const saveChanges = useCallback((newStartCol: number, newEndCol: number) => {
    const newStartDate = colToDate(newStartCol);
    const newEndDate = colToDate(newEndCol);

    // Извлекаем время из оригинального события
    const originalStart = parseLocalDateTime(event.startDateTime);
    const originalEnd = event.endDateTime ? parseLocalDateTime(event.endDateTime) : null;

    const startTime = event.allDay ? '00:00:00' : format(originalStart, 'HH:mm:ss');
    const endTime = originalEnd
      ? (event.allDay ? '23:59:59' : format(originalEnd, 'HH:mm:ss'))
      : '23:59:59';

    const newStartDateTime = `${format(newStartDate, 'yyyy-MM-dd')}T${startTime}`;
    const newEndDateTime = newStartCol === newEndCol && !event.endDateTime
      ? null
      : `${format(newEndDate, 'yyyy-MM-dd')}T${endTime}`;

    updateEvent(event.id, {
      startDateTime: newStartDateTime,
      endDateTime: newEndDateTime,
    });

    medium();
  }, [event, colToDate, updateEvent, medium]);

  // Обработчик движения указателя
  const handlePointerMove = useCallback((e: PointerEvent) => {
    const deltaX = e.clientX - initialX.current;
    const deltaCols = Math.round(deltaX / colWidth.current);

    // Отмечаем что было движение
    if (Math.abs(deltaX) > 5) {
      hasMoved.current = true;
    }

    const mode = modeRef.current;

    if (mode === 'drag') {
      // Drag: двигаем обе границы
      const eventSpan = initialEndCol.current - initialStartCol.current;
      let newStart = initialStartCol.current + deltaCols;
      let newEnd = newStart + eventSpan;

      // Ограничиваем пределами недели
      if (newStart < 0) {
        newStart = 0;
        newEnd = eventSpan;
      }
      if (newEnd > 6) {
        newEnd = 6;
        newStart = 6 - eventSpan;
      }

      setPreviewStartCol(newStart);
      setPreviewEndCol(newEnd);
    } else if (mode === 'resize-start') {
      // Resize start: двигаем левую границу
      let newStart = initialStartCol.current + deltaCols;
      newStart = Math.max(0, Math.min(newStart, initialEndCol.current));
      setPreviewStartCol(newStart);
    } else if (mode === 'resize-end') {
      // Resize end: двигаем правую границу
      let newEnd = initialEndCol.current + deltaCols;
      newEnd = Math.max(initialStartCol.current, Math.min(6, newEnd));
      setPreviewEndCol(newEnd);
    }
  }, []);

  // Обработчик отпускания указателя
  const handlePointerUp = useCallback(() => {
    const mode = modeRef.current;

    // Убираем слушатели
    document.removeEventListener('pointermove', handlePointerMove);
    document.removeEventListener('pointerup', handlePointerUp);

    if (mode !== 'none' && hasMoved.current) {
      // Получаем текущие preview значения
      setPreviewStartCol((prevStart) => {
        setPreviewEndCol((prevEnd) => {
          // Сохраняем изменения если позиция изменилась
          if (prevStart !== startCol || prevEnd !== endCol) {
            saveChanges(prevStart, prevEnd);
          }
          return prevEnd;
        });
        return prevStart;
      });
    }

    // Сбрасываем состояние
    modeRef.current = 'none';
    hasMoved.current = false;
    setIsDragging(false);
    setIsResizing(null);
  }, [startCol, endCol, saveChanges, handlePointerMove]);

  // Начало drag
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.stopPropagation();

    // Выделяем событие
    selectEvent(event.id);
    light();

    // Инициализация
    initialX.current = e.clientX;
    initialStartCol.current = startCol;
    initialEndCol.current = endCol;
    colWidth.current = getColWidth();
    hasMoved.current = false;
    modeRef.current = 'drag';

    setIsDragging(true);
    setPreviewStartCol(startCol);
    setPreviewEndCol(endCol);

    // Добавляем слушатели на document
    document.addEventListener('pointermove', handlePointerMove);
    document.addEventListener('pointerup', handlePointerUp);
  }, [event.id, startCol, endCol, getColWidth, selectEvent, light, handlePointerMove, handlePointerUp]);

  // Начало resize
  const handleResizePointerDown = useCallback((edge: 'start' | 'end', e: React.PointerEvent) => {
    e.stopPropagation();
    e.preventDefault();

    light();

    initialX.current = e.clientX;
    initialStartCol.current = startCol;
    initialEndCol.current = endCol;
    colWidth.current = getColWidth();
    hasMoved.current = false;
    modeRef.current = edge === 'start' ? 'resize-start' : 'resize-end';

    setIsResizing(edge);
    setPreviewStartCol(startCol);
    setPreviewEndCol(endCol);

    document.addEventListener('pointermove', handlePointerMove);
    document.addEventListener('pointerup', handlePointerUp);
  }, [startCol, endCol, getColWidth, light, handlePointerMove, handlePointerUp]);

  // Cleanup при размонтировании
  useEffect(() => {
    return () => {
      document.removeEventListener('pointermove', handlePointerMove);
      document.removeEventListener('pointerup', handlePointerUp);
    };
  }, [handlePointerMove, handlePointerUp]);

  return {
    isDragging,
    isResizing,
    previewStartCol,
    previewEndCol,
    handlePointerDown,
    handleResizePointerDown,
  };
}
