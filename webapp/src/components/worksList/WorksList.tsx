/**
 * WorksList - Список работ по месяцам
 * Показывается когда календарь свёрнут
 * Вертикальный скролл на 72 месяца (±3 года от текущей даты)
 */

import { useEffect, useRef, useMemo } from 'react';
import { MonthSection } from './MonthSection';
import styles from './WorksList.module.css';

interface MonthData {
  year: number;
  month: number;
  key: string;
}

/**
 * Генерирует массив месяцев в диапазоне ±3 года от текущей даты
 */
function generateMonthsRange(): MonthData[] {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth();

  const months: MonthData[] = [];

  // 3 года назад до 3 лет вперёд = 72 месяца
  for (let yearOffset = -3; yearOffset <= 3; yearOffset++) {
    for (let month = 0; month < 12; month++) {
      const year = currentYear + yearOffset;
      // Пропускаем месяцы до текущего, если это 3 года назад
      // и после текущего, если это 3 года вперёд
      if (yearOffset === -3 && month < currentMonth) continue;
      if (yearOffset === 3 && month > currentMonth) continue;

      months.push({
        year,
        month,
        key: `${year}-${month}`,
      });
    }
  }

  return months;
}

/**
 * Находит индекс текущего месяца в массиве
 */
function findCurrentMonthIndex(months: MonthData[]): number {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth();

  return months.findIndex(
    (m) => m.year === currentYear && m.month === currentMonth
  );
}

export function WorksList() {
  const containerRef = useRef<HTMLDivElement>(null);
  const hasScrolledRef = useRef(false);

  // Генерируем массив месяцев один раз
  const months = useMemo(() => generateMonthsRange(), []);
  const currentMonthIndex = useMemo(() => findCurrentMonthIndex(months), [months]);

  // Скролл к текущему месяцу при первом рендере
  useEffect(() => {
    if (hasScrolledRef.current || !containerRef.current) return;

    const container = containerRef.current;
    const monthSections = container.querySelectorAll('[data-month-section]');

    if (monthSections[currentMonthIndex]) {
      // Небольшая задержка для завершения рендера
      requestAnimationFrame(() => {
        monthSections[currentMonthIndex].scrollIntoView({
          behavior: 'instant',
          block: 'start',
        });
        hasScrolledRef.current = true;
      });
    }
  }, [currentMonthIndex]);

  return (
    <div
      ref={containerRef}
      className={styles.container}
    >
      <div className={styles.list}>
        {months.map((monthData) => (
          <div key={monthData.key} data-month-section>
            <MonthSection year={monthData.year} month={monthData.month} />
          </div>
        ))}
      </div>
    </div>
  );
}
