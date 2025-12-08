/**
 * DayEventsPanel - Панель событий выбранного дня
 * Показывает детали выбранного события или список событий дня
 */

import { useMemo } from 'react';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { formatDateForInput, parseLocalDateTime } from '@utils/dateUtils';
import { useCalendarStore } from '@store/calendarStore';
import { useEventsStore } from '@store/eventsStore';
import { useUIStore } from '@store/uiStore';
import { useTelegramHaptic, useFilteredEvents } from '@hooks/index';
import { EVENT_TYPES } from '@constants/eventTypes';
import { getCultureIconFromCode, getCultureTypeFromCode, getCultureConfig } from '@constants/plantingCultures';
import { UI_TEXT } from '@constants/ui';
import { EventCard } from './EventCard';
import styles from './DayEventsPanel.module.css';

export function DayEventsPanel() {
  const selectedDate = useCalendarStore((state) => state.selectedDate);
  const allEvents = useEventsStore((state) => state.events);
  const filteredEvents = useFilteredEvents();
  const deleteEvent = useEventsStore((state) => state.deleteEvent);
  const { openEventForm, selectedEventId, selectEvent } = useUIStore();
  const { light, medium, heavy, success } = useTelegramHaptic();

  // Получаем отфильтрованные события для выбранной даты (включая многодневные)
  const dayEvents = useMemo(() => {
    if (!selectedDate) return [];
    const selectedStr = formatDateForInput(selectedDate);
    return filteredEvents
      .filter((event) => {
        const startStr = event.startDateTime.slice(0, 10);
        const endStr = event.endDateTime?.slice(0, 10) || startStr;
        // Событие попадает в день если: start <= selected <= end
        return startStr <= selectedStr && selectedStr <= endStr;
      })
      .sort((a, b) => {
        // Сначала события на весь день, потом по времени
        if (a.allDay && !b.allDay) return -1;
        if (!a.allDay && b.allDay) return 1;
        return a.startDateTime.localeCompare(b.startDateTime);
      });
  }, [selectedDate, filteredEvents]);

  // Выбранное событие
  const selectedEvent = selectedEventId ? allEvents[selectedEventId] : null;

  const handleAddEvent = () => {
    medium();
    openEventForm();
  };

  const handleEventClick = (eventId: string) => {
    light();
    selectEvent(eventId);
  };

  const handleEdit = () => {
    if (!selectedEventId) return;
    medium();
    openEventForm(selectedEventId);
  };

  const handleDelete = () => {
    if (!selectedEventId) return;
    if (window.confirm(UI_TEXT.confirmDeleteText)) {
      heavy();
      deleteEvent(selectedEventId);
      success();
      selectEvent(null);
    }
  };

  const handleBack = () => {
    light();
    selectEvent(null);
  };

  // Форматируем дату для заголовка
  const formattedDate = selectedDate
    ? format(selectedDate, 'd MMMM, EEEE', { locale: ru })
    : null;

  // Если выбрано событие - показываем его детали
  if (selectedEvent) {
    const typeInfo = EVENT_TYPES[selectedEvent.type];
    const CultureIcon = selectedEvent.cultureCode ? getCultureIconFromCode(selectedEvent.cultureCode) : null;
    const cultureType = selectedEvent.cultureCode ? getCultureTypeFromCode(selectedEvent.cultureCode) : null;
    const cultureConfig = cultureType ? getCultureConfig(cultureType) : null;
    const startDate = parseLocalDateTime(selectedEvent.startDateTime);
    const endDate = selectedEvent.endDateTime ? parseLocalDateTime(selectedEvent.endDateTime) : null;
    const startDateStr = format(startDate, 'd MMMM', { locale: ru });
    const endDateStr = endDate ? format(endDate, 'd MMMM', { locale: ru }) : null;
    const hasEndDate = endDate && endDateStr !== startDateStr;

    const statusLabels: Record<string, string> = {
      planned: UI_TEXT.statusPlanned,
      done: UI_TEXT.statusDone,
      skipped: UI_TEXT.statusSkipped,
    };

    return (
      <div className={styles.panel}>
        <div className={styles.header}>
          <button className={styles.backButton} onClick={handleBack}>
            ← Назад
          </button>
        </div>

        <div className={styles.content}>
          <div className={styles.eventDetails}>
            <h2 className={styles.eventTitle}>{selectedEvent.title}</h2>

            <div className={styles.detailsGrid}>
              <div className={styles.detailRow}>
                <span className={styles.detailLabel}>{hasEndDate ? 'С' : 'Дата'}</span>
                <span className={styles.detailValue}>{startDateStr}</span>
              </div>

              {hasEndDate && (
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>До</span>
                  <span className={styles.detailValue}>{endDateStr}</span>
                </div>
              )}

              <div className={styles.detailRow}>
                <span className={styles.detailLabel}>Тип</span>
                <span className={styles.detailValue} style={{ color: typeInfo?.color }}>
                  {typeInfo?.icon} {typeInfo?.label}
                </span>
              </div>

              {CultureIcon && cultureConfig && (
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Культура</span>
                  <span className={`${styles.detailValue} ${styles.cultureValue}`}>
                    <CultureIcon width={20} height={20} />
                    {cultureConfig.label}
                  </span>
                </div>
              )}

              {selectedEvent.plotId && (
                <div className={styles.detailRow}>
                  <span className={styles.detailLabel}>Участок</span>
                  <span className={styles.detailValue}>{selectedEvent.plotId}</span>
                </div>
              )}

              <div className={styles.detailRow}>
                <span className={styles.detailLabel}>Статус</span>
                <span className={styles.detailValue}>{statusLabels[selectedEvent.status]}</span>
              </div>

              {selectedEvent.description && (
                <div className={styles.detailRowFull}>
                  <span className={styles.detailLabel}>Описание</span>
                  <p className={styles.description}>{selectedEvent.description}</p>
                </div>
              )}
            </div>
          </div>
        </div>

        <div className={styles.footer}>
          <div className={styles.actions}>
            <button className={styles.editButton} onClick={handleEdit}>
              {UI_TEXT.edit}
            </button>
            <button className={styles.deleteButton} onClick={handleDelete}>
              {UI_TEXT.delete}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Иначе показываем список событий
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
