/**
 * EventForm - Форма создания/редактирования события
 * Full-screen modal с полями формы
 */

import { useEffect, useCallback, useState, useRef } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { format } from 'date-fns';
import { parseLocalDateTime } from '@utils/dateUtils';
import { useUIStore } from '@store/uiStore';
import { useEventsStore } from '@store/eventsStore';
import { useCalendarStore } from '@store/calendarStore';
import { usePlantingsStore } from '@store/plantingsStore';
import { useTelegramBackButton } from '@hooks/useTelegramBackButton';
import { useTelegramMainButton } from '@hooks/useTelegramMainButton';
import { useTelegramHaptic } from '@hooks/useTelegramHaptic';
import { eventFormSchema, type EventFormValues, type EventFormInput } from '@/types/eventSchema';
import { EVENT_TYPES } from '@constants/eventTypes';
import { getCultureCode, getPlantingLabel, getCultureIconComponent } from '@constants/plantingCultures';
import { UI_TEXT } from '@constants/ui';
import styles from './EventForm.module.css';
import type { UserPlanting } from '@/types/planting';

export function EventForm() {
  const { isEventFormOpen, editingEventId, closeEventForm } = useUIStore();
  const { events, addEvent, updateEvent } = useEventsStore();
  const selectedDate = useCalendarStore((state) => state.selectedDate);
  const plantings = usePlantingsStore((state) => state.plantings);
  const { medium, light, success, error: hapticError } = useTelegramHaptic();

  // Состояние для кастомного dropdown культур
  const [isCultureDropdownOpen, setIsCultureDropdownOpen] = useState(false);
  const cultureDropdownRef = useRef<HTMLDivElement>(null);

  const editingEvent = editingEventId ? events[editingEventId] : null;
  const isEdit = !!editingEvent;

  // Дефолтные значения (input type - до трансформаций)
  const getDefaultValues = (): EventFormInput => {
    if (editingEvent) {
      const startDate = parseLocalDateTime(editingEvent.startDateTime);
      const endDate = editingEvent.endDateTime
        ? parseLocalDateTime(editingEvent.endDateTime)
        : null;
      return {
        title: editingEvent.title,
        startDate: format(startDate, 'yyyy-MM-dd'),
        startTime: editingEvent.allDay ? '' : format(startDate, 'HH:mm'),
        endDate: endDate ? format(endDate, 'yyyy-MM-dd') : '',
        endTime: endDate && !editingEvent.allDay ? format(endDate, 'HH:mm') : '',
        allDay: editingEvent.allDay,
        type: editingEvent.type,
        cultureCode: editingEvent.cultureCode || '',
        plotId: editingEvent.plotId || '',
        description: editingEvent.description || '',
      };
    }

    const defaultDate = selectedDate || new Date();
    return {
      title: '',
      startDate: format(defaultDate, 'yyyy-MM-dd'),
      startTime: '',
      endDate: '',
      endTime: '',
      allDay: true,
      type: 'nutrition',
      cultureCode: '',
      plotId: '',
      description: '',
    };
  };

  const {
    control,
    handleSubmit,
    reset,
    formState: { errors, isValid },
  } = useForm<EventFormInput, unknown, EventFormValues>({
    resolver: zodResolver(eventFormSchema),
    defaultValues: getDefaultValues(),
    mode: 'onChange',
  });

  // Reset form when opening
  useEffect(() => {
    if (isEventFormOpen) {
      reset(getDefaultValues());
      setIsCultureDropdownOpen(false);
    }
  }, [isEventFormOpen, editingEventId]);

  // Закрытие culture dropdown при клике вне
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (cultureDropdownRef.current && !cultureDropdownRef.current.contains(e.target as Node)) {
        setIsCultureDropdownOpen(false);
      }
    };
    if (isCultureDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isCultureDropdownOpen]);

  // BackButton закрывает форму
  useTelegramBackButton(() => {
    medium();
    closeEventForm();
  }, isEventFormOpen);

  // Обработчик сохранения
  const onSubmit = useCallback(async (data: EventFormValues) => {
    try {
      // Все события — весь день
      const startDateTime = `${data.startDate}T00:00:00`;
      const endDateTime = data.endDate ? `${data.endDate}T23:59:59` : null;

      if (isEdit && editingEventId) {
        await updateEvent(editingEventId, {
          title: data.title,
          startDateTime,
          endDateTime,
          allDay: true,
          type: data.type,
          cultureCode: data.cultureCode,
          plotId: data.plotId,
          description: data.description,
        });
      } else {
        await addEvent({
          title: data.title,
          startDateTime,
          endDateTime,
          allDay: true,
          type: data.type,
          cultureCode: data.cultureCode,
          plotId: data.plotId,
          status: 'planned',
          description: data.description,
        });
      }

      success();
      closeEventForm();
    } catch (err) {
      console.error('Failed to save event:', err);
      hapticError();
    }
  }, [isEdit, editingEventId, updateEvent, addEvent, success, closeEventForm, hapticError]);

  // MainButton для сохранения
  const handleSave = useCallback(() => {
    // Используем handleSubmit для корректной валидации и трансформации
    handleSubmit(onSubmit)();
  }, [handleSubmit, onSubmit]);

  useTelegramMainButton(
    isEventFormOpen
      ? {
          text: UI_TEXT.save,
          onClick: handleSave,
          enabled: isValid,
          visible: true,
        }
      : null
  );

  if (!isEventFormOpen) return null;

  return (
    <div className={styles.modal}>
      <header className={styles.header}>
        <button
          type="button"
          className={styles.cancelButton}
          onClick={closeEventForm}
          onTouchEnd={(e) => {
            e.preventDefault();
            closeEventForm();
          }}
        >
          {UI_TEXT.cancel}
        </button>
        <h1 className={styles.title}>
          {isEdit ? UI_TEXT.formTitleEdit : UI_TEXT.formTitleCreate}
        </h1>
        <button
          type="button"
          className={styles.saveButton}
          onClick={handleSave}
          onTouchEnd={(e) => {
            e.preventDefault();
            handleSave();
          }}
        >
          {UI_TEXT.save}
        </button>
      </header>

      <form className={styles.form} onSubmit={(e) => e.preventDefault()}>
        {/* Title */}
        <div className={styles.field}>
          <label className={styles.label}>{UI_TEXT.fieldTitle}</label>
          <Controller
            name="title"
            control={control}
            render={({ field }) => (
              <input
                {...field}
                type="text"
                className={`${styles.input} ${errors.title ? styles.inputError : ''}`}
                placeholder="Введите название"
              />
            )}
          />
          {errors.title && (
            <span className={styles.error}>{errors.title.message}</span>
          )}
        </div>

        {/* Date Range Section */}
        <div className={styles.dateSection}>
          {/* Start Date */}
          <div className={styles.dateRow}>
            <span className={styles.dateLabel}>С</span>
            <Controller
              name="startDate"
              control={control}
              render={({ field }) => (
                <input
                  {...field}
                  type="date"
                  className={styles.dateInput}
                />
              )}
            />
          </div>

          {/* End Date */}
          <div className={styles.dateRow}>
            <span className={styles.dateLabel}>До</span>
            <Controller
              name="endDate"
              control={control}
              render={({ field }) => (
                <input
                  {...field}
                  type="date"
                  className={styles.dateInput}
                  placeholder="Не указано"
                />
              )}
            />
          </div>
        </div>

        {/* Type */}
        <div className={styles.field}>
          <label className={styles.label}>{UI_TEXT.fieldType}</label>
          <Controller
            name="type"
            control={control}
            render={({ field }) => (
              <select {...field} className={styles.select}>
                {Object.entries(EVENT_TYPES).map(([key, info]) => (
                  <option key={key} value={key}>
                    {info.icon} {info.label}
                  </option>
                ))}
              </select>
            )}
          />
        </div>

        {/* Culture - Custom dropdown with SVG icons */}
        <div className={styles.field}>
          <label className={styles.label}>{UI_TEXT.fieldCulture}</label>
          <Controller
            name="cultureCode"
            control={control}
            render={({ field }) => {
              // Найти текущую посадку по cultureCode
              const selectedPlanting = plantings.find(
                (p: UserPlanting) => getCultureCode(p) === field.value
              );
              const SelectedIcon = selectedPlanting
                ? getCultureIconComponent(selectedPlanting.cultureType)
                : null;

              return (
                <div className={styles.cultureDropdown} ref={cultureDropdownRef}>
                  <button
                    type="button"
                    className={styles.cultureButton}
                    onClick={() => {
                      light();
                      setIsCultureDropdownOpen(!isCultureDropdownOpen);
                    }}
                  >
                    {selectedPlanting && SelectedIcon ? (
                      <>
                        <span className={styles.cultureButtonIcon}>
                          <SelectedIcon width={24} height={24} />
                        </span>
                        <span className={styles.cultureButtonLabel}>
                          {getPlantingLabel(selectedPlanting)}
                        </span>
                      </>
                    ) : (
                      <span className={styles.cultureButtonPlaceholder}>
                        {plantings.length > 0 ? 'Не выбрано' : 'Сначала добавьте посадки'}
                      </span>
                    )}
                    <ChevronIcon
                      className={`${styles.cultureButtonChevron} ${isCultureDropdownOpen ? styles.cultureButtonChevronOpen : ''}`}
                    />
                  </button>

                  {isCultureDropdownOpen && plantings.length > 0 && (
                    <ul className={styles.cultureDropdownList}>
                      {/* Option "Не выбрано" */}
                      <li
                        className={`${styles.cultureOption} ${!field.value ? styles.cultureOptionSelected : ''}`}
                        onClick={() => {
                          light();
                          field.onChange('');
                          setIsCultureDropdownOpen(false);
                        }}
                      >
                        <span className={styles.cultureOptionLabel}>Не выбрано</span>
                      </li>
                      {/* Посадки пользователя */}
                      {plantings.map((planting: UserPlanting) => {
                        const CultureIcon = getCultureIconComponent(planting.cultureType);
                        const cultureCode = getCultureCode(planting);
                        return (
                          <li
                            key={planting.id}
                            className={`${styles.cultureOption} ${field.value === cultureCode ? styles.cultureOptionSelected : ''}`}
                            onClick={() => {
                              light();
                              field.onChange(cultureCode);
                              setIsCultureDropdownOpen(false);
                            }}
                          >
                            <span className={styles.cultureOptionIcon}>
                              <CultureIcon width={24} height={24} />
                            </span>
                            <span className={styles.cultureOptionLabel}>
                              {getPlantingLabel(planting)}
                            </span>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>
              );
            }}
          />
        </div>

        {/* Plot */}
        <div className={styles.field}>
          <label className={styles.label}>{UI_TEXT.fieldPlot}</label>
          <Controller
            name="plotId"
            control={control}
            render={({ field }) => (
              <input
                {...field}
                value={field.value || ''}
                type="text"
                className={styles.input}
                placeholder="Например: Участок 1"
              />
            )}
          />
        </div>

        {/* Description */}
        <div className={styles.field}>
          <label className={styles.label}>{UI_TEXT.fieldDescription}</label>
          <Controller
            name="description"
            control={control}
            render={({ field }) => (
              <textarea
                {...field}
                value={field.value || ''}
                className={styles.textarea}
                placeholder="Добавьте описание"
                rows={3}
              />
            )}
          />
        </div>
      </form>
    </div>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      className={className}
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}
