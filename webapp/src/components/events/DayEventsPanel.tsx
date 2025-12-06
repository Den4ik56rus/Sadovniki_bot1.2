/**
 * DayEventsPanel - Панель событий выбранного дня
 * Отображает список событий и кнопку добавления
 */

import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { formatDateForInput } from '@utils/dateUtils';
import { useCalendarStore } from '@store/calendarStore';
import { useEventsStore } from '@store/eventsStore';
import { useUIStore } from '@store/uiStore';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { UI_TEXT } from '@constants/ui';
import { EventCard } from './EventCard';
import styles from './DayEventsPanel.module.css';

export function DayEventsPanel() {
  const selectedDate = useCalendarStore((state) => state.selectedDate);
  const events = useEventsStore((state) => state.events);
  const { openEventForm, openEventDetails } = useUIStore();
  const { light, medium } = useTelegramHaptic();

  // Получаем события для выбранной даты
  const dayEvents = selectedDate
    ? Object.values(events)
        .filter((event) => {
          const eventDate = event.startDateTime.slice(0, 10);
          const selectedStr = formatDateForInput(selectedDate); // yyyy-MM-dd в локальном времени
          return eventDate === selectedStr;
        })
        .sort((a, b) => {
          // Сначала события на весь день, потом по времени
          if (a.allDay && !b.allDay) return -1;
          if (!a.allDay && b.allDay) return 1;
          return a.startDateTime.localeCompare(b.startDateTime);
        })
    : [];

  const handleAddEvent = () => {
    medium();
    openEventForm();
  };

  const handleEventClick = (eventId: string) => {
    light();
    openEventDetails(eventId);
  };

  // Форматируем дату для заголовка
  const formattedDate = selectedDate
    ? format(selectedDate, 'd MMMM, EEEE', { locale: ru })
    : null;

  return (
    <div className={styles.panel}>
      {selectedDate ? (
        <>
          <div className={styles.header}>
            <h2 className={styles.title}>{formattedDate}</h2>
          </div>

          <div className={styles.content}>
            {dayEvents.length > 0 ? (
              <div className={styles.eventsList}>
                {dayEvents.map((event) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    onClick={() => handleEventClick(event.id)}
                  />
                ))}
              </div>
            ) : (
              <div className={styles.empty}>
                <span className={styles.emptyText}>{UI_TEXT.noEvents}</span>
              </div>
            )}
          </div>

          <div className={styles.footer}>
            <button className={styles.addButton} onClick={handleAddEvent}>
              {UI_TEXT.addEvent}
            </button>
          </div>
        </>
      ) : (
        <div className={styles.placeholder}>
          <span className={styles.placeholderText}>{UI_TEXT.selectDay}</span>
        </div>
      )}
    </div>
  );
}
