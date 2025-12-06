/**
 * Calendar Types - Типы для состояния календаря
 */

export type ViewMode = 'month' | 'year';

/**
 * CalendarState - Состояние календаря
 */
export interface CalendarState {
  currentDate: Date;                 // Текущий отображаемый месяц
  selectedDate: Date | null;         // Выбранный день
  viewMode: ViewMode;                // Режим отображения (year — отложено на будущее)
}

/**
 * CalendarActions - Действия календаря
 */
export interface CalendarActions {
  setCurrentDate: (date: Date) => void;
  setSelectedDate: (date: Date | null) => void;
  goToNextMonth: () => void;
  goToPrevMonth: () => void;
  goToToday: () => void;
  setViewMode: (mode: ViewMode) => void;
}

/**
 * DayInfo - Информация о дне в сетке
 */
export interface DayInfo {
  date: Date;
  isCurrentMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
  isWeekend: boolean;
}

/**
 * WeekDay - День недели
 */
export interface WeekDay {
  short: string;   // Пн
  full: string;    // Понедельник
  index: number;   // 0-6
}
