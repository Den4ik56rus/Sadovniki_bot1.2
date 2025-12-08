/**
 * MonthScroller - Горизонтальное колёсико выбора месяца (iOS-style)
 * Snap-scroll с фиксацией на ближайшем месяце при отпускании
 */

import { useRef, useMemo, useEffect, useCallback, useState } from 'react';
import { addMonths, format, isSameMonth } from 'date-fns';
import { ru } from 'date-fns/locale';
import { useCalendarStore } from '@store/calendarStore';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import styles from './MonthScroller.module.css';

const MONTHS_RANGE = 36; // ±3 года
const ITEM_WIDTH = 120; // Ширина элемента в px (для 3 видимых месяцев)

export function MonthScroller() {
  const { currentDate, setCurrentDate } = useCalendarStore();
  const { light } = useTelegramHaptic();
  const scrollerRef = useRef<HTMLDivElement>(null);
  const isScrollingRef = useRef(false);
  const scrollTimeoutRef = useRef<number | null>(null);
  const [activeIndex, setActiveIndex] = useState(MONTHS_RANGE);

  // Генерация массива месяцев (±3 года)
  const months = useMemo(() => {
    const result: Date[] = [];
    const baseDate = new Date();
    for (let i = -MONTHS_RANGE; i <= MONTHS_RANGE; i++) {
      result.push(addMonths(baseDate, i));
    }
    return result;
  }, []);

  // Форматирование месяца: "Дек 2024"
  const formatMonth = (date: Date) => {
    const monthName = format(date, 'LLL', { locale: ru });
    const year = format(date, 'yyyy');
    return `${monthName.charAt(0).toUpperCase() + monthName.slice(1)} ${year}`;
  };

  // Найти индекс текущего месяца
  const findMonthIndex = useCallback((date: Date) => {
    return months.findIndex(m => isSameMonth(m, date));
  }, [months]);

  // Скролл к определённому месяцу
  const scrollToMonth = useCallback((date: Date, smooth = true) => {
    const scroller = scrollerRef.current;
    if (!scroller) return;

    const index = findMonthIndex(date);
    if (index === -1) return;

    const scrollLeft = index * ITEM_WIDTH;
    scroller.scrollTo({
      left: scrollLeft,
      behavior: smooth ? 'smooth' : 'auto',
    });
  }, [findMonthIndex]);

  // При монтировании и изменении currentDate — скролл к текущему месяцу
  useEffect(() => {
    // Не скроллим если пользователь сам крутит
    if (isScrollingRef.current) return;

    const index = findMonthIndex(currentDate);
    if (index !== -1 && index !== activeIndex) {
      setActiveIndex(index);
      scrollToMonth(currentDate, true);
    }
  }, [currentDate, findMonthIndex, scrollToMonth, activeIndex]);

  // Инициализация: скролл к текущему месяцу без анимации
  useEffect(() => {
    const index = findMonthIndex(currentDate);
    if (index !== -1) {
      setActiveIndex(index);
      // Небольшая задержка для корректного рендера
      requestAnimationFrame(() => {
        scrollToMonth(currentDate, false);
      });
    }
  }, []);

  // Обработка скролла
  const handleScroll = useCallback(() => {
    const scroller = scrollerRef.current;
    if (!scroller) return;

    isScrollingRef.current = true;

    // Очищаем предыдущий таймаут
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }

    // Определяем центральный элемент
    const scrollLeft = scroller.scrollLeft;
    const centerIndex = Math.round(scrollLeft / ITEM_WIDTH);

    if (centerIndex >= 0 && centerIndex < months.length && centerIndex !== activeIndex) {
      setActiveIndex(centerIndex);
    }

    // Debounce: когда скролл остановился — обновляем store
    scrollTimeoutRef.current = window.setTimeout(() => {
      isScrollingRef.current = false;

      const finalIndex = Math.round(scroller.scrollLeft / ITEM_WIDTH);
      if (finalIndex >= 0 && finalIndex < months.length) {
        const selectedMonth = months[finalIndex];

        // Обновляем только если месяц изменился
        if (!isSameMonth(selectedMonth, currentDate)) {
          light();
          setCurrentDate(selectedMonth);
        }
      }
    }, 150);
  }, [months, activeIndex, currentDate, light, setCurrentDate]);

  // Клик по месяцу
  const handleMonthClick = (date: Date, index: number) => {
    if (index === activeIndex) return;

    light();
    setActiveIndex(index);
    scrollToMonth(date, true);

    // Обновляем store после анимации
    setTimeout(() => {
      if (!isSameMonth(date, currentDate)) {
        setCurrentDate(date);
      }
    }, 200);
  };

  return (
    <div className={styles.container}>
      <div
        ref={scrollerRef}
        className={styles.scroller}
        onScroll={handleScroll}
      >
        {months.map((date, index) => (
          <div
            key={date.toISOString()}
            className={`${styles.monthItem} ${index === activeIndex ? styles.active : ''}`}
            onClick={() => handleMonthClick(date, index)}
          >
            {formatMonth(date)}
          </div>
        ))}
      </div>
    </div>
  );
}
