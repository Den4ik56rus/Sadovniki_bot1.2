/**
 * EventForm - Форма создания/редактирования события
 * Full-screen modal с полями формы
 */

import { useEffect, useCallback } from 'react';
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
import { getCultureCode, getPlantingLabel, getCultureIcon } from '@constants/plantingCultures';
import { UI_TEXT } from '@constants/ui';
import styles from './EventForm.module.css';
import type { UserPlanting } from '@/types/planting';

export function EventForm() {
  const { isEventFormOpen, editingEventId, closeEventForm } = useUIStore();
  const { events, addEvent, updateEvent } = useEventsStore();
  const selectedDate = useCalendarStore((state) => state.selectedDate);
  const plantings = usePlantingsStore((state) => state.plantings);
  const { medium, success, error: hapticError } = useTelegramHaptic();

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
      startTime: '09:00',
      endDate: '',
      endTime: '',
      allDay: false,
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
    watch,
    formState: { errors, isValid },
  } = useForm<EventFormInput, unknown, EventFormValues>({
    resolver: zodResolver(eventFormSchema),
    defaultValues: getDefaultValues(),
    mode: 'onChange',
  });

  const allDay = watch('allDay');

  // Reset form when opening
  useEffect(() => {
    if (isEventFormOpen) {
      reset(getDefaultValues());
    }
  }, [isEventFormOpen, editingEventId]);

  // BackButton закрывает форму
  useTelegramBackButton(() => {
    medium();
    closeEventForm();
  }, isEventFormOpen);

  // Обработчик сохранения
  const onSubmit = useCallback((data: EventFormValues) => {
    try {
      const startDateTime = data.allDay
        ? `${data.startDate}T00:00:00`
        : `${data.startDate}T${data.startTime}:00`;

      const endDateTime = data.endDate
        ? data.allDay
          ? `${data.endDate}T23:59:59`
          : `${data.endDate}T${data.endTime || '23:59'}:00`
        : null;

      if (isEdit && editingEventId) {
        updateEvent(editingEventId, {
          title: data.title,
          startDateTime,
          endDateTime,
          allDay: data.allDay,
          type: data.type,
          cultureCode: data.cultureCode,
          plotId: data.plotId,
          description: data.description,
        });
      } else {
        addEvent({
          title: data.title,
          startDateTime,
          endDateTime,
          allDay: data.allDay,
          type: data.type,
          cultureCode: data.cultureCode,
          plotId: data.plotId,
          status: 'planned',
          description: data.description,
        });
      }

      success();
      closeEventForm();
    } catch {
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

        {/* All Day */}
        <div className={styles.fieldRow}>
          <label className={styles.label}>{UI_TEXT.fieldAllDay}</label>
          <Controller
            name="allDay"
            control={control}
            render={({ field }) => (
              <input
                type="checkbox"
                checked={field.value}
                onChange={field.onChange}
                className={styles.checkbox}
              />
            )}
          />
        </div>

        {/* Date Range Section */}
        <div className={styles.dateSection}>
          {/* Start Date/Time */}
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
            {!allDay && (
              <Controller
                name="startTime"
                control={control}
                render={({ field }) => (
                  <input
                    {...field}
                    type="time"
                    className={styles.timeInput}
                  />
                )}
              />
            )}
          </div>

          {/* End Date/Time */}
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
            {!allDay && (
              <Controller
                name="endTime"
                control={control}
                render={({ field }) => (
                  <input
                    {...field}
                    type="time"
                    className={styles.timeInput}
                  />
                )}
              />
            )}
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

        {/* Culture */}
        <div className={styles.field}>
          <label className={styles.label}>{UI_TEXT.fieldCulture}</label>
          <Controller
            name="cultureCode"
            control={control}
            render={({ field }) => (
              <select {...field} value={field.value || ''} className={styles.select}>
                <option value="">Не выбрано</option>
                {plantings.length > 0 ? (
                  plantings.map((planting: UserPlanting) => (
                    <option key={planting.id} value={getCultureCode(planting)}>
                      {getCultureIcon(planting.cultureType)} {getPlantingLabel(planting)}
                    </option>
                  ))
                ) : (
                  <option value="" disabled>
                    Сначала добавьте посадки
                  </option>
                )}
              </select>
            )}
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
