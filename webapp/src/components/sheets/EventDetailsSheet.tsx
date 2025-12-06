/**
 * EventDetailsSheet - Bottom sheet с деталями события
 * Отображает информацию о событии и кнопки действий
 */

import { Drawer } from 'vaul';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import { parseLocalDateTime } from '@utils/dateUtils';
import { useUIStore } from '@store/uiStore';
import { useEventsStore } from '@store/eventsStore';
import { useTelegramBackButton } from '@hooks/useTelegramBackButton';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { EVENT_TYPES } from '@constants/eventTypes';
import { CULTURES } from '@constants/cultures';
import { UI_TEXT } from '@constants/ui';
import styles from './EventDetailsSheet.module.css';

export function EventDetailsSheet() {
  const {
    isEventDetailsOpen,
    viewingEventId,
    closeEventDetails,
    openEventForm,
  } = useUIStore();
  const { events, deleteEvent } = useEventsStore();
  const { medium, heavy, success } = useTelegramHaptic();

  // BackButton закрывает sheet
  useTelegramBackButton(closeEventDetails, isEventDetailsOpen);

  const event = viewingEventId ? events[viewingEventId] : null;

  const handleEdit = () => {
    medium();
    closeEventDetails();
    if (viewingEventId) {
      openEventForm(viewingEventId);
    }
  };

  const handleDelete = () => {
    if (!viewingEventId) return;

    if (window.confirm(UI_TEXT.confirmDeleteText)) {
      heavy();
      deleteEvent(viewingEventId);
      success();
      closeEventDetails();
    }
  };

  if (!event) return null;

  const typeInfo = EVENT_TYPES[event.type];
  const cultureInfo = event.cultureCode ? CULTURES[event.cultureCode] : null;

  // Форматируем дату и время
  const startDate = parseLocalDateTime(event.startDateTime);
  const dateStr = format(startDate, 'd MMMM yyyy', { locale: ru });
  const timeStr = event.allDay ? 'Весь день' : format(startDate, 'HH:mm');

  const statusLabels: Record<string, string> = {
    planned: UI_TEXT.statusPlanned,
    done: UI_TEXT.statusDone,
    skipped: UI_TEXT.statusSkipped,
  };

  return (
    <Drawer.Root open={isEventDetailsOpen} onOpenChange={(open) => !open && closeEventDetails()}>
      <Drawer.Portal>
        <Drawer.Overlay className={styles.overlay} />
        <Drawer.Content className={styles.content}>
          <div className={styles.handle} />

          <Drawer.Title className={styles.title}>{event.title}</Drawer.Title>

          <div className={styles.details}>
            <div className={styles.row}>
              <span className={styles.label}>Дата</span>
              <span className={styles.value}>{dateStr}</span>
            </div>

            <div className={styles.row}>
              <span className={styles.label}>Время</span>
              <span className={styles.value}>{timeStr}</span>
            </div>

            <div className={styles.row}>
              <span className={styles.label}>Тип</span>
              <span
                className={styles.value}
                style={{ color: typeInfo?.color }}
              >
                {typeInfo?.icon} {typeInfo?.label}
              </span>
            </div>

            {cultureInfo && (
              <div className={styles.row}>
                <span className={styles.label}>Культура</span>
                <span className={styles.value}>
                  {cultureInfo.icon} {cultureInfo.label}
                </span>
              </div>
            )}

            {event.plotId && (
              <div className={styles.row}>
                <span className={styles.label}>Участок</span>
                <span className={styles.value}>{event.plotId}</span>
              </div>
            )}

            <div className={styles.row}>
              <span className={styles.label}>Статус</span>
              <span className={styles.value}>{statusLabels[event.status]}</span>
            </div>

            {event.description && (
              <div className={styles.description}>
                <span className={styles.label}>Описание</span>
                <p className={styles.descriptionText}>{event.description}</p>
              </div>
            )}
          </div>

          <div className={styles.actions}>
            <button className={styles.editButton} onClick={handleEdit}>
              {UI_TEXT.edit}
            </button>
            <button className={styles.deleteButton} onClick={handleDelete}>
              {UI_TEXT.delete}
            </button>
          </div>
        </Drawer.Content>
      </Drawer.Portal>
    </Drawer.Root>
  );
}
