/**
 * UI Types - Типы для состояния интерфейса
 */

export type Theme = 'light' | 'dark';

/**
 * UIState - Состояние UI
 */
export interface UIState {
  isSideMenuOpen: boolean;
  isEventFormOpen: boolean;
  isEventDetailsOpen: boolean;
  editingEventId: string | null;     // ID редактируемого события
  viewingEventId: string | null;     // ID просматриваемого события
  theme: Theme;                      // Тема (sync с Telegram)
}

/**
 * UIActions - Действия UI
 */
export interface UIActions {
  openSideMenu: () => void;
  closeSideMenu: () => void;
  openEventForm: (eventId?: string) => void;
  closeEventForm: () => void;
  openEventDetails: (eventId: string) => void;
  closeEventDetails: () => void;
  setTheme: (theme: Theme) => void;
}

/**
 * ConfirmDialogOptions - Опции диалога подтверждения
 */
export interface ConfirmDialogOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  onConfirm: () => void;
  onCancel?: () => void;
}
