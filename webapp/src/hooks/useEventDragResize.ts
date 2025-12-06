/**
 * useEventDragResize - Хук для drag и resize событий в календаре
 *
 * Логика:
 * - Клик без движения: выделяет событие (показывает handles)
 * - Клик + движение: начинает drag
 * - Клик на handle: начинает resize
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

// pending = ждём движения, drag/resize = активное перетаскивание
type InteractionMode = 'none' | 'pending' | 'drag' | 'resize-start' | 'resize-end';

const DRAG_THRESHOLD = 3; // Минимальное смещение для начала drag (px)

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

  // State для UI (isDragging = визуальный режим перетаскивания)
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState<'start' | 'end' | null>(null);
  const [previewStartCol, setPreviewStartCol] = useState(startCol);
  const [previewEndCol, setPreviewEndCol] = useState(endCol);

  // Refs для отслеживания состояния
  const modeRef = useRef<InteractionMode>('none');
  const initialX = useRef(0);
  const initialStartCol = useRef(startCol);
  const initialEndCol = useRef(endCol);
  const colWidth = useRef(0);
  const currentPreviewStart = useRef(startCol);
  const currentPreviewEnd = useRef(endCol);

  // Синхронизация refs с state
  useEffect(() => {
    currentPreviewStart.current = previewStartCol;
  }, [previewStartCol]);

  useEffect(() => {
    currentPreviewEnd.current = previewEndCol;
  }, [previewEndCol]);

  // Синхронизация при изменении props
  useEffect(() => {
    if (modeRef.current === 'none') {
      setPreviewStartCol(startCol);
      setPreviewEndCol(endCol);
      currentPreviewStart.current = startCol;
      currentPreviewEnd.current = endCol;
    }
  }, [startCol, endCol]);

  // Вычисление ширины колонки
  const getColWidth = useCallback(() => {
    if (containerRef.current) {
      return containerRef.current.offsetWidth / 7;
    }
    return 50;
  }, [containerRef]);

  // Конвертация колонки в дату
  const colToDate = useCallback((col: number): Date => {
    const clampedCol = Math.max(0, Math.min(6, col));
    return weekDays[clampedCol];
  }, [weekDays]);

  // Сохранение изменений в store
  const saveChanges = useCallback((newStartCol: number, newEndCol: number) => {
    if (newStartCol === startCol && newEndCol === endCol) {
      return;
    }

    const newStartDate = colToDate(newStartCol);
    const newEndDate = colToDate(newEndCol);

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
  }, [event, startCol, endCol, colToDate, updateEvent, medium]);

  // Refs для handlers
  const handlersRef = useRef({
    onMove: (_e: PointerEvent) => {},
    onUp: () => {},
  });

  // Обработчик движения
  handlersRef.current.onMove = (e: PointerEvent) => {
    const deltaX = e.clientX - initialX.current;
    const mode = modeRef.current;

    // Если pending, проверяем threshold для начала drag
    if (mode === 'pending') {
      if (Math.abs(deltaX) >= DRAG_THRESHOLD) {
        modeRef.current = 'drag';
        setIsDragging(true);
      } else {
        return;
      }
    }

    const deltaCols = Math.round(deltaX / colWidth.current);

    if (modeRef.current === 'drag') {
      const eventSpan = initialEndCol.current - initialStartCol.current;
      let newStart = initialStartCol.current + deltaCols;
      let newEnd = newStart + eventSpan;

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
      let newStart = initialStartCol.current + deltaCols;
      newStart = Math.max(0, Math.min(newStart, initialEndCol.current));
      setPreviewStartCol(newStart);
    } else if (mode === 'resize-end') {
      let newEnd = initialEndCol.current + deltaCols;
      newEnd = Math.max(initialStartCol.current, Math.min(6, newEnd));
      setPreviewEndCol(newEnd);
    }
  };

  // Обработчик отпускания
  handlersRef.current.onUp = () => {
    const mode = modeRef.current;

    document.removeEventListener('pointermove', globalMoveHandler);
    document.removeEventListener('pointerup', globalUpHandler);
    document.removeEventListener('pointercancel', globalUpHandler);

    // Сохраняем изменения только если был реальный drag/resize
    if (mode === 'drag' || mode === 'resize-start' || mode === 'resize-end') {
      saveChanges(currentPreviewStart.current, currentPreviewEnd.current);
    }
    // При pending (клик без движения) — событие уже выделено, ничего не делаем

    modeRef.current = 'none';
    setIsDragging(false);
    setIsResizing(null);
  };

  const globalMoveHandler = useCallback((e: PointerEvent) => {
    handlersRef.current.onMove(e);
  }, []);

  const globalUpHandler = useCallback(() => {
    handlersRef.current.onUp();
  }, []);

  // Клик на событие — выделяем и готовимся к drag
  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.stopPropagation();
    e.preventDefault(); // Предотвращает выделение текста на iOS

    // Выделяем событие сразу
    selectEvent(event.id);
    light();

    // Инициализация для возможного drag
    initialX.current = e.clientX;
    initialStartCol.current = startCol;
    initialEndCol.current = endCol;
    colWidth.current = getColWidth();
    modeRef.current = 'pending'; // Ждём движения

    setPreviewStartCol(startCol);
    setPreviewEndCol(endCol);

    document.addEventListener('pointermove', globalMoveHandler);
    document.addEventListener('pointerup', globalUpHandler);
    document.addEventListener('pointercancel', globalUpHandler);
  }, [event.id, startCol, endCol, getColWidth, selectEvent, light, globalMoveHandler, globalUpHandler]);

  // Клик на resize handle
  const handleResizePointerDown = useCallback((edge: 'start' | 'end', e: React.PointerEvent) => {
    e.stopPropagation();
    e.preventDefault();

    light();

    initialX.current = e.clientX;
    initialStartCol.current = startCol;
    initialEndCol.current = endCol;
    colWidth.current = getColWidth();
    modeRef.current = edge === 'start' ? 'resize-start' : 'resize-end';

    setIsResizing(edge);
    setPreviewStartCol(startCol);
    setPreviewEndCol(endCol);

    document.addEventListener('pointermove', globalMoveHandler);
    document.addEventListener('pointerup', globalUpHandler);
    document.addEventListener('pointercancel', globalUpHandler);
  }, [startCol, endCol, getColWidth, light, globalMoveHandler, globalUpHandler]);

  // Cleanup
  useEffect(() => {
    return () => {
      document.removeEventListener('pointermove', globalMoveHandler);
      document.removeEventListener('pointerup', globalUpHandler);
      document.removeEventListener('pointercancel', globalUpHandler);
    };
  }, [globalMoveHandler, globalUpHandler]);

  return {
    isDragging,
    isResizing,
    previewStartCol,
    previewEndCol,
    handlePointerDown,
    handleResizePointerDown,
  };
}
