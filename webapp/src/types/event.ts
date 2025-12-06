/**
 * Event Types - Типы событий в календаре
 */

export type EventType =
  | 'nutrition'   // Питание растений
  | 'soil'        // Улучшение почвы
  | 'protection'  // Защита растений
  | 'harvest'     // Сбор урожая
  | 'planting'    // Посадка
  | 'other';      // Прочее

export type EventStatus =
  | 'planned'     // Запланировано
  | 'done'        // Выполнено
  | 'skipped';    // Пропущено

/**
 * CalendarEvent - Основная модель события
 */
export interface CalendarEvent {
  id: string;                        // UUID v4
  title: string;                     // Заголовок (обязательно)
  startDateTime: string;             // ISO 8601
  endDateTime: string | null;        // ISO 8601 или null
  allDay: boolean;                   // Событие на весь день
  type: EventType;                   // Тип события
  cultureCode?: string;              // Код культуры (клубника ремонтантная, малина летняя...)
  plotId?: string;                   // Название участка (свободный ввод)
  status: EventStatus;               // Статус выполнения
  color?: string;                    // Hex-цвет (опционально, для кастомизации)
  description?: string;              // Описание
  tags?: string[];                   // Теги
  createdAt: string;                 // ISO 8601
  updatedAt: string;                 // ISO 8601
}

/**
 * EventFormData - Данные формы создания/редактирования события
 */
export interface EventFormData {
  title: string;
  startDate: string;                 // YYYY-MM-DD
  startTime: string;                 // HH:mm
  endDate: string;                   // YYYY-MM-DD
  endTime: string;                   // HH:mm
  allDay: boolean;
  type: EventType;
  cultureCode: string;
  plotId: string;
  description: string;
}

/**
 * EventTypeInfo - Метаданные типа события
 */
export interface EventTypeInfo {
  label: string;
  color: string;
  icon: string;
}

/**
 * CultureInfo - Метаданные культуры
 */
export interface CultureInfo {
  label: string;
  icon: string;
}
