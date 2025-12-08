/**
 * MonthSection - Секция одного месяца в списке работ
 * Показывает картинку месяца с бейджем типа работы и список событий
 */

import { useMemo } from 'react';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { parseLocalDateTime } from '@utils/dateUtils';
import { useEventsStore } from '@store/eventsStore';
import { useCalendarStore } from '@store/calendarStore';
import { useUIStore } from '@store/uiStore';
import { EventRow } from './EventRow';
import type { CalendarEvent, EventType } from '@/types';
import styles from './MonthSection.module.css';

// Импорт картинок месяцев
import januaryImg from '@/assets/images/months/january.svg';
import februaryImg from '@/assets/images/months/february.svg';
import marchImg from '@/assets/images/months/march.svg';
import aprilImg from '@/assets/images/months/april.svg';
import mayImg from '@/assets/images/months/may.svg';
import juneImg from '@/assets/images/months/june.svg';
import julyImg from '@/assets/images/months/july.svg';
import augustImg from '@/assets/images/months/august.svg';
import septemberImg from '@/assets/images/months/september.svg';
import octoberImg from '@/assets/images/months/october.svg';
import novemberImg from '@/assets/images/months/november.svg';
import decemberImg from '@/assets/images/months/december.svg';

// Импорт картинок типов работ
import plantingImg from '@/assets/images/workTypes/planting.svg';
import nutritionImg from '@/assets/images/workTypes/nutrition.svg';
import protectionImg from '@/assets/images/workTypes/protection.svg';
import harvestImg from '@/assets/images/workTypes/harvest.svg';
import soilImg from '@/assets/images/workTypes/soil.svg';
import otherImg from '@/assets/images/workTypes/other.svg';

const MONTH_IMAGES: Record<number, string> = {
  0: januaryImg,
  1: februaryImg,
  2: marchImg,
  3: aprilImg,
  4: mayImg,
  5: juneImg,
  6: julyImg,
  7: augustImg,
  8: septemberImg,
  9: octoberImg,
  10: novemberImg,
  11: decemberImg,
};

const WORK_TYPE_IMAGES: Record<EventType, string> = {
  planting: plantingImg,
  nutrition: nutritionImg,
  protection: protectionImg,
  harvest: harvestImg,
  soil: soilImg,
  other: otherImg,
};

interface MonthSectionProps {
  year: number;
  month: number; // 0-11
}

/**
 * Получить события для конкретного месяца
 */
function getEventsForMonth(
  events: CalendarEvent[],
  year: number,
  month: number
): CalendarEvent[] {
  return events.filter((event) => {
    const eventDate = parseLocalDateTime(event.startDateTime);
    return eventDate.getFullYear() === year && eventDate.getMonth() === month;
  }).sort((a, b) => a.startDateTime.localeCompare(b.startDateTime));
}

/**
 * Получить тип ближайшей работы в месяце
 */
function getNearestWorkType(events: CalendarEvent[]): EventType | null {
  if (events.length === 0) return null;

  const now = new Date();
  let nearestEvent: CalendarEvent | null = null;
  let minDiff = Infinity;

  for (const event of events) {
    const eventDate = parseLocalDateTime(event.startDateTime);
    const diff = Math.abs(eventDate.getTime() - now.getTime());
    if (diff < minDiff) {
      minDiff = diff;
      nearestEvent = event;
    }
  }

  return nearestEvent?.type || null;
}

export function MonthSection({ year, month }: MonthSectionProps) {
  // Получаем events объект напрямую (стабильная ссылка)
  const eventsRecord = useEventsStore((state) => state.events);
  const setCurrentDate = useCalendarStore((state) => state.setCurrentDate);
  const expandCalendar = useUIStore((state) => state.expandCalendar);
  const selectEvent = useUIStore((state) => state.selectEvent);

  // События этого месяца - преобразуем в массив внутри useMemo
  const monthEvents = useMemo(
    () => getEventsForMonth(Object.values(eventsRecord), year, month),
    [eventsRecord, year, month]
  );

  // Тип ближайшей работы для бейджа
  const nearestWorkType = useMemo(
    () => getNearestWorkType(monthEvents),
    [monthEvents]
  );

  // Форматирование даты для отображения
  const monthDate = new Date(year, month, 1);
  const monthLabel = format(monthDate, 'LLL yyyy г.', { locale: ru });

  // Картинка месяца
  const monthImage = MONTH_IMAGES[month];

  // Картинка типа работы (если есть события)
  const workTypeImage = nearestWorkType ? WORK_TYPE_IMAGES[nearestWorkType] : null;

  // Обработчик клика по событию
  const handleEventClick = (event: CalendarEvent) => {
    const eventDate = parseLocalDateTime(event.startDateTime);
    setCurrentDate(eventDate);
    selectEvent(event.id);
    expandCalendar();
  };

  // Обработчик клика по карточке месяца
  const handleMonthClick = () => {
    setCurrentDate(monthDate);
    expandCalendar();
  };

  return (
    <section className={styles.section}>
      {/* Картинка месяца */}
      <div
        className={styles.imageContainer}
        onClick={handleMonthClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && handleMonthClick()}
      >
        <img
          src={monthImage}
          alt={monthLabel}
          className={styles.monthImage}
          loading="lazy"
        />

        {/* Дата слева вверху */}
        <span className={styles.monthLabel}>{monthLabel}</span>

        {/* Бейдж типа работы справа внизу */}
        {workTypeImage && (
          <div className={styles.workTypeBadge}>
            <img
              src={workTypeImage}
              alt=""
              className={styles.workTypeImage}
            />
          </div>
        )}
      </div>

      {/* Список событий */}
      <div className={styles.eventsList}>
        {monthEvents.length > 0 ? (
          monthEvents.map((event) => (
            <EventRow
              key={event.id}
              event={event}
              onClick={() => handleEventClick(event)}
            />
          ))
        ) : (
          <p className={styles.emptyMessage}>Событий в этом месяце нет</p>
        )}
      </div>
    </section>
  );
}
